# 面试流程恢复与展示延迟验证（2026-09-05）

本轮范围：完整流程回归、刷新/断线恢复、结束后的报告入口，以及取消评分反馈对下一题的动画阻塞。没有调整真实模型、评分策略或数据库结构。

## 发现与修复

1. 已完成会话不存在当前轮次。旧前端仍请求 `current-turn`，404 后访问已经不存在的 `current-question` 接口，导致刷新已结束面试出现资源不存在。现在先读取会话状态，COMPLETED 直接恢复结束状态与报告入口。
2. 旧前端把 EVALUATING 轮次直接转换成可答题，刷新可能重新展示已提交题目。现在仅接受 WAITING_ANSWER 且 canAnswer 的轮次；评分中或预生成交接期间等待数据库状态推进。
3. 恢复失败后缺少恢复动作。增加“重新同步面试”和“返回面试列表”；同步完成前禁用答题。重新同步只读取状态，不重新提交已保存答案。
4. 同一个事件周期内重复触发提交，React 状态尚未更新，会发出两次请求。增加同步防重入保护；回答处理与结束操作互斥，按钮显示处理中。
5. 网络提交失败时恢复输入内容，保留请求标识。重新同步发现题目已推进时清除旧答案草稿，避免把上一题答案带入下一题。
6. 原来先逐字播放完整反馈，再等待 180ms，最后逐字展示问题。现在反馈和题目直接显示，保留原有题目语音播报、追问标记与顺序。

## 调用链

旧恢复：进入房间 → 查会话 → 查当前题 → 将评分中题目当成可答题；当前题不存在则回退旧接口。

新恢复：进入房间 → 查会话并按需等待准备/启动 → 查询持久化会话与当前轮次 → 已完成则显示报告入口；评分中等待；可答轮次就绪后开放输入。离开页面取消恢复等待。

答题业务顺序保持：提交答案 → Worker 评分 → 决定并生成当前题追问 → 保存评价和下一轮次 → 前端显示反馈与追问/下一主问题。PostgreSQL 仍是业务状态来源。

## 文件与原因

| 文件 | 修改原因 |
| --- | --- |
| `frontend/src/services/interviewService.ts` | 按持久化状态恢复；等待评分/预生成交接；明确终态及错误；取消轮询等待并清理监听器 |
| `frontend/src/hooks/interview/session/useInterviewRouteRecovery.ts` | 恢复中状态、手动重试、取消旧恢复、明确无权访问/不存在提示 |
| `frontend/src/hooks/interview/session/useInterviewSessionFlow.ts` | 按题目就绪状态开放输入、防重复提交、保留未确认答案、直接展示反馈 |
| `frontend/src/hooks/interview/session/useInterviewMessageStream.ts` | 去掉题目逐字展示等待，保留播报和去重 |
| `frontend/src/hooks/interview/session/interviewSessionFlow.shared.ts` | 更新查看报告提示；移除本次改动造成的无用常量/函数 |
| `frontend/src/hooks/interview/useInterviewPageController.ts` | 向页面传递恢复状态与重试动作 |
| `frontend/src/pages/interview/InterviewPage.tsx` | 同步进度、恢复/返回按钮、正确的答题与结束按钮可用状态 |
| `frontend/src/components/interview/InterviewHeader.tsx` | 正确区分同步中、暂停、进行中与已结束 |
| `frontend/src/services/interviewService.recovery.test.ts` | 新增 8 项恢复、终态、取消等待和错误传播回归 |
| `frontend/src/hooks/interview/session/useInterviewSessionFlow.test.tsx` | 新增 4 项：立即展示、防重复提交、恢复重试、保留答案与请求标识；更新已有恢复断言 |
| `frontend/e2e/mvp.spec.ts` | 通过页面回答整场面试；验证追问相邻、刷新、断线、报告、提前结束及保存内容 |
| `compose.e2e.yml` | 仅测试 Worker 使用 90 分追问阈值，使固定 80 分测试模型实际覆盖追问分支 |
| 本文 | 记录验收依据、性能口径及剩余事项 |

## 验证结果

- 修复前，新增针对性测试复现 7 项失败；修复后通过。
- 前端 `npm run check`：lint、TypeScript 检查通过；34 个测试文件、173 项测试通过。
- 前端 Docker 生产构建通过。
- Ruff：通过。
- mypy：117 个源文件通过。
- pytest：213 passed，12 integration deselected。显式使用 test 环境和 Unavailable AI/embedding Provider。
- 专用 `backend-python/scripts/run_integration_tests.py`：12 项集成测试连续通过两轮，0 skipped；测试容器及专用卷由脚本清理。
- Playwright `e2e/mvp.spec.ts`：最终一轮 1 passed，测试主体 34.8 秒。使用 Fake Provider、独立 PostgreSQL/Redis/Worker、18080 测试页面。
- E2E 验证：合成 PDF 上传与处理、继续面试、题目语音、逐题页面提交、追问 parentTurnId 相邻、重复请求、评分中刷新、连接失败后重试、完成后刷新及查看报告、报告刷新、提前结束、失效会话返回列表。
- E2E 验证数据库返回的轮次数、每条答案内容及报告条目数一致。
- 为稳定覆盖“评分中刷新”，浏览器重放已接受提交对应的 EVALUATING 状态快照，随后恢复真实接口；不延迟或修改数据库。断线通过阻断页面读请求模拟。
- `git diff --check` 通过。既有文档/PPT/项目素材保留。

非阻断提示：第三方库弃用提示、pytest 缓存目录权限提示、Browserslist 数据过期提示。麦克风拒绝日志来自预期失败场景测试。

## 展示延迟对比

| 项目 | 优化前 | 优化后 |
| --- | --- | --- |
| 500 字反馈对下一题的动画阻塞 | 根据旧代码计算：249 × 18ms + 180ms = 4662ms，尚未计题目自身动画 | 移除这部分定时等待；回归测试无需推进时间即可看到完整题目 |
| 题目响应完成至 DOM 确认可见 | 本轮没有旧版本浏览器实测 | Fake Provider E2E 单次观测上界 15.2ms |

15.2ms 从浏览器 Resource Timing 的 responseEnd 到 DOM 检查时刻计算，包含检查开销，不代表模型耗时，也不是多次采样的 P95。原有 26.6 秒创建面试基线与本指标不是同一链路，不能直接计算整场加速比例。

## 剩余事项

- 真实评分模型及独立追问生成仍串行，答题结果仍有 800ms 轮询；真实模型延迟本轮未重测。
- 本轮恢复当前可答轮次与终态；刷新后完整聊天消息历史回放、未提交草稿跨刷新持久化仍可单独完善。
- 当前答题请求处理期间结束按钮暂不可用，避免答题结果与结束动作竞争；跨标签页并发操作可后续专项覆盖。
- 下一步建议先埋点评分/追问链路，再评估精简评分结构与合并追问生成。真实模型性能测试与隔离回归分开执行。
