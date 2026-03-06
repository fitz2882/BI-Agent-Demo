"""Schema Provider - provides hardcoded schema context for the demo database.

Replaces the Google File Search retrieval agent with a simple local schema.
"""

import logging
from .state import MAKERState

logger = logging.getLogger(__name__)

# The demo database schema for "Acme Analytics" - an e-commerce company
DEMO_SCHEMA = {
    "tables": [
        "customers",
        "products",
        "categories",
        "orders",
        "order_items",
        "employees",
        "departments",
    ],
    "table_columns": {
        "customers": [
            {"name": "id", "type": "INTEGER PRIMARY KEY"},
            {"name": "name", "type": "TEXT"},
            {"name": "email", "type": "TEXT"},
            {"name": "city", "type": "TEXT"},
            {"name": "state", "type": "TEXT"},
            {"name": "signup_date", "type": "DATE"},
            {"name": "lifetime_value", "type": "REAL"},
        ],
        "products": [
            {"name": "id", "type": "INTEGER PRIMARY KEY"},
            {"name": "name", "type": "TEXT"},
            {"name": "category_id", "type": "INTEGER"},
            {"name": "price", "type": "REAL"},
            {"name": "cost", "type": "REAL"},
            {"name": "stock_quantity", "type": "INTEGER"},
        ],
        "categories": [
            {"name": "id", "type": "INTEGER PRIMARY KEY"},
            {"name": "name", "type": "TEXT"},
        ],
        "orders": [
            {"name": "id", "type": "INTEGER PRIMARY KEY"},
            {"name": "customer_id", "type": "INTEGER"},
            {"name": "order_date", "type": "DATE"},
            {"name": "status", "type": "TEXT"},
            {"name": "total_amount", "type": "REAL"},
        ],
        "order_items": [
            {"name": "id", "type": "INTEGER PRIMARY KEY"},
            {"name": "order_id", "type": "INTEGER"},
            {"name": "product_id", "type": "INTEGER"},
            {"name": "quantity", "type": "INTEGER"},
            {"name": "unit_price", "type": "REAL"},
        ],
        "employees": [
            {"name": "id", "type": "INTEGER PRIMARY KEY"},
            {"name": "name", "type": "TEXT"},
            {"name": "department_id", "type": "INTEGER"},
            {"name": "hire_date", "type": "DATE"},
            {"name": "salary", "type": "REAL"},
        ],
        "departments": [
            {"name": "id", "type": "INTEGER PRIMARY KEY"},
            {"name": "name", "type": "TEXT"},
        ],
    },
    "business_rules": [
        "orders.status can be: 'pending', 'shipped', 'delivered', 'cancelled'",
        "products.price is the retail price; products.cost is the wholesale cost",
        "order_items.unit_price is the price at time of purchase",
        "customers.lifetime_value is the total amount spent by the customer",
    ],
}


def _schema_as_ddl() -> str:
    """Format the schema as CREATE TABLE statements for LLM prompts."""
    lines = []
    for table in DEMO_SCHEMA["tables"]:
        cols = DEMO_SCHEMA["table_columns"].get(table, [])
        col_defs = ", ".join(f'{c["name"]} {c["type"]}' for c in cols)
        lines.append(f"CREATE TABLE {table} ({col_defs});")
    return "\n".join(lines)


SCHEMA_DDL = _schema_as_ddl()


class SchemaProvider:
    """Provides schema context for the demo database."""

    def retrieve(self, state: MAKERState) -> MAKERState:
        state.schema_context = {
            "tables": DEMO_SCHEMA["tables"],
            "table_columns": DEMO_SCHEMA["table_columns"],
            "business_rules": DEMO_SCHEMA["business_rules"],
            "ddl": SCHEMA_DDL,
        }
        state.log_step(
            "SchemaProvider",
            f"Loaded schema for {len(DEMO_SCHEMA['tables'])} tables",
        )
        logger.info("Schema context loaded: %d tables", len(DEMO_SCHEMA["tables"]))
        return state
