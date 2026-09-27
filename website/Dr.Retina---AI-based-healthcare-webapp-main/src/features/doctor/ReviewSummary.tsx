"use client";
import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";
export function ReviewSummary() {
  const [stats, setStats] = useState<Record<string, number> | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const load = () => apiClient<{ data: Record<string, number> }>("/analytics/dashboard").then(r => setStats(r.data)).catch(e => setError(e.message));
    void load(); const timer = setInterval(load,15000); return () => clearInterval(timer);
  }, []);
  return <section className="my-6"><div className="grid grid-cols-2 lg:grid-cols-4 gap-3">{[
    ["awaitingReview","Awaiting review"],["additionalAnalysis","Additional analysis"],
    ["completedScreenings","Completed"],["pendingAnalysis","AI processing"],
  ].map(([key,label]) => <div key={key} className="bg-white rounded-2xl border border-brand-100 p-4">
    <p className="text-xs text-slate-500">{label}</p><p className="text-2xl font-bold mt-1">{stats?.[key!] ?? "—"}</p>
  </div>)}</div>{error && <p role="alert" className="text-sm text-rose-700">{error}</p>}</section>;
}
