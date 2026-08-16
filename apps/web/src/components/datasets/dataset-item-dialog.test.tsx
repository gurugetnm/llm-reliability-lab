import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DatasetItemDialog } from "@/components/datasets/dataset-item-dialog";
import { api } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      createDatasetItem: vi.fn(),
      updateDatasetItem: vi.fn(),
    },
  };
});

const createDatasetItem = vi.mocked(api.createDatasetItem);
const updateDatasetItem = vi.mocked(api.updateDatasetItem);

beforeEach(() => {
  createDatasetItem.mockReset();
  updateDatasetItem.mockReset();
});

describe("DatasetItemDialog", () => {
  it("creates an item, parsing plain text input as a string", async () => {
    createDatasetItem.mockResolvedValue({
      id: "item-1",
      dataset_id: "d1",
      input: "What is TCP?",
      expected_output: null,
      metadata: null,
      position: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    const onSaved = vi.fn();
    const user = userEvent.setup();
    render(<DatasetItemDialog datasetId="d1" onSaved={onSaved} />);

    await user.click(screen.getByRole("button", { name: /add item/i }));
    await user.type(screen.getByLabelText(/^input$/i), "What is TCP?");
    await user.click(screen.getByRole("button", { name: /^add item$/i }));

    await waitFor(() =>
      expect(createDatasetItem).toHaveBeenCalledWith(
        "d1",
        expect.objectContaining({ input: "What is TCP?" }),
      ),
    );
    expect(onSaved).toHaveBeenCalled();
  });

  it("parses JSON-looking input as a structured value", async () => {
    createDatasetItem.mockResolvedValue({
      id: "item-2",
      dataset_id: "d1",
      input: { question: "hi" },
      expected_output: null,
      metadata: null,
      position: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    const user = userEvent.setup();
    render(<DatasetItemDialog datasetId="d1" onSaved={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /add item/i }));
    fireEvent.change(screen.getByLabelText(/^input$/i), {
      target: { value: '{"question": "hi"}' },
    });
    await user.click(screen.getByRole("button", { name: /^add item$/i }));

    await waitFor(() =>
      expect(createDatasetItem).toHaveBeenCalledWith(
        "d1",
        expect.objectContaining({ input: { question: "hi" } }),
      ),
    );
  });

  it("edits an existing item, pre-filling the form", async () => {
    updateDatasetItem.mockResolvedValue({
      id: "item-1",
      dataset_id: "d1",
      input: "Updated",
      expected_output: null,
      metadata: null,
      position: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    const onSaved = vi.fn();
    const user = userEvent.setup();
    render(
      <DatasetItemDialog
        datasetId="d1"
        item={{
          id: "item-1",
          dataset_id: "d1",
          input: "Original",
          expected_output: null,
          metadata: null,
          position: 0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }}
        open
        onOpenChange={vi.fn()}
        onSaved={onSaved}
      />,
    );

    const inputField = await screen.findByLabelText(/^input$/i);
    expect(inputField).toHaveValue("Original");

    await user.clear(inputField);
    await user.type(inputField, "Updated");
    await user.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(updateDatasetItem).toHaveBeenCalledWith("d1", "item-1",
      expect.objectContaining({ input: "Updated" }),
    ));
    expect(onSaved).toHaveBeenCalled();
  });
});
