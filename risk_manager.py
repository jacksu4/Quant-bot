"""
高级风险管理系统

功能：
1. Kelly Criterion仓位计算
2. VaR (Value at Risk) 风险价值
3. 最大回撤监控与控制
4. 相关性监控
5. 流动性管理
6. 动态风险调整
"""

import numpy as np
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from exchange import BinanceClient


class RiskMetrics:
    """风险指标类"""

    @staticmethod
    def calculate_returns(prices: List[float]) -> List[float]:
        """计算收益率序列"""
        if len(prices) < 2:
            return []
        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] > 0:
                ret = (prices[i] - prices[i-1]) / prices[i-1]
                returns.append(ret)
            else:
                returns.append(0.0)
        return returns

    @staticmethod
    def calculate_volatility(returns: List[float], annualize: bool = True) -> float:
        """计算波动率"""
        if len(returns) < 2:
            return 0.0

        vol = np.std(returns)

        if annualize:
            # 年化波动率 (假设24小时交易)
            vol = vol * np.sqrt(365 * 24)

        return float(vol)

    @staticmethod
    def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
        """
        计算夏普比率

        Args:
            returns: 收益率序列
            risk_free_rate: 无风险利率 (年化)

        Returns:
            夏普比率
        """
        if len(returns) < 2:
            return 0.0

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0.0

        # 年化
        annualized_return = mean_return * 365 * 24
        annualized_std = std_return * np.sqrt(365 * 24)

        sharpe = (annualized_return - risk_free_rate) / annualized_std
        return float(sharpe)

    @staticmethod
    def calculate_sortino_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
        """
        计算索提诺比率 (只考虑下行风险)

        Returns:
            索提诺比率
        """
        if len(returns) < 2:
            return 0.0

        mean_return = np.mean(returns)
        downside_returns = [r for r in returns if r < 0]

        if len(downside_returns) == 0:
            return float('inf')

        downside_std = np.std(downside_returns)

        if downside_std == 0:
            return 0.0

        # 年化
        annualized_return = mean_return * 365 * 24
        annualized_downside = downside_std * np.sqrt(365 * 24)

        sortino = (annualized_return - risk_free_rate) / annualized_downside
        return float(sortino)

    @staticmethod
    def calculate_max_drawdown(equity_curve: List[float]) -> Tuple[float, int, int]:
        """
        计算最大回撤

        Returns:
            (max_drawdown_pct, peak_idx, trough_idx)
        """
        if len(equity_curve) < 2:
            return 0.0, 0, 0

        peak = equity_curve[0]
        peak_idx = 0
        max_dd = 0.0
        max_dd_start = 0
        max_dd_end = 0

        for i in range(1, len(equity_curve)):
            if equity_curve[i] > peak:
                peak = equity_curve[i]
                peak_idx = i
            else:
                dd = (peak - equity_curve[i]) / peak
                if dd > max_dd:
                    max_dd = dd
                    max_dd_start = peak_idx
                    max_dd_end = i

        return float(max_dd), max_dd_start, max_dd_end

    @staticmethod
    def calculate_var(returns: List[float], confidence: float = 0.99) -> float:
        """
        计算VaR (Value at Risk)

        Args:
            returns: 收益率序列
            confidence: 置信度 (0.95, 0.99)

        Returns:
            VaR值 (百分比，正数表示损失)
        """
        if len(returns) < 10:
            return 0.0

        # 使用历史模拟法
        sorted_returns = sorted(returns)
        index = int((1 - confidence) * len(sorted_returns))
        var = -sorted_returns[index] if index < len(sorted_returns) else 0

        return float(var)

    @staticmethod
    def calculate_cvar(returns: List[float], confidence: float = 0.99) -> float:
        """
        计算CVaR (Conditional VaR, 条件风险价值)
        尾部平均损失

        Returns:
            CVaR值
        """
        if len(returns) < 10:
            return 0.0

        sorted_returns = sorted(returns)
        cutoff_index = int((1 - confidence) * len(sorted_returns))

        tail_losses = sorted_returns[:cutoff_index] if cutoff_index > 0 else sorted_returns[:1]
        cvar = -np.mean(tail_losses)

        return float(cvar)


