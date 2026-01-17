# Quant-bot - Cryptocurrency Quantitative Trading System

Professional-grade cryptocurrency quantitative trading system with multi-strategy support, automated deployment, and real-time monitoring.

专业级加密货币量化交易系统，支持多策略、自动化部署和实时监控。

---

## 🎯 Strategy Selection / 策略选择

This project includes **4 strategies** - choose based on your risk tolerance and goals:

本项目包含**4套策略**，根据你的风险承受能力和目标选择：

| Strategy 策略 | Target User 适用人群 | Risk Level 风险等级 | Target Return 目标收益 | Max Drawdown 最大回撤 |
|--------------|---------------------|---------------------|----------------------|---------------------|
| **Aggressive Momentum** ⚡NEW | Risk-seekers 追求高收益 | HIGH 高 | 100% in 2 months | <15% |
| **Simple RSI** | Beginners 新手 | MEDIUM 中 | Stable 稳定 | May exceed 30% |
| **Robust RSI** ⭐Recommended | Conservative 追求稳定 | LOW 低 | Sharpe >1.5 | <10% |
| **Professional Multi-Strategy** | Institutional 机构 | LOW-MED 中低 | 30-50% annual | <15% |

### Strategy Comparison / 策略对比

```
Risk Level / 风险等级:
LOW ──────────────────────────────────────────────────── HIGH
│                                                          │
Robust RSI ──── Professional ──── Simple RSI ──── Aggressive Momentum
(稳定优先)       (机构级)        (简单入门)       (高收益追求)
```

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

### 3. Run Strategy / 运行策略

```bash
# Option 1: Aggressive Momentum (high risk, high reward)
# 选项1: 激进动量策略（高风险高回报）
python run_aggressive_strategy.py

# Option 2: Robust RSI (recommended for most users)
# 选项2: Robust RSI策略（推荐大多数用户使用）
python run_robust_strategy.py

# Option 3: Docker deployment
# 选项3: Docker部署
docker-compose --profile aggressive up -d  # Aggressive Momentum
docker-compose --profile robust up -d      # Robust RSI
```

### 4. 查看Dashboard

```bash
# 本地运行
streamlit run dashboard.py

# 访问地址
http://localhost:8501
```

---

## 📊 Strategy Details / 策略详解

### Strategy 0: Aggressive Momentum ⚡ (NEW)
### 策略0: 激进动量策略 ⚡（新）

**How it works (in plain English):**
This strategy "rides the wave" - it finds coins that are going up strongly and buys them, then sells when the momentum slows down. Think of it like surfing: you catch the strongest waves and ride them until they start to break.

**核心逻辑（通俗解释）：**
这个策略"追涨强势币"——找到正在强势上涨的币种并买入，当动量减弱时卖出。就像冲浪一样：抓住最强的浪，一直骑到浪开始消退。

**Key Features / 主要特点:**
- Multi-factor scoring: Momentum + RSI + MACD + Trend + Volume
- Aggressive position sizing: Up to 50% per position on strong signals
- Smart rotation: Replace weak positions with stronger candidates every 4 hours
- Trailing stop: Lock in profits while letting winners run

**多因子评分**：动量 + RSI + MACD + 趋势 + 成交量
**激进仓位**：强信号时单仓最高50%
**智能轮动**：每4小时用更强的币替换弱势持仓
**跟踪止盈**：在保护利润的同时让盈利继续增长

**Risk Controls / 风控:**
| Parameter 参数 | Value 值 | Description 说明 |
|--------------|---------|-----------------|
| Hard Stop Loss | 3% | Exit immediately if loss exceeds 3% |
| Trailing Stop | 2% | Sell if price drops 2% from high |
| Max Single Position | 50% | Never put more than 50% in one coin |
| Max Total Exposure | 80% | Keep at least 20% in USDT |
| Daily Loss Limit | 5% | Stop trading if daily loss exceeds 5% |
| Max Drawdown | 15% | Stop trading if total drawdown exceeds 15% |

```bash
python run_aggressive_strategy.py
```

---

### Strategy 1: Simple RSI Mean Reversion
### 策略1: 简单RSI均值回归

**How it works (in plain English):**
RSI (Relative Strength Index) measures if a coin is "oversold" (too cheap) or "overbought" (too expensive). This strategy buys when RSI is below 30 (everyone is selling, price is likely too low) and sells when RSI is above 70 (everyone is buying, price is likely too high).

