"use client";
import { apiClient } from "@/lib/api/client";
import type { ScreeningResult } from "@/types/domain";
export interface ScreeningJob {
  jobId: string; screeningId: string;
  status: "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";
  screeningStatus?: string; errorCode?: string;
}
export async function requestScreeningAnalysis(payload: { patientId: string; eye: "OD" | "OS"; image: File; parentScreeningId?: string }, idempotencyKey: string): Promise<ScreeningJob> {
  const form = new FormData();
  form.append("patientId",payload.patientId); form.append("eye",payload.eye); form.append("image",payload.image);
  if (payload.parentScreeningId) form.append("parentScreeningId",payload.parentScreeningId);
  return apiClient<ScreeningJob>("/screenings/analyze",{ method:"POST",body:form,timeoutMs:65000,idempotencyKey });
}
export async function fetchScreeningStatus(jobId:string):Promise<ScreeningJob> {
  return apiClient<ScreeningJob>(`/screenings/jobs/${jobId}`);
}
export async function fetchScreenings(params:Record<string,string>={}):Promise<ScreeningResult[]> {
  return (await apiClient<{data:ScreeningResult[]}>(`/screenings?${new URLSearchParams(params)}`)).data;
}
