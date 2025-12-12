"""
Database setup and CRUD functions for Inventory Manager.
Uses SQLite with parameterized queries for SQL injection protection.

SECURITY FEATURES (Stage 3):
1. SQL Injection Protection: All queries use parameterized statements (prepared statements)
   with '?' placeholders instead of string concatenation. This prevents SQL injection attacks.
   
2. Database Indexes: 
   - idx_products_category_id: Optimizes JOINs and WHERE clauses on category_id
   - idx_products_name: Optimizes ORDER BY name queries
   
3. Transactions with SERIALIZABLE Isolation: Ensures ACID properties and prevents
   concurrency issues (dirty reads, non-repeatable reads, phantom reads) when multiple
   users access the database simultaneously.
"""

import sqlite3
import os
from typing import List, Tuple, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), 'data.db')


def get_connection():
    """Get a database connection with SERIALIZABLE isolation level for transaction safety.
    
    SQLite uses SERIALIZABLE isolation by default, which prevents:
    - Dirty reads: Cannot read uncommitted data from other transactions
    - Non-repeatable reads: Repeated reads within a transaction see consistent data
    - Phantom reads: Range queries see consistent results within a transaction
    
    This ensures ACID properties and prevents concurrency issues when multiple users
    access the database simultaneously. We use isolation_level=None to enable manual
    transaction control with BEGIN TRANSACTION statements.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    # Enable WAL mode for better concurrency (if supported)
    # WAL mode allows multiple readers and one writer simultaneously
    try:
        conn.execute('PRAGMA journal_mode=WAL')
    except Exception:
        pass  # WAL mode not supported, continue with default
    return conn


def init_db():
    """Initialize the database with Categories and Products tables, and create indexes.
    
    Indexes created:
    1. idx_products_category_id: Speeds up JOINs and WHERE clauses filtering by category
    2. idx_products_name: Speeds up ORDER BY name queries
    3. idx_categories_name: Speeds up category name lookups (UNIQUE constraint also creates an index)
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Begin transaction for atomic table and index creation
    cursor.execute('BEGIN TRANSACTION')
    
    try:
        # Create Categories table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Categories (
                category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        ''')
        
        # Create Products table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Products (
                product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0,
                category_id INTEGER NOT NULL,
                FOREIGN KEY (category_id) REFERENCES Categories(category_id)
            )
        ''')
        
        # Create indexes to optimize common queries
        # Index 1: Products.category_id - Used in JOINs and WHERE clauses
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_products_category_id 
            ON Products(category_id)
        ''')
        
        # Index 2: Products.name - Used in ORDER BY name queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_products_name 
            ON Products(name)
        ''')
        
        # Index 3: Categories.name - Already has UNIQUE index, but explicit for clarity
        # Note: UNIQUE constraint automatically creates an index, but we document it
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# Category CRUD operations
def get_all_categories() -> List[Tuple[int, str]]:
    """Get all categories as (category_id, name) tuples."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT category_id, name FROM Categories ORDER BY category_id')
    categories = cursor.fetchall()
    conn.close()
    return [(row[0], row[1]) for row in categories]


def add_category(name: str) -> bool:
    """Add a new category. Returns True if successful, False if name already exists."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO Categories (name) VALUES (?)', (name,))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def delete_category(category_id: int) -> bool:
    """Delete a category. Returns True if successful, False if category has products or doesn't exist.
    Automatically resets sequence to 0 if this is the last category.
    
    Uses a transaction with SERIALIZABLE isolation to ensure atomicity:
    - Checks if category has products (uses idx_products_category_id index)
    - Deletes category if safe
    - Resets sequence if table becomes empty
    All operations are atomic - either all succeed or all fail.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Begin transaction for atomic multi-step operation
        cursor.execute('BEGIN TRANSACTION')
        
        # Check if category has products (benefits from idx_products_category_id index)
        cursor.execute('SELECT COUNT(*) FROM Products WHERE category_id = ?', (category_id,))
        product_count = cursor.fetchone()[0]
        
        if product_count > 0:
            conn.rollback()
            conn.close()
            return False  # Cannot delete category with products
        
        # Delete the category
        cursor.execute('DELETE FROM Categories WHERE category_id = ?', (category_id,))
        
        # Check if table is now empty and reset sequence
        cursor.execute('SELECT COUNT(*) FROM Categories')
        remaining_count = cursor.fetchone()[0]
        if remaining_count == 0:
            cursor.execute('DELETE FROM sqlite_sequence WHERE name = "Categories"')
            cursor.execute('INSERT INTO sqlite_sequence (name, seq) VALUES ("Categories", 0)')
        
        conn.commit()
        conn.close()
        return True
    except Exception:
        if conn:
            conn.rollback()
            conn.close()
        return False


# Product CRUD operations
def get_all_products() -> List[sqlite3.Row]:
    """Get all products with their category names.
    
    Query benefits from indexes:
    - idx_products_category_id: Speeds up JOIN on Products.category_id = Categories.category_id
    - idx_products_name: Speeds up ORDER BY p.name
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.product_id, p.name, p.price, p.stock, p.category_id, c.name as category_name
        FROM Products p
        JOIN Categories c ON p.category_id = c.category_id
        ORDER BY p.name
    ''')
    products = cursor.fetchall()
    conn.close()
    return products


def get_products_by_category(category_id: Optional[int] = None, category_ids: Optional[List[int]] = None) -> List[sqlite3.Row]:
    """Get products, optionally filtered by category_id or list of category_ids.
    
    Query benefits from indexes:
    - idx_products_category_id: Speeds up WHERE p.category_id = ? and WHERE p.category_id IN (...)
    - idx_products_category_id: Speeds up JOIN on Products.category_id = Categories.category_id
    - idx_products_name: Speeds up ORDER BY p.name
    Used in: Reports page for filtering products by category
    """
    conn = get_connection()
    cursor = conn.cursor()
    if category_ids and len(category_ids) > 0:
        # Filter by multiple categories
        placeholders = ','.join('?' * len(category_ids))
        cursor.execute(f'''
            SELECT p.product_id, p.name, p.price, p.stock, p.category_id, c.name as category_name
            FROM Products p
            JOIN Categories c ON p.category_id = c.category_id
            WHERE p.category_id IN ({placeholders})
            ORDER BY p.name
        ''', tuple(category_ids))
    elif category_id:
        cursor.execute('''
            SELECT p.product_id, p.name, p.price, p.stock, p.category_id, c.name as category_name
            FROM Products p
            JOIN Categories c ON p.category_id = c.category_id
            WHERE p.category_id = ?
            ORDER BY p.name
        ''', (category_id,))
    else:
        cursor.execute('''
            SELECT p.product_id, p.name, p.price, p.stock, p.category_id, c.name as category_name
            FROM Products p
            JOIN Categories c ON p.category_id = c.category_id
            ORDER BY p.name
        ''')
    products = cursor.fetchall()
    conn.close()
    return products


def add_product(name: str, price: float, stock: int, category_id: int) -> bool:
    """Add a new product. Returns True if successful."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO Products (name, price, stock, category_id)
            VALUES (?, ?, ?, ?)
        ''', (name, price, stock, category_id))
        conn.commit()
        conn.close()
        return True
    except Exception:
        if conn:
            conn.close()
        return False


