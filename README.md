# 🧠 MnemOS v6.1 — 认知记忆操作系统

> **一句话**：为 AI Agent 提供长期记忆能力，支持语义检索、Trust 评分、自动提取、Shell Hook 注入、MCP 协议。

**版本**：v6.1.0  
**更新日期**：2026-07-12  
**适用对象**：Hermes Agent / 任何需要长期记忆的 AI Agent

---

## ✨ 核心特性

| 特性 | 说明 |
|------|------|
| 🔄 **语义检索** | SiliconFlow BGE-M3 向量嵌入，混合语义 + 全文检索 |
| 📊 **Trust 评分** | Bayesian 平滑，区分对错事实，低于 0.3 自动跳过 |
| ⏰ **半衰期衰减** | 老记忆自动归档，防止信息膨胀 |
| 🔁 **语义去重** | Jaccard 相似度 > 0.85 自动跳过 |
| 🗑️ **废话过滤** | Social Closer 过滤 "ok" "👍" 等无意义内容 |
| 🤖 **自动提取** | LLM 自动从对话中提取关键事实 |
| 🔌 **Shell Hook** | pre_llm_call 注入相关记忆到 LLM 上下文 |
| 🛡️ **安全认证** | API Key 认证，端口仅本机访问 |
| 🔗 **MCP 协议** | 标准 MCP 工具，Hermes 直接调用 |
| 🐍 **Python SDK** | 一行代码归档、检索、注入记忆 |
| 📚 **知识谱系** | 记录"哪个方案在什么场景下最好" |

---

## 🚀 一键部署

### 前置条件

- Docker Desktop (Windows/Mac) 或 Docker Engine (Linux)
- SiliconFlow API Key（免费注册：https://siliconflow.cn/）

### 5 分钟部署

```bash
# 1. 克隆仓库
git clone https://github.com/xiaobai-xiaohong/gerenzhuanyong.git
cd gerenzhuanyong

# 2. 复制配置文件
cp .env.example .env

# 3. 编辑 .env，填入你的 SiliconFlow API Key
#    SILICONFLOW_API_KEY=sk-xxxxxxx
#    LLM_API_KEY=sk-xxxxxxx  (同一个 Key 即可)

# 4. 一键部署
bash deploy.sh
```

### 验证部署

```bash
# 健康检查
curl http://127.0.0.1:8010/health

# 查看容器状态
docker ps --filter name=mnemosyne
```

---

## 🐍 Python SDK

### 安装

```bash
# 无需安装，直接使用
from sdk.mnemosyne import MnemosyneClient
```

### 快速开始

```python
from sdk.mnemosyne import MnemosyneClient

# 初始化客户端
c = MnemosyneClient(
    base_url="http://127.0.0.1:8010",
    api_key="your-api-key"
)

# 归档记忆
c.archive("Docker Hub 国内需要配置镜像加速", memory_type="E")

# 语义检索
results = c.search("Docker 部署问题", top_k=3)

# 获取注入上下文
context = c.inject("当前对话主题")

# LLM 提取事实
c.extract("今天遇到了Redis问题...", memory_type="E")

# Trust 反馈
c.feedback("mem_xxx", helpful=True)

# 统计信息
stats = c.stats()
```

---

## 🔗 MCP 协议

### 工具列表

| 工具 | 说明 |
|------|------|
| `mnemosyne_archive` | 归档记忆 |
| `mnemosyne_search` | 语义检索 |
| `mnemosyne_inject` | 获取注入上下文 |
| `mnemosyne_feedback` | Trust 反馈 |
| `mnemosyne_stats` | 统计信息 |

### 在 Hermes 中使用

```json
{
  "mcpServers": {
    "mnemosyne": {
      "command": "python",
      "args": ["mnemos-mcp/server.py"],
      "env": {
        "MNEMOSYNE_URL": "http://127.0.0.1:8010",
        "MNEMOSYNE_API_KEY": "your-api-key"
      }
    }
  }
}
```

---

## 📚 知识谱系

记录"哪个方案在什么场景下最好"，不只是存事实，还能追踪最佳实践。

### API 接口

