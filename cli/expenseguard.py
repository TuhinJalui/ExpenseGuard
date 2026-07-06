"""
expenseguard.py — ExpenseGuard CLI  (Agent Skills / CLI concept)

Usage:
  python cli/expenseguard.py submit  --employee E1001 --amount 250 --category travel --vendor "Delta Airlines" --date 2026-06-25
  python cli/expenseguard.py review  --id EXP-ABC123
  python cli/expenseguard.py audit   [--employee E1001] [--limit 20]
  python cli/expenseguard.py policy  --category travel --role employee
  python cli/expenseguard.py seed

Design note: The CLI runs the exact same agent pipeline as the web UI —
same Intake → Policy → Router chain. This demonstrates the "Agent Skills"
concept by making the multi-agent system accessible from a developer terminal,
not just a browser.
"""

import click
import json
import sys
import uuid
from pathlib import Path
from datetime import datetime

# Resolve project root regardless of where the CLI is invoked from
sys.path.insert(0, str(Path(__file__).parent.parent))


def _ensure_db():
    """Seed the database if it hasn't been created yet."""
    db_path = Path(__file__).parent.parent / "mcp_server" / "company_systems.db"
    if not db_path.exists():
        click.echo("[CLI] First run — seeding database...")
        from mcp_server.seed_data import seed
        seed()


@click.group()
def cli():
    """ExpenseGuard — multi-agent expense validation from your terminal."""
    pass


# ── submit ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--employee", "-e", required=True, help="Employee ID  (e.g. E1001)")
@click.option("--amount",   "-a", required=True, type=float, help="Amount in USD")
@click.option("--category", "-c", required=True, help="meals | travel | software | ...")
@click.option("--vendor",   "-v", required=True, help="Vendor / merchant name")
@click.option("--date",     "-d", default=None,  help="YYYY-MM-DD  (default: today)")
@click.option("--description", default="", help="Optional description")
@click.option("--receipt",  default=None, help="Receipt text (optional)")
def submit(employee, amount, category, vendor, date, description, receipt):
    """
    Submit an expense through the full three-agent pipeline.

    Shows the reasoning trace from every agent so you can see exactly
    why the system made its decision.
    """
    _ensure_db()

    if not date:
        date = datetime.today().strftime("%Y-%m-%d")

    click.echo(f"\n{'='*62}")
    click.echo("  ExpenseGuard  —  Expense Submission")
    click.echo(f"{'='*62}")
    click.echo(f"  Employee  : {employee}")
    click.echo(f"  Vendor    : {vendor}")
    click.echo(f"  Amount    : ${amount:.2f}")
    click.echo(f"  Category  : {category}")
    click.echo(f"  Date      : {date}")
    click.echo(f"{'='*62}\n")

    from agents.intake import ExpenseSubmission
    from agents.pipeline import run_pipeline
    from security.audit_log import AuditLog
    from dotenv import load_dotenv
    load_dotenv()

    # PII warning if receipt text provided
    if receipt:
        from security.pii_redaction import redact_pii
        redacted = redact_pii(receipt)
        if redacted != receipt:
            click.secho("  [Security] PII detected in receipt — will be redacted before LLM.", fg="yellow")

    submission = ExpenseSubmission(
        employee_id=employee,
        description=description or f"{category} — {vendor}",
        amount=amount,
        category=category,
        date=date,
        receipt_text=receipt,
    )

    audit = AuditLog()
    result = run_pipeline(submission, requesting_user_id=employee, audit_log=audit)

    # ── Trace output ──────────────────────────────────────────────────────────
    click.echo("  Agent pipeline trace:")
    for step in result.trace.steps:
        tool_summary = ""
        if step.tool_calls:
            names = ", ".join(tc.tool_name for tc in step.tool_calls)
            tool_summary = f"  [tools: {names}]"
        click.secho(f"    ✓ {step.agent_name}{tool_summary}", fg="cyan")
        click.echo(f"      {step.reasoning[:120]}{'...' if len(step.reasoning) > 120 else ''}")

    # ── Decision ──────────────────────────────────────────────────────────────
    decision = result.routing_decision.decision
    colors = {"auto-approved": "green", "escalate-to-human": "yellow", "rejected": "red"}

    click.echo(f"\n  Expense ID : {result.expense_id}")
    click.echo(f"  Extraction : {result.structured_expense.extraction_method}")
    click.echo(f"  Policy     : {result.compliance_verdict.status.upper()}")
    click.echo("  Decision   : ", nl=False)
    click.secho(decision.upper(), fg=colors.get(decision, "white"), bold=True)
    click.echo(f"  Reason     : {result.routing_decision.reason}")

    if result.routing_decision.risk_signals:
        click.echo("\n  Risk signals:")
        for sig in result.routing_decision.risk_signals:
            click.secho(f"    ⚠  {sig}", fg="yellow")

    if result.routing_decision.approver_id:
        click.echo(f"\n  Routed to  : {result.routing_decision.approver_id}")

    click.echo(f"\n  Audit entry written: {result.expense_id}\n")


