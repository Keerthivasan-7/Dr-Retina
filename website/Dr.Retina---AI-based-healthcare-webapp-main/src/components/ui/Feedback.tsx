import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils/cn";

export function CardSkeleton() {
  return <div className="p-5 rounded-2xl bg-white border border-slate-200/80 shadow-sm animate-pulse" aria-label="Loading card"><div className="h-4 w-24 bg-slate-200 rounded" /><div className="h-7 w-20 bg-slate-200 rounded mt-2" /></div>;
}

export function TableRowSkeleton({ cols = 4 }: { cols?: number }) {
  return (
    <div className="flex gap-3 py-3 animate-pulse" aria-label="Loading table row">
      {Array.from({ length: cols }).map((_, i) => (
        <div key={i} className="h-4 flex-1 bg-slate-200 rounded" />
      ))}
    </div>
  );
}

export function ChartSkeleton() {
  return <div className="h-48 rounded-2xl bg-slate-100 border border-slate-200 animate-pulse" aria-label="Loading chart" />;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon?: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="p-8 text-center rounded-2xl border-2 border-dashed border-slate-200 bg-slate-50/60">
      {Icon && (
        <div className="w-12 h-12 rounded-2xl bg-white border border-slate-200 flex items-center justify-center mx-auto mb-3 text-slate-400">
          <Icon className="w-6 h-6" aria-hidden="true" />
        </div>
      )}
      <h4 className="font-bold text-slate-800 text-sm">{title}</h4>
      <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  description = "Please try again. If the problem persists, contact your system administrator.",
  onRetry,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
}) {
  return (
    <div role="alert" className="p-8 text-center rounded-2xl bg-rose-50/60 border border-rose-200">
      <h4 className="font-bold text-rose-900 text-sm">{title}</h4>
      <p className="text-xs text-rose-700 mt-1 max-w-sm mx-auto">{description}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-4 px-4 py-2 rounded-xl text-xs font-semibold bg-white border border-rose-200 text-rose-700 hover:bg-rose-50">
          Try again
        </button>
      )}
    </div>
  );
}

export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
  ariaLabel,
}: {
  tabs: ReadonlyArray<{ id: T; label: string; badge?: string | null }>;
  active: T;
  onChange: (id: T) => void;
  ariaLabel: string;
}) {
  return (
    <div role="tablist" aria-label={ariaLabel} className="flex flex-wrap gap-2">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={active === t.id}
          onClick={() => onChange(t.id)}
          className={cn(
            "px-4 py-2 rounded-full text-xs font-semibold border transition-all focus-visible:outline-2 focus-visible:outline-brand-600",
            active === t.id
              ? "bg-brand-600 text-white border-brand-600 shadow-md shadow-brand-600/20"
              : "bg-white text-slate-600 border-slate-200 hover:border-brand-300",
          )}
        >
          {t.label}
          {t.badge && <span className="ml-1.5 opacity-80">({t.badge})</span>}
        </button>
      ))}
    </div>
  );
}
