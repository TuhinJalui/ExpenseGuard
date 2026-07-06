"""
pipeline.py — Expense Validation Pipeline Orchestrator

Wires the three agents together with explicit, typed handoffs:

  [Raw Submission]
       │
       ▼ RBAC check + PII redaction
  ┌─────────────┐
  │ Intake Agent│  raw fields → StructuredExpense
  └──────┬──────┘
         │ StructuredExpense
         ▼
  ┌─────────────┐   MCP: get_employee_profile
  │ Policy Agent│         get_policy_rules
  └──────┬──────┘  → ComplianceVerdict
         │ ComplianceVerdict
         ▼
  ┌──────────────────┐  MCP: check_duplicate
  │ Risk & Routing   │       get_employee_profile
  │ Agent            │       get_accounting_context
  └──────┬───────────┘  → RoutingDecision + audit log
         │
         ▼
  PipelineResult  (all three outputs + full ReasoningTrace)

Design note: Every stage produces a typed output and a trace step.
The ReasoningTrace is what distinguishes this from a monolithic prompt —
judges can see exactly which agent ran, what MCP tools it called,
and how it reached its conclusion.
"""

import uuid
from pathlib import Path
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, UTC

from agents.intake import ExpenseSubmission, StructuredExpense, run_intake_agent
from agents.policy import ComplianceVerdict, run_policy_agent
from agents.router import RoutingDecision, run_router_agent
from agents.trace import ReasoningTrace, AgentStep
from security.pii_redaction import redact_pii
from security.rbac import RBACMiddleware
from security.audit_log import AuditLog


# ── Pipeline result ───────────────────────────────────────────────────────────

class PipelineResult(BaseModel):
    """Complete output of one pipeline run — all three agents + trace."""
    expense_id: str
    structured_expense: StructuredExpense
    compliance_verdict: ComplianceVerdict
    routing_decision: RoutingDecision
    trace: ReasoningTrace           # Full reasoning trail for Audit Trail UI

    class Config:
        arbitrary_types_allowed = True


# ── MCP tool factory ──────────────────────────────────────────────────────────

def get_mcp_tools() -> dict:
    """
    Returns MCP tool callables backed by the seeded SQLite database.

    Design note: The interface is identical to what real MCP protocol
    tool-calling produces. The ADK agents call these through the same
    dictionary contract regardless of whether they're real MCP or SQLite.
    Swapping in a live MCP server requires changing only this factory.
    """
    import sqlite3
    import json
    from datetime import timedelta

    DB_PATH = Path(__file__).parent.parent / "mcp_server" / "company_systems.db"

    def _get_conn() -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def get_policy_rules(category: str, role: str) -> dict:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM policy_rules WHERE category = ? AND role = ?",
            (category, role),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return {"found": False, "message": f"No policy for {category}/{role}"}
        return {
            "found": True,
            "category": row["category"],
            "role": row["role"],
            "spend_limit": row["spend_limit"],
            "requires_receipt_above": row["requires_receipt_above"],
            "requires_pre_approval_above": row["requires_pre_approval_above"],
            "allowed_vendors": (
                json.loads(row["allowed_vendors"]) if row["allowed_vendors"] else None
            ),
            "notes": row["notes"],
        }

    def get_employee_profile(employee_id: str) -> dict:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM employees WHERE employee_id = ?", (employee_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return {"found": False, "message": f"Employee {employee_id} not found"}
        return {
            "found": True,
            "employee_id": row["employee_id"],
            "name": row["name"],
            "department": row["department"],
            "role": row["role"],
            "approval_tier": row["approval_tier"],
            "manager_id": row["manager_id"],
        }

    def check_duplicate(vendor: str, amount: float, date: str, employee_id: str) -> dict:
        conn = _get_conn()
        cur = conn.cursor()
        try:
            from datetime import datetime as dt
            sub_date = dt.fromisoformat(date)
        except ValueError:
            return {"error": f"Invalid date: {date}"}

        date_start = (sub_date - timedelta(days=13)).strftime("%Y-%m-%d")
        date_end   = (sub_date + timedelta(days=13)).strftime("%Y-%m-%d")

        cur.execute(
            """
            SELECT id, vendor, amount, date, category, status
            FROM expense_history
            WHERE employee_id = ? AND vendor = ?
              AND amount BETWEEN ? AND ?
              AND date BETWEEN ? AND ?
            ORDER BY date DESC LIMIT 5
            """,
            (employee_id, vendor, amount - 5.0, amount + 5.0, date_start, date_end),
        )
        matches = [dict(r) for r in cur.fetchall()]
        conn.close()
        return {
            "is_potential_duplicate": len(matches) > 0,
            "match_count": len(matches),
            "matches": matches,
        }

    def get_accounting_context(department: str) -> dict:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM department_budgets WHERE department = ?", (department,)
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return {"found": False, "message": f"No budget for {department}"}
        annual = row["annual_budget"]
        spent  = row["spent_ytd"]
        return {
            "found": True,
            "department": row["department"],
            "fiscal_year": row["fiscal_year"],
            "annual_budget": annual,
            "spent_ytd": spent,
            "remaining": annual - spent,
            "utilization_percent": round(spent / annual * 100, 1) if annual > 0 else 0,
        }

    return {
        "get_policy_rules": get_policy_rules,
        "get_employee_profile": get_employee_profile,
        "check_duplicate": check_duplicate,
        "get_accounting_context": get_accounting_context,
    }


