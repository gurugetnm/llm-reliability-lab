import { RunStatusBadge } from "@/components/experiments/run-status-badge";
import type { EvaluationRunStatus, ExperimentRunStatus } from "@/lib/api";

/** `EvaluationRunStatus` and `ExperimentRunStatus` are the same set of
 * string values (see `app/models/enums.py`'s docstring on why they're
 * still two distinct backend enums) — reuse the same badge rather than
 * duplicating its icon/color config. */
export function EvaluationStatusBadge({
  status,
  className,
}: {
  status: EvaluationRunStatus;
  className?: string;
}) {
  return <RunStatusBadge status={status as ExperimentRunStatus} className={className} />;
}
