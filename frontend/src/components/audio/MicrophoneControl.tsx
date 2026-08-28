import { Mic } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { type MediaError } from "@/lib/media";
import { useMicrophoneRecording } from "@/hooks/audio/useMicrophoneRecording";

type MicrophoneControlProps = {
  className?: string;
  audioConstraints?: MediaTrackConstraints;
  onStart?: (stream: MediaStream) => void;
  onStop?: () => void;
  onError?: (error: MediaError) => void;
  disabled?: boolean;
};

export default function MicrophoneControl({
  className,
  audioConstraints,
  onStart,
  onStop,
  onError,
  disabled,
}: MicrophoneControlProps) {
  const { isRecording, level, toggle } = useMicrophoneRecording({
    audioConstraints,
    onStart,
    onStop,
    onError,
  });

  const handleToggle = () => {
    if (disabled) return;
    toggle();
  };

  return (
    <Button
      variant={isRecording ? "destructive" : "ghost"}
      size="icon"
      className={cn(
        "relative h-10 w-10 transition-colors overflow-hidden",
        className,
      )}
      onClick={handleToggle}
      disabled={disabled}
      type="button"
    >
      {isRecording && (
        <>
          <span
            className="absolute inset-0 rounded-full border border-red-500/40 animate-ping"
            style={{ animationDuration: "1.6s" }}
          />
          <span
            className="absolute inset-0 rounded-full border border-red-500/30 animate-ping"
            style={{ animationDuration: "1.6s", animationDelay: "0.4s" }}
          />
          <span
            className="absolute inset-0 rounded-full bg-red-500/20"
            style={{ transform: `scale(${1 + level * 0.8})` }}
          />
        </>
      )}
      <Mic className="h-5 w-5 relative z-10" />
    </Button>
  );
}
