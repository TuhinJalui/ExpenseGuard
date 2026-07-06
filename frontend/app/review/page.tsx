"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  CheckCircle, AlertTriangle, XCircle,
  RefreshCw, User, ThumbsUp, ThumbsDown, Loader2,
} from "lucide-react";
import { Nav } from "../components/Nav";
import { ReasoningTrace, type ReasoningTraceData } from "../components/ReasoningTrace";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const MANAGERS = [
  { id: "E2001", name: "Frank Torres",   role: "Engineering Manager" },
  { id: "E2002", name: "Grace Kim",      role: "Marketing Manager" },
  { id: "E3001", name: "Isabelle Nguyen", role: "Exec/Finance — all queues" },
];

interface PolicyVerdict {
  status: string; rule_cited?: string | null;
  employee_role: string; spend_limit?: number | null;
}

interface RoutingDecision {
  decision: string; reason: string;
  approver_id?: string | null;
}

interface AuditEntry {
  expense_id: string; employee_id: string;
  vendor: string; amount: number;
  category: string; date: string;
  pipeline_timestamp: string;
  policy_verdict: PolicyVerdict;
  risk_signals: string[];
  routing_decision: RoutingDecision;
  reasoning_trace?: ReasoningTraceData | null;
}

export default function ReviewPage() {
  const [managerId, setManagerId] = useState("E2001");
  const [entries, setEntries]     = useState<AuditEntry[]>([]);
  const [loading, setLoading]     = useState(false);
  const [error,   setError]       = useState<string | null>(null);

  const loadApprovals = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await fetch(`${API_URL}/api/expenses/approvals/${managerId}`, {
        headers: { "X-User-ID": managerId },
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Failed");
      const data = await res.json();
      setEntries(data.pending_approvals || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally { setLoading(false); }
  }, [managerId]);

  useEffect(() => { loadApprovals(); }, [loadApprovals]);

  const handleDecision = async (expenseId: string, action: "approve" | "reject") => {
    try {
      const res = await fetch(`${API_URL}/api/expenses/${expenseId}/${action}`, {
        method: "POST", headers: { "X-User-ID": managerId },
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Action failed");
      setEntries((prev) => prev.filter((e) => e.expense_id !== expenseId));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  const manager = MANAGERS.find((m) => m.id === managerId);

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-page)" }}>
      <Nav />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
        {/* Header */}
        <div className="flex items-start justify-between mb-6 flex-wrap gap-4">
          <div>
            <h2 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
              Pending Approvals
            </h2>
            <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
              Expenses the Risk Agent escalated — expand any card to read the full agent trace.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2">
              <User className="w-4 h-4 shrink-0" style={{ color: "var(--text-muted)" }} />
              <select
                value={managerId}
                onChange={(e) => setManagerId(e.target.value)}
                className="field text-sm"
              >
                {MANAGERS.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.role})
                  </option>
                ))}
              </select>
            </div>
            <button
              onClick={loadApprovals}
              className="flex items-center gap-1.5 text-sm px-3 py-2 rounded-xl border transition-colors hover:opacity-80"
              style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* RBAC note */}
        <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl px-4 py-2.5 text-sm text-blue-600 dark:text-blue-400 mb-6">
          <strong>RBAC active</strong> — viewing queue for{" "}
          <strong>{manager?.name}</strong> ({manager?.role}).
          You only see expenses the Risk Agent routed to this approver.
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 text-red-600 dark:text-red-400 text-sm mb-4">
            {error}
          </div>
        )}

        {loading && (
          <div className="text-center py-16" style={{ color: "var(--text-muted)" }}>
            <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-3" />
            Loading escalations…
          </div>
        )}

        {!loading && entries.length === 0 && !error && (
          <div className="text-center py-20 card">
            <CheckCircle className="w-10 h-10 text-emerald-400 mx-auto mb-3" />
            <p className="font-medium" style={{ color: "var(--text-secondary)" }}>
              No pending escalations
            </p>
            <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
              Nothing has been routed to this approver yet.
            </p>
            <Link href="/submit" className="inline-block mt-4 text-sm text-blue-600 dark:text-blue-400 hover:underline">
              Submit a test expense →
            </Link>
          </div>
        )}

        {!loading && entries.length > 0 && (
          <div className="space-y-4 animate-fade-in">
            {entries.map((entry) => (
              <EscalationCard
                key={entry.expense_id}
                entry={entry}
                managerId={managerId}
                onDecision={handleDecision}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Escalation card ─────────────────────────────────────────────────────────

function EscalationCard({
  entry, managerId, onDecision,
}: {
  entry: AuditEntry;
  managerId: string;
  onDecision: (id: string, a: "approve" | "reject") => Promise<void>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [acting, setActing]     = useState<"approve" | "reject" | null>(null);

  const policyStatus = entry.policy_verdict?.status || "unknown";
  const statusBadge: Record<string, string> = {
    compliant: "bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800/40",
    flagged:   "bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-800/40",
    violation: "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400 border-red-200 dark:border-red-800/40",
  };

  const handleAct = async (action: "approve" | "reject") => {
    setActing(action);
    await onDecision(entry.expense_id, action);
    setActing(null);
  };

  const hasTrace = !!entry.reasoning_trace?.steps?.length;

  return (
    <div className="card status-escalated overflow-hidden border-amber-200 dark:border-amber-800/40">
      {/* Header */}
      <div className="px-5 py-4 flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5 shrink-0" />
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>
                {entry.vendor} — ${entry.amount.toFixed(2)}
              </span>
              <span className={`badge ${statusBadge[policyStatus] ?? "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700"}`}>
                {policyStatus}
              </span>
            </div>
            <p className="text-sm mt-0.5" style={{ color: "var(--text-muted)" }}>
              {entry.employee_id} · {entry.category} · {entry.date}
            </p>
          </div>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs font-medium shrink-0 transition-colors text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
        >
          {expanded ? "Hide trace" : "View trace"}
        </button>
      </div>

      {/* Why escalated */}
      <div className="px-5 pb-4">
        <div className="bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800/30 rounded-xl px-3.5 py-2.5 text-sm">
          <span className="font-semibold text-amber-700 dark:text-amber-400">Why escalated: </span>
          <span style={{ color: "var(--text-secondary)" }}>{entry.routing_decision?.reason}</span>
        </div>
      </div>

      {/* Risk signals */}
      {entry.risk_signals?.length > 0 && (
        <div className="px-5 pb-4">
          <div className="flex flex-wrap gap-1.5">
            {entry.risk_signals.map((sig, i) => (
              <span key={i} className="badge bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-800/40">
                ⚠ {sig}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Phase 2 reasoning trace */}
      {expanded && (
        <div
          className="px-5 pb-5 border-t pt-4 animate-slide-down"
          style={{ borderColor: "var(--border)", background: "var(--surface-raised)" }}
        >
          {hasTrace ? (
            <ReasoningTrace trace={entry.reasoning_trace!} />
          ) : (
            <div className="card p-4 space-y-2 text-xs">
              <p className="font-semibold text-xs uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
                Policy Agent Output
              </p>
              <div className="grid grid-cols-2 gap-2">
                <FlatDetail label="Status" value={entry.policy_verdict?.status} />
                <FlatDetail label="Role"   value={entry.policy_verdict?.employee_role} />
                <FlatDetail label="Limit"  value={entry.policy_verdict?.spend_limit != null ? `$${entry.policy_verdict.spend_limit.toFixed(2)}` : "N/A"} />
                {entry.policy_verdict?.rule_cited && (
                  <div className="col-span-2">
                    <span style={{ color: "var(--text-muted)" }}>Rule: </span>
                    <span className="text-red-600 dark:text-red-400">{entry.policy_verdict.rule_cited}</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Action buttons */}
      <div
        className="px-5 py-3 flex gap-3 border-t"
        style={{ borderColor: "var(--border)", background: "var(--surface-raised)" }}
      >
        <button
          onClick={() => handleAct("approve")}
          disabled={acting !== null}
          className="flex-1 text-sm bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 text-white py-2 rounded-xl font-medium transition-all flex items-center justify-center gap-1.5 shadow-glow-green"
        >
          {acting === "approve"
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <ThumbsUp className="w-3.5 h-3.5" />
          }
          Approve
        </button>
        <button
          onClick={() => handleAct("reject")}
          disabled={acting !== null}
          className="flex-1 text-sm bg-red-500 hover:bg-red-400 disabled:opacity-60 text-white py-2 rounded-xl font-medium transition-all flex items-center justify-center gap-1.5"
        >
          {acting === "reject"
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <XCircle className="w-3.5 h-3.5" />
          }
          Reject
        </button>
        <Link
          href="/audit"
          className="text-sm px-4 py-2 rounded-xl border transition-colors"
          style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
        >
          Audit →
        </Link>
      </div>
    </div>
  );
}

function FlatDetail({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <span style={{ color: "var(--text-muted)" }}>{label}: </span>
      <span className="font-medium" style={{ color: "var(--text-secondary)" }}>{value || "—"}</span>
    </div>
  );
}
