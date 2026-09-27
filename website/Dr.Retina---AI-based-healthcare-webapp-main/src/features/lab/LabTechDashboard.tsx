"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowRight,
  Camera,
  CheckCircle2,
  Clock,
  Eye,
  History,
  LayoutDashboard,
  Microscope,
  Plus,
  UserPlus,
  Users,
  Wifi,
} from "lucide-react";
import { StatCard } from "@/components/ui/Card";
import { SeverityBadge } from "@/components/ui/SeverityBadge";
import { EmptyState } from "@/components/shared/EmptyState";
import { QuickPatientModal } from "@/features/patients/QuickPatientModal";
import { ScreeningUploadModal } from "@/features/screenings/ScreeningUploadModal";
import { apiClient } from "@/lib/api/client";
import { isDemoMode } from "@/lib/env/env";
import { DEMO_LAB_STATS, DEMO_RECENT_SCREENINGS } from "@/features/demo/demoData";
import { ScreeningHistory } from "@/features/screenings/ScreeningHistory";
import { cn } from "@/lib/utils/cn";

export function LabTechDashboard({ orgName }: { orgName: string }) {
  const [isRegisterOpen, setIsRegisterOpen] = React.useState(false);
  const [isScreeningOpen, setIsScreeningOpen] = React.useState(false);
  const [recentScreenings, setRecentScreenings] = React.useState<typeof DEMO_RECENT_SCREENINGS>([]);
  const [stats, setStats] = React.useState<typeof DEMO_LAB_STATS | null>(null);
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [loadError, setLoadError] = React.useState("");
  const [isLoading, setIsLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      setIsLoading(true);
      try {
        if (isDemoMode()) {
          await new Promise((r) => setTimeout(r, 400));
          if (!cancelled) {
            setStats(DEMO_LAB_STATS);
            setRecentScreenings(DEMO_RECENT_SCREENINGS);
          }
          return;
        }
        const [s, sc] = await Promise.all([
          apiClient<{ data: typeof DEMO_LAB_STATS }>("/analytics/dashboard?role=lab_tech"),
          apiClient<{ data: typeof DEMO_RECENT_SCREENINGS }>("/screenings?limit=10"),
        ]);
        if (!cancelled) {
          setStats(s?.data ?? { screenedToday: 0, pendingAnalysis: 0, completedScreenings: 0, recentPatientsCount: 0 });
          setRecentScreenings(sc?.data ?? []);
        }
      } catch {
        if (!cancelled) setLoadError("Could not load screening activity. Please refresh.");
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  const navItems = [
    { id: "dashboard", label: "Dashboard", Icon: LayoutDashboard, href: "/lab" as const },
    { id: "register", label: "Register Patient", Icon: UserPlus, action: () => setIsRegisterOpen(true) },
    { id: "patients", label: "Patients", Icon: Users, href: "/lab/screenings" as const },
    { id: "screening", label: "New Screening", Icon: Camera, action: () => setIsScreeningOpen(true) },
    { id: "history", label: "Screening History", Icon: History, href: "/lab/screenings" as const },
  ];

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col md:flex-row">
      <aside className="w-full md:w-64 bg-white border-r border-slate-200/80 flex flex-col justify-between p-4 flex-shrink-0">
        <div>
          <div className="p-3.5 rounded-2xl bg-cyan-50/70 border border-cyan-200/80 mb-6">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl bg-cyan-700 text-white flex items-center justify-center font-bold text-xs shadow-sm">
                <Microscope className="w-5 h-5" aria-hidden="true" />
              </div>
              <div className="overflow-hidden">
                <h4 className="text-xs font-bold text-slate-900 truncate">Camp Technician</h4>
                <p className="text-[10px] text-cyan-700 font-medium truncate">{orgName || "Rural Camp Unit #1"}</p>
              </div>
            </div>
          </div>
          <nav className="space-y-1" aria-label="Lab technician">
            {navItems.map((item) => (
              "action" in item && item.action ? (
                <button
                  key={item.id}
                  onClick={item.action}
                  className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                >
                  <div className="flex items-center gap-3">
                    <item.Icon className="w-4 h-4" aria-hidden="true" />
                    <span>{item.label}</span>
                  </div>
                  <Plus className="w-3.5 h-3.5 opacity-60" aria-hidden="true" />
                </button>
              ) : (
                <Link
                  key={item.id}
                  href={(item as { href: string }).href}
                  className={cn("w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all", item.id === "dashboard" ? "bg-brand-600 text-white shadow-sm shadow-brand-600/20" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900")}
                >
                  <div className="flex items-center gap-3">
                    <item.Icon className="w-4 h-4" aria-hidden="true" />
                    <span>{item.label}</span>
                  </div>
                </Link>
              )
            ))}
          </nav>
        </div>
        <div className="pt-4 border-t border-slate-100 mt-6 space-y-2 text-xs">
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
            <div className="flex items-center justify-between text-slate-700 font-bold mb-1 text-[11px]">
              <span className="flex items-center gap-1.5">
                <Wifi className="w-3.5 h-3.5 text-brand-600" aria-hidden="true" />
                Camp Network
              </span>
              <span className="text-emerald-600 text-[10px]">Server-based processing</span>
            </div>
            <div className="flex items-center justify-between text-slate-500 text-[10px]">
              <span>Camera Hardware</span>
              <span className="font-semibold text-slate-700">Portable Non-Mydriatic</span>
            </div>
          </div>
        </div>
      </aside>

      <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">Lab Technician Workspace</h1>
              <span className="px-2.5 py-0.5 rounded-full bg-cyan-50 border border-cyan-200 text-cyan-800 text-xs font-bold">Rapid Camp Intake</span>
            </div>
            <p className="text-xs sm:text-sm text-slate-500 mt-1">High-throughput screening console engineered for field health camps and mobile eye vans.</p>
          </div>
          <div className="flex items-center gap-2 text-xs font-medium text-slate-500 bg-white px-3 py-1.5 rounded-xl border border-slate-200 shadow-sm">
            <Clock className="w-3.5 h-3.5 text-brand-600" aria-hidden="true" />
            <span>Active Camp Shift</span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6 mb-8">
          <button onClick={() => setIsRegisterOpen(true)} className="text-left p-6 rounded-3xl bg-gradient-to-br from-brand-600 via-brand-700 to-brand-800 text-white shadow-xl shadow-brand-600/20 hover:shadow-2xl hover:scale-[1.01] transition-all group relative overflow-hidden">
            <div className="absolute right-0 top-0 w-36 h-36 bg-white/10 rounded-full blur-2xl pointer-events-none transform translate-x-8 -translate-y-8" />
            <div className="flex items-start justify-between">
              <div>
                <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-white/20 text-white text-[11px] font-bold tracking-wider uppercase mb-3">Step 1 • Intake</span>
                <h3 className="text-2xl font-black tracking-tight">+ Register New Patient</h3>
                <p className="text-xs text-brand-100 mt-2 max-w-sm leading-relaxed">Fast demographic registration and diabetes duration recording for incoming camp attendees.</p>
              </div>
              <div className="w-14 h-14 rounded-2xl bg-white text-brand-700 flex items-center justify-center flex-shrink-0 shadow-lg group-hover:scale-110 transition-transform">
                <UserPlus className="w-7 h-7" aria-hidden="true" />
              </div>
            </div>
            <div className="mt-6 pt-4 border-t border-brand-500/50 flex items-center justify-between text-xs font-bold text-brand-100 group-hover:text-white">
              <span>Launch Intake Form</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" aria-hidden="true" />
            </div>
          </button>

          <button onClick={() => setIsScreeningOpen(true)} className="text-left p-6 rounded-3xl bg-gradient-to-br from-cyan-600 via-cyan-700 to-brand-700 text-white shadow-xl shadow-cyan-600/20 hover:shadow-2xl hover:scale-[1.01] transition-all group relative overflow-hidden">
            <div className="absolute right-0 top-0 w-36 h-36 bg-white/10 rounded-full blur-2xl pointer-events-none transform translate-x-8 -translate-y-8" />
            <div className="flex items-start justify-between">
              <div>
                <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-white/20 text-white text-[11px] font-bold tracking-wider uppercase mb-3">Step 2 • Fundus Capture</span>
                <h3 className="text-2xl font-black tracking-tight">Start New Screening</h3>
                <p className="text-xs text-cyan-100 mt-2 max-w-sm leading-relaxed">Capture fundus photography, execute instant AI quality checks, and compute ICDR severity.</p>
              </div>
              <div className="w-14 h-14 rounded-2xl bg-white text-cyan-700 flex items-center justify-center flex-shrink-0 shadow-lg group-hover:scale-110 transition-transform">
                <Camera className="w-7 h-7" aria-hidden="true" />
              </div>
            </div>
            <div className="mt-6 pt-4 border-t border-cyan-500/50 flex items-center justify-between text-xs font-bold text-cyan-100 group-hover:text-white">
              <span>Open Fundus Camera AI Pipeline</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" aria-hidden="true" />
            </div>
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard title="Screened Today" value={stats?.screenedToday?.toString() ?? "0"} subtitle="Camp daily throughput" icon={Eye} color="teal" isLoading={isLoading} />
          <StatCard title="Pending Analyses" value={stats?.pendingAnalysis?.toString() ?? "0"} subtitle="Processing in AI queue" icon={Clock} color="amber" isLoading={isLoading} />
          <StatCard title="Completed Screenings" value={stats?.completedScreenings?.toString() ?? "0"} subtitle="Sent to doctor triage" icon={CheckCircle2} color="emerald" isLoading={isLoading} />
          <StatCard title="Recent Patients" value={stats?.recentPatientsCount?.toString() ?? "0"} subtitle="Logged in camp shift" icon={Users} color="cyan" isLoading={isLoading} />
        </div>

        <div className="bg-white rounded-3xl border border-slate-200/80 shadow-card overflow-hidden">
          <div className="p-5 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Recent Camp Patients</h3>
              <p className="text-xs text-slate-500 mt-0.5">Real-time status of fundus captures during this screening camp</p>
            </div>
            <button onClick={() => setIsScreeningOpen(true)} className="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-brand-50 text-brand-700 border border-brand-200 hover:bg-brand-100 transition-all flex items-center gap-1">
              <Plus className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Screen Next Patient</span>
            </button>
          </div>
          {recentScreenings.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
                    <th className="py-3.5 px-5" scope="col">Patient Name</th>
                    <th className="py-3.5 px-4" scope="col">Patient MRN</th>
                    <th className="py-3.5 px-4" scope="col">Eye Lateral</th>
                    <th className="py-3.5 px-4" scope="col">AI Screening Severity</th>
                    <th className="py-3.5 px-4" scope="col">Time</th>
                    <th className="py-3.5 px-5 text-right" scope="col">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {recentScreenings.map((sc) => (
                    <tr key={sc.id} className="hover:bg-slate-50">
                      <td className="py-3.5 px-5 font-bold text-slate-800">{sc.patientName}</td>
                      <td className="py-3.5 px-4 font-mono text-slate-600">{sc.mrn}</td>
                      <td className="py-3.5 px-4 font-semibold text-slate-700">{sc.eye}</td>
                      <td className="py-3.5 px-4"><SeverityBadge severity={sc.severity} size="sm" /></td>
                      <td className="py-3.5 px-4 text-slate-500">{sc.time}</td>
                      <td className="py-3.5 px-5 text-right">
                        <span className="px-2.5 py-1 rounded-full bg-brand-50 text-brand-700 border border-brand-200 font-semibold text-[11px]">{sc.status}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-8">
              <EmptyState type="screenings" title="No patients screened today in current camp" description="Click '+ Register New Patient' or 'Start New Screening' to process your first camp attendee." actionLabel="+ Register Patient" onAction={() => setIsRegisterOpen(true)} />
            </div>
          )}
        </div>

        {loadError && <p role="alert" className="text-rose-700">{loadError}</p>}
        <ScreeningHistory technician />
        <QuickPatientModal
          open={isRegisterOpen}
          onClose={() => setIsRegisterOpen(false)}
          onPatientRegistered={() => { setRefreshKey(v => v + 1); setTimeout(() => setIsScreeningOpen(true), 400); }}
          campDefault={orgName}
        />
        <ScreeningUploadModal open={isScreeningOpen} onClose={() => { setIsScreeningOpen(false); setRefreshKey(v => v + 1); }} />
      </main>
    </div>
  );
}
