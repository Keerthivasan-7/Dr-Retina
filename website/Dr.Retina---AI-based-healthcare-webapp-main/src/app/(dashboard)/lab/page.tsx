import { requireRole } from "@/lib/auth/guards";
import { LabTechDashboard } from "@/features/lab/LabTechDashboard";

export const metadata = { title: "Lab Technician Workspace | Dr.Retina" };

export default async function LabPage() {
  const session = await requireRole("LAB_TECHNICIAN", "ORG_ADMIN");
  return <LabTechDashboard orgName={session.orgName} />;
}
