/** Domain types shared across features. Mirrors the FastAPI OpenAPI contract. */

export interface Organization {
  id: string;
  name: string;
  type: string;
  location: string;
}

export type Role = "ORG_ADMIN" | "DOCTOR" | "LAB_TECHNICIAN";

export interface Patient {
  id: string;
  mrn: string;
  fullName: string;
  age: number;
  gender: string;
  campLocation?: string;
  severity?: string;
  priorityStatus?: string;
  screeningDate?: string;
}

export type ScreeningStatus = "PATIENT_REGISTERED" | "IMAGE_UPLOADED" | "QUALITY_CHECKING" |
  "QUALITY_REJECTED" | "READY_FOR_ANALYSIS" | "AI_PROCESSING" | "REPORT_READY" |
  "SENT_TO_DOCTOR" | "DOCTOR_REVIEWING" | "VERIFIED" | "ADDITIONAL_ANALYSIS_REQUIRED" | "COMPLETED";

export interface ScreeningResult {
  id: string;
  patientId: string;
  patientName?: string;
  mrn?: string;
  eye: "OD" | "OS" | "OU";
  /** AI-generated classification. Never presented as final diagnosis. */
  aiSeverity: string | null;
  aiConfidence: number | null;
  status: ScreeningStatus;
  /** Set only after human review — stored separately from the AI prediction. */
  reviewerVerdict?: "VERIFIED" | "ADDITIONAL_ANALYSIS_REQUIRED" | null;
  createdAt: string;
}

export interface DashboardStats {
  totalPatients: number;
  totalScreenings: number;
  highPriorityCases: number;
  moderatePriorityCases?: number;
  screenedToday?: number;
  pendingAnalysis?: number;
  completedScreenings?: number;
  activeDoctors?: number;
  activeLabTechnicians?: number;
  activeCamps?: number;
}

export interface Camp {
  id: string;
  name: string;
  location: string;
  activeWorkers: number;
  screenedCount: number;
  status: string;
}

export interface AuditEvent {
  id: string;
  time: string;
  action: string;
  user: string;
}
