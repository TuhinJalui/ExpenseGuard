"""
policy.py — Policy Agent

Responsibility: Evaluate a structured expense against company policy rules.

Input:  StructuredExpense (from Intake Agent)
Output: ComplianceVerdict  (compliant / flagged / violation + cited rule)
        AgentStep          (reasoning trace entry for Audit Trail)

MCP tools called:
  1. get_employee_profile(employee_id) → determines which policy tier applies
  2. get_policy_rules(category, role)  → fetches the actual spend limits and rules

Design note: The compliance evaluation is fully deterministic code once the
MCP data is fetched. This is intentional — it keeps the decision logic
auditable and testable without an LLM, while the MCP calls demonstrate
real tool-use that judges can see in the trace.
"""

import time
from pydantic import BaseModel, Field
from typing import Optional, Literal

from agents.intake import StructuredExpense
from agents.trace import AgentStep, ToolCall


# ── Output contract ───────────────────────────────────────────────────────────

class ComplianceVerdict(BaseModel):
    """Typed output — the contract passed to the Risk & Routing Agent."""

    status: Literal["compliant", "flagged", "violation"]
    """
    compliant  — within all limits, receipt/pre-approval requirements met
    flagged    — policy concern that needs human judgement
    violation  — clear, unambiguous policy breach → always rejected
    """

    rule_cited: Optional[str] = Field(
        default=None,
        description="Exact policy rule that was breached or flagged"
    )

    details: str = Field(
        description="Plain-language explanation (shown to approver and employee)"
    )

    employee_role: str = Field(
        description="Role resolved from MCP employee profile"
    )

    spend_limit: Optional[float] = Field(
        default=None,
        description="Applicable per-transaction spend limit"
    )

    requires_receipt: bool = Field(
        default=False,
        description="True if policy requires a receipt for this amount"
    )

    requires_pre_approval: bool = Field(
        default=False,
        description="True if pre-approval was required for this amount"
    )


# ── Agent execution ───────────────────────────────────────────────────────────

def run_policy_agent(
    expense: StructuredExpense,
    mcp_tools: dict,
) -> tuple[ComplianceVerdict, AgentStep]:
    """
    Executes the Policy Agent.

    Args:
        expense:   StructuredExpense from the Intake Agent
        mcp_tools: Dict of MCP tool callables (real or mock)
                   Keys: get_employee_profile, get_policy_rules

    Returns:
        (ComplianceVerdict, AgentStep)  — verdict + trace entry

    Design note: accepting mcp_tools as a parameter makes this fully
    testable without a running MCP server. The production pipeline injects
    real SQLite-backed tools; tests inject mock tools.
    """
    started_at = time.monotonic()
    tool_calls: list[ToolCall] = []

    # ── MCP Call 1: employee profile ──────────────────────────────────────────
    t0 = time.monotonic()
    profile_result = mcp_tools["get_employee_profile"](employee_id=expense.employee_id)
    tool_calls.append(ToolCall(
        tool_name="get_employee_profile",
        arguments={"employee_id": expense.employee_id},
        result=profile_result,
        duration_ms=round((time.monotonic() - t0) * 1000, 1),
    ))

    if not profile_result.get("found"):
        verdict = ComplianceVerdict(
            status="violation",
            rule_cited="Employee not found in HR system",
            details=f"Employee '{expense.employee_id}' does not exist in the system. "
                    f"Submission rejected pending identity verification.",
            employee_role="unknown",
        )
        return verdict, _make_step(expense, tool_calls, verdict, started_at)

    employee_role = profile_result["role"]

    # ── MCP Call 2: policy rules ──────────────────────────────────────────────
    t0 = time.monotonic()
    policy_result = mcp_tools["get_policy_rules"](
        category=expense.category,
        role=employee_role,
    )
    tool_calls.append(ToolCall(
        tool_name="get_policy_rules",
        arguments={"category": expense.category, "role": employee_role},
        result=policy_result,
        duration_ms=round((time.monotonic() - t0) * 1000, 1),
    ))

    if not policy_result.get("found"):
        verdict = ComplianceVerdict(
            status="flagged",
            rule_cited=f"No policy defined for category='{expense.category}' / role='{employee_role}'",
            details="This expense category has no defined policy for this employee role. "
                    "Routing to manual review.",
            employee_role=employee_role,
        )
        return verdict, _make_step(expense, tool_calls, verdict, started_at)

    # ── Evaluate rules deterministically ─────────────────────────────────────
    spend_limit          = policy_result["spend_limit"]
    receipt_threshold    = policy_result.get("requires_receipt_above")
    preapproval_threshold = policy_result.get("requires_pre_approval_above")
    allowed_vendors      = policy_result.get("allowed_vendors")   # list or None

    # Rule: category not reimbursable (spend_limit == 0)
    if spend_limit == 0.0:
        verdict = ComplianceVerdict(
            status="violation",
            rule_cited=(
                f"Category '{expense.category}' has a $0 spend limit for "
                f"role '{employee_role}' — not reimbursable."
            ),
            details=(
                f"'{expense.category}' expenses are not covered for {employee_role}s. "
                f"Policy note: {policy_result.get('notes', 'See expense policy.')}"
            ),
            employee_role=employee_role,
            spend_limit=0.0,
        )
        return verdict, _make_step(expense, tool_calls, verdict, started_at)

    # Rule: amount exceeds spend limit
    if expense.amount > spend_limit:
        verdict = ComplianceVerdict(
            status="violation",
            rule_cited=(
                f"Amount ${expense.amount:.2f} exceeds the {employee_role} "
                f"spend limit of ${spend_limit:.2f} for '{expense.category}'."
            ),
            details=(
                f"The submitted amount of ${expense.amount:.2f} exceeds the "
                f"${spend_limit:.2f} per-transaction limit for {employee_role}s "
                f"in '{expense.category}'. "
                f"{policy_result.get('notes', '')}"
            ),
            employee_role=employee_role,
            spend_limit=spend_limit,
        )
        return verdict, _make_step(expense, tool_calls, verdict, started_at)

    # Rule: vendor not on approved list
    if allowed_vendors and expense.vendor not in allowed_vendors:
        verdict = ComplianceVerdict(
            status="violation",
            rule_cited=(
                f"Vendor '{expense.vendor}' is not on the approved vendor list "
                f"for '{expense.category}': {allowed_vendors}."
            ),
            details=(
                f"'{expense.category}' purchases must use approved vendors only. "
                f"'{expense.vendor}' is not approved. "
                f"Approved: {', '.join(allowed_vendors)}."
            ),
            employee_role=employee_role,
            spend_limit=spend_limit,
        )
        return verdict, _make_step(expense, tool_calls, verdict, started_at)

    # Rule: pre-approval required
    if preapproval_threshold is not None and expense.amount > preapproval_threshold:
        verdict = ComplianceVerdict(
            status="flagged",
            rule_cited=(
                f"Amount ${expense.amount:.2f} exceeds the pre-approval threshold "
                f"of ${preapproval_threshold:.2f} for '{expense.category}'."
            ),
            details=(
                f"Pre-approval is required for {employee_role} '{expense.category}' "
                f"expenses above ${preapproval_threshold:.2f}. "
                f"Please attach pre-approval documentation."
            ),
            employee_role=employee_role,
            spend_limit=spend_limit,
            requires_pre_approval=True,
        )
        return verdict, _make_step(expense, tool_calls, verdict, started_at)

    # Rule: receipt required
    has_receipt      = expense.receipt_data is not None
    receipt_required = (receipt_threshold is not None and expense.amount > receipt_threshold)
    if receipt_required and not has_receipt:
        verdict = ComplianceVerdict(
            status="flagged",
            rule_cited=(
                f"Receipt required for '{expense.category}' expenses above "
                f"${receipt_threshold:.2f}."
            ),
            details=(
                f"A receipt is required for amounts over ${receipt_threshold:.2f}. "
                f"Please attach a valid receipt."
            ),
            employee_role=employee_role,
            spend_limit=spend_limit,
            requires_receipt=True,
        )
        return verdict, _make_step(expense, tool_calls, verdict, started_at)

    # All checks passed
    verdict = ComplianceVerdict(
        status="compliant",
        details=(
            f"Expense satisfies all policy rules "
            f"(limit: ${spend_limit:.2f}, role: {employee_role})."
        ),
        employee_role=employee_role,
        spend_limit=spend_limit,
        requires_receipt=receipt_required,
    )
    return verdict, _make_step(expense, tool_calls, verdict, started_at)


