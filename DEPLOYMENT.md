# 🚀 Quant-bot 自动化部署指南

本指南将一步步教你如何在火山引擎服务器上部署量化交易系统，并实现自动化CI/CD。

---

## 📋 目录

1. [前置准备](#前置准备)
2. [服务器初始配置](#服务器初始配置)
3. [安装必要软件](#安装必要软件)
4. [部署项目](#部署项目)
5. [配置GitHub自动部署](#配置github自动部署)
6. [测试自动部署](#测试自动部署)
7. [监控和维护](#监控和维护)
8. [故障排查](#故障排查)

---

## 前置准备

### 你需要:
- ✅ 火山引擎服务器 (马来西亚柔佛)
- ✅ 服务器SSH访问权限
- ✅ GitHub账号和仓库
- ✅ Binance API Key和Secret

### 推荐服务器配置:
- **CPU**: 2核或以上
- **内存**: 4GB或以上
- **存储**: 40GB或以上
- **系统**: Ubuntu 20.04/22.04 LTS

---

## 服务器初始配置

### 1. 登录服务器

```bash
# 从本地终端登录（使用火山引擎提供的IP和密码）
ssh root@YOUR_SERVER_IP

# 首次登录后，建议修改root密码
passwd
```

### 2. 更新系统

```bash
# 更新软件包列表
apt update

# 升级所有软件包
apt upgrade -y

# 安装基础工具
apt install -y curl wget git vim htop
```

### 3. 配置时区

```bash
# 设置为新加坡时区（适合马来西亚）
timedatectl set-timezone Asia/Singapore

# 验证时区
date
```

### 4. 配置防火墙

```bash
# 安装ufw防火墙
apt install -y ufw

# 允许SSH（重要！避免被锁在外面）
ufw allow 22/tcp

# 允许Dashboard端口
ufw allow 8501/tcp
ufw allow 8502/tcp

# 启用防火墙
ufw enable

# 检查状态
ufw status
```

---

## 安装必要软件

### 1. 安装Docker

```bash
# 卸载旧版本（如果有）
apt remove docker docker-engine docker.io containerd runc

# 安装依赖
apt install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# 添加Docker官方GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# 添加Docker仓库
echo \
  "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装Docker
apt update
apt install -y docker-ce docker-ce-cli containerd.io

# 启动Docker服务
systemctl start docker
systemctl enable docker

# 验证安装
docker --version
docker run hello-world
```

### 2. 安装Docker Compose

```bash
# 下载Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# 添加执行权限
chmod +x /usr/local/bin/docker-compose

# 验证安装
docker-compose --version
```

---

## 部署项目

### 1. 生成SSH密钥（用于GitHub）

```bash
# 生成SSH密钥对
ssh-keygen -t ed25519 -C "your_email@example.com" -f ~/.ssh/github_deploy -N ""

# 查看公钥（稍后添加到GitHub）
cat ~/.ssh/github_deploy.pub

# 配置SSH
cat >> ~/.ssh/config << EOF
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/github_deploy
    StrictHostKeyChecking no
EOF

chmod 600 ~/.ssh/config
```

**重要**: 复制公钥内容，然后：
1. 访问 https://github.com/settings/keys
2. 点击 "New SSH key"
3. 粘贴公钥内容
4. 保存

### 2. 克隆项目

```bash
# 进入root目录
cd /root

# 克隆项目
git clone git@github.com:YOUR_USERNAME/Quant-bot.git

# 进入项目目录
cd Quant-bot

# 验证分支
git branch
git status
```

### 3. 配置环境变量

```bash
# 创建.env文件
cp .env.example .env

# 编辑.env文件
vim .env
```

在.env文件中填入你的配置:

```bash
# Binance API配置
BINANCE_API_KEY=你的API_KEY
BINANCE_API_SECRET=你的API_SECRET

# 交易模式 (testnet 或 mainnet)
TRADING_MODE=testnet

# 日志级别
LOG_LEVEL=INFO
```

**保存**: 按`ESC`，输入`:wq`，回车

### 4. 创建必要目录

```bash
# 在项目根目录下
mkdir -p data logs backups

# 设置权限
chmod 755 data logs backups
```

### 5. 首次部署

```bash
# 赋予部署脚本执行权限
chmod +x deploy.sh

# 运行部署脚本
./deploy.sh
```

### 6. 验证部署

```bash
# 查看容器状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 按Ctrl+C退出日志查看
```

预期输出:
```
NAME                         COMMAND                  SERVICE                STATUS
quant-dashboard              "streamlit run..."       dashboard              running
quant-professional-strategy  "python -u profes..."    professional-strategy  running
quant-rsi-strategy          "python -u run_st..."    rsi-strategy           running
```

---

## 配置GitHub自动部署

### 1. 在GitHub上配置Secrets

访问你的GitHub仓库: `https://github.com/YOUR_USERNAME/Quant-bot/settings/secrets/actions`

点击 "New repository secret"，添加以下secrets:

| Secret Name | Value | 说明 |
|------------|-------|------|
| `SERVER_HOST` | 服务器IP地址 | 例如: `123.456.789.0` |
| `SERVER_USER` | `root` | SSH用户名 |
| `SERVER_SSH_KEY` | 私钥内容 | 见下方获取方法 |
| `SERVER_PORT` | `22` | SSH端口（默认22） |

### 2. 获取SSH私钥

在服务器上运行:

```bash
# 查看私钥
cat ~/.ssh/github_deploy
```

复制**整个输出**（包括`-----BEGIN OPENSSH PRIVATE KEY-----`和`-----END OPENSSH PRIVATE KEY-----`），粘贴到`SERVER_SSH_KEY`。

### 3. 配置服务器接受Git Pull

```bash
# 配置Git（避免每次pull都要输入密码）
cd /root/Quant-bot

git config --global user.email "your_email@example.com"
git config --global user.name "Your Name"

# 测试Git连接
ssh -T git@github.com
# 应该看到: "Hi YOUR_USERNAME! You've successfully authenticated..."
```

---

## 测试自动部署

### 本地测试流程

1. **在本地修改代码** (例如修改README.md)

```bash
# 在本地仓库
cd ~/Desktop/Github/Quant-bot

# 修改一个文件
echo "# 测试自动部署" >> README.md

# 查看修改
git status
```

2. **提交并推送到main分支**

```bash
git add .
git commit -m "test: 测试自动部署功能"
git push origin main
```

3. **观察GitHub Actions**

- 访问 `https://github.com/YOUR_USERNAME/Quant-bot/actions`
- 你应该看到一个新的workflow正在运行
- 点击进入查看详细日志

4. **验证服务器上的部署**

```bash
# SSH到服务器
ssh root@YOUR_SERVER_IP

# 进入项目目录
cd /root/Quant-bot

# 查看最新commit
git log -1

# 查看容器状态
docker-compose ps

# 查看部署日志
docker-compose logs --tail=50
```

---

## 监控和维护

### 日常监控命令

```bash
# 查看服务状态
docker-compose ps

# 实时查看日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f rsi-strategy
docker-compose logs -f professional-strategy
docker-compose logs -f dashboard

# 查看系统资源
htop

# 查看磁盘空间
df -h

# 查看内存使用
free -h
```

### 常用维护命令

```bash
# 重启所有服务
docker-compose restart

# 重启特定服务
docker-compose restart rsi-strategy

# 停止所有服务
docker-compose down

# 启动所有服务
docker-compose up -d

# 查看容器资源使用
docker stats

# 清理未使用的镜像和容器
docker system prune -a
```

### 备份和恢复

```bash
# 手动备份
cd /root/Quant-bot
tar -czf ~/quant-bot-backup-$(date +%Y%m%d).tar.gz data/ .env

# 恢复备份
cd /root/Quant-bot
tar -xzf ~/quant-bot-backup-20260109.tar.gz

# 查看备份
ls -lh ~/quant-bot-backup-*.tar.gz
```

### 定时任务（可选）

创建每日备份的cron任务:

```bash
# 编辑crontab
crontab -e

# 添加以下行（每天凌晨2点备份）
0 2 * * * cd /root/Quant-bot && tar -czf ~/backups/quant-bot-$(date +\%Y\%m\%d).tar.gz data/ .env

# 保存退出
```

---

## 故障排查

### 问题1: 容器启动失败

```bash
# 查看详细错误
docker-compose logs

# 查看特定容器日志
docker-compose logs rsi-strategy

# 重新构建并启动
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### 问题2: GitHub Actions部署失败

1. 检查GitHub Secrets是否正确配置
2. 检查SSH密钥是否正确
3. 在服务器上手动运行部署脚本:

```bash
cd /root/Quant-bot
git pull origin main
./deploy.sh
```

### 问题3: 无法访问Dashboard

```bash
# 检查容器是否运行
docker-compose ps

# 检查端口是否开放
ufw status

# 检查Dashboard日志
docker-compose logs dashboard

# 测试端口连接（从本地）
curl http://YOUR_SERVER_IP:8501
```

### 问题4: API连接失败

```bash
# 进入容器测试
docker-compose exec rsi-strategy python -c "
from exchange import BinanceClient
client = BinanceClient()
print(client.get_mode_str())
print(client.get_balance())
"

# 检查.env配置
cat .env
```

### 问题5: 磁盘空间不足

```bash
# 查看磁盘使用
df -h

# 清理Docker
docker system prune -a -f

# 清理日志
docker-compose logs --tail=0 > /dev/null

# 删除旧备份
find ~/backups -name "*.tar.gz" -mtime +30 -delete
```

---

## 高级配置

### 配置Nginx反向代理（可选）

如果你想通过域名访问Dashboard:

```bash
# 安装Nginx
apt install -y nginx

# 创建配置文件
cat > /etc/nginx/sites-available/quant-bot << 'EOF'
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /professional {
        proxy_pass http://localhost:8502;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

# 启用配置
ln -s /etc/nginx/sites-available/quant-bot /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

### 配置SSL证书（可选）

```bash
# 安装certbot
apt install -y certbot python3-certbot-nginx

# 获取SSL证书
certbot --nginx -d your-domain.com

# 证书会自动续期
```

---

## 安全建议

1. **定期更新系统**
   ```bash
   apt update && apt upgrade -y
   ```

2. **修改SSH端口** (可选)
   ```bash
   # 编辑SSH配置
   vim /etc/ssh/sshd_config
   # 修改Port 22为其他端口，如Port 2222
   systemctl restart sshd
   ```

3. **禁用密码登录，只允许密钥登录**
   ```bash
   vim /etc/ssh/sshd_config
   # 设置: PasswordAuthentication no
   systemctl restart sshd
   ```

4. **配置fail2ban防止暴力破解**
   ```bash
   apt install -y fail2ban
   systemctl enable fail2ban
   systemctl start fail2ban
   ```

5. **定期检查日志**
   ```bash
   tail -f /var/log/auth.log
   ```

---

## 完整工作流程总结

```
本地开发 → 测试 → git push → GitHub Actions触发 → SSH到服务器 →
git pull → 运行deploy.sh → 重新构建镜像 → 重启容器 → 健康检查 → 完成
```

### 日常开发流程:

1. **本地开发和测试**
   ```bash
   # 修改代码
   vim strategy.py

   # 本地测试
   python run_strategy.py
   ```

2. **提交到main分支**
   ```bash
   git add .
   git commit -m "feat: 添加新策略"
   git push origin main
   ```

3. **自动部署**
   - GitHub Actions自动触发
   - 服务器自动pull最新代码
   - 自动重新构建和部署

4. **验证**
   - 访问Dashboard查看运行状态
   - 检查日志确认无误

---

## 联系和支持

如果遇到问题:
1. 查看本文档的[故障排查](#故障排查)章节
2. 查看GitHub Issues
3. 查看docker-compose日志

---

**最后更新**: 2026-01-09

**祝你部署顺利！** 🚀
