"use client";

import { useState, useCallback } from "react";
import {
  ChevronDown,
  ChevronRight,
  Shield,
  Search,
  GitMerge,
  Cpu,
  Clock,
  CheckCircle2,
  AlertCircle,
  Wrench,
  Copy,
  Check,
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────

export interface ToolCallData {
  tool_name: string;
  arguments: Record<string, unknown>;
  result: Record<string, unknown>;
  duration_ms?: number | null;
}

export interface AgentStepData {
  agent_name: string;
  started_at: string;
  inputs: Record<string, unknown>;
  tool_calls: ToolCallData[];
  output: Record<string, unknown>;
  reasoning: string;
}

export interface ReasoningTraceData {
  expense_id: string;
  pipeline_started_at?: string;
  steps: AgentStepData[];
}

// ── Agent config ────────────────────────────────────────────────────────────

const AGENT_CONFIG: Record<
  string,
  {
    lightBg: string; lightBorder: string; lightText: string; lightBadge: string;
    darkBg: string;  darkBorder: string;  darkText: string;  darkBadge: string;
    dotColor: string; Icon: React.ElementType;
  }
> = {
  "PII Redaction": {
    lightBg: "bg-emerald-50", lightBorder: "border-emerald-200",
    lightText: "text-emerald-700", lightBadge: "bg-emerald-100 text-emerald-700 border-emerald-200",
    darkBg: "dark:bg-emerald-950/30", darkBorder: "dark:border-emerald-800/50",
    darkText: "dark:text-emerald-400", darkBadge: "dark:bg-emerald-900/30 dark:text-emerald-400 dark:border-emerald-800/40",
    dotColor: "bg-emerald-400",
    Icon: Shield,
  },
  "Intake Agent": {
    lightBg: "bg-blue-50", lightBorder: "border-blue-200",
    lightText: "text-blue-700", lightBadge: "bg-blue-100 text-blue-700 border-blue-200",
    darkBg: "dark:bg-blue-950/30", darkBorder: "dark:border-blue-800/50",
    darkText: "dark:text-blue-400", darkBadge: "dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-800/40",
    dotColor: "bg-blue-400",
    Icon: Search,
  },
  "Policy Agent": {
    lightBg: "bg-purple-50", lightBorder: "border-purple-200",
    lightText: "text-purple-700", lightBadge: "bg-purple-100 text-purple-700 border-purple-200",
    darkBg: "dark:bg-purple-950/30", darkBorder: "dark:border-purple-800/50",
    darkText: "dark:text-purple-400", darkBadge: "dark:bg-purple-900/30 dark:text-purple-400 dark:border-purple-800/40",
    dotColor: "bg-purple-400",
    Icon: GitMerge,
  },
  "Risk & Routing Agent": {
    lightBg: "bg-indigo-50", lightBorder: "border-indigo-200",
    lightText: "text-indigo-700", lightBadge: "bg-indigo-100 text-indigo-700 border-indigo-200",
    darkBg: "dark:bg-indigo-950/30", darkBorder: "dark:border-indigo-800/50",
    darkText: "dark:text-indigo-400", darkBadge: "dark:bg-indigo-900/30 dark:text-indigo-400 dark:border-indigo-800/40",
    dotColor: "bg-indigo-400",
    Icon: Cpu,
  },
};

const DEFAULT_CONFIG = {
  lightBg: "bg-slate-50", lightBorder: "border-slate-200",
  lightText: "text-slate-700", lightBadge: "bg-slate-100 text-slate-600 border-slate-200",
  darkBg: "dark:bg-slate-900/30", darkBorder: "dark:border-slate-700",
  darkText: "dark:text-slate-400", darkBadge: "dark:bg-slate-800/30 dark:text-slate-400 dark:border-slate-700",
  dotColor: "bg-slate-400",
  Icon: Cpu,
};

// ── Syntax-highlighted JSON renderer ────────────────────────────────────────

function highlightJson(json: string): string {
  return json
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(
      /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
      (match) => {
        if (/^"/.test(match)) {
          if (/:$/.test(match)) return `<span class="json-key">${match}</span>`;
          return `<span class="json-string">${match}</span>`;
        }
        if (/true|false/.test(match)) return `<span class="json-boolean">${match}</span>`;
        if (/null/.test(match)) return `<span class="json-null">${match}</span>`;
        return `<span class="json-number">${match}</span>`;
      }
    );
}

// ── Copy button ──────────────────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [text]);

  return (
    <button
      onClick={copy}
      className="p-1 rounded transition-colors text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
      aria-label="Copy"
    >
      {copied
        ? <Check className="w-3 h-3 text-emerald-500" />
        : <Copy className="w-3 h-3" />
      }
    </button>
  );
}

// ── JSON block ───────────────────────────────────────────────────────────────

