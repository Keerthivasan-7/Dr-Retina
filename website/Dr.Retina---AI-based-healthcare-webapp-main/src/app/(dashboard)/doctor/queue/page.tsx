import { requireRole } from "@/lib/auth/guards";
import { DoctorDashboard } from "@/features/doctor/DoctorDashboard";

export const metadata = { title: "Triage Queue | Doctor | Dr.Retina" };

export default async function DoctorQueuePage() {
  const session = await requireRole("DOCTOR", "ORG_ADMIN");
  return <DoctorDashboard orgName={session.orgName} queue="high_priority" />;
}
