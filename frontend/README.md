# 寻知前端

新的 React + TypeScript + Vite 前端只负责接入 FastAPI 的用户认证和基础导航，原有 `frontend/` 项目保持不变并仅作接口、路由和视觉参考。

## 本地开发

```powershell
npm install
npm run api:generate
npm run dev
```

开发服务器默认使用 `/api` 作为浏览器请求前缀，并将请求代理到 `http://localhost:8000`。可通过 `.env` 覆盖：

```text
VITE_API_BASE_URL=/api
VITE_API_TARGET=http://localhost:8000
```

OpenAPI 类型由后端应用生成，输出为 `src/api/generated.ts`，不要手工编辑生成文件。

## 认证接口

页面接入 FastAPI 的以下接口：

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

Axios 客户端会自动附加 Bearer Token，并使用 single-flight 机制刷新过期 Access Token。Refresh Token 仅存储在浏览器本地存储中，密码不会写入状态管理或日志。

## 知识库与 RAG 聊天

`/chat` 页面接入 `/api/xunzhi/v1/knowledge-bases`、文档上传和 `/api/xunzhi/v1/ai` 会话接口。知识库文档处于 `READY` 后才会出现在 RAG 选择器中；`PENDING`/`PROCESSING` 会自动轮询，`FAILED` 会停止轮询并展示安全错误。

聊天使用 POST SSE（`start`、`delta`、`complete`、`error`）而不是原生 EventSource，支持 AbortController、401 刷新重试、稳定 `requestId`、跨网络块 UTF-8 和引用展开。普通对话不会发送 `knowledgeBaseId`，RAG 对话发送 `knowledgeBaseId` 与限定范围内的 `topK`。

## 模拟面试创建与面试房间

`/interview` 会从 `/api/xunzhi/v1/knowledge-bases` 及其文档接口筛选至少包含一个 `READY` 文档的知识库。创建请求使用后端 OpenAPI 类型，字段包括 `knowledgeBaseId`、`jobTitle`、`jobDescription`、`interviewType`、`difficulty`、`questionCount` 和稳定的 `requestId`，成功后进入 `/interview/:sessionId`。

面试房间按后端 Session/Turn 状态恢复页面：`CREATED`/`PREPARING` 轮询准备进度，`READY` 等待开始，`IN_PROGRESS` 轮询 `current-turn`。答案通过 `POST /api/xunzhi/v1/interview/sessions/{sessionId}/answers` 提交，使用 `turnId`、`answer` 和同一轮稳定的 `requestId`；评分、追问和下一道基础题均由后端状态推进。`PRIMARY` 与 `FOLLOW_UP` 使用不同提示，前端不会展示 `expectedPoints` 或内部来源字段。

## 面试报告

面试完成页会进入 `/interview/:sessionId/report`，页面先查询已有报告；如果报告不存在，会幂等发起生成请求，并在 `PENDING`/`GENERATING` 状态下自动轮询。报告就绪后跳转到稳定的 `/interview/reports/:reportId` 地址。

`/interview/reports` 提供当前用户的历史报告分页，详情页展示总分、四维能力雷达、优势/弱点、改进建议、行动计划、PRIMARY/FOLLOW_UP 问答回放和报告中保存的来源快照。报告内容均作为纯文本渲染，不依赖原知识库文档仍然存在，也不会展示内部路径、Prompt 或存储字段。

详情页的“打印报告”调用浏览器打印能力，仅提供打印样式，不代表服务端 PDF 导出。

## 验证

```powershell
npm run lint
npm run typecheck
npm run test:run
npm run build
```

## 容器运行

根目录的 Compose 会构建 `frontend` 服务并通过 Nginx 提供静态页面：

```powershell
docker compose build frontend
docker compose up -d frontend
docker compose ps
```

浏览器访问 `http://localhost:8080`。Nginx 会把 `/api/` 转发到 Compose 内的 `api:8000`，因此浏览器端不应配置容器内部主机名。
