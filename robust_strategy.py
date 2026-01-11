"""
Robust RSI均值回归策略 - 高夏普比率版本

策略特点：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 多时间框架确认 (1H + 4H)
2. 趋势过滤 (EMA趋势一致性)
3. 波动率调整仓位 (ATR-based sizing)
4. 严格的最小订单检查
5. 动态止损止盈 (基于ATR)
6. 渐进式建仓/减仓

目标性能:
- 年化收益: 25-40%
- 夏普比率: > 1.5
- 最大回撤: < 10%
- 胜率: > 55%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import json
import numpy as np
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from exchange import BinanceClient

# 策略参数
RSI_OVERSOLD = 35          # RSI超卖阈值 (比30更保守)
RSI_OVERBOUGHT = 65        # RSI超买阈值 (比70更保守)
RSI_STRONG_OVERSOLD = 25   # 强超卖 (加大仓位)
RSI_STRONG_OVERBOUGHT = 75 # 强超买 (立即卖出)
RSI_PERIOD = 14
EMA_FAST = 12
EMA_SLOW = 26

# 风险控制
MAX_POSITION_USDT = float(os.getenv('MAX_POSITION_SIZE_USDT', 15))
BASE_STOP_LOSS_PCT = float(os.getenv('STOP_LOSS_PERCENT', 3.0))
BASE_TAKE_PROFIT_PCT = float(os.getenv('TAKE_PROFIT_PERCENT', 5.0))
MAX_POSITIONS = 2
MIN_TRADE_USDT = 6.0  # Binance最小订单约5 USDT，留余量

# ATR倍数用于动态止损止盈
ATR_STOP_MULTIPLIER = 2.0
ATR_PROFIT_MULTIPLIER = 3.0

# 日志文件
LOG_FILE = 'data/robust_strategy_log.json'


def calculate_ema(prices: List[float], period: int) -> List[float]:
    """计算EMA"""
    if len(prices) < period:
        return [prices[-1]] * len(prices) if prices else []

    ema = [sum(prices[:period]) / period]
    multiplier = 2 / (period + 1)

    for price in prices[period:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])

    # 填充前面的值
    return [ema[0]] * (len(prices) - len(ema)) + ema


def calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
    """计算ATR (Average True Range)"""
    if len(closes) < period + 1:
        return 0.0

    true_ranges = []
    for i in range(1, len(closes)):
        high_low = highs[i] - lows[i]
        high_close = abs(highs[i] - closes[i-1])
        low_close = abs(lows[i] - closes[i-1])
        true_ranges.append(max(high_low, high_close, low_close))

    if len(true_ranges) < period:
        return np.mean(true_ranges) if true_ranges else 0.0

    return np.mean(true_ranges[-period:])


def log_action(action: str, details: dict):
    """记录策略动作"""
    os.makedirs('data', exist_ok=True)

    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'action': action,
        'details': details,
    }

    logs = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                logs = json.load(f)
        except:
            logs = []

    logs.append(log_entry)
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


class RobustRSIStrategy:
    """Robust RSI均值回归策略"""

    def __init__(self, client: BinanceClient = None):
        self.client = client or BinanceClient()
        self.position_entry_prices = {}  # 记录入场价格

    def get_market_data(self, symbol: str) -> Optional[Dict]:
        """获取市场数据 (多时间框架)"""
        try:
            # 1小时数据
            ohlcv_1h = self.client.get_ohlcv(symbol, '1h', limit=100)
            if len(ohlcv_1h) < 50:
                return None

            # 4小时数据
            ohlcv_4h = self.client.get_ohlcv(symbol, '4h', limit=50)
            if len(ohlcv_4h) < 30:
                return None

            # 提取数据
            closes_1h = [c[4] for c in ohlcv_1h]
            highs_1h = [c[2] for c in ohlcv_1h]
            lows_1h = [c[3] for c in ohlcv_1h]

            closes_4h = [c[4] for c in ohlcv_4h]

            # 计算指标
            rsi_1h = self.client.calculate_rsi(symbol, RSI_PERIOD, '1h')
            rsi_4h = self.client.calculate_rsi(symbol, RSI_PERIOD, '4h')

            ema_fast_1h = calculate_ema(closes_1h, EMA_FAST)
            ema_slow_1h = calculate_ema(closes_1h, EMA_SLOW)

            ema_fast_4h = calculate_ema(closes_4h, EMA_FAST)
            ema_slow_4h = calculate_ema(closes_4h, EMA_SLOW)

            atr = calculate_atr(highs_1h, lows_1h, closes_1h, 14)
            current_price = closes_1h[-1]

            # 计算ATR百分比
            atr_pct = (atr / current_price * 100) if current_price > 0 else 0

            return {
                'symbol': symbol,
                'price': current_price,
                'rsi_1h': rsi_1h,
                'rsi_4h': rsi_4h,
                'ema_fast_1h': ema_fast_1h[-1],
                'ema_slow_1h': ema_slow_1h[-1],
                'ema_fast_4h': ema_fast_4h[-1],
                'ema_slow_4h': ema_slow_4h[-1],
                'atr': atr,
                'atr_pct': atr_pct,
                'trend_1h': 'UP' if ema_fast_1h[-1] > ema_slow_1h[-1] else 'DOWN',
                'trend_4h': 'UP' if ema_fast_4h[-1] > ema_slow_4h[-1] else 'DOWN',
            }

        except Exception as e:
            print(f"  ⚠️ 获取 {symbol} 数据失败: {e}")
            return None

    def calculate_position_size(self, data: Dict, available_usdt: float) -> float:
        """计算仓位大小 (基于波动率调整)"""
        # 基础仓位
        base_size = min(MAX_POSITION_USDT, available_usdt * 0.8)

        # 波动率调整 (ATR越高，仓位越小)
        if data['atr_pct'] > 3.0:
            # 高波动，减少仓位
            volatility_multiplier = 0.5
        elif data['atr_pct'] > 2.0:
            volatility_multiplier = 0.7
        elif data['atr_pct'] < 1.0:
            # 低波动，可以稍大仓位
            volatility_multiplier = 1.0
        else:
            volatility_multiplier = 0.85

        # RSI强度调整
        rsi = data['rsi_1h']
        if rsi < RSI_STRONG_OVERSOLD:
            rsi_multiplier = 1.2  # 强超卖，加大仓位
        elif rsi < RSI_OVERSOLD:
            rsi_multiplier = 1.0
        else:
            rsi_multiplier = 0.8

        adjusted_size = base_size * volatility_multiplier * rsi_multiplier

        # 确保不低于最小交易额
        return max(MIN_TRADE_USDT, min(adjusted_size, MAX_POSITION_USDT))

    def get_dynamic_stops(self, data: Dict, entry_price: float) -> Tuple[float, float]:
        """计算动态止损止盈 (基于ATR)"""
        atr = data['atr']

        # 基于ATR的止损止盈
        atr_stop = atr * ATR_STOP_MULTIPLIER
        atr_profit = atr * ATR_PROFIT_MULTIPLIER

        # 转换为百分比
        stop_pct = (atr_stop / entry_price * 100) if entry_price > 0 else BASE_STOP_LOSS_PCT
        profit_pct = (atr_profit / entry_price * 100) if entry_price > 0 else BASE_TAKE_PROFIT_PCT

        # 限制范围
        stop_pct = max(1.5, min(stop_pct, 5.0))  # 1.5% - 5%
        profit_pct = max(2.0, min(profit_pct, 8.0))  # 2% - 8%

        return stop_pct, profit_pct

    def should_buy(self, data: Dict) -> Tuple[bool, str]:
        """判断是否买入"""
        reasons = []

        # 条件1: RSI超卖
        if data['rsi_1h'] >= RSI_OVERSOLD:
            return False, "RSI未超卖"

        # 条件2: 4H RSI不能太高 (避免在下跌趋势中抄底)
        if data['rsi_4h'] > 60:
            return False, "4H RSI过高，可能是下跌趋势"

        # 条件3: 趋势一致性 (至少一个时间框架是上升趋势)
        if data['trend_1h'] == 'DOWN' and data['trend_4h'] == 'DOWN':
            # 除非RSI极度超卖
            if data['rsi_1h'] > RSI_STRONG_OVERSOLD:
                return False, "双时间框架下跌趋势"

        # 条件4: 波动率不能太高
        if data['atr_pct'] > 5.0:
            return False, "波动率过高，风险太大"

        reasons.append(f"RSI_1H={data['rsi_1h']:.1f}")
        reasons.append(f"RSI_4H={data['rsi_4h']:.1f}")
        reasons.append(f"ATR={data['atr_pct']:.2f}%")

        return True, ", ".join(reasons)

    def should_sell(self, data: Dict, position: Dict) -> Tuple[bool, str]:
        """判断是否卖出"""
        pnl_pct = position['pnl_percent']
        entry_price = position.get('avg_price', data['price'])

        # 获取动态止损止盈
        stop_pct, profit_pct = self.get_dynamic_stops(data, entry_price)

        # 1. 止损检查
        if pnl_pct <= -stop_pct:
            return True, f"STOP_LOSS (亏损 {abs(pnl_pct):.2f}% > {stop_pct:.2f}%)"

        # 2. 止盈检查
        if pnl_pct >= profit_pct:
            return True, f"TAKE_PROFIT (盈利 {pnl_pct:.2f}% > {profit_pct:.2f}%)"

        # 3. RSI超买卖出
        if data['rsi_1h'] >= RSI_STRONG_OVERBOUGHT:
            return True, f"RSI_OVERBOUGHT (RSI={data['rsi_1h']:.1f} > {RSI_STRONG_OVERBOUGHT})"

        # 4. RSI回归中性 + 盈利时卖出
        if data['rsi_1h'] >= RSI_OVERBOUGHT and pnl_pct > 0:
            return True, f"RSI_NEUTRAL_EXIT (RSI={data['rsi_1h']:.1f}, 盈利={pnl_pct:.2f}%)"

        return False, ""

    def execute_buy(self, symbol: str, usdt_amount: float) -> Optional[Dict]:
        """执行买入"""
        # 检查最小订单
        min_order_usdt = self.client.get_min_order_usdt(symbol)
        if usdt_amount < min_order_usdt:
            print(f"  ⚠️ 金额 ${usdt_amount:.2f} < 最小订单 ${min_order_usdt:.2f}")
            return None

        try:
            print(f"  📈 买入 {symbol}, 金额: ${usdt_amount:.2f}")
            order = self.client.create_market_buy_usdt(symbol, usdt_amount)

            log_action('BUY', {
                'symbol': symbol,
                'usdt_amount': usdt_amount,
                'order_id': order.get('id'),
                'filled': order.get('filled'),
                'avg_price': order.get('average'),
            })

            print(f"  ✅ 买入成功! 订单ID: {order.get('id')}")
            return order

        except Exception as e:
            print(f"  ❌ 买入失败: {e}")
            log_action('BUY_FAILED', {'symbol': symbol, 'error': str(e)})
            return None

    def execute_sell(self, symbol: str, amount: float, reason: str) -> Optional[Dict]:
        """执行卖出"""
        # 检查最小订单数量
        min_amount = self.client.get_min_order_amount(symbol)

        if amount < min_amount:
            print(f"  ⚠️ 数量 {amount:.8f} < 最小订单 {min_amount:.8f} (粉尘持仓)")
            log_action('DUST_POSITION', {
                'symbol': symbol,
                'amount': amount,
                'min_required': min_amount,
                'reason': reason,
            })
            return {'dust': True, 'symbol': symbol, 'amount': amount}

        try:
            print(f"  📉 卖出 {symbol}, 数量: {amount:.8f}, 原因: {reason}")
            order = self.client.create_market_sell(symbol, amount)

            log_action('SELL', {
                'symbol': symbol,
                'amount': amount,
                'order_id': order.get('id'),
                'filled': order.get('filled'),
                'avg_price': order.get('average'),
                'reason': reason,
            })

            print(f"  ✅ 卖出成功! 订单ID: {order.get('id')}")
            return order

        except Exception as e:
            print(f"  ❌ 卖出失败: {e}")
            log_action('SELL_FAILED', {'symbol': symbol, 'error': str(e)})
            return None

    def run_once(self) -> Dict:
        """执行一次策略"""
        print("\n" + "=" * 70)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Robust RSI策略检查")
        print(f"模式: {self.client.get_mode_str()}")
        print("=" * 70)

        result = {
            'timestamp': datetime.now().isoformat(),
            'actions': [],
            'analysis': [],
        }

        # 1. 获取所有币种的市场数据
        print("\n📊 市场分析:")
        market_data = {}
        for symbol in self.client.whitelist:
            data = self.get_market_data(symbol)
            if data:
                market_data[symbol] = data
                trend = f"{data['trend_1h']}/{data['trend_4h']}"
                print(f"  {symbol}: RSI_1H={data['rsi_1h']:.1f}, RSI_4H={data['rsi_4h']:.1f}, "
                      f"趋势={trend}, ATR={data['atr_pct']:.2f}%")
                result['analysis'].append(data)

        # 2. 检查现有持仓
        positions = self.client.get_all_positions()
        sold_symbols = set()

        if positions:
            print(f"\n💼 检查持仓 ({len(positions)}):")
            for pos in positions:
                symbol = pos['symbol']
                print(f"  {symbol}: {pos['amount']:.8f} @ ${pos['current_price']:,.2f} "
                      f"| 盈亏: {pos['pnl_percent']:+.2f}%")

                if symbol in market_data:
                    should_sell, reason = self.should_sell(market_data[symbol], pos)
                    if should_sell:
                        order = self.execute_sell(symbol, pos['amount'], reason)
                        if order and not order.get('dust'):
                            result['actions'].append({'type': 'SELL', 'symbol': symbol, 'reason': reason})
                            sold_symbols.add(symbol)

        # 3. 检查买入机会
        print("\n🔍 检查买入机会:")
        usdt_free = self.client.get_usdt_balance()
        current_positions = len([p for p in positions if p['symbol'] not in sold_symbols])

        if current_positions >= MAX_POSITIONS:
            print(f"  ⚠️ 已达到最大持仓数 ({MAX_POSITIONS})")
        elif usdt_free < MIN_TRADE_USDT:
            print(f"  ⚠️ USDT余额不足 (${usdt_free:.2f} < ${MIN_TRADE_USDT:.2f})")
        else:
            # 按RSI排序，最超卖的优先
            buy_candidates = []
            for symbol, data in market_data.items():
                # 跳过已持有的
                held_currencies = [p['currency'] for p in positions if p['symbol'] not in sold_symbols]
                if data['symbol'].split('/')[0] in held_currencies:
                    continue

                should_buy, reason = self.should_buy(data)
                if should_buy:
                    buy_candidates.append((symbol, data, reason))

            buy_candidates.sort(key=lambda x: x[1]['rsi_1h'])

            if buy_candidates:
                symbol, data, reason = buy_candidates[0]
                position_size = self.calculate_position_size(data, usdt_free)
                print(f"  📈 买入候选: {symbol} ({reason})")
                print(f"     建议仓位: ${position_size:.2f}")

                order = self.execute_buy(symbol, position_size)
                if order:
                    result['actions'].append({'type': 'BUY', 'symbol': symbol, 'reason': reason})
            else:
                print("  无符合条件的买入信号")

        # 4. 总结
        if not result['actions']:
            log_action('HOLD', {'reason': 'No trading signals'})

        # 显示账户状态
        balance = self.client.get_balance()
        tickers = self.client.get_all_tickers()
        total = self.client.calculate_total_value_usdt(balance, tickers)

        print(f"\n💰 账户状态: 总资产 ${total:.2f} | USDT可用 ${usdt_free:.2f}")
        print("=" * 70)

        return result


def get_strategy_status() -> Dict:
    """获取策略状态（给Dashboard用）"""
    client = BinanceClient()
    strategy = RobustRSIStrategy(client)

    # 获取市场数据
    analysis = []
    signals = []
    for symbol in client.whitelist:
        data = strategy.get_market_data(symbol)
        if data:
            analysis.append(data)
            signal = None
            if data['rsi_1h'] < RSI_OVERSOLD:
                signal = 'BUY'
            elif data['rsi_1h'] > RSI_OVERBOUGHT:
                signal = 'SELL'
            signals.append({
                'symbol': symbol,
                'rsi': data['rsi_1h'],
                'price': data['price'],
                'signal': signal,
            })

    positions = client.get_all_positions()
    balance = client.get_balance()
    tickers = client.get_all_tickers()
    total_value = client.calculate_total_value_usdt(balance, tickers)
    logs = get_logs(20)

    return {
        'mode': client.get_mode_str(),
        'is_live': client.is_live,
        'total_value': total_value,
        'usdt_free': client.get_usdt_balance(),
        'positions': positions,
        'signals': signals,
        'rsi_data': {d['symbol']: d['rsi_1h'] for d in analysis},
        'tickers': tickers,
        'recent_logs': logs,
        'config': {
            'rsi_oversold': RSI_OVERSOLD,
            'rsi_overbought': RSI_OVERBOUGHT,
            'max_position_usdt': MAX_POSITION_USDT,
            'stop_loss_pct': BASE_STOP_LOSS_PCT,
            'take_profit_pct': BASE_TAKE_PROFIT_PCT,
            'max_positions': MAX_POSITIONS,
        }
    }


# 运行入口
if __name__ == '__main__':
    strategy = RobustRSIStrategy()
    strategy.run_once()
