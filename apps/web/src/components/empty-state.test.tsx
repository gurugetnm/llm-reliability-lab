import { render, screen } from "@testing-library/react";
import { FlaskConical } from "lucide-react";
import { describe, expect, it } from "vitest";
import { EmptyState } from "@/components/empty-state";

describe("EmptyState", () => {
  it("renders the title, description, and optional action", () => {
    render(
      <EmptyState
        icon={FlaskConical}
        title="No experiments yet"
        description="Create a project to get started."
        action={<button>Create Project</button>}
      />,
    );

    expect(screen.getByText("No experiments yet")).toBeInTheDocument();
    expect(screen.getByText("Create a project to get started.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create Project" })).toBeInTheDocument();
  });

  it("omits the action region when no action is passed", () => {
    render(
      <EmptyState icon={FlaskConical} title="No experiments yet" description="..." />,
    );

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