class KellyCriterion:
    """Kelly Criterion 仓位计算"""

    @staticmethod
    def calculate_kelly_fraction(win_rate: float, avg_win: float, avg_loss: float, kelly_fraction: float = 0.5) -> float:
        """
        计算Kelly仓位

        Kelly% = (p * b - q) / b
        p = 胜率
        b = 赔率 (平均盈利/平均亏损)
        q = 1 - p

        Args:
            win_rate: 胜率 (0-1)
            avg_win: 平均盈利 (百分比)
            avg_loss: 平均亏损 (百分比，正数)
            kelly_fraction: Kelly分数调整 (0.25-0.5保守)

        Returns:
            建议仓位 (0-1)
        """
        if win_rate <= 0 or win_rate >= 1 or avg_loss == 0:
            return 0.0

        lose_rate = 1 - win_rate
        odds_ratio = avg_win / avg_loss  # b

        kelly_pct = (win_rate * odds_ratio - lose_rate) / odds_ratio

        # 限制Kelly值
        kelly_pct = max(0, min(kelly_pct, 1.0))

        # 使用部分Kelly (更保守)
        adjusted_kelly = kelly_pct * kelly_fraction

        return float(adjusted_kelly)

    @staticmethod
    def estimate_kelly_from_history(pnl_history: List[float], kelly_fraction: float = 0.5) -> float:
        """
        从历史交易记录估算Kelly仓位

        Args:
            pnl_history: 历史盈亏记录 (百分比)
            kelly_fraction: Kelly分数

        Returns:
            建议仓位
        """
        if len(pnl_history) < 10:
            return 0.3  # 默认保守值

        wins = [p for p in pnl_history if p > 0]
        losses = [abs(p) for p in pnl_history if p < 0]

        if len(wins) == 0 or len(losses) == 0:
            return 0.3

        win_rate = len(wins) / len(pnl_history)
        avg_win = np.mean(wins)
        avg_loss = np.mean(losses)

        kelly = KellyCriterion.calculate_kelly_fraction(win_rate, avg_win, avg_loss, kelly_fraction)

        return kelly


