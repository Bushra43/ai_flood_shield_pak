import { Card } from "@/components/ui/card";

export function LoadingState() {
  return (
    <div className="space-y-6">
      <Card className="h-64 animate-pulse bg-slate-100 dark:bg-slate-800" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <Card key={i} className="h-36 animate-pulse bg-slate-100 dark:bg-slate-800" />
        ))}
      </div>
      <Card className="h-96 animate-pulse bg-slate-100 dark:bg-slate-800" />
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <Card className="p-8 text-center">
      <p className="text-sm font-medium text-slate-600 dark:text-slate-300">
        {message}
      </p>
    </Card>
  );
}
