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
