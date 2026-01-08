"""
技术指标库 - 专业级量化交易指标
支持所有主流技术分析指标
"""

import numpy as np
import pandas as pd
from typing import List, Tuple


class TechnicalIndicators:
    """技术指标计算类"""

    @staticmethod
    def ema(prices: List[float], period: int) -> List[float]:
        """
        指数移动平均线 (Exponential Moving Average)

        Args:
            prices: 价格序列
            period: 周期

        Returns:
            EMA序列
        """
        prices = np.array(prices)
        ema = np.zeros_like(prices)
        ema[0] = prices[0]

        multiplier = 2 / (period + 1)

        for i in range(1, len(prices)):
            ema[i] = (prices[i] - ema[i-1]) * multiplier + ema[i-1]

        return ema.tolist()

    @staticmethod
    def sma(prices: List[float], period: int) -> List[float]:
        """简单移动平均线 (Simple Moving Average)"""
        if len(prices) < period:
            return [np.nan] * len(prices)

        result = []
        for i in range(len(prices)):
            if i < period - 1:
                result.append(np.nan)
            else:
                result.append(np.mean(prices[i-period+1:i+1]))

        return result

    @staticmethod
    def macd(prices: List[float], fast=12, slow=26, signal=9) -> Tuple[List[float], List[float], List[float]]:
        """
        MACD指标 (Moving Average Convergence Divergence)

        Returns:
            (DIF, DEA, MACD)
            DIF: 快线 (MACD Line)
            DEA: 慢线 (Signal Line)
            MACD: 柱状图 (Histogram)
        """
        ema_fast = TechnicalIndicators.ema(prices, fast)
        ema_slow = TechnicalIndicators.ema(prices, slow)

        dif = [f - s for f, s in zip(ema_fast, ema_slow)]
        dea = TechnicalIndicators.ema(dif, signal)
        macd_hist = [2 * (d - e) for d, e in zip(dif, dea)]

        return dif, dea, macd_hist

    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> List[float]:
        """
        相对强弱指标 (Relative Strength Index)

        Returns:
            RSI序列 (0-100)
        """
        if len(prices) < period + 1:
            return [50.0] * len(prices)

        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        rsi_values = [50.0] * (period + 1)

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            if avg_loss == 0:
                rsi_values.append(100.0 if avg_gain > 0 else 50.0)
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
                rsi_values.append(rsi)

        return rsi_values

    @staticmethod
    def bollinger_bands(prices: List[float], period: int = 20, std_dev: float = 2.0) -> Tuple[List[float], List[float], List[float]]:
        """
        布林带 (Bollinger Bands)

        Returns:
            (upper_band, middle_band, lower_band)
        """
        middle = TechnicalIndicators.sma(prices, period)

        upper = []
        lower = []

        for i in range(len(prices)):
            if i < period - 1:
                upper.append(np.nan)
                lower.append(np.nan)
            else:
                std = np.std(prices[i-period+1:i+1])
                upper.append(middle[i] + std_dev * std)
                lower.append(middle[i] - std_dev * std)

        return upper, middle, lower

    @staticmethod
    def atr(high: List[float], low: List[float], close: List[float], period: int = 14) -> List[float]:
        """
        平均真实波幅 (Average True Range)
        衡量波动率的指标
        """
        if len(high) < 2:
            return [0.0] * len(high)

        tr_list = [high[0] - low[0]]  # First TR

        for i in range(1, len(high)):
            h_l = high[i] - low[i]
            h_pc = abs(high[i] - close[i-1])
            l_pc = abs(low[i] - close[i-1])
            tr = max(h_l, h_pc, l_pc)
            tr_list.append(tr)

        # 计算ATR (使用EMA平滑)
        atr_values = [np.mean(tr_list[:period])]

        for i in range(period, len(tr_list)):
            atr = (atr_values[-1] * (period - 1) + tr_list[i]) / period
            atr_values.append(atr)

        # 填充前面的值
        result = [atr_values[0]] * period + atr_values
        return result[:len(high)]

    @staticmethod
    def adx(high: List[float], low: List[float], close: List[float], period: int = 14) -> List[float]:
        """
        平均趋向指标 (Average Directional Index)
        衡量趋势强度，ADX > 25表示强趋势

        Returns:
            ADX值 (0-100)
        """
        if len(high) < period + 1:
            return [0.0] * len(high)

        # 计算+DM和-DM
        plus_dm = []
        minus_dm = []

        for i in range(1, len(high)):
            up_move = high[i] - high[i-1]
            down_move = low[i-1] - low[i]

            if up_move > down_move and up_move > 0:
                plus_dm.append(up_move)
            else:
                plus_dm.append(0)

            if down_move > up_move and down_move > 0:
                minus_dm.append(down_move)
            else:
                minus_dm.append(0)

        # 计算ATR
        atr_values = TechnicalIndicators.atr(high, low, close, period)

        # 计算+DI和-DI
        plus_di = []
        minus_di = []

        for i in range(len(plus_dm)):
            if atr_values[i+1] > 0:
                plus_di.append(100 * plus_dm[i] / atr_values[i+1])
                minus_di.append(100 * minus_dm[i] / atr_values[i+1])
            else:
                plus_di.append(0)
                minus_di.append(0)

        # 计算DX
        dx = []
        for i in range(len(plus_di)):
            di_sum = plus_di[i] + minus_di[i]
            if di_sum > 0:
                dx.append(100 * abs(plus_di[i] - minus_di[i]) / di_sum)
            else:
                dx.append(0)

        # 计算ADX (DX的平滑移动平均)
        if len(dx) < period:
            return [0.0] * len(high)

        adx_values = [np.mean(dx[:period])]

        for i in range(period, len(dx)):
            adx = (adx_values[-1] * (period - 1) + dx[i]) / period
            adx_values.append(adx)

        # 填充前面的值
        result = [0.0] * (period + 1) + adx_values
        return result[:len(high)]

    @staticmethod
    def stochastic(high: List[float], low: List[float], close: List[float], period: int = 14) -> Tuple[List[float], List[float]]:
        """
        随机指标 (Stochastic Oscillator)

        Returns:
            (K值, D值)
        """
        k_values = []

        for i in range(len(close)):
            if i < period - 1:
                k_values.append(50.0)
            else:
                highest = max(high[i-period+1:i+1])
                lowest = min(low[i-period+1:i+1])

                if highest == lowest:
                    k_values.append(50.0)
                else:
                    k = 100 * (close[i] - lowest) / (highest - lowest)
                    k_values.append(k)

        # D值是K值的3日SMA
        d_values = TechnicalIndicators.sma(k_values, 3)

        return k_values, d_values

    @staticmethod
    def obv(close: List[float], volume: List[float]) -> List[float]:
        """
        能量潮指标 (On-Balance Volume)
        衡量资金流入流出
        """
        obv_values = [0]

        for i in range(1, len(close)):
            if close[i] > close[i-1]:
                obv_values.append(obv_values[-1] + volume[i])
            elif close[i] < close[i-1]:
                obv_values.append(obv_values[-1] - volume[i])
            else:
                obv_values.append(obv_values[-1])

        return obv_values

    @staticmethod
    def momentum(prices: List[float], period: int = 10) -> List[float]:
        """
        动量指标 (Momentum)
        计算当前价格与N期前价格的差值
        """
        result = []
        for i in range(len(prices)):
            if i < period:
                result.append(0)
            else:
                result.append(prices[i] - prices[i-period])
        return result

    @staticmethod
    def roc(prices: List[float], period: int = 10) -> List[float]:
        """
        变动率指标 (Rate of Change)
        计算当前价格相对N期前的百分比变化
        """
        result = []
        for i in range(len(prices)):
            if i < period or prices[i-period] == 0:
                result.append(0)
            else:
                roc = ((prices[i] - prices[i-period]) / prices[i-period]) * 100
                result.append(roc)
        return result

    @staticmethod
    def williams_r(high: List[float], low: List[float], close: List[float], period: int = 14) -> List[float]:
        """
        威廉指标 (Williams %R)
        类似Stochastic，但范围是-100到0
        """
        wr_values = []

        for i in range(len(close)):
            if i < period - 1:
                wr_values.append(-50.0)
            else:
                highest = max(high[i-period+1:i+1])
                lowest = min(low[i-period+1:i+1])

                if highest == lowest:
                    wr_values.append(-50.0)
                else:
                    wr = -100 * (highest - close[i]) / (highest - lowest)
                    wr_values.append(wr)

        return wr_values

    @staticmethod
    def cci(high: List[float], low: List[float], close: List[float], period: int = 20) -> List[float]:
        """
        顺势指标 (Commodity Channel Index)
        衡量价格偏离平均值的程度
        """
        typical_price = [(h + l + c) / 3 for h, l, c in zip(high, low, close)]
        sma_tp = TechnicalIndicators.sma(typical_price, period)

        cci_values = []
        for i in range(len(typical_price)):
            if i < period - 1:
                cci_values.append(0)
            else:
                mean_dev = np.mean([abs(typical_price[j] - sma_tp[i])
                                   for j in range(i-period+1, i+1)])
                if mean_dev > 0:
                    cci = (typical_price[i] - sma_tp[i]) / (0.015 * mean_dev)
                    cci_values.append(cci)
                else:
                    cci_values.append(0)

        return cci_values

    @staticmethod
    def calculate_returns(prices: List[float], period: int = 1) -> List[float]:
        """
        计算收益率

        Args:
            prices: 价格序列
            period: 计算周期

        Returns:
            收益率序列 (百分比)
        """
        returns = []
        for i in range(len(prices)):
            if i < period:
                returns.append(0.0)
            else:
                if prices[i-period] > 0:
                    ret = ((prices[i] - prices[i-period]) / prices[i-period]) * 100
                    returns.append(ret)
                else:
                    returns.append(0.0)
        return returns

    @staticmethod
    def volatility(prices: List[float], period: int = 20) -> List[float]:
        """
        计算历史波动率 (标准差)

        Returns:
            波动率序列 (年化百分比)
        """
        returns = TechnicalIndicators.calculate_returns(prices, 1)

        vol_values = []
        for i in range(len(returns)):
            if i < period - 1:
                vol_values.append(0.0)
            else:
                std = np.std(returns[i-period+1:i+1])
                # 年化波动率 (假设24小时交易)
                annualized_vol = std * np.sqrt(365 * 24)
                vol_values.append(annualized_vol)

        return vol_values

    @staticmethod
    def sharpe_ratio(prices: List[float], period: int = 30, risk_free_rate: float = 0.0) -> List[float]:
        """
        夏普比率 (风险调整后收益)

        Args:
            prices: 价格序列
            period: 计算周期
            risk_free_rate: 无风险利率 (年化百分比)

        Returns:
            夏普比率序列
        """
        returns = TechnicalIndicators.calculate_returns(prices, 1)

        sharpe_values = []
        for i in range(len(returns)):
            if i < period - 1:
                sharpe_values.append(0.0)
            else:
                period_returns = returns[i-period+1:i+1]
                mean_return = np.mean(period_returns)
                std_return = np.std(period_returns)

                if std_return > 0:
                    # 年化夏普比率
                    annualized_return = mean_return * 365 * 24
                    annualized_std = std_return * np.sqrt(365 * 24)
                    sharpe = (annualized_return - risk_free_rate) / annualized_std
                    sharpe_values.append(sharpe)
                else:
                    sharpe_values.append(0.0)

        return sharpe_values


