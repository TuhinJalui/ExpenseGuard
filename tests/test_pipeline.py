"""
test_pipeline.py — End-to-end pipeline tests

Covers:
  - Policy Agent: compliance rules (pass, violation, flag)
  - Router Agent: routing decisions (auto-approve, reject, escalate)
  - Trace:        AgentStep + ToolCall records are populated correctly
  - Audit log:    entries written immutably
  - PII redaction
  - RBAC
"""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.intake import StructuredExpense
from agents.policy import run_policy_agent, ComplianceVerdict
from agents.router import run_router_agent, RoutingDecision
from agents.trace import AgentStep, ToolCall
from security.audit_log import AuditLog
from tests.mock_mcp_tools import get_mock_mcp_tools


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def audit_log(tmp_path):
    return AuditLog(db_path=tmp_path / "test_audit.db")


@pytest.fixture
def mcp_tools():
    return get_mock_mcp_tools()


def make_expense(**kwargs) -> StructuredExpense:
    defaults = dict(
        employee_id="E1001",
        vendor="Acme Corp",
        amount=50.0,
        currency="USD",
        category="meals",
        date="2026-06-25",
        description="Team lunch",
        receipt_data=None,
    )
    return StructuredExpense(**{**defaults, **kwargs})


# ── Policy Agent: compliance rules ───────────────────────────────────────────

def test_compliant_expense(mcp_tools):
    """Travel expense within limits + receipt → compliant."""
    expense = make_expense(
        vendor="Delta Airlines", amount=250.0, category="travel",
        receipt_data={"vendor": "Delta Airlines", "amount": 250.0, "date": "2026-06-25"},
    )
    verdict, step = run_policy_agent(expense, mcp_tools)
    assert verdict.status == "compliant"
    assert verdict.spend_limit == 500.0
    assert verdict.employee_role == "employee"


def test_policy_step_has_tool_calls(mcp_tools):
    """Policy Agent must record MCP tool calls in its trace step."""
    expense = make_expense(vendor="Delta Airlines", amount=100.0, category="travel",
                           receipt_data={"vendor": "Delta Airlines", "amount": 100.0})
    verdict, step = run_policy_agent(expense, mcp_tools)
    assert isinstance(step, AgentStep)
    assert step.agent_name == "Policy Agent"
    tool_names = [tc.tool_name for tc in step.tool_calls]
    assert "get_employee_profile" in tool_names
    assert "get_policy_rules" in tool_names


def test_amount_exceeds_limit(mcp_tools):
    """Travel expense over $500 limit for employee → violation."""
    expense = make_expense(vendor="Delta Airlines", amount=600.0, category="travel")
    verdict, step = run_policy_agent(expense, mcp_tools)
    assert verdict.status == "violation"
    assert "500" in verdict.rule_cited


def test_pre_approval_required(mcp_tools):
    """Travel >$300 requires pre-approval → flagged."""
    expense = make_expense(vendor="Delta Airlines", amount=350.0, category="travel")
    verdict, step = run_policy_agent(expense, mcp_tools)
    assert verdict.status == "flagged"
    assert verdict.requires_pre_approval is True


def test_vendor_restriction_violation(mcp_tools):
    """Software from non-approved vendor → violation."""
    expense = make_expense(vendor="SomeRandomSaaS", amount=49.0, category="software")
    verdict, step = run_policy_agent(expense, mcp_tools)
    assert verdict.status == "violation"
    assert "SomeRandomSaaS" in verdict.rule_cited


def test_category_not_covered(mcp_tools):
    """Entertainment not covered for employees (spend_limit=$0) → violation."""
    expense = make_expense(vendor="Fancy Restaurant", amount=80.0, category="entertainment")
    verdict, step = run_policy_agent(expense, mcp_tools)
    assert verdict.status == "violation"
    assert verdict.spend_limit == 0.0


def test_unknown_employee(mcp_tools):
    """Unknown employee ID → violation."""
    expense = make_expense(employee_id="UNKNOWN99")
    verdict, step = run_policy_agent(expense, mcp_tools)
    assert verdict.status == "violation"
    assert "not found" in verdict.rule_cited.lower()


