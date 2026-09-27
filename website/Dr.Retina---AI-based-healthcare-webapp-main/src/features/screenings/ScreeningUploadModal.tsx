"use client";
import { useEffect, useRef, useState } from "react";
import { Dialog, DialogHeader } from "@/components/ui/Dialog";
import { fetchPatients } from "@/features/patients/api";
import { apiClient } from "@/lib/api/client";
import type { Patient } from "@/types/domain";
import { ReportPanel } from "./ReportPanel";
export function ScreeningUploadModal({ open, onClose, onScreeningCompleted, repeat }: {
  open: boolean; onClose: () => void; onScreeningCompleted?: (r: unknown) => void;
  repeat?: { patientId: string; screeningId: string } | null;
}) {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [search, setSearch] = useState("");
  const [patient, setPatient] = useState("");
  const [eye, setEye] = useState("OD");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<{ jobId: string; screeningId: string } | null>(null);
  const [status, setStatus] = useState("");
  const requestKey = useRef<string | null>(null);
  useEffect(() => {
    if (!open) return;
    let alive = true;
    const timer = setTimeout(() => { fetchPatients({ q: search }).then(rows => { if (alive) { setPatients(rows); setPatient(repeat?.patientId ?? ""); requestKey.current = null; } })
      .catch(e => { if (alive) setError(e.message); }); }, 250);
    return () => { alive = false; clearTimeout(timer); };
  }, [open, repeat, search]);
  useEffect(() => {
    if (!open || !job) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const result = await apiClient<{ status: string; screeningStatus: string; errorCode?: string }>(`/screenings/jobs/${job.jobId}`);
        if (!alive) return;
        setStatus(result.screeningStatus);
        if (result.status === "FAILED") {
          setError(result.errorCode === "AI_NOT_CONFIGURED" ? "The image is preserved. AI analysis is not configured; contact your administrator." : "Analysis is unavailable. The image is preserved; retry analysis when the service recovers.");
          return;
        }
        if (result.status === "COMPLETED") { onScreeningCompleted?.(result); return; }
        timer = setTimeout(poll, 3000);
      } catch (e) { if (alive) { setError(e instanceof Error ? e.message : "Could not refresh status"); timer = setTimeout(poll, 10000); } }
    };
    void poll();
    return () => { alive = false; clearTimeout(timer); };
  }, [job, open, onScreeningCompleted]);
  const close = () => { setJob(null); setFile(null); setError(""); setStatus(""); requestKey.current = null; onClose(); };
  return <Dialog open={open} onClose={close} labelledBy="su-title" maxWidth="max-w-2xl">
    <DialogHeader id="su-title" title={repeat ? "Repeat retinal acquisition" : "Start Fundus Screening"} subtitle="Patient intake · Image quality · AI analysis · Doctor review" onClose={close} />
    <div className="p-6 max-h-[75vh] overflow-y-auto space-y-4">
      {!job ? <form className="space-y-4" method="post" encType="multipart/form-data" onSubmit={async e => {
        e.preventDefault(); if (!file) return;
        if (!["image/jpeg", "image/png"].includes(file.type) || file.size > 25 * 1024 * 1024) { setError("Choose a JPEG or PNG image of up to 25 MB."); return; }
        setBusy(true); setError("");
        const form = new FormData(); form.set("patientId", patient); form.set("eye", eye); form.set("image", file);
        if (repeat) form.set("parentScreeningId", repeat.screeningId);
        requestKey.current ??= crypto.randomUUID();
        try {
          const result = await apiClient<{ jobId: string; screeningId: string }>("/screenings/analyze", {
            method: "POST", body: form, timeoutMs: 65000, idempotencyKey: requestKey.current,
          });
          setJob(result); setStatus("IMAGE_UPLOADED");
        } catch (e) { setError(e instanceof Error ? e.message : "Upload failed"); }
        finally { setBusy(false); }
      }}>
        <label className="block text-sm font-semibold">Patient
          {!repeat && <input aria-label="Search patients" placeholder="Search by name or patient ID" value={search} onChange={e => setSearch(e.target.value)} className="w-full mt-2 border rounded-xl p-3" />}
          <select required value={patient} disabled={!!repeat} onChange={e => { setPatient(e.target.value); requestKey.current = null; }} className="w-full mt-2 border rounded-xl p-3">
            <option value="">Select a registered patient</option>{patients.map(p => <option key={p.id} value={p.id}>{p.fullName} · {p.mrn}</option>)}
            {repeat && !patients.some(p => p.id === repeat.patientId) && <option value={repeat.patientId}>Patient from the original screening</option>}
          </select>
        </label>
        <label className="block text-sm font-semibold">Eye<select value={eye} onChange={e => { setEye(e.target.value); requestKey.current = null; }} className="w-full mt-2 border rounded-xl p-3">
          <option value="OD">Right eye (OD)</option><option value="OS">Left eye (OS)</option>
        </select></label>
        <label className="block rounded-2xl border-2 border-dashed border-brand-200 bg-brand-50 p-6 text-sm font-semibold">Retinal fundus image
          <input type="file" accept="image/jpeg,image/png" required onChange={e => { setFile(e.target.files?.[0] ?? null); requestKey.current = null; }} className="block mt-3 w-full" />
          <span className="block mt-3 text-xs font-normal text-slate-600">JPEG or PNG, up to 25 MB. The original image is preserved unchanged. DICOM is not supported.</span>
        </label>
        <button disabled={busy || !patient} className="w-full rounded-xl bg-brand-600 text-white py-3 font-semibold disabled:opacity-50">{busy ? "Uploading…" : "Submit screening"}</button>
      </form> : (() => {
        const done = ["QUALITY_REJECTED", "REPORT_READY", "SENT_TO_DOCTOR", "DOCTOR_REVIEWING", "VERIFIED", "COMPLETED"].includes(status);
        return <>
          <p role="status" className="rounded-xl bg-brand-50 p-4 font-semibold flex items-center gap-2">
            {!done && <span className="inline-block w-4 h-4 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" aria-hidden="true" />}
            {done ? "Analysis complete" : `${status.replaceAll("_", " ")}…`}
          </p>
          {!done && <p className="text-sm text-slate-600">Checking image quality, then running AI analysis. This usually takes under 30 seconds — results appear below as soon as they&apos;re ready. You can also close this window and find this screening in history later.</p>}
          {done && <ReportPanel id={job.screeningId} />}
        </>;
      })()}
      {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
    </div>
  </Dialog>;
}
