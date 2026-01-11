# Quant-bot - 量化交易系统

专业级加密货币量化交易系统，支持多策略、自动化部署和实时监控。

---

## 🎯 策略选择

本项目包含三套策略，根据你的需求选择：

| 策略 | 适用人群 | 资金规模 | 预期夏普比率 | 最大回撤 |
|------|----------|----------|--------------|----------|
| **简单RSI策略** | 新手 | $100-1,000 | ~1.0 | 可能>30% |
| **Robust RSI策略** ⭐推荐 | 追求稳定 | $500-10,000 | >1.5 | <10% |
| **专业多策略系统** | 机构/进阶 | $10,000+ | >2.0 | <15% |

---

## 🚀 快速开始

### 1. 安装

```bash
# 克隆仓库
git clone https://github.com/jacksu4/Quant-bot.git
cd Quant-bot

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置 (重要!)
vim .env
```

**.env 配置说明:**
```bash
# Binance API密钥
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret

# 交易模式 (非常重要!)
TRADING_MODE=live      # live=真实交易, testnet=测试网

# 风控参数
MAX_POSITION_SIZE_USDT=15    # 单次最大交易$15
STOP_LOSS_PERCENT=3.0        # 止损3%
TAKE_PROFIT_PERCENT=5.0      # 止盈5%
```

### 3. 运行策略

```bash
# 方式1: 直接运行 (推荐Robust策略)
python run_robust_strategy.py

# 方式2: Docker运行
docker-compose up -d robust-strategy dashboard
```

### 4. 查看Dashboard

```bash
# 本地运行
streamlit run dashboard.py

# 访问地址
http://localhost:8501
```

---

## 📊 策略详解

### 策略1: 简单RSI均值回归

**核心逻辑:**
- RSI < 30 (超卖) → 买入
- RSI > 70 (超买) → 卖出
- 止损: -3%, 止盈: +5%

```bash
python run_strategy.py
```

### 策略2: Robust RSI策略 ⭐推荐

**特点:**
- 多时间框架确认 (1H + 4H)
- EMA趋势过滤
- ATR波动率调整仓位
- 动态止损止盈

**目标性能:**
- 夏普比率 > 1.5
- 最大回撤 < 10%
- 胜率 > 55%

```bash
python run_robust_strategy.py
```

### 策略3: 专业多策略系统

**5大策略组合:**
| 策略 | 权重 | 说明 |
|------|------|------|
| 多因子选币 | 40% | 6因子综合评分 |
| 趋势跟踪 | 25% | EMA/MACD/ADX |
| 统计套利 | 15% | 配对交易 |
| 波动率突破 | 10% | 布林带突破 |
| 动态对冲 | 10% | 市场状态调整 |

```bash
python professional_strategy.py
```

---

## 🔄 策略切换

### 本地运行切换

```bash
# 简单RSI
python run_strategy.py

# Robust RSI (推荐)
python run_robust_strategy.py

# 专业多策略
python professional_strategy.py
```

### Docker切换

```bash
# 停止当前策略
docker-compose down

# 启动指定策略
docker-compose up -d rsi-strategy dashboard          # 简单RSI
docker-compose up -d robust-strategy dashboard       # Robust RSI
docker-compose up -d professional-strategy dashboard # 专业多策略

# 或使用profile
docker-compose --profile robust up -d
```

---

## 🖥️ Dashboard访问

### 本地访问
```
简单Dashboard:   http://localhost:8501
专业Dashboard:   http://localhost:8502
```

### 服务器访问
部署到服务器后:
```
简单Dashboard:   http://服务器IP:8501
专业Dashboard:   http://服务器IP:8502
```

**安全建议:**
- 配置防火墙限制访问IP
- 使用Nginx反向代理+HTTPS
- 添加Basic Auth认证

---

## 🚢 服务器部署

### 方式1: 自动部署 (推荐)

本项目已配置GitHub Actions，推送到main分支自动部署:

```bash
# 本地修改后
git add .
git commit -m "更新配置"
git push origin main
# GitHub Actions自动部署到服务器
```

