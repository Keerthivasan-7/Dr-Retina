"use client";
import { useState } from "react";
import Link from "next/link";
import { changePassword, requestPasswordReset, registerOrganizationAccount } from "./actions";
export function AccountForm({ mode }: { mode: "reset" | "password" | "register" }) {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const title = mode === "reset" ? "Recover your account" : mode === "password" ? "Set your password" : "Create your administrator account";
  return <div className="max-w-lg mx-auto my-12 p-8 bg-white rounded-3xl border border-brand-100 shadow-card">
    <h1 className="text-2xl font-bold mb-3">{title}</h1>
    <p className="text-sm text-slate-600 mb-6">Credentials are securely managed by Supabase Auth.</p>
    <form className="space-y-4" method="post" onSubmit={async e => {
      e.preventDefault(); setBusy(true); setMessage(""); setFailed(false);
      try {
        const form = new FormData(e.currentTarget);
        if (mode !== "reset" && form.get("password") !== form.get("confirmPassword")) {
          setFailed(true); setMessage("Passwords do not match."); return;
        }
        const result = await (mode === "reset" ? requestPasswordReset(form) : mode === "password" ? changePassword(form) : registerOrganizationAccount(form));
        setMessage(result.error ?? result.message ?? "");
        setFailed(!!result.error);
      } catch { setFailed(true); setMessage("The request could not be completed. Please try again."); }
      finally { setBusy(false); }
    }}>
      {mode !== "password" && <label className="block text-sm">Email<input name="email" type="email" autoComplete="email" required className="mt-2 w-full border rounded-xl p-3" /></label>}
      {mode !== "reset" && <label className="block text-sm">New password<input name="password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required className="mt-2 w-full border rounded-xl p-3" /></label>}
      {mode !== "reset" && <label className="block text-sm">Confirm password<input name="confirmPassword" type="password" autoComplete="new-password" minLength={12} maxLength={128} required className="mt-2 w-full border rounded-xl p-3" /></label>}
      <button disabled={busy} className="w-full rounded-xl bg-brand-600 text-white p-3 font-semibold disabled:opacity-50">{busy ? "Please wait…" : mode === "reset" ? "Send recovery link" : mode === "password" ? "Save password" : "Verify email"}</button>
      {message && <p role={failed ? "alert" : "status"} className={failed ? "text-sm text-rose-700" : "text-sm text-emerald-700"}>{message}</p>}
    </form>
    <Link className="inline-block mt-5 text-sm text-brand-700" href="/login">Back to sign in</Link>
  </div>;
}
