import { requireRole } from "@/lib/auth/guards";
import { AdminDashboard } from "@/features/admin/AdminDashboard";

export const metadata = { title: "Admin Dashboard | Dr.Retina" };

export default async function AdminPage() {
  const session = await requireRole("ORG_ADMIN");
  return <AdminDashboard orgName={session.orgName} section="dashboard" />;
}
