"""
main.py — FastAPI Backend for ExpenseGuard

Endpoints:
  POST /api/expenses/submit              Submit + run full agent pipeline
  GET  /api/expenses/{expense_id}        Single expense detail + full trace
  GET  /api/expenses/employee/{id}       All expenses for an employee
  GET  /api/expenses/approvals/{id}      Pending approvals for a manager
  GET  /api/audit/all                    All entries (exec/finance role only)
  GET  /api/health                       Health + config status

Security enforced on every protected route:
  - X-User-ID header (simulated auth — production would decode a JWT)
  - RBAC checked server-side before any agent work starts
  - PII redaction runs inside the pipeline before LLM ingestion
"""

import os
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from agents.intake import ExpenseSubmission
from agents.pipeline import run_pipeline
from security.audit_log import AuditLog
from security.rbac import RBACMiddleware, RBACException

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ExpenseGuard API",
    description="Multi-agent expense validation and routing — Google ADK capstone",
    version="2.0.0",
)

_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    # Vercel deployments
    "https://expense-guard.vercel.app",
    "https://expenseguard.vercel.app",
]
# Also allow any custom FRONTEND_URL from env (set this on Render/Vercel)
_frontend_url = os.getenv("FRONTEND_URL")
if _frontend_url:
    _ALLOWED_ORIGINS.append(_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",   # all Vercel preview URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared singletons
_audit_log = AuditLog()
_rbac = RBACMiddleware()


# ── Request / response models ─────────────────────────────────────────────────

class SubmitExpenseRequest(BaseModel):
    employee_id: str
    description: str
    amount: Optional[float] = None
    category: str
    date: str                               # YYYY-MM-DD
    receipt_text: Optional[str] = None


class SubmitExpenseResponse(BaseModel):
    success: bool
    expense_id: str
    decision: str                           # auto-approved | escalate-to-human | rejected
    reason: str
    compliance_status: str                  # compliant | flagged | violation
    extraction_method: str                  # gemini_text | gemini_vision | employee_entered
    risk_signals: list[str]
    approver_id: Optional[str] = None
    trace_steps: list[str]                  # Agent names in execution order (for UI)


# ── Auth helper ───────────────────────────────────────────────────────────────

def _require_user(x_user_id: Optional[str]) -> str:
    """Extracts the requesting user from the X-User-ID header."""
    if not x_user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required — provide X-User-ID header"
        )
    return x_user_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health_check():
    """
    Health + configuration status.
    Reports whether the Gemini API key is configured (affects extraction mode).
    """
    api_key_set = bool(os.getenv("GOOGLE_API_KEY"))
    return {
        "status": "healthy",
        "service": "ExpenseGuard",
        "version": "2.0.0",
        "gemini_configured": api_key_set,
        "extraction_mode": "gemini" if api_key_set else "fallback (employee-entered fields)",
    }


@app.post("/api/expenses/submit", response_model=SubmitExpenseResponse)
def submit_expense(
    request: SubmitExpenseRequest,
    x_user_id: str = Header(None),
):
    """
    Submit an expense through the full three-agent pipeline.

    Pipeline stages (all visible in the returned trace_steps):
      1. PII Redaction   — strips card numbers, emails, phones before LLM
      2. Intake Agent    — raw fields → StructuredExpense (Gemini or fallback)
      3. Policy Agent    — MCP policy/profile lookup → ComplianceVerdict
      4. Router Agent    — MCP duplicate/budget check → RoutingDecision

    RBAC: X-User-ID must match employee_id (or be an exec).
    """
    requesting_user = _require_user(x_user_id)

    submission = ExpenseSubmission(
        employee_id=request.employee_id,
        description=request.description,
        amount=request.amount,
        category=request.category,
        date=request.date,
        receipt_text=request.receipt_text,
    )

    try:
        result = run_pipeline(
            submission,
            requesting_user_id=requesting_user,
            audit_log=_audit_log,
        )
    except RBACException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {e}")

    return SubmitExpenseResponse(
        success=True,
        expense_id=result.expense_id,
        decision=result.routing_decision.decision,
        reason=result.routing_decision.reason,
        compliance_status=result.compliance_verdict.status,
        extraction_method=result.structured_expense.extraction_method,
        risk_signals=result.routing_decision.risk_signals,
        approver_id=result.routing_decision.approver_id,
        trace_steps=[step.agent_name for step in result.trace.steps],
    )


