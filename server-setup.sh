#!/bin/bash

# ========================================
# Quant-bot 服务器一键配置脚本
# 适用于全新的Ubuntu服务器
# ========================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
cat << "EOF"
  ____                   _          ____        _
 / ___| _   _  __ _ _ __ | |_ ______| __ )  ___ | |_
| |  | | | | |/ _` | '_ \| __|______|  _ \ / _ \| __|
| |__| |_| | | (_| | | | | |_ ______| |_) | (_) | |_
 \____\__,_| \__,_|_| |_|\__|______|____/ \___/ \__|

           服务器自动配置脚本 v1.0
EOF
echo -e "${NC}"

log_info() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_step() {
    echo -e "\n${BLUE}==>${NC} $1\n"
}

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then
    log_error "请使用root用户运行此脚本"
    exit 1
fi

# 步骤1: 更新系统
log_step "步骤1: 更新系统软件包"
apt update -y
apt upgrade -y
log_info "系统更新完成"

# 步骤2: 安装基础工具
log_step "步骤2: 安装基础工具"
apt install -y curl wget git vim htop ufw
log_info "基础工具安装完成"

# 步骤3: 配置时区
log_step "步骤3: 配置时区"
timedatectl set-timezone Asia/Singapore
log_info "时区设置为: $(timedatectl | grep "Time zone")"

# 步骤4: 安装Docker
log_step "步骤4: 安装Docker"

# 卸载旧版本
apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

# 安装依赖
apt install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# 添加Docker GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# 添加Docker仓库
echo \
  "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装Docker
apt update -y
apt install -y docker-ce docker-ce-cli containerd.io

# 启动Docker
systemctl start docker
systemctl enable docker

log_info "Docker安装完成: $(docker --version)"

# 步骤5: 安装Docker Compose
log_step "步骤5: 安装Docker Compose"
curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
log_info "Docker Compose安装完成: $(docker-compose --version)"

# 步骤6: 配置防火墙
log_step "步骤6: 配置防火墙"
ufw --force enable
ufw allow 22/tcp    # SSH
ufw allow 8501/tcp  # Dashboard
ufw allow 8502/tcp  # Professional Dashboard
log_info "防火墙配置完成"
ufw status

# 步骤7: 生成SSH密钥
log_step "步骤7: 生成SSH密钥（用于GitHub）"
if [ ! -f ~/.ssh/github_deploy ]; then
    read -p "请输入你的GitHub邮箱: " email
    ssh-keygen -t ed25519 -C "$email" -f ~/.ssh/github_deploy -N ""

    cat >> ~/.ssh/config << EOF
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/github_deploy
    StrictHostKeyChecking no
EOF
    chmod 600 ~/.ssh/config

    log_info "SSH密钥生成完成"
    echo ""
    log_warn "请将以下公钥添加到GitHub (https://github.com/settings/keys):"
    echo ""
    cat ~/.ssh/github_deploy.pub
    echo ""
    read -p "按Enter继续..."
else
    log_info "SSH密钥已存在，跳过生成"
fi

# 步骤8: 配置Git
log_step "步骤8: 配置Git"
read -p "请输入你的Git用户名: " git_name
read -p "请输入你的Git邮箱: " git_email
git config --global user.name "$git_name"
git config --global user.email "$git_email"
log_info "Git配置完成"

# 步骤9: 克隆项目
log_step "步骤9: 克隆项目"
cd /root

if [ -d "Quant-bot" ]; then
    log_warn "项目目录已存在，跳过克隆"
else
    read -p "请输入你的GitHub用户名: " github_user
    log_info "正在克隆项目..."
    git clone git@github.com:${github_user}/Quant-bot.git
    log_info "项目克隆完成"
fi

cd /root/Quant-bot

# 步骤10: 配置环境变量
log_step "步骤10: 配置环境变量"
if [ ! -f .env ]; then
    cp .env.example .env
    log_warn ".env文件已创建，请手动编辑填入你的API密钥"
    log_info "使用命令: vim /root/Quant-bot/.env"
else
    log_info ".env文件已存在"
fi

# 步骤11: 创建必要目录
log_step "步骤11: 创建必要目录"
mkdir -p data logs backups
chmod 755 data logs backups
log_info "目录创建完成"

# 步骤12: 测试Docker
log_step "步骤12: 测试Docker"
docker run hello-world
log_info "Docker测试成功"

# 完成
echo ""
echo "========================================"
log_info "🎉 服务器配置完成！"
echo "========================================"
echo ""
log_info "接下来的步骤:"
echo "  1. 编辑.env文件，填入你的Binance API密钥"
echo "     vim /root/Quant-bot/.env"
echo ""
echo "  2. 运行首次部署"
echo "     cd /root/Quant-bot"
echo "     chmod +x deploy.sh"
echo "     ./deploy.sh"
echo ""
echo "  3. 配置GitHub Secrets用于自动部署"
echo "     - SERVER_HOST: $(hostname -I | awk '{print $1}')"
echo "     - SERVER_USER: root"
echo "     - SERVER_SSH_KEY: 见下方私钥"
echo "     - SERVER_PORT: 22"
echo ""
log_warn "SSH私钥内容（复制到GitHub Secrets）:"
cat ~/.ssh/github_deploy
echo ""
log_info "详细文档: /root/Quant-bot/DEPLOYMENT.md"
echo "========================================"