class RiskManager:
    """风险管理主类"""

    def __init__(self, client: BinanceClient = None):
        self.client = client or BinanceClient()

        # 风险参数
        self.MAX_DRAWDOWN = 0.15  # 最大回撤15%
        self.DAILY_LOSS_LIMIT = 0.03  # 单日最大损失3%
        self.MAX_VAR_99 = 0.05  # 99% VaR不超过5%
        self.MAX_CORRELATION = 0.8  # 最大相关性
        self.MIN_LIQUIDITY_RATIO = 0.01  # 最小流动性比率 (仓位/24h成交量)

        # 历史数据文件
        self.HISTORY_FILE = 'data/equity_history.json'

        # 当前状态
        self.current_drawdown = 0.0
        self.daily_pnl = 0.0
        self.risk_level = 'NORMAL'  # NORMAL, CAUTIOUS, DEFENSIVE

    def load_equity_history(self) -> List[Dict]:
        """加载权益曲线历史"""
        if not os.path.exists(self.HISTORY_FILE):
            return []

        try:
            with open(self.HISTORY_FILE, 'r') as f:
                return json.load(f)
        except:
            return []

    def save_equity_snapshot(self, total_value: float):
        """保存权益快照"""
        os.makedirs('data', exist_ok=True)

        history = self.load_equity_history()

        snapshot = {
            'timestamp': datetime.now().isoformat(),
            'total_value': total_value,
            'mode': self.client.get_mode_str(),
        }

        history.append(snapshot)

        # 只保留最近1000个快照
        history = history[-1000:]

        with open(self.HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)

    def calculate_current_drawdown(self) -> float:
        """计算当前回撤"""
        history = self.load_equity_history()

        if len(history) < 2:
            return 0.0

        values = [h['total_value'] for h in history]
        current_value = values[-1]
        peak_value = max(values)

        if peak_value > 0:
            drawdown = (peak_value - current_value) / peak_value
        else:
            drawdown = 0.0

        self.current_drawdown = drawdown
        return drawdown

    def calculate_daily_pnl(self) -> float:
        """计算当日盈亏"""
        history = self.load_equity_history()

        if len(history) < 2:
            return 0.0

        # 找到24小时前的记录
        current_time = datetime.now()
        day_ago = current_time - timedelta(hours=24)

        current_value = history[-1]['total_value']

        # 找最接近24小时前的记录
        for h in reversed(history[:-1]):
            h_time = datetime.fromisoformat(h['timestamp'])
            if h_time <= day_ago:
                old_value = h['total_value']
                if old_value > 0:
                    pnl = (current_value - old_value) / old_value
                else:
                    pnl = 0.0
                self.daily_pnl = pnl
                return pnl

        return 0.0

    def assess_risk_level(self) -> str:
        """
        评估当前风险等级

        Returns:
            'NORMAL', 'CAUTIOUS', 'DEFENSIVE'
        """
        drawdown = self.calculate_current_drawdown()
        daily_pnl = self.calculate_daily_pnl()

        # DEFENSIVE: 触发紧急防守
        if drawdown > self.MAX_DRAWDOWN * 0.8 or daily_pnl < -self.DAILY_LOSS_LIMIT:
            self.risk_level = 'DEFENSIVE'
            return 'DEFENSIVE'

        # CAUTIOUS: 谨慎模式
        if drawdown > self.MAX_DRAWDOWN * 0.5 or daily_pnl < -self.DAILY_LOSS_LIMIT * 0.5:
            self.risk_level = 'CAUTIOUS'
            return 'CAUTIOUS'

        # NORMAL: 正常模式
        self.risk_level = 'NORMAL'
        return 'NORMAL'

    def get_position_size_multiplier(self) -> float:
        """
        根据风险等级返回仓位乘数

        Returns:
            仓位乘数 (0-1)
        """
        risk_level = self.assess_risk_level()

        multipliers = {
            'NORMAL': 1.0,
            'CAUTIOUS': 0.5,
            'DEFENSIVE': 0.2,
        }

        return multipliers.get(risk_level, 1.0)

    def calculate_optimal_position_size(self, symbol: str, total_capital: float,
                                       win_rate: float = 0.55, avg_win: float = 0.03,
                                       avg_loss: float = 0.02) -> float:
        """
        计算最优仓位大小

        综合考虑：
        1. Kelly Criterion
        2. 风险等级
        3. 流动性
        4. 相关性

        Returns:
            建议仓位金额 (USDT)
        """
        # 1. Kelly仓位
        kelly_fraction = KellyCriterion.calculate_kelly_fraction(
            win_rate, avg_win, avg_loss, kelly_fraction=0.5
        )

        # 2. 风险等级调整
        risk_multiplier = self.get_position_size_multiplier()

        # 3. 流动性检查
        try:
            ticker = self.client.get_ticker(symbol)
            volume_24h = ticker.get('quoteVolume', 0)

            # 仓位不应超过24h成交量的1%
            max_liquidity_position = volume_24h * self.MIN_LIQUIDITY_RATIO
        except:
            max_liquidity_position = total_capital * 0.2

        # 计算建议仓位
        kelly_position = total_capital * kelly_fraction * risk_multiplier

        # 限制仓位
        suggested_position = min(kelly_position, max_liquidity_position, total_capital * 0.3)

        return float(suggested_position)

    def check_correlation_risk(self, positions: List[Dict]) -> bool:
        """
        检查持仓相关性风险

        Returns:
            True if 相关性过高，需要分散
        """
        if len(positions) < 2:
            return False

        try:
            # 获取所有持仓的价格历史
            price_data = {}
            for pos in positions:
                symbol = pos['symbol']
                ohlcv = self.client.get_ohlcv(symbol, '1h', limit=100)
                if ohlcv:
                    closes = [candle[4] for candle in ohlcv]
                    price_data[symbol] = closes

            # 计算所有两两相关系数
            correlations = []
            symbols = list(price_data.keys())

            for i in range(len(symbols)):
                for j in range(i+1, len(symbols)):
                    prices_i = price_data[symbols[i]]
                    prices_j = price_data[symbols[j]]

                    if len(prices_i) == len(prices_j) and len(prices_i) > 10:
                        corr = np.corrcoef(prices_i, prices_j)[0, 1]
                        correlations.append(abs(corr))

            # 平均相关性
            if correlations:
                avg_correlation = np.mean(correlations)
                print(f"  持仓平均相关性: {avg_correlation:.2f}")

                if avg_correlation > self.MAX_CORRELATION:
                    print(f"  ⚠️ 相关性过高 ({avg_correlation:.2f} > {self.MAX_CORRELATION})！需要分散持仓")
                    return True

        except Exception as e:
            print(f"  ❌ 相关性检查失败: {e}")

        return False

    def should_stop_trading(self) -> bool:
        """
        判断是否应该停止交易

        Returns:
            True if 应该停止交易
        """
        drawdown = self.calculate_current_drawdown()
        daily_pnl = self.calculate_daily_pnl()

        # 触发熔断机制
        if drawdown > self.MAX_DRAWDOWN:
            print(f"\n🚨 熔断触发！回撤 {drawdown*100:.2f}% > {self.MAX_DRAWDOWN*100:.0f}%")
            print("  停止所有交易，保持USDT")
            return True

        if daily_pnl < -self.DAILY_LOSS_LIMIT:
            print(f"\n🚨 单日亏损限制触发！当日亏损 {daily_pnl*100:.2f}% > {self.DAILY_LOSS_LIMIT*100:.0f}%")
            print("  今日停止交易")
            return True

        return False

    def generate_risk_report(self) -> Dict:
        """
        生成风险报告

        Returns:
            风险报告字典
        """
        print("\n" + "=" * 70)
        print("风险管理报告")
        print("=" * 70)

        history = self.load_equity_history()

        if len(history) < 2:
            print("  数据不足，无法生成报告")
            return {}

        values = [h['total_value'] for h in history]
        returns = RiskMetrics.calculate_returns(values)

        # 计算各项指标
        current_dd = self.calculate_current_drawdown()
        max_dd, _, _ = RiskMetrics.calculate_max_drawdown(values)
        daily_pnl = self.calculate_daily_pnl()
        sharpe = RiskMetrics.calculate_sharpe_ratio(returns)
        sortino = RiskMetrics.calculate_sortino_ratio(returns)
        var_99 = RiskMetrics.calculate_var(returns, 0.99)
        cvar_99 = RiskMetrics.calculate_cvar(returns, 0.99)
        volatility = RiskMetrics.calculate_volatility(returns)

        risk_level = self.assess_risk_level()

        report = {
            'timestamp': datetime.now().isoformat(),
            'risk_level': risk_level,
            'current_drawdown': current_dd,
            'max_drawdown': max_dd,
            'daily_pnl': daily_pnl,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'var_99': var_99,
            'cvar_99': cvar_99,
            'volatility': volatility,
        }

        # 输出报告
        print(f"\n📊 风险等级: {risk_level}")
        print(f"\n回撤指标:")
        print(f"  当前回撤: {current_dd*100:.2f}% {'⚠️' if current_dd > 0.10 else '✅'}")
        print(f"  历史最大回撤: {max_dd*100:.2f}%")
        print(f"  回撤限制: {self.MAX_DRAWDOWN*100:.0f}%")

        print(f"\n收益指标:")
        print(f"  当日盈亏: {daily_pnl*100:+.2f}%")
        print(f"  夏普比率: {sharpe:.2f}")
        print(f"  索提诺比率: {sortino:.2f}")

        print(f"\n风险指标:")
        print(f"  VaR (99%): {var_99*100:.2f}%")
        print(f"  CVaR (99%): {cvar_99*100:.2f}%")
        print(f"  年化波动率: {volatility*100:.1f}%")

        print(f"\n仓位调整:")
        print(f"  仓位乘数: {self.get_position_size_multiplier()*100:.0f}%")

        print("=" * 70)

        return report


# 测试代码
if __name__ == '__main__':
    rm = RiskManager()

    # 模拟权益曲线
    for i in range(20):
        total_value = 10000 + i * 100 - (i % 5) * 50
        rm.save_equity_snapshot(total_value)

    # 生成报告
    report = rm.generate_risk_report()

    # 测试Kelly计算
    optimal_size = rm.calculate_optimal_position_size(
        'BTC/USDT',
        total_capital=10000,
        win_rate=0.55,
        avg_win=0.03,
        avg_loss=0.02
    )
    print(f"\n建议仓位: ${optimal_size:.2f}")
