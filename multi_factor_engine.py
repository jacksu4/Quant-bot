"""
多因子选币引擎 - 专业级量化选币系统

整合6大因子：
1. 动量因子
2. 波动率调整收益因子
3. 相对强度因子
4. 流动性因子
5. 均值回归因子
6. 技术指标综合因子
"""

import numpy as np
from typing import Dict, List, Tuple
from indicators import TechnicalIndicators, z_score, calculate_beta
from exchange import BinanceClient


class Factor:
    """因子基类"""

    def __init__(self, name: str, weight: float):
        self.name = name
        self.weight = weight

    def calculate(self, symbol: str, data: Dict) -> float:
        """计算因子得分，需要子类实现"""
        raise NotImplementedError


class MomentumFactor(Factor):
    """动量因子 - 强者恒强"""

    def __init__(self, weight: float = 0.25):
        super().__init__("Momentum", weight)

    def calculate(self, symbol: str, data: Dict) -> float:
        """
        计算动量得分
        综合7日、14日、30日收益率
        """
        try:
            ohlcv = data.get('ohlcv', {}).get(symbol, [])
            if len(ohlcv) < 30:
                return 0.0

            closes = [candle[4] for candle in ohlcv]

            # 计算不同周期的收益率
            returns_7d = (closes[-1] - closes[-7]) / closes[-7] if len(closes) >= 7 else 0
            returns_14d = (closes[-1] - closes[-14]) / closes[-14] if len(closes) >= 14 else 0
            returns_30d = (closes[-1] - closes[-30]) / closes[-30] if len(closes) >= 30 else 0

            # 加权平均 (近期权重更高)
            momentum_score = (returns_7d * 0.5 + returns_14d * 0.3 + returns_30d * 0.2) * 100

            return momentum_score

        except Exception as e:
            print(f"动量因子计算失败 {symbol}: {e}")
            return 0.0


class SharpeRatioFactor(Factor):
    """波动率调整收益因子 - 风险调整后收益"""

    def __init__(self, weight: float = 0.20):
        super().__init__("SharpeRatio", weight)

    def calculate(self, symbol: str, data: Dict) -> float:
        """计算夏普比率得分"""
        try:
            ohlcv = data.get('ohlcv', {}).get(symbol, [])
            if len(ohlcv) < 30:
                return 0.0

            closes = [candle[4] for candle in ohlcv]

            # 计算30日收益率和波动率
            returns = [(closes[i] - closes[i-1]) / closes[i-1]
                      for i in range(1, len(closes))]

            mean_return = np.mean(returns[-30:])
            std_return = np.std(returns[-30:])

            if std_return > 0:
                sharpe = (mean_return / std_return) * np.sqrt(30)  # 30日年化
                return sharpe * 10  # 放大得分
            return 0.0

        except Exception as e:
            print(f"夏普因子计算失败 {symbol}: {e}")
            return 0.0


class RelativeStrengthFactor(Factor):
    """相对强度因子 - 跑赢大盘"""

    def __init__(self, weight: float = 0.15):
        super().__init__("RelativeStrength", weight)

    def calculate(self, symbol: str, data: Dict) -> float:
        """
        计算相对BTC的强度
        币种收益率 / BTC收益率
        """
        try:
            if symbol == 'BTC/USDT':
                return 0.0  # BTC作为基准，得分为0

            symbol_ohlcv = data.get('ohlcv', {}).get(symbol, [])
            btc_ohlcv = data.get('ohlcv', {}).get('BTC/USDT', [])

            if len(symbol_ohlcv) < 14 or len(btc_ohlcv) < 14:
                return 0.0

            symbol_closes = [candle[4] for candle in symbol_ohlcv]
            btc_closes = [candle[4] for candle in btc_ohlcv]

            # 计算14日收益率
            symbol_return = (symbol_closes[-1] - symbol_closes[-14]) / symbol_closes[-14]
            btc_return = (btc_closes[-1] - btc_closes[-14]) / btc_closes[-14]

            if btc_return != 0:
                relative_strength = (symbol_return / btc_return - 1) * 100
            else:
                relative_strength = symbol_return * 100

            return relative_strength

        except Exception as e:
            print(f"相对强度因子计算失败 {symbol}: {e}")
            return 0.0


class LiquidityFactor(Factor):
    """流动性因子 - 高流动性降低滑点"""

    def __init__(self, weight: float = 0.15):
        super().__init__("Liquidity", weight)

    def calculate(self, symbol: str, data: Dict) -> float:
        """
        计算流动性得分
        24小时成交量相对评分
        """
        try:
            ticker = data.get('tickers', {}).get(symbol, {})
            volume_24h = ticker.get('quoteVolume', 0)  # USDT计价的成交量

            if volume_24h == 0:
                return 0.0

            # 流动性评分 (对数缩放)
            liquidity_score = np.log10(volume_24h + 1) * 2

            return liquidity_score

        except Exception as e:
            print(f"流动性因子计算失败 {symbol}: {e}")
            return 0.0


