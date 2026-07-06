"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  ArrowRight,
  Cpu,
  GitMerge,
  Search,
  Lock,
  Database,
  Wrench,
  Shield,
  Zap,
} from "lucide-react";
import { Nav } from "./components/Nav";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface HealthData {
  status: string;
  gemini_configured: boolean;
  extraction_mode: string;
}

interface StatsData {
  total: number;
  approved: number;
  escalated: number;
  rejected: number;
}

export default function Home() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [stats, setStats] = useState<StatsData | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/health`)
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => null);

    fetch(`${API_URL}/api/audit/all?limit=200`, {
      headers: { "X-User-ID": "E3001" },
    })
      .then((r) => r.json())
      .then((d) => {
        const entries = d.audit_entries || [];
        setStats({
          total: entries.length,
          approved: entries.filter(
            (e: { routing_decision: { decision: string } }) =>
              e.routing_decision?.decision === "auto-approved"
          ).length,
          escalated: entries.filter(
            (e: { routing_decision: { decision: string } }) =>
              e.routing_decision?.decision === "escalate-to-human"
          ).length,
          rejected: entries.filter(
            (e: { routing_decision: { decision: string } }) =>
              e.routing_decision?.decision === "rejected"
          ).length,
        });
      })
      .catch(() => null);
  }, []);

  const apiStatus = health
    ? {
        online: health.status === "healthy",
        mode: health.gemini_configured ? "Gemini" : "Fallback",
      }
    : null;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-[#0f0a2e] to-slate-950 dark:from-slate-950 dark:via-[#0f0a2e] dark:to-slate-950">
      {/* Mesh gradient overlay */}
      <div className="absolute inset-0 bg-gradient-mesh opacity-60 pointer-events-none" />

      {/* Subtle grid */}
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.03]"
        style={{
          backgroundImage: `linear-gradient(rgb(255 255 255) 1px, transparent 1px), linear-gradient(90deg, rgb(255 255 255) 1px, transparent 1px)`,
          backgroundSize: "40px 40px",
        }}
      />

      <div className="relative z-10">
        <Nav apiStatus={apiStatus} />

        {/* Hero */}
        <div className="max-w-5xl mx-auto px-6 pt-24 pb-16 text-center">
          <div className="inline-flex items-center gap-2 bg-blue-500/10 text-blue-300 px-3 py-1.5 rounded-full text-xs mb-8 border border-blue-500/20 backdrop-blur-sm">
            <Zap className="w-3 h-3" />
            Multi-agent · MCP tools · Security layer · CLI + API
          </div>

          <h1 className="text-5xl md:text-6xl font-bold text-white mb-6 leading-[1.1] tracking-tight">
            Expense validation,
            <br />
            <span className="bg-gradient-to-r from-blue-400 via-violet-400 to-indigo-400 bg-clip-text text-transparent">
              handled by agents
            </span>
          </h1>

          <p className="text-slate-400 text-lg mb-10 max-w-2xl mx-auto leading-relaxed">
            Three specialized AI agents — Intake, Policy, and Risk — process every submission
            in sequence. Each calls real MCP tools, records its reasoning, and hands off a
            typed result to the next.
          </p>

          <div className="flex gap-3 justify-center flex-wrap">
            <Link
              href="/submit"
              className="group flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-xl font-medium transition-all duration-200 shadow-glow-blue hover:shadow-glow-blue hover:-translate-y-0.5"
            >
              Submit an Expense
              <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
            </Link>
            <Link
              href="/audit"
              className="flex items-center gap-2 glass text-slate-200 hover:text-white px-6 py-3 rounded-xl font-medium transition-all duration-200 hover:-translate-y-0.5"
            >
              <Database className="w-4 h-4" />
              View Audit Trail
            </Link>
          </div>
        </div>

        {/* Live stats */}
        {stats && stats.total > 0 && (
          <div className="max-w-3xl mx-auto px-6 pb-16">
            <p className="text-center text-slate-600 text-xs mb-4 uppercase tracking-widest">
              Live Pipeline Stats
            </p>
            <div className="grid grid-cols-4 gap-3">
              <LiveStat label="Total" value={stats.total} color="text-blue-300" bg="bg-blue-500/10 border-blue-500/20" />
              <LiveStat label="Approved" value={stats.approved} color="text-emerald-300" bg="bg-emerald-500/10 border-emerald-500/20" />
              <LiveStat label="Escalated" value={stats.escalated} color="text-amber-300" bg="bg-amber-500/10 border-amber-500/20" />
              <LiveStat label="Rejected" value={stats.rejected} color="text-red-300" bg="bg-red-500/10 border-red-500/20" />
            </div>
          </div>
        )}

        {/* Pipeline diagram */}
        <div className="max-w-5xl mx-auto px-6 pb-20">
          <p className="text-center text-slate-600 text-xs mb-8 uppercase tracking-widest">
            The Agent Pipeline
          </p>
          <div className="flex items-stretch justify-center gap-0 flex-col md:flex-row">
            <PipelineStep
              num="01"
              name="Intake Agent"
              desc="Parses receipts or employee fields into structured StructuredExpense JSON"
              tools={[]}
              color="blue"
              Icon={Search}
            />
            <PipelineConnector />
            <PipelineStep
              num="02"
              name="Policy Agent"
              desc="Checks compliance via MCP — spend limits, vendor allowlists, pre-approval"
              tools={["get_employee_profile", "get_policy_rules"]}
              color="purple"
              Icon={GitMerge}
            />
            <PipelineConnector />
            <PipelineStep
              num="03"
              name="Risk & Routing Agent"
              desc="Detects duplicates, checks budget utilization, routes to final decision"
              tools={["check_duplicate", "get_employee_profile", "get_accounting_context"]}
              color="indigo"
              Icon={Cpu}
            />
          </div>
        </div>

        {/* Feature grid */}
        <div className="max-w-5xl mx-auto px-6 pb-20">
          <p className="text-center text-slate-600 text-xs mb-8 uppercase tracking-widest">
            What&apos;s Built In
          </p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <FeatureCard icon={<Cpu className="w-4 h-4 text-blue-400" />} title="Multi-agent ADK"
              desc="Three agents with typed handoffs: StructuredExpense → ComplianceVerdict → RoutingDecision" />
            <FeatureCard icon={<Wrench className="w-4 h-4 text-purple-400" />} title="MCP Tool Server"
              desc="4 tools backed by SQLite: policy rules, employee profiles, duplicate detection, budget context" />
            <FeatureCard icon={<Lock className="w-4 h-4 text-emerald-400" />} title="Security Layer"
              desc="PII redaction before any LLM call. RBAC on every endpoint. Immutable append-only audit log." />
            <FeatureCard icon={<Database className="w-4 h-4 text-indigo-400" />} title="Reasoning Trace"
              desc="Every MCP call, agent step, and decision rationale stored in the audit log." />
            <FeatureCard icon={<Shield className="w-4 h-4 text-amber-400" />} title="CLI + REST API"
              desc="expenseguard submit/review/audit commands. FastAPI with RBAC guards on every route." />
            <FeatureCard icon={<Zap className="w-4 h-4 text-rose-400" />} title="Deployable"
              desc="docker-compose + Dockerfiles for API and frontend. Single command to start everything." />
          </div>
        </div>

        {/* Outcomes */}
        <div className="max-w-3xl mx-auto px-6 pb-28">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <OutcomeCard icon={<CheckCircle className="w-4 h-4" />} title="Auto-Approved"
              desc="Compliant, low-risk expenses cleared without human touch" color="green" />
            <OutcomeCard icon={<AlertTriangle className="w-4 h-4" />} title="Escalated"
              desc="Flagged for the right manager with full reasoning visible" color="yellow" />
            <OutcomeCard icon={<XCircle className="w-4 h-4" />} title="Rejected"
              desc="Policy violations rejected with the exact rule cited" color="red" />
          </div>
        </div>
      </div>
    </div>
  );
}

function LiveStat({ label, value, color, bg }: { label: string; value: number; color: string; bg: string }) {
  return (
    <div className={`border rounded-xl px-4 py-3 text-center backdrop-blur-sm ${bg}`}>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      <div className="text-slate-500 text-xs mt-0.5">{label}</div>
    </div>
  );
}

function PipelineConnector() {
  return (
    <div className="flex md:items-center md:justify-center px-2 py-2 md:py-0">
      <ArrowRight className="w-5 h-5 text-slate-700 hidden md:block" />
      <div className="w-px h-6 bg-slate-700 md:hidden mx-auto" />
    </div>
  );
}

function PipelineStep({
  num, name, desc, tools, color, Icon,
}: {
  num: string; name: string; desc: string;
  tools: string[]; color: string; Icon: React.ElementType;
}) {
  const colors: Record<string, string> = {
    blue: "border-blue-500/20 bg-blue-500/5 text-blue-300",
    purple: "border-purple-500/20 bg-purple-500/5 text-purple-300",
    indigo: "border-indigo-500/20 bg-indigo-500/5 text-indigo-300",
  };
  const toolBg: Record<string, string> = {
    blue: "bg-blue-500/10 text-blue-400",
    purple: "bg-purple-500/10 text-purple-400",
    indigo: "bg-indigo-500/10 text-indigo-400",
  };

  return (
    <div className={`rounded-2xl border p-5 flex-1 min-w-0 md:max-w-xs backdrop-blur-sm ${colors[color]}`}>
      <div className="flex items-center gap-2 mb-2.5">
        <Icon className="w-4 h-4 opacity-80" />
        <span className="text-[10px] font-mono text-slate-600">{num}</span>
      </div>
      <div className="font-semibold mb-1.5 text-sm">{name}</div>
      <div className="text-xs opacity-60 leading-relaxed mb-3">{desc}</div>
      {tools.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {tools.map((t) => (
            <span key={t} className={`text-[10px] font-mono px-1.5 py-0.5 rounded-md ${toolBg[color]}`}>
              {t}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function FeatureCard({ icon, title, desc }: { icon: React.ReactNode; title: string; desc: string }) {
  return (
    <div className="glass rounded-2xl p-4 hover:-translate-y-0.5 transition-transform duration-200">
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="text-white font-medium text-sm">{title}</span>
      </div>
      <p className="text-slate-400 text-xs leading-relaxed">{desc}</p>
    </div>
  );
}

function OutcomeCard({ icon, title, desc, color }: { icon: React.ReactNode; title: string; desc: string; color: string }) {
  const styles: Record<string, string> = {
    green: "border-emerald-500/20 bg-emerald-500/5 text-emerald-400",
    yellow: "border-amber-500/20 bg-amber-500/5 text-amber-400",
    red: "border-red-500/20 bg-red-500/5 text-red-400",
  };
  return (
    <div className={`rounded-2xl border p-4 backdrop-blur-sm ${styles[color]}`}>
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="text-white font-medium text-sm">{title}</span>
      </div>
      <p className="text-slate-400 text-xs leading-relaxed">{desc}</p>
    </div>
  );
}
