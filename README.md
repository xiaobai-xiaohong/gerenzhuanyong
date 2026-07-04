# MnemOS v6.0 — 认知记忆操作系统

> 一键部署认知记忆系统，支持 Trust Scoring、语义去重、半衰期衰减、7类记忆分类

## 一键部署

```bash
git clone https://github.com/xiaobai-xiaohong/gerenzhuanyong.git
cd gerenzhuanyong
cp .env.example .env
# 编辑 .env，填入 MODEL_API_KEY（MiniMax API Key）
bash deploy.sh
```

> **Windows**：打开 Docker Desktop → 运行 `bash deploy.sh`（Git Bash / MSYS2）
> **Linux/macOS**：直接运行 `bash deploy.sh`

部署完成后服务地址：http://localhost:8010

## 快速验证

```bash
curl http://localhost:8010/api/v5/health/full
docker ps --filter name=mnemosyne
```

## 获取 API Key

1. 访问 MiniMax 开放平台：https://platform.minimax.chat/
2. 注册并申请 API Key
3. 将 Key 填入 `.env` 文件的 `MODEL_API_KEY`
4. `MNEMOSYNE_API_KEY` 可自定义（随便写一个）

## 核心 API

| 接口 | 说明 |
|------|------|
| `POST /api/v5/memory/archive` | 归档记忆（支持 7 类分类） |
| `POST /api/v5/memory/search` | 语义检索（Trust 加权） |
| `GET /api/v5/memory/{id}` | 查看详情 |
| `POST /api/v5/tool/archive` | 归档工具结果 |
| `GET /api/v5/memory/trust-stats` | Trust 统计 |
| `POST /api/v5/memory/feedback` | Bayesian Trust 更新 |
| `GET /api/v5/health/full` | 完整健康检查 |

## v6.0 新特性

### Trust Scoring + Decay Engine
- Bayesian 平滑：`(trust*n + helpful) / (n+1)`
- 每周 5% 指数衰减：`decayed = trust * exp(-0.05 * weeks_elapsed)`
- 低于 0.3 的记忆注入时自动跳过

### Social Closer 废话过滤
- 识别并过滤无营养的废话、闲聊、安慰性表达
- 仅保留可操作的事实和洞察

### Jaccard 语义去重（阈值 0.85）
- 文本相似度 > 85% 的记忆自动跳过归档
- 避免重复记忆污染知识库

### 7类记忆分类
| 代码 | 类型 | 说明 |
|------|------|------|
| W | Workflow | 工作流铁律 |
| K | Knowledge | 工具知识 |
| I | Identity | 身份/人物 |
| D | Dialogue | 对话记录 |
| E | Pitfall | 踩坑记录 |
| R | Reflection | 反思总结 |
| S | Research | 研究探索 |

### CIRAAF 周维护自动化
- 每周日自动执行：Trust 重算、衰减扫描、去重、经验蒸馏

## 调用示例

```bash
# 归档记忆
curl -X POST http://localhost:8010/api/v5/memory/archive \
  -H "Content-Type: application/json" \
  -d '{"content": "pgvector索引创建失败", "content_type": "text", "memory_type": "E"}'

# 检索记忆
curl -X POST http://localhost:8010/api/v5/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "pgvector索引问题", "top_k": 3}'

# Trust 更新
curl -X POST http://localhost:8010/api/v5/memory/feedback \
  -H "Content-Type: application/json" \
  -d '{"memory_id": 1, "helpful": true}'
```

## 系统架构

```
mnemosyne-core (FastAPI :8010)
  ├─ 三馆闭环：归档→研究→工程→验收
  ├─ 三层检索：L0/L1/L2 语义+全文
  ├─ Trust Scoring + Decay Engine
  ├─ Social Closer 废话过滤
  ├─ Jaccard 语义去重
  └─ CIRAAF 自动化维护

依赖服务：
  ├─ PostgreSQL + pgvector (:5432)
  └─ Redis (:6379)
```

## 端口说明

| 端口 | 服务 |
|------|------|
| 8010 | mnemosyne-core 对外 API |
| 5432 | PostgreSQL 仅容器间 |
| 6379 | Redis 仅容器间 |

## 维护脚本（加入 cron）

```bash
# 每周二 02:30  扫描衰减
30 2 * * 2 cd /path/to/gerenzhuanyong && python3 scripts/decay_scanner.py

# 每周日 03:00  语义去重
0 3 * * 0 cd /path/to/gerenzhuanyong && python3 scripts/dedup_facts.py

# 每周日 04:00  Trust 重算
0 4 * * 0 cd /path/to/gerenzhuanyong && python3 scripts/recompute_trust.py

# 每周日 03:30  CIRAAF 维护
30 3 * * 0 cd /path/to/gerenzhuanyong && python3 scripts/ciraaf_sunday.py

# 每天 07:00  经验蒸馏
0 7 * * * cd /path/to/gerenzhuanyong && python3 scripts/experience_distiller.py
```

## Hermes 集成

MnemOS v6.0 已配置为 Hermes 的 MCP Server：

1. `config.yaml` 中已注册 `mcp_servers.mnemos`
2. Hermes 背景复盘（`review memory`）时自动引导模型调用 `mnemos_search` / `mnemos_feedback`

详见 `hermes-patch.diff`（已应用）。

## 常见问题

**Q: 检索不到内容？**
A: 确保 `MODEL_API_KEY` 正确，向量服务需要访问 MiniMax API

**Q: 容器启动失败？**
A: 检查 `.env` 文件是否存在且格式正确

**Q: 如何停止服务？**
A: `docker-compose down`

**Q: 如何更新？**
A: `git pull && bash deploy.sh`
