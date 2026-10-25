import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LogIn, Loader2 } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import ThemeToggle from "../components/ThemeToggle";

const DEMO = [
  {
    username: "officer1",
    password: "officer123",
    role: "officer",
    name: "Atharva Bhangale",
  },
  {
    username: "reviewer1",
    password: "reviewer123",
    role: "reviewer",
    name: "Nayan Khune",
  },
  {
    username: "auditor1",
    password: "auditor123",
    role: "auditor (read-only)",
    name: "Tejas Bagade",
  },
];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("officer1");
  const [password, setPassword] = useState("officer123");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(username, password);
      navigate("/");
    } catch {
      setError("Invalid username or password");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 p-4">
      <ThemeToggle className="btn-ghost absolute right-4 top-4 !py-1.5 text-xs" />
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-center gap-3">
          <span className="relative">
            <span className="absolute -inset-2 rounded-3xl bg-gradient-to-br from-indigo-500/40 via-sky-500/25 to-emerald-500/20 blur-xl" />
            <img
              src="/logo.png"
              alt="VeriGate logo"
              className="relative h-14 w-14 drop-shadow-lg"
            />
          </span>
          <div>
            <h1 className="gradient-text text-3xl font-bold tracking-tight">
              VeriGate
            </h1>
            <p className="text-xs uppercase tracking-widest text-slate-400">
              AICTE Extension of Approval Validator
            </p>
          </div>
        </div>
        <p className="mb-5 text-center text-sm leading-relaxed text-slate-400">
          AI reads the paperwork and checks it against the rules —{" "}
          <span className="text-slate-200">officers make the final call.</span>
          <br />
          When evidence is weak, the system abstains instead of guessing.
        </p>

        <form onSubmit={onSubmit} className="card space-y-4">
          <div>
            <label className="label">Username</label>
            <input
              className="input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
            />
          </div>
          <div>
            <label className="label">Password</label>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && (
            <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-300">
              {error}
            </div>
          )}
          <button className="btn-primary w-full" disabled={busy}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
            Sign in
          </button>
          <p className="text-center text-xs text-slate-500">
            Decision-support only. The Evidence Gate abstains; officers decide.
          </p>
        </form>

        <div className="card mt-4">
          <div className="label">Demo accounts</div>
          <div className="space-y-2">
            {DEMO.map((d) => (
              <button
                key={d.username}
                className="flex w-full items-center justify-between rounded-lg border border-slate-800 px-3 py-2 text-left text-sm hover:border-indigo-500/50 hover:bg-slate-800/60"
                onClick={() => {
                  setUsername(d.username);
                  setPassword(d.password);
                }}
              >
                <span className="flex min-w-0 flex-col">
                  <span className="font-mono text-indigo-300">{d.username}</span>
                  <span className="truncate text-[11px] text-slate-500">
                    {d.name}
                  </span>
                </span>
                <span className="font-mono text-slate-400">{d.password}</span>
                <span className="text-right text-xs text-slate-500">
                  {d.role}
                </span>
              </button>
            ))}
          </div>
        </div>

        <p className="mt-5 text-center text-xs text-slate-500">
          VeriGate prototype
          <br />
          Synthetic demo data only — no real institution records.
        </p>
      </div>
    </div>
  );
}
