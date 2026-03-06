# Acme Analytics - Database Schema

SQLite database for the Acme Analytics e-commerce platform. 

## Table of Contents

**Core Tables:**
- [customers](#customers) - **[PRIMARY CUSTOMER TABLE]** Customer profiles and lifetime value.
- [products](#products) - **[PRIMARY PRODUCT TABLE]** Product catalog with pricing.
- [categories](#categories) - Product category definitions.
- [orders](#orders) - **[PRIMARY ORDER TABLE]** Customer orders with status tracking.
- [order_items](#order_items) - **[ORDER LINE ITEMS]** Individual items within each order.
- [employees](#employees) - Employee records with department and salary.
- [departments](#departments) - Department definitions.

---

# customers
## 1. Schema Context
* **Table Name:** `customers`
* **Database:** SQLite
* **Description:** **[PRIMARY CUSTOMER TABLE]** Customer profiles including contact info, location, and lifetime spending.
* **Usage Context:** Use for customer demographics, geographic analysis, signup trends, and lifetime value analysis.
* **Joins:** Join with `orders` on `customers.id = orders.customer_id` to see purchase history.

## 2. Columns

### `id`
* **Data Type:** INTEGER PRIMARY KEY
* **Description:** Unique customer identifier.

### `name`
* **Data Type:** TEXT
* **Description:** Full name of the customer.

### `email`
* **Data Type:** TEXT
* **Description:** Customer email address.

### `city`
* **Data Type:** TEXT
* **Description:** Customer's city of residence.

### `state`
* **Data Type:** TEXT
* **Description:** Two-letter US state code (e.g., "NY", "CA", "TX").

### `signup_date`
* **Data Type:** DATE
* **Description:** Date the customer created their account. Format: YYYY-MM-DD.

### `lifetime_value`
* **Data Type:** REAL
* **Description:** Total amount spent by the customer across all non-cancelled orders. Stored in **dollars** (e.g., 1234.56). This is a denormalized/precomputed field updated when orders change.

---

# products
## 1. Schema Context
* **Table Name:** `products`
* **Database:** SQLite
* **Description:** **[PRIMARY PRODUCT TABLE]** Full product catalog with retail pricing, wholesale cost, and inventory levels.
* **Usage Context:** Use for product analysis, margin calculations, inventory queries, and category breakdowns.
* **Joins:** Join with `categories` on `products.category_id = categories.id` for category names. Join with `order_items` on `products.id = order_items.product_id` for sales data.
* **Critical Note:** `price` is the retail price; `cost` is the wholesale cost. Profit margin = `(price - cost) / price`.

## 2. Columns

### `id`
* **Data Type:** INTEGER PRIMARY KEY
* **Description:** Unique product identifier.

### `name`
* **Data Type:** TEXT
* **Description:** Product display name (e.g., "Wireless Headphones", "Running Shoes").

### `category_id`
* **Data Type:** INTEGER
* **Description:** Foreign key to `categories.id`.

### `price`
* **Data Type:** REAL
* **Description:** Retail price in **dollars** (e.g., 49.99).

### `cost`
* **Data Type:** REAL
* **Description:** Wholesale/acquisition cost in **dollars** (e.g., 22.50).

### `stock_quantity`
* **Data Type:** INTEGER
* **Description:** Current units in stock. A value of 0 means out of stock.

---

# categories
## 1. Schema Context
* **Table Name:** `categories`
* **Database:** SQLite
* **Description:** Product category definitions. There are 6 categories: Electronics, Clothing, Home & Garden, Sports, Books, Food & Beverage.
* **Usage Context:** Use to group and aggregate product/sales data by category.
* **Joins:** Join with `products` on `categories.id = products.category_id`.

## 2. Columns

### `id`
* **Data Type:** INTEGER PRIMARY KEY
* **Description:** Unique category identifier.

### `name`
* **Data Type:** TEXT
* **Description:** Category display name. Values: "Electronics", "Clothing", "Home & Garden", "Sports", "Books", "Food & Beverage".

---

# orders
## 1. Schema Context
* **Table Name:** `orders`
* **Database:** SQLite
* **Description:** **[PRIMARY ORDER TABLE]** Customer orders with status tracking and total amounts.
* **Usage Context:** Use for revenue analysis, order volume trends, status breakdowns, and customer purchase frequency. For line-item detail, join with `order_items`.
* **Joins:** Join with `customers` on `orders.customer_id = customers.id` for customer info. Join with `order_items` on `orders.id = order_items.order_id` for line items.
* **Critical Note:** `total_amount` is in **dollars**. When calculating revenue, **exclude cancelled orders** by filtering `status != 'cancelled'`.

## 2. Columns

### `id`
* **Data Type:** INTEGER PRIMARY KEY
* **Description:** Unique order identifier.

### `customer_id`
* **Data Type:** INTEGER
* **Description:** Foreign key to `customers.id`.

### `order_date`
* **Data Type:** DATE
* **Description:** Date the order was placed. Format: YYYY-MM-DD. Orders span from 2024-01 through early 2025.

### `status`
* **Data Type:** TEXT
* **Description:** Current order status. One of: `'pending'`, `'shipped'`, `'delivered'`, `'cancelled'`.
* **Status Definitions:**
  - `'pending'` — Order placed but not yet shipped.
  - `'shipped'` — Order has been dispatched to the customer.
  - `'delivered'` — Order successfully delivered.
  - `'cancelled'` — Order was cancelled (should be excluded from revenue calculations).

### `total_amount`
* **Data Type:** REAL
* **Description:** Total order amount in **dollars**. This equals the sum of `order_items.quantity * order_items.unit_price` for all items in the order.

---

# order_items
## 1. Schema Context
* **Table Name:** `order_items`
* **Database:** SQLite
* **Description:** **[ORDER LINE ITEMS]** Individual products within each order, with quantity and price at time of purchase.
* **Usage Context:** Use for product-level sales analysis, revenue by product, average items per order, and basket analysis.
* **Joins:** Join with `orders` on `order_items.order_id = orders.id`. Join with `products` on `order_items.product_id = products.id`.
* **Critical Note:** `unit_price` is the price at the time of purchase (may differ from current `products.price` if prices changed).

## 2. Columns

### `id`
* **Data Type:** INTEGER PRIMARY KEY
* **Description:** Unique line item identifier.

### `order_id`
* **Data Type:** INTEGER
* **Description:** Foreign key to `orders.id`.

### `product_id`
* **Data Type:** INTEGER
* **Description:** Foreign key to `products.id`.

### `quantity`
* **Data Type:** INTEGER
* **Description:** Number of units of this product in the order.

### `unit_price`
* **Data Type:** REAL
* **Description:** Price per unit at the time of purchase, in **dollars**.

---

# employees
## 1. Schema Context
* **Table Name:** `employees`
* **Database:** SQLite
* **Description:** Employee records including department assignment, hire date, and salary.
* **Usage Context:** Use for HR analytics: headcount by department, salary analysis, tenure calculations.
* **Joins:** Join with `departments` on `employees.department_id = departments.id` for department names.

## 2. Columns

### `id`
* **Data Type:** INTEGER PRIMARY KEY
* **Description:** Unique employee identifier.

### `name`
* **Data Type:** TEXT
* **Description:** Full name of the employee.

### `department_id`
* **Data Type:** INTEGER
* **Description:** Foreign key to `departments.id`.

### `hire_date`
* **Data Type:** DATE
* **Description:** Date the employee was hired. Format: YYYY-MM-DD.

### `salary`
* **Data Type:** REAL
* **Description:** Annual salary in **dollars** (e.g., 85000.00).

---

# departments
## 1. Schema Context
* **Table Name:** `departments`
* **Database:** SQLite
* **Description:** Department definitions. There are 5 departments: Engineering, Sales, Marketing, Support, Operations.
* **Usage Context:** Use to group employee data by department.
* **Joins:** Join with `employees` on `departments.id = employees.department_id`.

## 2. Columns

### `id`
* **Data Type:** INTEGER PRIMARY KEY
* **Description:** Unique department identifier.

### `name`
* **Data Type:** TEXT
* **Description:** Department name. Values: "Engineering", "Sales", "Marketing", "Support", "Operations".
