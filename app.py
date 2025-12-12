"""
Streamlit UI for Local Store Inventory Manager.
Provides CRUD interface for products and category-based reports.
"""

import streamlit as st
import pandas as pd

# Page configuration - MUST be first Streamlit command
st.set_page_config(
    page_title="Inventory Manager",
    page_icon="📦",
    layout="wide"
)

from db import (
    init_db, get_all_categories, add_category, delete_category,
    get_all_products, get_products_by_category, 
    add_product, update_product, delete_product, get_product_by_id,
    get_category_report, get_connection
)
import sqlite3

# Initialize database on app start
init_db()

st.title("📦 Local Store Inventory Manager")
st.markdown("---")

# Sidebar for navigation
page = st.sidebar.radio(
    "Navigation",
    ["Products", "Categories", "Reports", "Testing"]
)

# Initialize session state for form modes
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False
if 'editing_product_id' not in st.session_state:
    st.session_state.editing_product_id = None

# Helper function to reset form state
def reset_form():
    st.session_state.edit_mode = False
    st.session_state.editing_product_id = None

# PRODUCTS PAGE (CRUD)
if page == "Products":
    st.header("Product Management")
    
    # Get all categories for dropdown
    categories = get_all_categories()
    category_dict = {name: cat_id for cat_id, name in categories}
    
    if not categories:
        st.warning("⚠️ No categories found. Please add categories first in the Categories page.")
        st.info("💡 Go to the 'Categories' page in the sidebar to add your first category.")
    
    # Add/Edit Product Form
    if categories:
        # Load product data if in edit mode
        edit_product = None
        if st.session_state.edit_mode and st.session_state.editing_product_id:
            edit_product = get_product_by_id(st.session_state.editing_product_id)
        
        with st.expander("➕ Add New Product" if not st.session_state.edit_mode else "✏️ Edit Product", expanded=st.session_state.edit_mode):
            with st.form("product_form", clear_on_submit=not st.session_state.edit_mode):
                # Pre-populate form fields if editing
                default_name = edit_product['name'] if edit_product else ""
                default_price = float(edit_product['price']) if edit_product else 0.0
                default_stock = int(edit_product['stock']) if edit_product else 0
                default_category = edit_product['category_name'] if edit_product else list(category_dict.keys())[0]
                
                # Find the index of the default category
                category_options = list(category_dict.keys())
                default_category_index = category_options.index(default_category) if default_category in category_options else 0
                
                product_name = st.text_input("Product Name *", value=default_name)
                col1, col2 = st.columns(2)
                with col1:
                    product_price = st.number_input("Price *", min_value=0.0, value=default_price, step=0.01, format="%.2f")
                with col2:
                    product_stock = st.number_input("Stock *", min_value=0, value=default_stock, step=1)
                
                product_category = st.selectbox(
                    "Category *",
                    options=category_options,
                    index=default_category_index
                )
                
                submitted = st.form_submit_button("Save Product" if st.session_state.edit_mode else "Add Product")
                
                if submitted:
                    if product_name.strip():
                        category_id = category_dict[product_category]
                        if st.session_state.edit_mode:
                            success = update_product(
                                st.session_state.editing_product_id,
                                product_name.strip(),
                                product_price,
                                product_stock,
                                category_id
                            )
                            if success:
                                st.success("✅ Product updated successfully!")
                                reset_form()
                                st.rerun()
                            else:
                                st.error("❌ Failed to update product.")
                        else:
                            success = add_product(
                                product_name.strip(),
                                product_price,
                                product_stock,
                                category_id
                            )
                            if success:
                                st.success("✅ Product added successfully!")
                                st.rerun()
                            else:
                                st.error("❌ Failed to add product.")
                    else:
                        st.error("❌ Product name is required.")
    
    # Products Table
    st.subheader("All Products")
    products = get_all_products()
    
    if products:
        # Convert to DataFrame for display
        df = pd.DataFrame([{
            'ID': p['product_id'],
            'Name': p['name'],
            'Price': f"${p['price']:.2f}",
            'Stock': p['stock'],
            'Category': p['category_name']
        } for p in products])
        
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Edit/Delete Actions
        st.subheader("Edit or Delete Product")
        product_options = {f"{p['name']} (ID: {p['product_id']})": p['product_id'] for p in products}
        selected_product_key = st.selectbox("Select a product to edit or delete:", options=list(product_options.keys()))
        
        if selected_product_key:
            selected_product_id = product_options[selected_product_key]
            product = get_product_by_id(selected_product_id)
            
            if product:
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("✏️ Edit Product", use_container_width=True):
                        st.session_state.edit_mode = True
                        st.session_state.editing_product_id = selected_product_id
                        st.rerun()
                
                with col2:
                    if st.button("🗑️ Delete Product", use_container_width=True, type="primary"):
                        if delete_product(selected_product_id):
                            st.success("✅ Product deleted successfully!")
                            reset_form()
                            st.rerun()
                        else:
                            st.error("❌ Failed to delete product.")
    else:
        st.info("No products found. Add your first product using the form above.")

