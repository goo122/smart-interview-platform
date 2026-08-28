import { useCallback, useEffect, useRef, useState } from "react";

export function useInterviewResumePreviewState() {
  const [resumeName, setResumeName] = useState<string | null>(null);
  const [resumeFileUrl, setResumeFileUrl] = useState<string | null>(null);
  const [resumeRemoteFile, setResumeRemoteFile] = useState<File | null>(null);
  const [resumeLocalFile, setResumeLocalFile] = useState<File | null>(null);
  const [resumePreviewError, setResumePreviewError] = useState<string | null>(
    null,
  );
  const [numPages, setNumPages] = useState(1);

  const previewObjectUrlRef = useRef<string | null>(null);

  const replaceRemoteResumePreview = useCallback(
    (
      nextBlob: Blob | null,
      nextUrl: string | null,
      nextName?: string | null,
    ) => {
      const previousUrl = previewObjectUrlRef.current;
      if (previousUrl && previousUrl !== nextUrl) {
        URL.revokeObjectURL(previousUrl);
      }

      previewObjectUrlRef.current = nextUrl;

      if (nextBlob) {
        setResumeRemoteFile(
          new File([nextBlob], nextName || "resume.pdf", {
            type: "application/pdf",
          }),
        );
      } else {
        setResumeRemoteFile(null);
      }

      setResumeFileUrl(nextUrl);
    },
    [],
  );

  const clearRemoteResumePreview = useCallback(() => {
    replaceRemoteResumePreview(null, null);
  }, [replaceRemoteResumePreview]);

  const clearPreviewState = useCallback(() => {
    setResumeName(null);
    clearRemoteResumePreview();
    setResumeLocalFile(null);
    setResumeRemoteFile(null);
    setResumePreviewError(null);
    setNumPages(1);
  }, [clearRemoteResumePreview]);

  const handleResumePreviewLoadSuccess = useCallback((nextNumPages: number) => {
    setNumPages(nextNumPages);
    setResumePreviewError(null);
  }, []);

  const handleResumePreviewLoadError = useCallback((message: string) => {
    setResumePreviewError(message);
  }, []);

  useEffect(
    () => () => {
      const previousUrl = previewObjectUrlRef.current;
      if (previousUrl) {
        URL.revokeObjectURL(previousUrl);
      }
    },
    [],
  );

  return {
    resumeName,
    setResumeName,
    resumeFileUrl,
    resumeRemoteFile,
    resumeLocalFile,
    setResumeLocalFile,
    resumePreviewError,
    setResumePreviewError,
    numPages,
    setNumPages,
    resumePreviewSource: resumeLocalFile || resumeRemoteFile || undefined,
    resumeOpenPreviewUrl: resumeFileUrl || null,
    replaceRemoteResumePreview,
    clearRemoteResumePreview,
    clearPreviewState,
    handleResumePreviewLoadSuccess,
    handleResumePreviewLoadError,
  };
}
