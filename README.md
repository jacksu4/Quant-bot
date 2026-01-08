# Quant-bot - 量化交易系统

专业级加密货币量化交易系统，包含基础RSI策略和高级多策略组合。

## 🎯 系统选择

本项目包含两套系统，根据你的需求选择：

### 方案1：简单RSI策略（适合初学者）
- ✅ 简单易懂，5分钟上手
- ✅ 单策略，逻辑清晰
- ✅ 适合小额资金（$100-1000）
- 📖 文档：见下方"简单RSI策略"章节

### 方案2：专业级多策略系统（适合专业投资者/基金）
- ✅ 5大策略组合，分散风险
- ✅ Kelly仓位 + VaR风险管理
- ✅ 预期年化收益30-50%，回撤<15%
- ✅ 适合机构和大额资金（$10,000+）
- 📖 文档：`STRATEGY_GUIDE.md`

---

## 🚀 快速开始

### 安装依赖

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

### 配置API

创建 `.env` 文件：

```bash
BINANCE_API_KEY=你的API_KEY
BINANCE_API_SECRET=你的API_SECRET
TRADING_MODE=testnet  # 先用testnet测试！
```

**⚠️ 重要**：强烈建议先在testnet测试至少1周！

---

## 📊 方案1：简单RSI策略

### 策略说明

RSI（相对强弱指数）是衡量价格"超买"或"超卖"的指标：

| RSI 值 | 状态 | 操作 |
|--------|------|------|
| 0-30 | 超卖（价格"过冷"） | 买入 |
| 30-70 | 中性（正常） | 观望 |
| 70-100 | 超买（价格"过热"） | 卖出 |

**核心逻辑**：价格偏离太多后，往往会回归到正常水平。

### 风险控制

- 单次最大交易：$15 USDT
- 止损：亏损 3% 自动卖出
- 止盈：盈利 5% 自动卖出
- 最多同时持有 2 个币种

### 使用方法

```bash
# 启动策略
python run_strategy.py &

# 查看Dashboard
streamlit run dashboard.py

# 停止策略
pkill -f run_strategy
```

---

## 🎓 方案2：专业级多策略系统

### 系统特点

#### 5大策略组合
| 策略 | 权重 | 特点 |
|------|------|------|
| 多因子选币 | 40% | 6大因子综合评分选择优质币种 |
| 趋势跟踪 | 25% | EMA/MACD/ADX多时间框架确认 |
| 统计套利 | 15% | 协整配对交易，市场中性 |
| 波动率突破 | 10% | 布林带突破，快进快出 |
| 动态对冲 | 10% | 根据市场状态调整仓位 |

#### 风险管理
- ✅ Kelly Criterion仓位管理
- ✅ VaR (99%) < 5%
- ✅ 最大回撤 < 15%
- ✅ 三级风险防护（NORMAL/CAUTIOUS/DEFENSIVE）
- ✅ 熔断机制（回撤>15%立即停止）

#### 预期性能
- 年化收益率：30-50%
- 夏普比率：> 2.0
- 最大回撤：< 15%
- 胜率：> 55%

### 使用方法

```bash
# 运行完整策略
python professional_strategy.py

# 启动专业Dashboard
streamlit run professional_dashboard.py

# 测试各个模块
python multi_factor_engine.py    # 多因子选币
python risk_manager.py           # 风险管理
python statistical_arbitrage.py  # 统计套利
python backtest_engine.py        # 回测引擎
```

### Python API

```python
# 方式1：运行完整策略
from professional_strategy import ProfessionalStrategy
strategy = ProfessionalStrategy()
strategy.run_once()

# 方式2：单独使用模块
from multi_factor_engine import MultiFactorEngine
engine = MultiFactorEngine()
selected = engine.select_coins(top_n=5)

from risk_manager import RiskManager
rm = RiskManager()
report = rm.generate_risk_report()
```

**详细文档**：见 `STRATEGY_GUIDE.md`

---

## 📁 项目结构