class MeanReversionFactor(Factor):
    """均值回归因子 - 价格偏离均值"""

    def __init__(self, weight: float = 0.15):
        super().__init__("MeanReversion", weight)

    def calculate(self, symbol: str, data: Dict) -> float:
        """
        计算均值回归得分
        (当前价格 - MA20) / STD20 的Z-Score
        负值越大表示越超卖（得分越高）
        """
        try:
            ohlcv = data.get('ohlcv', {}).get(symbol, [])
            if len(ohlcv) < 20:
                return 0.0

            closes = [candle[4] for candle in ohlcv]

            # 计算20日均线和标准差
            ma_20 = np.mean(closes[-20:])
            std_20 = np.std(closes[-20:])

            if std_20 > 0:
                z = (closes[-1] - ma_20) / std_20
                # 超卖(负Z-Score)得分高，超买(正Z-Score)得分低
                mean_reversion_score = -z * 10
            else:
                mean_reversion_score = 0.0

            return mean_reversion_score

        except Exception as e:
            print(f"均值回归因子计算失败 {symbol}: {e}")
            return 0.0


class TechnicalFactor(Factor):
    """技术指标综合因子 - RSI、MACD、布林带"""

    def __init__(self, weight: float = 0.10):
        super().__init__("Technical", weight)

    def calculate(self, symbol: str, data: Dict) -> float:
        """
        综合多个技术指标得分
        """
        try:
            ohlcv = data.get('ohlcv', {}).get(symbol, [])
            if len(ohlcv) < 30:
                return 0.0

            closes = [candle[4] for candle in ohlcv]
            highs = [candle[2] for candle in ohlcv]
            lows = [candle[3] for candle in ohlcv]

            score = 0.0

            # 1. RSI得分 (超卖30以下得分高)
            rsi_values = TechnicalIndicators.rsi(closes, 14)
            rsi = rsi_values[-1]

            if rsi < 30:
                rsi_score = (30 - rsi) / 30 * 30  # 0-30分
            elif rsi > 70:
                rsi_score = -(rsi - 70) / 30 * 30  # 负分
            else:
                rsi_score = 0

            score += rsi_score * 0.4

            # 2. MACD得分 (金叉得分高)
            dif, dea, macd_hist = TechnicalIndicators.macd(closes)
            if len(macd_hist) >= 2:
                # 金叉
                if dif[-1] > dea[-1] and dif[-2] <= dea[-2]:
                    macd_score = 20
                # 死叉
                elif dif[-1] < dea[-1] and dif[-2] >= dea[-2]:
                    macd_score = -20
                # DIF在DEA上方
                elif dif[-1] > dea[-1]:
                    macd_score = 10
                # DIF在DEA下方
                else:
                    macd_score = -10
            else:
                macd_score = 0

            score += macd_score * 0.3

            # 3. 布林带得分 (触及下轨得分高)
            upper, middle, lower = TechnicalIndicators.bollinger_bands(closes, 20, 2)

            if not np.isnan(lower[-1]) and not np.isnan(upper[-1]):
                bb_width = upper[-1] - lower[-1]
                if bb_width > 0:
                    # 价格在布林带中的位置 (0=下轨, 1=上轨)
                    bb_position = (closes[-1] - lower[-1]) / bb_width

                    # 在下轨附近得分高 (超卖)
                    if bb_position < 0.2:
                        bb_score = 20
                    # 在上轨附近得分低 (超买)
                    elif bb_position > 0.8:
                        bb_score = -20
                    else:
                        bb_score = 0
                else:
                    bb_score = 0
            else:
                bb_score = 0

            score += bb_score * 0.3

            return score

        except Exception as e:
            print(f"技术因子计算失败 {symbol}: {e}")
            return 0.0