# ── review ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--id", "expense_id", required=True, help="Expense ID  (e.g. EXP-ABC123)")
def review(expense_id):
    """
    Review a submitted expense — shows the full agent reasoning trail.
    """
    _ensure_db()
    from security.audit_log import AuditLog

    entry = AuditLog().get_by_expense_id(expense_id)
    if not entry:
        click.secho(f"  Expense '{expense_id}' not found.", fg="red")
        sys.exit(1)

    click.echo(f"\n{'='*62}")
    click.echo(f"  Expense Review  —  {expense_id}")
    click.echo(f"{'='*62}")
    click.echo(f"  Employee  : {entry['employee_id']}")
    click.echo(f"  Vendor    : {entry['vendor']}")
    click.echo(f"  Amount    : ${entry['amount']:.2f}")
    click.echo(f"  Category  : {entry['category']}")
    click.echo(f"  Date      : {entry['date']}")
    click.echo(f"  Submitted : {entry['pipeline_timestamp']}")

    pv = entry.get("policy_verdict", {})
    status = pv.get("status", "unknown")
    sc = {"compliant": "green", "flagged": "yellow", "violation": "red"}
    click.echo(f"\n  Policy verdict  : ", nl=False)
    click.secho(status.upper(), fg=sc.get(status, "white"))
    if pv.get("rule_cited"):
        click.echo(f"  Rule cited      : {pv['rule_cited']}")

    signals = entry.get("risk_signals", [])
    if signals:
        click.echo("\n  Risk signals:")
        for s in signals:
            click.secho(f"    ⚠  {s}", fg="yellow")

    rd = entry.get("routing_decision", {})
    decision = rd.get("decision", "unknown")
    dc = {"auto-approved": "green", "escalate-to-human": "yellow", "rejected": "red"}
    click.echo(f"\n  Decision  : ", nl=False)
    click.secho(decision.upper(), fg=dc.get(decision, "white"), bold=True)
    click.echo(f"  Reason    : {rd.get('reason', '')}")

    # Show reasoning trace if available (Phase 2)
    trace = entry.get("reasoning_trace")
    if trace and trace.get("steps"):
        click.echo("\n  Full reasoning trace:")
        for step in trace["steps"]:
            agent = step.get("agent_name", "?")
            reasoning = step.get("reasoning", "")[:100]
            tools = [tc["tool_name"] for tc in step.get("tool_calls", [])]
            tool_str = f"  [{', '.join(tools)}]" if tools else ""
            click.secho(f"    • {agent}{tool_str}", fg="cyan")
            if reasoning:
                click.echo(f"      {reasoning}")
    click.echo()


# ── audit ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--employee", "-e", default=None, help="Filter by employee ID")
@click.option("--limit", default=20, help="Max entries to show")
def audit(employee, limit):
    """Show the immutable audit trail."""
    _ensure_db()
    from security.audit_log import AuditLog

    log = AuditLog()
    entries = log.get_by_employee(employee) if employee else log.get_all(limit=limit)

    label = f"employee {employee}" if employee else f"last {limit} entries"
    click.echo(f"\nAudit trail — {label}")
    click.echo(f"{'='*82}")
    click.echo(f"  {'ID':<18} {'Emp':<7} {'Vendor':<22} {'Amt':>8}  {'Decision':<22} Date")
    click.echo(f"{'='*82}")

    dc = {"auto-approved": "green", "escalate-to-human": "yellow", "rejected": "red"}
    for e in entries:
        rd  = e.get("routing_decision", {})
        dec = rd.get("decision", "unknown")
        click.echo(
            f"  {e['expense_id']:<18} {e['employee_id']:<7} "
            f"{e['vendor'][:20]:<22} ${e['amount']:>7.2f}  ",
            nl=False,
        )
        click.secho(f"{dec:<22}", fg=dc.get(dec, "white"), nl=False)
        click.echo(f" {e['date']}")

    click.echo(f"{'='*82}")
    click.echo(f"  Total: {len(entries)} entries\n")


# ── policy ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--category", "-c", required=True, help="Expense category")
@click.option("--role",     "-r", required=True, help="employee | manager | exec")
def policy(category, role):
    """Look up policy rules for a category × role combination."""
    _ensure_db()
    from tests.mock_mcp_tools import get_mock_mcp_tools
    result = get_mock_mcp_tools()["get_policy_rules"](category=category, role=role)

    click.echo(f"\nPolicy  —  {category} / {role}")
    click.echo("─" * 50)
    if not result.get("found"):
        click.secho(f"  No policy defined for {category}/{role}", fg="red")
        return
    click.echo(f"  Spend limit           : ${result['spend_limit']:.2f}")
    if result.get("requires_receipt_above") is not None:
        click.echo(f"  Receipt required above: ${result['requires_receipt_above']:.2f}")
    if result.get("requires_pre_approval_above") is not None:
        click.echo(f"  Pre-approval above    : ${result['requires_pre_approval_above']:.2f}")
    if result.get("allowed_vendors"):
        click.echo(f"  Approved vendors      : {', '.join(result['allowed_vendors'])}")
    if result.get("notes"):
        click.echo(f"  Notes                 : {result['notes']}")
    click.echo()


# ── seed ──────────────────────────────────────────────────────────────────────

@cli.command()
def seed():
    """Seed the mock company database (run once on first setup)."""
    from mcp_server.seed_data import seed as run_seed
    run_seed()
    click.secho("\n  Database seeded successfully.\n", fg="green")


if __name__ == "__main__":
    cli()
