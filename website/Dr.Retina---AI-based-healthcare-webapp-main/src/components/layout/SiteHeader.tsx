import Link from "next/link";
import { logoutAction } from "@/features/auth/actions";
import { Building2, ChevronRight, Eye, Shield } from "lucide-react";

export function SiteHeader({
  mode,
  orgName,
  roleLabel,
}: {
  mode: "landing" | "app";
  orgName?: string;
  roleLabel?: string;
}) {
  return (
    <header className="sticky top-0 z-50 bg-white/90 backdrop-blur-md border-b border-slate-200/80 transition-all shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between min-h-20 gap-3 py-3">
          <Link href="/" className="flex items-center gap-3 group" aria-label="Dr.Retina home">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-700 via-brand-600 to-cyan-500 flex items-center justify-center shadow-md shadow-brand-500/20 group-hover:scale-105 transition-transform">
              <div className="relative flex items-center justify-center">
                <Eye className="w-6 h-6 text-white" aria-hidden="true" />
                <span className="absolute w-2 h-2 rounded-full bg-sky-200 top-0 right-0" />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="text-xl font-extrabold tracking-tight text-slate-900 font-sans">
                  Dr.<span className="text-brand-600">Retina</span>
                </span>
                <span className="hidden sm:inline text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-brand-50 text-brand-700 border border-brand-200">
                  AI Screening
                </span>
              </div>
              <p className="text-[11px] text-slate-500 -mt-0.5 font-medium">Clearer insights. Closer care.</p>
            </div>
          </Link>

          {mode === "landing" ? (
            <nav className="hidden lg:flex items-center gap-5 text-sm font-medium text-slate-600" aria-label="Primary">
              <a href="#how-it-works" className="hover:text-brand-600 transition-colors">How It Works</a>
              <a href="#benefits" className="hover:text-brand-600 transition-colors">Camp Benefits</a>
              <a href="#disclaimer" className="hover:text-brand-600 transition-colors">Medical Disclaimer</a>
            </nav>
          ) : (
            <div className="hidden md:flex items-center gap-3 text-xs">
              {orgName && (
                <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-100 border border-slate-200 text-slate-700 font-medium">
                  <Building2 className="w-3.5 h-3.5 text-brand-600" aria-hidden="true" />
                  <span>{orgName}</span>
                </div>
              )}
              {roleLabel && (
                <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-brand-50 border border-brand-200 text-brand-800 font-medium">
                  <Shield className="w-3.5 h-3.5 text-brand-600" aria-hidden="true" />
                  <span>{roleLabel} Mode</span>
                </div>
              )}
            </div>
          )}

          <div className="flex items-center gap-3">
            {mode === "landing" ? (
              <Link
                href="/select-org"
                className="inline-flex items-center justify-center px-5 py-2.5 rounded-full text-sm font-semibold text-white bg-brand-600 hover:bg-brand-700 active:bg-brand-800 shadow-md shadow-brand-600/20 transition-all hover:shadow-lg hover:scale-[1.02] gap-2"
              >
                <span>Login</span>
                <ChevronRight className="w-4 h-4" aria-hidden="true" />
              </Link>
            ) : (
              <div className="flex items-center gap-2">
                {roleLabel && <form action={logoutAction}><button className="text-xs text-brand-700 font-semibold px-2">Sign out</button></form>}
                <Link href="/" className="px-3.5 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors">
                  Exit to Home
                </Link>
                <Link href="/select-org" className="px-3.5 py-1.5 rounded-lg text-xs font-medium bg-brand-50 text-brand-700 border border-brand-200 hover:bg-brand-100 transition-colors">
                  Organization
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
