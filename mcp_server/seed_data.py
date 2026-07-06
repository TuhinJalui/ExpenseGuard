"""
seed_data.py — Populates the SQLite mock database with realistic but
obviously synthetic company data. Run once on first startup.

Design note: Using SQLite (not a real accounting system) keeps MCP tool
responses deterministic and demo-safe. The realistic structure is what
matters for judging — not live integration depth.
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent / "company_systems.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def seed():
    conn = get_connection()
    cur = conn.cursor()

    # ── Schema ────────────────────────────────────────────────────────────────

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS policy_rules (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            category    TEXT NOT NULL,
            role        TEXT NOT NULL,          -- 'employee' | 'manager' | 'exec'
            spend_limit REAL NOT NULL,          -- per-transaction limit in USD
            requires_receipt_above REAL,        -- receipt required if > this amount
            requires_pre_approval_above REAL,   -- pre-approval required if > this
            allowed_vendors TEXT,               -- JSON array or NULL (any)
            notes       TEXT
        );

        CREATE TABLE IF NOT EXISTS employees (
            employee_id     TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            department      TEXT NOT NULL,
            role            TEXT NOT NULL,      -- 'employee' | 'manager' | 'exec'
            approval_tier   INTEGER NOT NULL,   -- 1=self, 2=manager, 3=finance
            manager_id      TEXT
        );

        CREATE TABLE IF NOT EXISTS expense_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            vendor      TEXT NOT NULL,
            amount      REAL NOT NULL,
            currency    TEXT DEFAULT 'USD',
            date        TEXT NOT NULL,          -- ISO 8601
            category    TEXT NOT NULL,
            status      TEXT NOT NULL           -- 'approved'|'rejected'|'pending'
        );

        CREATE TABLE IF NOT EXISTS department_budgets (
            department      TEXT PRIMARY KEY,
            annual_budget   REAL NOT NULL,
            spent_ytd       REAL NOT NULL,
            fiscal_year     INTEGER NOT NULL
        );
    """)

    # ── Policy Rules ─────────────────────────────────────────────────────────
    # Realistic spend limits by category × role. Judges can read these and
    # immediately understand the policy logic being enforced.

    policy_data = [
        # (category, role, spend_limit, receipt_above, pre_approval_above, allowed_vendors, notes)
        ("meals",        "employee", 75.00,   25.00,  None,    None, "Per-meal limit. Team meals covered up to $200 with manager approval."),
        ("meals",        "manager",  150.00,  25.00,  None,    None, "Includes client entertainment meals."),
        ("meals",        "exec",     500.00,  25.00,  None,    None, "Client entertainment — attach attendee list."),

        ("travel",       "employee", 500.00,  50.00,  300.00,  None, "Economy class only. Hotels max $200/night."),
        ("travel",       "manager",  1500.00, 50.00,  1000.00, None, "Business class allowed for flights >6 hours."),
        ("travel",       "exec",     5000.00, 50.00,  3000.00, None, "Policy: attach travel itinerary."),

        ("software",     "employee", 100.00,  0.00,   50.00,   json.dumps(["Adobe", "Microsoft", "JetBrains", "GitHub", "Figma", "Notion"]), "Pre-approved vendor list only. IT approval required above $50."),
        ("software",     "manager",  500.00,  0.00,   200.00,  None, "Any vendor with IT review above $200."),
        ("software",     "exec",     2000.00, 0.00,   500.00,  None, "Finance review above $500."),

        ("office_supplies", "employee", 50.00,  25.00, None, None, "Reasonable office supplies. No furniture."),
        ("office_supplies", "manager",  200.00, 25.00, 100.00, None, "Includes minor equipment."),
        ("office_supplies", "exec",     500.00, 25.00, 250.00, None, ""),

        ("training",     "employee", 500.00,  0.00,   200.00,  None, "Job-relevant only. Manager pre-approval above $200."),
        ("training",     "manager",  2000.00, 0.00,   1000.00, None, "Department-relevant training."),
        ("training",     "exec",     5000.00, 0.00,   2500.00, None, "Board-level executive coaching included."),

        ("entertainment","employee", 0.00,    0.00,   0.00,    None, "Not covered for individual contributors. Must be client-facing."),
        ("entertainment","manager",  300.00,  0.00,   150.00,  None, "Client entertainment only. Attach client names."),
        ("entertainment","exec",     1000.00, 0.00,   500.00,  None, "Client/board entertainment."),

        ("equipment",    "employee", 200.00,  0.00,   100.00,  None, "IT-approved equipment list only."),
        ("equipment",    "manager",  1000.00, 0.00,   500.00,  None, "Pre-approval required above $500."),
        ("equipment",    "exec",     5000.00, 0.00,   2000.00, None, ""),
    ]

    cur.executemany("""
        INSERT OR IGNORE INTO policy_rules
            (category, role, spend_limit, requires_receipt_above,
             requires_pre_approval_above, allowed_vendors, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, policy_data)

    # ── Employees ─────────────────────────────────────────────────────────────
    employee_data = [
        ("E1001", "Alice Johnson",   "Engineering",  "employee", 2, "E2001"),
        ("E1002", "Bob Martinez",    "Engineering",  "employee", 2, "E2001"),
        ("E1003", "Carol Smith",     "Marketing",    "employee", 2, "E2002"),
        ("E1004", "David Lee",       "Marketing",    "employee", 2, "E2002"),
        ("E1005", "Eva Chen",        "Finance",      "employee", 2, "E2003"),
        ("E2001", "Frank Torres",    "Engineering",  "manager",  2, "E3001"),
        ("E2002", "Grace Kim",       "Marketing",    "manager",  2, "E3001"),
        ("E2003", "Henry Patel",     "Finance",      "manager",  2, "E3001"),
        ("E3001", "Isabelle Nguyen", "Executive",    "exec",     3, None),
    ]

    cur.executemany("""
        INSERT OR IGNORE INTO employees
            (employee_id, name, department, role, approval_tier, manager_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, employee_data)

    # ── Expense History (for duplicate detection) ─────────────────────────────
    history_data = [
        ("E1001", "Delta Airlines",  345.00, "USD", "2026-06-10", "travel",         "approved"),
        ("E1001", "Hilton Hotels",   189.00, "USD", "2026-06-10", "travel",         "approved"),
        ("E1001", "Chipotle",         23.50, "USD", "2026-06-11", "meals",          "approved"),
        ("E1001", "GitHub",           10.00, "USD", "2026-06-01", "software",       "approved"),
        ("E1002", "United Airlines", 412.00, "USD", "2026-06-15", "travel",         "approved"),
        ("E1002", "Uber Eats",        48.00, "USD", "2026-06-16", "meals",          "approved"),
        ("E1002", "Figma",            15.00, "USD", "2026-06-01", "software",       "approved"),
        ("E1003", "Adobe",            54.99, "USD", "2026-06-01", "software",       "approved"),
        ("E1003", "The Capital Grille",156.00,"USD","2026-06-20", "entertainment",  "rejected"),
        ("E1004", "Marriott",        210.00, "USD", "2026-06-12", "travel",         "approved"),
        ("E2001", "American Airlines",890.00,"USD", "2026-05-20", "travel",         "approved"),
        ("E2001", "Nobu Restaurant", 280.00, "USD", "2026-05-21", "meals",          "approved"),
        # Intentional near-duplicate for demo: same vendor/amount, close date
        ("E1001", "Delta Airlines",  345.00, "USD", "2026-06-17", "travel",         "pending"),
    ]

    cur.executemany("""
        INSERT OR IGNORE INTO expense_history
            (employee_id, vendor, amount, currency, date, category, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, history_data)

    # ── Department Budgets ────────────────────────────────────────────────────
    budget_data = [
        ("Engineering",  250000.00, 142350.00, 2026),
        ("Marketing",    180000.00, 165200.00, 2026),   # Near limit — good demo signal
        ("Finance",      120000.00,  61800.00, 2026),
        ("Executive",    500000.00, 198400.00, 2026),
    ]

    cur.executemany("""
        INSERT OR REPLACE INTO department_budgets
            (department, annual_budget, spent_ytd, fiscal_year)
        VALUES (?, ?, ?, ?)
    """, budget_data)

    conn.commit()
    conn.close()
    print(f"[seed_data] Database seeded at {DB_PATH}")


if __name__ == "__main__":
    seed()
