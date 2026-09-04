# 预发布与生产部署

## 前置条件

- 一台安装 Docker Engine 与 Docker Compose 的 Linux 主机；
- 域名的 A/AAAA 记录已经指向主机；
- 防火墙只需对公网开放 TCP 80、TCP 443 和 UDP 443；
- AI 与 Embedding 服务的真实凭据，且已设置调用预算和额度告警。

## 首次部署

```bash
cp .env.production.example .env.production
# 编辑 .env.production，替换所有占位内容
chmod 600 .env.production
python scripts/check_staging_readiness.py
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml up -d --build
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml ps
```

Caddy 会根据 `DOMAIN` 自动申请和续期 HTTPS 证书。生产覆盖文件不会向宿主机开放 API、PostgreSQL 或 Redis 端口。`.env.production` 和 `backups/` 已被 Git 忽略。

## 发布前检查

`check_staging_readiness.py` 会检查必填变量、占位值、密钥长度、数据库密码格式、Compose 合并结果以及后端生产配置。该检查不会连接 AI、PostgreSQL 或 Redis，也不会产生模型费用。

部署完成后人工验证：

```bash
curl --fail https://your-domain.example/api/health/live
curl --fail https://your-domain.example/api/health/ready
```

随后使用专用测试账号完成注册、PDF 上传、知识库处理、聊天、面试和报告流程。真实 AI 冒烟应限制调用次数并检查供应商账单。

## 备份与恢复演练

创建数据库和知识库文件备份：

```bash
python scripts/backup_production.py
```

备份默认写入 `backups/<UTC 时间>/`，包含 `database.dump`、`knowledge-storage/` 和记录 Git 提交的 `manifest.json`。为避免备份期间正好上传文件造成不一致，应在低流量维护窗口执行。将该目录同步到加密的异机存储，并设置保留周期。

恢复属于破坏性操作，只能在维护窗口执行。先停止 `api` 与 `worker`，为当前数据再做一次备份，然后在空白预发布实例中演练：

```bash
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml stop api worker
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml exec -T postgres \
  pg_restore --username=postgres --dbname=ai_interview --clean --if-exists \
  --no-owner --no-privileges < backups/<时间>/database.dump
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml cp \
  backups/<时间>/knowledge-storage/. api:/app/storage/
docker compose --env-file .env.production \
  -f docker-compose.yml -f compose.production.yml start api worker
```

恢复后必须重新检查 readiness、文件下载、知识库查询和一场完整面试。不要未经演练直接在正式环境执行恢复。