def calculate_correlation(prices_a: List[float], prices_b: List[float]) -> float:
    """
    计算两个价格序列的相关系数

    Returns:
        相关系数 (-1 到 1)
    """
    if len(prices_a) != len(prices_b) or len(prices_a) < 2:
        return 0.0

    return np.corrcoef(prices_a, prices_b)[0, 1]


def calculate_beta(prices_asset: List[float], prices_market: List[float]) -> float:
    """
    计算资产相对市场的Beta系数

    Args:
        prices_asset: 资产价格序列
        prices_market: 市场(如BTC)价格序列

    Returns:
        Beta系数
    """
    if len(prices_asset) != len(prices_market) or len(prices_asset) < 2:
        return 1.0

    returns_asset = np.diff(prices_asset) / prices_asset[:-1]
    returns_market = np.diff(prices_market) / prices_market[:-1]

    covariance = np.cov(returns_asset, returns_market)[0, 1]
    market_variance = np.var(returns_market)

    if market_variance > 0:
        return covariance / market_variance
    return 1.0


def z_score(values: List[float], period: int = 20) -> List[float]:
    """
    计算Z-Score (标准化分数)
    Z = (X - μ) / σ

    Returns:
        Z-Score序列
    """
    result = []
    for i in range(len(values)):
        if i < period - 1:
            result.append(0.0)
        else:
            window = values[i-period+1:i+1]
            mean = np.mean(window)
            std = np.std(window)

            if std > 0:
                z = (values[i] - mean) / std
                result.append(z)
            else:
                result.append(0.0)

    return result