function JsonBlock({ label, data }: { label: string; data: unknown }) {
  const json = JSON.stringify(data, null, 2);
  const highlighted = highlightJson(json);

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700/60 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 bg-slate-100 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-700/60">
        <span className="text-[10px] font-medium uppercase tracking-wider text-slate-400 dark:text-slate-500">
          {label}
        </span>
        <CopyButton text={json} />
      </div>
      <pre
        className="px-3 py-2.5 text-xs font-mono leading-relaxed overflow-auto max-h-48 bg-white dark:bg-slate-900/40 text-slate-700 dark:text-slate-300"
        dangerouslySetInnerHTML={{ __html: highlighted }}
      />
    </div>
  );
}

// ── Tool call row ────────────────────────────────────────────────────────────

function ToolCallRow({ tc, index }: { tc: ToolCallData; index: number }) {
  const [open, setOpen] = useState(false);
  const colors = [
    "border-l-blue-400",
    "border-l-purple-400",
    "border-l-emerald-400",
    "border-l-indigo-400",
    "border-l-amber-400",
  ];
  const colorClass = colors[index % colors.length];

  return (
    <div className={`border border-slate-200 dark:border-slate-700/60 rounded-xl overflow-hidden border-l-2 ${colorClass}`}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2.5 px-3 py-2 bg-white dark:bg-slate-800/40 hover:bg-slate-50 dark:hover:bg-slate-800/70 transition-colors text-left"
      >
        <Wrench className="w-3 h-3 text-slate-400 dark:text-slate-500 shrink-0" />
        <span className="font-mono text-xs font-medium text-slate-700 dark:text-slate-300">
          {tc.tool_name}
        </span>

        {/* Arg preview */}
        <span className="text-[10px] text-slate-400 dark:text-slate-600 font-mono truncate max-w-[160px] hidden sm:block">
          ({Object.entries(tc.arguments).map(([k,v]) => `${k}=${JSON.stringify(v)}`).join(", ")})
        </span>

        {tc.duration_ms != null && (
          <span className="ml-auto flex items-center gap-1 text-[10px] text-slate-400 dark:text-slate-500 shrink-0">
            <Clock className="w-3 h-3" />
            {tc.duration_ms.toFixed(1)}ms
          </span>
        )}
        <ChevronRight className={`w-3.5 h-3.5 text-slate-400 shrink-0 transition-transform duration-200 ${open ? "rotate-90" : ""}`} />
      </button>

      {open && (
        <div className="border-t border-slate-200 dark:border-slate-700/60 bg-slate-50/50 dark:bg-slate-900/20 px-3 py-2.5 space-y-2 animate-slide-down">
          <JsonBlock label="Arguments" data={tc.arguments} />
          <JsonBlock label="Result" data={tc.result} />
        </div>
      )}
    </div>
  );
}

// ── Single agent step ────────────────────────────────────────────────────────

