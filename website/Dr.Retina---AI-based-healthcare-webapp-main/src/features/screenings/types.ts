export interface ClinicalReport {
  screening: { id: string; patient_id: string; status: string; assigned_doctor_id: string | null; assignment_status: string };
  patient: { id: string; fullName: string; mrn: string; age: number; gender: string; knownDiabetic?: string; diabetesDurationYears?: number; clinicalHistory?: string };
  quality: { score: number; accepted: boolean; reasons: string[]; model_version: string } | null;
  ai: { severity: string; confidence: number; probabilities: Record<string, number>; model_version: string; created_at: string; findings: string[] } | null;
  review: { doctor_id: string; decision: string; final_assessment: string; comments: string; reason: string; created_at: string } | null;
  events: { status: string; created_at: string }[];
}
