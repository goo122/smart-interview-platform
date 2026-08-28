# 基于 Codex 构建智能模拟面试平台操作手册

> 目标：使用 Codex 逐步复刻现有“码上面试”项目，建设一个基于 FastAPI、LangChain、LangGraph 和 RAG 的智能模拟面试平台。

## 目录

1. 项目目标与实施原则
2. 推荐技术架构
3. 推荐目录结构
4. 开发环境准备
5. Codex 项目规则
6. 与 Codex 交互的方法
7. 阶段一：分析原项目
8. 阶段二：初始化 FastAPI
9. 阶段三：用户认证
10. 阶段四：普通 AI 对话
11. 阶段五：知识库与 RAG
12. 阶段六：模拟面试主流程
13. 阶段七：面试报告
14. 阶段八：适配原 React 前端
15. 阶段九：语音与实时通信
16. 测试与质量门禁
17. 每轮任务的验收方法
18. 常见问题和处理提示词
19. 最终验收清单
20. 推荐的第一个 Codex 任务

---

## 1. 项目目标与实施原则

### 1.1 项目目标

最终平台包含以下能力：

- 用户注册、登录和权限隔离；
- PDF 简历上传、解析和预览；
- 基于简历、岗位描述和题库的 RAG；
- AI 自动生成面试题；
- 文本模拟面试；
- AI 评分、反馈和动态追问；
- 面试历史和报告；
- SSE 流式回复；
- WebSocket 实时语音识别；
- TTS 语音合成；
- 摄像头截图和神态分析，可选；
- 可恢复的长会话状态；
- 测试、监控和容器化部署。

核心业务闭环：

```text
注册/登录
  → 上传简历
  → 解析并建立知识库
  → 绑定岗位描述
  → AI 生成面试题
  → 创建面试会话
  → 用户回答
  → AI 评分
  → 判断是否追问
  → 生成面试报告
```

### 1.2 MVP 范围

第一版只实现：

```text
登录
+ PDF 简历
+ 基础 RAG
+ AI 出题
+ 文本答题
+ AI 评分
+ 面试报告
```

以下功能放在后续阶段：

- 实时语音；
- TTS；
- 摄像头和神态分析；
- 多 Agent 协作；
- 分布式 Single-flight；
- 复杂后台管理；
- 专用向量数据库；
- Kubernetes 部署。

### 1.3 实施原则

1. 保留原项目的业务流程和前端体验，不逐行翻译 Java 代码。
2. 保持前端依赖的 API 契约，优先重写后端。
3. 每次只交付一个垂直业务切片。
4. 每个切片同时包含 API、Schema、Service、Repository、迁移和测试。
5. PostgreSQL 是业务事实来源，Redis 只保存临时状态。
6. LangGraph 负责编排，不作为最终数据源。
7. AI 输出必须使用 Pydantic 结构化模型。
8. 所有 RAG 检索必须强制进行用户和知识库隔离。
9. 测试不能调用真实收费模型。
10. 任何密钥都不能提交到 Git。

---

## 2. 推荐技术架构

### 2.1 技术选型

| 领域 | 推荐技术 | 主要职责 |
| --- | --- | --- |
| 前端 | React + TypeScript + Vite | 页面、状态和实时交互 |
| API | FastAPI | HTTP、SSE、WebSocket |
| 数据模型 | Pydantic v2 | DTO、配置和 AI 结构化输出 |
| ORM | SQLAlchemy 2 async | 异步数据库访问 |
| 数据迁移 | Alembic | 数据库版本管理 |
| 主数据库 | PostgreSQL | 用户、消息、会话、面试、报告 |
| 向量检索 | pgvector | MVP 阶段的向量存储与检索 |
| 缓存 | Redis | 登录会话、限流、锁、临时状态 |
| AI 集成 | LangChain | 模型、Embedding、Prompt、Retriever |
| 工作流 | LangGraph | 面试状态和多步骤 AI 流程 |
| 异步任务 | ARQ | PDF 解析、Embedding、报告生成 |
| 测试 | pytest + httpx | 单元、API 和集成测试 |
| 质量检查 | Ruff + mypy | 代码和类型检查 |
| 部署 | Docker Compose | 本地和演示环境 |

### 2.2 数据流