@app.get("/api/expenses/{expense_id}")
def get_expense(expense_id: str, x_user_id: str = Header(None)):
    """
    Full detail for one expense including the complete reasoning trace.
    RBAC: must be the submitter, their manager, or exec.
    """
    user = _require_user(x_user_id)
    entry = _audit_log.get_by_expense_id(expense_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Expense not found")
    try:
        _rbac.assert_can_view(user, entry["employee_id"])
    except RBACException as e:
        raise HTTPException(status_code=403, detail=str(e))
    return entry


@app.get("/api/expenses/employee/{employee_id}")
def get_employee_expenses(employee_id: str, x_user_id: str = Header(None)):
    """
    All expenses for an employee.
    RBAC: must be the employee, their manager, or exec.
    """
    user = _require_user(x_user_id)
    try:
        _rbac.assert_can_view(user, employee_id)
    except RBACException as e:
        raise HTTPException(status_code=403, detail=str(e))
    return {"expenses": _audit_log.get_by_employee(employee_id)}


@app.get("/api/expenses/approvals/{approver_id}")
def get_pending_approvals(approver_id: str, x_user_id: str = Header(None)):
    """
    Expenses escalated to this approver that are pending review.
    RBAC: must be the approver or exec.
    """
    user = _require_user(x_user_id)
    if user != approver_id:
        # Allow execs to view any queue
        role = _rbac._get_employee_role(user)
        if role != "exec":
            raise HTTPException(
                status_code=403,
                detail="You can only view your own approval queue"
            )
    return {"pending_approvals": _audit_log.get_pending_approvals(approver_id)}


@app.post("/api/expenses/{expense_id}/approve")
def approve_expense(expense_id: str, x_user_id: str = Header(None)):
    """
    Mark an escalated expense as approved by the manager.
    RBAC: must be the designated approver or exec.
    """
    user = _require_user(x_user_id)
    entry = _audit_log.get_by_expense_id(expense_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Expense not found")
    routing = entry.get("routing_decision", {})
    if routing.get("decision") != "escalate-to-human":
        raise HTTPException(status_code=400, detail="Expense is not pending human review")
    approver_id = routing.get("approver_id")
    role = _rbac._get_employee_role(user)
    if user != approver_id and role != "exec":
        raise HTTPException(status_code=403, detail="Not authorized to approve this expense")
    _audit_log.record_human_decision(expense_id, action="approved", decided_by=user)
    return {"success": True, "expense_id": expense_id, "action": "approved", "decided_by": user}


@app.post("/api/expenses/{expense_id}/reject")
def reject_expense(expense_id: str, x_user_id: str = Header(None)):
    """
    Mark an escalated expense as rejected by the manager.
    RBAC: must be the designated approver or exec.
    """
    user = _require_user(x_user_id)
    entry = _audit_log.get_by_expense_id(expense_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Expense not found")
    routing = entry.get("routing_decision", {})
    if routing.get("decision") != "escalate-to-human":
        raise HTTPException(status_code=400, detail="Expense is not pending human review")
    approver_id = routing.get("approver_id")
    role = _rbac._get_employee_role(user)
    if user != approver_id and role != "exec":
        raise HTTPException(status_code=403, detail="Not authorized to reject this expense")
    _audit_log.record_human_decision(expense_id, action="rejected", decided_by=user)
    return {"success": True, "expense_id": expense_id, "action": "rejected", "decided_by": user}


@app.get("/api/audit/all")
def get_all_audit_entries(x_user_id: str = Header(None), limit: int = 100):
    """
    All audit entries — exec/finance role only.
    Each entry includes the full reasoning trace from all three agents.
    """
    user = _require_user(x_user_id)
    role = _rbac._get_employee_role(user)
    if role != "exec":
        raise HTTPException(
            status_code=403,
            detail="exec/finance role required to view all audit entries"
        )
    entries = _audit_log.get_all(limit=limit)
    return {"audit_entries": entries, "count": len(entries)}


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    from pathlib import Path
    db_path = Path(__file__).parent.parent / "mcp_server" / "company_systems.db"
    if not db_path.exists():
        print("[Startup] Seeding MCP database...")
        from mcp_server.seed_data import seed
        seed()

    key = os.getenv("GOOGLE_API_KEY")
    if key:
        print("[Startup] GOOGLE_API_KEY found — Intake Agent will use Gemini 2.0 Flash")
    else:
        print("[Startup] No GOOGLE_API_KEY — Intake Agent using fallback extraction")


if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv
    load_dotenv()
    uvicorn.run(app, host="0.0.0.0", port=8000)
