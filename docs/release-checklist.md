# MVP 发布候选版验收清单

## 运行前

- [ ] Docker Desktop 正在运行，`docker version` 和 `docker compose version` 可用；
- [ ] 已从 `backend-python/.env.example` 创建本地 `backend-python/.env`；
- [ ] 未在 `.env`、日志、前端代码或镜像构建上下文中提交真实 Key；
- [ ] 生产环境没有配置 `APP_AI_PROVIDER=fake` 或 `APP_EMBEDDING_PROVIDER=fake`。

## Compose

- [ ] `docker compose config` 通过；
- [ ] `postgres` 和 `redis` 变为 healthy；
- [ ] `migrate` 成功退出并执行 `alembic upgrade head`；
- [ ] `api` 的 readiness 通过后 `frontend` 才启动；
- [ ] API 使用命名卷 `knowledge-storage`，而不是 tmpfs；
- [ ] 未执行 `docker compose down -v`。

## API、Nginx 和数据

- [ ] `/health` 和 `/health/live` 返回 200；
- [ ] PostgreSQL 或 Redis 不可用时 `/health/live` 仍返回 200，`/health/ready` 返回 503；
- [ ] Nginx `/api/` 代理到 `api:8000`；
- [ ] SSE 响应关闭代理缓冲并允许长连接；
- [ ] PDF 上传大小限制与后端一致；
- [ ] API 重启后，命名卷中的 PDF 仍可用于文档查询；
- [ ] 上传文件不能通过 Nginx 静态路径直接访问。

## E2E

- [ ] 使用 `compose.e2e.yml` 的独立数据库、Redis 和存储卷；
- [ ] Fake Provider 完成注册、登录、知识库、PDF 导入、RAG 聊天、面试、评分、追问、报告和退出；
- [ ] 页面刷新后认证、知识库、面试和报告状态可以恢复；
- [ ] E2E 使用合成 PDF 和唯一测试账号；
- [ ] 测试失败时已检查截图/trace，确认没有 Token 或个人数据。

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