```text
React 前端
  │
  ├─ HTTP ──────→ FastAPI Router
  ├─ SSE ───────→ AI 流式回复
  └─ WebSocket ─→ 实时语音
                    │
                    ▼
              Application Service
               ├─ Domain Model
               ├─ LangGraph
               ├─ LangChain/RAG
               ├─ PostgreSQL/pgvector
               ├─ Redis
               └─ 外部 AI/语音服务
```

### 2.3 为什么使用 PostgreSQL + pgvector

MVP 阶段建议将原项目的 MySQL、MongoDB 和向量数据库合并为 PostgreSQL：

- 关系数据使用普通表；
- 灵活运行态使用 JSONB；
- 向量数据使用 pgvector；
- 事务和权限管理更容易统一；
- 本地只需运行 PostgreSQL 和 Redis。

如果后续知识库规模和检索压力明显增加，再迁移到 Qdrant。

---

## 3. 推荐目录结构

```text
智能模拟面试平台/
├─ frontend/
├─ backend-python/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ api/
│  │  │  └─ v1/
│  │  ├─ core/
│  │  │  ├─ config.py
│  │  │  ├─ database.py
│  │  │  ├─ redis.py
│  │  │  ├─ security.py
│  │  │  ├─ exceptions.py
│  │  │  └─ logging.py
│  │  ├─ modules/
│  │  │  ├─ auth/
│  │  │  ├─ chat/
│  │  │  ├─ knowledge/
│  │  │  ├─ interview/
│  │  │  ├─ agent/
│  │  │  └─ media/
│  │  ├─ ai/
│  │  │  ├─ models.py
│  │  │  ├─ prompts/
│  │  │  ├─ structured_output.py
│  │  │  └─ callbacks.py
│  │  ├─ infrastructure/
│  │  │  ├─ llm/
│  │  │  ├─ vectorstore/
│  │  │  ├─ storage/
│  │  │  └─ external/
│  │  └─ workers/
│  ├─ tests/
│  ├─ alembic/
│  ├─ pyproject.toml
│  ├─ Dockerfile
│  └─ .env.example
├─ docs/
│  ├─ architecture.md
│  ├─ api-contract.md
│  ├─ domain-model.md
│  ├─ rag-design.md
│  └─ adr/
├─ AGENTS.md
├─ docker-compose.yml
└─ README.md
```

每个业务模块统一采用：

```text
router.py        # HTTP 路由
schemas.py       # 请求和响应模型
domain.py        # 领域对象和规则
service.py       # 用例编排
repository.py    # 仓储接口
models.py        # SQLAlchemy 模型
dependencies.py  # FastAPI 依赖
exceptions.py    # 模块异常
```

---

## 4. 开发环境准备

### 4.1 本机软件

- Git；
- Python 3.12；
- uv；
- Docker Desktop；
- Node.js；
- Codex Desktop。

### 4.2 环境变量

```env
APP_ENV=development
APP_SECRET_KEY=replace-me

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_interview
REDIS_URL=redis://localhost:6379/0

LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=

EMBEDDING_API_KEY=
EMBEDDING_BASE_URL=
EMBEDDING_MODEL=

JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

创建 `.env.example`，只保留变量名和安全示例。真实值写入被 Git 忽略的 `.env`。

### 4.3 开发前检查

- [ ] 原项目可以正常启动；
- [ ] 原前端主要页面可以访问；
- [ ] 已备份原 API 和数据结构；
- [ ] 已轮换代码中曾暴露的密钥；
- [ ] 新后端使用独立目录；
- [ ] 新项目已经初始化 Git；
- [ ] Docker 可以正常运行。

---

## 5. 创建 Codex 项目规则

在项目根目录创建 `AGENTS.md`：

```markdown
# Project Instructions

## Architecture

- Backend uses FastAPI, Pydantic v2 and SQLAlchemy 2.
- Business logic must not be placed in API routers.
- Routers call services, and services depend on repository abstractions.
- PostgreSQL is the source of truth.
- Redis is used only for cache, locks, rate limits and temporary state.
- LangGraph orchestrates workflows but is not the source of truth.
- AI outputs must use Pydantic structured models.
- RAG requests must filter by user_id and knowledge_base_id.

## Code Quality

- Every new service requires unit tests.
- Every new endpoint requires API tests.
- Use async interfaces for network and database operations.
- Do not hard-code secrets.
- Do not silently catch exceptions.
- Run Ruff, mypy and pytest before completing a task.
- Do not modify unrelated files.

## Workflow

