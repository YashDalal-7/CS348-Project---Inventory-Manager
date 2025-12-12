# Inventory Manager - CS348 Project Stage 3

A Streamlit-based inventory management application with SQL injection protection, database indexes, and transaction support.

## Features

- **SQL Injection Protection**: All queries use parameterized statements (prepared statements)
- **Database Indexes**: Optimized queries with indexes on `category_id` and `name` columns
- **Transactions**: SERIALIZABLE isolation level for concurrent access safety
- **CRUD Operations**: Full create, read, update, delete for products and categories
- **Reports**: Category-based inventory reports with filtering

## Setup

1. Install dependencies:
```bash
pip install streamlit pandas
```

2. Run the application:
```bash
streamlit run app.py
```

3. The app will open in your browser at `http://localhost:8501`

## Database

- SQLite database (`data.db`) - created automatically on first run
- Tables: `Categories`, `Products`
- Indexes: `idx_products_category_id`, `idx_products_name`

## Stage 3 Implementation

### SQL Injection Protection
All database queries use parameterized statements with `?` placeholders. See `db.py` for examples.

### Indexes
- `idx_products_category_id`: Optimizes JOINs and WHERE clauses on category_id
- `idx_products_name`: Optimizes ORDER BY name queries

### Transactions
- SERIALIZABLE isolation level (SQLite default)
- Explicit transactions for multi-step operations
- WAL mode enabled for better concurrency

## Files

- `app.py`: Streamlit UI application
- `db.py`: Database operations and schema
- `DATABASE_DESIGN.txt`: Database schema documentation

