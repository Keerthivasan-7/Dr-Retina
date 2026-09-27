"use client";

import * as React from "react";
import Link from "next/link";
import {
  Activity,
  BarChart3,
  Building2,
  Clock,
  Download,
  Eye,
  FileText,
  LayoutDashboard,
  Microscope,
  Plus,
  Settings,
  ShieldAlert,
  Stethoscope,
  Tent,
  UserCheck,
  Users,
} from "lucide-react";
import { StatCard } from "@/components/ui/Card";
import { ChartSkeleton } from "@/components/ui/Feedback";
import { EmptyState } from "@/components/shared/EmptyState";
import { apiClient } from "@/lib/api/client";
import { isDemoMode } from "@/lib/env/env";
import { DEMO_ADMIN_STATS, DEMO_CAMPS } from "@/features/demo/demoData";
import type { Camp, DashboardStats } from "@/types/domain";
import { UsersPanel } from "./UsersPanel";
import { OrganizationSettings } from "@/features/organizations/OrganizationSettings";
import { ScreeningHistory } from "@/features/screenings/ScreeningHistory";
import { PatientDirectory } from "@/features/patients/PatientDirectory";
import { cn } from "@/lib/utils/cn";

const NAV = [
  { id: "dashboard", label: "Dashboard", Icon: LayoutDashboard, href: "/admin" },
  { id: "users", label: "User Management", Icon: Users, href: "/admin/users" },
  { id: "workers", label: "Healthcare Workers", Icon: UserCheck, href: "/admin/users" },
  { id: "camps", label: "Screening Camps", Icon: Tent, href: "/admin/organizations" },
  { id: "patients", label: "Patients", Icon: FileText, href: "/admin/patients" },
  { id: "analytics", label: "Analytics & Reports", Icon: BarChart3, href: "/admin/analytics" },
  { id: "settings", label: "Settings", Icon: Settings, href: "/admin" },
] as const;

type Section = (typeof NAV)[number]["id"];

interface AdminStats extends DashboardStats {
  screeningVolume?: number[];
  severityDistribution?: Record<string, number>;
  recentActivity?: Array<{ id: string; time: string; action: string; user: string }>;
}

