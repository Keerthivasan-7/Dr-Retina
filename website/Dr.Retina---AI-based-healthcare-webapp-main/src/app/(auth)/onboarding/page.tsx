import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth/session";
import { defaultRouteForRole } from "@/lib/auth/permissions";
import { backendToken } from "@/lib/api/server";
import { AccountForm } from "@/features/auth/AccountForm";
import { OrganizationForm } from "@/features/organizations/OrganizationForm";
export const dynamic = "force-dynamic";
export default async function Page() {
  const session = await getSession();
  if (session) redirect(defaultRouteForRole(session.role));
  const token = await backendToken();
  if (!token) return <AccountForm mode="register" />;
  return <div className="max-w-2xl mx-auto my-12 px-4"><OrganizationForm /></div>;
}
