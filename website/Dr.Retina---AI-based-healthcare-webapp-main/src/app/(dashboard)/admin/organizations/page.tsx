import { requireRole } from "@/lib/auth/guards";
import { AdminDashboard } from "@/features/admin/AdminDashboard";

export const metadata = { title: "Organizations | Admin | Dr.Retina" };

export default async function AdminOrgsPage() {
  const session = await requireRole("ORG_ADMIN");
  return <AdminDashboard orgName={session.orgName} section="camps" />;
}
