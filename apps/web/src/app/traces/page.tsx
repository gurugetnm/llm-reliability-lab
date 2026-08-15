import { Activity } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";

export default function TracesPage() {
  return (
    <>
      <PageHeader
        title="Traces"
        description="Inspect request, retrieval, and response execution traces."
      />
      <EmptyState
        icon={Activity}
        title="No traces yet"
        description="Tracing and observability — capturing every step of a run, from retrieval to generation — is introduced in a later phase."
      />
    </>
  );
}
