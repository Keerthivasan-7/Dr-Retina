import { requireSession } from "@/lib/auth/guards";
import { SiteHeader } from "@/components/layout/SiteHeader";
import { Notifications } from "@/components/shared/Notifications";
export const dynamic = "force-dynamic";

const ROLE_LABEL: Record<string, string> = {
  ORG_ADMIN: "Admin",
  DOCTOR: "Doctor",
  LAB_TECHNICIAN: "Lab Tech",
};

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const session = await requireSession();
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
      <SiteHeader
        mode="app"
        orgName={session.orgName || undefined}
        roleLabel={ROLE_LABEL[session.role]}
      />
      <Notifications doctor={session.role === "DOCTOR"} />
      <div className="flex-1">{children}</div>
    </div>
  );
}
