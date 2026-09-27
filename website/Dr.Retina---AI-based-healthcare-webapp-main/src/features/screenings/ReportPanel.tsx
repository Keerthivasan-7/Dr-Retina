"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { apiClient } from "@/lib/api/client";
import type { ClinicalReport } from "./types";
export function ReportPanel({ id, canReview = false, onChanged }: { id: string; canReview?: boolean; onChanged?: () => void }) {
  const [report, setReport] = useState<ClinicalReport | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  const [decision, setDecision] = useState("VERIFIED");
  const [overlayError, setOverlayError] = useState(false);
  useEffect(() => {
    let alive = true;
    apiClient<ClinicalReport>(`/screenings/${id}`).then(r => { if (alive) setReport(r); })
      .catch(e => { if (alive) setError(e.message); });
    return () => { alive = false; };
  }, [id, reload]);
  if (!report) return <p role="status" className="p-5">{error || "Loading clinical report…"}</p>;
  const reviewable = canReview && ["SENT_TO_DOCTOR", "DOCTOR_REVIEWING"].includes(report.screening.status);
  return <div className="space-y-5 text-sm">
    <div className="rounded-xl bg-brand-50 p-4">
      <h3 className="font-bold">{report.patient.fullName} · {report.patient.mrn}</h3>
      <p>{report.patient.age} years · {report.patient.gender} · {report.screening.status.replaceAll("_", " ")}</p>
      <p className="mt-2">Diabetes: {report.patient.knownDiabetic ?? "Unknown"} · Duration: {report.patient.diabetesDurationYears ?? "Not recorded"} years</p>
      {report.patient.clinicalHistory && <p className="mt-2 whitespace-pre-wrap">Clinical history: {report.patient.clinicalHistory}</p>}
    </div>
    <div className="grid sm:grid-cols-2 gap-4">
      <figure><figcaption className="font-semibold mb-2">Original retinal image</figcaption>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={`/api/backend/screenings/${id}/image`} alt="Original fundus capture" className="w-full rounded-xl bg-slate-950 max-h-80 object-contain" />
      </figure>
      <div><h4 className="font-semibold">Image quality assessment</h4>
        {report.quality ? <><p className="mt-2">{report.quality.accepted ? "Accepted" : "Rejected"} · {(Number(report.quality.score) * 100).toFixed(1)}%</p>
          <p>{report.quality.reasons.join("; ")}</p><p className="text-xs text-slate-500">Quality model: {report.quality.model_version}</p></>
          : <p className="mt-2 text-slate-500">Quality assessment pending</p>}
      </div>
    </div>
    <section className="rounded-2xl border border-brand-200 p-4">
      <h4 className="font-bold text-brand-800">AI result — decision support</h4>
      {report.ai ? <>
        <p className="mt-2 text-lg font-bold">{report.ai.severity} · {(Number(report.ai.confidence) * 100).toFixed(1)}% confidence</p>
        <p className="text-xs text-slate-500">Model {report.ai.model_version} · {new Date(report.ai.created_at).toLocaleString()}</p>
        <dl className="mt-3 space-y-1">{Object.entries(report.ai.probabilities).map(([name, probability]) =>
          <div key={name} className="flex justify-between gap-3"><dt>{name}</dt><dd>{(probability * 100).toFixed(1)}%</dd></div>)}</dl>
        {report.ai.findings.length > 0 && <p className="mt-3">{report.ai.findings.join("; ")}</p>}
        <h5 className="font-semibold mt-4">Explainability</h5>
        {overlayError ? <p className="text-slate-500">No explainability image was supplied by this model.</p> :
          /* eslint-disable-next-line @next/next/no-img-element */
          <img src={`/api/backend/screenings/${id}/image?kind=explainability`} alt="Model Grad-CAM++ explanation" onError={() => setOverlayError(true)} className="mt-2 max-h-72 rounded-xl" />}
      </> : <p className="mt-2 text-slate-500">No AI prediction is available yet.</p>}
    </section>
    <section className="rounded-2xl border p-4">
      <h4 className="font-bold">Doctor’s final assessment</h4>
      {report.review ? <div className="mt-2 space-y-1"><p>{report.review.decision.replaceAll("_", " ")}</p>
        <p>{report.review.final_assessment}</p><p>{report.review.reason} {report.review.comments}</p>
        <p className="text-xs text-slate-500">Doctor {report.review.doctor_id} · {new Date(report.review.created_at).toLocaleString()}</p></div>
        : <p className="mt-2 text-slate-500">Awaiting a doctor’s decision. The AI result is not a final diagnosis.</p>}
    </section>
    {reviewable && <form className="space-y-3" method="post" onSubmit={async e => {
      e.preventDefault(); const data = new FormData(e.currentTarget); setBusy(true); setError("");
      try {
        await apiClient(`/screenings/${id}/start-review`, { method: "POST" });
        await apiClient(`/screenings/${id}/reviews`, { method: "POST", idempotencyKey: crypto.randomUUID(),
          body: { decision, finalAssessment: data.get("finalAssessment") ?? "", comments: data.get("comments") ?? "",
                  reason: decision === "VERIFIED" ? null : data.get("reason") } });
        setReload(v => v + 1); onChanged?.();
      } catch (e) { setError(e instanceof Error ? e.message : "Could not save decision"); }
      finally { setBusy(false); }
    }}>
      <label className="block font-semibold">Doctor decision<select value={decision} onChange={e => setDecision(e.target.value)} className="block w-full border rounded-xl p-3 mt-1">
        <option value="VERIFIED">Verify report</option><option value="ADDITIONAL_ANALYSIS_REQUIRED">Needs additional analysis</option>
      </select></label>
      {decision === "VERIFIED" ? <label className="block">Final assessment<textarea name="finalAssessment" required maxLength={4000} className="block w-full rounded-xl border p-3 mt-1" /></label> :
        <label className="block">Reason<select name="reason" className="block w-full border rounded-xl p-3 mt-1">
          {["IMAGE_QUALITY", "AI_UNCERTAIN", "ADDITIONAL_IMAGE", "ADDITIONAL_ANALYSIS", "CLINICAL_DISAGREEMENT", "OTHER"].map(r => <option key={r} value={r}>{r.replaceAll("_", " ")}</option>)}
        </select></label>}
      <label className="block">Clinical comments<textarea name="comments" required={decision !== "VERIFIED"} maxLength={4000} className="block w-full rounded-xl border p-3 mt-1" /></label>
      <button disabled={busy} className="rounded-xl bg-brand-600 text-white px-5 py-3 disabled:opacity-50">{busy ? "Saving…" : "Save doctor decision"}</button>
    </form>}
    {canReview && report.screening.status === "VERIFIED" && <button disabled={busy} className="rounded-xl bg-brand-600 text-white p-3" onClick={async () => {
      setBusy(true); try { await apiClient(`/screenings/${id}/complete`, { method: "POST" }); setReload(v => v + 1); onChanged?.(); }
      catch (e) { setError(e instanceof Error ? e.message : "Could not finalize"); } finally { setBusy(false); }
    }}>Finalize report</button>}
    {["VERIFIED","COMPLETED"].includes(report.screening.status) && <Link href={`/reports/${id}`} className="block text-brand-700 font-semibold">Open printable final report</Link>}
    {error && <p role="alert" className="text-rose-700">{error}</p>}
    <details><summary className="cursor-pointer font-semibold">Screening timeline</summary><ol className="mt-2 space-y-2">{report.events.map((event, i) => <li key={i}>{event.status.replaceAll("_", " ")} · {new Date(event.created_at).toLocaleString()}</li>)}</ol></details>
  </div>;
}
