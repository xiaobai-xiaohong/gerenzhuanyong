#!/bin/bash
###############################################################################
# MnemOS v6.0 一键部署脚本
# 使用方法: bash deploy.sh
# 适用环境: Windows (Git-Bash/MSYS) 或 Linux/macOS
###############################################################################
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo " MnemOS v6.0 部署脚本"
echo "=========================================="

# 颜色输出
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# 1. 检查 Docker
info "检查 Docker 环境..."
if ! command -v docker &> /dev/null; then
    error "Docker 未安装"
fi
docker info &> /dev/null || error "Docker 未运行，请启动 Docker Desktop"

# 2. 检查 .env 文件
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        warn ".env 不存在，从 .env.example 复制..."
        cp .env.example .env
        echo ""
        echo "⚠️  请编辑 .env 填入你的 MiniMax API Key!"
        echo "   路径: $SCRIPT_DIR/.env"
        echo ""
        read -p "按回车继续（已填好 API Key）..."
    else
        error ".env 和 .env.example 都不存在"
    fi
fi

# 3. 数据库迁移（如需要）
info "检查数据库迁移..."
echo "如果这是首次从 v5.2 升级到 v6.0，"
echo "迁移 SQL 会通过 docker-compose exec 自动执行"
echo "（已在首次部署时完成，如有需要可重新运行 scripts/migrate_v6.py）"

# 4. 构建 + 启动
info "构建 v6.0 镜像..."
docker-compose build mnemosyne-core

info "启动服务..."
docker-compose up -d

# 5. 等待服务健康
info "等待服务启动（30秒）..."
sleep 25

# 6. 健康检查
info "执行健康检查..."
HEALTH=$(curl -sf http://localhost:8010/api/v5/health/full 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(d.get('version','?')+'/'+str(d.get('memory_stats',{}).get('total',0)))" 2>/dev/null || echo "FAILED")

if [ "$HEALTH" != "FAILED" ] && [ -n "$HEALTH" ]; then
    info "部署成功！版本: $HEALTH"
else
    error "健康检查失败，请检查: docker-compose logs mnemosyne-core"
fi

# 7. 显示状态
echo ""
echo "=========================================="
echo " MnemOS v6.0 部署完成"
echo "=========================================="
docker-compose ps
echo ""
echo "访问地址: http://localhost:8010"
echo "API文档:  http://localhost:8010/docs"
echo ""
echo "核心新增功能:"
echo "  - Trust Scoring + Decay Engine"
echo "  - Social Closer 废话过滤"
echo "  - Jaccard 语义去重 (阈值0.85)"
echo "  - 7类记忆分类 (W/K/I/D/E/R/S)"
echo "  - pre-LLM inject-context hook"
echo "  - CIRAAF 周日自动化维护"
echo ""
echo "维护脚本（需手动加入 cron）:"
echo "  30 2 * * * cd $SCRIPT_DIR && python3 scripts/decay_scanner.py"
echo "  0 3 * * 0 cd $SCRIPT_DIR && python3 scripts/dedup_facts.py"
echo "  0 4 * * 0 cd $SCRIPT_DIR && python3 scripts/recompute_trust.py"
echo "  30 3 * * 0 cd $SCRIPT_DIR && python3 scripts/ciraaf_sunday.py"
echo "  0 7 * * * cd $SCRIPT_DIR && python3 scripts/experience_distiller.py"
echo ""
