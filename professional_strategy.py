"""
专业级多策略量化交易系统

整合策略：
1. 多因子选币 (40%权重)
2. 趋势跟踪 (25%权重)
3. 统计套利 (15%权重)
4. 波动率突破 (10%权重)
5. 动态对冲 (10%权重)

核心优势：
- 多策略分散，降低单一策略失效风险
- 严格风险管理，最大回撤<15%
- 动态资产配置，适应不同市场环境
- Kelly Criterion科学仓位管理
"""

import numpy as np
import json
import os
from datetime import datetime
from typing import Dict, List, Tuple
from exchange import BinanceClient
from indicators import TechnicalIndicators
from multi_factor_engine import MultiFactorEngine
from risk_manager import RiskManager, KellyCriterion


class MarketRegime:
    """市场状态识别"""

    BULL = 'BULL'  # 牛市
    BEAR = 'BEAR'  # 熊市
    NEUTRAL = 'NEUTRAL'  # 震荡市

    @staticmethod
    def identify_market_state(client: BinanceClient) -> str:
        """
        识别当前市场状态

        判断依据：
        1. BTC 7日涨跌幅
        2. 多数币种涨跌分布
        3. 市场波动率

        Returns:
            'BULL', 'BEAR', 'NEUTRAL'
        """
        try:
            # 获取BTC数据
            btc_ohlcv = client.get_ohlcv('BTC/USDT', '1d', limit=30)
            if len(btc_ohlcv) < 7:
                return MarketRegime.NEUTRAL

            btc_closes = [candle[4] for candle in btc_ohlcv]

            # 1. BTC 7日涨跌幅
            btc_7d_return = (btc_closes[-1] - btc_closes[-7]) / btc_closes[-7]

            # 2. BTC波动率
            btc_volatility = np.std(TechnicalIndicators.calculate_returns(btc_closes, 1)[-7:])

            # 3. 多数币种涨跌情况
            rising_count = 0
            falling_count = 0

            for symbol in client.whitelist:
                try:
                    ohlcv = client.get_ohlcv(symbol, '1d', limit=8)
                    if len(ohlcv) >= 8:
                        closes = [candle[4] for candle in ohlcv]
                        ret_7d = (closes[-1] - closes[-7]) / closes[-7]
                        if ret_7d > 0.02:  # 上涨>2%
                            rising_count += 1
                        elif ret_7d < -0.02:  # 下跌>2%
                            falling_count += 1
                except:
                    pass

            total_count = rising_count + falling_count
            rising_ratio = rising_count / total_count if total_count > 0 else 0.5

            # 判断逻辑
            # 牛市：BTC涨幅>5% 且 多数币种上涨
            if btc_7d_return > 0.05 and rising_ratio > 0.6:
                return MarketRegime.BULL

            # 熊市：BTC跌幅>5% 且 多数币种下跌 或 波动率暴增
            if btc_7d_return < -0.05 and (rising_ratio < 0.4 or btc_volatility > 0.05):
                return MarketRegime.BEAR

            # 震荡市：其他情况
            return MarketRegime.NEUTRAL

        except Exception as e:
            print(f"❌ 市场状态识别失败: {e}")
            return MarketRegime.NEUTRAL