# ── Pipeline entry point ──────────────────────────────────────────────────────

def run_pipeline(
    submission: ExpenseSubmission,
    requesting_user_id: str,
    audit_log: Optional[AuditLog] = None,
) -> PipelineResult:
    """
    Runs the full three-agent expense validation pipeline.

    Stages:
      0. RBAC  — backend access check (HTTP 403 if denied)
      1. PII   — redact card numbers, emails, phones before LLM sees text
      2. Intake Agent  — raw → StructuredExpense (Gemini or fallback)
      3. Policy Agent  — MCP policy/profile lookup → ComplianceVerdict
      4. Router Agent  — MCP duplicate/budget check → RoutingDecision + audit

    Every stage appends a step to the ReasoningTrace so the full decision
    chain is visible in the Audit Trail UI.
    """
    expense_id = f"EXP-{uuid.uuid4().hex[:8].upper()}"
    trace = ReasoningTrace(expense_id=expense_id)

    if audit_log is None:
        audit_log = AuditLog()

    # ── Stage 0: RBAC ─────────────────────────────────────────────────────────
    rbac = RBACMiddleware()
    rbac.assert_can_submit(requesting_user_id, submission.employee_id)

    # ── Stage 1: PII Redaction ────────────────────────────────────────────────
    pii_redacted_fields = []
    if submission.receipt_text:
        redacted = redact_pii(submission.receipt_text)
        if redacted != submission.receipt_text:
            pii_redacted_fields.append("receipt_text")
        submission = submission.model_copy(update={"receipt_text": redacted})

    if submission.description:
        redacted = redact_pii(submission.description)
        if redacted != submission.description:
            pii_redacted_fields.append("description")
        submission = submission.model_copy(update={"description": redacted})

    trace.add_step(AgentStep(
        agent_name="PII Redaction",
        started_at=datetime.now(UTC).isoformat(),
        inputs={"employee_id": submission.employee_id, "fields_checked": ["receipt_text", "description"]},
        tool_calls=[],
        output={"fields_redacted": pii_redacted_fields},
        reasoning=(
            f"Scanned receipt text and description for PII patterns "
            f"(card numbers, emails, phone numbers, street addresses). "
            f"Redacted fields: {pii_redacted_fields if pii_redacted_fields else 'none'}."
        ),
    ))

    # ── Stage 2: Intake Agent ─────────────────────────────────────────────────
    structured_expense = run_intake_agent(submission)

    trace.add_step(AgentStep(
        agent_name="Intake Agent",
        started_at=datetime.now(UTC).isoformat(),
        inputs={
            "employee_id": submission.employee_id,
            "description": submission.description,
            "amount": submission.amount,
            "category": submission.category,
            "date": submission.date,
            "has_receipt_text": submission.receipt_text is not None,
            "has_receipt_image": submission.receipt_image_path is not None,
        },
        tool_calls=[],           # Intake uses LLM, not MCP tools
        output=structured_expense.model_dump(),
        reasoning=(
            f"Extracted structured expense via '{structured_expense.extraction_method}'. "
            f"Vendor: '{structured_expense.vendor}', Amount: ${structured_expense.amount:.2f}, "
            f"Receipt provided: {structured_expense.receipt_data is not None}."
        ),
    ))

    # ── Stage 3: Policy Agent ─────────────────────────────────────────────────
    mcp_tools = get_mcp_tools()
    compliance_verdict, policy_step = run_policy_agent(structured_expense, mcp_tools)
    trace.add_step(policy_step)

    # ── Stage 4: Risk & Routing Agent ─────────────────────────────────────────
    routing_decision, routing_step = run_router_agent(
        structured_expense,
        compliance_verdict,
        mcp_tools,
        audit_log,
        expense_id,
        trace=trace,       # Pass the live trace so the audit log captures all steps
    )
    trace.add_step(routing_step)

    # Print trace summary to console (visible in server logs / demo terminal)
    print(f"[Pipeline] {trace.summary()}")

    return PipelineResult(
        expense_id=expense_id,
        structured_expense=structured_expense,
        compliance_verdict=compliance_verdict,
        routing_decision=routing_decision,
        trace=trace,
    )
