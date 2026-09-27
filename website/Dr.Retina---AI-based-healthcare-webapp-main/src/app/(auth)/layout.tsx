import { SiteHeader } from "@/components/layout/SiteHeader";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
      <SiteHeader mode="app" />
      <div className="flex-1">{children}</div>
    </div>
  );
}
