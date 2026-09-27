"use client";
import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";
export function Notifications({ doctor = false }: { doctor?: boolean }) {
  const [items, setItems] = useState<{ id: string; message: string; created_at: string }[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    const load = () => apiClient<{ data: typeof items }>("/notifications").then(r => { if (alive) setItems(r.data); }).catch(() => {});
    void load(); const timer = setInterval(load, 15000);
    return () => { alive = false; clearInterval(timer); };
  }, []);
  return <details className="max-w-7xl mx-auto px-5 py-3 bg-brand-50 border-b border-brand-100 text-sm">
    <summary className="cursor-pointer font-semibold text-brand-800">Team notifications ({items.length})</summary>
    {doctor && <label className="block my-3">Doctor availability<select defaultValue="" className="ml-3 rounded-lg border p-2" onChange={async e => {
      try { await apiClient("/me/availability", { method: "PATCH", body: { available: e.target.value === "available" } }); setError("Availability updated."); }
      catch { setError("Could not update availability."); }
    }}><option value="" disabled>Set availability</option><option value="available">Available for assignment</option><option value="unavailable">Unavailable</option></select></label>}
    {error && <p role="status">{error}</p>}
    <ul className="space-y-2 py-3">{items.slice(0, 10).map(item => <li key={item.id}>{item.message} <span className="text-slate-500 text-xs">{new Date(item.created_at).toLocaleString()}</span></li>)}</ul>
  </details>;
}

