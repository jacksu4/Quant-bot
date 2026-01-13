#!/usr/bin/env python3
"""
激进动量策略回测脚本

使用历史数据验证策略的表现
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import json

from exchange import BinanceClient
from indicators import TechnicalIndicators


# 策略参数（与 aggressive_momentum_strategy.py 保持一致）
MOMENTUM_LOOKBACK_SHORT = 7
MOMENTUM_LOOKBACK_MEDIUM = 24
MOMENTUM_LOOKBACK_LONG = 72
RSI_PERIOD = 14
RSI_BUY_THRESHOLD = 40
RSI_SELL_THRESHOLD = 70
EMA_FAST = 8
EMA_SLOW = 21
EMA_TREND = 50
MAX_SINGLE_POSITION_PCT = 0.50
MAX_TOTAL_POSITION_PCT = 0.80
HARD_STOP_LOSS_PCT = 3.0
TRAILING_STOP_PCT = 2.0
MIN_TAKE_PROFIT_PCT = 3.0
AGGRESSIVE_TAKE_PROFIT_PCT = 8.0


def calculate_momentum(closes: List[float], period: int) -> float:
    """计算动量"""
    if len(closes) < period + 1:
        return 0.0
    return ((closes[-1] - closes[-period]) / closes[-period]) * 100


def calculate_coin_score(closes: List[float], highs: List[float], lows: List[float],
                         volumes: List[float]) -> float:
    """计算币种得分"""
    if len(closes) < 50:
        return 0.0

    score = 0.0

    # 动量得分
    mom_short = calculate_momentum(closes, MOMENTUM_LOOKBACK_SHORT)
    mom_medium = calculate_momentum(closes, MOMENTUM_LOOKBACK_MEDIUM)
    mom_long = calculate_momentum(closes, min(MOMENTUM_LOOKBACK_LONG, len(closes) - 1))
    momentum_score = mom_short * 0.5 + mom_medium * 0.3 + mom_long * 0.2
    score += momentum_score * 4.0

    # RSI得分
    rsi_values = TechnicalIndicators.rsi(closes, RSI_PERIOD)
    rsi = rsi_values[-1] if rsi_values else 50
    if rsi < 30:
        rsi_score = 20
    elif rsi < 40:
        rsi_score = 15
    elif rsi > 70:
        rsi_score = -10
    else:
        rsi_score = 5
    score += rsi_score

    # MACD得分
    dif, dea, _ = TechnicalIndicators.macd(closes, 12, 26, 9)
    if len(dif) >= 2 and len(dea) >= 2:
        if dif[-1] > dea[-1] and dif[-2] <= dea[-2]:
            macd_score = 10
        elif dif[-1] > dea[-1]:
            macd_score = 5
        elif dif[-1] < dea[-1]:
            macd_score = -5
        else:
            macd_score = 0
    else:
        macd_score = 0
    score += macd_score

    # 趋势得分
    ema_fast = TechnicalIndicators.ema(closes, EMA_FAST)[-1]
    ema_slow = TechnicalIndicators.ema(closes, EMA_SLOW)[-1]
    if ema_fast > ema_slow:
        score += 10
    else:
        score -= 5

    return score


class AggressiveBacktest:
    """激进策略回测"""

    def __init__(self, initial_capital: float = 600):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions = {}  # {symbol: {'amount': x, 'entry_price': y, 'high_price': z}}
        self.trades = []
        self.equity_curve = []
        self.timestamps = []

        # 交易成本
        self.fee_rate = 0.001  # 0.1%
        self.slippage = 0.002  # 0.2%

    def buy(self, symbol: str, price: float, usdt_amount: float, timestamp: datetime, reason: str):
        """买入"""
        cost = usdt_amount * (self.fee_rate + self.slippage)
        actual_price = price * (1 + self.slippage)
        amount = (usdt_amount - cost) / actual_price

        if amount <= 0 or usdt_amount > self.capital:
            return False

        self.capital -= usdt_amount

        if symbol in self.positions:
            old_amount = self.positions[symbol]['amount']
            old_cost = self.positions[symbol]['entry_price'] * old_amount
            new_cost = actual_price * amount
            total_amount = old_amount + amount
            self.positions[symbol] = {
                'amount': total_amount,
                'entry_price': (old_cost + new_cost) / total_amount,
                'high_price': max(self.positions[symbol].get('high_price', price), price)
            }
        else:
            self.positions[symbol] = {
                'amount': amount,
                'entry_price': actual_price,
                'high_price': price
            }

        self.trades.append({
            'timestamp': timestamp,
            'symbol': symbol,
            'action': 'BUY',
            'price': actual_price,
            'amount': amount,
            'usdt_value': usdt_amount,
            'reason': reason
        })
        return True

    def sell(self, symbol: str, price: float, timestamp: datetime, reason: str):
        """卖出全部持仓"""
        if symbol not in self.positions:
            return False

        pos = self.positions[symbol]
        actual_price = price * (1 - self.slippage)
        usdt_value = pos['amount'] * actual_price
        cost = usdt_value * self.fee_rate

        net_proceeds = usdt_value - cost
        pnl = net_proceeds - (pos['entry_price'] * pos['amount'])
        pnl_pct = (actual_price - pos['entry_price']) / pos['entry_price'] * 100

        self.capital += net_proceeds
        del self.positions[symbol]

        self.trades.append({
            'timestamp': timestamp,
            'symbol': symbol,
            'action': 'SELL',
            'price': actual_price,
            'amount': pos['amount'],
            'usdt_value': net_proceeds,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'reason': reason
        })
        return True

    def update_equity(self, prices: Dict[str, float], timestamp: datetime):
        """更新权益"""
        position_value = sum(
            pos['amount'] * prices.get(sym, pos['entry_price'])
            for sym, pos in self.positions.items()
        )
        total_equity = self.capital + position_value
        self.equity_curve.append(total_equity)
        self.timestamps.append(timestamp)

        # 更新最高价
        for sym, pos in self.positions.items():
            if sym in prices:
                pos['high_price'] = max(pos['high_price'], prices[sym])

    def run_backtest(self, client: BinanceClient, days: int = 60):
        """运行回测"""
        print(f"\n{'='*70}")
        print(f"激进动量策略回测 - 最近 {days} 天")
        print(f"初始资金: ${self.initial_capital:.2f}")
        print(f"{'='*70}\n")

        symbols = client.whitelist

        # 获取历史数据
        print("获取历史数据...")
        all_data = {}
        for symbol in symbols:
            ohlcv = client.get_ohlcv(symbol, '1h', limit=min(days * 24 + 100, 1000))
            if ohlcv:
                all_data[symbol] = ohlcv
                print(f"  {symbol}: {len(ohlcv)} 条记录")

        if not all_data:
            print("无法获取数据")
            return

        # 确定回测时间范围
        min_len = min(len(data) for data in all_data.values())
        start_idx = max(50, min_len - days * 24)  # 至少留50个点用于指标计算

        print(f"\n回测 {min_len - start_idx} 个小时 ({(min_len - start_idx) / 24:.1f} 天)")
        print("-" * 70)

        # 回测循环
        for i in range(start_idx, min_len):
            # 获取当前时间的数据
            timestamp = datetime.fromtimestamp(all_data[symbols[0]][i][0] / 1000)

            current_prices = {}
            coin_scores = {}

            for symbol in symbols:
                data = all_data[symbol][:i+1]
                closes = [c[4] for c in data]
                highs = [c[2] for c in data]
                lows = [c[3] for c in data]
                volumes = [c[5] for c in data]

                current_prices[symbol] = closes[-1]
                coin_scores[symbol] = calculate_coin_score(closes, highs, lows, volumes)

            # 检查卖出条件
            for symbol in list(self.positions.keys()):
                pos = self.positions[symbol]
                price = current_prices.get(symbol, pos['entry_price'])
                pnl_pct = (price - pos['entry_price']) / pos['entry_price'] * 100

                # 从最高价回撤
                if pos['high_price'] > 0:
                    drawdown_from_high = ((pos['high_price'] - price) / pos['high_price']) * 100
                else:
                    drawdown_from_high = 0

                should_sell = False
                sell_reason = ""

                # 硬止损
                if pnl_pct <= -HARD_STOP_LOSS_PCT:
                    should_sell = True
                    sell_reason = f"STOP_LOSS ({pnl_pct:.2f}%)"

                # 跟踪止盈
                elif pnl_pct > MIN_TAKE_PROFIT_PCT and drawdown_from_high > TRAILING_STOP_PCT:
                    should_sell = True
                    sell_reason = f"TRAILING_STOP ({pnl_pct:.2f}%)"

                # 激进止盈
                elif pnl_pct >= AGGRESSIVE_TAKE_PROFIT_PCT:
                    should_sell = True
                    sell_reason = f"TAKE_PROFIT ({pnl_pct:.2f}%)"

                if should_sell:
                    self.sell(symbol, price, timestamp, sell_reason)

            # 检查买入条件
            position_value = sum(
                pos['amount'] * current_prices.get(sym, pos['entry_price'])
                for sym, pos in self.positions.items()
            )
            total_value = self.capital + position_value
            position_ratio = position_value / total_value if total_value > 0 else 0

            if position_ratio < MAX_TOTAL_POSITION_PCT and self.capital > 10:
                # 找最高分的未持有币种
                held_currencies = [s.split('/')[0] for s in self.positions.keys()]
                best_symbol = None
                best_score = 10  # 最小买入阈值

                for symbol, score in coin_scores.items():
                    currency = symbol.split('/')[0]
                    if currency not in held_currencies and score > best_score:
                        best_symbol = symbol
                        best_score = score

                if best_symbol:
                    # 计算仓位
                    if best_score > 30:
                        position_pct = MAX_SINGLE_POSITION_PCT
                    elif best_score > 20:
                        position_pct = 0.40
                    else:
                        position_pct = 0.30

                    usdt_amount = min(
                        total_value * position_pct,
                        self.capital * 0.95
                    )

                    if usdt_amount > 10:
                        self.buy(best_symbol, current_prices[best_symbol],
                                usdt_amount, timestamp, f"Score={best_score:.1f}")

            # 更新权益
            self.update_equity(current_prices, timestamp)

        # 生成报告
        self.generate_report()

    def generate_report(self):
        """生成回测报告"""
        print(f"\n{'='*70}")
        print("回测结果报告")
        print(f"{'='*70}\n")

        if not self.equity_curve:
            print("无交易数据")
            return

        final_equity = self.equity_curve[-1]
        total_return = (final_equity - self.initial_capital) / self.initial_capital * 100

        # 计算最大回撤
        peak = self.equity_curve[0]
        max_dd = 0
        for value in self.equity_curve:
            if value > peak:
                peak = value
            dd = (peak - value) / peak * 100
            if dd > max_dd:
                max_dd = dd

        # 计算夏普比率
        if len(self.equity_curve) > 1:
            returns = np.diff(self.equity_curve) / self.equity_curve[:-1]
            if np.std(returns) > 0:
                sharpe = np.mean(returns) / np.std(returns) * np.sqrt(365 * 24)
            else:
                sharpe = 0
        else:
            sharpe = 0

        # 交易统计
        sell_trades = [t for t in self.trades if t['action'] == 'SELL']
        winning_trades = [t for t in sell_trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in sell_trades if t.get('pnl', 0) <= 0]

        win_rate = len(winning_trades) / len(sell_trades) * 100 if sell_trades else 0

        avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([abs(t['pnl']) for t in losing_trades]) if losing_trades else 0

        print(f"资金情况:")
        print(f"  初始资金: ${self.initial_capital:.2f}")
        print(f"  最终资金: ${final_equity:.2f}")
        print(f"  总收益率: {total_return:+.2f}%")

        # 计算回测天数
        if len(self.timestamps) >= 2:
            days = (self.timestamps[-1] - self.timestamps[0]).days
            monthly_return = total_return / max(days / 30, 1)
            print(f"  月均收益: {monthly_return:+.2f}%")
            print(f"  回测天数: {days} 天")

        print(f"\n风险指标:")
        print(f"  最大回撤: {max_dd:.2f}%")
        print(f"  夏普比率: {sharpe:.2f}")

        print(f"\n交易统计:")
        print(f"  总交易次数: {len(sell_trades)}")
        print(f"  胜率: {win_rate:.1f}%")
        print(f"  平均盈利: ${avg_win:.2f}")
        print(f"  平均亏损: ${avg_loss:.2f}")

        if avg_loss > 0:
            profit_factor = avg_win * len(winning_trades) / (avg_loss * len(losing_trades)) if losing_trades else float('inf')
            print(f"  盈亏比: {profit_factor:.2f}")

        # 最近交易
        print(f"\n最近10笔交易:")
        for trade in self.trades[-10:]:
            action = trade['action']
            symbol = trade['symbol'].split('/')[0]
            if action == 'SELL':
                pnl = trade.get('pnl_pct', 0)
                print(f"  {trade['timestamp'].strftime('%m-%d %H:%M')} {action} {symbol} "
                      f"${trade['usdt_value']:.2f} ({pnl:+.2f}%) - {trade['reason']}")
            else:
                print(f"  {trade['timestamp'].strftime('%m-%d %H:%M')} {action} {symbol} "
                      f"${trade['usdt_value']:.2f} - {trade['reason']}")

        print(f"\n{'='*70}")

        # 评估是否能达到目标
        if len(self.timestamps) >= 2:
            days = (self.timestamps[-1] - self.timestamps[0]).days
            if days > 0:
                projected_60d = (1 + total_return/100) ** (60 / days) - 1
                print(f"\n📊 60天预测收益率: {projected_60d * 100:.1f}%")
                if projected_60d >= 1.0:
                    print("✅ 按当前表现，有望在2个月内达到100%收益目标")
                else:
                    print("⚠️  按当前表现，可能无法在2个月内达到100%收益目标")
                    print("   建议：需要更好的市场条件或调整策略参数")

        print(f"{'='*70}\n")


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("激进动量策略回测")
    print("=" * 70)

    # 初始化客户端
    client = BinanceClient()
    print(f"交易模式: {client.get_mode_str()}")

    # 运行回测
    backtest = AggressiveBacktest(initial_capital=600)
    backtest.run_backtest(client, days=60)


if __name__ == "__main__":
    main()
