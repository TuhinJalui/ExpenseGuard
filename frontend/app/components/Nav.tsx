"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Shield, Sun, Moon, Menu, X, Cpu } from "lucide-react";

const LINKS = [
  { href: "/submit", label: "Submit Expense" },
  { href: "/review", label: "Review Queue" },
  { href: "/audit", label: "Audit Trail" },
];

// ── Theme toggle button ─────────────────────────────────────────────────

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Avoid hydration mismatch
  useEffect(() => setMounted(true), []);
  if (!mounted) return <div className="w-8 h-8" />;

  const isDark = theme === "dark";

  return (
    <button
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label="Toggle theme"
      className={`
        relative w-8 h-8 rounded-lg flex items-center justify-center
        transition-all duration-200 group
        ${isDark
          ? "bg-white/10 hover:bg-white/20 text-yellow-300"
          : "bg-slate-100 hover:bg-slate-200 text-slate-600"
        }
      `}
    >
      <span className={`absolute transition-all duration-300 ${isDark ? "rotate-0 scale-100 opacity-100" : "rotate-90 scale-0 opacity-0"}`}>
        <Sun className="w-4 h-4" />
      </span>
      <span className={`absolute transition-all duration-300 ${isDark ? "rotate-90 scale-0 opacity-0" : "rotate-0 scale-100 opacity-100"}`}>
        <Moon className="w-4 h-4" />
      </span>
    </button>
  );
}

// ── Main Nav ────────────────────────────────────────────────────────────

export function Nav({
  apiStatus,
}: {
  apiStatus?: { online: boolean; mode: string } | null;
}) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { theme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const isHomepage = pathname === "/";

  return (
    <>
      <nav
        className={`
          sticky top-0 z-50 w-full
          transition-all duration-200
          ${isHomepage
            ? "border-b border-white/8 bg-black/20 backdrop-blur-xl"
            : mounted && theme === "dark"
            ? "border-b border-white/8 bg-[#161b28]/90 backdrop-blur-xl"
            : "border-b border-slate-200 bg-white/90 backdrop-blur-xl shadow-sm"
          }
        `}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="flex items-center h-14 gap-4">
            {/* Logo */}
            <Link href="/" className="flex items-center gap-2 shrink-0 group">
              <div className="relative">
                <Shield className={`w-5 h-5 transition-colors ${isHomepage || (mounted && theme === "dark") ? "text-blue-400" : "text-blue-600"}`} />
                <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
              </div>
              <span className={`font-bold text-sm tracking-tight ${isHomepage || (mounted && theme === "dark") ? "text-white" : "text-slate-900"}`}>
                ExpenseGuard
              </span>
            </Link>

            {/* Desktop links */}
            <div className="hidden sm:flex items-center gap-1 ml-2">
              {LINKS.map((l) => {
                const active = pathname === l.href;
                return (
                  <Link
                    key={l.href}
                    href={l.href}
                    className={`
                      px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-150
                      ${isHomepage || (mounted && theme === "dark")
                        ? active
                          ? "bg-white/15 text-white"
                          : "text-slate-300 hover:text-white hover:bg-white/10"
                        : active
                          ? "bg-blue-50 text-blue-700"
                          : "text-slate-500 hover:text-slate-900 hover:bg-slate-100"
                      }
                    `}
                  >
                    {l.label}
                  </Link>
                );
              })}
            </div>

            {/* Right side */}
            <div className="flex items-center gap-2 ml-auto">
              {/* API status pill */}
              {apiStatus && (
                <div className={`hidden md:flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border transition-colors ${
                  apiStatus.online
                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                    : "border-red-500/30 bg-red-500/10 text-red-400"
                }`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${apiStatus.online ? "bg-emerald-400 animate-pulse" : "bg-red-400"}`} />
                  <Cpu className="w-3 h-3" />
                  {apiStatus.online ? apiStatus.mode : "offline"}
                </div>
              )}

              {/* Theme toggle */}
              <ThemeToggle />

              {/* Mobile menu button */}
              <button
                onClick={() => setMobileOpen(!mobileOpen)}
                className={`sm:hidden p-1.5 rounded-lg transition-colors ${
                  isHomepage || (mounted && theme === "dark")
                    ? "text-slate-300 hover:bg-white/10"
                    : "text-slate-500 hover:bg-slate-100"
                }`}
                aria-label="Menu"
              >
                {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile dropdown */}
        {mobileOpen && (
          <div className={`sm:hidden border-t animate-slide-down ${
            mounted && theme === "dark"
              ? "border-white/10 bg-[#1e2433]"
              : "border-slate-200 bg-white"
          }`}>
            {LINKS.map((l) => {
              const active = pathname === l.href;
              return (
                <Link
                  key={l.href}
                  href={l.href}
                  onClick={() => setMobileOpen(false)}
                  className={`block px-6 py-3 text-sm font-medium transition-colors ${
                    active
                      ? mounted && theme === "dark"
                        ? "text-blue-400 bg-blue-400/5"
                        : "text-blue-700 bg-blue-50"
                      : mounted && theme === "dark"
                        ? "text-slate-300 hover:text-white hover:bg-white/5"
                        : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                  }`}
                >
                  {l.label}
                </Link>
              );
            })}
          </div>
        )}
      </nav>
    </>
  );
}
