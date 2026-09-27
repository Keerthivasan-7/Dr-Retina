import Link from "next/link";
import { Building2 } from "lucide-react";
export function OrgSelectForm() {
  return <div className="max-w-lg mx-auto my-16 p-8 bg-white rounded-3xl border border-brand-100 shadow-card">
    <Building2 className="h-12 w-12 text-brand-600 mb-5" aria-hidden="true" />
    <h1 className="text-2xl font-bold">Your organization workspace</h1>
    <p className="mt-3 text-slate-600">Sign in with your authorized account. Your organization and portal are determined by your membership.</p>
    <Link href="/login" className="block text-center rounded-xl bg-brand-600 text-white p-3 font-semibold mt-6">Continue to Login</Link>
    <Link href="/onboarding" className="block text-center text-brand-700 mt-5 text-sm">Create a new organization</Link>
  </div>;
}
