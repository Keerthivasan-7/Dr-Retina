import { ShieldCheck } from "lucide-react";
import { SiteHeader } from "@/components/layout/SiteHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { exchangeCodeAction } from "@/features/auth/actions";

const COPY = {
  "/onboarding": {
    title: "Confirm your account",
    body: "Click below to verify your email and finish setting up your administrator account.",
    cta: "Confirm my account",
  },
  "/account/password": {
    title: "Continue to password reset",
    body: "Click below to continue to the password reset page.",
    cta: "Continue",
  },
} as const;

export default async function CallbackPage({
  searchParams,
}: {
  searchParams: Promise<{ code?: string; next?: string }>;
}) {
  const { code, next } = await searchParams;
  const target = next === "/account/password" ? "/account/password" : "/onboarding";
  const copy = COPY[target];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
      <SiteHeader mode="app" />
      <div className="flex-1 flex items-center justify-center px-4 py-16">
        <Card className="max-w-md w-full text-center">
          <div className="w-12 h-12 rounded-xl bg-brand-50 border border-brand-200 flex items-center justify-center mx-auto mb-4">
            <ShieldCheck className="w-6 h-6 text-brand-600" aria-hidden="true" />
          </div>
          {code ? (
            <>
              <h1 className="text-xl font-bold text-slate-900">{copy.title}</h1>
              <p className="mt-2 text-sm text-slate-600">{copy.body}</p>
              <p className="mt-1 text-xs text-slate-400">
                For your security, this link isn&apos;t confirmed automatically — some email apps
                open links to scan them, which would otherwise use up a one-time link before you do.
              </p>
              <form action={exchangeCodeAction} className="mt-6">
                <input type="hidden" name="code" value={code} />
                <input type="hidden" name="next" value={target} />
                <Button type="submit" size="lg" className="w-full">
                  {copy.cta}
                </Button>
              </form>
            </>
          ) : (
            <>
              <h1 className="text-xl font-bold text-slate-900">Link incomplete</h1>
              <p className="mt-2 text-sm text-slate-600">
                This confirmation link is missing required information. Request a new verification or
                recovery email and try again.
              </p>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
