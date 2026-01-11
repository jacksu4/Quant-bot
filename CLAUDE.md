# CLAUDE.md - Quant-bot 项目指南

本文档为 Claude Code 提供项目上下文和开发指南。

## 项目概述

Quant-bot 是一个专业级加密货币量化交易系统，支持 Binance 交易所。

### 核心特性
- 多策略支持（RSI均值回归、Robust RSI、专业多策略）
- 完善的风险管理（止损止盈、Kelly仓位、VaR控制）
- Web Dashboard 实时监控
- Docker 容器化部署
- GitHub Actions 自动化 CI/CD

---

## 项目结构

```
Quant-bot/
├── 核心策略文件
│   ├── strategy.py              # 简单RSI均值回归策略
│   ├── robust_strategy.py       # Robust RSI策略（高夏普比率）
│   ├── professional_strategy.py # 专业多策略系统
│   ├── run_strategy.py          # RSI策略运行器
│   ├── run_robust_strategy.py   # Robust策略运行器
│
├── 交易所和数据
│   ├── exchange.py              # Binance API 封装
│   ├── data_store.py            # 数据持久化
│
├── 高级模块
│   ├── multi_factor_engine.py   # 多因子选币引擎
│   ├── risk_manager.py          # 风险管理系统
│   ├── indicators.py            # 技术指标库
│   ├── backtest_engine.py       # 回测引擎
│
├── 前端展示
│   ├── dashboard.py             # 简单Dashboard (Streamlit)
│   ├── professional_dashboard.py# 专业Dashboard
│
├── 部署配置
│   ├── docker-compose.yml       # Docker编排
│   ├── Dockerfile.strategy      # RSI策略容器
│   ├── Dockerfile.robust        # Robust策略容器
│   ├── Dockerfile.professional  # 专业策略容器
│   ├── Dockerfile.dashboard     # Dashboard容器
│   ├── deploy.sh                # 部署脚本
│   ├── supervisord.conf         # 进程管理
│
├── CI/CD (.github/workflows/)
│   ├── deploy.yml               # 自动部署到服务器
│   ├── test.yml                 # 自动测试
│
├── 配置文件
│   ├── .env                     # API密钥配置（不提交）
│   ├── .env.example             # 配置模板
│   ├── requirements.txt         # Python依赖
│
└── 数据目录
    ├── data/                    # 交易数据、日志
    └── logs/                    # 应用日志
```

---

## 策略说明

### 1. 简单RSI策略 (strategy.py)
- **适用人群**: 新手、小额资金
- **核心逻辑**: RSI < 30 买入，RSI > 70 卖出
- **风险控制**: 止损3%，止盈5%，最大持仓2个
- **运行命令**: `python run_strategy.py`

### 2. Robust RSI策略 (robust_strategy.py) ⭐推荐
- **适用人群**: 追求稳定收益的用户
- **特点**:
  - 多时间框架确认 (1H + 4H)
  - 趋势过滤 (EMA一致性)
  - 波动率调整仓位 (ATR-based)
  - 动态止损止盈
- **目标性能**: 夏普比率 > 1.5，最大回撤 < 10%
- **运行命令**: `python run_robust_strategy.py`

### 3. 专业多策略系统 (professional_strategy.py)
- **适用人群**: 机构、大额资金
- **策略组合**:
  - 多因子选币 (40%)
  - 趋势跟踪 (25%)
  - 统计套利 (15%)
  - 波动率突破 (10%)
  - 动态对冲 (10%)
- **目标性能**: 年化30-50%，夏普 > 2.0，回撤 < 15%
- **运行命令**: `python professional_strategy.py`

---

## 策略切换指南

### 本地运行切换

```bash
# 运行简单RSI策略
python run_strategy.py

# 运行Robust RSI策略（推荐）
python run_robust_strategy.py

# 运行专业多策略
python professional_strategy.py
```

### Docker部署切换

```bash
# 方式1: 使用profile启动特定策略
docker-compose --profile rsi up -d         # 简单RSI
docker-compose --profile robust up -d      # Robust RSI
docker-compose --profile professional up -d # 专业多策略
docker-compose --profile all up -d         # 全部策略

# 方式2: 直接指定服务
docker-compose up -d rsi-strategy dashboard
docker-compose up -d robust-strategy dashboard
docker-compose up -d professional-strategy dashboard

# 停止当前策略并切换
docker-compose down
docker-compose up -d robust-strategy dashboard
```

---

