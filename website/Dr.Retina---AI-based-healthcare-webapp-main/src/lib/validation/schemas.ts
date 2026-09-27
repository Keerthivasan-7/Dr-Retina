import { z } from "zod";

export const PatientRegistrationSchema = z.object({
  fullName: z.string().trim().min(2, "Full name is required").max(120),
  age: z.coerce.number().int().min(0).max(120, "Age must be 0–120"),
  gender: z.enum(["Female", "Male", "Other"]),
  contactNumber: z.string().trim().max(32).optional().default(""),
  diabetesDurationYears: z.coerce.number().min(0).max(100).optional().default(0),
  knownDiabetic: z.enum(["Yes", "No", "Unknown"]).default("Unknown"),
  campLocation: z.string().trim().max(200).optional().default(""),
  address: z.string().trim().max(500).optional().default(""),
  clinicalHistory: z.string().trim().max(4000).optional().default(""),
});

export type PatientRegistration = z.infer<typeof PatientRegistrationSchema>;

export const ScreeningRequestSchema = z.object({
  patientId: z.string().trim().min(1, "Patient ID is required").max(64),
  eye: z.enum(["OD", "OS", "OU"]),
});

export type ScreeningRequest = z.infer<typeof ScreeningRequestSchema>;

export const LoginSchema = z.object({
  email: z.string().trim().min(3, "Email or username is required").max(254),
  password: z.string().min(1, "Password is required").max(256),
  role: z.enum(["ORG_ADMIN", "DOCTOR", "LAB_TECHNICIAN"]),
  orgId: z.string().trim(),
});

export type LoginInput = z.infer<typeof LoginSchema>;

export const DoctorReviewSchema = z.object({
  screeningId: z.string().trim().min(1),
  verdict: z.enum(["CONFIRMED", "AMENDED", "REJECTED"]),
  notes: z.string().trim().max(4000).optional().default(""),
});

export type DoctorReview = z.infer<typeof DoctorReviewSchema>;
