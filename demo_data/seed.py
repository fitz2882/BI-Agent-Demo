"""Seed the demo SQLite database with fake Acme Analytics data."""

import sqlite3
import os
import random
from datetime import datetime, timedelta

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "demo.db"))

# Remove existing DB
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# -- Schema --

cursor.executescript("""
CREATE TABLE departments (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE employees (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    department_id INTEGER REFERENCES departments(id),
    hire_date DATE,
    salary REAL
);

CREATE TABLE categories (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category_id INTEGER REFERENCES categories(id),
    price REAL,
    cost REAL,
    stock_quantity INTEGER
);

CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    city TEXT,
    state TEXT,
    signup_date DATE,
    lifetime_value REAL DEFAULT 0
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    order_date DATE,
    status TEXT CHECK(status IN ('pending', 'shipped', 'delivered', 'cancelled')),
    total_amount REAL
);

CREATE TABLE order_items (
    id INTEGER PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER,
    unit_price REAL
);
""")

# -- Seed data --

random.seed(42)

# Departments
departments = ["Engineering", "Sales", "Marketing", "Support", "Operations"]
for i, name in enumerate(departments, 1):
    cursor.execute("INSERT INTO departments VALUES (?, ?)", (i, name))

# Employees
first_names = ["Alice", "Bob", "Charlie", "Diana", "Edward", "Fiona", "George", "Hannah", "Ivan", "Julia",
               "Kevin", "Laura", "Mike", "Nancy", "Oscar", "Patricia", "Quinn", "Rachel", "Steve", "Tina"]
last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]

for i in range(1, 21):
    name = f"{first_names[i-1]} {random.choice(last_names)}"
    dept_id = random.randint(1, 5)
    hire_date = (datetime(2020, 1, 1) + timedelta(days=random.randint(0, 1800))).strftime("%Y-%m-%d")
    salary = round(random.uniform(55000, 150000), 2)
    cursor.execute("INSERT INTO employees VALUES (?, ?, ?, ?, ?)", (i, name, dept_id, hire_date, salary))

# Categories
categories = ["Electronics", "Clothing", "Home & Garden", "Sports", "Books", "Food & Beverage"]
for i, name in enumerate(categories, 1):
    cursor.execute("INSERT INTO categories VALUES (?, ?)", (i, name))

# Products
product_names = {
    1: ["Wireless Headphones", "Smart Watch", "USB-C Hub", "Bluetooth Speaker", "Tablet Stand",
        "Phone Case", "Laptop Sleeve", "Webcam HD", "Mechanical Keyboard", "Monitor Light"],
    2: ["Running Shoes", "Denim Jacket", "Cotton T-Shirt", "Wool Sweater", "Baseball Cap",
        "Hiking Boots", "Rain Coat", "Polo Shirt", "Cargo Pants", "Scarf"],
    3: ["LED Desk Lamp", "Plant Pot Set", "Throw Pillow", "Wall Clock", "Candle Set",
        "Door Mat", "Picture Frame", "Shower Curtain", "Kitchen Timer", "Cutting Board"],
    4: ["Yoga Mat", "Water Bottle", "Resistance Bands", "Jump Rope", "Tennis Balls",
        "Foam Roller", "Gym Bag", "Wrist Wraps", "Ab Wheel", "Pull-Up Bar"],
    5: ["Python Cookbook", "Design Patterns", "Data Science Guide", "Marketing 101", "History of Art",
        "Sci-Fi Novel", "Mystery Thriller", "Self-Help Book", "Travel Guide", "Poetry Collection"],
    6: ["Organic Coffee", "Green Tea Pack", "Protein Bars", "Trail Mix", "Hot Sauce",
        "Olive Oil", "Honey Jar", "Granola", "Dark Chocolate", "Dried Fruit"],
}

pid = 1
for cat_id, names in product_names.items():
    for name in names:
        price = round(random.uniform(9.99, 199.99), 2)
        cost = round(price * random.uniform(0.3, 0.6), 2)
        stock = random.randint(10, 500)
        cursor.execute("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)", (pid, name, cat_id, price, cost, stock))
        pid += 1

