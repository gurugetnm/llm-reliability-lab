import { FlaskConical } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";

export default function ExperimentsPage() {
  return (
    <>
      <PageHeader
        title="Experiments"
        description="Run and compare prompt, model, and RAG configurations side by side."
      />
      <EmptyState
        icon={FlaskConical}
        title="No experiments yet"
        description="The experiment engine — running a prompt across models and configurations, then diffing the results — lands in a later phase. Create a project first to get set up."
      />
    </>
  );
}
