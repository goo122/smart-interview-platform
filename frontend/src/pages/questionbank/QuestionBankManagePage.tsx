import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { ROUTES } from "@/lib/constants";
import { Link } from "react-router-dom";
import { ArrowRight, Filter, Sparkles } from "lucide-react";

const directions = [
  { name: "后端基础", count: 96 },
  { name: "系统设计", count: 54 },
  { name: "数据库", count: 71 },
  { name: "高并发", count: 43 },
  { name: "云原生", count: 28 },
];

const aiBatches = [
  { id: "B-1023", source: "LLM · 后端基础", status: "待审核", count: 38 },
  { id: "B-1022", source: "抓取 · 大厂面经", status: "已通过", count: 24 },
  { id: "B-1021", source: "LLM · 系统设计", status: "待审核", count: 42 },
];

const reviewQueue = [
  {
    title: "如何设计一个高可用的消息队列？",
    tags: ["系统设计", "高频"],
    level: "中等",
    source: "LLM · 系统设计",
  },
  {
    title: "数据库索引失效的常见场景有哪些？",
    tags: ["数据库"],
    level: "基础",
    source: "抓取 · 面经",
  },
  {
    title: "如何处理 Redis 缓存穿透与击穿？",
    tags: ["后端基础", "高频"],
    level: "中等",
    source: "LLM · 后端基础",
  },
];

export default function QuestionBankManagePage() {
  return (
    <div className="h-full overflow-y-auto bg-white">
      <div className="max-w-6xl mx-auto px-6 py-10 space-y-8">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">
              面试题库管理
            </h1>
            <p className="text-sm text-slate-500">
              AI 自动采集 + 人工筛选，保证题库质量与时效。
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button asChild variant="outline" className="rounded-full">
              <Link to={ROUTES.questionBank}>返回题库</Link>
            </Button>
            <Button className="rounded-full">新建采集任务</Button>
          </div>
        </div>

        <div className="grid lg:grid-cols-[0.4fr_0.6fr] gap-6">
          <Card className="p-6 border-slate-100 space-y-4">
            <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
              <Sparkles className="h-4 w-4 text-slate-400" />
              AI 采集任务
            </div>
            <Separator />
            <div className="space-y-3">
              <Input placeholder="输入采集方向，如：系统设计 / 分布式" />
              <Input placeholder="关键词过滤，如：缓存、数据库" />
              <div className="flex gap-2">
                <Button className="rounded-full">开始采集</Button>
                <Button variant="outline" className="rounded-full">
                  保存模板
                </Button>
              </div>
              <p className="text-xs text-slate-500">
                AI 会自动汇总候选题目，并进入人工审核队列。
              </p>
            </div>
          </Card>

          <Card className="p-6 border-slate-100 space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-slate-900">采集批次</p>
              <Button variant="outline" size="sm" className="rounded-full">
                查看全部
              </Button>
            </div>
            <div className="space-y-3">
              {aiBatches.map((batch) => (
                <div
                  key={batch.id}
                  className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2 text-sm"
                >
                  <div>
                    <p className="text-slate-700">{batch.source}</p>
                    <p className="text-xs text-slate-400">
                      {batch.id} · {batch.count} 题
                    </p>
                  </div>
                  <span className="text-xs text-slate-500">{batch.status}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>

        <Card className="p-6 border-slate-100 space-y-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
              <Filter className="h-4 w-4 text-slate-400" />
              待审核队列
            </div>
            <div className="flex flex-wrap gap-2">
              {directions.map((item) => (
                <Button
                  key={item.name}
                  variant="outline"
                  size="sm"
                  className="rounded-full"
                >
                  {item.name} · {item.count}
                </Button>
              ))}
            </div>
          </div>
          <Separator />
          <div className="space-y-4">
            {reviewQueue.map((item) => (
              <div
                key={item.title}
                className="rounded-lg border border-slate-100 p-4"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-slate-900">
                      {item.title}
                    </p>
                    <div className="flex flex-wrap gap-2 text-xs text-slate-500">
                      <span>难度：{item.level}</span>
                      <span>来源：{item.source}</span>
                      {item.tags.map((tag) => (
                        <span
                          key={tag}
                          className="rounded-full bg-slate-50 px-2 py-0.5 text-slate-500"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="rounded-full"
                    >
                      驳回
                    </Button>
                    <Button size="sm" className="rounded-full">
                      通过
                    </Button>
                  </div>
                </div>
                <div className="mt-3 flex items-center justify-end gap-2 text-xs text-slate-400">
                  <span>编辑详情</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