# Customers
cities = [
    ("New York", "NY"), ("Los Angeles", "CA"), ("Chicago", "IL"), ("Houston", "TX"),
    ("Phoenix", "AZ"), ("Philadelphia", "PA"), ("San Antonio", "TX"), ("San Diego", "CA"),
    ("Dallas", "TX"), ("San Jose", "CA"), ("Austin", "TX"), ("Jacksonville", "FL"),
    ("Portland", "OR"), ("Seattle", "WA"), ("Denver", "CO"), ("Boston", "MA"),
    ("Nashville", "TN"), ("Atlanta", "GA"), ("Miami", "FL"), ("Minneapolis", "MN"),
]

cust_first = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
              "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
              "Thomas", "Sarah", "Christopher", "Karen", "Daniel", "Lisa", "Matthew", "Betty",
              "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley", "Steven", "Dorothy",
              "Paul", "Kimberly", "Andrew", "Emily", "Joshua", "Donna", "Kenneth", "Michelle",
              "Brian", "Carol", "George", "Amanda", "Timothy", "Melissa", "Ronald", "Deborah",
              "Jason", "Stephanie"]

for i in range(1, 51):
    fname = cust_first[(i-1) % len(cust_first)]
    lname = random.choice(last_names)
    city, st = random.choice(cities)
    signup = (datetime(2022, 1, 1) + timedelta(days=random.randint(0, 1000))).strftime("%Y-%m-%d")
    cursor.execute("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, 0)",
                   (i, f"{fname} {lname}", f"{fname.lower()}.{lname.lower()}@example.com", city, st, signup))

# Orders & Order Items
statuses = ["pending", "shipped", "delivered", "delivered", "delivered", "cancelled"]

oid = 1
oiid = 1
for _ in range(200):
    cust_id = random.randint(1, 50)
    order_date = (datetime(2024, 1, 1) + timedelta(days=random.randint(0, 400))).strftime("%Y-%m-%d")
    status = random.choice(statuses)

    # Generate order items first to calculate total
    num_items = random.randint(1, 5)
    items = []
    total = 0.0
    for _ in range(num_items):
        prod_id = random.randint(1, 60)
        qty = random.randint(1, 4)
        # Get product price
        cursor.execute("SELECT price FROM products WHERE id = ?", (prod_id,))
        price = cursor.fetchone()[0]
        item_total = round(price * qty, 2)
        total += item_total
        items.append((oiid, oid, prod_id, qty, price))
        oiid += 1

    total = round(total, 2)
    cursor.execute("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", (oid, cust_id, order_date, status, total))

    for item in items:
        cursor.execute("INSERT INTO order_items VALUES (?, ?, ?, ?, ?)", item)

    oid += 1

# Update customer lifetime values
cursor.execute("""
    UPDATE customers SET lifetime_value = (
        SELECT COALESCE(SUM(o.total_amount), 0)
        FROM orders o
        WHERE o.customer_id = customers.id AND o.status != 'cancelled'
    )
""")

conn.commit()

# Print summary
cursor.execute("SELECT COUNT(*) FROM departments")
print(f"Departments: {cursor.fetchone()[0]}")
cursor.execute("SELECT COUNT(*) FROM employees")
print(f"Employees: {cursor.fetchone()[0]}")
cursor.execute("SELECT COUNT(*) FROM categories")
print(f"Categories: {cursor.fetchone()[0]}")
cursor.execute("SELECT COUNT(*) FROM products")
print(f"Products: {cursor.fetchone()[0]}")
cursor.execute("SELECT COUNT(*) FROM customers")
print(f"Customers: {cursor.fetchone()[0]}")
cursor.execute("SELECT COUNT(*) FROM orders")
print(f"Orders: {cursor.fetchone()[0]}")
cursor.execute("SELECT COUNT(*) FROM order_items")
print(f"Order Items: {cursor.fetchone()[0]}")

conn.close()
print(f"\nDemo database created at: {DB_PATH}")
