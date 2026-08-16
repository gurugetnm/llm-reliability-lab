import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DatasetsPage from "@/app/datasets/page";
import { api } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      listDatasets: vi.fn(),
      listProjects: vi.fn(),
    },
  };
});

const listDatasets = vi.mocked(api.listDatasets);
const listProjects = vi.mocked(api.listProjects);

beforeEach(() => {
  listDatasets.mockReset();
  listProjects.mockReset();
  listProjects.mockResolvedValue([]);
});

describe("DatasetsPage", () => {
  it("shows a loading skeleton while datasets are being fetched", () => {
    listDatasets.mockReturnValue(new Promise(() => {}));
    const { container } = render(<DatasetsPage />);
    expect(container.querySelector('[data-slot="skeleton"]')).toBeInTheDocument();
  });

  it("shows an empty state when there are no datasets", async () => {
    listDatasets.mockResolvedValue([]);
    render(<DatasetsPage />);

    expect(await screen.findByText(/no datasets yet/i)).toBeInTheDocument();
  });

  it("shows an error state with a retry action when the request fails", async () => {
    listDatasets.mockRejectedValue(new Error("Could not reach the API"));
    render(<DatasetsPage />);

    expect(await screen.findByText(/couldn't reach the api/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("renders dataset cards with name, version, and item count", async () => {
    listDatasets.mockResolvedValue([
      {
        id: "1",
        project_id: "p1",
        name: "Q&A set",
        description: "A test set",
        version: 3,
        item_count: 42,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ]);
    render(<DatasetsPage />);

    expect(await screen.findByText("Q&A set")).toBeInTheDocument();
    expect(screen.getByText("v3")).toBeInTheDocument();
    expect(screen.getByText(/42 items/)).toBeInTheDocument();
  });
});