class MultiFactorEngine:
    """多因子选币引擎"""

    def __init__(self, client: BinanceClient = None):
        self.client = client or BinanceClient()

        # 初始化6大因子
        self.factors = [
            MomentumFactor(weight=0.25),
            SharpeRatioFactor(weight=0.20),
            RelativeStrengthFactor(weight=0.15),
            LiquidityFactor(weight=0.15),
            MeanReversionFactor(weight=0.15),
            TechnicalFactor(weight=0.10),
        ]

    def collect_data(self, symbols: List[str], timeframe: str = '1h', limit: int = 100) -> Dict:
        """
        收集所有币种的数据

        Returns:
            {
                'ohlcv': {symbol: [[timestamp, o, h, l, c, v], ...]},
                'tickers': {symbol: {...}},
            }
        """
        print("\n📊 收集市场数据...")

        data = {
            'ohlcv': {},
            'tickers': {},
        }

        # 获取K线数据
        for symbol in symbols:
            try:
                ohlcv = self.client.get_ohlcv(symbol, timeframe, limit)
                if ohlcv:
                    data['ohlcv'][symbol] = ohlcv
            except Exception as e:
                print(f"  ❌ 获取{symbol}数据失败: {e}")

        # 获取ticker数据
        try:
            all_tickers = self.client.get_all_tickers()
            data['tickers'] = all_tickers
        except Exception as e:
            print(f"  ❌ 获取ticker数据失败: {e}")

        print(f"  ✅ 数据收集完成: {len(data['ohlcv'])} 个币种")
        return data

    def calculate_factor_scores(self, symbols: List[str], data: Dict) -> Dict[str, Dict[str, float]]:
        """
        计算所有币种的因子得分

        Returns:
            {
                symbol: {
                    'Momentum': 8.5,
                    'SharpeRatio': 3.2,
                    ...
                    'total_score': 45.6
                }
            }
        """
        print("\n🧮 计算因子得分...")

        all_scores = {}

        for symbol in symbols:
            if symbol not in data['ohlcv']:
                continue

            symbol_scores = {}

            # 计算每个因子的原始得分
            raw_scores = []
            for factor in self.factors:
                score = factor.calculate(symbol, data)
                symbol_scores[factor.name] = score
                raw_scores.append(score)

            all_scores[symbol] = symbol_scores

        # 对每个因子进行标准化 (Z-Score)
        print("  标准化因子得分...")
        factor_names = [f.name for f in self.factors]

        for factor_name in factor_names:
            # 收集该因子的所有得分
            scores = [all_scores[sym][factor_name] for sym in all_scores]

            if len(scores) > 0:
                mean = np.mean(scores)
                std = np.std(scores)

                # 标准化
                if std > 0:
                    for symbol in all_scores:
                        raw_score = all_scores[symbol][factor_name]
                        z_score = (raw_score - mean) / std
                        all_scores[symbol][f'{factor_name}_z'] = z_score

        # 计算加权总分
        for symbol in all_scores:
            total_score = 0.0
            for factor in self.factors:
                z_key = f'{factor.name}_z'
                if z_key in all_scores[symbol]:
                    total_score += all_scores[symbol][z_key] * factor.weight

            all_scores[symbol]['total_score'] = total_score

        return all_scores

    def select_coins(self, top_n: int = 5) -> List[Tuple[str, float, Dict]]:
        """
        选择得分最高的N个币种

        Returns:
            [(symbol, total_score, factor_scores), ...]
            按得分从高到低排序
        """
        print("\n" + "=" * 70)
        print("多因子选币引擎")
        print("=" * 70)

        # 收集数据
        symbols = self.client.whitelist
        data = self.collect_data(symbols)

        # 计算得分
        all_scores = self.calculate_factor_scores(symbols, data)

        # 排序
        ranked = []
        for symbol, scores in all_scores.items():
            total_score = scores.get('total_score', 0)
            ranked.append((symbol, total_score, scores))

        ranked.sort(key=lambda x: x[1], reverse=True)

        # 输出结果
        print("\n📈 选币结果:")
        print("-" * 70)
        print(f"{'排名':<4} {'币种':<12} {'总分':<8} {'动量':<8} {'夏普':<8} {'相对强度':<10} {'流动性':<8}")
        print("-" * 70)

        for i, (symbol, total_score, scores) in enumerate(ranked[:top_n], 1):
            momentum = scores.get('Momentum', 0)
            sharpe = scores.get('SharpeRatio', 0)
            relative = scores.get('RelativeStrength', 0)
            liquidity = scores.get('Liquidity', 0)

            print(f"{i:<4} {symbol:<12} {total_score:>7.2f} {momentum:>7.2f} {sharpe:>7.2f} {relative:>9.2f} {liquidity:>7.2f}")

        print("=" * 70)

        return ranked[:top_n]

    def calculate_optimal_weights(self, selected_coins: List[Tuple[str, float, Dict]]) -> Dict[str, float]:
        """
        根据得分计算最优权重

        使用Softmax函数将得分转换为权重
        """
        if not selected_coins:
            return {}

        scores = np.array([score for _, score, _ in selected_coins])

        # 使用Softmax确保权重和为1
        # 温度参数控制权重分布的集中度
        temperature = 2.0
        exp_scores = np.exp(scores / temperature)
        weights = exp_scores / np.sum(exp_scores)

        # 构建权重字典
        weight_dict = {}
        for i, (symbol, _, _) in enumerate(selected_coins):
            weight_dict[symbol] = float(weights[i])

        print("\n💰 最优权重分配:")
        for symbol, weight in weight_dict.items():
            print(f"  {symbol}: {weight*100:.1f}%")

        return weight_dict


# 测试代码
if __name__ == '__main__':
    engine = MultiFactorEngine()

    # 选择top 3币种
    selected = engine.select_coins(top_n=3)

    # 计算权重
    weights = engine.calculate_optimal_weights(selected)
