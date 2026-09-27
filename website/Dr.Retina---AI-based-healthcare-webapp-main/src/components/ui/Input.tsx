import * as React from "react";
import { cn } from "@/lib/utils/cn";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

export function Input({ className, ...props }: InputProps) {
  return (
    <input
      className={cn(
        "w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-xs sm:text-sm",
        "font-medium text-slate-800 placeholder:text-slate-400",
        "focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none transition-all",
        className,
      )}
      {...props}
    />
  );
}

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {}

export function Select({ className, children, ...props }: SelectProps) {
  return (
    <select
      className={cn(
        "w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-xs bg-white",
        "focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}

export function FieldLabel({ children, htmlFor }: { children: React.ReactNode; htmlFor?: string }) {
  return (
    <label
      htmlFor={htmlFor}
      className="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5"
    >
      {children}
    </label>
  );
}
