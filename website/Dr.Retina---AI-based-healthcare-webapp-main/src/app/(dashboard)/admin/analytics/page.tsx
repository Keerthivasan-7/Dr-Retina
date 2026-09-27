import { requireRole } from "@/lib/auth/guards";
import { AdminDashboard } from "@/features/admin/AdminDashboard";

export const metadata = { title: "Analytics | Admin | Dr.Retina" };

export default async function AdminAnalyticsPage() {
  const session = await requireRole("ORG_ADMIN");
  return <AdminDashboard orgName={session.orgName} section="analytics" />;
}
