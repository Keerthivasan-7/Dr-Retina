"use client";

import Link from "next/link";
import { toUserMessage } from "@/lib/api/errors";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="max-w-2xl mx-auto px-4 py-16 text-center">
      <div role="alert" className="p-8 rounded-3xl bg-white border border-slate-200 shadow-sm">
        <h2 className="text-lg font-extrabold text-slate-900">Something went wrong</h2>
        <p className="text-sm text-slate-500 mt-2">{toUserMessage(error)}</p>
        <div className="mt-6 flex items-center justify-center gap-3">
          <button
            onClick={reset}
            className="px-5 py-2.5 rounded-full text-sm font-semibold text-white bg-brand-600 hover:bg-brand-700"
          >
            Try again
          </button>
          <Link href="/" className="px-5 py-2.5 rounded-full text-sm font-semibold bg-white border border-slate-200 text-slate-700 hover:border-brand-300">
            Back home
          </Link>
        </div>
      </div>
    </div>
  );
}
