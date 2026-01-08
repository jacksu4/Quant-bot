"""
RSI均值回归策略

策略逻辑（简单易懂版）:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RSI (相对强弱指数) 是衡量价格"超买"或"超卖"的指标:
- RSI < 30: 超卖 → 价格可能被低估，考虑买入
- RSI > 70: 超买 → 价格可能被高估，考虑卖出
- 30-70: 中性区间，观望

本策略的核心思想是"均值回归":
价格偏离太多后，往往会回归到正常水平。

风险控制:
- 每次交易最多用 15 USDT（约总资金的 30%）
- 止损: 亏损 3% 自动卖出
- 止盈: 盈利 5% 自动卖出部分
- 同时最多持有 2 个币种
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import json
from datetime import datetime
from typing import Optional
from exchange import BinanceClient

# 策略参数
RSI_OVERSOLD = 30      # RSI低于此值视为超卖（买入信号）
RSI_OVERBOUGHT = 70    # RSI高于此值视为超买（卖出信号）
RSI_PERIOD = 14        # RSI计算周期
TIMEFRAME = '1h'       # K线周期

# 风险控制参数（从环境变量读取，有默认值）
MAX_POSITION_USDT = float(os.getenv('MAX_POSITION_SIZE_USDT', 15))  # 单次最大交易金额
STOP_LOSS_PCT = float(os.getenv('STOP_LOSS_PERCENT', 3.0))         # 止损百分比
TAKE_PROFIT_PCT = float(os.getenv('TAKE_PROFIT_PERCENT', 5.0))     # 止盈百分比
MAX_POSITIONS = 2      # 最多同时持有几个币种

# 日志文件
LOG_FILE = 'data/strategy_log.json'


def log_action(action: str, details: dict):
    """记录策略动作到日志文件"""
    os.makedirs('data', exist_ok=True)

    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'action': action,
        'details': details,
    }

    # 读取现有日志
    logs = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                logs = json.load(f)
        except:
            logs = []

    logs.append(log_entry)

    # 只保留最近1000条日志
    logs = logs[-1000:]

    with open(LOG_FILE, 'w') as f:
        json.dump(logs, f, indent=2, default=str)

    return log_entry


def get_logs(limit: int = 100) -> list:
    """获取策略日志"""
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, 'r') as f:
            logs = json.load(f)
        return logs[-limit:]
    except:
        return []


class RSIMeanReversionStrategy:
    """RSI均值回归策略"""

    def __init__(self, client: BinanceClient = None):
        self.client = client or BinanceClient()
        self.positions = {}  # 记录持仓信息

    def analyze_market(self) -> dict:
        """
        分析市场状态

        返回:
        {
            'signals': [{'symbol': 'XRP/USDT', 'rsi': 28.5, 'signal': 'BUY'}, ...],
            'tickers': {...},
            'rsi_data': {...},
        }
        """
        tickers = self.client.get_all_tickers()
        rsi_data = self.client.get_all_rsi(TIMEFRAME)

        signals = []

        for symbol in self.client.whitelist:
            rsi = rsi_data.get(symbol, 50)
            price = tickers.get(symbol, {}).get('last', 0)

            signal = None
            if rsi < RSI_OVERSOLD:
                signal = 'BUY'
            elif rsi > RSI_OVERBOUGHT:
                signal = 'SELL'

            signals.append({
                'symbol': symbol,
                'rsi': rsi,
                'price': price,
                'signal': signal,
            })

        # 按RSI排序（最超卖的在前）
        signals.sort(key=lambda x: x['rsi'])

        return {
            'signals': signals,
            'tickers': tickers,
            'rsi_data': rsi_data,
        }

    def check_stop_loss_take_profit(self, position: dict) -> Optional[str]:
        """
        检查是否需要止损或止盈

        返回: 'STOP_LOSS', 'TAKE_PROFIT', 或 None
        """
        pnl_pct = position['pnl_percent']

        if pnl_pct <= -STOP_LOSS_PCT:
            return 'STOP_LOSS'
        elif pnl_pct >= TAKE_PROFIT_PCT:
            return 'TAKE_PROFIT'

        return None

    def should_buy(self, signal: dict) -> bool:
        """判断是否应该买入"""
        # 检查是否有买入信号
        if signal['signal'] != 'BUY':
            return False

        # 检查持仓数量限制
        positions = self.client.get_all_positions()
        if len(positions) >= MAX_POSITIONS:
            print(f"⚠️ 已达到最大持仓数 ({MAX_POSITIONS})，跳过买入")
            return False

        # 检查是否已经持有该币种
        currency = signal['symbol'].split('/')[0]
        for pos in positions:
            if pos['currency'] == currency:
                print(f"⚠️ 已持有 {currency}，跳过重复买入")
                return False

        # 检查USDT余额
        usdt_free = self.client.get_usdt_balance()
        min_order = self.client.get_min_order_usdt(signal['symbol'])

        if usdt_free < min_order:
            print(f"⚠️ USDT余额不足 ({usdt_free:.2f} < {min_order:.2f})，跳过买入")
            return False

        return True

    def execute_buy(self, symbol: str, usdt_amount: float) -> dict:
        """执行买入"""
        try:
            # 确保不超过最大仓位
            usdt_amount = min(usdt_amount, MAX_POSITION_USDT)

            # 确保满足最小订单要求
            min_order = self.client.get_min_order_usdt(symbol)
            if usdt_amount < min_order:
                print(f"⚠️ 交易金额 {usdt_amount:.2f} 小于最小要求 {min_order:.2f}")
                return None

            print(f"📈 执行买入: {symbol}, 金额: ${usdt_amount:.2f}")

            order = self.client.create_market_buy_usdt(symbol, usdt_amount)

            log_action('BUY', {
                'symbol': symbol,
                'usdt_amount': usdt_amount,
                'order_id': order.get('id'),
                'filled': order.get('filled'),
                'avg_price': order.get('average'),
            })

            print(f"✅ 买入成功! 订单ID: {order.get('id')}")
            return order

        except Exception as e:
            error_msg = str(e)
            print(f"❌ 买入失败: {error_msg}")
            log_action('BUY_FAILED', {'symbol': symbol, 'error': error_msg})
            return None

    def execute_sell(self, symbol: str, amount: float, reason: str = 'SIGNAL') -> dict:
        """执行卖出"""
        try:
            print(f"📉 执行卖出: {symbol}, 数量: {amount}, 原因: {reason}")

            order = self.client.create_market_sell(symbol, amount)

            log_action('SELL', {
                'symbol': symbol,
                'amount': amount,
                'reason': reason,
                'order_id': order.get('id'),
                'filled': order.get('filled'),
                'avg_price': order.get('average'),
            })

            print(f"✅ 卖出成功! 订单ID: {order.get('id')}")
            return order

        except Exception as e:
            error_msg = str(e)
            print(f"❌ 卖出失败: {error_msg}")
            log_action('SELL_FAILED', {'symbol': symbol, 'error': error_msg})
            return None

    def run_once(self) -> dict:
        """
        执行一次策略检查

        返回策略执行结果
        """
        print("\n" + "=" * 60)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 策略检查")
        print("=" * 60)

        result = {
            'timestamp': datetime.now().isoformat(),
            'actions': [],
            'positions': [],
            'analysis': None,
        }

        try:
            # 1. 分析市场
            analysis = self.analyze_market()
            result['analysis'] = analysis

            print("\n📊 市场分析:")
            for sig in analysis['signals']:
                status = "🟢超卖" if sig['signal'] == 'BUY' else "🔴超买" if sig['signal'] == 'SELL' else "⚪中性"
                print(f"  {sig['symbol']}: RSI={sig['rsi']:.1f} {status} @ ${sig['price']:,.2f}")

            # 2. 检查现有持仓的止损/止盈
            positions = self.client.get_all_positions()
            result['positions'] = positions
            sold_symbols = set()  # 记录已卖出的symbol，避免重复卖出

            if positions:
                print(f"\n💼 当前持仓 ({len(positions)}):")
                for pos in positions:
                    pnl_str = f"+${pos['pnl']:.2f}" if pos['pnl'] >= 0 else f"-${abs(pos['pnl']):.2f}"
                    print(f"  {pos['symbol']}: {pos['amount']:.8f} @ ${pos['current_price']:,.2f} | 盈亏: {pnl_str} ({pos['pnl_percent']:+.2f}%)")

                    # 检查止损/止盈
                    action = self.check_stop_loss_take_profit(pos)
                    if action == 'STOP_LOSS':
                        print(f"  ⚠️ 触发止损! 亏损 {abs(pos['pnl_percent']):.2f}%")
                        order = self.execute_sell(pos['symbol'], pos['amount'], 'STOP_LOSS')
                        if order:
                            result['actions'].append({'type': 'STOP_LOSS', 'symbol': pos['symbol']})
                            sold_symbols.add(pos['symbol'])
                    elif action == 'TAKE_PROFIT':
                        print(f"  🎯 触发止盈! 盈利 {pos['pnl_percent']:.2f}%")
                        order = self.execute_sell(pos['symbol'], pos['amount'], 'TAKE_PROFIT')
                        if order:
                            result['actions'].append({'type': 'TAKE_PROFIT', 'symbol': pos['symbol']})
                            sold_symbols.add(pos['symbol'])

            # 3. 检查RSI信号的卖出（非止损/止盈，跳过已卖出的）
            for pos in positions:
                if pos['symbol'] in sold_symbols:
                    continue  # 跳过已在步骤2中卖出的持仓
                rsi = analysis['rsi_data'].get(pos['symbol'], 50)
                if rsi > RSI_OVERBOUGHT:
                    print(f"  📉 {pos['symbol']} RSI={rsi:.1f} 超买，执行卖出")
                    order = self.execute_sell(pos['symbol'], pos['amount'], 'RSI_OVERBOUGHT')
                    if order:
                        result['actions'].append({'type': 'RSI_SELL', 'symbol': pos['symbol']})

            # 4. 检查买入信号
            for sig in analysis['signals']:
                if self.should_buy(sig):
                    # 计算买入金额
                    usdt_free = self.client.get_usdt_balance()
                    buy_amount = min(MAX_POSITION_USDT, usdt_free * 0.9)  # 保留10%缓冲

                    if buy_amount >= 5:  # 最小交易额
                        order = self.execute_buy(sig['symbol'], buy_amount)
                        if order:
                            result['actions'].append({'type': 'RSI_BUY', 'symbol': sig['symbol']})
                            break  # 一次只买入一个

            # 5. 记录状态
            if not result['actions']:
                print("\n⏳ 无交易动作，继续观望")
                log_action('HOLD', {
                    'reason': 'No trading signals',
                    'rsi_summary': {s['symbol']: s['rsi'] for s in analysis['signals']},
                })

            # 显示账户状态
            balance = self.client.get_balance()
            total = self.client.calculate_total_value_usdt(balance, analysis['tickers'])
            usdt = self.client.get_usdt_balance()

            print(f"\n💰 账户状态: 总资产 ${total:.2f} | USDT可用 ${usdt:.2f}")

        except Exception as e:
            print(f"❌ 策略执行错误: {e}")
            log_action('ERROR', {'error': str(e)})
            result['error'] = str(e)

        print("=" * 60)
        return result


def get_strategy_status() -> dict:
    """获取策略状态（给Dashboard用）"""
    client = BinanceClient()
    strategy = RSIMeanReversionStrategy(client)

    analysis = strategy.analyze_market()
    positions = client.get_all_positions()
    balance = client.get_balance()
    total_value = client.calculate_total_value_usdt(balance, analysis['tickers'])
    logs = get_logs(20)

    return {
        'mode': client.get_mode_str(),
        'is_live': client.is_live,
        'total_value': total_value,
        'usdt_free': client.get_usdt_balance(),
        'positions': positions,
        'signals': analysis['signals'],
        'rsi_data': analysis['rsi_data'],
        'tickers': analysis['tickers'],
        'recent_logs': logs,
        'config': {
            'rsi_oversold': RSI_OVERSOLD,
            'rsi_overbought': RSI_OVERBOUGHT,
            'max_position_usdt': MAX_POSITION_USDT,
            'stop_loss_pct': STOP_LOSS_PCT,
            'take_profit_pct': TAKE_PROFIT_PCT,
            'max_positions': MAX_POSITIONS,
        }
    }
