import Link from "next/link";
import { FlaskConical } from "lucide-react";

export function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2 px-2">
      <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
        <FlaskConical className="size-3.5" strokeWidth={2.25} />
      </span>
      <span className="text-sm font-semibold tracking-tight text-sidebar-foreground">
        LLM Reliability Lab
      </span>
    </Link>
  );
}
