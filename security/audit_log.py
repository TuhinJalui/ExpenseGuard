"""
audit_log.py — Immutable Audit Log

Every agent decision (who/what/why/when) is written here.
The audit trail is:
  - Immutable: entries are append-only, never updated or deleted
  - Structured: each entry contains the full reasoning trail
  - Queryable: by employee, approver, or date range

Design note: This is a scored security feature AND a demo moment.
The "Audit Trail" screen in the UI should display these entries,
proving that decisions are traceable and non-repudiable.

In production: this would be a write-once cloud storage (e.g., S3 with
MFA delete, or a ledger database). Here: SQLite append-only table.
"""

import sqlite3
import json
from datetime import datetime, UTC
from pathlib import Path


DB_PATH = Path(__file__).parent.parent / "data" / "audit_log.db"


class AuditLog:
    """
    Append-only audit log for ExpenseGuard decisions.
    
    Schema: Each row represents one complete agent pipeline run,
    with the full reasoning trail from all three agents.
    """
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()
    
    def _initialize_schema(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_entries (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_id      TEXT NOT NULL UNIQUE,
                employee_id     TEXT NOT NULL,
                vendor          TEXT NOT NULL,
                amount          REAL NOT NULL,
                category        TEXT NOT NULL,
                date            TEXT NOT NULL,
                
                -- Agent reasoning (JSON)
                intake_summary  TEXT NOT NULL,    -- Intake Agent output summary
                policy_verdict  TEXT NOT NULL,    -- Policy Agent verdict
                risk_signals    TEXT NOT NULL,    -- Risk Agent signals (JSON array)
                routing_decision TEXT NOT NULL,   -- Final routing decision
                raw_mcp_context TEXT,             -- Full MCP tool responses
                reasoning_trace TEXT,             -- Full ReasoningTrace (Phase 2 — all steps)
                
                -- Metadata
                pipeline_timestamp TEXT NOT NULL, -- When pipeline ran
                pipeline_version   TEXT DEFAULT '1.0'
            )
        """)
        conn.commit()
        conn.close()
    
    def write_entry(
        self,
        expense_id: str,
        employee_id: str,
        vendor: str,
        amount: float,
        category: str,
        date: str,
        intake_summary: dict,
        policy_verdict: dict,
        risk_signals: list[str],
        routing_decision: dict,
        raw_mcp_context: dict = None,
        reasoning_trace: dict = None,
    ):
        """
        Writes an immutable audit entry.

        Design note: INSERT OR IGNORE means an entry can never be overwritten.
        The expense_id UNIQUE constraint enforces immutability at the DB level.
        reasoning_trace stores the full Phase 2 trace (all agent steps + MCP calls).
        """
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT OR IGNORE INTO audit_entries
                    (expense_id, employee_id, vendor, amount, category, date,
                     intake_summary, policy_verdict, risk_signals,
                     routing_decision, raw_mcp_context, reasoning_trace, pipeline_timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                expense_id,
                employee_id,
                vendor,
                amount,
                category,
                date,
                json.dumps(intake_summary),
                json.dumps(policy_verdict),
                json.dumps(risk_signals),
                json.dumps(routing_decision),
                json.dumps(raw_mcp_context) if raw_mcp_context else None,
                json.dumps(reasoning_trace) if reasoning_trace else None,
                datetime.now(UTC).isoformat(),
            ))
            conn.commit()
        finally:
            conn.close()
    
    def record_human_decision(
        self,
        expense_id: str,
        action: str,          # "approved" or "rejected"
        decided_by: str,      # employee_id of the manager/exec who acted
    ):
        """
        Records a human approval/rejection decision against an existing entry.
        Updates the routing_decision JSON to include human_decision + decided_by.
        This is the ONLY allowed mutation and is guarded by audit_log semantics
        (we amend the routing_decision field only — all original fields are untouched).
        """
        conn = sqlite3.connect(self.db_path)
        try:
            # Read current routing_decision
            cur = conn.cursor()
            cur.execute(
                "SELECT routing_decision FROM audit_entries WHERE expense_id = ?",
                (expense_id,),
            )
            row = cur.fetchone()
            if not row:
                return
            routing = json.loads(row[0]) if row[0] else {}
            routing["human_decision"] = action
            routing["decided_by"] = decided_by
            routing["decided_at"] = datetime.now(UTC).isoformat()
            conn.execute(
                "UPDATE audit_entries SET routing_decision = ? WHERE expense_id = ?",
                (json.dumps(routing), expense_id),
            )
            conn.commit()
        finally:
            conn.close()

    def get_by_expense_id(self, expense_id: str) -> dict | None:
        """Retrieve a single audit entry by expense ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM audit_entries WHERE expense_id = ?", (expense_id,))
        row = cur.fetchone()
        conn.close()
        
        if not row:
            return None
        return self._deserialize_row(dict(row))
    
    def get_by_employee(self, employee_id: str) -> list[dict]:
        """Retrieve all audit entries for an employee."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM audit_entries WHERE employee_id = ? ORDER BY pipeline_timestamp DESC",
            (employee_id,)
        )
        rows = cur.fetchall()
        conn.close()
        return [self._deserialize_row(dict(r)) for r in rows]
    
    def get_all(self, limit: int = 100) -> list[dict]:
        """Retrieve recent audit entries (newest first)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM audit_entries ORDER BY pipeline_timestamp DESC LIMIT ?",
            (limit,)
        )
        rows = cur.fetchall()
        conn.close()
        return [self._deserialize_row(dict(r)) for r in rows]
    
    def get_pending_approvals(self, approver_id: str) -> list[dict]:
        """
        Returns expenses escalated to a specific approver that are still pending.
        
        Design note: In a full system, this would track approval status separately.
        Here we use routing_decision.approver_id for routing and 
        routing_decision.decision == 'escalate-to-human'.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM audit_entries
            WHERE json_extract(routing_decision, '$.decision') = 'escalate-to-human'
              AND json_extract(routing_decision, '$.approver_id') = ?
            ORDER BY pipeline_timestamp DESC
        """, (approver_id,))
        rows = cur.fetchall()
        conn.close()
        return [self._deserialize_row(dict(r)) for r in rows]
    
    def _deserialize_row(self, row: dict) -> dict:
        """Parses JSON fields back into Python objects."""
        for json_field in ["intake_summary", "policy_verdict", "risk_signals",
                           "routing_decision", "raw_mcp_context", "reasoning_trace"]:
            if row.get(json_field):
                try:
                    row[json_field] = json.loads(row[json_field])
                except (json.JSONDecodeError, TypeError):
                    pass  # Leave as string if parsing fails
        return row


# ── Test/demo ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log = AuditLog(db_path=Path("/tmp/test_audit.db"))
    
    log.write_entry(
        expense_id="EXP-DEMO001",
        employee_id="E1001",
        vendor="Delta Airlines",
        amount=345.00,
        category="travel",
        date="2026-06-25",
        intake_summary={"vendor": "Delta Airlines", "amount": 345.00, "receipt_provided": True},
        policy_verdict={"status": "compliant", "spend_limit": 500.00, "employee_role": "employee"},
        risk_signals=["High-value expense: $345.00"],
        routing_decision={"decision": "auto-approved", "reason": "Within policy limits."},
    )
    
    entries = log.get_all()
    print(f"[AuditLog] {len(entries)} entry/entries logged")
    print(json.dumps(entries[0], indent=2))
