"use client";
import { useState } from "react";
import { resendVerification } from "./actions";
export function ResendVerification() {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  return <details className="mt-5 text-sm text-slate-600"><summary className="cursor-pointer text-brand-700">Resend verification email</summary>
    <form className="mt-3 space-y-3" method="post" onSubmit={async e => {
      e.preventDefault(); const form = new FormData(e.currentTarget); setBusy(true); setMessage("");
      try { const result = await resendVerification(form); setMessage(result.error ?? result.message ?? ""); }
      catch { setMessage("Unable to send email. Please try again."); } finally { setBusy(false); }
    }}>
      <label className="block">Email<input name="email" type="email" autoComplete="email" required className="block w-full border rounded-xl p-3 mt-1" /></label>
      <button disabled={busy} className="border rounded-xl px-4 py-2 disabled:opacity-50">{busy ? "Sending…" : "Send verification email"}</button>
      {message && <p role="status">{message}</p>}
    </form>
  </details>;
}
