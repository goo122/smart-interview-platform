import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { HTMLAttributes, ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import InterviewSketchpadSheet from "@/components/interview/sketchpad/InterviewSketchpadSheet";

const useAudioToTextMock = vi.fn();
const getCurrentQuestionMock = vi.fn();
const TRANSCRIPTION_RESULT = "first transcription result";
const EXISTING_TRANSCRIPTION = "existing transcription result";
const MERGED_TRANSCRIPTION = `${EXISTING_TRANSCRIPTION}\n\n${TRANSCRIPTION_RESULT}`;

vi.mock("@/hooks/useAudioToText", () => ({
  useAudioToText: () => useAudioToTextMock(),
}));

vi.mock("@/services/interviewService", () => ({
  interviewService: {
    getCurrentQuestion: (...args: unknown[]) => getCurrentQuestionMock(...args),
  },
}));

vi.mock("@/components/ui/sheet", () => ({
  Sheet: ({
    open,
    onOpenChange,
    children,
  }: {
    open: boolean;
    onOpenChange?: (open: boolean) => void;
    children: ReactNode;
  }) =>
    open ? (
      <div>
        <button type="button" onClick={() => onOpenChange?.(false)}>
          close-sheet
        </button>
        {children}
      </div>
    ) : null,
  SheetContent: ({ children, ...props }: HTMLAttributes<HTMLDivElement>) => (
    <div
      {...Object.fromEntries(
        Object.entries(props).filter(([key]) => key !== "onInteractOutside"),
      )}
    >
      {children}
    </div>
  ),
  SheetHeader: ({ children, ...props }: HTMLAttributes<HTMLDivElement>) => (
    <div {...props}>{children}</div>
  ),
  SheetTitle: ({ children, ...props }: HTMLAttributes<HTMLDivElement>) => (
    <div {...props}>{children}</div>
  ),
  SheetDescription: ({
    children,
    ...props
  }: HTMLAttributes<HTMLParagraphElement>) => <p {...props}>{children}</p>,
}));

type MockAudioState = {
  isRecording: boolean;
  transcription: string;
  error: string | null;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
};

const createAudioState = (
  overrides: Partial<MockAudioState> = {},
): MockAudioState => ({
  isRecording: false,
  transcription: "",
  error: null,
  startRecording: vi.fn(async () => undefined),
  stopRecording: vi.fn(),
  ...overrides,
});

const createQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

type RenderSheetOptions = {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  sessionId?: string | null;
  currentQuestionNumber?: string | null;
  currentQuestionContent?: string | null;
  onInsertNotes?: (notes: string) => void;
};

const renderSheet = ({
  open = true,
  onOpenChange = vi.fn(),
  sessionId = "session-1",
  currentQuestionNumber = null,
  currentQuestionContent = null,
  onInsertNotes = vi.fn(),
}: RenderSheetOptions = {}) => {
  const queryClient = createQueryClient();

  return render(
    <QueryClientProvider client={queryClient}>
      <InterviewSketchpadSheet
        open={open}
        onOpenChange={onOpenChange}
        sessionId={sessionId}
        currentQuestionNumber={currentQuestionNumber}
        currentQuestionContent={currentQuestionContent}
        onInsertNotes={onInsertNotes}
      />
    </QueryClientProvider>,
  );
};

describe("InterviewSketchpadSheet", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
    getCurrentQuestionMock.mockResolvedValue(null);
  });

  it("hydrates the persisted transcription buffer for the current session", async () => {
    window.localStorage.setItem(
      "interview-sketchpad:v2:session-1",
      JSON.stringify({
        notes: "",
        transcriptionBuffer: TRANSCRIPTION_RESULT,
        transcriptionCommitted: true,
        updatedAt: Date.now(),
      }),
    );

    useAudioToTextMock.mockReturnValue(
      createAudioState({
        isRecording: false,
        transcription: "",
      }),
    );

    renderSheet();

    await waitFor(() => {
      const textareas = screen.getAllByRole("textbox");
      expect((textareas[1] as HTMLTextAreaElement).value).toBe(
        TRANSCRIPTION_RESULT,
      );
    });
  });

  it("hydrates an existing merged transcription buffer from local storage", async () => {
    window.localStorage.setItem(
      "interview-sketchpad:v2:session-1",
      JSON.stringify({
        notes: "",
        transcriptionBuffer: MERGED_TRANSCRIPTION,
        transcriptionCommitted: true,
        updatedAt: Date.now(),
      }),
    );

    useAudioToTextMock.mockReturnValue(
      createAudioState({
        isRecording: false,
        transcription: "",
      }),
    );

    renderSheet();

    await waitFor(() => {
      const textareas = screen.getAllByRole("textbox");
      expect((textareas[1] as HTMLTextAreaElement).value).toBe(
        MERGED_TRANSCRIPTION,
      );
    });
  });

  it("commits the live transcription and stops recording when closing the sheet", async () => {
    const stopRecording = vi.fn();
    const onOpenChange = vi.fn();

    useAudioToTextMock.mockReturnValue(
      createAudioState({
        isRecording: true,
        transcription: TRANSCRIPTION_RESULT,
        stopRecording,
      }),
    );

    renderSheet({
      onOpenChange,
    });

    fireEvent.click(screen.getByRole("button", { name: "close-sheet" }));

    await waitFor(() => {
      expect(stopRecording).toHaveBeenCalledTimes(1);
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });

    await waitFor(() => {
      const persisted = window.localStorage.getItem(
        "interview-sketchpad:v2:session-1",
      );
      expect(persisted).toContain(TRANSCRIPTION_RESULT);
    });
  });

  it("prefers the server question content over the page fallback", async () => {
    getCurrentQuestionMock.mockResolvedValue({
      questionNumber: "9",
      questionContent: "Server question",
      finished: false,
    });

    renderSheet({
      currentQuestionNumber: "3",
      currentQuestionContent: "Fallback question",
    });

    await waitFor(() => {
      expect(screen.getByText("Server question")).toBeTruthy();
    });

    expect(screen.queryByText("Fallback question")).toBeNull();
  });

  it("does not render the next question content after the interview is finished", async () => {
    getCurrentQuestionMock.mockResolvedValue({
      questionNumber: "10",
      questionContent: "Finished server question",
      finished: true,
    });

    renderSheet({
      currentQuestionContent: "Fallback question",
    });

    await waitFor(() => {
      expect(screen.queryByText("Finished server question")).toBeNull();
      expect(screen.queryByText("Fallback question")).toBeNull();
    });
  });
});
