"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  RefreshCw, CheckCircle, AlertTriangle, XCircle,
  Lock, ChevronDown, ChevronUp, Shield, Filter,
} from "lucide-react";
import { Nav } from "../components/Nav";
import { ReasoningTrace, type ReasoningTraceData } from "../components/ReasoningTrace";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface PolicyVerdict {
  status: string;
  rule_cited?: string | null;
  employee_role: string;
  spend_limit?: number | null;
}

interface RoutingDecision {
  decision: string;
  reason: string;
  approver_id?: string | null;
  human_decision?: string | null;
  decided_by?: string | null;
}

interface IntakeSummary {
  vendor: string;
  amount: number;
  receipt_provided: boolean;
  extraction_method?: string;
}

interface AuditEntry {
  id: number;
  expense_id: string;
  employee_id: string;
  vendor: string;
  amount: number;
  category: string;
  date: string;
  pipeline_timestamp: string;
  intake_summary: IntakeSummary;
  policy_verdict: PolicyVerdict;
  risk_signals: string[];
  routing_decision: RoutingDecision;
  reasoning_trace?: ReasoningTraceData | null;
}

const VIEWERS = [
  { id: "E3001", label: "Isabelle Nguyen (Exec — full access)" },
  { id: "E2001", label: "Frank Torres (Manager — own team)" },
];

const DECISION_FILTERS = ["all", "auto-approved", "escalate-to-human", "rejected"] as const;
type DecisionFilter = typeof DECISION_FILTERS[number];

