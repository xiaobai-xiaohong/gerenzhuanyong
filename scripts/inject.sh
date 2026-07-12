#!/bin/bash
# MnemOS Shell Hook — pre_llm_call 注入脚本
# 对标 duMem 的 mem0-inject.sh
#
# 用法：
#   1. 在 Hermes 的 pre_llm_call Hook 中配置：
#      pre_llm_call: bash /path/to/inject.sh "<query>"
#
#   2. 或者手动调用：
#      bash inject.sh "Docker 部署问题"
#
# 环境变量：
#   MNEMOSYNE_URL - 服务地址（默认 http://localhost:8010）

set -euo pipefail

MNEMOSYNE_URL="${MNEMOSYNE_URL:-http://localhost:8010}"
QUERY="${1:-}"
TIMEOUT=2  # 2秒超时，失败不阻塞 LLM

if [ -z "$QUERY" ]; then
    echo ""
    exit 0
fi

# URL 编码查询
ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$QUERY'))" 2>/dev/null || echo "$QUERY")

# 调用 inject API（带超时）
RESULT=$(curl -s --max-time "$TIMEOUT" \
    -X POST "${MNEMOSYNE_URL}/api/v5/memory/inject?query=${ENCODED}&depth=L0&top_k=3" \
    2>/dev/null || echo '{"data":{"context":""}}')

# 提取 context 字段
CONTEXT=$(echo "$RESULT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('data', {}).get('context', ''))
except:
    print('')
" 2>/dev/null || echo "")

# 输出注入上下文
if [ -n "$CONTEXT" ]; then
    echo "$CONTEXT"
fi
