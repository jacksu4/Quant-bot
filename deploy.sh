#!/bin/bash

# ========================================
# Quant-bot 自动部署脚本
# ========================================

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 检查是否在项目根目录
if [ ! -f "docker-compose.yml" ]; then
    log_error "请在项目根目录运行此脚本！"
    exit 1
fi

# 检查必需文件
log_step "检查必需文件..."
if [ ! -f ".env" ]; then
    log_error ".env 文件不存在！请先创建 .env 文件。"
    log_info "参考 .env.example 创建 .env 文件"
    exit 1
fi

# 创建必要的目录
log_step "创建必要的目录..."
mkdir -p data logs backups

# 备份数据（如果存在）
log_step "备份交易数据..."
if [ -d "data" ] && [ "$(ls -A data 2>/dev/null)" ]; then
    BACKUP_FILE="backups/data_backup_$(date +%Y%m%d_%H%M%S).tar.gz"
    tar -czf "$BACKUP_FILE" data/ 2>/dev/null || true
    log_info "数据已备份到: $BACKUP_FILE"

    # 保留最近7天的备份
    find backups/ -name "data_backup_*.tar.gz" -mtime +7 -delete 2>/dev/null || true
else
    log_warn "没有发现交易数据，跳过备份"
fi

# 停止现有容器（如果存在）
log_step "停止现有容器..."
if docker-compose ps -q | grep -q .; then
    docker-compose down
    log_info "已停止现有容器"
else
    log_info "没有运行中的容器"
fi

# 清理旧的容器和镜像
log_step "清理旧容器和镜像..."
docker container prune -f || true
docker image prune -f || true

# 构建新镜像
log_step "构建 Docker 镜像..."
docker-compose build --no-cache aggressive-strategy dashboard

# 启动服务 - 默认只启动激进策略和Dashboard
log_step "启动服务..."
docker-compose up -d aggressive-strategy dashboard

# 等待服务启动
log_step "等待服务启动..."
sleep 15

# 检查服务状态
log_step "检查服务状态..."
docker-compose ps

# 显示日志（最后20行）
log_step "查看最近日志..."
docker-compose logs --tail=20

# 运行健康检查
log_step "运行健康检查..."
HEALTHY=true

# 检查激进策略容器（默认策略）
if docker-compose ps | grep -q "quant-aggressive-strategy.*Up"; then
    log_info "✅ 激进动量策略容器运行正常"
else
    log_warn "❌ 激进动量策略容器未运行"
    HEALTHY=false
fi

if docker-compose ps | grep -q "quant-dashboard.*Up"; then
    log_info "✅ Dashboard容器运行正常"
else
    log_warn "❌ Dashboard容器未运行"
    HEALTHY=false
fi

# 最终状态
echo ""
echo "========================================"
if [ "$HEALTHY" = true ]; then
    log_info "🎉 部署成功！所有服务运行正常"
    log_info "📊 Dashboard地址:"
    log_info "   - 简单Dashboard: http://$(hostname -I | awk '{print $1}'):8501"
    log_info "   - 专业Dashboard: http://$(hostname -I | awk '{print $1}'):8502"
else
    log_warn "⚠️  部署完成，但部分服务未运行"
    log_info "请检查日志: docker-compose logs"
fi
echo "========================================"
echo ""

# 显示监控命令
log_info "常用监控命令:"
echo "  docker-compose ps          # 查看服务状态"
echo "  docker-compose logs -f     # 实时查看日志"
echo "  docker-compose restart     # 重启所有服务"
echo "  docker-compose down        # 停止所有服务"

exit 0
