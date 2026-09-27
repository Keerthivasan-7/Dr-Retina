import { requireRole } from "@/lib/auth/guards";
import { DoctorDashboard } from "@/features/doctor/DoctorDashboard";

export const metadata = { title: "Reports | Doctor | Dr.Retina" };

export default async function DoctorReportsPage() {
  const session = await requireRole("DOCTOR", "ORG_ADMIN");
  return <DoctorDashboard orgName={session.orgName} queue="followups" />;
}
