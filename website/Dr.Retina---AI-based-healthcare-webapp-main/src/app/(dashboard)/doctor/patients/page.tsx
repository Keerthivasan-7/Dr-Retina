import { requireRole } from "@/lib/auth/guards";
import { DoctorDashboard } from "@/features/doctor/DoctorDashboard";

export const metadata = { title: "Patients | Doctor | Dr.Retina" };

export default async function DoctorPatientsPage() {
  const session = await requireRole("DOCTOR", "ORG_ADMIN");
  return <DoctorDashboard orgName={session.orgName} queue="recent" />;
}
