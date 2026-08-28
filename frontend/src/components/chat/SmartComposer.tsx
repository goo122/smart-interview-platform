import { useEffect } from "react";
import SmartComposerView, {
  type SmartComposerViewProps,
} from "@/components/chat/SmartComposerView";
import {
  useAudioToText,
  useAudioToTextComposerBridge,
} from "@/hooks/useAudioToText";

export type SmartComposerProps = Omit<
  SmartComposerViewProps,
  "isRecording" | "onMicClick"
>;

export default function SmartComposer({
  value,
  onChange,
  onSend,
  placeholder = "今天我能怎么帮助你？",
  disabled = false,
  showDefaultLeading = true,
  showVoiceButton = true,
  leading,
  actions,
  className,
}: SmartComposerProps) {
  const { isRecording, transcription, error, startRecording, stopRecording } =
    useAudioToText();

  useAudioToTextComposerBridge({
    enabled: showVoiceButton,
    isRecording,
    transcription,
    value,
    onChange,
  });

  useEffect(() => {
    if (error) {
      console.error("Audio recording error:", error);
    }
  }, [error]);

  const handleMicClick = (event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    if (disabled) return;

    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  return (
    <SmartComposerView
      value={value}
      onChange={onChange}
      onSend={onSend}
      placeholder={placeholder}
      disabled={disabled}
      showDefaultLeading={showDefaultLeading}
      showVoiceButton={showVoiceButton}
      leading={leading}
      actions={actions}
      className={className}
      isRecording={isRecording}
      onMicClick={handleMicClick}
    />
  );
}
