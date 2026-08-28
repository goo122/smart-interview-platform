import { useCallback, useState } from "react";
import { type MediaError } from "@/lib/media";

export type CameraErrorCopy = {
  title: string;
  description: string;
} | null;

const getMediaErrorCopy = (error: MediaError | null): CameraErrorCopy => {
  if (!error) return null;
  switch (error.kind) {
    case "permission_denied":
      return {
        title: "Camera permission denied",
        description:
          "Please allow camera access in browser settings and retry.",
      };
    case "not_found":
      return {
        title: "No camera detected",
        description: "Check your device connection or system camera settings.",
      };
    case "not_readable":
      return {
        title: "Camera is busy",
        description: "Close other apps using the camera and try again.",
      };
    case "overconstrained":
      return {
        title: "Camera constraints not supported",
        description: "Adjust camera constraints and retry.",
      };
    case "not_supported":
      return {
        title: "Camera not supported in this environment",
        description: "Use HTTPS or localhost to access camera APIs.",
      };
    default:
      return {
        title: "Failed to initialize camera",
        description: "Please retry later or switch browser.",
      };
  }
};

export function useInterviewCameraState() {
  const [isCameraOpen, setIsCameraOpen] = useState(true);
  const [isCameraExpanded, setIsCameraExpanded] = useState(false);
  const [cameraError, setCameraError] = useState<MediaError | null>(null);

  const handleCameraError = useCallback((error: MediaError) => {
    setCameraError(error);
  }, []);

  const handleToggleCamera = useCallback(() => {
    setCameraError(null);
    setIsCameraOpen((prev) => !prev);
  }, []);

  const handleToggleCameraExpanded = useCallback(() => {
    setIsCameraExpanded((prev) => !prev);
  }, []);

  return {
    isCameraOpen,
    isCameraExpanded,
    cameraErrorCopy: getMediaErrorCopy(cameraError),
    handleCameraError,
    handleToggleCamera,
    handleToggleCameraExpanded,
  };
}
