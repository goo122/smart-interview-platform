# RAG 离线评测基准

`dataset_v1.json` 是仅含合成简历的版本化评测集，覆盖 Java/Spring、Python/FastAPI、
React、数据分析和无关对照文档，以及精确匹配、改写、跨语言、短/长查询、缺失事实、
无关查询和跨知识库查询。每条查询记录所属用户、知识库、应命中的文档/Chunk、页码和
是否应返回结果。

## 当前检索链路

- `PgVectorRetriever` 使用 pgvector `cosine_distance`；检索分数为 `1 - cosine_distance`，
  查询按分数降序排列，语义为分数越高越相关。
- `RagContextProvider` 先校验 `user_id` 和 `knowledge_base_id`，再在数据库查询中限制
  `READY` 文档，并将阈值放入 SQL `WHERE similarity >= threshold`，不是查询后过滤。
- Chat RAG 使用请求显式传入的阈值/Top-K，缺省值来自 Settings；面试上下文使用同一默认
  阈值，若没有命中会在同一用户和知识库范围内做阈值为 0 的安全兜底。因此两者共享配置，
  但面试的空结果最终行为不同。
- Top-K 会在上下文层先按 `rag_max_top_k` 限制，在 Retriever 层再次限制到 1–100；上下文
  组装器还会因为去重和 token 预算进一步减少结果。
- 空 Chat 结果按 `rag_no_result_policy` 处理；面试在安全兜底后仍无内容则报告知识库不可用。
  引用由检索 Chunk 绑定文档、页码和分数，再由 `ContextAssembler` 分配来源编号。

## 运行

Fake 基准不访问网络，使用隔离的 PostgreSQL/pgvector/Redis Compose 项目，自动迁移、导入
合成数据、运行 8 个阈值 × 4 个 Top-K 的矩阵两次，并清理资源：

```powershell
python backend-python/scripts/run_rag_eval.py --mode fake
```

报告写入 `evals/rag/results/rag_eval_fake.json` 和 `.md`，只包含指标，不保存原始向量。
真实校准只能显式执行，并且必须通过 `RUN_REAL_RAG_EVAL=1`、`openai_compatible`、
`text-embedding-v4`、1536 维校验；评测脚本不会调用 Chat Model。真实模式针对
DashScope 每批最多 10 条输入，默认将缓存放在系统临时目录，缓存键包含模型、维度和输入哈希。

Fake Embedding 是稳定哈希向量，只用于验证评测框架、指标计算、pgvector 查询和用户/知识库
隔离，不能据此选择生产阈值。真实 Embedding 校准前必须取得明确授权。
