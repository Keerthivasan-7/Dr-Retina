"use client";
import { useState } from "react";
import { updateProfile } from "./actions";
export function ProfileForm({ displayName }: { displayName: string }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  return <form className="my-6 space-y-3" method="post" onSubmit={async e => {
    e.preventDefault(); const form = new FormData(e.currentTarget); setBusy(true); setMessage("");
    try { const result = await updateProfile(form); setMessage(result.error ?? result.message ?? ""); }
    catch { setMessage("Unable to save. Please try again."); } finally { setBusy(false); }
  }}>
    <label className="block text-sm">Display name<input name="displayName" autoComplete="name" defaultValue={displayName} maxLength={100} className="block w-full rounded-xl border p-3 mt-2" /></label>
    <button disabled={busy} className="rounded-xl bg-brand-600 px-4 py-3 text-white disabled:opacity-50">{busy ? "Saving…" : "Save profile"}</button>
    {message && <p role="status" className="text-sm">{message}</p>}
  </form>;
}