def test_receipt_required_missing(mcp_tools):
    """Meals >$25 without receipt → flagged."""
    expense = make_expense(
        vendor="Chipotle", amount=30.0, category="meals",
        receipt_data=None,   # no receipt
    )
    verdict, step = run_policy_agent(expense, mcp_tools)
    assert verdict.status == "flagged"
    assert verdict.requires_receipt is True


# ── Router Agent: routing decisions ──────────────────────────────────────────

def test_auto_approve_compliant(mcp_tools, audit_log):
    """Compliant + no risk signals → auto-approved."""
    expense = make_expense(
        vendor="GitHub", amount=10.0, category="software",
        receipt_data={"vendor": "GitHub", "amount": 10.0},
    )
    verdict = ComplianceVerdict(
        status="compliant", details="Within limits.",
        employee_role="employee", spend_limit=100.0,
    )
    decision, step = run_router_agent(expense, verdict, mcp_tools, audit_log, "EXP-TEST-001")
    assert decision.decision == "auto-approved"


def test_router_step_has_tool_calls(mcp_tools, audit_log):
    """Router Agent must record MCP tool calls in its trace step."""
    expense = make_expense(vendor="GitHub", amount=10.0, category="software",
                           receipt_data={"vendor": "GitHub", "amount": 10.0})
    verdict = ComplianceVerdict(
        status="compliant", details="OK", employee_role="employee", spend_limit=100.0
    )
    decision, step = run_router_agent(expense, verdict, mcp_tools, audit_log, "EXP-TEST-TRACE")
    assert isinstance(step, AgentStep)
    assert step.agent_name == "Risk & Routing Agent"
    tool_names = [tc.tool_name for tc in step.tool_calls]
    assert "check_duplicate" in tool_names
    assert "get_employee_profile" in tool_names
    assert "get_accounting_context" in tool_names


def test_reject_violation(mcp_tools, audit_log):
    """Policy violation → always rejected regardless of signals."""
    expense = make_expense(vendor="Capital Grille", amount=80.0, category="entertainment")
    verdict = ComplianceVerdict(
        status="violation",
        rule_cited="$0 spend limit for entertainment/employee",
        details="Not covered.",
        employee_role="employee",
        spend_limit=0.0,
    )
    decision, step = run_router_agent(expense, verdict, mcp_tools, audit_log, "EXP-TEST-002")
    assert decision.decision == "rejected"
    assert decision.rule_cited is not None


def test_escalate_flagged(mcp_tools, audit_log):
    """Flagged compliance → escalated to manager."""
    expense = make_expense(vendor="Delta Airlines", amount=350.0, category="travel")
    verdict = ComplianceVerdict(
        status="flagged",
        rule_cited="Pre-approval required above $300",
        details="Pre-approval required.",
        employee_role="employee",
        spend_limit=500.0,
        requires_pre_approval=True,
    )
    decision, step = run_router_agent(expense, verdict, mcp_tools, audit_log, "EXP-TEST-003")
    assert decision.decision == "escalate-to-human"
    assert decision.approver_id == "E2001"   # Alice (E1001) reports to Frank (E2001)


def test_escalate_duplicate(mcp_tools, audit_log):
    """Duplicate submission → escalated even if compliant."""
    # E1001 + Delta + $345 matches the mock duplicate
    expense = make_expense(
        employee_id="E1001", vendor="Delta Airlines", amount=345.0, category="travel"
    )
    verdict = ComplianceVerdict(
        status="compliant", details="Within limits.",
        employee_role="employee", spend_limit=500.0,
    )
    decision, step = run_router_agent(expense, verdict, mcp_tools, audit_log, "EXP-TEST-004")
    assert decision.decision == "escalate-to-human"
    assert any("duplicate" in s.lower() for s in decision.risk_signals)


def test_near_budget_escalates(mcp_tools, audit_log):
    """Marketing dept is at 91.8% budget → high-scrutiny signal triggers escalation."""
    expense = make_expense(
        employee_id="E1003",   # Carol — Marketing
        vendor="Hilton Hotels", amount=180.0, category="travel",
    )
    verdict = ComplianceVerdict(
        status="compliant", details="Within limits.",
        employee_role="employee", spend_limit=500.0,
    )
    decision, step = run_router_agent(expense, verdict, mcp_tools, audit_log, "EXP-TEST-005")
    assert decision.decision == "escalate-to-human"
    assert any("91" in s or "budget" in s.lower() for s in decision.risk_signals)


