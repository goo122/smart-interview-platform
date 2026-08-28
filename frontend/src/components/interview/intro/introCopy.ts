export type IntroHighlight = {
  title: string;
  description: string;
};

export type InterviewIntroLocale = "zh-CN" | "en-US";

type InterviewIntroCopy = {
  badge: string;
  title: string;
  description: string;
  continueButton: string;
  startButton: string;
  reportButton: string;
  processTitle: string;
  processUpdateTitle: string;
  processUpdateDescription: string;
  sampleRadarTitle: string;
  highlights: IntroHighlight[];
  steps: string[];
  mockRadarPoints: Array<{
    label: string;
    value: number;
  }>;
};

const INTRO_COPY_BY_LOCALE: Record<InterviewIntroLocale, InterviewIntroCopy> = {
  "zh-CN": {
    badge: "AI 面试评估",
    title: "用一条清晰、可控的流程复盘你的面试表现",
    description:
      "从简历分析开始，进入逐题实战练习，最后生成可追溯、可恢复的面试报告。",
    continueButton: "继续上次面试",
    startButton: "进入面试室",
    reportButton: "查看示例报告",
    processTitle: "面试流程",
    processUpdateTitle: "题库每日动态更新",
    processUpdateDescription:
      "覆盖新技术栈与真实面试场景，持续保持命中率。",
    sampleRadarTitle: "示例雷达图",
    highlights: [
      {
        title: "简历得分",
        description: "基于岗位与能力模型进行多维打分",
      },
      {
        title: "回答得分",
        description: "逻辑、结构、深度与表达一致评估",
      },
      {
        title: "能力雷达",
        description: "技术深度、沟通、项目、临场综合画像",
      },
      {
        title: "题库日更",
        description: "每日更新题库，覆盖最新趋势与场景",
      },
    ],
    steps: [
      "上传简历与岗位方向",
      "进入面试室，AI 逐题追问",
      "生成表现报告与提升建议",
    ],
    mockRadarPoints: [
      { label: "技术深度", value: 84 },
      { label: "项目表达", value: 76 },
      { label: "沟通协作", value: 81 },
      { label: "临场反应", value: 72 },
      { label: "题目分析", value: 88 },
    ],
  },
  "en-US": {
    badge: "AI interview evaluation",
    title: "Review your interview performance with a clean, guided flow",
    description:
      "Start from resume analysis, continue with question-by-question practice, and finish with a report that keeps your session state isolated and recoverable.",
    continueButton: "Continue last interview",
    startButton: "Enter interview room",
    reportButton: "View sample report",
    processTitle: "Interview flow",
    processUpdateTitle: "Daily question updates",
    processUpdateDescription:
      "Stay aligned with current stacks and realistic interview scenarios.",
    sampleRadarTitle: "Sample radar chart",
    highlights: [
      {
        title: "Resume score",
        description: "Multi-dimensional scoring based on role and capability models",
      },
      {
        title: "Answer score",
        description: "Evaluate logic, structure, depth, and expression together",
      },
      {
        title: "Capability radar",
        description: "Technical depth, communication, projects, and live response",
      },
      {
        title: "Fresh question bank",
        description: "Updated daily with new trends and interview scenarios",
      },
    ],
    steps: [
      "Upload your resume and target role",
      "Enter the room and answer AI-guided questions",
      "Receive a report with actionable suggestions",
    ],
    mockRadarPoints: [
      { label: "Technical depth", value: 84 },
      { label: "Project delivery", value: 76 },
      { label: "Communication", value: 81 },
      { label: "Composure", value: 72 },
      { label: "Problem analysis", value: 88 },
    ],
  },
};

export const DEFAULT_INTERVIEW_INTRO_LOCALE: InterviewIntroLocale = "zh-CN";

export const getInterviewIntroCopy = (
  locale: InterviewIntroLocale = DEFAULT_INTERVIEW_INTRO_LOCALE,
) => {
  return INTRO_COPY_BY_LOCALE[locale] ?? INTRO_COPY_BY_LOCALE["zh-CN"];
};
