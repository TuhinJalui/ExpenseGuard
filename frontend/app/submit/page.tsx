"use client";

import { useState } from "react";
import Link from "next/link";
import {
  CheckCircle, AlertTriangle, XCircle,
  Lock, Loader2, ExternalLink, Sparkles,
} from "lucide-react";
import { Nav } from "../components/Nav";
import {
  ReasoningTrace, PipelineProgress,
  type ReasoningTraceData,
} from "../components/ReasoningTrace";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const CATEGORIES = [
  "meals", "travel", "software", "office_supplies",
  "training", "entertainment", "equipment",
];

const EMPLOYEES = [
  { id: "E1001", name: "Alice Johnson", dept: "Engineering" },
  { id: "E1002", name: "Bob Martinez",  dept: "Engineering" },
  { id: "E1003", name: "Carol Smith",   dept: "Marketing" },
  { id: "E1004", name: "David Lee",     dept: "Marketing" },
  { id: "E2001", name: "Frank Torres",  dept: "Eng Manager" },
  { id: "E2002", name: "Grace Kim",     dept: "Mkt Manager" },
  { id: "E3001", name: "Isabelle Nguyen", dept: "Exec/Finance" },
];

const PIPELINE_STEPS = [
  "PII Redaction", "Intake Agent",
  "Policy Agent", "Risk & Routing Agent",
];

interface SubmitResult {
  success: boolean;
  expense_id: string;
  decision: "auto-approved" | "escalate-to-human" | "rejected";
  reason: string;
  compliance_status: "compliant" | "flagged" | "violation";
  extraction_method: string;
  risk_signals: string[];
  approver_id?: string | null;
  trace_steps: string[];
}

interface DemoScenario {
  label: string; expected: string; expectedColor: string;
  employee_id: string; vendor: string; amount: number;
  category: string; date: string; description: string;
  receipt_text?: string;
}