## 环境配置

### .env 文件配置

```bash
# API配置
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret

# 交易模式 (重要!)
TRADING_MODE=live    # live=真实交易, testnet=测试网

# 风控参数
MAX_POSITION_SIZE_USDT=15    # 单次最大交易额
STOP_LOSS_PERCENT=3.0        # 止损百分比
TAKE_PROFIT_PERCENT=5.0      # 止盈百分比
```

### 真实交易注意事项
1. 确保 `TRADING_MODE=live`
2. 使用真实Binance API密钥（非testnet）
3. API密钥需要有现货交易权限
4. 建议先小额测试

---

## Dashboard访问

### 本地运行

```bash
# 简单Dashboard
streamlit run dashboard.py
# 访问: http://localhost:8501

# 专业Dashboard
streamlit run professional_dashboard.py
# 访问: http://localhost:8502
```

### 服务器访问

部署到服务器后，通过以下地址访问：

```
简单/Robust Dashboard: http://服务器IP:8501
专业Dashboard:         http://服务器IP:8502
```

**安全建议**:
- 配置防火墙只允许特定IP访问
- 考虑使用Nginx反向代理+HTTPS
- 添加Basic Auth认证

---

## 部署流程

### 1. 本地推送触发自动部署

```bash
# 修改代码后
git add .
git commit -m "更新策略参数"
git push origin main
```

GitHub Actions 会自动：
1. SSH连接到服务器
2. 拉取最新代码
3. 运行 deploy.sh
4. 重建Docker容器
5. 执行健康检查

### 2. 手动服务器部署

```bash
# SSH登录服务器
ssh root@服务器IP

# 进入项目目录
cd /root/Quant-bot

# 拉取最新代码
git pull origin main

# 部署
bash deploy.sh
```

### 3. GitHub Secrets配置

在仓库 Settings > Secrets 中配置：
- `SERVER_HOST`: 服务器IP
- `SERVER_USER`: SSH用户名 (root)
- `SERVER_SSH_KEY`: SSH私钥
- `SERVER_PORT`: SSH端口 (22)

---

## 常用命令

### 策略管理

```bash
# 本地运行
python run_strategy.py --once          # 单次执行
python run_strategy.py --interval 60   # 60秒间隔

# Docker运行
docker-compose up -d                   # 启动所有服务
docker-compose ps                      # 查看状态
docker-compose logs -f rsi-strategy    # 查看日志
docker-compose restart rsi-strategy    # 重启策略
docker-compose down                    # 停止所有
```

### 监控和调试

```bash
# 查看容器状态
docker-compose ps
docker stats

# 查看日志
docker-compose logs --tail=100 rsi-strategy
tail -f data/strategy_log.json

# 健康检查
bash healthcheck.sh
```

### 数据备份

```bash
# 备份交易数据
tar -czf backup_$(date +%Y%m%d).tar.gz data/

# 恢复数据
tar -xzf backup_20260111.tar.gz
```

---

## 开发指南

### 代码规范
- Python 3.9+
- 使用类型注解
- 函数和类需要docstring
- 关键操作需要日志记录

### 添加新策略

1. 创建策略文件 `new_strategy.py`
2. 实现 `run_once()` 方法
3. 创建运行器 `run_new_strategy.py`
4. 创建 `Dockerfile.new`
5. 更新 `docker-compose.yml`

### 测试

```bash
# 运行所有测试
python -m pytest tests/

# 运行Bug修复测试
python test_bug_fixes.py
```

---

## 风险提示

1. **先测试**: 使用testnet至少测试1周
2. **小额开始**: 初始不超过$500
3. **监控**: 每日检查Dashboard
4. **备份**: 定期备份data目录
5. **止损**: 确保止损参数已设置

---

## 故障排查

### API连接失败
```python
from exchange import BinanceClient
client = BinanceClient()
print(client.get_mode_str())  # 确认模式
balance = client.get_balance()  # 测试连接
```

### 策略未运行
```bash
docker-compose ps                    # 检查容器状态
docker-compose logs rsi-strategy     # 查看错误日志
```

### 订单失败
- 检查余额是否充足
- 检查最小订单金额限制
- 查看exchange.py中的错误日志

---

## 版本历史

- v1.0: 简单RSI策略
- v2.0: 添加专业多策略系统
- v2.1: 添加Robust RSI策略，修复Bug
- v2.2: Docker部署，CI/CD自动化

---

*最后更新: 2026-01-11*
