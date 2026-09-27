import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils/cn";

const colorMap = {
  teal: { iconBg: "bg-brand-500/10 text-brand-700 border-brand-200/60", border: "border-slate-200/80 hover:border-brand-300" },
  cyan: { iconBg: "bg-cyan-500/10 text-cyan-700 border-cyan-200/60", border: "border-slate-200/80 hover:border-cyan-300" },
  rose: { iconBg: "bg-rose-500/10 text-rose-700 border-rose-200/60", border: "border-slate-200/80 hover:border-rose-300" },
  amber: { iconBg: "bg-amber-500/10 text-amber-700 border-amber-200/60", border: "border-slate-200/80 hover:border-amber-300" },
  emerald: { iconBg: "bg-emerald-500/10 text-emerald-700 border-emerald-200/60", border: "border-slate-200/80 hover:border-emerald-300" },
  slate: { iconBg: "bg-slate-500/10 text-slate-700 border-slate-200/60", border: "border-slate-200/80 hover:border-slate-300" },
} as const;

export type StatColor = keyof typeof colorMap;

export function StatCard({
  title,
  value,
  subtitle = null,
  icon: Icon,
  color = "teal",
  trend = null,
  trendPositive = true,
  isLoading = false,
}: {
  title: string;
  value: React.ReactNode;
  subtitle?: React.ReactNode;
  icon?: LucideIcon;
  color?: StatColor;
  trend?: React.ReactNode;
  trendPositive?: boolean;
  isLoading?: boolean;
}) {
  const scheme = colorMap[color] ?? colorMap.teal;
  return (
    <div className={cn("p-5 rounded-2xl bg-white border shadow-soft hover:shadow-card transition-all", scheme.border)}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{title}</p>
          {isLoading ? (
            <div className="h-7 w-20 bg-slate-200 rounded animate-pulse my-1" aria-label="Loading statistic" />
          ) : (
            <h3 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mt-1 tracking-tight">{value}</h3>
          )}
        </div>
        {Icon && (
          <div className={cn("w-11 h-11 rounded-xl flex items-center justify-center border", scheme.iconBg)}>
            <Icon className="w-5 h-5" aria-hidden="true" />
          </div>
        )}
      </div>
      {(subtitle ?? trend) && (
        <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
          {subtitle && <span>{subtitle}</span>}
          {trend && (
            <span className={cn("inline-flex items-center gap-0.5 font-semibold", trendPositive ? "text-brand-700" : "text-rose-600")}>
              {trendPositive ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
              {trend}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-6 rounded-3xl bg-white border border-brand-100 shadow-card", className)} {...props} />;
}