- Inspect relevant files before editing.
- State assumptions before implementing ambiguous behavior.
- Implement one vertical slice at a time.
- Report changed files, tests and remaining risks.
```

---

## 6. 与 Codex 交互的方法

### 6.1 标准任务结构

每次给 Codex 的任务都应说明：

```text
目标：要实现什么。
背景：当前代码和业务处于什么状态。
范围：允许修改哪些目录。
约束：禁止事项和架构要求。
接口：请求、响应、状态码。
验收：完成标准。
验证：需要执行的测试。
```

### 6.2 通用提示词模板

```text
请先阅读 AGENTS.md 和相关模块，然后完成下面的任务。

目标：
[填写目标]

当前状态：
[填写已有功能]

允许修改：
[填写目录]

约束：
1. Router 中不写业务逻辑。
2. Service 依赖 Repository 抽象。
3. 使用异步数据库接口。
4. AI 返回使用 Pydantic 结构化模型。
5. 不修改无关文件。
6. 不提交真实密钥。

验收条件：
1. [条件一]
2. [条件二]
3. [条件三]

测试要求：
1. 添加单元测试。
2. 添加 API 测试。
3. 运行 Ruff、mypy 和 pytest。

请先检查代码并说明实施方案，然后直接实现和验证。
```

### 6.3 一次任务的推荐流程

```text
让 Codex 检查代码
  → 确认实施范围
  → 实现一个垂直切片
  → 运行测试
  → 查看改动
  → 修复问题
  → 更新文档
  → 提交 Git
```

### 6.4 如何要求 Codex 汇报结果

```text
完成后请汇报：
1. 修改了哪些文件；
2. 新增或修改了哪些接口；
3. 数据库发生了什么变化；
4. 执行了哪些测试；
5. 测试结果是什么；
6. 有哪些风险或未完成事项；
7. 下一步建议是什么。
```

---

## 7. 阶段一：分析原项目

第一轮让 Codex 建立项目认知，不修改业务代码。

```text
请分析当前 Java 后端和 React 前端。

输出：
1. 前端所有页面及其调用的接口；
2. 后端所有 Controller、请求和响应结构；
3. 核心领域实体；
4. 面试主链路；
5. SSE 和 WebSocket 链路；
6. MySQL、MongoDB、Redis 分别保存的数据；
7. 可以保留的 API 契约；
8. Python 重构时可以简化的部分。

本轮只分析，不修改业务代码。

将结果写入：
- docs/architecture.md
- docs/api-contract.md
- docs/domain-model.md
```

验收重点：

- 是否覆盖登录、聊天、面试、报告；
- 是否记录前端真实使用的字段；
- 是否区分 HTTP、SSE 和 WebSocket；
- 是否记录面试状态转换；
- 是否记录数据库和缓存职责；
- 是否标记存在风险的密钥和配置。

---

## 8. 阶段二：初始化 FastAPI

```text
请在 backend-python 目录初始化 FastAPI 项目骨架。

技术要求：
- Python 3.12
- uv
- FastAPI
- Pydantic Settings
- SQLAlchemy 2 async
- Alembic
- asyncpg
- redis asyncio
- pytest
- pytest-asyncio
- httpx
- Ruff
- mypy

实现：
1. app/main.py；
2. /api/v1 路由；
3. /health 健康检查；
4. PostgreSQL 和 Redis 配置；
5. 统一错误响应；
6. 请求 ID；
7. 结构化日志；
8. Dockerfile；
9. docker-compose.yml；
10. .env.example。

不要实现用户、AI、RAG、面试和前端功能。

验收：
- 应用能够启动；
- /health 返回 200；
- PostgreSQL 和 Redis 有健康检查；
- pytest 可以运行；
- Ruff 和 mypy 通过。
```

---

## 9. 阶段三：用户认证

实现范围：注册、登录、刷新 Token、退出登录和查询当前用户。

```text
请实现 auth 垂直业务切片。

要求：
1. User SQLAlchemy 模型；
2. Alembic 迁移；
3. 注册、登录、刷新、退出和当前用户接口；
4. 密码使用安全哈希；
5. Access Token 和 Refresh Token 分离；
6. Redis 保存可撤销的登录会话；
7. 统一认证依赖；
8. 登录接口限流；
9. 用户名和邮箱唯一；
10. 添加 Service、Repository 和 API 测试。