**核心逻辑（通俗解释）：**
RSI（相对强弱指数）衡量币种是否"超卖"（太便宜）或"超买"（太贵）。当RSI低于30时买入（大家都在卖，价格可能太低了），当RSI高于70时卖出（大家都在买，价格可能太高了）。

**Parameters / 参数:**
- RSI < 30 (oversold/超卖) → BUY 买入
- RSI > 70 (overbought/超买) → SELL 卖出
- Stop Loss 止损: -3%
- Take Profit 止盈: +5%

```bash
python run_strategy.py
```

---

### Strategy 2: Robust RSI ⭐Recommended
### 策略2: Robust RSI策略 ⭐推荐

**How it works (in plain English):**
This is an improved version of the Simple RSI strategy. It uses TWO timeframes (1-hour and 4-hour) to confirm signals - like getting a second opinion before making a decision. It also adjusts position size based on volatility (smaller positions when markets are crazy, larger when calm).

**核心逻辑（通俗解释）：**
这是简单RSI策略的改进版。它使用两个时间框架（1小时和4小时）来确认信号——就像做决定前再征求一次意见。它还根据波动率调整仓位大小（市场疯狂时仓位小，平静时仓位大）。

**Key Features / 特点:**
- Multi-timeframe confirmation (1H + 4H) / 多时间框架确认
- EMA trend filter (don't buy in downtrends) / EMA趋势过滤（下跌趋势不买）
- ATR-based position sizing / ATR波动率调整仓位
- Dynamic stop-loss/take-profit / 动态止损止盈

**Target Performance / 目标性能:**
- Sharpe Ratio > 1.5 / 夏普比率 > 1.5
- Max Drawdown < 10% / 最大回撤 < 10%
- Win Rate > 55% / 胜率 > 55%

```bash
python run_robust_strategy.py
```

---

### Strategy 3: Professional Multi-Strategy System
### 策略3: 专业多策略系统

**How it works (in plain English):**
This is a "hedge fund style" approach that combines 5 different strategies. By diversifying across multiple strategies, it reduces risk - when one strategy loses, another might win. It's like having multiple fishing rods in the water instead of just one.

**核心逻辑（通俗解释）：**
这是一种"对冲基金风格"的方法，结合了5种不同的策略。通过多策略分散，降低风险——当一个策略亏损时，另一个可能盈利。就像在水里放多根鱼竿而不是只放一根。

**Strategy Composition / 5大策略组合:**
| Strategy 策略 | Weight 权重 | Description 说明 |
|--------------|------------|-----------------|
| Multi-Factor Selection 多因子选币 | 40% | 6-factor composite scoring / 6因子综合评分 |
| Trend Following 趋势跟踪 | 25% | EMA/MACD/ADX indicators / EMA/MACD/ADX指标 |
| Statistical Arbitrage 统计套利 | 15% | Pair trading / 配对交易 |
| Volatility Breakout 波动率突破 | 10% | Bollinger Band breakout / 布林带突破 |
| Dynamic Hedging 动态对冲 | 10% | Market state adjustment / 市场状态调整 |

```bash
python professional_strategy.py
```

---

## 🔄 Strategy Switching / 策略切换

### Local Execution / 本地运行切换

```bash
# Aggressive Momentum (high risk, high reward)
# 激进动量（高风险高回报）
python run_aggressive_strategy.py

# Simple RSI (beginner-friendly)
# 简单RSI（适合新手）
python run_strategy.py

# Robust RSI (recommended for most users)
# Robust RSI（推荐大多数用户）
python run_robust_strategy.py

# Professional Multi-Strategy (institutional)
# 专业多策略（机构级）
python professional_strategy.py
```

### Docker Switching / Docker切换

```bash
# Stop current strategy / 停止当前策略
docker-compose down

# Start specific strategy / 启动指定策略
docker-compose up -d aggressive-strategy dashboard   # Aggressive Momentum
docker-compose up -d rsi-strategy dashboard          # Simple RSI
docker-compose up -d robust-strategy dashboard       # Robust RSI
docker-compose up -d professional-strategy dashboard # Professional

# Or use profile / 或使用profile
docker-compose --profile aggressive up -d
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

*Last Updated / 最后更新: 2026-01-13*
