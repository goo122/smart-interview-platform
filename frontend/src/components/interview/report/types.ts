export type RadarPoint = {
  label: string;
  value: number;
};

export type QaReview = {
  seq?: number | null;
  questionNumber?: string | null;
  question: string;
  answer: string;
  score: number | null;
  feedback?: string | null;
  isFollowUp?: boolean;
  followUpNeeded?: boolean;
  followUpCount?: number | null;
};

export type ReviewFeedback = {
  overallComment: string | null;
  highlights: string[];
  improvementTips: string[];
  nextActions: string[];
};
