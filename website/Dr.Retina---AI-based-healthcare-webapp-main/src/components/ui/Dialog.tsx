"use client";

import * as React from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils/cn";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  labelledBy: string;
  children: React.ReactNode;
  maxWidth?: string;
}

/** Accessible modal dialog: focus close on open, Escape to close, aria-modal. */
export function Dialog({ open, onClose, labelledBy, children, maxWidth = "max-w-xl" }: DialogProps) {
  const closeRef = React.useRef<HTMLButtonElement>(null);

  React.useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        onClick={(e) => e.stopPropagation()}
        className={cn(
          "bg-white rounded-3xl border border-slate-200 shadow-2xl w-full overflow-hidden animate-scale-in",
          maxWidth,
        )}
      >
        {children}
      </div>
    </div>
  );
}

export function DialogHeader({
  id,
  title,
  subtitle,
  onClose,
}: {
  id: string;
  title: string;
  subtitle: string;
  onClose: () => void;
}) {
  return (
    <div className="px-6 py-4 bg-gradient-to-r from-brand-700 via-brand-800 to-cyan-800 text-white flex items-center justify-between">
      <div>
        <h3 id={id} className="font-bold text-sm">
          {title}
        </h3>
        <p className="text-[11px] text-brand-200">{subtitle}</p>
      </div>
      <button
        ref={undefined}
        onClick={onClose}
        aria-label="Close dialog"
        className="p-1 rounded-lg hover:bg-brand-600/40 text-brand-200 hover:text-white transition-colors focus-visible:outline-2 focus-visible:outline-white"
      >
        <X className="w-5 h-5" />
      </button>
    </div>
  );
}
