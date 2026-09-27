import Link from "next/link";
import { redirect } from "next/navigation";
import { createSupabaseServerClient } from "@/lib/auth/supabase";
import { logoutAction } from "@/features/auth/actions";
import { ProfileForm } from "@/features/auth/ProfileForm";
export const dynamic = "force-dynamic";
export default async function AccountPage({ searchParams }: { searchParams: Promise<{ notice?: string }> }) {
  const client = await createSupabaseServerClient();
  const { data: { user }, error } = await client.auth.getUser();
  if (error || !user) redirect("/login");
  const { data: profile, error: profileError } = await client.from("profiles").select("display_name").eq("id", user.id).single();
  const { notice } = await searchParams;
  return <section className="max-w-lg mx-auto my-12 p-8 rounded-3xl border bg-white shadow-card">
    <h1 className="text-2xl font-bold">Your account</h1><p className="mt-2 text-sm text-slate-600">{user.email}</p>
    {notice === "organization_unavailable" && <p role="status" className="mt-4 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">You are signed in. The organization service is currently unavailable. You can manage your account here and try your workspace again later.</p>}
    {profileError ? <p role="alert" className="my-4 text-rose-700">Your profile could not be loaded. Please try again.</p> : <ProfileForm displayName={profile?.display_name ?? ""} />}
    <div className="flex flex-wrap gap-4 text-sm text-brand-700"><Link href="/onboarding">Open organization workspace</Link><Link href="/account/password">Change password</Link><form action={logoutAction}><button>Sign out</button></form></div>
  </section>;
}
