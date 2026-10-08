import { useState, type FormEvent } from "react";
import { HeartPulse, Loader2 } from "lucide-react";
import type { PatientRegisterPayload } from "@/types";
interface Props {
  onLogin: (username: string, password: string) => Promise<{ ok: true } | { ok: false; status: number; message: string }>;
  onRegister: (payload: PatientRegisterPayload) => Promise<{ ok: true } | { ok: false; status: number; message: string }>;
}
export function PatientGate({ onLogin }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); if (busy) return;
    setBusy(true); setError(null);
    try { const r = await onLogin(username.trim(), password); if (!r.ok) setError(r.message); }
    catch { setError("Sign-in failed. Please try again."); }
    finally { setPassword(""); setBusy(false); }
  };
  return <div className="h-full flex items-center justify-center px-4"><div className="w-full max-w-md">
    <div className="text-center mb-8"><HeartPulse size={28} className="mx-auto text-brand-400 mb-3" />
      <h1 className="text-xl font-semibold text-slate-100">Auckland Hospital Health Assistant</h1>
      <p className="text-sm text-slate-400 mt-2">Sign in to access your own appointments and records.</p></div>
    <form onSubmit={submit} className="card p-5 space-y-4">
      <label className="block text-sm">Username<input className="input mt-1.5" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} disabled={busy} required /></label>
      <label className="block text-sm">Password<input className="input mt-1.5" type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} disabled={busy} required /></label>
      {error && <p className="text-sm text-danger" role="alert">{error}</p>}
      <button className="btn-primary w-full" disabled={busy || !username.trim() || !password}>{busy && <Loader2 size={14} className="animate-spin" />}{busy ? "Signing in…" : "Sign in"}</button>
      <p className="text-xs text-slate-400">Use the account issued by your clinic. Contact the clinic if you need access for another person.</p>
    </form></div></div>;
}
