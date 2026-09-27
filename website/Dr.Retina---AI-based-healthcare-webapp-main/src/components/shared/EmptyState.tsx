import {
  CalendarClock,
  Database,
  FileCheck2,
  FolderSearch,
  Plus,
  ShieldAlert,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";

export type EmptyStateType =
  | "default"
  | "patients"
  | "screenings"
  | "priority"
  | "consultations"
  | "search";

/**
 * Legacy-compatible empty state (visual parity with the Vite implementation).
 * Type maps to icon only — status is always conveyed with text, never color alone.
 */
export function EmptyState({
  type = "default",
  title = "No data available",
  description = "There are currently no records stored in the database for this view.",
  actionLabel = null,
  onAction = null,
  action,
  compact = false,
}: {
  type?: EmptyStateType;
  title?: string;
  description?: string;
  actionLabel?: string | null;
  onAction?: (() => void) | null;
  action?: React.ReactNode;
  compact?: boolean;
}) {
  const icon = (() => {
    switch (type) {
      case "patients":
        return <Users className="w-8 h-8 text-brand-600/70" aria-hidden="true" />;
      case "screenings":
        return <FileCheck2 className="w-8 h-8 text-cyan-600/70" aria-hidden="true" />;
      case "priority":
        return <ShieldAlert className="w-8 h-8 text-emerald-600/70" aria-hidden="true" />;
      case "consultations":
        return <CalendarClock className="w-8 h-8 text-blue-600/70" aria-hidden="true" />;
      case "search":
        return <FolderSearch className="w-8 h-8 text-slate-500/70" aria-hidden="true" />;
      default:
        return <Database className="w-8 h-8 text-slate-400" aria-hidden="true" />;
    }
  })();

  return (
    <div
      className={cn(
        "w-full flex flex-col items-center justify-center text-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/60 transition-all",
        compact ? "py-8 px-4" : "py-14 px-6",
      )}
    >
      <div className="w-14 h-14 rounded-2xl bg-white border border-slate-200/80 shadow-sm flex items-center justify-center mb-3.5">
        {icon}
      </div>
      <h4 className="text-sm font-bold text-slate-800 tracking-tight">{title}</h4>
      <p className="text-xs text-slate-500 max-w-sm mt-1 leading-relaxed">{description}</p>
      {action ?? (actionLabel && onAction && (
        <button
          onClick={onAction}
          className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold text-brand-700 bg-brand-50 border border-brand-200 hover:bg-brand-100 active:bg-brand-200 transition-all shadow-sm"
        >
          <Plus className="w-3.5 h-3.5" aria-hidden="true" />
          <span>{actionLabel}</span>
        </button>
      ))}
    </div>
  );
}
