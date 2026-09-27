"use client";

import dynamic from "next/dynamic";

/**
 * Client boundary for the code-split retina viewer. `ssr: false` is not
 * allowed in Server Components, so the landing page (server) renders this
 * island instead — keeping viewer JS out of dashboard bundles.
 */
const RetinaViewerInner = dynamic(
  () => import("@/features/diagnosis/RetinaViewer").then((m) => m.RetinaViewer),
  {
    ssr: false,
    loading: () => (
      <div
        className="h-72 animate-pulse rounded-full bg-brand-100/40 max-w-md mx-auto"
        aria-label="Loading retina viewer"
      />
    ),
  },
);

export function RetinaViewerLazy() {
  return <RetinaViewerInner />;
}
