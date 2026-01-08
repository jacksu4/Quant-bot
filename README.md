# Quant-bot

一个简单的加密货币量化交易机器人，使用 RSI 均值回归策略在 Binance 进行自动交易。

## 策略说明

### RSI 均值回归策略是什么？

RSI（相对强弱指数）就像一个"温度计"，测量价格是"过热"还是"过冷"：

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

### 支持的交易对

- BTC/USDT
- ETH/USDT
- SOL/USDT
- XRP/USDT
- BNB/USDT

## 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/Quant-bot.git
cd Quant-bot

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

## 配置

1. 复制 `.env.example` 为 `.env`
2. 填入你的 Binance API 密钥：

```
BINANCE_API_KEY=你的API_KEY
BINANCE_API_SECRET=你的API_SECRET
TRADING_MODE=live
```

**获取 API Key**：
1. 登录 binance.com
2. 个人中心 → API管理 → 创建API
3. 启用"Enable Spot & Margin Trading"
4. 设置 IP 白名单（必须）

## 使用方法

### 启动策略

```bash
source venv/bin/activate
python run_strategy.py &
```

策略会每 5 分钟检查一次市场，发现信号自动交易。

### 停止策略

```bash
pkill -f run_strategy
```

### 查看 Dashboard

```bash
source venv/bin/activate
streamlit run dashboard.py
```

然后打开浏览器访问 http://localhost:8501

### 查看策略日志

```bash
tail -f /tmp/strategy.log
```

### 检查策略是否在运行

```bash
ps aux | grep run_strategy
```

## 常见问题

### 电脑需要一直开机吗？

**是的**。策略运行在本地电脑上：
- 电脑关机 → 策略停止
- 电脑睡眠 → 策略停止
- 关闭终端 → 策略停止

### 多久交易一次？

每 5 分钟检查一次，但只有满足条件才会交易：
- RSI < 30（超卖）→ 买入
- RSI > 70（超买）→ 卖出
- 亏损 > 3% → 止损卖出

大部分时间是"观望，不动"。

### 能保证盈利吗？

**不能**。这是一个简单的技术指标策略，不保证盈利。请用你能承受损失的资金进行测试。

## 项目结构

```
Quant-bot/
├── run_strategy.py   # 策略运行器（启动自动交易）
├── dashboard.py      # 可视化界面
├── strategy.py       # 策略逻辑
├── exchange.py       # Binance API 封装
├── data_store.py     # 数据存储
├── .env              # API 密钥配置
├── .env.example      # 配置示例
└── data/             # 策略日志和资产快照
```

## 风险提示

- 加密货币交易具有高风险
- 本策略仅供学习和测试使用
- 请勿投入超出承受能力的资金
- 过去的表现不代表未来的收益