export default function AuditPage() {
  const [viewerId,  setViewerId]  = useState("E3001");
  const [entries,   setEntries]   = useState<AuditEntry[]>([]);
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState<string | null>(null);
  const [filter,    setFilter]    = useState<DecisionFilter>("all");

  const loadEntries = async () => {
    setLoading(true); setError(null);
    try {
      const res = await fetch(`${API_URL}/api/audit/all?limit=50`, {
        headers: { "X-User-ID": viewerId },
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Failed");
      const data = await res.json();
      setEntries(data.audit_entries || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadEntries(); }, [viewerId]); // eslint-disable-line react-hooks/exhaustive-deps

  const visible = filter === "all"
    ? entries
    : entries.filter((e) => e.routing_decision?.decision === filter);

  const stats = {
    total: entries.length,
    approved:  entries.filter((e) => e.routing_decision?.decision === "auto-approved").length,
    escalated: entries.filter((e) => e.routing_decision?.decision === "escalate-to-human").length,
    rejected:  entries.filter((e) => e.routing_decision?.decision === "rejected").length,
  };

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-page)" }}>
      <Nav />

      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        {/* Header */}
        <div className="flex items-start justify-between mb-6 flex-wrap gap-4">
          <div>
            <h2 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
              Immutable Audit Trail
            </h2>
            <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
              Every agent decision logged permanently — expand any row to see the full
              Phase 2 reasoning trace with all MCP tool calls.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={viewerId}
              onChange={(e) => setViewerId(e.target.value)}
              className="field text-sm"
            >
              {VIEWERS.map((v) => (
                <option key={v.id} value={v.id}>{v.label}</option>
              ))}
            </select>
            <button
              onClick={loadEntries}
              className="flex items-center gap-1.5 text-sm px-3 py-2 rounded-xl border transition-colors hover:opacity-80"
              style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* Security note */}
        <div className="flex items-start gap-3 bg-slate-800/60 dark:bg-slate-900/60 text-slate-300 text-xs px-4 py-3 rounded-xl mb-6 border border-slate-700/60">
          <Lock className="w-3.5 h-3.5 mt-0.5 shrink-0 text-slate-500" />
          <span>
            Entries are <strong className="text-slate-200">append-only</strong> (INSERT OR IGNORE + UNIQUE constraint).
            No entry can be modified or deleted after writing.{" "}
            <strong className="text-slate-200">Non-repudiable by design.</strong>{" "}
            Each entry stores the full Phase 2 reasoning trace — every MCP call, timing, and agent output.
          </span>
        </div>

        {/* Stats */}
        {!loading && entries.length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <StatCard label="Total"         value={stats.total}     color="blue"   active={filter === "all"}             onClick={() => setFilter("all")} />
            <StatCard label="Auto-Approved" value={stats.approved}  color="green"  active={filter === "auto-approved"}   onClick={() => setFilter("auto-approved")} />
            <StatCard label="Escalated"     value={stats.escalated} color="yellow" active={filter === "escalate-to-human"} onClick={() => setFilter("escalate-to-human")} />
            <StatCard label="Rejected"      value={stats.rejected}  color="red"    active={filter === "rejected"}        onClick={() => setFilter("rejected")} />
          </div>
        )}

        {/* Filter bar */}
        {entries.length > 0 && filter !== "all" && (
          <div className="flex items-center gap-2 mb-4 text-xs">
            <Filter className="w-3.5 h-3.5" style={{ color: "var(--text-muted)" }} />
            <span style={{ color: "var(--text-muted)" }}>
              Showing {visible.length} of {entries.length} entries — filtered by{" "}
              <strong style={{ color: "var(--text-secondary)" }}>{filter}</strong>
            </span>
            <button
              onClick={() => setFilter("all")}
              className="ml-2 text-blue-500 dark:text-blue-400 hover:underline"
            >
              Clear filter
            </button>
          </div>
        )}

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 text-red-600 dark:text-red-400 text-sm mb-4">
            {error}
          </div>
        )}

        {loading && (
          <div className="text-center py-16" style={{ color: "var(--text-muted)" }}>
            <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-3" />
            Loading audit entries…
          </div>
        )}

        {!loading && entries.length === 0 && !error && (
          <div className="text-center py-20 card">
            <Shield className="w-10 h-10 mx-auto mb-3 text-slate-300 dark:text-slate-700" />
            <p className="font-medium" style={{ color: "var(--text-secondary)" }}>
              No audit entries yet
            </p>
            <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
              Submit an expense to see the full agent reasoning trail here.
            </p>
            <Link href="/submit" className="inline-block mt-4 text-sm text-blue-600 dark:text-blue-400 hover:underline">
              Submit a test expense →
            </Link>
          </div>
        )}

        {!loading && visible.length > 0 && (
          <div className="space-y-2 animate-fade-in">
            {visible.map((entry) => (
              <AuditRow key={entry.expense_id} entry={entry} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Clickable stat card ─────────────────────────────────────────────────────

function StatCard({
  label, value, color, active, onClick,
}: {
  label: string; value: number; color: string;
  active?: boolean; onClick?: () => void;
}) {
  const styles: Record<string, { bg: string; border: string; text: string }> = {
    blue:   { bg: "bg-blue-500/10 dark:bg-blue-500/10",   border: "border-blue-200 dark:border-blue-800/50",   text: "text-blue-600 dark:text-blue-400" },
    green:  { bg: "bg-emerald-500/10",                     border: "border-emerald-200 dark:border-emerald-800/50", text: "text-emerald-600 dark:text-emerald-400" },
    yellow: { bg: "bg-amber-500/10",                       border: "border-amber-200 dark:border-amber-800/50",  text: "text-amber-600 dark:text-amber-400" },
    red:    { bg: "bg-red-500/10",                         border: "border-red-200 dark:border-red-800/50",      text: "text-red-600 dark:text-red-400" },
  };
  const s = styles[color];
  return (
    <button
      onClick={onClick}
      className={`rounded-xl border px-4 py-3 text-left w-full transition-all duration-150 hover:-translate-y-0.5 ${s.bg} ${s.border} ${active ? "ring-2 ring-offset-2 ring-blue-500/40 dark:ring-offset-[#161b28]" : ""}`}
    >
      <div className={`text-2xl font-bold ${s.text}`}>{value}</div>
      <div className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>{label}</div>
    </button>
  );
}

// ── Audit row ───────────────────────────────────────────────────────────────

function AuditRow({ entry }: { entry: AuditEntry }) {
  const [expanded, setExpanded] = useState(false);
  const decision = entry.routing_decision?.decision || "unknown";

  const decisionCfg: Record<string, { icon: React.ReactNode; badge: string; row: string }> = {
    "auto-approved": {
      icon: <CheckCircle className="w-4 h-4 text-emerald-500 shrink-0" />,
      badge: "bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800/40",
      row: "hover:border-emerald-200/60 dark:hover:border-emerald-800/40",
    },
    "escalate-to-human": {
      icon: <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />,
      badge: "bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-800/40",
      row: "hover:border-amber-200/60 dark:hover:border-amber-800/40",
    },
    rejected: {
      icon: <XCircle className="w-4 h-4 text-red-500 shrink-0" />,
      badge: "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400 border-red-200 dark:border-red-800/40",
      row: "hover:border-red-200/60 dark:hover:border-red-800/40",
    },
  };

  const cfg = decisionCfg[decision] ?? decisionCfg["auto-approved"];
  const hasTrace = !!entry.reasoning_trace?.steps?.length;
  const toolCount = hasTrace
    ? entry.reasoning_trace!.steps.reduce((n, s) => n + s.tool_calls.length, 0)
    : 0;

  const humanDecision = entry.routing_decision?.human_decision;

  return (
    <div className={`card transition-all duration-200 ${cfg.row}`}>
      {/* Collapsed row */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-5 py-3.5 flex items-center gap-3 transition-colors text-left rounded-2xl"
        style={{ color: "var(--text-primary)" }}
      >
        {cfg.icon}

        <span className="font-mono text-xs w-28 shrink-0 hidden sm:block" style={{ color: "var(--text-muted)" }}>
          {entry.expense_id}
        </span>
        <span className="text-xs w-10 shrink-0" style={{ color: "var(--text-muted)" }}>
          {entry.employee_id}
        </span>
        <span className="text-sm font-medium w-32 truncate shrink-0" style={{ color: "var(--text-primary)" }}>
          {entry.vendor}
        </span>
        <span className="text-sm w-20 shrink-0" style={{ color: "var(--text-secondary)" }}>
          ${entry.amount.toFixed(2)}
        </span>
        <span className="text-xs w-24 shrink-0 hidden md:block" style={{ color: "var(--text-muted)" }}>
          {entry.category}
        </span>

        <span className={`badge ${cfg.badge} shrink-0`}>{decision}</span>

        {/* Human decision badge */}
        {humanDecision && (
          <span className={`badge shrink-0 ${humanDecision === "approved"
            ? "bg-emerald-100 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800/40"
            : "bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400 border-red-200 dark:border-red-800/40"
          }`}>
            👤 {humanDecision}
          </span>
        )}

        {/* MCP call count */}
        {hasTrace && (
          <span className="hidden lg:flex items-center gap-1 text-[10px] shrink-0" style={{ color: "var(--text-muted)" }}>
            <Lock className="w-3 h-3" />
            {toolCount} MCP
          </span>
        )}

        <span className="text-xs ml-auto shrink-0 hidden md:block" style={{ color: "var(--text-muted)" }}>
          {new Date(entry.pipeline_timestamp).toLocaleString()}
        </span>

        {expanded
          ? <ChevronUp className="w-4 h-4 shrink-0" style={{ color: "var(--text-muted)" }} />
          : <ChevronDown className="w-4 h-4 shrink-0" style={{ color: "var(--text-muted)" }} />
        }
      </button>

      {/* Expanded reasoning trace */}
      {expanded && (
        <div
          className="border-t px-5 py-5 animate-slide-down"
          style={{ borderColor: "var(--border)", background: "var(--surface-raised)" }}
        >
          {hasTrace ? (
            <ReasoningTrace trace={entry.reasoning_trace!} />
          ) : (
            <FlatFallback entry={entry} badge={cfg.badge} />
          )}
        </div>
      )}
    </div>
  );
}

// ── Flat fallback for entries without Phase 2 trace ─────────────────────────

function FlatFallback({ entry, badge }: { entry: AuditEntry; badge: string }) {
  return (
    <div className="space-y-3">
      <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
        Agent Reasoning Trail (legacy format)
      </p>

      {[
        {
          label: "1. Intake Agent",
          color: "text-blue-600 dark:text-blue-400",
          content: (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              <FlatDetail label="Vendor"  value={entry.intake_summary?.vendor} />
              <FlatDetail label="Amount"  value={`$${entry.intake_summary?.amount?.toFixed(2)}`} />
              <FlatDetail label="Receipt" value={entry.intake_summary?.receipt_provided ? "Provided" : "None"} />
              <FlatDetail label="Method"  value={entry.intake_summary?.extraction_method || "—"} />
            </div>
          ),
        },
        {
          label: "2. Policy Agent",
          color: "text-purple-600 dark:text-purple-400",
          content: (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
              <FlatDetail label="Status" value={entry.policy_verdict?.status} />
              <FlatDetail label="Role"   value={entry.policy_verdict?.employee_role} />
              <FlatDetail label="Limit"  value={entry.policy_verdict?.spend_limit != null ? `$${entry.policy_verdict.spend_limit.toFixed(2)}` : "N/A"} />
              {entry.policy_verdict?.rule_cited && (
                <div className="col-span-3 text-xs">
                  <span style={{ color: "var(--text-muted)" }}>Rule: </span>
                  <span className="text-red-600 dark:text-red-400">{entry.policy_verdict.rule_cited}</span>
                </div>
              )}
            </div>
          ),
        },
        {
          label: "3. Risk & Routing Agent",
          color: "text-indigo-600 dark:text-indigo-400",
          content: (
            <div className="space-y-1 text-xs">
              <div>
                <span style={{ color: "var(--text-muted)" }}>Decision: </span>
                <span className={`badge ${badge} text-[10px]`}>{entry.routing_decision?.decision}</span>
              </div>
              <div>
                <span style={{ color: "var(--text-muted)" }}>Reason: </span>
                <span style={{ color: "var(--text-secondary)" }}>{entry.routing_decision?.reason}</span>
              </div>
              {entry.risk_signals?.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {entry.risk_signals.map((sig, i) => (
                    <span key={i} className="badge bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-800/40">
                      ⚠ {sig}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ),
        },
      ].map(({ label, color, content }) => (
        <div key={label} className="card p-3">
          <p className={`text-xs font-semibold mb-2 ${color}`}>{label}</p>
          {content}
        </div>
      ))}
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
