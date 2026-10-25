import { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  UploadCloud,
  Inbox,
  ScrollText,
  BarChart3,
  Globe,
  LogOut,
  FlaskConical,
} from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import ThemeToggle from "./ThemeToggle";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/upload", label: "Upload", icon: UploadCloud },
  { to: "/queue", label: "Review Queue", icon: Inbox },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/issuers", label: "Issuer Portals", icon: Globe },
  { to: "/audit", label: "Audit Log", icon: ScrollText },
];

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout, canUpload } = useAuth();
  const navigate = useNavigate();

  const nav = NAV.filter((n) => n.to !== "/upload" || canUpload); // upload is officer-only

  return (
    <div className="flex min-h-screen">
      <aside className="fixed inset-y-0 left-0 flex w-56 flex-col border-r border-slate-800/80 bg-slate-900/85 backdrop-blur">
        <div className="flex items-center gap-2.5 px-4 py-5">
          <span className="relative">
            <span className="absolute -inset-1.5 rounded-2xl bg-gradient-to-br from-indigo-500/40 to-sky-500/30 blur-md" />
            <img
              src="/logo.png"
              alt="VeriGate logo"
              className="relative h-9 w-9 shrink-0"
            />
          </span>
          <div>
            <div className="gradient-text text-lg font-bold tracking-tight">
              VeriGate
            </div>
            <div className="text-[10px] uppercase tracking-widest text-slate-500">
              AICTE EoA Validator
            </div>
          </div>
        </div>

        <nav className="mt-2 flex-1 space-y-1 px-3">
          {nav.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  isActive
                    ? "bg-gradient-to-r from-indigo-600/40 to-sky-600/20 text-indigo-200 shadow-md shadow-indigo-950/60 ring-1 ring-indigo-500/30"
                    : "text-slate-300 hover:bg-slate-800/70 hover:text-slate-100"
                }`
              }
            >
              <Icon className="h-4 w-4 transition group-hover:scale-110" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-slate-800/80 p-3 text-xs">
          <div className="mb-2 flex items-center gap-2 text-slate-300">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-sky-500 font-bold text-white shadow-md shadow-indigo-950">
              {user?.full_name?.[0] ?? "?"}
            </div>
            <div className="min-w-0">
              <div className="truncate font-semibold">{user?.full_name}</div>
              <div className="text-slate-500">{user?.role}</div>
            </div>
          </div>
          <ThemeToggle className="btn-ghost mb-2 w-full !py-1.5 text-xs" />
          <button
            className="btn-ghost w-full !py-1.5 text-xs"
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            <LogOut className="h-3.5 w-3.5" /> Sign out
          </button>
        </div>
      </aside>

      <main className="ml-56 flex-1 p-6">{children}</main>
    </div>
  );
}

export function MockBanner() {
  return (
    <div className="mb-3 inline-flex items-center gap-1.5 rounded-full border border-slate-700/70 bg-slate-900/70 px-3 py-1 text-[11px] text-slate-400">
      <FlaskConical className="h-3 w-3 shrink-0 text-slate-500" />
      Synthetic demo data · AI advises, officers decide
    </div>
  );
}
