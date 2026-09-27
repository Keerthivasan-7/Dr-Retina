import { ChartSkeleton, CardSkeleton, TableRowSkeleton } from "@/components/ui/Feedback";

export default function Loading() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6" aria-busy="true" aria-label="Loading">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>
      <ChartSkeleton />
      <TableRowSkeleton cols={4} />
      <TableRowSkeleton cols={4} />
    </div>
  );
}
