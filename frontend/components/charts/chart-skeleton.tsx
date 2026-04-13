import { Skeleton } from "@/components/ui/skeleton";

interface ChartSkeletonProps {
  height?: number;
}

export function ChartSkeleton({ height = 300 }: ChartSkeletonProps) {
  return (
    <div className="w-full rounded-md border p-4" style={{ height }}>
      <div className="flex h-full flex-col justify-between">
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-16" />
        </div>
        <div className="flex flex-1 items-end gap-1 py-4">
          {[40, 65, 45, 80, 55, 70, 60, 90, 50, 75].map((h, i) => (
            <Skeleton
              key={i}
              className="flex-1"
              style={{ height: `${h}%` }}
            />
          ))}
        </div>
        <div className="flex items-center justify-between">
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-3 w-16" />
        </div>
      </div>
    </div>
  );
}
