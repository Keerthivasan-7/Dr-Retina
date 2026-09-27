import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  ShieldAlert,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";

export type SeverityInput = string | null | undefined;

/**
 * ICDR severity badge. Pure presentational component — no data fetching.
 * Never communicates severity by color alone: label + grade + priority text.
 */
export function SeverityBadge({
  severity,
  showGrade = true,
  size = "md",
}: {
  severity: SeverityInput;
  showGrade?: boolean;
  size?: "sm" | "md";
}) {
  const normalized = (severity ?? "").toLowerCase().trim();

  let config = {
    label: "Not Evaluated",
    grade: "Grade -",
    priority: "Unknown",
    bg: "bg-slate-100 text-slate-700 border-slate-200",
    Icon: HelpCircle,
    urgencyText: "Awaiting AI Analysis",
  };

  if (
    normalized.includes("proliferative") ||
    normalized === "pdr" ||
    normalized.includes("severe") ||
    normalized === "grade 4" ||
    normalized === "grade 3"
  ) {
    config =
      normalized.includes("proliferative") || normalized === "pdr" || normalized === "grade 4"
        ? {
            label: "Proliferative DR (PDR)",
            grade: "Grade 4 (Critical)",
            priority: "CRITICAL",
            bg: "bg-rose-50 text-rose-800 border-rose-200 ring-1 ring-rose-300",
            Icon: AlertOctagon,
            urgencyText: "Immediate Action Required",
          }
        : {
            label: "Severe NPDR",
            grade: "Grade 3 (High Risk)",
            priority: "HIGH PRIORITY",
            bg: "bg-amber-50 text-amber-800 border-amber-200 ring-1 ring-amber-300",
            Icon: ShieldAlert,
            urgencyText: "Expedited Review",
          };
  } else if (normalized.includes("moderate") || normalized === "grade 2") {
    config = {
      label: "Moderate NPDR",
      grade: "Grade 2 (Moderate)",
      priority: "MODERATE",
      bg: "bg-yellow-50 text-yellow-800 border-yellow-200",
      Icon: AlertTriangle,
      urgencyText: "3-Month Review",
    };
  } else if (normalized.includes("mild") || normalized === "grade 1") {
    config = {
      label: "Mild NPDR",
      grade: "Grade 1 (Mild)",
      priority: "ROUTINE",
      bg: "bg-brand-50 text-brand-800 border-brand-200",
      Icon: CheckCircle2,
      urgencyText: "6-Month Review",
    };
  } else if (
    normalized.includes("no dr") ||
    normalized.includes("normal") ||
    normalized === "grade 0"
  ) {
    config = {
      label: "No DR Detected",
      grade: "Grade 0 (Normal)",
      priority: "LOW",
      bg: "bg-emerald-50 text-emerald-800 border-emerald-200",
      Icon: CheckCircle2,
      urgencyText: "Annual Follow-up",
    };
  }

  const { Icon } = config;
  const isCompact = size === "sm";

  return (
    <div className="inline-flex flex-col items-start gap-0.5">
      <span
        className={cn(
          "inline-flex items-center gap-1.5 font-semibold rounded-lg border",
          config.bg,
          isCompact ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs",
        )}
      >
        <Icon className={isCompact ? "w-3 h-3" : "w-3.5 h-3.5"} aria-hidden="true" />
        <span>{config.label}</span>
        {showGrade && <span className="opacity-70 font-normal ml-0.5">({config.grade})</span>}
      </span>
      {size !== "sm" && (
        <span className="text-[10px] text-slate-500 font-medium tracking-tight">
          Priority: <strong className="text-slate-700">{config.priority}</strong> •{" "}
          {config.urgencyText}
        </span>
      )}
    </div>
  );
}