def update_product(product_id: int, name: str, price: float, stock: int, category_id: int) -> bool:
    """Update an existing product. Returns True if successful.
    
    Uses a transaction with SERIALIZABLE isolation to ensure atomicity.
    In a concurrent scenario, if two users try to update the same product simultaneously,
    the SERIALIZABLE isolation level ensures that one transaction completes before the other
    begins, preventing lost updates and maintaining data consistency.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Begin transaction for atomic operation
        cursor.execute('BEGIN TRANSACTION')
        
        cursor.execute('''
            UPDATE Products
            SET name = ?, price = ?, stock = ?, category_id = ?
            WHERE product_id = ?
        ''', (name, price, stock, category_id, product_id))
        
        conn.commit()
        conn.close()
        return True
    except Exception:
        if conn:
            conn.rollback()
            conn.close()
        return False


def delete_product(product_id: int) -> bool:
    """Delete a product. Returns True if successful.
    Automatically resets sequence to 0 if this is the last product.
    
    Uses a transaction with SERIALIZABLE isolation to ensure atomicity:
    - Deletes the product
    - Checks if table is empty and resets sequence if needed
    All operations are atomic - either all succeed or all fail.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Begin transaction for atomic multi-step operation
        cursor.execute('BEGIN TRANSACTION')
        
        cursor.execute('DELETE FROM Products WHERE product_id = ?', (product_id,))
        
        # Check if table is now empty and reset sequence
        cursor.execute('SELECT COUNT(*) FROM Products')
        remaining_count = cursor.fetchone()[0]
        if remaining_count == 0:
            cursor.execute('DELETE FROM sqlite_sequence WHERE name = "Products"')
            cursor.execute('INSERT INTO sqlite_sequence (name, seq) VALUES ("Products", 0)')
        
        conn.commit()
        conn.close()
        return True
    except Exception:
        if conn:
            conn.rollback()
            conn.close()
        return False


def get_product_by_id(product_id: int) -> Optional[sqlite3.Row]:
    """Get a single product by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.product_id, p.name, p.price, p.stock, p.category_id, c.name as category_name
        FROM Products p
        JOIN Categories c ON p.category_id = c.category_id
        WHERE p.product_id = ?
    ''', (product_id,))
    product = cursor.fetchone()
    conn.close()
    return product


# Report functions
def get_category_report(category_id: Optional[int] = None, category_ids: Optional[List[int]] = None) -> dict:
    """Get report metrics for products, optionally filtered by category or list of categories.
    Returns dict with avg_price, total_stock, total_value.
    
    Query benefits from indexes:
    - idx_products_category_id: Speeds up WHERE category_id = ? and WHERE category_id IN (...)
    Used in: Reports page for calculating aggregate statistics (average price, total stock, total value)
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if category_ids and len(category_ids) > 0:
        # Filter by multiple categories
        placeholders = ','.join('?' * len(category_ids))
        cursor.execute(f'''
            SELECT 
                ROUND(AVG(price), 2) as avg_price,
                SUM(stock) as total_stock,
                SUM(price * stock) as total_value
            FROM Products
            WHERE category_id IN ({placeholders})
        ''', tuple(category_ids))
    elif category_id:
        cursor.execute('''
            SELECT 
                ROUND(AVG(price), 2) as avg_price,
                SUM(stock) as total_stock,
                SUM(price * stock) as total_value
            FROM Products
            WHERE category_id = ?
        ''', (category_id,))
    else:
        cursor.execute('''
            SELECT 
                ROUND(AVG(price), 2) as avg_price,
                SUM(stock) as total_stock,
                SUM(price * stock) as total_value
            FROM Products
        ''')
    
    result = cursor.fetchone()
    conn.close()
    
    # Ensure avg_price is properly rounded
    avg_price = round(float(result[0]), 2) if result[0] is not None else 0.0
    
    return {
        'avg_price': avg_price,
        'total_stock': result[1] if result[1] is not None else 0,
        'total_value': result[2] if result[2] is not None else 0.0
    }