禁止：
- Router 直接访问数据库；
- 在日志中输出密码或 Token；
- 在配置中写固定密钥。
```

必须验证：

- 正常注册和登录；
- 重复邮箱或用户名；
- 密码错误；
- Access Token 过期；
- Refresh Token 被撤销；
- 未登录访问受保护接口；
- 用户不能访问其他用户数据。

---

## 10. 阶段四：普通 AI 对话

目标结构：

```text
ChatRouter
  → ChatService
  → ChatModelPort
  → LangChainChatModelAdapter
```

```text
请实现普通 AI 对话模块。

要求：
1. 创建 Conversation 和 Message 数据模型；
2. 支持创建、查询和删除会话；
3. 支持历史消息查询；
4. 支持 SSE 流式回复；
5. AI 模型通过 ChatModelPort 抽象；
6. LangChain 实现具体适配器；
7. AI 输出失败时记录失败消息；
8. 校验会话所属用户；
9. SSE 断开时正确释放资源；
10. 使用 Fake 或 Mock 模型完成自动化测试。
```

自动化测试不得调用真实大模型，也不能依赖真实 API Key。

---

## 11. 阶段五：知识库与 RAG

### 11.1 数据模型

```text
KnowledgeBase
KnowledgeDocument
KnowledgeChunk
IngestionTask
```

### 11.2 文档导入

```text
上传文件
  → 校验类型和大小
  → 保存原文件
  → 提取文本
  → 清洗
  → Token 分块
  → Embedding
  → 写入 pgvector
  → 标记导入完成
```

```text
请实现 knowledge 模块的 PDF 导入链路。

要求：
1. 创建 KnowledgeBase、KnowledgeDocument 和 KnowledgeChunk；
2. 文件必须归属当前用户；
3. 计算文件 SHA-256，避免重复导入；
4. 提取 PDF 页码和文本；
5. 使用 token-aware splitter 分块；
6. 保存 chunk_index、page_number、content_hash；
7. 通过 EmbeddingPort 调用向量模型；
8. 向量保存到 pgvector；
9. 导入过程使用后台任务；
10. 支持查询任务状态；
11. 文件解析失败必须记录明确原因；
12. 添加解析、分块、重复上传和权限测试。
```

### 11.3 检索服务

```text
KnowledgeRetriever
  → 权限和元数据过滤
  → 向量检索
  → 关键词检索
  → 合并和重排
  → 返回带来源的上下文
```

```text
请实现 RagRetriever。

输入：
- user_id
- knowledge_base_id
- query
- top_k

要求：
1. 强制按 user_id 和 knowledge_base_id 过滤；
2. 支持向量相似度检索；
3. 保留扩展到关键词混合检索的接口；
4. 返回文档名、页码、chunk_id、分数和文本；
5. 相似度低于阈值时返回空结果；
6. 禁止跨用户检索；
7. 添加权限隔离和相似度过滤测试。
```

### 11.4 接入聊天和面试

```text
用户问题
  → RagRetriever
  → ContextAssembler
  → Prompt
  → ChatModel
  → SSE
```

面试场景增加统一的 `InterviewContextRetriever`，负责提供：

- 简历上下文；
- 岗位描述；
- 企业或个人题库；
- 历史回答；
- 评分标准。

AI 回复和评分要保留检索来源，不能让模型自行编造文件名或页码。

---

## 12. 阶段六：模拟面试主流程

### 12.1 核心模型

```text
InterviewSession
InterviewQuestion
InterviewTurn
InterviewEvaluation
InterviewReport
InterviewEvent
```

### 12.2 面试状态

```text
CREATED
PREPARING
ASKING
WAITING_ANSWER
EVALUATING
FOLLOWING_UP
FINISHED
FAILED
```

### 12.3 LangGraph 节点

```text
load_session
retrieve_context
select_question
ask_question
evaluate_answer
decide_followup
persist_turn
advance_session
generate_report
```

### 12.4 实现提示词

```text
请实现文本面试核心流程。

要求：
1. 面试业务状态保存在 PostgreSQL；
2. LangGraph 只负责编排；
3. 创建 InterviewSession、Question、Turn 和 Evaluation；
4. 支持根据简历知识库生成问题；
5. 支持提交文本答案；
6. 使用结构化模型返回评分；
7. 根据规则判断是否追问；
8. 每次状态变更保存 InterviewEvent；
9. 提交答案必须支持幂等键；
10. 校验会话归属；
11. 已结束会话禁止继续答题；
12. 添加状态机和 API 测试。
```

推荐评分模型：

```python
class InterviewEvaluation(BaseModel):
    score: int
    technical_score: int
    communication_score: int
    strengths: list[str]
    weaknesses: list[str]
    suggestion: str
    should_follow_up: bool
    follow_up_question: str | None