# REPORTS PAGE
elif page == "Reports":
    st.header("📊 Inventory Reports")
    
    categories = get_all_categories()
    category_dict = {name: cat_id for cat_id, name in categories}
    
    # Category filter - multi-select
    if categories:
        category_options = list(category_dict.keys())
        selected_category_names = st.multiselect(
            "Filter by Categories (select multiple):",
            options=category_options,
            default=[]
        )
        
        # Get report data
        if not selected_category_names:
            category_ids = None
            category_name = "All Categories"
        else:
            category_ids = [category_dict[name] for name in selected_category_names]
            category_name = ", ".join(selected_category_names) if len(selected_category_names) <= 3 else f"{len(selected_category_names)} categories"
    else:
        selected_category_names = []
        category_ids = None
        category_name = "All Categories"
        st.warning("⚠️ No categories found.")
    
    report = get_category_report(category_ids=category_ids if category_ids else None)
    
    # Display metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="Average Price",
            value=f"${report['avg_price']:.2f}"
        )
    
    with col2:
        st.metric(
            label="Total Stock",
            value=f"{report['total_stock']:,}"
        )
    
    with col3:
        st.metric(
            label="Total Inventory Value",
            value=f"${report['total_value']:.2f}"
        )
    
    # Display products table
    st.subheader(f"Products in {category_name}")
    products = get_products_by_category(category_ids=category_ids if category_ids else None)
    
    if products:
        df = pd.DataFrame([{
            'Name': p['name'],
            'Price': f"${p['price']:.2f}",
            'Stock': p['stock'],
            'Value': f"${p['price'] * p['stock']:.2f}",
            'Category': p['category_name']
        } for p in products])
        
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info(f"No products found in {category_name}.")

# CATEGORIES PAGE
elif page == "Categories":
    st.header("Category Management")
    
    # Add Category Form
    with st.expander("➕ Add New Category"):
        with st.form("category_form", clear_on_submit=True):
            category_name = st.text_input("Category Name *", value="")
            submitted = st.form_submit_button("Add Category")
            
            if submitted:
                if category_name.strip():
                    if add_category(category_name.strip()):
                        st.success("✅ Category added successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Category name already exists or invalid.")
                else:
                    st.error("❌ Category name is required.")
    
    # Categories List
    st.subheader("All Categories")
    categories = get_all_categories()
    
    if categories:
        df = pd.DataFrame([{'ID': cat_id, 'Name': name} for cat_id, name in categories])
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Delete Category Section
        st.subheader("Delete Category")
        category_options = {f"{name} (ID: {cat_id})": cat_id for cat_id, name in categories}
        selected_category_key = st.selectbox("Select a category to delete:", options=list(category_options.keys()))
        
        if selected_category_key:
            selected_category_id = category_options[selected_category_key]
            category_name = selected_category_key.split(" (ID:")[0]
            
            if st.button("🗑️ Delete Category", type="primary"):
                if delete_category(selected_category_id):
                    st.success("✅ Category deleted successfully!")
                    st.rerun()
                else:
                    st.error("❌ Cannot delete category. It may have products associated with it or doesn't exist.")
    else:
        st.info("No categories found. Add your first category using the form above.")

