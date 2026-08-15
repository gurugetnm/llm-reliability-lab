import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NavList } from "@/components/layout/nav-list";

const { usePathname } = vi.hoisted(() => ({ usePathname: vi.fn() }));

vi.mock("next/navigation", () => ({ usePathname }));

describe("NavList", () => {
  it("marks only the Dashboard link as current when at the root path", () => {
    usePathname.mockReturnValue("/");
    render(<NavList />);

    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Projects" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("marks the Projects link as current on a nested projects route", () => {
    usePathname.mockReturnValue("/projects/123");
    render(<NavList />);

    expect(screen.getByRole("link", { name: "Projects" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Dashboard" })).not.toHaveAttribute(
      "aria-current",
    );
  });
});
