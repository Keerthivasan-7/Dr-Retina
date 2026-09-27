/**
 * DEMO_MODE datasets. Explicitly isolated per master prompt §30.
 * Production (DEMO_MODE=false) NEVER touches this module's data —
 * components fall back to real API results / clean empty states instead.
 */
import type { AuditEvent, Camp, DashboardStats, Patient } from "@/types/domain";

export const DEMO_ADMIN_STATS: DashboardStats & {
  screeningVolume: number[];
  severityDistribution: Record<string, number>;
  recentActivity: AuditEvent[];
} = {
  totalPatients: 1420,
  totalScreenings: 1890,
  highPriorityCases: 148,
  activeDoctors: 12,
  activeLabTechnicians: 28,
  activeCamps: 4,
  screeningVolume: [120, 180, 240, 310, 420, 580],
  severityDistribution: {
    noDR: 980,
    mildNPDR: 420,
    moderateNPDR: 342,
    severeNPDR: 104,
    proliferativeDR: 44,
  },
  recentActivity: [
    { id: "1", time: "10 mins ago", action: "Camp Unit #4 (Rural District North) started screening session", user: "Technician Lead" },
    { id: "2", time: "25 mins ago", action: "Dr. Anita Desai verified 14 high-priority screening reports", user: "Dr. Anita Desai" },
    { id: "3", time: "1 hour ago", action: "AI Model v2.4 recalibrated for non-mydriatic camera profiles", user: "System Service" },
  ],
};

export const DEMO_CAMPS: Camp[] = [
  { id: "c1", name: "North District Community Camp #1", location: "Primary Health Centre, Bhor", activeWorkers: 6, screenedCount: 142, status: "Active" },
  { id: "c2", name: "Mobile Retinal Screening Van #2", location: "Sector 7 Rural Outreach", activeWorkers: 4, screenedCount: 88, status: "Active" },
  { id: "c3", name: "Taluka Diabetic Clinic Camp", location: "Civil Hospital Annex", activeWorkers: 8, screenedCount: 210, status: "Active" },
];

export interface DemoDoctorPatient extends Patient {
  screeningDate: string;
  campLocation: string;
  severity: string;
  priorityStatus: string;
  dmeRisk: string;
  aiConfidence: number;
  findings: string[];
}

export const DEMO_DOCTOR_PATIENTS: DemoDoctorPatient[] = [
  {
    id: "P-1048",
    mrn: "MRN-2026-0891",
    fullName: "Kavita Sundaram",
    age: 58,
    gender: "Female",
    screeningDate: "2026-08-27 (Today)",
    campLocation: "District Rural Camp #4",
    severity: "Proliferative DR",
    priorityStatus: "Immediate Review",
    dmeRisk: "High DME Risk",
    aiConfidence: 99.1,
    findings: ["Neovascularization at Disc (NVD)", "Preretinal Hemorrhage in Upper Arcade"],
  },
  {
    id: "P-1042",
    mrn: "MRN-2026-0842",
    fullName: "Rajesh K. Verma",
    age: 64,
    gender: "Male",
    screeningDate: "2026-08-27 (Today)",
    campLocation: "Civil Hospital Camp",
    severity: "Severe NPDR",
    priorityStatus: "High Priority",
    dmeRisk: "Moderate DME",
    aiConfidence: 97.8,
    findings: ["Venous Beading in 2 Quadrants", "Multiple Intraretinal Hemorrhages"],
  },
  {
    id: "P-1039",
    mrn: "MRN-2026-0810",
    fullName: "Meenakshi Iyer",
    age: 51,
    gender: "Female",
    screeningDate: "2026-08-26",
    campLocation: "Taluka Primary Clinic",
    severity: "Moderate NPDR",
    priorityStatus: "Moderate",
    dmeRisk: "No DME",
    aiConfidence: 96.5,
    findings: ["Microaneurysms (<10)", "Hard Exudates outside Fovea"],
  },
];

export const DEMO_LAB_STATS = {
  screenedToday: 38,
  pendingAnalysis: 2,
  completedScreenings: 36,
  recentPatientsCount: 38,
};

export const DEMO_RECENT_SCREENINGS = [
  { id: "SC-809", patientName: "Devendra Patel", mrn: "MRN-2026-0902", time: "8 mins ago", eye: "OD (Right)", severity: "Mild NPDR", status: "Completed" },
  { id: "SC-808", patientName: "Sunita Rao", mrn: "MRN-2026-0901", time: "22 mins ago", eye: "OU (Both)", severity: "Severe NPDR", status: "Queued to Doctor" },
  { id: "SC-807", patientName: "Govind Swamy", mrn: "MRN-2026-0900", time: "45 mins ago", eye: "OS (Left)", severity: "No DR Detected", status: "Completed" },
];