# TESTING PAGE
elif page == "Testing":
    st.header("🧪 Stage 3 Features Testing")
    st.markdown("---")
    
    tab1, tab2, tab3 = st.tabs(["SQL Injection Protection", "Index Verification", "Transaction Testing"])
    
    with tab1:
        st.subheader("SQL Injection Protection Test")
        st.markdown("""
        **How it works:** All queries use parameterized statements (prepared statements) with `?` placeholders.
        This prevents SQL injection attacks by treating user input as data, not executable SQL code.
        """)
        
        st.markdown("### Test 1: Try SQL Injection in Category Name")
        st.markdown("Enter a malicious SQL injection attempt below:")
        
        malicious_input = st.text_input(
            "Category Name (try: `'; DROP TABLE Categories; --`)",
            value="'; DROP TABLE Categories; --",
            key="sql_inject_test"
        )
        
        if st.button("Test SQL Injection Protection"):
            # This uses the safe parameterized query
            result = add_category(malicious_input)
            if result:
                st.success("✅ Category added safely!")
                st.info(f"**Result:** The input `{malicious_input}` was stored as a literal string, NOT executed as SQL.")
                st.markdown("""
                **Why it's safe:**
                - The query uses: `INSERT INTO Categories (name) VALUES (?)`
                - The value is bound as a parameter: `(name,)`
                - SQLite treats it as data, not code
                """)
                
                # Show that the table still exists
                categories = get_all_categories()
                st.success(f"✅ Categories table still exists with {len(categories)} categories!")
                
                # Show the malicious input was stored safely
                if categories:
                    st.code(f"Latest category: {categories[-1][1]}", language="text")
            else:
                st.warning("Category name might already exist. Try a different name.")
        
        st.markdown("---")
        st.markdown("### Test 2: View Safe Query Code")
        with st.expander("Show parameterized query code"):
            st.code("""
# SAFE: Parameterized query (used in db.py)
cursor.execute('INSERT INTO Categories (name) VALUES (?)', (name,))

# UNSAFE: String concatenation (NOT used - would be vulnerable)
cursor.execute(f"INSERT INTO Categories (name) VALUES ('{name}')")
            """, language="python")
    
    with tab2:
        st.subheader("Index Verification")
        st.markdown("""
        **Indexes created:**
        - `idx_products_category_id` on `Products(category_id)`
        - `idx_products_name` on `Products(name)`
        """)
        
        if st.button("Check Indexes in Database"):
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get indexes on Products table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='Products'")
            indexes = cursor.fetchall()
            
            st.markdown("### Indexes Found:")
            if indexes:
                for idx in indexes:
                    st.success(f"✅ {idx[0]}")
            else:
                st.warning("No indexes found. Make sure you've run the app at least once.")
            
            conn.close()
        
        st.markdown("---")
        st.markdown("### Query Plan Analysis")
        st.markdown("Test which queries use indexes:")
        
        test_query = st.selectbox(
            "Select query to test:",
            [
                "JOIN with ORDER BY (Products page)",
                "WHERE category_id = ? (Reports page)",
                "Aggregation with WHERE (Reports page)",
                "ORDER BY name only"
            ]
        )
        
        if st.button("Show Query Plan"):
            conn = get_connection()
            cursor = conn.cursor()
            
            queries = {
                "JOIN with ORDER BY (Products page)": '''
                    SELECT p.product_id, p.name, p.price, p.stock, c.name as category_name
                    FROM Products p
                    JOIN Categories c ON p.category_id = c.category_id
                    ORDER BY p.name
                ''',
                "WHERE category_id = ? (Reports page)": '''
                    SELECT p.product_id, p.name, p.price, p.stock, c.name as category_name
                    FROM Products p
                    JOIN Categories c ON p.category_id = c.category_id
                    WHERE p.category_id = 1
                    ORDER BY p.name
                ''',
                "Aggregation with WHERE (Reports page)": '''
                    SELECT ROUND(AVG(price), 2), SUM(stock), SUM(price * stock)
                    FROM Products
                    WHERE category_id = 1
                ''',
                "ORDER BY name only": '''
                    SELECT * FROM Products ORDER BY name
                '''
            }
            
            query = queries[test_query]
            
            st.markdown("**Query:**")
            st.code(query, language="sql")
            
            cursor.execute(f"EXPLAIN QUERY PLAN {query}")
            plan = cursor.fetchall()
            
            st.markdown("**Query Plan:**")
            plan_text = ""
            uses_index = False
            for row in plan:
                plan_text += f"{row}\n"
                if 'idx_products_category_id' in str(row) or 'idx_products_name' in str(row):
                    uses_index = True
            
            st.code(plan_text, language="text")
            
            if uses_index:
                st.success("✅ Index is being used!")
                if 'idx_products_category_id' in plan_text:
                    st.info("Using: `idx_products_category_id`")
                if 'idx_products_name' in plan_text:
                    st.info("Using: `idx_products_name`")
            else:
                st.warning("⚠️ Index may not be used (check if you have data in the database)")
            
            conn.close()
    
    with tab3:
        st.subheader("Transaction and Isolation Level Testing")
        st.markdown("""
        **Isolation Level:** SERIALIZABLE
        - Prevents dirty reads, non-repeatable reads, and phantom reads
        - Ensures ACID properties for concurrent access
        """)
        
        st.markdown("### Test 1: Multi-Step Transaction (Category Deletion)")
        st.markdown("""
        The `delete_category()` function uses a transaction to ensure atomicity:
        1. Check if category has products
        2. Delete category if safe
        3. Reset sequence if table becomes empty
        
        All steps happen atomically - either all succeed or all fail.
        """)
        
        categories = get_all_categories()
        if categories:
            cat_options = {f"{name} (ID: {cat_id})": cat_id for cat_id, name in categories}
            selected_cat = st.selectbox("Select category to test deletion:", list(cat_options.keys()))
            
            if st.button("Test Transaction (Try to Delete)"):
                cat_id = cat_options[selected_cat]
                result = delete_category(cat_id)
                
                if result:
                    st.success("✅ Transaction completed successfully!")
                    st.info("All steps (check products, delete category, reset sequence) completed atomically.")
                else:
                    st.warning("⚠️ Transaction prevented deletion")
                    st.info("The transaction checked for products first and rolled back to maintain data integrity.")
                    st.markdown("**This demonstrates:** Transaction ensures atomicity - the check and delete happen together.")
        
        st.markdown("---")
        st.markdown("### Test 2: Concurrent Update Scenario")
        st.markdown("""
        **SERIALIZABLE Isolation Behavior:**
        - If two users update the same product simultaneously, transactions execute serially
        - Last commit wins, but both see consistent data during their transaction
        - No lost updates or inconsistent states
        """)
        
        products = get_all_products()
        if products:
            prod_options = {f"{p['name']} (ID: {p['product_id']})": p['product_id'] for p in products}
            selected_prod = st.selectbox("Select product to simulate update:", list(prod_options.keys()))
            
            selected_prod_id = prod_options[selected_prod]
            product = get_product_by_id(selected_prod_id)
            
            if product:
                st.markdown(f"**Current Stock:** {product['stock']}")
                new_stock = st.number_input("New Stock Value:", min_value=0, value=int(product['stock']) + 5, step=1)
                
                if st.button("Simulate Concurrent Update"):
                    # This uses a transaction with SERIALIZABLE isolation
                    result = update_product(
                        selected_prod_id,
                        product['name'],
                        product['price'],
                        new_stock,
                        product['category_id']
                    )
                    
                    if result:
                        st.success("✅ Update completed in transaction!")
                        st.info("""
                        **In a real concurrent scenario:**
                        - User A reads product (stock = 10)
                        - User B reads product (stock = 10)
                        - User A updates to 15 and commits
                        - User B updates to 20 and commits
                        - SERIALIZABLE ensures User B sees User A's update
                        - Final value: 20 (last commit wins, but consistent)
                        """)
        
        st.markdown("---")
        st.markdown("### Connection Settings")
        with st.expander("Show isolation level configuration"):
            st.code("""
# In db.py, get_connection():
conn = sqlite3.connect(DB_PATH, isolation_level=None)
# SQLite uses SERIALIZABLE by default
# WAL mode enabled for better concurrency
conn.execute('PRAGMA journal_mode=WAL')
            """, language="python")

