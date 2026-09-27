"use client";

import { apiClient } from "@/lib/api/client";
import type { Patient } from "@/types/domain";
import type { PatientRegistration } from "@/lib/validation/schemas";

export async function fetchPatients(params: Record<string, string> = {}): Promise<Patient[]> {
  const query = new URLSearchParams(params).toString();
  const res = await apiClient<{ data: Patient[] }>(`/patients${query ? `?${query}` : ""}`);
  return res.data ?? [];
}

export async function registerPatient(payload: PatientRegistration): Promise<{ data: Patient }> {
  return apiClient<{ data: Patient }>("/patients", {
    method: "POST",
    body: payload,
    idempotencyKey: crypto.randomUUID(),
  });
}
