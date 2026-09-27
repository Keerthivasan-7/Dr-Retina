"use client";
import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";
import { Dialog, DialogHeader } from "@/components/ui/Dialog";
import { ReportPanel } from "./ReportPanel";
import { ScreeningUploadModal } from "./ScreeningUploadModal";
type Row = { id: string; patientId: string; patientName: string; mrn: string; status: string; createdAt: string; reviewComments?: string; reviewReason?: string; assignmentStatus: string };
type Doctor = { user_id: string; full_name: string; role: string; active: boolean; available: boolean };
export function ScreeningHistory({ technician = false, admin = false, patientId }: { technician?: boolean; admin?: boolean; patientId?: string }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [offset, setOffset] = useState(0);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [repeat, setRepeat] = useState<{ patientId: string; screeningId: string } | null>(null);
  const [error, setError] = useState("");
  const refresh = useCallback(() => {
    const request = patientId
      ? apiClient<{ screenings: Row[] }>(`/patients/${patientId}/history?limit=200&offset=${offset}`).then(r => r.screenings)
      : apiClient<{ data: Row[] }>(`/screenings?limit=200&offset=${offset}`).then(r => r.data);
    request.then(data => { setRows(data); setError(""); }).catch(e => setError(e.message));
  }, [patientId, offset]);
  useEffect(() => { refresh(); const timer = setInterval(refresh, 15000); return () => clearInterval(timer); }, [refresh]);
  useEffect(() => { if (admin) apiClient<{ data: Doctor[] }>("/users").then(r => setDoctors(r.data.filter(d => d.role === "DOCTOR" && d.active && d.available))).catch(e => setError(e.message)); }, [admin]);
  return <section className="rounded-3xl bg-white border border-brand-100 p-5 my-6">
    <h2 className="font-bold text-lg mb-2">Screening history &amp; follow-up tasks</h2>
    <p className="text-xs text-slate-500 mb-4">Page {offset / 200 + 1} · Up to 200 screenings per page. Refreshes every 15 seconds.</p>
    <div className="flex gap-3 mb-4 text-sm"><button className="border rounded-lg px-3 py-2 disabled:opacity-40" disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - 200))}>Previous</button><button className="border rounded-lg px-3 py-2 disabled:opacity-40" disabled={rows.length < 200} onClick={() => setOffset(value => value + 200)}>Next</button></div>
    {error && <p role="alert" className="text-rose-700 mb-3">{error}</p>}
    <div className="space-y-3">{rows.filter(r => !patientId || r.patientId === patientId).map(row => <div key={row.id} className="rounded-xl border p-4 flex flex-wrap items-center justify-between gap-3">
      <div><p className="font-semibold text-sm">{row.patientName} · {row.mrn}</p><p className="text-xs text-brand-700 mt-1">{row.status.replaceAll("_", " ")} · {new Date(row.createdAt).toLocaleString()}</p>
        {row.reviewComments && <p className="text-sm mt-2">{row.reviewReason}: {row.reviewComments}</p>}</div>
      <div className="flex flex-wrap gap-2">
        <button onClick={() => setSelected(row.id)} className="text-sm rounded-lg bg-brand-50 text-brand-700 px-3 py-2">View report</button>
        {technician && ["QUALITY_REJECTED", "ADDITIONAL_ANALYSIS_REQUIRED"].includes(row.status) && <button onClick={() => setRepeat({ patientId: row.patientId, screeningId: row.id })} className="text-sm rounded-lg bg-brand-600 text-white px-3 py-2">Capture repeat image</button>}
        {technician && ["QUALITY_CHECKING", "AI_PROCESSING", "IMAGE_UPLOADED", "READY_FOR_ANALYSIS"].includes(row.status) && <button className="text-sm border rounded-lg px-3 py-2" onClick={async () => {
          try { await apiClient(`/screenings/${row.id}/retry`, { method: "POST" }); refresh(); } catch (e) { setError(e instanceof Error ? e.message : "Retry unavailable"); }
        }}>Retry failed analysis</button>}
        {admin && ["REPORT_READY", "SENT_TO_DOCTOR", "DOCTOR_REVIEWING"].includes(row.status) && <select aria-label={`Assign doctor for ${row.mrn}`} defaultValue="" className="text-sm border rounded-lg p-2" onChange={async e => {
          try { await apiClient(`/screenings/${row.id}/assign`, { method: "POST", body: { doctorId: e.target.value } }); refresh(); } catch (e) { setError(e instanceof Error ? e.message : "Assignment failed"); }
        }}><option value="" disabled>Assign / reassign doctor</option>{doctors.map(d => <option key={d.user_id} value={d.user_id}>{d.full_name}</option>)}</select>}
      </div>
    </div>)}</div>
    {!rows.length && !error && <p className="text-sm text-slate-500">No screenings recorded yet.</p>}
    <Dialog open={!!selected} onClose={() => setSelected(null)} labelledBy="history-title" maxWidth="max-w-3xl">
      <DialogHeader id="history-title" title="Clinical report" subtitle="AI findings and clinical decisions" onClose={() => setSelected(null)} />
      <div className="p-6 max-h-[75vh] overflow-y-auto">{selected && <ReportPanel key={selected} id={selected} />}</div>
    </Dialog>
    <ScreeningUploadModal open={!!repeat} repeat={repeat} onClose={() => { setRepeat(null); refresh(); }} onScreeningCompleted={refresh} />
  </section>;
}
