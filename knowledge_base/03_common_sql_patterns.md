# Acme Analytics - Common SQL Patterns

This document contains common SQL patterns and query templates for the Acme Analytics SQLite database.

---

## SQLite Function Reference (CRITICAL)

**CRITICAL RULE:** This database uses SQLite. Always use SQLite-compatible SQL syntax.

### Date/Time Functions (SQLite)
| Function | Description | Example |
|----------|-------------|---------|
| `date('now')` | Current date | `WHERE order_date = date('now')` |
| `strftime('%Y-%m', col)` | Extract year-month | `GROUP BY strftime('%Y-%m', order_date)` |
| `strftime('%Y', col)` | Extract year | `WHERE strftime('%Y', order_date) = '2024'` |
| `strftime('%m', col)` | Extract month number | `ORDER BY strftime('%m', signup_date)` |
| `date(col, '-N days')` | Subtract N days | `WHERE order_date >= date('now', '-30 days')` |
| `date(col, '+N months')` | Add N months | `WHERE signup_date <= date('now', '-6 months')` |
| `julianday(d2) - julianday(d1)` | Days between dates | `julianday(order_date) - julianday(signup_date)` |

### Functions NOT Available in SQLite
| Function | Status | Use Instead |
|----------|--------|-------------|
| `DATE_FORMAT()` | MySQL only | `strftime()` |
| `NOW()`, `CURDATE()` | MySQL only | `date('now')` |
| `YEAR()`, `MONTH()` | MySQL only | `strftime('%Y', col)`, `strftime('%m', col)` |
| `DATE_TRUNC()` | PostgreSQL only | `strftime()` for truncation |
| `EXTRACT()` | PostgreSQL only | `strftime()` |
| `ILIKE` | PostgreSQL only | Use `LIKE` (case-insensitive by default in SQLite) |

### Aggregate Functions (SQLite)
| Function | Description | Example |
|----------|-------------|---------|
| `COUNT(*)` | Count rows | `SELECT COUNT(*) FROM orders` |
| `SUM(col)` | Sum values | `SELECT SUM(total_amount) FROM orders` |
| `AVG(col)` | Average | `SELECT AVG(salary) FROM employees` |
| `MAX(col)` / `MIN(col)` | Max/Min | `SELECT MAX(price) FROM products` |
| `GROUP_CONCAT(col, sep)` | Concatenate | `GROUP_CONCAT(name, ', ')` |
| `ROUND(col, N)` | Round to N decimals | `ROUND(AVG(price), 2)` |

---

## Revenue Patterns

### Total Revenue (Excluding Cancelled)
```sql
SELECT SUM(total_amount) AS total_revenue
FROM orders
WHERE status != 'cancelled';
```

### Revenue by Month
```sql
SELECT
    strftime('%Y-%m', order_date) AS month,
    SUM(total_amount) AS revenue,
    COUNT(*) AS order_count
FROM orders
WHERE status != 'cancelled'
GROUP BY strftime('%Y-%m', order_date)
ORDER BY month;
```

### Revenue by Product Category
```sql
SELECT
    c.name AS category,
    SUM(oi.quantity * oi.unit_price) AS revenue,
    SUM(oi.quantity) AS units_sold
FROM order_items oi
JOIN orders o ON oi.order_id = o.id
JOIN products p ON oi.product_id = p.id
JOIN categories c ON p.category_id = c.id
WHERE o.status != 'cancelled'
GROUP BY c.name
ORDER BY revenue DESC;
```

---

## Customer Patterns

### Top Customers by Lifetime Value
```sql
SELECT name, email, city, state, lifetime_value
FROM customers
ORDER BY lifetime_value DESC
LIMIT 10;
```

### Customer Signups by Month
```sql
SELECT
    strftime('%Y-%m', signup_date) AS month,
    COUNT(*) AS new_customers
FROM customers
GROUP BY strftime('%Y-%m', signup_date)
ORDER BY month;
```

### Customers by State
```sql
SELECT state, COUNT(*) AS customer_count
FROM customers
GROUP BY state
ORDER BY customer_count DESC;
```

---

## Product Patterns

### Products with Highest Profit Margin
```sql
SELECT
    name,
    price,
    cost,
    ROUND((price - cost) / price * 100, 1) AS margin_pct
FROM products
ORDER BY margin_pct DESC
LIMIT 10;
```

### Best-Selling Products
```sql
SELECT
    p.name AS product,
    c.name AS category,
    SUM(oi.quantity) AS total_units,
    SUM(oi.quantity * oi.unit_price) AS total_revenue
FROM order_items oi
JOIN products p ON oi.product_id = p.id
JOIN categories c ON p.category_id = c.id
JOIN orders o ON oi.order_id = o.id
WHERE o.status != 'cancelled'
GROUP BY p.id, p.name, c.name
ORDER BY total_revenue DESC
LIMIT 10;
```

### Low Stock Products
```sql
SELECT name, category_id, stock_quantity, price
FROM products
WHERE stock_quantity < 50
ORDER BY stock_quantity ASC;
```

---

## Order Patterns

### Order Status Breakdown
```sql
SELECT
    status,
    COUNT(*) AS order_count,
    SUM(total_amount) AS total_value
FROM orders
GROUP BY status
ORDER BY order_count DESC;
```

### Average Order Value
```sql
SELECT
    ROUND(AVG(total_amount), 2) AS avg_order_value
FROM orders
WHERE status != 'cancelled';
```

### Orders per Customer
```sql
SELECT
    c.name,
    COUNT(o.id) AS order_count,
    SUM(o.total_amount) AS total_spent
FROM customers c
JOIN orders o ON c.id = o.customer_id
WHERE o.status != 'cancelled'
GROUP BY c.id, c.name
ORDER BY order_count DESC
LIMIT 10;
```

---

## Employee Patterns

### Average Salary by Department
```sql
SELECT
    d.name AS department,
    COUNT(e.id) AS headcount,
    ROUND(AVG(e.salary), 2) AS avg_salary,
    MIN(e.salary) AS min_salary,
    MAX(e.salary) AS max_salary
FROM employees e
JOIN departments d ON e.department_id = d.id
GROUP BY d.name
ORDER BY avg_salary DESC;
```

### Employee Tenure
```sql
SELECT
    name,
    hire_date,
    ROUND(julianday('now') - julianday(hire_date)) AS days_employed
FROM employees
ORDER BY days_employed DESC;
```

---

## Multi-Join Patterns

### Full Order Detail (Customer + Items + Products)
```sql
SELECT
    c.name AS customer,
    o.order_date,
    o.status,
    p.name AS product,
    cat.name AS category,
    oi.quantity,
    oi.unit_price,
    oi.quantity * oi.unit_price AS line_total
FROM orders o
JOIN customers c ON o.customer_id = c.id
JOIN order_items oi ON o.id = oi.order_id
JOIN products p ON oi.product_id = p.id
JOIN categories cat ON p.category_id = cat.id
WHERE o.status != 'cancelled'
ORDER BY o.order_date DESC;
```