def test_audit_log_written(mcp_tools, audit_log):
    """Router Agent must persist an audit entry."""
    expense = make_expense()
    verdict = ComplianceVerdict(
        status="compliant", details="OK", employee_role="employee", spend_limit=75.0
    )
    run_router_agent(expense, verdict, mcp_tools, audit_log, "EXP-AUDIT-TEST")
    entry = audit_log.get_by_expense_id("EXP-AUDIT-TEST")
    assert entry is not None
    assert entry["employee_id"] == "E1001"
    assert entry["routing_decision"]["decision"] in {
        "auto-approved", "escalate-to-human", "rejected"
    }


def test_audit_entry_is_immutable(mcp_tools, audit_log):
    """Writing the same expense_id twice keeps the first entry (immutable)."""
    expense = make_expense(amount=40.0)
    verdict = ComplianceVerdict(
        status="compliant", details="OK", employee_role="employee", spend_limit=75.0
    )
    run_router_agent(expense, verdict, mcp_tools, audit_log, "EXP-IMMUTABLE")
    # Try to write again with different amount
    expense2 = make_expense(amount=999.0)
    run_router_agent(expense2, verdict, mcp_tools, audit_log, "EXP-IMMUTABLE")
    entry = audit_log.get_by_expense_id("EXP-IMMUTABLE")
    # Original amount must be preserved
    assert entry["amount"] == 40.0


# ── PII Redaction ─────────────────────────────────────────────────────────────

def test_pii_card_redaction():
    from security.pii_redaction import redact_pii
    result = redact_pii("Card: 4111 1111 1111 1111 Total: $42.00")
    assert "4111 1111 1111 1111" not in result
    assert "[REDACTED:CARD]" in result


def test_pii_email_redaction():
    from security.pii_redaction import redact_pii
    result = redact_pii("Contact: alice@example.com")
    assert "alice@example.com" not in result
    assert "[REDACTED:EMAIL]" in result


def test_pii_phone_redaction():
    from security.pii_redaction import redact_pii
    result = redact_pii("Call 555-123-4567")
    assert "555-123-4567" not in result
    assert "[REDACTED:PHONE]" in result


def test_pii_no_false_positive():
    from security.pii_redaction import redact_pii
    # Expense amounts must not be redacted
    result = redact_pii("Total: $345.00 for 2 travelers on June 25")
    assert "345.00" in result


def test_pii_multiple_patterns():
    from security.pii_redaction import redact_pii
    text = "Card: 4111 1111 1111 1111\nEmail: bob@corp.com\nPhone: (555) 987-6543"
    result = redact_pii(text)
    assert "[REDACTED:CARD]" in result
    assert "[REDACTED:EMAIL]" in result
    assert "[REDACTED:PHONE]" in result
    # Original values gone
    assert "4111" not in result
    assert "bob@corp.com" not in result
    assert "987-6543" not in result


# ── RBAC ──────────────────────────────────────────────────────────────────────

def test_rbac_self_submit():
    from security.rbac import RBACMiddleware
    RBACMiddleware().assert_can_submit("E1001", "E1001")  # must not raise


def test_rbac_cross_submit_denied():
    from security.rbac import RBACMiddleware, RBACException
    with pytest.raises(RBACException):
        RBACMiddleware().assert_can_submit("E1001", "E1002")


def test_rbac_manager_can_view_report():
    from security.rbac import RBACMiddleware
    RBACMiddleware().assert_can_view("E2001", "E1001")   # E2001 manages E1001


def test_rbac_manager_cannot_view_non_report():
    from security.rbac import RBACMiddleware, RBACException
    with pytest.raises(RBACException):
        RBACMiddleware().assert_can_view("E2001", "E1003")  # E1003 is Marketing


def test_rbac_exec_can_view_anyone():
    from security.rbac import RBACMiddleware
    RBACMiddleware().assert_can_view("E3001", "E1001")   # E3001 is exec


def test_rbac_exec_can_submit_for_anyone():
    from security.rbac import RBACMiddleware
    RBACMiddleware().assert_can_submit("E3001", "E1001")  # exec bypass
