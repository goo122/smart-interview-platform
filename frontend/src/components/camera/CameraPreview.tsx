import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import { cn } from "@/lib/utils";
import { normalizeMediaError, type MediaError } from "@/lib/media";

export type CameraPreviewHandle = {
  captureFrame: (options?: {
    type?: string;
    quality?: number;
  }) => Promise<Blob | null>;
};

type CameraPreviewProps = {
  isOpen: boolean;
  className?: string;
  videoConstraints?: MediaTrackConstraints;
  muted?: boolean;
  onError?: (error: MediaError) => void;
};

const CameraPreview = forwardRef<CameraPreviewHandle, CameraPreviewProps>(
  function CameraPreview(
    {
      isOpen,
      className,
      videoConstraints,
      muted = true,
      onError,
    }: CameraPreviewProps,
    ref,
  ) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const canvasRef = useRef<HTMLCanvasElement | null>(null);

    useImperativeHandle(
      ref,
      () => ({
        captureFrame: (options) => {
          const video = videoRef.current;
          if (
            !video ||
            video.videoWidth <= 0 ||
            video.videoHeight <= 0 ||
            video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA
          ) {
            return Promise.resolve(null);
          }

          const canvas = canvasRef.current || document.createElement("canvas");
          canvasRef.current = canvas;
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;

          const context = canvas.getContext("2d");
          if (!context) {
            return Promise.resolve(null);
          }

          context.drawImage(video, 0, 0, canvas.width, canvas.height);
          return new Promise<Blob | null>((resolve) => {
            canvas.toBlob(
              (blob) => resolve(blob),
              options?.type || "image/jpeg",
              options?.quality ?? 0.86,
            );
          });
        },
      }),
      [],
    );

    useEffect(() => {
      const stopStream = () => {
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((track) => track.stop());
          streamRef.current = null;
        }
        if (videoRef.current) {
          videoRef.current.srcObject = null;
        }
      };

      if (!isOpen) {
        stopStream();
        return;
      }

      let cancelled = false;

      const start = async () => {
        try {
          if (!navigator.mediaDevices?.getUserMedia) {
            onError?.({ kind: "not_supported" });
            return;
          }
          const stream = await navigator.mediaDevices.getUserMedia({
            video: videoConstraints ?? { facingMode: "user" },
          });
          if (cancelled) {
            stream.getTracks().forEach((track) => track.stop());
            return;
          }
          streamRef.current = stream;
          if (videoRef.current) {
            videoRef.current.srcObject = stream;
            const play = videoRef.current.play?.();
            if (play) {
              await play.catch(() => undefined);
            }
          }
        } catch (error) {
          onError?.(normalizeMediaError(error));
          stopStream();
        }
      };

      void start();

      return () => {
        cancelled = true;
        stopStream();
      };
    }, [isOpen, videoConstraints, onError]);

    return (
      <video
        ref={videoRef}
        autoPlay
        muted={muted}
        playsInline
        className={cn("h-full w-full object-cover", className)}
      />
    );
  },
);

export default CameraPreview;
