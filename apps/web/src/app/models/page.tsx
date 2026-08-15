import { Cpu } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";

export default function ModelsPage() {
  return (
    <>
      <PageHeader
        title="Models"
        description="Local and remote LLM providers available to your experiments."
      />
      <EmptyState
        icon={Cpu}
        title="No models configured"
        description="The API already speaks to Ollama through a provider-agnostic interface. Model discovery and configuration in this UI arrive in a later phase."
      />
    </>
  );
}
