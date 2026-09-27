import { AccountForm } from "@/features/auth/AccountForm";
import { redirect } from "next/navigation";
import { createSupabaseServerClient } from "@/lib/auth/supabase";
export const dynamic = "force-dynamic";
export default async function Page() {
  const client = await createSupabaseServerClient();
  const { data: { user }, error } = await client.auth.getUser();
  if (error || !user) redirect("/login?error=session_required");
  return <AccountForm mode="password" />;
}
