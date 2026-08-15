import { CheckSquare } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";

export default function EvaluationsPage() {
  return (
    <>
      <PageHeader
        title="Evaluations"
        description="Score and compare experiment runs against your datasets."
      />
      <EmptyState
        icon={CheckSquare}
        title="No evaluation runs yet"
        description="Automated scoring — exact-match, LLM-as-judge, retrieval metrics, and regression detection — is part of the evaluation engine, coming in a later phase."
      />
    </>
  );
}
