"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api/client";
export function OrganizationForm({ existing }: { existing?: Record<string, string> }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const fields: [string, string][] = [
    ["name", "Organization name"], ["type", "Organization type"], ["address", "Address"],
    ["contactEmail", "Contact email"], ["contactPhone", "Contact phone"], ["identifier", "Organization identifier"],
  ];
  return <form className="max-w-2xl space-y-4 rounded-3xl border border-brand-100 bg-white p-6 shadow-card" method="post" onSubmit={async e => {
    e.preventDefault(); setError(""); setBusy(true);
    const data = Object.fromEntries(new FormData(e.currentTarget));
    try {
      await apiClient(existing ? "/organization" : "/organizations", { method: existing ? "PATCH" : "POST", body: data });
      if (!existing) { router.push("/admin"); router.refresh(); } else setError("Organization updated.");
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to save organization."); }
    finally { setBusy(false); }
  }}>
    <h2 className="text-xl font-bold">{existing ? "Organization settings" : "Create your organization"}</h2>
    <p className="text-sm text-slate-600">Your verified account becomes this organization’s administrator.</p>
    {fields.map(([key, label]) => <label key={key} className="block text-sm font-medium">{label}
      <input name={key} type={key === "contactEmail" ? "email" : "text"} defaultValue={existing?.[key] ?? ""} required={key !== "contactPhone"} maxLength={key === "address" ? 500 : 200} className="mt-1 w-full rounded-xl border p-3" />
    </label>)}
    <button disabled={busy} className="rounded-xl bg-brand-600 text-white px-5 py-3 disabled:opacity-50">{busy ? "Saving…" : existing ? "Save changes" : "Create organization"}</button>
    {error && <p role="status" className="text-sm">{error}</p>}
  </form>;
}
