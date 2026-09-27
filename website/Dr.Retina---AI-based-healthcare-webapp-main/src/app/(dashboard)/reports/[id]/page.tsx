import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import { requireSession } from "@/lib/auth/guards";
import { PrintButton } from "@/components/shared/PrintButton";
import type { ClinicalReport } from "@/features/screenings/types";
export default async function FinalReport({ params }: { params: Promise<{ id: string }> }) {
  await requireSession();
  const { id } = await params;
  if (!/^[0-9a-f-]{36}$/i.test(id)) notFound();
  const report = await apiServer<ClinicalReport>(`/screenings/${id}`);
  if (!report.review || !["VERIFIED","COMPLETED"].includes(report.screening.status)) notFound();
  return <article className="max-w-3xl mx-auto my-10 rounded-3xl bg-white border p-8 space-y-6 print:border-0 print:my-0">
    <header><p className="text-brand-700 font-bold">Dr.Retina · Clinical screening report</p>
      <h1 className="text-2xl font-bold mt-3">{report.patient.fullName}</h1>
      <p>{report.patient.mrn} · {report.patient.age} years · {report.patient.gender}</p>
      <p className="text-xs mt-2">Screening: {id} · {report.screening.status}</p></header>
    <section><h2 className="font-bold text-lg">Doctor’s assessment</h2><p className="mt-2 whitespace-pre-wrap">{report.review.final_assessment}</p>
      <p className="whitespace-pre-wrap">{report.review.comments}</p>
      <p className="text-xs text-slate-600 mt-3">Verified by {report.review.doctor_id} on {new Date(report.review.created_at).toLocaleString()}</p></section>
    <section className="border-t pt-5"><h2 className="font-bold">Original AI result — decision support</h2>
      <p>{report.ai?.severity} · {report.ai ? (Number(report.ai.confidence)*100).toFixed(1) : "—"}% confidence</p>
      <p className="text-xs">Model: {report.ai?.model_version} · Processed: {report.ai?.created_at}</p>
      <p className="mt-2 text-sm">Image quality: {report.quality?.accepted ? "Accepted" : "Not accepted"} · {Number(report.quality?.score ?? 0)*100}%</p></section>
    <p className="text-sm text-slate-600">The AI prediction is preserved separately from the doctor’s assessment. Screening results must be interpreted in clinical context.</p>
    <PrintButton />
  </article>;
}
