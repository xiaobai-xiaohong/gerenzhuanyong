# Mnemosyne v5.2 · 认知型记忆操作系统

## 快速部署

### 1. 克隆
```bash
git clone https://github.com/xiaobai-xiaohong/gerenzhuanyong.git
cd gerenzhuanyong
```

### 2. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env，填入 MiniMax API Key
```

### 3. 启动
```bash
docker-compose up -d
```

### 4. 验证
```bash
docker-compose ps
curl http://localhost:8010/health
```

## API 调用示例

### 归档记忆
```bash
curl -X POST http://localhost:8010/api/v5/memory/archive \
  -H "Authorization: Bearer mnemosyne-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{"content": "pgvector索引创建失败，glibc版本过低", "content_type": "text", "category": "运维"}'
```

### 检索记忆
```bash
curl -X POST http://localhost:8010/api/v5/memory/search \
  -H "Authorization: Bearer mnemosyne-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{"query": "pgvector索引问题", "top_k": 3}'
```

## 目录结构
- `app/` — 核心业务代码
- `docker-compose.yml` — 三容器编排（mnemosyne-core + postgres + redis）
- `Dockerfile` — 应用镜像构建
- `requirements.txt` — Python 依赖
- `.env.example` — 环境变量模板