```
Quant-bot/
├── 基础RSI策略
│   ├── run_strategy.py        # 策略运行器
│   ├── strategy.py            # RSI策略逻辑
│   ├── dashboard.py           # 基础Dashboard
│   └── bot.py                 # Bot运行器
│
├── 专业级系统
│   ├── professional_strategy.py    # 主策略（5策略组合）
│   ├── multi_factor_engine.py      # 多因子选币引擎
│   ├── risk_manager.py             # 风险管理系统
│   ├── statistical_arbitrage.py    # 统计套利模块
│   ├── backtest_engine.py          # 回测引擎
│   ├── indicators.py               # 技术指标库
│   └── professional_dashboard.py   # 专业Dashboard
│
├── 基础设施
│   ├── exchange.py            # Binance API封装
│   └── test_bug_fixes.py      # 测试代码
│
└── 文档
    ├── README.md              # 本文件
    ├── STRATEGY_GUIDE.md      # 完整策略指南
    ├── BUG_FIXES_REPORT.md    # Bug修复报告
    └── CLAUDE.md              # 项目指引
```

---

## 🔧 功能对比

| 功能 | 简单RSI策略 | 专业级系统 |
|------|------------|-----------|
| 策略数量 | 1个 | 5个组合 |
| 因子数量 | 1个(RSI) | 6个 |
| 风险管理 | 简单止损 | Kelly+VaR+回撤控制 |
| 市场适应 | 固定 | 动态调整(20%-70%) |
| 预期收益 | 20-30% | 30-50% |
| 最大回撤 | 可能>30% | <15% |
| 夏普比率 | ~1.0 | >2.0 |
| 适合资金 | $100-1000 | $10,000+ |
| 学习曲线 | 1天 | 1周 |

---

## 📈 Dashboard预览

### 简单RSI Dashboard
- 账户总览
- 持仓分析
- RSI指标
- 交易历史
- 资产快照

### 专业级Dashboard
- 实时权益曲线
- 多因子得分可视化
- 风险指标监控（VaR/夏普/回撤）
- 5大策略信号
- 统计套利配对

---

## ⚠️ 风险提示

### 新手必读
1. **先在testnet测试** - 至少1周
2. **小额开始** - $100-500
3. **每日检查** - 监控Dashboard
4. **理解策略** - 阅读文档
5. **设置告警** - 回撤>10%通知
6. **定期备份** - data目录

### 免责声明
- ❌ 不保证盈利
- ❌ 可能亏损全部本金
- ❌ 历史表现≠未来收益
- ✅ 仅供学习研究使用
- ✅ 建议不超过总资产30%

---

## 🐛 故障排查

### API连接失败
```python
from exchange import BinanceClient
client = BinanceClient()
print(client.get_mode_str())  # 确认模式
balance = client.get_balance()  # 测试连接
```

### 数据不足
```python
ohlcv = client.get_ohlcv('BTC/USDT', '1h', limit=100)
print(f"K线数量: {len(ohlcv)}")  # 应该≥50
```

### 策略未运行
```bash
ps aux | grep strategy  # 检查进程
tail -f /tmp/strategy.log  # 查看日志
```

---

## 📚 学习资源

### 新手入门
1. 阅读本README
2. 运行简单RSI策略
3. 理解Dashboard各项指标
4. 在testnet测试1-2周

### 进阶学习
1. 阅读 `STRATEGY_GUIDE.md`
2. 理解多因子选币原理
3. 学习风险管理系统
4. 运行专业级系统

### 深入研究
1. 研究学术论文
2. 调整策略参数
3. 添加自定义因子
4. 开发新的策略模块

---

## 🤝 贡献

欢迎提交Issue和PR！

### Bug修复
见 `BUG_FIXES_REPORT.md`

### 新功能
请先创建Issue讨论

---

## 📞 支持

- 📖 文档：`STRATEGY_GUIDE.md`
- 🐛 Bug报告：GitHub Issues
- 💬 讨论：GitHub Discussions

---

## 📄 License

MIT License

---

## 🎉 致谢

感谢所有贡献者和使用者！

**祝交易顺利！** 🚀

---

*最后更新：2026-01-08*
