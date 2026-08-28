import { toSuggestionList } from "@/hooks/interview/shared/interviewUtils";

type ResumeMetadataInput = {
  resumeScore?: number | null;
  interviewType?: string | null;
  suggestions?: Record<string, string> | null;
  resumeFileUrl?: string | null;
};

export const deriveResumeName = (fileUrl?: string | null) => {
  if (!fileUrl) return null;
  try {
    const parsed = new URL(fileUrl);
    const pathname = parsed.pathname.split("/").filter(Boolean).pop();
    return pathname ? decodeURIComponent(pathname) : null;
  } catch {
    const pathname = fileUrl.split("?")[0]?.split("/").filter(Boolean).pop();
    return pathname ? decodeURIComponent(pathname) : null;
  }
};

export const isPdfResumeFile = (file: File) =>
  file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");

export const buildResumeMetadata = ({
  resumeScore,
  interviewType,
  suggestions,
  resumeFileUrl,
}: ResumeMetadataInput) => ({
  resumeName: deriveResumeName(resumeFileUrl) || null,
  resumeScore: typeof resumeScore === "number" ? resumeScore : null,
  resumeInterviewType: interviewType || null,
  resumeSuggestions: toSuggestionList(suggestions ?? undefined),
});