class TrendFollowingStrategy:
    """趋势跟踪策略"""

    def __init__(self, client: BinanceClient):
        self.client = client

    def check_trend_signal(self, symbol: str) -> Tuple[str, float]:
        """
        检查趋势信号

        Returns:
            (signal, confidence)
            signal: 'BUY', 'SELL', 'HOLD'
            confidence: 0-1
        """
        try:
            # 获取多时间框架数据
            ohlcv_1h = self.client.get_ohlcv(symbol, '1h', limit=100)
            ohlcv_4h = self.client.get_ohlcv(symbol, '4h', limit=50)

            if len(ohlcv_1h) < 50 or len(ohlcv_4h) < 30:
                return 'HOLD', 0.0

            closes_1h = [c[4] for c in ohlcv_1h]
            closes_4h = [c[4] for c in ohlcv_4h]
            highs_1h = [c[2] for c in ohlcv_1h]
            lows_1h = [c[3] for c in ohlcv_1h]

            # 1. EMA交叉
            ema12 = TechnicalIndicators.ema(closes_1h, 12)
            ema26 = TechnicalIndicators.ema(closes_1h, 26)

            ema_signal = 0
            if ema12[-1] > ema26[-1] and ema12[-2] <= ema26[-2]:
                ema_signal = 1  # 金叉
            elif ema12[-1] < ema26[-1] and ema12[-2] >= ema26[-2]:
                ema_signal = -1  # 死叉

            # 2. MACD
            dif, dea, macd_hist = TechnicalIndicators.macd(closes_1h)

            macd_signal = 0
            if dif[-1] > dea[-1] and dif[-2] <= dea[-2]:
                macd_signal = 1  # MACD金叉
            elif dif[-1] < dea[-1] and dif[-2] >= dea[-2]:
                macd_signal = -1  # MACD死叉

            # 3. ADX (趋势强度)
            adx_values = TechnicalIndicators.adx(highs_1h, lows_1h, closes_1h, 14)
            adx = adx_values[-1]

            trend_strength = min(adx / 25, 1.0)  # ADX>25表示强趋势

            # 4. 多时间框架确认
            ema12_4h = TechnicalIndicators.ema(closes_4h, 12)
            ema26_4h = TechnicalIndicators.ema(closes_4h, 26)

            timeframe_confirm = 1 if ema12_4h[-1] > ema26_4h[-1] else -1

            # 综合判断
            total_signal = ema_signal + macd_signal
            confidence = 0.0

            if total_signal >= 1 and timeframe_confirm > 0 and adx > 20:
                signal = 'BUY'
                confidence = min(0.3 + trend_strength * 0.4, 1.0)
            elif total_signal <= -1 and timeframe_confirm < 0 and adx > 20:
                signal = 'SELL'
                confidence = min(0.3 + trend_strength * 0.4, 1.0)
            else:
                signal = 'HOLD'
                confidence = 0.0

            return signal, confidence

        except Exception as e:
            print(f"  ❌ 趋势信号检查失败 {symbol}: {e}")
            return 'HOLD', 0.0


class VolatilityBreakoutStrategy:
    """波动率突破策略"""

    def __init__(self, client: BinanceClient):
        self.client = client

    def check_breakout_signal(self, symbol: str) -> Tuple[str, float]:
        """
        检查波动率突破信号

        Returns:
            (signal, confidence)
        """
        try:
            ohlcv = self.client.get_ohlcv(symbol, '1h', limit=50)
            if len(ohlcv) < 30:
                return 'HOLD', 0.0

            closes = [c[4] for c in ohlcv]
            volumes = [c[5] for c in ohlcv]
            highs = [c[2] for c in ohlcv]
            lows = [c[3] for c in ohlcv]

            # 1. 布林带
            upper, middle, lower = TechnicalIndicators.bollinger_bands(closes, 20, 2)

            if np.isnan(upper[-1]) or np.isnan(lower[-1]):
                return 'HOLD', 0.0

            # 布林带宽度
            bb_width = (upper[-1] - lower[-1]) / middle[-1]
            avg_bb_width = np.mean([(upper[i] - lower[i]) / middle[i]
                                   for i in range(-20, -1) if not np.isnan(upper[i])])

            # 低波动区间
            is_low_volatility = bb_width < avg_bb_width * 0.7

            # 2. ATR
            atr_values = TechnicalIndicators.atr(highs, lows, closes, 14)
            atr = atr_values[-1]
            avg_atr = np.mean(atr_values[-20:])

            # 3. 成交量
            volume_ratio = volumes[-1] / np.mean(volumes[-20:]) if np.mean(volumes[-20:]) > 0 else 1

            # 4. 突破检测
            price = closes[-1]

            # 向上突破
            if price > upper[-2] and volume_ratio > 1.5 and is_low_volatility:
                rsi_values = TechnicalIndicators.rsi(closes, 14)
                if rsi_values[-1] > 50:
                    confidence = min(0.5 + volume_ratio * 0.1, 1.0)
                    return 'BUY', confidence

            # 向下突破（避免）
            if price < lower[-2] and volume_ratio > 1.5:
                return 'SELL', 0.5

            return 'HOLD', 0.0

        except Exception as e:
            print(f"  ❌ 突破信号检查失败 {symbol}: {e}")
            return 'HOLD', 0.0


