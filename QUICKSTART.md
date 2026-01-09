# ⚡ 快速开始 - 自动化部署

## 🎯 5分钟完成服务器部署

### 第一步：在服务器上运行一键配置脚本

```bash
# 1. SSH登录到你的火山引擎服务器
ssh root@YOUR_SERVER_IP

# 2. 下载并运行配置脚本
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/Quant-bot/main/server-setup.sh | bash

# 或者手动下载后运行
wget https://raw.githubusercontent.com/YOUR_USERNAME/Quant-bot/main/server-setup.sh
chmod +x server-setup.sh
./server-setup.sh
```

这个脚本会自动完成:
- ✅ 更新系统
- ✅ 安装Docker和Docker Compose
- ✅ 配置防火墙
- ✅ 生成SSH密钥
- ✅ 克隆项目代码
- ✅ 创建必要目录

### 第二步：配置API密钥

```bash
# 编辑.env文件
cd /root/Quant-bot
vim .env
```

填入你的配置:
```bash
BINANCE_API_KEY=你的API_KEY
BINANCE_API_SECRET=你的API_SECRET
TRADING_MODE=testnet
```

保存：按`ESC`，输入`:wq`，回车

### 第三步：首次部署

```bash
cd /root/Quant-bot
./deploy.sh
```

等待3-5分钟，部署完成！

### 第四步：配置自动部署

1. **获取服务器信息**
   ```bash
   # 在服务器上运行
   echo "SERVER_HOST: $(hostname -I | awk '{print $1}')"
   echo "SERVER_USER: root"
   echo "SERVER_PORT: 22"
   cat ~/.ssh/github_deploy  # 这是SERVER_SSH_KEY的内容
   ```

2. **在GitHub上配置Secrets**
   - 访问: `https://github.com/YOUR_USERNAME/Quant-bot/settings/secrets/actions`
   - 点击"New repository secret"，添加:
     - `SERVER_HOST`: 服务器IP
     - `SERVER_USER`: root
     - `SERVER_SSH_KEY`: 上面的私钥内容
     - `SERVER_PORT`: 22

3. **测试自动部署**
   ```bash
   # 在本地
   echo "# 测试" >> README.md
   git add .
   git commit -m "test: 自动部署"
   git push origin main
   ```

4. **观察部署过程**
   - 访问: `https://github.com/YOUR_USERNAME/Quant-bot/actions`
   - 查看workflow运行状态

---

## 🎉 完成！

访问Dashboard:
- 简单版: `http://YOUR_SERVER_IP:8501`
- 专业版: `http://YOUR_SERVER_IP:8502`

---

## 📚 详细文档

需要更多信息？查看:
- [完整部署指南](DEPLOYMENT.md) - 详细的步骤说明
- [策略指南](STRATEGY_GUIDE.md) - 策略详解
- [README](README.md) - 项目总览

---

## 🆘 遇到问题？

### 常见问题快速解决

**容器未启动？**
```bash
docker-compose ps
docker-compose logs
```

**无法访问Dashboard？**
```bash
# 检查防火墙
ufw status
ufw allow 8501/tcp
ufw allow 8502/tcp
```

**自动部署失败？**
- 检查GitHub Secrets配置
- 查看Actions日志
- 在服务器手动运行: `cd /root/Quant-bot && git pull && ./deploy.sh`

更多故障排查：见 [DEPLOYMENT.md#故障排查](DEPLOYMENT.md#故障排查)
