"""
mock_mcp_tools.py — Mock MCP Tool Callables for Testing

Provides the same interface as the real MCP tools but backed by
hardcoded data. Used for unit tests and CLI demos that don't need
the full MCP server running.

Design note: The policy agent and router accept tool callables as
dependency injection, so they're testable without any MCP server.
"""

import json


MOCK_EMPLOYEES = {
    "E1001": {"found": True, "employee_id": "E1001", "name": "Alice Johnson",
              "department": "Engineering", "role": "employee", "approval_tier": 2, "manager_id": "E2001"},
    "E1002": {"found": True, "employee_id": "E1002", "name": "Bob Martinez",
              "department": "Engineering", "role": "employee", "approval_tier": 2, "manager_id": "E2001"},
    "E1003": {"found": True, "employee_id": "E1003", "name": "Carol Smith",
              "department": "Marketing", "role": "employee", "approval_tier": 2, "manager_id": "E2002"},
    "E2001": {"found": True, "employee_id": "E2001", "name": "Frank Torres",
              "department": "Engineering", "role": "manager", "approval_tier": 2, "manager_id": "E3001"},
    "E2002": {"found": True, "employee_id": "E2002", "name": "Grace Kim",
              "department": "Marketing", "role": "manager", "approval_tier": 2, "manager_id": "E3001"},
    "E3001": {"found": True, "employee_id": "E3001", "name": "Isabelle Nguyen",
              "department": "Executive", "role": "exec", "approval_tier": 3, "manager_id": None},
}

MOCK_POLICIES = {
    ("meals",     "employee"): {"found": True, "spend_limit": 75.00,  "requires_receipt_above": 25.0, "requires_pre_approval_above": None, "allowed_vendors": None, "notes": "Per-meal limit."},
    ("meals",     "manager"):  {"found": True, "spend_limit": 150.00, "requires_receipt_above": 25.0, "requires_pre_approval_above": None, "allowed_vendors": None, "notes": "Client entertainment."},
    ("travel",    "employee"): {"found": True, "spend_limit": 500.00, "requires_receipt_above": 50.0, "requires_pre_approval_above": 300.0, "allowed_vendors": None, "notes": "Economy class."},
    ("travel",    "manager"):  {"found": True, "spend_limit": 1500.00,"requires_receipt_above": 50.0, "requires_pre_approval_above": 1000.0, "allowed_vendors": None, "notes": "Business class ok."},
    ("software",  "employee"): {"found": True, "spend_limit": 100.00, "requires_receipt_above": 0.0,  "requires_pre_approval_above": 50.0, "allowed_vendors": ["Adobe","Microsoft","JetBrains","GitHub","Figma","Notion"], "notes": "Approved vendor list only."},
    ("entertainment","employee"):{"found": True, "spend_limit": 0.0,  "requires_receipt_above": 0.0,  "requires_pre_approval_above": None, "allowed_vendors": None, "notes": "Not covered for ICs."},
    ("entertainment","manager"):{"found": True, "spend_limit": 300.00,"requires_receipt_above": 0.0,  "requires_pre_approval_above": 150.0, "allowed_vendors": None, "notes": "Client entertainment only."},
}

MOCK_BUDGETS = {
    "Engineering": {"found": True, "department": "Engineering", "fiscal_year": 2026, "annual_budget": 250000, "spent_ytd": 142350, "remaining": 107650, "utilization_percent": 56.9},
    "Marketing":   {"found": True, "department": "Marketing",   "fiscal_year": 2026, "annual_budget": 180000, "spent_ytd": 165200, "remaining": 14800,  "utilization_percent": 91.8},
    "Finance":     {"found": True, "department": "Finance",     "fiscal_year": 2026, "annual_budget": 120000, "spent_ytd": 61800,  "remaining": 58200,  "utilization_percent": 51.5},
    "Executive":   {"found": True, "department": "Executive",   "fiscal_year": 2026, "annual_budget": 500000, "spent_ytd": 198400, "remaining": 301600, "utilization_percent": 39.7},
}


def get_mock_mcp_tools() -> dict:
    """Returns mock MCP tool callables."""

    def get_policy_rules(category: str, role: str) -> dict:
        result = MOCK_POLICIES.get((category, role))
        if not result:
            return {"found": False, "message": f"No policy for {category}/{role}"}
        return {**result, "category": category, "role": role}

    def get_employee_profile(employee_id: str) -> dict:
        result = MOCK_EMPLOYEES.get(employee_id)
        if not result:
            return {"found": False, "message": f"Employee {employee_id} not found"}
        return result

    def check_duplicate(vendor: str, amount: float, date: str, employee_id: str) -> dict:
        # Only flag E1001 / Delta / 345 as duplicate (mirrors seed data)
        is_dup = (employee_id == "E1001" and vendor == "Delta Airlines" and abs(amount - 345.00) < 5)
        return {
            "is_potential_duplicate": is_dup,
            "match_count": 1 if is_dup else 0,
            "matches": [{"vendor": "Delta Airlines", "amount": 345.00, "date": "2026-06-10"}] if is_dup else [],
        }

    def get_accounting_context(department: str) -> dict:
        result = MOCK_BUDGETS.get(department)
        if not result:
            return {"found": False, "message": f"No budget for {department}"}
        return result

    return {
        "get_policy_rules": get_policy_rules,
        "get_employee_profile": get_employee_profile,
        "check_duplicate": check_duplicate,
        "get_accounting_context": get_accounting_context,
    }
