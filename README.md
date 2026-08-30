# 寻知智能模拟面试平台

MVP 发布候选版由 React/Vite 前端和 FastAPI/Python 后端组成，使用 PostgreSQL 保存业务事实数据、Redis 保存会话和临时状态，AI Provider 通过端口适配器接入。

## 环境和配置

- Python 3.12+
- Node.js 20+
- Docker Desktop（容器联调需要）

首次本地配置：

```powershell
Copy-Item backend-python/.env.example backend-python/.env
```

开发环境可以使用：

```text
APP_AI_PROVIDER=fake
APP_EMBEDDING_PROVIDER=fake
APP_AI_FAKE_MODE=follow_up
```

Fake Provider 只允许 `development`/`test`，生产环境配置会拒绝启动。真实 OpenAI-compatible Provider 需要同时配置 API Key、Base URL 和 Model；不要把 `.env` 或真实 Key 提交到 Git。

### 千问（DashScope，可选）

项目使用 OpenAI-compatible 接口接入千问，配置写在本地 `backend-python/.env`：

```text
APP_AI_PROVIDER=openai_compatible
APP_LLM_API_KEY=<你的 DashScope Key>
APP_LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
APP_LLM_MODEL=qwen-plus

APP_EMBEDDING_PROVIDER=openai_compatible
APP_EMBEDDING_API_KEY=<你的 DashScope Key>
APP_EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
APP_EMBEDDING_MODEL=text-embedding-v4
APP_EMBEDDING_DIMENSIONS=1536
```

`qwen-plus` 可按账号权限替换为其他兼容模型；Embedding 模型必须返回 1536 维向量。应用启动时会检查 Key、Base URL、Model 和实际向量维度。本仓库的自动化测试默认使用 Fake Provider，不会自动调用真实千问或产生费用。

### 语音转文字（ASR）

语音输入使用认证 WebSocket：
`/api/xunzhi/v1/xunfei/audio-to-text/{userId}`；能力查询使用
`GET /api/xunzhi/v1/speech/capabilities`。浏览器发送 PCM16、16kHz、单声道二进制音频，
服务端返回增量快照和最终快照，结果只会填入聊天输入框或面试构思板，不会自动提交。

后端通过 `APP_SPEECH_TO_TEXT_PROVIDER` 选择 `unavailable`、`fake` 或 `xunfei`。
Fake 仅限 development/test，真实讯飞凭据只配置在后端环境变量中；自动化测试使用 Fake，
不会连接讯飞或产生费用。

### 语音合成（TTS）

登录后可查询 `GET /api/xunzhi/v1/speech/tts/capabilities`，并通过兼容的
`POST /api/xunzhi/v1/xunfei/tts/synthesize` 合成消息音频。默认的
`APP_TEXT_TO_SPEECH_PROVIDER=unavailable` 会安全拒绝请求；本地测试和 E2E 使用 `fake`，
返回浏览器可播放的短 WAV。真实讯飞模式只在后端配置 `APP_XUNFEI_TTS_APP_ID`、
`APP_XUNFEI_TTS_API_KEY`、`APP_XUNFEI_TTS_API_SECRET` 后启用，凭据不会返回给前端或提交到 Git。

## Docker Compose 启动

```powershell
docker compose up -d --build
docker compose ps
```

Compose 服务启动顺序为 `postgres`/`redis` 健康 → `migrate` 执行 `alembic upgrade head` → `api` readiness → `frontend`。上传 PDF 使用命名卷 `knowledge-storage` 持久化，API 容器以非 root 用户运行。浏览器访问 `http://localhost:8080`。

健康检查：

- `GET http://localhost:8000/health`：兼容的存活别名；
- `GET http://localhost:8000/health/live`：只检查进程；
- `GET http://localhost:8000/health/ready`：检查 PostgreSQL 和 Redis；
- Nginx 的 `/api/` 代理到 Compose 内部 `api:8000`，浏览器不需要知道容器主机名。

停止服务但保留数据卷：

```powershell
docker compose stop
```

不要使用 `docker compose down -v`，否则会删除本地数据库、Redis 和上传文件卷。

## E2E 环境

E2E 使用独立 Compose 项目、端口、数据库/Redis/存储卷和 Fake Provider：

```powershell
docker compose -f docker-compose.yml -f compose.e2e.yml up -d --build
cd frontend
npx playwright install chromium
npm run test:e2e
```

默认 Playwright 地址为 `http://127.0.0.1:18080`。测试使用合成 PDF、唯一用户名和稳定请求编号，不读取真实模型 Key。失败时 Playwright 会保留截图、视频和 trace；这些产物不应提交 Git。

## 本地开发和质量检查

后端：

```powershell
cd backend-python
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run pytest
uv run pytest -m integration
uv run ruff check .
uv run mypy app
```

前端：

```powershell
cd frontend
npm install
npm run api:generate
npm run lint
npm run typecheck
npm run test:run
npm run build
```

API 类型从 FastAPI OpenAPI 生成，输出到 `frontend/src/api/generated.ts`，不要手工编辑生成文件。报告、面试、聊天和知识库接口都复用统一 Bearer Token 刷新机制。

## Alembic 和常见故障

迁移命令：

```powershell
cd backend-python
uv run alembic upgrade head
uv run alembic heads
uv run alembic check
uv run alembic upgrade head --sql
```

如果 API readiness 失败，先确认 PostgreSQL、Redis 已 healthy，并检查 `.env` 中 Provider 配置是否完整；`/health/live` 只表示进程存活，`/health/ready` 才会检查依赖。Compose 内部会把数据库和 Redis 地址覆盖为 `postgres`、`redis` 服务名。

如果提示找不到 `docker`，请安装并启动 Docker Desktop 后重新打开终端，再依次运行 `docker version`、`docker compose version` 和 `docker context show`。不要复制来源不明的二进制文件，也不要把 YAML 解析结果当作容器验证。

## 发布验收

逐项验收项见 [docs/release-checklist.md](docs/release-checklist.md)。当前仓库未包含真实密钥、个人简历、`node_modules`、构建产物、截图或日志。
