import { CheckCircle2, CircleDashed, Loader2, OctagonX, TriangleAlert, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { ExperimentRunStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

const CONFIG: Record<
  ExperimentRunStatus,
  { label: string; icon: typeof CheckCircle2; className: string }
> = {
  pending: {
    label: "Pending",
    icon: CircleDashed,
    className: "bg-muted text-muted-foreground",
  },
  running: {
    label: "Running",
    icon: Loader2,
    className: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
  },
  completed: {
    label: "Completed",
    icon: CheckCircle2,
    className: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  },
  completed_with_errors: {
    label: "Completed with errors",
    icon: TriangleAlert,
    className: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  },
  failed: {
    label: "Failed",
    icon: XCircle,
    className: "bg-destructive/10 text-destructive",
  },
  cancelled: {
    label: "Cancelled",
    icon: OctagonX,
    className: "bg-muted text-muted-foreground",
  },
};

export function RunStatusBadge({
  status,
  className,
}: {
  status: ExperimentRunStatus;
  className?: string;
}) {
  const config = CONFIG[status];
  const Icon = config.icon;
  return (
    <Badge variant="outline" className={cn("border-transparent", config.className, className)}>
      <Icon className={cn("size-3", status === "running" && "animate-spin")} />
      {config.label}
    </Badge>
  );
}
