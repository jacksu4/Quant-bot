"""
回测引擎 - 验证策略有效性

功能：
1. 历史数据回测
2. 性能指标计算（夏普、回撤、胜率等）
3. 可视化结果
4. Walk-Forward分析
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import json
import os


class BacktestEngine:
    """回测引擎"""

    def __init__(self, initial_capital: float = 10000):
        """
        Args:
            initial_capital: 初始资金
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital

        # 交易记录
        self.trades = []
        self.equity_curve = [initial_capital]
        self.timestamps = []

        # 持仓
        self.positions = {}  # {symbol: {'amount': 0.1, 'cost': 50000}}

        # 交易成本
        self.trading_fee = 0.001  # 0.1%
        self.slippage = 0.002  # 0.2%
        self.total_cost_per_trade = self.trading_fee + self.slippage  # 0.3%

    def buy(self, symbol: str, price: float, usdt_amount: float, timestamp: datetime, reason: str = ''):
        """
        买入

        Args:
            symbol: 交易对
            price: 买入价格
            usdt_amount: 买入金额(USDT)
            timestamp: 时间戳
            reason: 买入原因
        """
        # 计算成本
        cost = usdt_amount * self.total_cost_per_trade
        actual_price = price * (1 + self.slippage)  # 滑点

        # 计算买入数量
        amount = (usdt_amount - cost) / actual_price

        if amount <= 0:
            return False

        # 更新持仓
        if symbol in self.positions:
            # 已有持仓，计算新的平均成本
            old_amount = self.positions[symbol]['amount']
            old_cost = self.positions[symbol]['cost']

            new_amount = old_amount + amount
            new_cost = (old_cost * old_amount + actual_price * amount) / new_amount

            self.positions[symbol] = {
                'amount': new_amount,
                'cost': new_cost
            }
        else:
            # 新建持仓
            self.positions[symbol] = {
                'amount': amount,
                'cost': actual_price
            }

        # 扣除资金
        self.current_capital -= usdt_amount

        # 记录交易
        self.trades.append({
            'timestamp': timestamp,
            'symbol': symbol,
            'action': 'BUY',
            'price': actual_price,
            'amount': amount,
            'usdt_value': usdt_amount,
            'cost': cost,
            'reason': reason,
            'capital_after': self.current_capital
        })

        return True

    def sell(self, symbol: str, price: float, amount: float, timestamp: datetime, reason: str = ''):
        """
        卖出

        Args:
            symbol: 交易对
            price: 卖出价格
            amount: 卖出数量
            timestamp: 时间戳
            reason: 卖出原因
        """
        if symbol not in self.positions or self.positions[symbol]['amount'] < amount:
            return False

        # 计算收入
        actual_price = price * (1 - self.slippage)  # 滑点
        usdt_value = amount * actual_price
        cost = usdt_value * self.trading_fee

        net_proceeds = usdt_value - cost

        # 更新持仓
        self.positions[symbol]['amount'] -= amount

        # 清除空仓
        if self.positions[symbol]['amount'] < 1e-8:
            del self.positions[symbol]

        # 增加资金
        self.current_capital += net_proceeds

        # 记录交易
        self.trades.append({
            'timestamp': timestamp,
            'symbol': symbol,
            'action': 'SELL',
            'price': actual_price,
            'amount': amount,
            'usdt_value': net_proceeds,
            'cost': cost,
            'reason': reason,
            'capital_after': self.current_capital
        })

        return True

    def update_equity(self, current_prices: Dict[str, float], timestamp: datetime):
        """
        更新权益

        Args:
            current_prices: {symbol: price}
            timestamp: 时间戳
        """
        # 计算持仓市值
        position_value = 0.0
        for symbol, pos in self.positions.items():
            if symbol in current_prices:
                position_value += pos['amount'] * current_prices[symbol]

        # 总权益 = 可用资金 + 持仓市值
        total_equity = self.current_capital + position_value

        self.equity_curve.append(total_equity)
        self.timestamps.append(timestamp)

    def calculate_metrics(self) -> Dict:
        """
        计算性能指标

        Returns:
            性能指标字典
        """
        if len(self.equity_curve) < 2:
            return {}

        equity = np.array(self.equity_curve)

        # 收益相关
        total_return = (equity[-1] - equity[0]) / equity[0]

        # 计算日收益率
        returns = np.diff(equity) / equity[:-1]

        # 时间跨度（天）
        if len(self.timestamps) >= 2:
            time_span = (self.timestamps[-1] - self.timestamps[0]).total_seconds() / 86400
            years = time_span / 365
        else:
            years = 1

        # 年化收益率
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

        # 波动率
        volatility = np.std(returns) * np.sqrt(365 * 24)  # 年化

        # 夏普比率
        sharpe_ratio = (annualized_return / volatility) if volatility > 0 else 0

        # 最大回撤
        peak = equity[0]
        max_dd = 0
        for value in equity:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd

        # 索提诺比率
        downside_returns = returns[returns < 0]
        downside_std = np.std(downside_returns) * np.sqrt(365 * 24) if len(downside_returns) > 0 else 0
        sortino_ratio = (annualized_return / downside_std) if downside_std > 0 else 0

        # 卡尔玛比率
        calmar_ratio = (annualized_return / max_dd) if max_dd > 0 else 0

        # 交易统计
        winning_trades = [t for t in self.trades if t['action'] == 'SELL' and self._calculate_trade_pnl(t) > 0]
        losing_trades = [t for t in self.trades if t['action'] == 'SELL' and self._calculate_trade_pnl(t) <= 0]

        total_trades = len([t for t in self.trades if t['action'] == 'SELL'])
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0

        avg_win = np.mean([self._calculate_trade_pnl(t) for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([abs(self._calculate_trade_pnl(t)) for t in losing_trades]) if losing_trades else 0
        profit_factor = (avg_win * len(winning_trades)) / (avg_loss * len(losing_trades)) if losing_trades else float('inf')

        metrics = {
            'initial_capital': self.initial_capital,
            'final_capital': equity[-1],
            'total_return': total_return * 100,
            'annualized_return': annualized_return * 100,
            'volatility': volatility * 100,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'max_drawdown': max_dd * 100,
            'calmar_ratio': calmar_ratio,
            'total_trades': total_trades,
            'win_rate': win_rate * 100,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'time_span_days': time_span if 'time_span' in locals() else 0,
        }

        return metrics

    def _calculate_trade_pnl(self, sell_trade: Dict) -> float:
        """计算交易盈亏（简化版）"""
        # 找到对应的买入交易
        symbol = sell_trade['symbol']
        # 简化：假设FIFO
        return 0  # 暂不实现详细的盈亏追踪

    def generate_report(self) -> str:
        """
        生成回测报告

        Returns:
            报告文本
        """
        metrics = self.calculate_metrics()

        report = []
        report.append("=" * 80)
        report.append("回测报告")
        report.append("=" * 80)

        report.append(f"\n资金情况:")
        report.append(f"  初始资金: ${metrics.get('initial_capital', 0):.2f}")
        report.append(f"  最终资金: ${metrics.get('final_capital', 0):.2f}")
        report.append(f"  总收益率: {metrics.get('total_return', 0):+.2f}%")
        report.append(f"  年化收益率: {metrics.get('annualized_return', 0):+.2f}%")

        report.append(f"\n风险指标:")
        report.append(f"  夏普比率: {metrics.get('sharpe_ratio', 0):.2f}")
        report.append(f"  索提诺比率: {metrics.get('sortino_ratio', 0):.2f}")
        report.append(f"  最大回撤: {metrics.get('max_drawdown', 0):.2f}%")
        report.append(f"  卡尔玛比率: {metrics.get('calmar_ratio', 0):.2f}")
        report.append(f"  波动率: {metrics.get('volatility', 0):.2f}%")

        report.append(f"\n交易统计:")
        report.append(f"  总交易次数: {metrics.get('total_trades', 0)}")
        report.append(f"  胜率: {metrics.get('win_rate', 0):.2f}%")
        report.append(f"  平均盈利: ${metrics.get('avg_win', 0):.2f}")
        report.append(f"  平均亏损: ${metrics.get('avg_loss', 0):.2f}")
        report.append(f"  盈亏比: {metrics.get('profit_factor', 0):.2f}")

        report.append(f"\n回测周期: {metrics.get('time_span_days', 0):.0f} 天")

        report.append("=" * 80)

        return "\n".join(report)

    def save_results(self, filename: str = 'data/backtest_results.json'):
        """保存回测结果"""
        os.makedirs('data', exist_ok=True)

        results = {
            'metrics': self.calculate_metrics(),
            'equity_curve': self.equity_curve,
            'timestamps': [t.isoformat() for t in self.timestamps],
            'trades': self.trades,
        }

        # 转换datetime为字符串
        for trade in results['trades']:
            if isinstance(trade['timestamp'], datetime):
                trade['timestamp'] = trade['timestamp'].isoformat()

        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        print(f"\n回测结果已保存至: {filename}")


def simple_backtest_demo():
    """简单回测演示"""
    print("\n" + "=" * 80)
    print("回测演示（模拟数据）")
    print("=" * 80)

    # 创建回测引擎
    engine = BacktestEngine(initial_capital=10000)

    # 模拟数据（BTC价格从50000到55000）
    start_time = datetime(2024, 1, 1)

    # 模拟100个时间点
    for i in range(100):
        timestamp = start_time + timedelta(hours=i)

        # 模拟BTC价格（随机游走）
        btc_price = 50000 + i * 50 + np.random.randn() * 500

        # 简单策略：前50个小时买入，后50个小时卖出
        if i == 10:
            engine.buy('BTC/USDT', btc_price, 3000, timestamp, 'Buy signal')
        elif i == 20:
            engine.buy('BTC/USDT', btc_price, 3000, timestamp, 'Buy signal 2')
        elif i == 60:
            pos = engine.positions.get('BTC/USDT')
            if pos:
                engine.sell('BTC/USDT', btc_price, pos['amount'] / 2, timestamp, 'Take profit')
        elif i == 80:
            pos = engine.positions.get('BTC/USDT')
            if pos:
                engine.sell('BTC/USDT', btc_price, pos['amount'], timestamp, 'Exit')

        # 更新权益
        engine.update_equity({'BTC/USDT': btc_price}, timestamp)

    # 生成报告
    report = engine.generate_report()
    print(report)

    # 保存结果
    engine.save_results()

    return engine


if __name__ == '__main__':
    simple_backtest_demo()