function AgentStep({
  step,
  index,
  isLast,
  defaultOpen = false,
}: {
  step: AgentStepData;
  index: number;
  isLast: boolean;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const cfg = AGENT_CONFIG[step.agent_name] ?? DEFAULT_CONFIG;
  const { Icon } = cfg;
  const hasTools = step.tool_calls.length > 0;

  return (
    <div className="flex gap-3">
      {/* Timeline spine */}
      <div className="flex flex-col items-center shrink-0 pt-3">
        <div className={`w-2.5 h-2.5 rounded-full border-2 border-white dark:border-[#1e2433] ${cfg.dotColor} shadow-sm shrink-0`} />
        {!isLast && (
          <div className="w-px flex-1 mt-1 bg-slate-200 dark:bg-slate-700/60 min-h-4" />
        )}
      </div>

      {/* Card */}
      <div className={`flex-1 mb-3 border rounded-2xl overflow-hidden ${cfg.lightBorder} ${cfg.darkBorder} shadow-card transition-shadow hover:shadow-card-md`}>
        {/* Header */}
        <button
          onClick={() => setOpen(!open)}
          className={`w-full flex items-center gap-3 px-4 py-3 text-left transition-colors ${cfg.lightBg} ${cfg.darkBg} hover:opacity-90`}
        >
          <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 bg-white/60 dark:bg-black/20`}>
            <Icon className={`w-3.5 h-3.5 ${cfg.lightText} ${cfg.darkText}`} />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`text-sm font-semibold ${cfg.lightText} ${cfg.darkText}`}>
                {step.agent_name}
              </span>
              <span className="text-xs text-slate-400 dark:text-slate-600 font-mono">
                step {index + 1}
              </span>
              {hasTools && (
                <div className="flex gap-1 flex-wrap">
                  {step.tool_calls.map((tc, i) => (
                    <span
                      key={i}
                      className={`badge ${cfg.lightBadge} ${cfg.darkBadge} font-mono text-[10px]`}
                    >
                      <Wrench className="w-2.5 h-2.5" />
                      {tc.tool_name}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          <ChevronDown className={`w-4 h-4 text-slate-400 dark:text-slate-600 shrink-0 transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
        </button>

        {/* Reasoning — always visible */}
        <div className="px-4 py-2.5 bg-white dark:bg-[#1e2433] border-t border-slate-100 dark:border-slate-700/40">
          <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
            {step.reasoning}
          </p>
        </div>

        {/* Expanded detail */}
        {open && (
          <div className="bg-slate-50/80 dark:bg-slate-900/30 border-t border-slate-100 dark:border-slate-700/40 px-4 py-3 space-y-3 animate-slide-down">
            {hasTools && (
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-2">
                  MCP Tool Calls — {step.tool_calls.length}
                </p>
                <div className="space-y-2">
                  {step.tool_calls.map((tc, i) => (
                    <ToolCallRow key={i} tc={tc} index={i} />
                  ))}
                </div>
              </div>
            )}
            <JsonBlock label="Agent Output" data={step.output} />
          </div>
        )}
      </div>
    </div>
  );
}

// ── Full trace component ─────────────────────────────────────────────────────

export function ReasoningTrace({
  trace,
  defaultExpandFirst = false,
  compact = false,
}: {
  trace: ReasoningTraceData;
  defaultExpandFirst?: boolean;
  compact?: boolean;
}) {
  if (!trace?.steps?.length) {
    return (
      <div className="text-sm text-slate-400 dark:text-slate-600 py-8 text-center">
        No trace data available.
      </div>
    );
  }

  const totalTools = trace.steps.reduce((n, s) => n + s.tool_calls.length, 0);

  return (
    <div>
      {!compact && (
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-200 dark:border-slate-700/60">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Full Agent Reasoning Trail
          </p>
          <div className="flex items-center gap-3 text-xs text-slate-400 dark:text-slate-600">
            <span className="flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3 text-emerald-500" />
              {trace.steps.length} agents
            </span>
            <span className="flex items-center gap-1">
              <Wrench className="w-3 h-3 text-purple-400" />
              {totalTools} MCP calls
            </span>
          </div>
        </div>
      )}

      <div className="pl-1">
        {trace.steps.map((step, i) => (
          <AgentStep
            key={i}
            step={step}
            index={i}
            isLast={i === trace.steps.length - 1}
            defaultOpen={defaultExpandFirst && i === 0}
          />
        ))}
      </div>

      <p className="text-[10px] font-mono text-slate-300 dark:text-slate-700 mt-1 pl-1">
        trace_id: {trace.expense_id}
      </p>
    </div>
  );
}

// ── Animated pipeline progress ────────────────────────────────────────────────

export function PipelineProgress({
  steps,
  activeStep,
}: {
  steps: string[];
  activeStep: number;
}) {
  return (
    <div className="space-y-2">
      {steps.map((name, i) => {
        const cfg = AGENT_CONFIG[name] ?? DEFAULT_CONFIG;
        const { Icon } = cfg;
        const done = i < activeStep;
        const active = i === activeStep;
        const pending = !done && !active;

        return (
          <div
            key={i}
            className={`
              flex items-center gap-3 px-4 py-2.5 rounded-xl border transition-all duration-300
              ${done
                ? `${cfg.lightBorder} ${cfg.darkBorder} ${cfg.lightBg} ${cfg.darkBg}`
                : active
                  ? `${cfg.lightBorder} ${cfg.darkBorder} bg-white dark:bg-[#1e2433] shadow-card`
                  : "border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/20"
              }
            `}
          >
            {/* Icon */}
            <div className={`w-6 h-6 rounded-lg flex items-center justify-center shrink-0 ${
              done ? `bg-white/60 dark:bg-black/20` : active ? "bg-white dark:bg-white/5" : ""
            }`}>
              {done ? (
                <CheckCircle2 className={`w-4 h-4 ${cfg.lightText} ${cfg.darkText}`} />
              ) : active ? (
                <Icon className={`w-4 h-4 ${cfg.lightText} ${cfg.darkText} animate-pulse`} />
              ) : (
                <AlertCircle className="w-4 h-4 text-slate-300 dark:text-slate-700" />
              )}
            </div>

            <span className={`text-sm font-medium ${
              done || active ? `${cfg.lightText} ${cfg.darkText}` : "text-slate-300 dark:text-slate-700"
            }`}>
              {name}
            </span>

            {done && (
              <span className={`ml-auto badge ${cfg.lightBadge} ${cfg.darkBadge} text-[10px]`}>
                done
              </span>
            )}
            {active && (
              <span className="ml-auto text-[10px] text-slate-400 dark:text-slate-500 animate-pulse">
                running…
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
