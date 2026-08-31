import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import InterviewResumeUploadCard from "@/components/interview/InterviewResumeUploadCard";

describe("InterviewResumeUploadCard", () => {
  it("caps the question-generation stage before READY", () => {
    render(
      <InterviewResumeUploadCard
        fileInputRef={{ current: null }}
        isResumeUploading
        showUploadButton
        resumeUploadStage={2}
        resumeLocalFile={null}
        resumeFileUrl={null}
        resumeName="resume.pdf"
        resumePreviewError={null}
        resumeUploadError={null}
        interviewError={null}
        onResumeFileSelect={() => undefined}
        onOpenResume={() => undefined}
      />,
    );

    expect(screen.getByText("90%")).toBeTruthy();
    expect(screen.queryByText("100%")).toBeNull();
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe(
      "90",
    );
  });
});