export default function SubmitPage() {
  const [employeeId, setEmployeeId] = useState("E1001");
  const [amount,      setAmount]     = useState("");
  const [category,    setCategory]   = useState("meals");
  const [vendor,      setVendor]     = useState("");
  const [date,        setDate]       = useState(new Date().toISOString().split("T")[0]);
  const [description, setDesc]       = useState("");
  const [receiptText, setReceipt]    = useState("");

  const [loading,    setLoading]    = useState(false);
  const [activeStep, setActiveStep] = useState(-1);
  const [result,     setResult]     = useState<SubmitResult | null>(null);
  const [fullTrace,  setFullTrace]  = useState<ReasoningTraceData | null>(null);
  const [error,      setError]      = useState<string | null>(null);
  const [piiWarn,    setPiiWarn]    = useState(false);

  const detectPii = (text: string) => {
    setPiiWarn(
      /\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b/.test(text) ||
      /[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}/.test(text) ||
      /\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}/.test(text)
    );
  };

  const animatePipeline = () => {
    setActiveStep(0);
    [400, 900, 1500, 2200].forEach((ms, i) =>
      setTimeout(() => setActiveStep(i + 1), ms)
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true); setResult(null); setFullTrace(null);
    setError(null); animatePipeline();

    try {
      const res = await fetch(`${API_URL}/api/expenses/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-User-ID": employeeId },
        body: JSON.stringify({
          employee_id: employeeId,
          description: description || `${category} — ${vendor}`,
          amount: parseFloat(amount),
          category, date,
          receipt_text: receiptText || undefined,
        }),
      });

      if (!res.ok) throw new Error((await res.json()).detail || "Submission failed");

      const data: SubmitResult = await res.json();
      setResult(data);
      setActiveStep(PIPELINE_STEPS.length);

      try {
        const tr = await fetch(`${API_URL}/api/expenses/${data.expense_id}`, {
          headers: { "X-User-ID": employeeId },
        });
        if (tr.ok) {
          const td = await tr.json();
          if (td.reasoning_trace) setFullTrace(td.reasoning_trace as ReasoningTraceData);
        }
      } catch { /* non-fatal */ }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setActiveStep(-1);
    } finally {
      setLoading(false);
    }
  };

  const loadScenario = (s: DemoScenario) => {
    setEmployeeId(s.employee_id); setVendor(s.vendor);
    setAmount(String(s.amount)); setCategory(s.category);
    setDate(s.date); setDesc(s.description);
    setReceipt(s.receipt_text || "");
    setPiiWarn(false); setResult(null);
    setFullTrace(null); setError(null); setActiveStep(-1);
  };

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-page)" }}>
      <Nav />

      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
        {/* PII security banner */}
        <div className="flex items-start gap-3 bg-emerald-500/10 dark:bg-emerald-500/5 text-emerald-700 dark:text-emerald-400 text-sm px-4 py-3 rounded-xl border border-emerald-500/20 mb-6">
          <Lock className="w-4 h-4 mt-0.5 shrink-0" />
          <span>
            <strong>Security active:</strong> Card numbers, emails, and phone numbers are
            automatically redacted from receipt text before any AI processing. Enforced
            server-side regardless of client state.
          </span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* ── Form ──────────────────────────────────────────────── */}
          <div className="lg:col-span-3">
            <form onSubmit={handleSubmit} className="card overflow-hidden">
              <div className="px-6 py-5 border-b" style={{ borderColor: "var(--border)" }}>
                <h2 className="font-semibold" style={{ color: "var(--text-primary)" }}>
                  Expense Details
                </h2>
                <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
                  Submit for automated policy validation and AI routing.
                </p>
              </div>

              <div className="px-6 py-5 space-y-5">
                {/* Employee */}
                <div>
                  <label className="block text-sm font-medium mb-1.5" style={{ color: "var(--text-secondary)" }}>
                    Submitting as
                  </label>
                  <select
                    value={employeeId}
                    onChange={(e) => setEmployeeId(e.target.value)}
                    className="field w-full"
                    required
                  >
                    {EMPLOYEES.map((emp) => (
                      <option key={emp.id} value={emp.id}>
                        {emp.name} — {emp.dept} ({emp.id})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Vendor + Amount */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1.5" style={{ color: "var(--text-secondary)" }}>
                      Vendor / Merchant
                    </label>
                    <input
                      type="text" value={vendor}
                      onChange={(e) => setVendor(e.target.value)}
                      placeholder="e.g. Delta Airlines"
                      className="field w-full" required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1.5" style={{ color: "var(--text-secondary)" }}>
                      Amount (USD)
                    </label>
                    <div className="relative">
                      <span className="absolute left-3 top-2 text-sm" style={{ color: "var(--text-muted)" }}>$</span>
                      <input
                        type="number" value={amount}
                        onChange={(e) => setAmount(e.target.value)}
                        placeholder="0.00" step="0.01" min="0"
                        className="field w-full pl-7" required
                      />
                    </div>
                  </div>
                </div>

                {/* Category + Date */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1.5" style={{ color: "var(--text-secondary)" }}>
                      Category
                    </label>
                    <select
                      value={category} onChange={(e) => setCategory(e.target.value)}
                      className="field w-full" required
                    >
                      {CATEGORIES.map((cat) => (
                        <option key={cat} value={cat}>
                          {cat.replace("_", " ").replace(/\b\w/g, (l) => l.toUpperCase())}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1.5" style={{ color: "var(--text-secondary)" }}>
                      Date
                    </label>
                    <input
                      type="date" value={date}
                      onChange={(e) => setDate(e.target.value)}
                      className="field w-full" required
                    />
                  </div>
                </div>

                {/* Description */}
                <div>
                  <label className="block text-sm font-medium mb-1.5" style={{ color: "var(--text-secondary)" }}>
                    Description
                    <span className="ml-1 font-normal" style={{ color: "var(--text-muted)" }}>(optional)</span>
                  </label>
                  <input
                    type="text" value={description}
                    onChange={(e) => setDesc(e.target.value)}
                    placeholder="Brief description"
                    className="field w-full"
                  />
                </div>

                {/* Receipt text */}
                <div>
                  <label className="block text-sm font-medium mb-1.5" style={{ color: "var(--text-secondary)" }}>
                    Receipt Text
                    <span className="ml-1 font-normal" style={{ color: "var(--text-muted)" }}>(optional — triggers Gemini extraction)</span>
                  </label>
                  <textarea
                    value={receiptText}
                    onChange={(e) => { setReceipt(e.target.value); detectPii(e.target.value); }}
                    placeholder="Paste receipt text here…"
                    rows={4}
                    className="field w-full font-mono resize-none"
                  />
                  {piiWarn && (
                    <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 text-xs mt-2 bg-amber-500/10 px-3 py-2 rounded-lg border border-amber-500/20">
                      <Lock className="w-3 h-3 shrink-0" />
                      PII detected — will be automatically redacted before AI processing.
                    </div>
                  )}
                </div>
              </div>

              <div className="px-6 py-4 border-t" style={{ borderColor: "var(--border)", background: "var(--surface-raised)" }}>
                <button
                  type="submit" disabled={loading}
                  className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white py-2.5 rounded-xl font-medium text-sm transition-all duration-200 flex items-center justify-center gap-2 shadow-glow-blue"
                >
                  {loading ? (
                    <><Loader2 className="w-4 h-4 animate-spin" />Running agent pipeline…</>
                  ) : (
                    <><Sparkles className="w-4 h-4" />Submit for Validation</>
                  )}
                </button>
              </div>
            </form>

            {/* Error */}
            {error && (
              <div className="mt-4 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 text-red-600 dark:text-red-400 text-sm animate-fade-in">
                {error}
              </div>
            )}

            {/* Decision result */}
            {result && <DecisionCard result={result} />}
          </div>

          {/* ── Right panel ──────────────────────────────────────── */}
          <div className="lg:col-span-2 space-y-4">
            {(loading || result || activeStep >= 0) && (
              <div className="card p-4 animate-fade-in">
                <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--text-muted)" }}>
                  Agent Pipeline
                </p>
                <PipelineProgress steps={PIPELINE_STEPS} activeStep={activeStep} />
              </div>
            )}

            {fullTrace && (
              <div className="card p-4 animate-slide-up">
                <ReasoningTrace trace={fullTrace} />
              </div>
            )}

            {!fullTrace && !loading && (
              <DemoScenarios onLoad={loadScenario} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Decision card ─────────────────────────────────────────────────────────

function DecisionCard({ result }: { result: SubmitResult }) {
  const cfg = {
    "auto-approved": {
      icon: <CheckCircle className="w-5 h-5 text-emerald-500" />,
      cls: "status-approved border-emerald-200 dark:border-emerald-800/50 bg-emerald-50 dark:bg-emerald-950/30",
      badge: "bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800/40",
      title: "Auto-Approved",
    },
    "escalate-to-human": {
      icon: <AlertTriangle className="w-5 h-5 text-amber-500" />,
      cls: "status-escalated border-amber-200 dark:border-amber-800/50 bg-amber-50 dark:bg-amber-950/30",
      badge: "bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-800/40",
      title: "Escalated for Review",
    },
    rejected: {
      icon: <XCircle className="w-5 h-5 text-red-500" />,
      cls: "status-rejected border-red-200 dark:border-red-800/50 bg-red-50 dark:bg-red-950/30",
      badge: "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400 border-red-200 dark:border-red-800/40",
      title: "Rejected",
    },
  }[result.decision] ?? {
    icon: null, cls: "border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900",
    badge: "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700",
    title: result.decision,
  };

  return (
    <div className={`mt-4 rounded-2xl border p-4 animate-slide-up ${cfg.cls}`}>
      <div className="flex items-start gap-3">
        {cfg.icon}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>
              {cfg.title}
            </span>
            <span className={`badge ${cfg.badge}`}>{result.compliance_status}</span>
            <span className="text-[10px] font-mono ml-auto" style={{ color: "var(--text-muted)" }}>
              {result.extraction_method}
            </span>
          </div>
          <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            {result.reason}
          </p>
          {result.risk_signals.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {result.risk_signals.map((sig, i) => (
                <span key={i} className="badge bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-800/40">
                  ⚠ {sig}
                </span>
              ))}
            </div>
          )}
          <div className="flex items-center gap-3 mt-3 pt-2.5 border-t border-black/5 dark:border-white/5">
            <span className="text-[10px] font-mono" style={{ color: "var(--text-muted)" }}>
              {result.expense_id}
            </span>
            <Link
              href="/audit"
              className="text-xs text-blue-600 dark:text-blue-400 hover:underline font-medium flex items-center gap-1 ml-auto"
            >
              Full audit trail <ExternalLink className="w-3 h-3" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Demo scenarios ─────────────────────────────────────────────────────────

function DemoScenarios({ onLoad }: { onLoad: (s: DemoScenario) => void }) {
  const scenarios: DemoScenario[] = [
    { label: "✅ Compliant Meal", expected: "Auto-approved", expectedColor: "text-emerald-500",
      employee_id: "E1001", vendor: "Chipotle", amount: 23.5, category: "meals",
      date: "2026-07-01", description: "Team lunch" },
    { label: "❌ Amount Violation", expected: "Rejected", expectedColor: "text-red-500",
      employee_id: "E1001", vendor: "United Airlines", amount: 890, category: "travel",
      date: "2026-07-01", description: "Flight to NYC" },
    { label: "⚠️ Pre-approval Needed", expected: "Escalated", expectedColor: "text-amber-500",
      employee_id: "E1001", vendor: "Delta Airlines", amount: 350, category: "travel",
      date: "2026-07-01", description: "Flight to Chicago" },
    { label: "❌ Vendor Not Approved", expected: "Rejected", expectedColor: "text-red-500",
      employee_id: "E1001", vendor: "SomeRandomSaaS", amount: 49, category: "software",
      date: "2026-07-01", description: "SaaS subscription" },
    { label: "⚠️ Duplicate Submission", expected: "Escalated", expectedColor: "text-amber-500",
      employee_id: "E1001", vendor: "Delta Airlines", amount: 345, category: "travel",
      date: "2026-07-01", description: "Flight (again?)" },
    { label: "❌ Category Not Covered", expected: "Rejected", expectedColor: "text-red-500",
      employee_id: "E1001", vendor: "The Capital Grille", amount: 120, category: "entertainment",
      date: "2026-07-01", description: "Client dinner" },
    { label: "🔒 PII in Receipt", expected: "Approved (PII stripped)", expectedColor: "text-emerald-500",
      employee_id: "E1001", vendor: "Amazon", amount: 35, category: "office_supplies",
      date: "2026-07-01", description: "Office supplies",
      receipt_text: "Amazon\nCard: 4111 1111 1111 1111\nEmail: alice@test.com\nTotal: $35.00" },
  ];

  return (
    <div className="card p-4">
      <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--text-muted)" }}>
        Demo Scenarios
      </p>
      <div className="space-y-1.5">
        {scenarios.map((s, i) => (
          <button
            key={i}
            onClick={() => onLoad(s)}
            className="w-full text-left flex items-center justify-between rounded-xl px-3 py-2 transition-all duration-150 text-sm border hover:-translate-y-px"
            style={{
              background: "var(--surface-raised)",
              borderColor: "var(--border)",
              color: "var(--text-secondary)",
            }}
          >
            <span>{s.label}</span>
            <span className={`text-xs font-medium shrink-0 ${s.expectedColor}`}>{s.expected}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