```

必须测试：

- 分数范围；
- AI 非法输出；
- AI 超时；
- 重试和降级；
- 重复提交；
- 状态跳转是否合法；
- 已结束面试再次答题；
- 用户访问其他人的面试。

---

## 13. 阶段七：面试报告

报告至少包含：

- 面试基本信息；
- 问题和回答回放；
- 单题评分；
- 优点和待提升项；
- 雷达图数据；
- AI 综合建议；
- 引用的简历或岗位知识。

```text
请实现面试结束和报告生成。

要求：
1. 结束操作幂等；
2. 聚合所有 InterviewTurn；
3. 计算总分和各维度分数；
4. 生成雷达图数据；
5. 生成结构化综合建议；
6. 保存不可变报告快照；
7. 报告接口校验用户权限；
8. AI 报告生成失败时提供规则化降级报告；
9. 添加并发结束、重复结束和权限测试。
```

---

## 14. 阶段八：适配原 React 前端

优先保持原 API 路径和响应字段，减少前端改动。重点检查：

```text
frontend/src/services/authService.ts
frontend/src/services/aiService.ts
frontend/src/services/agentService.ts
frontend/src/services/interviewService.ts
frontend/src/services/audioToTextWs.ts
frontend/src/services/xunfeiTtsService.ts
```

```text
请对比 docs/api-contract.md、前端 services 和 FastAPI OpenAPI。

输出不兼容清单：
1. URL 不一致；
2. HTTP 方法不一致；
3. 请求字段不一致；
4. 响应结构不一致；
5. Token 传递不一致；
6. SSE 事件格式不一致；
7. WebSocket 消息格式不一致。

优先修改 Python 后端以兼容已有前端。
修改后添加契约测试，并运行前端类型检查和构建。
```

---

## 15. 阶段九：语音与实时通信

文本面试稳定后再实现：

- WebSocket 音频上传；
- ASR 实时转写；
- TTS；
- 心跳；
- 断线重连；
- 增量文本合并；
- 超时和资源释放。

第三方语音服务封装为：

```text
SpeechToTextPort
TextToSpeechPort
```

具体供应商实现放在 `infrastructure/external/`。业务层不能直接依赖讯飞或其他供应商 SDK。

---

## 16. 测试与质量门禁

### 16.1 后端检查

```bash
ruff check .
mypy app
pytest
pytest --cov=app --cov-report=term-missing
```

建议覆盖率目标：

- 整体不低于 80%；
- 领域规则和状态机不低于 90%；
- Router 重点验证接口契约；
- Repository 使用集成测试；
- LLM 使用 Fake 或 Mock；
- PostgreSQL 和 Redis 使用 Testcontainers。

必须覆盖：

- 权限隔离；
- 重复提交；
- 并发提交；
- AI 超时；
- AI 非法 JSON；
- Redis 不可用；
- 数据库事务回滚；
- SSE 中断；
- 知识库跨用户访问；
- 低相似度无结果；
- 面试中断恢复；
- 面试重复结束。

### 16.2 前端检查

```bash
npm run lint
npm run typecheck
npm run test:run
npm run build
```

重点测试登录状态、路由保护、SSE、WebSocket 重连、面试状态切换、重复提交、报告渲染和错误提示。

### 16.3 CI 门禁

每次提交至少运行：

```text
后端 Ruff
后端 mypy
后端 pytest
后端覆盖率
前端 ESLint
前端 TypeScript
前端 Vitest
前端 Build
密钥扫描
```

---

## 17. 每轮任务的验收方法

要求 Codex 在完成后汇报：

1. 完成了什么；
2. 修改了哪些文件；
3. 数据库迁移是什么；
4. 新增或修改了哪些接口；
5. 执行了哪些测试；
6. 测试结果是什么；
7. 有哪些风险；
8. 下一步是什么。

人工检查：

- 是否修改无关文件；
- 是否把业务逻辑写进 Router；
- 是否出现硬编码密钥；
- 是否真的执行测试；
- 是否存在跨用户访问；
- 是否只有成功场景测试；
- 是否引入无必要的框架；
- 是否破坏原前端 API 契约。

推荐开发循环：

```text
分析
  → 写接口契约
  → 写测试
  → 实现最小功能
  → 运行测试
  → 检查差异
  → 更新文档
  → 提交 Git
