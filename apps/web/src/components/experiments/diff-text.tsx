import type { DiffPart } from "@/lib/text-diff";
import { cn } from "@/lib/utils";

export function DiffText({ parts }: { parts: DiffPart[] }) {
  return (
    <>
      {parts.map((part, index) => (
        <span
          key={index}
          className={cn(
            part.type === "added" &&
              "rounded-sm bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
            part.type === "removed" &&
              "rounded-sm bg-destructive/15 text-destructive line-through decoration-1",
          )}
        >
          {part.text}
        </span>
      ))}
    </>
  );
}