**GitHub Secrets配置:**
1. 进入仓库 Settings > Secrets and variables > Actions
2. 添加以下secrets:
   - `SERVER_HOST`: 服务器IP
   - `SERVER_USER`: SSH用户名 (通常是root)
   - `SERVER_SSH_KEY`: SSH私钥
   - `SERVER_PORT`: SSH端口 (默认22)

### 方式2: 手动部署

```bash
# SSH登录服务器
ssh root@服务器IP

# 进入项目目录
cd /root/Quant-bot

# 拉取最新代码
git pull origin main

# 部署
bash deploy.sh

# 查看状态
docker-compose ps
```

---

## 📁 项目结构

```
Quant-bot/
├── 策略文件
│   ├── strategy.py              # 简单RSI策略
│   ├── robust_strategy.py       # Robust RSI策略 ⭐
│   ├── professional_strategy.py # 专业多策略
│   ├── run_strategy.py          # RSI运行器
│   ├── run_robust_strategy.py   # Robust运行器
│
├── 核心模块
│   ├── exchange.py              # Binance API封装
│   ├── risk_manager.py          # 风险管理
│   ├── multi_factor_engine.py   # 多因子引擎
│   ├── indicators.py            # 技术指标库
│
├── 前端
│   ├── dashboard.py             # 简单Dashboard
│   ├── professional_dashboard.py# 专业Dashboard
│
├── 部署
│   ├── docker-compose.yml       # Docker编排
│   ├── Dockerfile.*             # 各策略容器
│   ├── deploy.sh                # 部署脚本
│
├── CI/CD
│   └── .github/workflows/
│       ├── deploy.yml           # 自动部署
│       └── test.yml             # 自动测试
│
└── 配置
    ├── .env                     # API配置 (不提交)
    ├── .env.example             # 配置模板
    └── requirements.txt         # Python依赖
```

---

## ⚙️ 常用命令

### 策略管理
```bash
# 单次运行
python run_robust_strategy.py --once

# 自定义间隔 (秒)
python run_robust_strategy.py --interval 60
```

### Docker管理
```bash
docker-compose up -d           # 启动
docker-compose ps              # 状态
docker-compose logs -f         # 日志
docker-compose restart         # 重启
docker-compose down            # 停止
```

### 监控
```bash
docker-compose logs --tail=100 robust-strategy
tail -f data/robust_strategy_log.json
bash healthcheck.sh
```

### 备份
```bash
tar -czf backup_$(date +%Y%m%d).tar.gz data/
```

---

## ⚠️ 风险提示

### 使用前必读

1. **先测试** - 使用testnet至少测试1周
2. **小额开始** - 初始资金不超过$500
3. **每日监控** - 检查Dashboard和日志
4. **设置止损** - 确保风控参数已配置
5. **定期备份** - 备份data目录

### 免责声明

- ❌ 不保证盈利
- ❌ 可能亏损全部本金
- ❌ 历史表现≠未来收益
- ✅ 仅供学习研究使用
- ✅ 建议不超过总资产30%用于交易

---

## 🐛 故障排查

### API连接失败
```python
from exchange import BinanceClient
client = BinanceClient()
print(client.get_mode_str())  # 检查模式
balance = client.get_balance()  # 测试连接
```

### 策略未运行
```bash
docker-compose ps              # 检查容器状态
docker-compose logs strategy   # 查看错误
```

### 订单失败
- 检查USDT余额是否充足
- 确认交易金额大于最小订单限制 ($5)
- 查看日志中的错误信息

---

## 📚 文档

- `CLAUDE.md` - 项目开发指南
- `DEPLOYMENT.md` - 详细部署文档
- `STRATEGY_GUIDE.md` - 策略详解
- `BUG_FIXES_REPORT.md` - Bug修复记录

---

## 🤝 贡献

欢迎提交Issue和PR！

---

## 📄 License

MIT License

---

**祝交易顺利！** 🚀

*最后更新: 2026-01-11*
