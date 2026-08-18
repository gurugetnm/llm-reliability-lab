import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EvaluatorConfigFields } from "@/components/evaluations/evaluator-config-fields";

describe("EvaluatorConfigFields", () => {
  it("renders exact_match toggles and reports changes", () => {
    const onChange = vi.fn();
    render(
      <EvaluatorConfigFields evaluatorType="exact_match" config={{}} onChange={onChange} />,
    );

    const toggle = screen.getByRole("switch", { name: /case sensitive/i });
    expect(toggle).toBeInTheDocument();
    fireEvent.click(toggle);
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ case_sensitive: true }));
  });

  it("renders contains' required terms and threshold", () => {
    render(
      <EvaluatorConfigFields
        evaluatorType="contains"
        config={{ required_terms: ["SYN", "ACK"], threshold: 0.5 }}
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByLabelText(/required terms/i)).toHaveValue("SYN\nACK");
    expect(screen.getByText("0.50")).toBeInTheDocument();
  });

  it("renders semantic_similarity's threshold slider", () => {
    render(
      <EvaluatorConfigFields
        evaluatorType="semantic_similarity"
        config={{ threshold: 0.8 }}
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByText("0.80")).toBeInTheDocument();
    expect(screen.getByText(/local embedding model/i)).toBeInTheDocument();
  });

  it("renders llm_judge's model, scale, threshold, and criteria fields", () => {
    render(
      <EvaluatorConfigFields
        evaluatorType="llm_judge"
        config={{ judge_model: "qwen3", score_scale: 5 }}
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByLabelText(/judge model/i)).toHaveValue("qwen3");
    expect(screen.getByLabelText(/score scale/i)).toHaveValue(5);
    expect(screen.getByLabelText(/criteria/i)).toHaveValue("accuracy\nrelevance\ncompleteness");
  });

  it("updates required_terms as a trimmed, non-empty line list", () => {
    const onChange = vi.fn();
    render(<EvaluatorConfigFields evaluatorType="contains" config={{}} onChange={onChange} />);

    fireEvent.change(screen.getByLabelText(/required terms/i), {
      target: { value: "SYN\n ACK \n\nFIN" },
    });
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ required_terms: ["SYN", "ACK", "FIN"] }),
    );
  });

  it("renders nothing for an unknown evaluator type", () => {
    const { container } = render(
      <EvaluatorConfigFields evaluatorType="not_a_real_evaluator" config={{}} onChange={vi.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
