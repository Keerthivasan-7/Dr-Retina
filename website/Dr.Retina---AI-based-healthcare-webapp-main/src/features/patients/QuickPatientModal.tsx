"use client";

import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { CheckCircle2, UserPlus } from "lucide-react";
import { Dialog, DialogHeader } from "@/components/ui/Dialog";
import { PatientRegistrationSchema, type PatientRegistration } from "@/lib/validation/schemas";
import { registerPatient } from "@/features/patients/api";
import { isDemoMode } from "@/lib/env/env";
import { z } from "zod";

type PatientFormInput = z.input<typeof PatientRegistrationSchema>;

export function QuickPatientModal({
  open,
  onClose,
  onPatientRegistered,
  campDefault = "Camp Unit #1",
}: {
  open: boolean;
  onClose: () => void;
  onPatientRegistered?: (p: PatientRegistration) => void;
  campDefault?: string;
}) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<PatientFormInput>({
    resolver: zodResolver(PatientRegistrationSchema),
    defaultValues: {
      fullName: "",
      age: 0,
      gender: "Female",
      contactNumber: "",
      diabetesDurationYears: 0,
      knownDiabetic: "Unknown",
      campLocation: campDefault,
    },
  });
  const [success, setSuccess] = React.useState<string | null>(null);
  const [serverError, setServerError] = React.useState<string | null>(null);

  const onSubmit = async (raw: PatientFormInput) => {
    setServerError(null);
    const data = PatientRegistrationSchema.parse(raw);
    try {
      if (isDemoMode()) {
        // DEMO_MODE: simulate latency without touching the API.
        await new Promise((r) => setTimeout(r, 600));
      } else {
        await registerPatient(data);
      }
      setSuccess("Patient registered successfully! You can now proceed to fundus screening.");
      setTimeout(() => {
        setSuccess(null);
        reset();
        onPatientRegistered?.(data);
        onClose();
      }, 1400);
    } catch {
      setServerError("Registration failed. Please try again.");
    }
  };

  return (
    <Dialog open={open} onClose={onClose} labelledBy="qp-title" maxWidth="max-w-lg">
      <DialogHeader id="qp-title" title="Register New Patient" subtitle="Rapid camp intake form" onClose={onClose} />
      {success ? (
        <div className="p-8 text-center flex flex-col items-center" role="status">
          <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mb-3">
            <CheckCircle2 className="w-6 h-6" aria-hidden="true" />
          </div>
          <h4 className="font-bold text-slate-800 text-sm">{success}</h4>
        </div>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} method="post" className="p-6 space-y-4 max-h-[75vh] overflow-y-auto" noValidate>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="sm:col-span-2">
              <label htmlFor="qp-name" className="block text-xs font-semibold text-slate-700 mb-1">Patient Full Name *</label>
              <input id="qp-name" type="text" placeholder="e.g., Ananya Sharma" {...register("fullName")} className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-xs focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none" />
              {errors.fullName && <p role="alert" className="text-xs text-rose-600 mt-1">{errors.fullName.message}</p>}
            </div>
            <div>
              <label htmlFor="qp-age" className="block text-xs font-semibold text-slate-700 mb-1">Age (Years) *</label>
              <input id="qp-age" type="number" min={0} max={120} placeholder="e.g., 52" {...register("age")} className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-xs focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none" />
              {errors.age && <p role="alert" className="text-xs text-rose-600 mt-1">{errors.age.message}</p>}
            </div>
            <div>
              <label htmlFor="qp-gender" className="block text-xs font-semibold text-slate-700 mb-1">Gender</label>
              <select id="qp-gender" {...register("gender")} className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-xs focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none bg-white">
                <option value="Female">Female</option>
                <option value="Male">Male</option>
                <option value="Other">Other</option>
              </select>
            </div>
            <div>
              <label htmlFor="qp-contact" className="block text-xs font-semibold text-slate-700 mb-1">Contact Phone</label>
              <input id="qp-contact" type="tel" placeholder="e.g., +91 98765 43210" {...register("contactNumber")} className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-xs focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none" />
            </div>
            <div>
              <label htmlFor="qp-diabetes" className="block text-xs font-semibold text-slate-700 mb-1">Known Diabetes (Years)</label>
              <input id="qp-diabetes" type="number" min={0} placeholder="e.g., 8" {...register("diabetesDurationYears")} className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-xs focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none" />
            </div>
            <label className="block text-xs font-semibold text-slate-700">Diabetes status
              <select {...register("knownDiabetic")} className="block w-full mt-1 border rounded-xl p-3">
                <option>Unknown</option><option>Yes</option><option>No</option>
              </select>
            </label>
            <label className="block text-xs font-semibold text-slate-700">Address (optional)
              <input {...register("address")} maxLength={500} className="block w-full mt-1 border rounded-xl p-3" />
            </label>
            <label className="sm:col-span-2 block text-xs font-semibold text-slate-700">Relevant clinical history (optional)
              <textarea {...register("clinicalHistory")} maxLength={4000} rows={2} className="block w-full mt-1 border rounded-xl p-3" />
            </label>
          </div>
          {serverError && <p role="alert" className="text-xs text-rose-600">{serverError}</p>}
          <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-3">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-xl text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors">Cancel</button>
            <button type="submit" disabled={isSubmitting} className="px-5 py-2.5 rounded-xl text-xs font-semibold text-white bg-brand-600 hover:bg-brand-700 shadow-md shadow-brand-600/20 transition-all inline-flex items-center gap-1.5 disabled:opacity-60">
              <UserPlus className="w-3.5 h-3.5" aria-hidden="true" />
              {isSubmitting ? "Saving..." : "Register Patient"}
            </button>
          </div>
        </form>
      )}
    </Dialog>
  );
}
