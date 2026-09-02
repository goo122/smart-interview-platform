export const MARKETING_HERO_VIDEO_SRC = "/videos/home-bg.mp4";

export const MARKETING_TEXT = {
  heroTitle: "寻知",
  heroSubtitle: "拟真AI面试场景，给你一次不一样的体验，帮你更快取得理想offer",
  startNow: "立即体验",
  advantagesTitle: "平台优势",
  workflowTitle: "使用流程",
  outcomeTitle: "你将获得",
} as const;

export const MARKETING_ADVANTAGES = [
  {
    icon: "target",
    title: "岗位定制问题",
    description: "按岗位方向与技能栈生成高相关问题，覆盖真实面试高频场景。",
  },
  {
    icon: "brain",
    title: "实时追问与反馈",
    description: "模拟面试官追问逻辑，逐轮指出表达与结构问题，给出改进建议。",
  },
  {
    icon: "resume",
    title: "简历与回答联动分析",
    description: "从简历亮点到回答表现做统一评分，帮你快速定位短板。",
  },
  {
    icon: "report",
    title: "可复盘的面试报告",
    description: "自动沉淀评估记录与能力雷达，清晰看到每次训练的提升轨迹。",
  },
] as const;

export const MARKETING_WORKFLOW = [
  "上传简历并选择目标岗位方向",
  "进入 AI 面试评估页开始模拟问答",
  "根据反馈优化表达并继续练习",
  "生成面试报告并复盘提升点",
] as const;

export const MARKETING_OUTCOMES = [
  "清晰的面试表现评分与改进方向",
  "可追溯的问答记录与复盘报告",
  "针对目标岗位的持续训练节奏",
] as const;