# ── Trace helper ──────────────────────────────────────────────────────────────

def _make_step(
    expense: StructuredExpense,
    tool_calls: list[ToolCall],
    verdict: ComplianceVerdict,
    started_at: float,
) -> AgentStep:
    """Builds the AgentStep trace entry for this policy check."""
    status_labels = {
        "compliant":  "All policy rules satisfied.",
        "flagged":    "Policy flag raised — needs human review.",
        "violation":  "Policy violation detected — will be rejected.",
    }
    reasoning = (
        f"Checked {len(tool_calls)} MCP tool(s). "
        f"Employee role resolved as '{verdict.employee_role}'. "
        f"Verdict: {verdict.status.upper()}. "
        f"{status_labels.get(verdict.status, '')} "
        + (f"Rule: {verdict.rule_cited}" if verdict.rule_cited else "")
    )

    return AgentStep(
        agent_name="Policy Agent",
        started_at=str(started_at),
        inputs={
            "employee_id": expense.employee_id,
            "vendor": expense.vendor,
            "amount": expense.amount,
            "category": expense.category,
        },
        tool_calls=tool_calls,
        output={
            "status": verdict.status,
            "rule_cited": verdict.rule_cited,
            "employee_role": verdict.employee_role,
            "spend_limit": verdict.spend_limit,
            "requires_receipt": verdict.requires_receipt,
            "requires_pre_approval": verdict.requires_pre_approval,
        },
        reasoning=reasoning,
    )


# ── Standalone test harness ───────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, "..")
    from tests.mock_mcp_tools import get_mock_mcp_tools
    from agents.intake import StructuredExpense

    cases = [
        ("Compliant meal",         "E1001", "Chipotle",         23.50, "meals"),
        ("Violation: over limit",  "E1001", "United Airlines", 890.00, "travel"),
        ("Flagged: pre-approval",  "E1001", "Delta Airlines",  350.00, "travel"),
        ("Violation: bad vendor",  "E1001", "SomeRandomSaaS",   49.00, "software"),
        ("Violation: entertainment", "E1001", "Capital Grille", 80.00, "entertainment"),
    ]

    for label, emp, vendor, amt, cat in cases:
        exp = StructuredExpense(
            employee_id=emp, vendor=vendor, amount=amt,
            currency="USD", category=cat, date="2026-06-25",
            description=label,
        )
        verdict, step = run_policy_agent(exp, get_mock_mcp_tools())
        print(f"\n[{label}]")
        print(f"  Status:  {verdict.status.upper()}")
        print(f"  Rule:    {verdict.rule_cited or '—'}")
        print(f"  Tools:   {[tc.tool_name for tc in step.tool_calls]}")