export function AdminDashboard({ orgName, section = "dashboard" }: { orgName: string; section?: Section }) {
  const [activeNav, setActiveNav] = React.useState<Section>(section);
  const [stats, setStats] = React.useState<AdminStats | null>(null);
  const [camps, setCamps] = React.useState<Camp[]>([]);
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
            setStats(DEMO_ADMIN_STATS);
            setCamps(DEMO_CAMPS);
          }
          return;
        }
        const [s, c] = await Promise.all([
          apiClient<{ data: AdminStats }>("/analytics/dashboard?role=admin"),
          apiClient<{ data: Camp[] }>("/camps"),
        ]);
        if (!cancelled) {
          setStats(s?.data ?? {
            totalPatients: 0, totalScreenings: 0, highPriorityCases: 0,
            activeDoctors: 0, activeLabTechnicians: 0, activeCamps: 0,
            recentActivity: [], screeningVolume: [],
            severityDistribution: { noDR: 0, mildNPDR: 0, moderateNPDR: 0, severeNPDR: 0, proliferativeDR: 0 },
          });
          setCamps(c?.data ?? []);
        }
      } catch {
        if (!cancelled) setLoadError("Could not load organization activity. Please refresh.");
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col md:flex-row">
      <aside className="w-full md:w-64 bg-white border-r border-slate-200/80 flex flex-col justify-between p-4 flex-shrink-0">
        <div>
          <div className="p-3.5 rounded-2xl bg-brand-50/70 border border-brand-200/80 mb-6">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-brand-600 text-white flex items-center justify-center font-bold text-xs">
                <Building2 className="w-4 h-4" aria-hidden="true" />
              </div>
              <div className="overflow-hidden">
                <h4 className="text-xs font-bold text-slate-900 truncate">{orgName || "Main Hospital Org"}</h4>
                <p className="text-[10px] text-brand-700 font-medium">Administrator Console</p>
              </div>
            </div>
          </div>
          <nav className="space-y-1" aria-label="Admin">
            {NAV.map((item) => {
              const isActive = activeNav === item.id;
              return (
                <Link
                  key={item.id}
                  href={item.href}
                  onClick={() => setActiveNav(item.id)}
                  aria-current={isActive ? "page" : undefined}
                  className={cn("w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all", isActive ? "bg-brand-600 text-white shadow-sm shadow-brand-600/20" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900")}
                >
                  <item.Icon className="w-4 h-4" aria-hidden="true" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="pt-4 border-t border-slate-100 mt-6">
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[11px] font-bold text-slate-700">AI Screening Server</span>
              <span className="flex items-center gap-1 text-[10px] font-semibold text-emerald-600">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Check job status
              </span>
            </div>
            <p className="text-[10px] text-slate-400">Model version is recorded on each AI result</p>
          </div>
        </div>
      </aside>

      <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">Administrator Dashboard</h1>
              <span className="px-2.5 py-0.5 rounded-full bg-brand-50 border border-brand-200 text-brand-800 text-xs font-bold">Live Overview</span>
            </div>
            <p className="text-xs sm:text-sm text-slate-500 mt-1">System monitoring, screening camp oversight, and healthcare worker management.</p>
          </div>
          <div className="flex items-center gap-2.5">
            <button onClick={() => document.getElementById("team-management")?.scrollIntoView({ behavior: "smooth" })} className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-all flex items-center gap-1.5 shadow-sm">
              <Plus className="w-3.5 h-3.5 text-brand-600" aria-hidden="true" />
              <span>Add Healthcare Worker</span>
            </button>
            <button onClick={() => document.getElementById("organization-settings")?.scrollIntoView()} className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-brand-600 hover:bg-brand-700 text-white shadow-sm shadow-brand-600/20 transition-all flex items-center gap-1.5">
              <Tent className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Organization Settings</span>
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
          <StatCard title="Total Patients" value={stats?.totalPatients?.toLocaleString() ?? "0"} subtitle="Registered in system" icon={Users} color="teal" isLoading={isLoading} />
          <StatCard title="Total Screenings" value={stats?.totalScreenings?.toLocaleString() ?? "0"} subtitle="Fundus scans analyzed" icon={Eye} color="cyan" isLoading={isLoading} />
          <StatCard title="High-Priority Cases" value={stats?.highPriorityCases?.toLocaleString() ?? "0"} subtitle="Urgent clinical review" icon={ShieldAlert} color="rose" isLoading={isLoading} />
          <StatCard title="Active Doctors" value={stats?.activeDoctors?.toLocaleString() ?? "0"} subtitle="Ophthalmologist roster" icon={Stethoscope} color="emerald" isLoading={isLoading} />
          <StatCard title="Active Lab Techs" value={stats?.activeLabTechnicians?.toLocaleString() ?? "0"} subtitle="Camp screener staff" icon={Microscope} color="slate" isLoading={isLoading} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <div className="lg:col-span-2 p-6 rounded-3xl bg-white border border-slate-200/80 shadow-card">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Screening Statistics &amp; AI Volume</h3>
                <p className="text-xs text-slate-500 mt-0.5">Aggregate screening intake across field camps</p>
              </div>
              <span className="text-xs font-semibold text-brand-700 bg-brand-50 px-2.5 py-1 rounded-full border border-brand-200">Monthly Trend</span>
            </div>
            {isLoading ? (
              <ChartSkeleton />
            ) : stats?.screeningVolume && stats.screeningVolume.length > 0 ? (
              <div className="space-y-4">
                <div className="h-44 flex items-end justify-between gap-3 pt-6 px-2 border-b border-slate-100">
                  {stats.screeningVolume.map((vol, idx) => (
                    <div key={idx} className="flex-1 flex flex-col items-center gap-1.5 h-full justify-end">
                      <span className="text-[10px] font-bold text-slate-700">{vol}</span>
                      <div style={{ height: `${Math.min(100, (vol / 600) * 100)}%` }} className="w-full max-w-[40px] rounded-t-xl bg-gradient-to-t from-brand-700 to-brand-500 hover:to-cyan-400 transition-all cursor-pointer" />
                      <span className="text-[10px] text-slate-400 font-medium mt-1">M{idx + 1}</span>
                    </div>
                  ))}
                </div>
                <div className="grid grid-cols-5 gap-2 text-center text-xs pt-2">
                  <div className="p-2 rounded-xl bg-emerald-50 text-emerald-800 border border-emerald-100"><span className="block text-[10px] font-medium text-emerald-600">No DR</span><strong className="text-xs">{stats.severityDistribution?.noDR}</strong></div>
                  <div className="p-2 rounded-xl bg-brand-50 text-brand-800 border border-brand-100"><span className="block text-[10px] font-medium text-brand-600">Mild NPDR</span><strong className="text-xs">{stats.severityDistribution?.mildNPDR}</strong></div>
                  <div className="p-2 rounded-xl bg-yellow-50 text-yellow-800 border border-yellow-100"><span className="block text-[10px] font-medium text-yellow-600">Mod NPDR</span><strong className="text-xs">{stats.severityDistribution?.moderateNPDR}</strong></div>
                  <div className="p-2 rounded-xl bg-amber-50 text-amber-800 border border-amber-100"><span className="block text-[10px] font-medium text-amber-600">Severe NPDR</span><strong className="text-xs">{stats.severityDistribution?.severeNPDR}</strong></div>
                  <div className="p-2 rounded-xl bg-rose-50 text-rose-800 border border-rose-100"><span className="block text-[10px] font-medium text-rose-600">PDR (Critical)</span><strong className="text-xs">{stats.severityDistribution?.proliferativeDR}</strong></div>
                </div>
              </div>
            ) : (
              <EmptyState type="screenings" title="No screening records available" description="When healthcare workers screen patients at camps, longitudinal volume metrics will render here." compact />
            )}
          </div>

          <div className="p-6 rounded-3xl bg-white border border-slate-200/80 shadow-card flex flex-col justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900 mb-1">User Management Shortcuts</h3>
              <p className="text-xs text-slate-500 mb-4">Quick actions for administrators</p>
              <div className="space-y-2.5">
                <button onClick={() => document.getElementById("team-management")?.scrollIntoView()} className="w-full p-3 rounded-2xl border border-slate-200 hover:border-brand-300 hover:bg-brand-50/40 text-left transition-all flex items-center justify-between group">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center"><Stethoscope className="w-4 h-4" aria-hidden="true" /></div>
                    <div><h4 className="text-xs font-bold text-slate-800">Assign Ophthalmologists</h4><p className="text-[10px] text-slate-500">Route priority cases to doctor queues</p></div>
                  </div>
                  <Plus className="w-4 h-4 text-slate-400 group-hover:text-brand-600" aria-hidden="true" />
                </button>
                <button onClick={() => document.getElementById("team-management")?.scrollIntoView()} className="w-full p-3 rounded-2xl border border-slate-200 hover:border-brand-300 hover:bg-brand-50/40 text-left transition-all flex items-center justify-between group">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-xl bg-cyan-50 text-cyan-600 flex items-center justify-center"><Microscope className="w-4 h-4" aria-hidden="true" /></div>
                    <div><h4 className="text-xs font-bold text-slate-800">Provision Field Screener</h4><p className="text-[10px] text-slate-500">Grant camp tablet &amp; camera access</p></div>
                  </div>
                  <Plus className="w-4 h-4 text-slate-400 group-hover:text-brand-600" aria-hidden="true" />
                </button>
                <button onClick={() => document.getElementById("team-management")?.scrollIntoView()} className="w-full p-3 rounded-2xl border border-slate-200 hover:border-brand-300 hover:bg-brand-50/40 text-left transition-all flex items-center justify-between group">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center"><Download className="w-4 h-4" aria-hidden="true" /></div>
                    <div><h4 className="text-xs font-bold text-slate-800">View Team &amp; Organization Records</h4><p className="text-[10px] text-slate-500">Review authorized organization activity</p></div>
                  </div>
                  <FileText className="w-4 h-4 text-slate-400 group-hover:text-slate-700" aria-hidden="true" />
                </button>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-slate-100 text-center">
              <span className="text-[11px] text-slate-400 font-medium">All user accounts authenticated via organization SSO</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="p-6 rounded-3xl bg-white border border-slate-200/80 shadow-card">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Screening Camp Overview</h3>
                <p className="text-xs text-slate-500 mt-0.5">Active field units and rural outreach centers</p>
              </div>
              <button onClick={() => document.getElementById("organization-settings")?.scrollIntoView()} className="text-xs text-brand-600 hover:text-brand-700 font-semibold flex items-center gap-1">
                <Plus className="w-3.5 h-3.5" aria-hidden="true" />
                <span>Organization Settings</span>
              </button>
            </div>
            {camps.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-200 text-slate-400 font-semibold">
                      <th className="pb-2" scope="col">Camp Name</th>
                      <th className="pb-2" scope="col">Location</th>
                      <th className="pb-2 text-center" scope="col">Screened</th>
                      <th className="pb-2 text-right" scope="col">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {camps.map((camp) => (
                      <tr key={camp.id} className="hover:bg-slate-50">
                        <td className="py-3 font-bold text-slate-800 flex items-center gap-2"><Tent className="w-3.5 h-3.5 text-brand-600" aria-hidden="true" /><span>{camp.name}</span></td>
                        <td className="py-3 text-slate-500">{camp.location}</td>
                        <td className="py-3 text-center font-semibold text-slate-700">{camp.screenedCount}</td>
                        <td className="py-3 text-right"><span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold text-[10px]">{camp.status}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState type="search" title="No active screening camps recorded" description="Set up your first rural screening camp or mobile clinic unit to start capturing patient records." actionLabel="Organization Settings" onAction={() => document.getElementById("organization-settings")?.scrollIntoView()} compact />
            )}
          </div>

          <div className="p-6 rounded-3xl bg-white border border-slate-200/80 shadow-card">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Recent Activity</h3>
                <p className="text-xs text-slate-500 mt-0.5">System audit log &amp; camp operational events</p>
              </div>
              <Clock className="w-4 h-4 text-slate-400" aria-hidden="true" />
            </div>
            {stats?.recentActivity && stats.recentActivity.length > 0 ? (
              <div className="space-y-3">
                {stats.recentActivity.map((act) => (
                  <div key={act.id} className="p-3 rounded-2xl bg-slate-50 border border-slate-200/80 flex items-start gap-3">
                    <div className="w-7 h-7 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center flex-shrink-0 mt-0.5"><Activity className="w-3.5 h-3.5" aria-hidden="true" /></div>
                    <div className="flex-1">
                      <p className="text-xs font-semibold text-slate-800">{act.action}</p>
                      <div className="flex items-center gap-2 mt-1 text-[10px] text-slate-400 font-medium"><span>{act.user}</span><span>•</span><span>{act.time}</span></div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState type="default" title="No recent administrative activity" description="Administrative events, camp launches, and doctor validations will appear in this real-time log." compact />
            )}
          </div>
        </div>
        {loadError && <p role="alert" className="text-rose-700">{loadError}</p>}
        <div id="team-management"><UsersPanel /></div>
        <ScreeningHistory admin />
        <PatientDirectory />
        <div id="organization-settings"><OrganizationSettings /></div>
      </main>
    </div>
  );
}
