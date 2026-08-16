import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ImportDatasetDialog } from "@/components/datasets/import-dataset-dialog";
import { api, ApiError } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { ...actual.api, importDatasetItems: vi.fn() },
  };
});

const importDatasetItems = vi.mocked(api.importDatasetItems);

beforeEach(() => {
  importDatasetItems.mockReset();
});

describe("ImportDatasetDialog", () => {
  it("imports JSONL content and reports the dataset back", async () => {
    importDatasetItems.mockResolvedValue({
      imported_count: 2,
      dataset: {
        id: "d1",
        project_id: "p1",
        name: "Set",
        description: null,
        version: 2,
        item_count: 2,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    });
    const onImported = vi.fn();
    const user = userEvent.setup();
    render(<ImportDatasetDialog datasetId="d1" onImported={onImported} />);

    await user.click(screen.getByRole("button", { name: /^import$/i }));
    const dialog = within(screen.getByRole("dialog"));
    fireEvent.change(screen.getByPlaceholderText(/input.*tcp/i), {
      target: { value: '{"input":"a"}\n{"input":"b"}' },
    });
    await user.click(dialog.getByRole("button", { name: /^import$/i }));

    await waitFor(() =>
      expect(importDatasetItems).toHaveBeenCalledWith("d1", "jsonl", '{"input":"a"}\n{"input":"b"}'),
    );
    expect(onImported).toHaveBeenCalled();
  });

  it("shows per-line validation errors when the import is rejected", async () => {
    importDatasetItems.mockRejectedValue(
      new ApiError("Dataset import failed validation", 422, {
        detail: "Dataset import failed validation",
        errors: [{ line: 17, message: "missing required field: input" }],
      }),
    );
    const user = userEvent.setup();
    render(<ImportDatasetDialog datasetId="d1" onImported={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /^import$/i }));
    const dialog = within(screen.getByRole("dialog"));
    fireEvent.change(screen.getByPlaceholderText(/input.*tcp/i), { target: { value: "{}" } });
    await user.click(dialog.getByRole("button", { name: /^import$/i }));

    expect(await screen.findByText(/line 17/i)).toBeInTheDocument();
    expect(screen.getByText(/missing required field: input/i)).toBeInTheDocument();
  });
});
