# MVP 发布候选版验收清单

## 运行前

- [x] Docker Desktop 正在运行，`docker version` 和 `docker compose version` 可用；
- [x] 已从 `backend-python/.env.example` 创建本地 `backend-python/.env`；
- [x] 未在 `.env`、日志、前端代码或镜像构建上下文中提交真实 Key；
- [ ] 生产环境没有配置 `APP_AI_PROVIDER=fake` 或 `APP_EMBEDDING_PROVIDER=fake`。

## Compose

- [x] `docker compose config` 通过；
- [x] `postgres` 和 `redis` 变为 healthy；
- [x] `migrate` 成功退出并执行 `alembic upgrade head`；
- [x] `api` 的 readiness 通过后 `frontend` 才启动；
- [x] API 使用命名卷 `knowledge-storage`，而不是 tmpfs；
- [x] 未对正式或开发环境执行 `docker compose down -v`（隔离 E2E/集成环境可清理）。

## API、Nginx 和数据

- [x] `/health` 和 `/health/live` 返回 200；
- [x] PostgreSQL 或 Redis 不可用时 `/health/live` 仍返回 200，`/health/ready` 返回 503；
- [x] Nginx `/api/` 代理到 `api:8000`，并在 API 容器地址变化后动态重新解析；
- [x] SSE 响应关闭代理缓冲并允许长连接；
- [x] PDF 上传大小限制与后端一致；
- [x] API 重启后，命名卷中的 PDF 仍可用于文档查询；
- [x] 上传文件不能通过 Nginx 静态路径直接访问。

## E2E

- [x] 使用 `compose.e2e.yml` 的独立数据库、Redis 和存储卷；
- [x] Fake Provider 完成注册、登录、知识库、PDF 导入、RAG 聊天、面试、评分、追问、报告和退出；
- [x] 页面刷新后认证、知识库、面试和报告状态可以恢复；
- [x] E2E 使用合成 PDF 和唯一测试账号；
- [ ] 测试失败时已检查截图/trace，确认没有 Token 或个人数据。

## 2026-09-04 验收记录

- Docker Engine 29.7.2、Docker Compose 5.4.0；当前 Codex 终端未刷新 `PATH`，验收脚本通过 Docker Desktop 安装路径自动发现 CLI。
- Docker 集成测试连续两轮各 12 项通过；Alembic head 为 `0014_demeanor_evaluation`，`alembic check` 未发现待生成迁移。
- Fake Provider 浏览器 E2E 通过；真实 AI Provider 冒烟测试按安全策略跳过，未产生外部调用费用。
- Redis 进程退出后 Redis 与 worker 均自动重启并恢复 healthy；恢复后完整 E2E 再次通过。
- 本地 `.env` 使用真实 provider 类型且已被 Git 和 Docker 构建上下文排除；生产部署变量仍需在目标环境单独复核。
- 失败截图和文本上下文只含合成账号；trace 的网络头脱敏尚未建立自动校验，因此相关检查项保持未完成。

## 质量门禁

```powershell
cd backend-python
uv run pytest
uv run pytest -m integration
uv run ruff check .
uv run mypy app
uv run alembic heads
uv run alembic check

cd ..\frontend
npm run api:generate
npm run lint
npm run typecheck
npm run test:run
npm run build
npm run test:e2e
```

Docker CLI 缺失、Docker Desktop 未运行、数据库/Redis 不可用或浏览器未安装时，必须在验收报告中明确标注未验证项；YAML 解析或组件测试不能替代容器和真实浏览器验证。
