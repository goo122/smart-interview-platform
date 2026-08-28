import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ROUTES } from "@/lib/constants";
import { Link } from "react-router-dom";
import { ArrowRight, Flame, Search, Tags } from "lucide-react";

const categories = [
  { name: "后端基础", count: 124 },
  { name: "系统设计", count: 68 },
  { name: "数据库", count: 92 },
  { name: "高并发", count: 57 },
  { name: "云原生", count: 41 },
  { name: "项目经验", count: 73 },
];

const questions = [
  {
    title: "如何设计一个高可用的缓存系统？",
    level: "中等",
    tag: "系统设计",
    hot: true,
  },
  {
    title: "你如何处理 Java GC 停顿对延迟的影响？",
    level: "高难",
    tag: "后端基础",
    hot: false,
  },
  {
    title: "数据库索引失效有哪些常见场景？",
    level: "基础",
    tag: "数据库",
    hot: true,
  },
  {
    title: "分布式事务有哪些主流方案？优缺点是什么？",
    level: "中等",
    tag: "高并发",
    hot: false,
  },
];

const tags = ["日更题", "高频", "面试官最爱", "新技术"];

export default function QuestionBankPage() {
  return (
    <div className="h-full overflow-y-auto bg-white">
      <div className="max-w-6xl mx-auto px-6 py-10 space-y-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold text-slate-900">面试题库</h1>
            <p className="text-sm text-slate-500">
              每日更新面试题库，覆盖最新趋势与真实场景。
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button variant="outline" className="rounded-full">
              今日更新 36 题
            </Button>
            <Button asChild className="rounded-full">
              <Link to={ROUTES.interviewIntro}>
                进入 AI 面试 <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>

        <Card className="p-6 border-slate-100">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-3 text-sm text-slate-500">
              <Search className="h-4 w-4" />
              <span>搜索题目、标签或方向</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {tags.map((tag) => (
                <Button
                  key={tag}
                  variant="outline"
                  size="sm"
                  className="rounded-full"
                >
                  {tag}
                </Button>
              ))}
            </div>
          </div>
        </Card>

        <div className="grid lg:grid-cols-[0.35fr_0.65fr] gap-6">
          <Card className="p-6 border-slate-100 space-y-4">
            <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
              <Tags className="h-4 w-4 text-slate-400" />
              题目方向
            </div>
            <Separator />
            <div className="space-y-3">
              {categories.map((item) => (
                <div
                  key={item.name}
                  className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2 text-sm text-slate-600"
                >
                  <span>{item.name}</span>
                  <span className="text-xs text-slate-400">{item.count}</span>
                </div>
              ))}
            </div>
          </Card>

          <div className="space-y-4">
            {questions.map((question) => (
              <Card key={question.title} className="p-5 border-slate-100">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-slate-900">
                        {question.title}
                      </p>
                      {question.hot && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-xs text-red-500">
                          <Flame className="h-3 w-3" />
                          热门
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 text-xs text-slate-500">
                      <span>难度：{question.level}</span>
                      <span>方向：{question.tag}</span>
                    </div>
                  </div>
                  <Button variant="outline" size="sm" className="rounded-full">
                    收藏
                  </Button>
                </div>
              </Card>
            ))}
            <Card className="p-5 border-dashed border-slate-200 text-center text-sm text-slate-500">
              更多题库将在每日凌晨更新
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
