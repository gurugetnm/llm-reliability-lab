import { Database } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";

export default function DatasetsPage() {
  return (
    <>
      <PageHeader
        title="Datasets"
        description="Manage evaluation datasets and RAG document collections."
      />
      <EmptyState
        icon={Database}
        title="No datasets yet"
        description="Datasets — evaluation sets, golden answers, and RAG corpora — are introduced alongside the evaluation and RAG engines in a later phase."
      />
    </>
  );
}
