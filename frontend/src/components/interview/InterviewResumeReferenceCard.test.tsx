import { render, screen } from "@testing-library/react";
import type { HTMLAttributes, ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import InterviewResumeReferenceCard from "@/components/interview/InterviewResumeReferenceCard";

const previewContentSpy = vi.fn();

vi.mock("framer-motion", () => ({
  motion: {
    div: ({
      children,
      ...props
    }: HTMLAttributes<HTMLDivElement> & { children?: ReactNode }) => (
      <div {...props}>{children}</div>
    ),
  },
}));

vi.mock("@/components/interview/InterviewResumePreviewContent", () => ({
  default: (props: Record<string, unknown>) => {
    previewContentSpy(props);
    return <div data-testid="resume-preview-content" />;
  },
}));

describe("InterviewResumeReferenceCard", () => {
  beforeEach(() => {
    previewContentSpy.mockClear();
  });

  it("renders the inline pdf preview immediately when a source is available", () => {
    render(
      <InterviewResumeReferenceCard
        open
        resumeName="resume.pdf"
        resumePreviewSource="blob:resume"
        resumePreviewError={null}
        resumeOpenPreviewUrl="blob:resume"
        numPages={3}
        onLoadSuccess={vi.fn()}
        onLoadError={vi.fn()}
      />,
    );

    expect(screen.getByTestId("resume-preview-content")).toBeTruthy();
    expect(previewContentSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        numPages: 3,
        resumePreviewSource: "blob:resume",
      }),
    );
  });

  it("shows the inline preview again after remounting the card", () => {
    const firstRender = render(
      <InterviewResumeReferenceCard
        open
        resumeName="resume.pdf"
        resumePreviewSource="blob:resume"
        resumePreviewError={null}
        resumeOpenPreviewUrl="blob:resume"
        numPages={2}
        onLoadSuccess={vi.fn()}
        onLoadError={vi.fn()}
      />,
    );

    expect(screen.getByTestId("resume-preview-content")).toBeTruthy();

    firstRender.unmount();

    render(
      <InterviewResumeReferenceCard
        open
        resumeName="resume.pdf"
        resumePreviewSource="blob:resume"
        resumePreviewError={null}
        resumeOpenPreviewUrl="blob:resume"
        numPages={2}
        onLoadSuccess={vi.fn()}
        onLoadError={vi.fn()}
      />,
    );

    expect(screen.getByTestId("resume-preview-content")).toBeTruthy();
  });
});
