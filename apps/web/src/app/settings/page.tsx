import { Settings as SettingsIcon } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function SettingsPage() {
  return (
    <>
      <PageHeader title="Settings" description="Workspace and provider configuration." />

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-sm font-medium">Connection</CardTitle>
          <CardDescription>Read-only for this phase — configured via environment variables.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <p className="text-xs text-muted-foreground">API URL</p>
            <p className="mt-1 font-mono text-xs">{API_URL}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Version</p>
            <p className="mt-1 font-mono text-xs">0.1.0</p>
          </div>
        </CardContent>
      </Card>

      <EmptyState
        icon={SettingsIcon}
        title="No provider settings yet"
        description="Managing LLM provider credentials and defaults from this screen is planned for a later phase."
      />
    </>
  );
}