```

---

## 18. 常见问题和处理提示词

### 18.1 Codex 修改范围失控

```text
停止继续扩展功能。

请只保留本轮要求的垂直切片，列出超出范围的改动。
不要删除现有用户代码。
先给出安全的收敛方案，再执行修改。
```

### 18.2 测试失败

```text
请分析当前失败测试。

要求：
1. 区分代码缺陷、测试缺陷和环境问题；
2. 不得通过删除测试或降低断言解决；
3. 不修改与失败无关的代码；
4. 修复后重新运行受影响测试和完整测试；
5. 汇报根因和修复证据。
```

### 18.3 只完成代码但没有验证

```text
请不要继续增加功能。

现在只做验证：
1. 运行 Ruff；
2. 运行 mypy；
3. 运行相关测试；
4. 运行完整测试；
5. 检查未提交差异；
6. 汇报失败项和风险。
```

### 18.4 LangChain 耦合严重

建立以下端口：

```text
ChatModelPort
EmbeddingPort
RetrieverPort
VectorStorePort
```

业务 Service 依赖端口，LangChain 只存在于基础设施适配器中。

### 18.5 LangGraph 和数据库状态不一致

数据库必须是最终数据源。每个重要节点完成后保存业务事件和状态，恢复时从数据库重新构造 Graph State。

### 18.6 RAG 出现数据串库

所有向量必须携带 `user_id` 和 `knowledge_base_id`。检索服务必须强制过滤，并通过自动化测试验证跨用户访问被拒绝。

### 18.7 LLM 输出格式不稳定

使用 Pydantic Structured Output，增加：

- Schema 校验；
- 有限次数重试；
- 非法输出日志；
- 规则化降级结果；
- 测试中的非法输出样例。

---

## 19. 最终验收清单

### 功能

- [ ] 用户能够注册和登录
- [ ] 用户能够上传 PDF 简历
- [ ] 系统能够建立简历知识库
- [ ] 系统能够根据简历生成面试题
- [ ] 用户能够创建面试会话
- [ ] 用户能够提交文本答案
- [ ] 系统能够评分并决定是否追问
- [ ] 系统能够生成面试报告
- [ ] 用户只能访问自己的数据
- [ ] AI 回复支持流式输出

### 架构

- [ ] Router 中没有核心业务逻辑
- [ ] Service 不直接依赖 LangChain 具体实现
- [ ] LangGraph 不是最终数据源
- [ ] RAG 强制用户和知识库隔离
- [ ] AI 输出使用结构化模型
- [ ] 数据库迁移可重复执行
- [ ] 外部服务经过适配器封装

### 质量

- [ ] Ruff 通过
- [ ] mypy 通过
- [ ] pytest 通过
- [ ] 前端 lint、类型检查、测试和构建通过
- [ ] 核心流程有集成测试
- [ ] 没有硬编码密钥
- [ ] 日志不包含密码、Token 和简历原文
- [ ] Docker Compose 可以启动完整环境

### 部署

- [ ] PostgreSQL 健康检查正常
- [ ] Redis 健康检查正常
- [ ] FastAPI 健康检查正常
- [ ] Alembic 迁移成功
- [ ] 前后端接口契约一致
- [ ] 生产环境关闭调试模式
- [ ] CORS 和可信域名正确配置

---

## 20. 推荐的第一个 Codex 任务

将下面的内容发送给 Codex：

```text
请先阅读根目录 AGENTS.md，并检查当前项目结构。

目标：
在新的 backend-python 目录初始化 FastAPI 项目骨架。

本轮只完成：
1. FastAPI 应用；
2. /health；
3. Pydantic Settings；
4. PostgreSQL async 配置；
5. Redis async 配置；
6. 统一错误响应；
7. pytest 测试；
8. Ruff 和 mypy；
9. Dockerfile；
10. docker-compose.yml。

不要实现：
- 用户认证；
- AI；
- RAG；
- 面试业务；
- 前端改动。

验收：
1. 应用可以启动；
2. /health 返回 200；
3. 测试通过；
4. Ruff 和 mypy 通过；
5. Docker Compose 配置有效；
6. 没有真实密钥。

完成后汇报修改文件、启动命令、测试结果和下一步建议。
```

完成骨架后，按照本手册依次实现认证、聊天、知识库、RAG、面试和报告。
