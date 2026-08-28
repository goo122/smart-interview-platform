import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import RadarChart from "@/features/report/components/RadarChart";

const scores = [
  { dimension: "technical" as const, score: 86 },
  { dimension: "relevance" as const, score: 78 },
  { dimension: "clarity" as const, score: 92 },
  { dimension: "depth" as const, score: 71 },
];

describe("RadarChart", () => {
  it("renders the four dimensions with a text alternative", () => {
    render(<RadarChart scores={scores} />);

    expect(screen.getByRole("img", { name: "面试能力雷达图" })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "面试能力维度分数" })).toBeInTheDocument();
    expect(screen.getAllByText("技术能力").length).toBeGreaterThan(0);
    expect(screen.getByText("86 / 100")).toBeInTheDocument();
    expect(screen.getAllByText("表达清晰度").length).toBeGreaterThan(0);
  });

  it("does not turn a missing dimension into a zero score", () => {
    render(<RadarChart scores={scores.map((item, index) => index === 2 ? { ...item, score: null } : item)} />);

    expect(screen.getByText("评分维度数据异常")).toBeInTheDocument();
    expect(screen.getAllByText("数据异常").length).toBeGreaterThan(0);
    expect(document.querySelector(".radar-value")).not.toBeInTheDocument();
  });
});
