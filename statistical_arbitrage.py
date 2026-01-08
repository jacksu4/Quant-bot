"""
统计套利模块 - 配对交易

核心思想：
寻找高度相关的币种对，当价差偏离均值时进行对冲交易，
等待价差回归时平仓获利。

适用场景：
- 震荡市或低波动市场
- 相关性稳定的币种对
- 市场中性策略，降低方向性风险
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from scipy import stats
from exchange import BinanceClient
from indicators import z_score


class PairTrading:
    """配对交易类"""

    def __init__(self, symbol_a: str, symbol_b: str, lookback: int = 60):
        """
        Args:
            symbol_a: 币种A
            symbol_b: 币种B
            lookback: 回溯期（用于计算均值和标准差）
        """
        self.symbol_a = symbol_a
        self.symbol_b = symbol_b
        self.lookback = lookback
        self.beta = 1.0  # 对冲比率
        self.spread_mean = 0.0
        self.spread_std = 1.0
        self.spread_history = []

    def calculate_hedge_ratio(self, prices_a: List[float], prices_b: List[float]) -> float:
        """
        计算对冲比率β (通过线性回归)

        Price_A = α + β * Price_B + ε

        Returns:
            β值
        """
        if len(prices_a) != len(prices_b) or len(prices_a) < 10:
            return 1.0

        # 线性回归
        slope, intercept, r_value, p_value, std_err = stats.linregress(prices_b, prices_a)

        self.beta = slope
        return slope

    def calculate_spread(self, price_a: float, price_b: float) -> float:
        """
        计算价差

        Spread = Price_A - β * Price_B
        """
        spread = price_a - self.beta * price_b
        return spread

    def update_spread_statistics(self, spread: float):
        """更新价差统计信息"""
        self.spread_history.append(spread)

        # 只保留最近lookback个数据
        if len(self.spread_history) > self.lookback:
            self.spread_history = self.spread_history[-self.lookback:]

        if len(self.spread_history) >= 20:
            self.spread_mean = np.mean(self.spread_history)
            self.spread_std = np.std(self.spread_history)

    def get_z_score(self, current_spread: float) -> float:
        """
        计算当前价差的Z-Score

        Z = (Spread - Mean) / Std
        """
        if self.spread_std == 0:
            return 0.0

        z = (current_spread - self.spread_mean) / self.spread_std
        return z

    def generate_signal(self, price_a: float, price_b: float) -> Tuple[str, float, Dict]:
        """
        生成交易信号

        Args:
            price_a: 币种A当前价格
            price_b: 币种B当前价格

        Returns:
            (signal, confidence, details)
            signal: 'OPEN_LONG', 'OPEN_SHORT', 'CLOSE', 'HOLD'
            confidence: 0-1
            details: 详细信息
        """
        spread = self.calculate_spread(price_a, price_b)
        self.update_spread_statistics(spread)

        z = self.get_z_score(spread)

        details = {
            'spread': spread,
            'z_score': z,
            'beta': self.beta,
            'mean': self.spread_mean,
            'std': self.spread_std,
        }

        # 信号逻辑
        # Z > 2: 价差过大，做空价差（卖A买B）
        # Z < -2: 价差过小，做多价差（买A卖B）
        # |Z| < 0.5: 价差回归，平仓

        if z > 2.0:
            # 价差过大：A相对B太贵
            signal = 'OPEN_SHORT'  # 卖A买B（实际中因为无法做空，我们降低A增持B）
            confidence = min(abs(z) / 3.0, 1.0)
        elif z < -2.0:
            # 价差过小：A相对B太便宜
            signal = 'OPEN_LONG'  # 买A卖B（增持A降低B）
            confidence = min(abs(z) / 3.0, 1.0)
        elif abs(z) < 0.5:
            # 价差回归
            signal = 'CLOSE'
            confidence = 0.8
        else:
            signal = 'HOLD'
            confidence = 0.0

        return signal, confidence, details


class StatisticalArbitrageEngine:
    """统计套利引擎"""

    def __init__(self, client: BinanceClient = None):
        self.client = client or BinanceClient()
        self.pairs: List[PairTrading] = []
        self.correlation_threshold = 0.7
        self.cointegration_pvalue_threshold = 0.05

    def find_cointegrated_pairs(self, symbols: List[str], min_correlation: float = 0.7) -> List[Tuple[str, str, float, float]]:
        """
        寻找协整的币种对

        Args:
            symbols: 币种列表
            min_correlation: 最小相关系数

        Returns:
            [(symbol_a, symbol_b, correlation, p_value), ...]
        """
        print("\n" + "=" * 70)
        print("寻找协整币种对")
        print("=" * 70)

        # 获取所有币种的价格数据
        price_data = {}
        for symbol in symbols:
            try:
                ohlcv = self.client.get_ohlcv(symbol, '1h', limit=100)
                if ohlcv and len(ohlcv) >= 50:
                    closes = [c[4] for c in ohlcv]
                    price_data[symbol] = closes
            except Exception as e:
                print(f"  ❌ 获取{symbol}数据失败: {e}")

        if len(price_data) < 2:
            print("  数据不足，无法进行配对分析")
            return []

        # 计算所有两两相关性
        cointegrated_pairs = []
        symbols_list = list(price_data.keys())

        print(f"\n分析 {len(symbols_list)} 个币种的配对关系...")

        for i in range(len(symbols_list)):
            for j in range(i+1, len(symbols_list)):
                symbol_a = symbols_list[i]
                symbol_b = symbols_list[j]

                prices_a = price_data[symbol_a]
                prices_b = price_data[symbol_b]

                # 确保长度一致
                min_len = min(len(prices_a), len(prices_b))
                prices_a = prices_a[-min_len:]
                prices_b = prices_b[-min_len:]

                # 1. 计算相关系数
                if len(prices_a) < 20:
                    continue

                correlation = np.corrcoef(prices_a, prices_b)[0, 1]

                # 相关性过低，跳过
                if abs(correlation) < min_correlation:
                    continue

                # 2. ADF检验协整关系
                # 计算价差
                slope, intercept, _, _, _ = stats.linregress(prices_b, prices_a)
                spread = np.array(prices_a) - slope * np.array(prices_b)

                # ADF检验（检验价差是否平稳）
                try:
                    from statsmodels.tsa.stattools import adfuller
                    adf_result = adfuller(spread)
                    p_value = adf_result[1]

                    # p_value < 0.05 表示拒绝原假设（非平稳），即价差是平稳的
                    if p_value < self.cointegration_pvalue_threshold:
                        cointegrated_pairs.append((symbol_a, symbol_b, correlation, p_value))
                        print(f"  ✅ 发现协整对: {symbol_a} <-> {symbol_b} (相关性: {correlation:.3f}, p值: {p_value:.4f})")

                except ImportError:
                    # 如果没有statsmodels，使用简化判断
                    # 检查价差的标准差是否稳定
                    spread_z = z_score(spread.tolist(), period=20)
                    if np.std(spread_z[-20:]) < 1.5:  # 价差相对稳定
                        cointegrated_pairs.append((symbol_a, symbol_b, correlation, 0.01))
                        print(f"  ✅ 发现高相关对: {symbol_a} <-> {symbol_b} (相关性: {correlation:.3f})")
                except Exception as e:
                    pass

        print(f"\n共发现 {len(cointegrated_pairs)} 个协整币种对")
        print("=" * 70)

        return cointegrated_pairs

    def initialize_pairs(self, top_n: int = 3):
        """
        初始化配对交易

        选择top N个协整对进行交易
        """
        symbols = self.client.whitelist
        cointegrated = self.find_cointegrated_pairs(symbols)

        # 按相关性排序，选择top N
        cointegrated.sort(key=lambda x: abs(x[2]), reverse=True)
        selected = cointegrated[:top_n]

        self.pairs = []
        for symbol_a, symbol_b, corr, pval in selected:
            pair = PairTrading(symbol_a, symbol_b, lookback=60)

            # 初始化对冲比率
            try:
                ohlcv_a = self.client.get_ohlcv(symbol_a, '1h', limit=100)
                ohlcv_b = self.client.get_ohlcv(symbol_b, '1h', limit=100)

                if ohlcv_a and ohlcv_b:
                    prices_a = [c[4] for c in ohlcv_a]
                    prices_b = [c[4] for c in ohlcv_b]
                    pair.calculate_hedge_ratio(prices_a, prices_b)

                    # 初始化价差历史
                    for pa, pb in zip(prices_a, prices_b):
                        spread = pair.calculate_spread(pa, pb)
                        pair.update_spread_statistics(spread)

                self.pairs.append(pair)
                print(f"\n✅ 初始化配对: {symbol_a} <-> {symbol_b}")
                print(f"   对冲比率β: {pair.beta:.4f}")
                print(f"   价差均值: {pair.spread_mean:.2f}")
                print(f"   价差标准差: {pair.spread_std:.2f}")

            except Exception as e:
                print(f"\n❌ 初始化配对失败 {symbol_a} <-> {symbol_b}: {e}")

    def generate_all_signals(self) -> List[Dict]:
        """
        生成所有配对的交易信号

        Returns:
            [{
                'pair': (symbol_a, symbol_b),
                'signal': 'OPEN_LONG',
                'confidence': 0.8,
                'details': {...}
            }, ...]
        """
        print("\n" + "=" * 70)
        print("统计套利信号生成")
        print("=" * 70)

        all_signals = []

        for pair in self.pairs:
            try:
                # 获取当前价格
                ticker_a = self.client.get_ticker(pair.symbol_a)
                ticker_b = self.client.get_ticker(pair.symbol_b)

                price_a = ticker_a['last']
                price_b = ticker_b['last']

                # 生成信号
                signal, confidence, details = pair.generate_signal(price_a, price_b)

                if signal != 'HOLD':
                    print(f"\n{pair.symbol_a} <-> {pair.symbol_b}:")
                    print(f"  价差: {details['spread']:.4f}")
                    print(f"  Z-Score: {details['z_score']:.2f}")
                    print(f"  信号: {signal} (置信度: {confidence:.2f})")

                    all_signals.append({
                        'pair': (pair.symbol_a, pair.symbol_b),
                        'signal': signal,
                        'confidence': confidence,
                        'details': details,
                    })

            except Exception as e:
                print(f"\n❌ 生成信号失败 {pair.symbol_a} <-> {pair.symbol_b}: {e}")

        if not all_signals:
            print("\n  无交易信号")

        print("=" * 70)

        return all_signals

    def execute_pair_trade(self, pair_signal: Dict, total_capital: float):
        """
        执行配对交易（演示）

        Args:
            pair_signal: 配对信号
            total_capital: 总资金
        """
        symbol_a, symbol_b = pair_signal['pair']
        signal = pair_signal['signal']
        confidence = pair_signal['confidence']

        print(f"\n配对交易执行计划:")
        print(f"  币种对: {symbol_a} <-> {symbol_b}")
        print(f"  信号: {signal}")

        # 分配资金（配对交易使用较小比例）
        allocation = total_capital * 0.15 * confidence  # 15%最多

        if signal == 'OPEN_LONG':
            # 做多价差：买A，卖/降低B
            print(f"  买入 {symbol_a}: ${allocation * 0.6:.2f}")
            print(f"  减持 {symbol_b}: ${allocation * 0.4:.2f}")
        elif signal == 'OPEN_SHORT':
            # 做空价差：卖/降低A，买B
            print(f"  减持 {symbol_a}: ${allocation * 0.4:.2f}")
            print(f"  买入 {symbol_b}: ${allocation * 0.6:.2f}")
        elif signal == 'CLOSE':
            # 平仓：恢复到中性配置
            print(f"  平仓配对，恢复均衡")

        print(f"\n⚠️  交易执行已禁用（演示模式）")


# 测试代码
if __name__ == '__main__':
    engine = StatisticalArbitrageEngine()

    # 寻找协整对
    engine.initialize_pairs(top_n=2)

    # 生成信号
    if engine.pairs:
        signals = engine.generate_all_signals()

        # 模拟执行
        for sig in signals:
            engine.execute_pair_trade(sig, total_capital=10000)
