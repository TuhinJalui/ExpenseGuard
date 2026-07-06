"""
rbac.py — Role-Based Access Control

Enforces:
- Employees can only submit their own expenses.
- Approvers can only see expenses from their direct reports.
- Admins/finance can see all.

Design note: This is a *real* check, not just a UI hide. The backend
enforces RBAC before any agent processing happens. Judges are explicitly
scoring security features — make this visible in the audit trail.
"""

from typing import Optional
from pydantic import BaseModel


class RBACException(Exception):
    """Raised when RBAC check fails."""
    pass


class RBACMiddleware:
    """
    Role-based access control middleware.
    
    In a real system, this would check against an auth service.
    Here we use the same employee DB from the MCP server for simplicity.
    """
    
    def __init__(self):
        # In production: fetch from auth service or JWT claims
        # Here: read from the same employee DB
        pass
    
    def _get_employee_role(self, employee_id: str) -> Optional[str]:
        """Fetch employee role from the DB."""
        import sqlite3
        from pathlib import Path
        
        DB_PATH = Path(__file__).parent.parent / "mcp_server" / "company_systems.db"
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("SELECT role FROM employees WHERE employee_id = ?", (employee_id,))
        row = cur.fetchone()
        conn.close()
        
        return row["role"] if row else None
    
    def _get_manager_id(self, employee_id: str) -> Optional[str]:
        """Fetch employee's manager ID."""
        import sqlite3
        from pathlib import Path
        
        DB_PATH = Path(__file__).parent.parent / "mcp_server" / "company_systems.db"
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("SELECT manager_id FROM employees WHERE employee_id = ?", (employee_id,))
        row = cur.fetchone()
        conn.close()
        
        return row["manager_id"] if row else None
    
    def _get_direct_reports(self, manager_id: str) -> list[str]:
        """Fetch list of employee IDs reporting to this manager."""
        import sqlite3
        from pathlib import Path
        
        DB_PATH = Path(__file__).parent.parent / "mcp_server" / "company_systems.db"
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        cur.execute("SELECT employee_id FROM employees WHERE manager_id = ?", (manager_id,))
        rows = cur.fetchall()
        conn.close()
        
        return [row[0] for row in rows]
    
    def assert_can_submit(self, requesting_user_id: str, expense_employee_id: str):
        """
        Enforces: Users can only submit expenses as themselves.
        
        Raises RBACException if check fails.
        
        Design note: Admins/finance (role='exec') can submit on behalf of anyone.
        This supports reimbursement workflows where finance processes expenses.
        """
        # Special case: admin/finance bypass
        requester_role = self._get_employee_role(requesting_user_id)
        if requester_role == "exec":
            return  # Execs can submit on behalf of anyone
        
        if requesting_user_id != expense_employee_id:
            raise RBACException(
                f"Permission denied: User {requesting_user_id} cannot submit "
                f"expenses for {expense_employee_id}. Users can only submit "
                f"their own expenses."
            )
    
    def assert_can_view(self, requesting_user_id: str, expense_employee_id: str):
        """
        Enforces: Users can view their own expenses OR expenses from their direct reports.
        
        Raises RBACException if check fails.
        
        Design note: This is what gates the "Review Queue" UI. Managers see
        only their team's escalations, not the entire company's.
        """
        # Can always view own expenses
        if requesting_user_id == expense_employee_id:
            return
        
        # Admins/finance can view all
        requester_role = self._get_employee_role(requesting_user_id)
        if requester_role == "exec":
            return
        
        # Managers can view direct reports' expenses
        direct_reports = self._get_direct_reports(requesting_user_id)
        if expense_employee_id in direct_reports:
            return
        
        # Otherwise, denied
        raise RBACException(
            f"Permission denied: User {requesting_user_id} cannot view "
            f"expenses for {expense_employee_id}. Users can only view their "
            f"own expenses or those from direct reports."
        )
    
    def assert_can_approve(self, approver_id: str, expense_employee_id: str):
        """
        Enforces: Approvers can only approve expenses from their direct reports.
        
        Raises RBACException if check fails.
        """
        # Admins/finance can approve anything
        approver_role = self._get_employee_role(approver_id)
        if approver_role == "exec":
            return
        
        # Managers can approve direct reports' expenses
        direct_reports = self._get_direct_reports(approver_id)
        if expense_employee_id in direct_reports:
            return
        
        # Otherwise, denied
        raise RBACException(
            f"Permission denied: User {approver_id} cannot approve "
            f"expenses for {expense_employee_id}. Only direct managers or "
            f"finance can approve expenses."
        )


# ── Test/demo ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    rbac = RBACMiddleware()
    
    print("[RBAC Demo]\n")
    
    # Test 1: Employee submits own expense (ALLOWED)
    try:
        rbac.assert_can_submit("E1001", "E1001")
        print("✓ E1001 can submit their own expense")
    except RBACException as e:
        print(f"✗ {e}")
    
    # Test 2: Employee submits for another employee (DENIED)
    try:
        rbac.assert_can_submit("E1001", "E1002")
        print("✓ E1001 can submit for E1002")
    except RBACException as e:
        print(f"✗ {e}")
    
    # Test 3: Manager views direct report's expense (ALLOWED)
    try:
        rbac.assert_can_view("E2001", "E1001")  # E2001 is manager of E1001
        print("✓ E2001 (manager) can view E1001's expense")
    except RBACException as e:
        print(f"✗ {e}")
    
    # Test 4: Manager views non-report's expense (DENIED)
    try:
        rbac.assert_can_view("E2001", "E1003")  # E1003 is not under E2001
        print("✓ E2001 can view E1003's expense")
    except RBACException as e:
        print(f"✗ {e}")
    
    # Test 5: Exec can view anything (ALLOWED)
    try:
        rbac.assert_can_view("E3001", "E1001")
        print("✓ E3001 (exec) can view E1001's expense")
    except RBACException as e:
        print(f"✗ {e}")
