"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  ArrowLeft,
  Building2,
  CheckCircle2,
  Eye,
  EyeOff,
  KeyRound,
  LayoutDashboard,
  Lock,
  Mail,
  Microscope,
  ShieldCheck,
  Stethoscope,
} from "lucide-react";
import Link from "next/link";
import { loginAction } from "@/features/auth/actions";
import { LoginSchema, type LoginInput } from "@/lib/validation/schemas";
import { cn } from "@/lib/utils/cn";

const ROLES = [
  { id: "DOCTOR", label: "Doctor", subtitle: "Ophthalmologist / Reviewer", Icon: Stethoscope, description: "Review high-priority AI detections, verify clinical reports, and manage follow-ups." },
  { id: "LAB_TECHNICIAN", label: "Lab Technician", subtitle: "Field Screener / Camp Worker", Icon: Microscope, description: "Rapid patient intake, portable fundus camera upload, and AI triage at rural camps." },
  { id: "ORG_ADMIN", label: "Administrator", subtitle: "System & Camp Manager", Icon: LayoutDashboard, description: "Manage healthcare workers, screening camps, organization analytics, and audit logs." },
] as const;

export function LoginForm() {
  const searchParams = useSearchParams();
  const orgId = searchParams.get("orgId") ?? "";
  const orgName = searchParams.get("orgName") ?? "Selected Healthcare Org";
  const linkError = searchParams.get("error");
  const [serverError, setServerError] = React.useState<string | null>(
    linkError === "invalid_link" ? "This link has expired or was already used. Request a new verification or recovery email." :
    linkError === "logout_failed" ? "Sign-out could not be completed. Please try again before leaving this device." :
    linkError === "session_required" ? "Sign in or open a valid recovery link to change your password." : null);

  const {
    register,
    handleSubmit,
    control,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<LoginInput>({
    resolver: zodResolver(LoginSchema),
    defaultValues: { email: "", password: "", role: "DOCTOR", orgId },
  });

  const role = useWatch({ control, name: "role" });

  React.useEffect(() => {
    setValue("orgId", orgId);
  }, [orgId, setValue]);

  const onSubmit = async (data: LoginInput) => {
    setServerError(null);
    const fd = new FormData();
    fd.set("email", data.email);
    fd.set("password", data.password);
    fd.set("role", data.role);
    fd.set("orgId", data.orgId || orgId);
    fd.set("orgName", orgName);
    const result = await loginAction(fd);
    if (result && !result.ok) setServerError(result.error);
  };

  return (
    <div className="min-h-[calc(100vh-64px)] flex items-center justify-center p-4 sm:p-6 bg-gradient-to-br from-brand-50/60 via-slate-50 to-cyan-50/40">
      <div className="w-full max-w-xl">
        <div className="flex items-center justify-between mb-4 text-xs font-semibold">
          <Link href="/select-org" className="inline-flex items-center gap-1.5 text-slate-500 hover:text-brand-700 transition-colors">
            <ArrowLeft className="w-4 h-4" aria-hidden="true" />
            <span>Change Organization</span>
          </Link>
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white border border-brand-200 text-brand-800 shadow-sm">
            <Building2 className="w-3.5 h-3.5 text-brand-600" aria-hidden="true" />
            <span className="truncate max-w-[200px]">{orgName}</span>
          </div>
        </div>

        <div className="bg-white rounded-3xl border border-slate-200/90 shadow-card p-6 sm:p-8">
          <div className="text-center mb-6">
            <h2 className="text-2xl font-extrabold text-slate-900 tracking-tight">Sign In to Dr.Retina</h2>
            <p className="text-xs sm:text-sm text-slate-500 mt-1">Sign in with your authorized email. Your account determines your role and organization.</p>
          </div>

          <div className="mb-6">
            <span id="role-label" className="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-2">Portal overview</span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5" role="radiogroup" aria-labelledby="role-label">
              {ROLES.map((r) => {
                const isSelected = role === r.id;
                return (
                  <button
                    key={r.id}
                    type="button"
                    role="radio"
                    aria-checked={isSelected}
                    onClick={() => setValue("role", r.id)}
                    className={cn("p-3 rounded-2xl border text-left transition-all relative flex flex-col justify-between", isSelected ? "bg-brand-50/90 border-brand-500 ring-2 ring-brand-400/50 shadow-sm" : "bg-slate-50/80 border-slate-200 hover:bg-slate-50 hover:border-slate-300")}
                  >
                    <div className="flex items-center justify-between">
                      <div className={cn("w-8 h-8 rounded-xl flex items-center justify-center", isSelected ? "bg-brand-600 text-white" : "bg-slate-200 text-slate-600")}>
                        <r.Icon className="w-4 h-4" aria-hidden="true" />
                      </div>
                      {isSelected && <CheckCircle2 className="w-4 h-4 text-brand-600" aria-hidden="true" />}
                    </div>
                    <div className="mt-2.5">
                      <h4 className="text-xs font-bold text-slate-900">{r.label}</h4>
                      <p className="text-[10px] text-slate-500 leading-tight mt-0.5">{r.subtitle}</p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="mb-6 p-3 rounded-xl bg-slate-50 border border-slate-200/80 text-[11px] text-slate-600 flex items-start gap-2">
            <ShieldCheck className="w-4 h-4 text-brand-600 flex-shrink-0 mt-0.5" aria-hidden="true" />
            <span>{ROLES.find((r) => r.id === role)?.description}</span>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} method="post" className="space-y-4" noValidate>
            <div>
              <label htmlFor="email" className="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">Official Email</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" aria-hidden="true" />
                <input
                  id="email"
                  type="text"
                  autoComplete="username"
                  placeholder={role === "ORG_ADMIN" ? "admin@hospital.org" : role === "DOCTOR" ? "dr.sharma@hospital.org" : "technician.camp1@hospital.org"}
                  {...register("email")}
                  aria-invalid={!!errors.email}
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 text-xs sm:text-sm font-medium text-slate-800 placeholder:text-slate-400 focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none transition-all"
                />
              </div>
              {errors.email && <p role="alert" className="text-xs text-rose-600 mt-1">{errors.email.message}</p>}
            </div>

            <PasswordField register={register} error={errors.password?.message} />

            <button type="submit" disabled={isSubmitting} className="w-full py-3.5 rounded-full text-sm font-bold text-white bg-brand-600 hover:bg-brand-700 active:bg-brand-800 shadow-md shadow-brand-600/25 transition-all flex items-center justify-center gap-2 disabled:opacity-60">
              <KeyRound className="w-4 h-4" aria-hidden="true" />
              <span>{isSubmitting ? "Authenticating..." : "Sign In"}</span>
            </button>
            {serverError && <p role="alert" className="text-xs text-rose-600 text-center">{serverError}</p>}
            {errors.orgId && <p role="alert" className="text-xs text-rose-600 text-center">Please select an organization first.</p>}
          </form>
        </div>
        <p className="text-center text-[11px] text-slate-400 mt-4 leading-relaxed">Accessing authorized ophthalmic healthcare portal. Clinical access is restricted to authorized organization members.</p>
      </div>
    </div>
  );
}

function PasswordField({ register, error }: { register: ReturnType<typeof useForm<LoginInput>>["register"]; error?: string }) {
  const [show, setShow] = React.useState(false);
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <label htmlFor="password" className="block text-xs font-semibold uppercase tracking-wider text-slate-600">Password</label>
        <Link href="/forgot-password" className="text-xs text-brand-600 font-semibold">Forgot password?</Link>
      </div>
      <div className="relative">
        <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" aria-hidden="true" />
        <input
          id="password"
          type={show ? "text" : "password"}
          autoComplete="current-password"
          placeholder="Enter security password"
          {...register("password")}
          aria-invalid={!!error}
          className="w-full pl-10 pr-10 py-2.5 rounded-xl border border-slate-200 text-xs sm:text-sm font-medium text-slate-800 placeholder:text-slate-400 focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none transition-all"
        />
        <button type="button" onClick={() => setShow(!show)} aria-label={show ? "Hide password" : "Show password"} className="p-1 text-slate-400 hover:text-slate-600 absolute right-3 top-1/2 -translate-y-1/2">
          {show ? <EyeOff className="w-4 h-4" aria-hidden="true" /> : <Eye className="w-4 h-4" aria-hidden="true" />}
        </button>
      </div>
      {error && <p role="alert" className="text-xs text-rose-600 mt-1">{error}</p>}
    </div>
  );
}
