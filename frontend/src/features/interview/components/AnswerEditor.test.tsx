import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AnswerEditor } from "@/features/interview/components/AnswerEditor";

describe("AnswerEditor", () => {
  it("blocks short answers and keeps the request id stable for retries", async () => {
    const submit = vi.fn<(_: string, requestId: string) => Promise<void>>().mockResolvedValue(undefined);
    const { rerender } = render(<AnswerEditor turnId="turn-1" onSubmit={submit} />);
    const input = screen.getByLabelText("回答 turn-1");
    fireEvent.change(input, { target: { value: "太短" } });
    fireEvent.click(screen.getByRole("button", { name: "提交回答" }));
    expect(submit).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("至少需要 10");

    fireEvent.change(input, { target: { value: "这是一个足够长的回答，用于验证幂等请求编号。" } });
    fireEvent.click(screen.getByRole("button", { name: "提交回答" }));
    await waitFor(() => expect(submit).toHaveBeenCalledTimes(1));
    const firstRequestId = submit.mock.calls[0]?.[1];
    rerender(<AnswerEditor turnId="turn-1" onSubmit={submit} />);
    fireEvent.change(screen.getByLabelText("回答 turn-1"), { target: { value: "再次提交同一轮回答内容" } });
    fireEvent.click(screen.getByRole("button", { name: "提交回答" }));
    await waitFor(() => expect(submit).toHaveBeenCalledTimes(2));
    expect(submit.mock.calls[1]?.[1]).toBe(firstRequestId);
  });
});

