# Acme Analytics - Business Rules & Logic

This document contains business rules, status code definitions, and domain logic for the Acme Analytics e-commerce platform.

---

## Revenue Calculations

### Order Revenue
* **Rule:** When calculating revenue, **always exclude cancelled orders** by adding `WHERE status != 'cancelled'` or `WHERE status IN ('pending', 'shipped', 'delivered')`.
* **Rule:** Revenue = `SUM(orders.total_amount)` for non-cancelled orders.
* **Rule:** All monetary values are stored in **dollars** (not cents). No division needed.

### Product Revenue (Line-Item Level)
* **Rule:** For product-level revenue, use `SUM(order_items.quantity * order_items.unit_price)` and join with `orders` to filter by status.
* **Rule:** `order_items.unit_price` may differ from `products.price` if product prices were updated after the order was placed.

### Profit Margin
* **Rule:** Gross margin per product = `(products.price - products.cost) / products.price * 100` (as a percentage).
* **Rule:** Actual profit per sale = `order_items.unit_price - products.cost` (note: uses sale price, not current price).

---

## Order Status Definitions

| Status | Meaning | Include in Revenue? |
|--------|---------|-------------------|
| `pending` | Order placed, not yet shipped | Yes |
| `shipped` | Order dispatched to customer | Yes |
| `delivered` | Successfully received by customer | Yes |
| `cancelled` | Order was cancelled | **No** |

* **Rule:** "Completed orders" = orders with status `'delivered'`.
* **Rule:** "Active orders" = orders with status `'pending'` or `'shipped'`.
* **Rule:** When asked about "revenue" or "sales", always exclude `'cancelled'` orders unless explicitly asked to include them.

---

## Customer Lifetime Value

* **Rule:** `customers.lifetime_value` is a precomputed field that equals the sum of `orders.total_amount` for all non-cancelled orders by that customer.
* **Rule:** This field is periodically updated. For real-time accuracy, calculate directly: `SELECT SUM(o.total_amount) FROM orders o WHERE o.customer_id = ? AND o.status != 'cancelled'`.

---

## Date Handling (SQLite)

* **Rule:** All dates are stored in `YYYY-MM-DD` format (ISO 8601).
* **Rule:** Use SQLite date functions:
  - `date('now')` for current date
  - `strftime('%Y-%m', order_date)` to extract year-month
  - `strftime('%Y', order_date)` to extract year
  - `strftime('%m', order_date)` to extract month number
  - `date(order_date, '-30 days')` for date arithmetic
* **Anti-Pattern:** Do NOT use MySQL functions like `DATE_FORMAT()`, `NOW()`, `CURDATE()`, or `YEAR()`. These do not work in SQLite.
* **Anti-Pattern:** Do NOT use PostgreSQL/Redshift functions like `DATE_TRUNC()`, `EXTRACT()`, or `::date` casting.

---

## Product Categories

There are exactly 6 product categories:

| ID | Category Name | Description |
|----|--------------|-------------|
| 1 | Electronics | Tech gadgets, headphones, keyboards, etc. |
| 2 | Clothing | Apparel, shoes, accessories |
| 3 | Home & Garden | Home decor, lighting, kitchen items |
| 4 | Sports | Fitness equipment, yoga, outdoor gear |
| 5 | Books | Fiction, non-fiction, cookbooks, guides |
| 6 | Food & Beverage | Coffee, tea, snacks, organic foods |

* **Rule:** Each product belongs to exactly one category via `products.category_id`.
* **Rule:** There are 10 products per category (60 total).

---

## Department Structure

There are exactly 5 departments:

| ID | Department | Typical Headcount |
|----|-----------|------------------|
| 1 | Engineering | ~4 employees |
| 2 | Sales | ~4 employees |
| 3 | Marketing | ~4 employees |
| 4 | Support | ~4 employees |
| 5 | Operations | ~4 employees |

* **Rule:** Each employee belongs to exactly one department via `employees.department_id`.
* **Rule:** Total company headcount is 20 employees.

---

## Join Reference Guide

| Question Type | Tables to Join | Join Condition |
|--------------|---------------|----------------|
| Revenue by category | `orders` + `order_items` + `products` + `categories` | `orders.id = order_items.order_id AND order_items.product_id = products.id AND products.category_id = categories.id` |
| Customer orders | `customers` + `orders` | `customers.id = orders.customer_id` |
| Product sales detail | `order_items` + `products` | `order_items.product_id = products.id` |
| Employee departments | `employees` + `departments` | `employees.department_id = departments.id` |
| Monthly revenue | `orders` (single table) | Use `strftime('%Y-%m', order_date)` for grouping |
| Top customers | `customers` (single table) | Sort by `lifetime_value DESC` |
| Product margins | `products` (single table) | Calculate `(price - cost) / price` |

---

## Common Query Anti-Patterns

1. **Forgetting to exclude cancelled orders** — Always filter `status != 'cancelled'` for revenue queries.
2. **Using MySQL/PostgreSQL date functions** — Use SQLite `strftime()` and `date()` instead.
3. **Joining orders directly to products** — You need `order_items` as the bridge table: `orders` -> `order_items` -> `products`.
4. **Using `products.price` for revenue** — Use `order_items.unit_price` instead (historical price at time of purchase).
5. **Double-counting with multiple joins** — When joining orders -> order_items -> products, be careful with aggregation. Use `DISTINCT` or aggregate at the right level.
