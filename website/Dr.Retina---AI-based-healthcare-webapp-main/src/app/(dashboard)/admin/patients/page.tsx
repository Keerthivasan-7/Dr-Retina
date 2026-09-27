import { requireRole } from "@/lib/auth/guards";
import { AdminDashboard } from "@/features/admin/AdminDashboard";

export const metadata = { title: "Patients | Admin | Dr.Retina" };

export default async function AdminPatientsPage() {
  const session = await requireRole("ORG_ADMIN");
  return <AdminDashboard orgName={session.orgName} section="patients" />;
}