```bash
# 添加知识谱系
curl -X POST "http://127.0.0.1:8010/api/v5/genealogy/add?knowledge_id=mem_xxx&scenario=Docker部署&solution=配置镜像加速" \
  -H "x-api-key: your-key"

# 记录使用结果
curl -X POST "http://127.0.0.1:8010/api/v5/genealogy/record?genealogy_id=xxx&success=true" \
  -H "x-api-key: your-key"

# 查找最佳方案
curl -X POST "http://127.0.0.1:8010/api/v5/genealogy/find?scenario=Docker" \
  -H "x-api-key: your-key"
```

---

## 📡 API 接口

### 认证方式

所有写入接口需要在 Header 中携带 API Key：

```
x-api-key: <你的 MNEMOSYNE_API_KEY>
```

### 核心接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查（无需认证） |
| `/api/v5/memory/archive` | POST | 归档记忆 |
| `/api/v5/memory/search` | POST | 语义检索 |
| `/api/v5/memory/inject` | POST | Shell Hook 注入 |
| `/api/v5/memory/extract` | POST | LLM 提取事实 |
| `/api/v5/memory/feedback` | POST | Trust 反馈 |
| `/api/v5/memory/trust-stats` | GET | Trust 统计 |
| `/api/v5/genealogy/add` | POST | 添加知识谱系 |
| `/api/v5/genealogy/find` | POST | 查找最佳方案 |
| `/api/v5/genealogy/stats` | GET | 谱系统计 |

---

## 🏷️ 7 类记忆类型

| 代码 | 类型 | 说明 |
|------|------|------|
| W | 铁律 | 不可违反的规则 |
| K | 工具 | 工具使用知识 |
| I | 人物 | 人物信息 |
| D | 对话 | 对话记录 |
| E | 踩坑 | 踩坑记录（含解决方案） |
| R | 反思 | 反思总结 |
| S | 研究 | 研究探索 |

---

## 🔧 配置说明

### .env 配置项

```bash
# 嵌入模型（必填）
MODEL_PROVIDER=siliconflow
SILICONFLOW_API_KEY=sk-xxxxxxx

# LLM 提取（可选，用于自动提取）
LLM_API_KEY=sk-xxxxxxx
LLM_BASE_URL=https://api.siliconflow.cn
LLM_MODEL=deepseek-ai/deepseek-v4-flash

# 安全（必填）
MNEMOSYNE_API_KEY=<自定义API密钥>

# 自动提取（可选）
AUTO_EXTRACT_ENABLED=true
AUTO_EXTRACT_INTERVAL=3600
```

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────┐
│                 FastAPI 服务 (:8010)                 │
├─────────────────────────────────────────────────────┤
│  归档 API │ 搜索 API │ 注入 API │ 提取 API         │
│  MCP 服务 │ SDK 接口 │ 知识谱系                    │
├─────────────────────────────────────────────────────┤
│              核心服务层                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐    │
│  │ 三馆管线 │ │ 检索引擎 │ │ 自动提取服务     │    │
│  └────┬─────┘ └────┬─────┘ └────────┬─────────┘    │
│       │            │                │               │
│  ┌────▼────────────▼────────────────▼──────────┐    │
│  │        SiliconFlow 嵌入 (BGE-M3)            │    │
│  └─────────────────┬───────────────────────────┘    │
│                    │                                │
│  ┌─────────────────▼───────────────────────────┐    │
│  │  辅助引擎：去重 │ 废话过滤 │ Trust + Decay  │    │
│  │  知识谱系 │ MCP 协议                        │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
                        │
          ┌─────────────▼─────────────┐
          │   PostgreSQL + pgvector    │
          │   (向量存储 + 元数据)      │
          └───────────────────────────┘
```

---

## 📁 项目结构

```
gerenzhuanyong/
├── app/
│   ├── core/           # 配置、数据库
│   ├── models/         # 数据模型
│   ├── routers/        # API 路由
│   ├── schemas/        # 请求/响应模型
│   └── services/       # 核心业务逻辑
├── sdk/
│   └── mnemosyne.py    # Python SDK
├── mnemos-mcp/
│   └── server.py       # MCP 协议服务端
├── scripts/
│   ├── inject.sh       # Shell Hook 脚本
│   └── *.py            # 维护脚本
├── docker-compose.yml
├── Dockerfile
├── deploy.sh           # 一键部署
└── .env.example        # 配置模板
```

---

## 📄 License

MIT

---

> 🐒 让 AI 拥有真正的记忆
