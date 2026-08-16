import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ModelSelect } from "@/components/playground/model-select";
import { llm } from "@/lib/llm/client";

vi.mock("@/lib/llm/client", () => ({
  llm: { listModels: vi.fn() },
}));

const listModels = vi.mocked(llm.listModels);

beforeEach(() => {
  listModels.mockReset();
});

describe("ModelSelect", () => {
  it("shows a loading skeleton while models are being fetched", () => {
    listModels.mockReturnValue(new Promise(() => {})); // never resolves
    const { container } = render(<ModelSelect value="" onChange={vi.fn()} />);
    expect(container.querySelector('[data-slot="skeleton"]')).toBeInTheDocument();
  });

  it("shows an empty state when Ollama has no models installed", async () => {
    listModels.mockResolvedValue([]);
    render(<ModelSelect value="" onChange={vi.fn()} />);

    expect(await screen.findByText(/no models installed/i)).toBeInTheDocument();
  });

  it("shows an unavailable state when the request fails", async () => {
    listModels.mockRejectedValue(new Error("Could not reach the API"));
    render(<ModelSelect value="" onChange={vi.fn()} />);

    expect(await screen.findByText(/ollama is unreachable/i)).toBeInTheDocument();
  });

  it("auto-selects the first model once models load, if nothing is selected", async () => {
    listModels.mockResolvedValue([
      { name: "llama3.1", provider: "ollama", size_bytes: null, modified_at: null, parameter_size: null, quantization: null, family: null, capabilities: null },
    ]);
    const onChange = vi.fn();
    render(<ModelSelect value="" onChange={onChange} />);

    await waitFor(() => expect(onChange).toHaveBeenCalledWith("llama3.1"));
  });

  it("lets the user pick a different installed model", async () => {
    listModels.mockResolvedValue([
      { name: "llama3.1", provider: "ollama", size_bytes: null, modified_at: null, parameter_size: null, quantization: null, family: null, capabilities: null },
      { name: "qwen2.5", provider: "ollama", size_bytes: null, modified_at: null, parameter_size: null, quantization: null, family: null, capabilities: null },
    ]);
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<ModelSelect value="llama3.1" onChange={onChange} />);

    await screen.findByRole("combobox");
    await user.click(screen.getByRole("combobox"));
    await user.click(await screen.findByText("qwen2.5"));

    expect(onChange).toHaveBeenCalledWith("qwen2.5");
  });
});