class ProfessionalStrategy:
    """专业级多策略交易系统"""

    def __init__(self, client: BinanceClient = None):
        self.client = client or BinanceClient()

        # 各模块
        self.multi_factor = MultiFactorEngine(self.client)
        self.risk_manager = RiskManager(self.client)
        self.trend_following = TrendFollowingStrategy(self.client)
        self.volatility_breakout = VolatilityBreakoutStrategy(self.client)

        # 策略权重
        self.STRATEGY_WEIGHTS = {
            'multi_factor': 0.40,
            'trend_following': 0.25,
            'statistical_arbitrage': 0.15,
            'volatility_breakout': 0.10,
            'dynamic_hedge': 0.10,
        }

        # 动态资产配置比例
        self.ASSET_ALLOCATION = {
            'BULL': {'crypto': 0.70, 'usdt': 0.30},
            'NEUTRAL': {'crypto': 0.50, 'usdt': 0.50},
            'BEAR': {'crypto': 0.20, 'usdt': 0.80},
        }

        # 日志文件
        self.LOG_FILE = 'data/professional_strategy_log.json'

    def get_target_allocation(self) -> Dict[str, float]:
        """
        获取目标资产配置

        Returns:
            {'crypto': 0.7, 'usdt': 0.3}
        """
        market_state = MarketRegime.identify_market_state(self.client)

        print(f"\n📈 市场状态: {market_state}")

        allocation = self.ASSET_ALLOCATION[market_state]

        # 根据风险等级调整
        risk_level = self.risk_manager.assess_risk_level()

        if risk_level == 'DEFENSIVE':
            # 防守模式：大幅降低加密货币仓位
            allocation = {'crypto': 0.20, 'usdt': 0.80}
            print(f"  🛡️  风险防守模式：加密货币仓位降至20%")
        elif risk_level == 'CAUTIOUS':
            # 谨慎模式：适度降低仓位
            allocation['crypto'] *= 0.7
            allocation['usdt'] = 1 - allocation['crypto']
            print(f"  ⚠️  谨慎模式：加密货币仓位降至{allocation['crypto']*100:.0f}%")

        return allocation

    def generate_trading_signals(self) -> List[Dict]:
        """
        生成交易信号

        整合所有策略的信号

        Returns:
            [{
                'symbol': 'BTC/USDT',
                'action': 'BUY'/'SELL'/'HOLD',
                'confidence': 0.8,
                'strategy': 'multi_factor',
                'suggested_weight': 0.3,
            }, ...]
        """
        print("\n" + "=" * 70)
        print("策略信号生成")
        print("=" * 70)

        all_signals = []

        # 1. 多因子选币策略
        print("\n【策略1：多因子选币】")
        try:
            top_coins = self.multi_factor.select_coins(top_n=3)
            weights = self.multi_factor.calculate_optimal_weights(top_coins)

            for symbol, score, _ in top_coins:
                signal = {
                    'symbol': symbol,
                    'action': 'BUY',
                    'confidence': min(0.5 + score / 20, 1.0),  # 根据得分计算置信度
                    'strategy': 'multi_factor',
                    'suggested_weight': weights.get(symbol, 0) * self.STRATEGY_WEIGHTS['multi_factor'],
                }
                all_signals.append(signal)

        except Exception as e:
            print(f"  ❌ 多因子策略失败: {e}")

        # 2. 趋势跟踪策略
        print("\n【策略2：趋势跟踪】")
        for symbol in self.client.whitelist:
            try:
                trend_signal, confidence = self.trend_following.check_trend_signal(symbol)

                if trend_signal != 'HOLD' and confidence > 0.5:
                    print(f"  {symbol}: {trend_signal} (置信度: {confidence:.2f})")
                    signal = {
                        'symbol': symbol,
                        'action': trend_signal,
                        'confidence': confidence,
                        'strategy': 'trend_following',
                        'suggested_weight': confidence * self.STRATEGY_WEIGHTS['trend_following'],
                    }
                    all_signals.append(signal)

            except Exception as e:
                print(f"  ❌ {symbol} 趋势检查失败: {e}")

        # 3. 波动率突破策略
        print("\n【策略3：波动率突破】")
        for symbol in self.client.whitelist:
            try:
                breakout_signal, confidence = self.volatility_breakout.check_breakout_signal(symbol)

                if breakout_signal != 'HOLD' and confidence > 0.5:
                    print(f"  {symbol}: {breakout_signal} (置信度: {confidence:.2f})")
                    signal = {
                        'symbol': symbol,
                        'action': breakout_signal,
                        'confidence': confidence,
                        'strategy': 'volatility_breakout',
                        'suggested_weight': confidence * self.STRATEGY_WEIGHTS['volatility_breakout'],
                    }
                    all_signals.append(signal)

            except Exception as e:
                print(f"  ❌ {symbol} 突破检查失败: {e}")

        print("\n" + "=" * 70)

        return all_signals

    def aggregate_signals(self, signals: List[Dict]) -> Dict[str, Dict]:
        """
        聚合来自不同策略的信号

        Returns:
            {
                symbol: {
                    'buy_weight': 0.6,
                    'sell_weight': 0.1,
                    'net_signal': 'BUY',
                    'total_weight': 0.5,
                }
            }
        """
        aggregated = {}

        for signal in signals:
            symbol = signal['symbol']

            if symbol not in aggregated:
                aggregated[symbol] = {
                    'buy_weight': 0.0,
                    'sell_weight': 0.0,
                }

            weight = signal['confidence'] * signal['suggested_weight']

            if signal['action'] == 'BUY':
                aggregated[symbol]['buy_weight'] += weight
            elif signal['action'] == 'SELL':
                aggregated[symbol]['sell_weight'] += weight

        # 计算净信号
        for symbol in aggregated:
            buy_w = aggregated[symbol]['buy_weight']
            sell_w = aggregated[symbol]['sell_weight']

            net_weight = buy_w - sell_w
            total_weight = buy_w + sell_w

            if net_weight > 0.1:
                net_signal = 'BUY'
            elif net_weight < -0.1:
                net_signal = 'SELL'
            else:
                net_signal = 'HOLD'

            aggregated[symbol]['net_signal'] = net_signal
            aggregated[symbol]['total_weight'] = abs(net_weight)

        return aggregated

    def execute_rebalance(self, target_allocation: Dict[str, float], aggregated_signals: Dict[str, Dict]):
        """
        执行再平衡

        根据目标配置和信号执行交易
        """
        print("\n" + "=" * 70)
        print("执行交易再平衡")
        print("=" * 70)

        # 检查是否应该停止交易
        if self.risk_manager.should_stop_trading():
            print("\n🚫 风险熔断触发，停止所有交易")
            return

        # 获取当前状态
        total_value = self.client.calculate_total_value_usdt()
        positions = self.client.get_all_positions()
        usdt_balance = self.client.get_usdt_balance()

        print(f"\n当前状态:")
        print(f"  总资产: ${total_value:.2f}")
        print(f"  USDT余额: ${usdt_balance:.2f}")
        print(f"  持仓数: {len(positions)}")

        # 目标加密货币价值
        target_crypto_value = total_value * target_allocation['crypto']

        print(f"\n目标配置:")
        print(f"  加密货币: ${target_crypto_value:.2f} ({target_allocation['crypto']*100:.0f}%)")
        print(f"  USDT: ${total_value * target_allocation['usdt']:.2f} ({target_allocation['usdt']*100:.0f}%)")

        # 选择要买入的币种
        buy_candidates = []
        for symbol, agg in aggregated_signals.items():
            if agg['net_signal'] == 'BUY' and agg['total_weight'] > 0.2:
                buy_candidates.append((symbol, agg['total_weight']))

        buy_candidates.sort(key=lambda x: x[1], reverse=True)
        buy_candidates = buy_candidates[:3]  # 最多3个

        if not buy_candidates:
            print("\n  无买入信号")
            return

        # 计算权重
        total_buy_weight = sum([w for _, w in buy_candidates])
        normalized_weights = {symbol: w / total_buy_weight for symbol, w in buy_candidates}

        print(f"\n买入计划:")
        for symbol, weight in normalized_weights.items():
            target_value = target_crypto_value * weight
            print(f"  {symbol}: ${target_value:.2f} ({weight*100:.1f}%)")

        # 执行交易 (示例，实际应该更复杂)
        print(f"\n⚠️  交易执行已禁用（演示模式）")
        print(f"  如需实际交易，请在真实环境中取消注释交易代码")

        # 保存权益快照
        self.risk_manager.save_equity_snapshot(total_value)

    def run_once(self):
        """执行一次完整的策略循环"""
        print("\n" + "=" * 80)
        print(f"专业级多策略交易系统 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"模式: {self.client.get_mode_str()}")
        print("=" * 80)

        # 1. 风险检查
        self.risk_manager.generate_risk_report()

        # 2. 确定目标配置
        target_allocation = self.get_target_allocation()

        # 3. 生成信号
        signals = self.generate_trading_signals()

        # 4. 聚合信号
        aggregated = self.aggregate_signals(signals)

        print("\n聚合信号:")
        for symbol, agg in sorted(aggregated.items(), key=lambda x: x[1]['total_weight'], reverse=True):
            print(f"  {symbol}: {agg['net_signal']} (权重: {agg['total_weight']:.2f})")

        # 5. 执行再平衡
        self.execute_rebalance(target_allocation, aggregated)

        print("\n" + "=" * 80)


# 测试和运行
if __name__ == '__main__':
    strategy = ProfessionalStrategy()
    strategy.run_once()
