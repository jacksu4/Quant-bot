"""
激进动量策略 - 高收益追求版本

目标：2个月100%收益（非常激进，高风险高回报）

策略核心逻辑：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 动量追踪 - 追涨最强势的币种
2. 多因子选币 - 综合动量、相对强度、技术指标
3. 激进仓位 - 高确定性信号时使用大仓位(最高50%)
4. 快速轮动 - 每小时评估，及时换入更强的币种
5. 动态止盈止损 - 跟踪止盈锁定利润，紧急止损控制风险
6. 波动率利用 - 高波动期加大仓位

风险控制：
- 单仓最大50%
- 总仓位最大80%
- 每日亏损5%熔断
- 最大回撤15%熔断
- 紧急止损3%

目标性能（激进市场条件下）：
- 月收益: 30-50%
- 胜率: > 50%
- 夏普比率: > 1.5

⚠️  警告：此策略风险极高，仅适用于能承受高风险的投资者
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import json
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from exchange import BinanceClient
from indicators import TechnicalIndicators

# ============================================================================
# 策略参数配置
# ============================================================================

# 动量参数
MOMENTUM_LOOKBACK_SHORT = 7    # 短期动量（小时）
MOMENTUM_LOOKBACK_MEDIUM = 24  # 中期动量（小时）
MOMENTUM_LOOKBACK_LONG = 72    # 长期动量（小时）
MOMENTUM_THRESHOLD = 0.5       # 动量阈值（%）

# RSI参数
RSI_PERIOD = 14
RSI_BUY_THRESHOLD = 40         # RSI低于此值考虑买入（比传统30更激进）
RSI_SELL_THRESHOLD = 70        # RSI高于此值考虑卖出
RSI_STRONG_BUY = 30            # 强买入信号

# EMA参数
EMA_FAST = 8                   # 快速EMA
EMA_SLOW = 21                  # 慢速EMA
EMA_TREND = 50                 # 趋势EMA

# 仓位管理
MAX_SINGLE_POSITION_PCT = 0.50   # 单仓最大50%
MAX_TOTAL_POSITION_PCT = 0.80    # 总仓位最大80%
MIN_TRADE_USDT = 6.0             # 最小交易额
BASE_POSITION_PCT = 0.30         # 基础仓位30%

# 止损止盈
HARD_STOP_LOSS_PCT = 3.0         # 硬止损3%
TRAILING_STOP_PCT = 2.0          # 跟踪止盈回撤2%
MIN_TAKE_PROFIT_PCT = 3.0        # 最小止盈3%
AGGRESSIVE_TAKE_PROFIT_PCT = 8.0 # 激进止盈8%

# 风控参数
DAILY_LOSS_LIMIT_PCT = 5.0       # 每日亏损限制5%
MAX_DRAWDOWN_PCT = 15.0          # 最大回撤限制15%

# 轮动参数
ROTATION_INTERVAL_HOURS = 4      # 每4小时评估轮动
MIN_ROTATION_IMPROVEMENT = 2.0   # 最小轮动提升（分数）

# 日志文件
LOG_FILE = 'data/aggressive_strategy_log.json'
EQUITY_FILE = 'data/aggressive_equity_history.json'


def calculate_momentum(closes: List[float], period: int) -> float:
    """计算动量（百分比变化）"""
    if len(closes) < period + 1:
        return 0.0
    return ((closes[-1] - closes[-period]) / closes[-period]) * 100


def calculate_volatility(closes: List[float], period: int = 20) -> float:
    """计算波动率（标准差）"""
    if len(closes) < period:
        return 0.0
    returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
    if len(returns) < period:
        return 0.0
    return np.std(returns[-period:]) * 100


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
    logs = logs[-2000:]  # 保留更多日志

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


class AggressiveMomentumStrategy:
    """激进动量策略 - 高收益追求版"""

    def __init__(self, client: BinanceClient = None):
        self.client = client or BinanceClient()
        self.position_entry_prices = {}  # 入场价格
        self.position_high_prices = {}   # 持仓期间最高价（用于跟踪止盈）
        self.last_rotation_time = None   # 上次轮动时间
        self.daily_starting_value = None # 每日起始价值
        self.daily_start_date = None     # 每日起始日期

    def get_market_data(self, symbol: str) -> Optional[Dict]:
        """获取市场数据并计算指标"""
        try:
            # 获取1小时K线（用于主要分析）
            ohlcv_1h = self.client.get_ohlcv(symbol, '1h', limit=100)
            if len(ohlcv_1h) < 50:
                return None

            # 获取15分钟K线（用于入场时机）
            ohlcv_15m = self.client.get_ohlcv(symbol, '15m', limit=50)
            if len(ohlcv_15m) < 20:
                return None

            # 获取4小时K线（用于趋势确认）
            ohlcv_4h = self.client.get_ohlcv(symbol, '4h', limit=50)
            if len(ohlcv_4h) < 20:
                return None

            # 提取1小时数据
            closes_1h = [c[4] for c in ohlcv_1h]
            highs_1h = [c[2] for c in ohlcv_1h]
            lows_1h = [c[3] for c in ohlcv_1h]
            volumes_1h = [c[5] for c in ohlcv_1h]

            # 提取15分钟数据
            closes_15m = [c[4] for c in ohlcv_15m]

            # 提取4小时数据
            closes_4h = [c[4] for c in ohlcv_4h]

            current_price = closes_1h[-1]

            # 计算动量
            momentum_short = calculate_momentum(closes_1h, MOMENTUM_LOOKBACK_SHORT)
            momentum_medium = calculate_momentum(closes_1h, MOMENTUM_LOOKBACK_MEDIUM)
            momentum_long = calculate_momentum(closes_1h, MOMENTUM_LOOKBACK_LONG)

            # 综合动量得分（近期权重更高）
            momentum_score = momentum_short * 0.5 + momentum_medium * 0.3 + momentum_long * 0.2

            # RSI
            rsi_1h = TechnicalIndicators.rsi(closes_1h, RSI_PERIOD)[-1]
            rsi_15m = TechnicalIndicators.rsi(closes_15m, RSI_PERIOD)[-1]
            rsi_4h = TechnicalIndicators.rsi(closes_4h, RSI_PERIOD)[-1]

            # EMA
            ema_fast = TechnicalIndicators.ema(closes_1h, EMA_FAST)[-1]
            ema_slow = TechnicalIndicators.ema(closes_1h, EMA_SLOW)[-1]
            ema_trend = TechnicalIndicators.ema(closes_1h, EMA_TREND)[-1]

            # MACD
            dif, dea, macd_hist = TechnicalIndicators.macd(closes_1h, 12, 26, 9)
            macd_signal = 0
            if len(dif) >= 2 and len(dea) >= 2:
                if dif[-1] > dea[-1] and dif[-2] <= dea[-2]:
                    macd_signal = 1  # 金叉
                elif dif[-1] < dea[-1] and dif[-2] >= dea[-2]:
                    macd_signal = -1  # 死叉
                elif dif[-1] > dea[-1]:
                    macd_signal = 0.5  # DIF在DEA上方
                else:
                    macd_signal = -0.5  # DIF在DEA下方

            # 布林带
            upper, middle, lower = TechnicalIndicators.bollinger_bands(closes_1h, 20, 2)
            bb_position = 0.5
            if not np.isnan(upper[-1]) and not np.isnan(lower[-1]):
                bb_width = upper[-1] - lower[-1]
                if bb_width > 0:
                    bb_position = (current_price - lower[-1]) / bb_width

            # 波动率
            volatility = calculate_volatility(closes_1h, 20)

            # 成交量分析
            avg_volume = np.mean(volumes_1h[-20:])
            volume_ratio = volumes_1h[-1] / avg_volume if avg_volume > 0 else 1.0

            # 趋势强度 (ADX)
            adx_values = TechnicalIndicators.adx(highs_1h, lows_1h, closes_1h, 14)
            adx = adx_values[-1] if adx_values else 0

            # 趋势判断
            trend_1h = 'UP' if ema_fast > ema_slow else 'DOWN'
            trend_4h = 'UP' if closes_4h[-1] > TechnicalIndicators.ema(closes_4h, 21)[-1] else 'DOWN'
            overall_trend = 'UP' if current_price > ema_trend else 'DOWN'

            return {
                'symbol': symbol,
                'price': current_price,
                'momentum_short': momentum_short,
                'momentum_medium': momentum_medium,
                'momentum_long': momentum_long,
                'momentum_score': momentum_score,
                'rsi_1h': rsi_1h,
                'rsi_15m': rsi_15m,
                'rsi_4h': rsi_4h,
                'ema_fast': ema_fast,
                'ema_slow': ema_slow,
                'ema_trend': ema_trend,
                'macd_signal': macd_signal,
                'macd_dif': dif[-1] if dif else 0,
                'macd_dea': dea[-1] if dea else 0,
                'bb_position': bb_position,
                'bb_upper': upper[-1] if not np.isnan(upper[-1]) else current_price * 1.05,
                'bb_lower': lower[-1] if not np.isnan(lower[-1]) else current_price * 0.95,
                'volatility': volatility,
                'volume_ratio': volume_ratio,
                'adx': adx,
                'trend_1h': trend_1h,
                'trend_4h': trend_4h,
                'overall_trend': overall_trend,
            }

        except Exception as e:
            print(f"  ⚠️ 获取 {symbol} 数据失败: {e}")
            return None

    def calculate_coin_score(self, data: Dict) -> float:
        """计算币种综合得分（用于选币和轮动）"""
        score = 0.0

        # 1. 动量得分 (40%)
        momentum_score = data['momentum_score']
        score += momentum_score * 4.0

        # 2. RSI得分 (20%) - RSI较低但在上升
        rsi = data['rsi_1h']
        if rsi < RSI_STRONG_BUY:
            rsi_score = 20  # 强超卖
        elif rsi < RSI_BUY_THRESHOLD:
            rsi_score = 15  # 超卖
        elif rsi > RSI_SELL_THRESHOLD:
            rsi_score = -10  # 超买
        else:
            rsi_score = 5  # 中性偏好
        score += rsi_score

        # 3. MACD得分 (15%)
        macd_score = data['macd_signal'] * 10
        score += macd_score

        # 4. 趋势得分 (15%)
        trend_score = 0
        if data['trend_1h'] == 'UP':
            trend_score += 5
        if data['trend_4h'] == 'UP':
            trend_score += 5
        if data['overall_trend'] == 'UP':
            trend_score += 5
        score += trend_score

        # 5. 成交量得分 (10%)
        volume_ratio = data['volume_ratio']
        if volume_ratio > 2.0:
            volume_score = 10  # 成交量暴增
        elif volume_ratio > 1.5:
            volume_score = 7
        elif volume_ratio > 1.0:
            volume_score = 3
        else:
            volume_score = 0
        score += volume_score

        return score

    def calculate_position_size(self, data: Dict, available_usdt: float,
                                total_value: float, current_positions: int) -> float:
        """计算仓位大小（激进版）"""
        # 基础仓位
        base_size = total_value * BASE_POSITION_PCT

        # 信号强度调整
        coin_score = self.calculate_coin_score(data)

        if coin_score > 30:
            # 强信号，使用最大仓位
            signal_multiplier = MAX_SINGLE_POSITION_PCT / BASE_POSITION_PCT
        elif coin_score > 20:
            signal_multiplier = 1.3
        elif coin_score > 10:
            signal_multiplier = 1.0
        else:
            signal_multiplier = 0.7

        # 波动率调整（高波动适度减仓）
        volatility = data['volatility']
        if volatility > 5.0:
            vol_multiplier = 0.7
        elif volatility > 3.0:
            vol_multiplier = 0.85
        elif volatility < 1.5:
            vol_multiplier = 1.2  # 低波动可以加仓
        else:
            vol_multiplier = 1.0

        # 趋势确认调整
        trend_multiplier = 1.0
        if data['trend_1h'] == 'UP' and data['trend_4h'] == 'UP':
            trend_multiplier = 1.2  # 双趋势确认
        elif data['trend_1h'] == 'DOWN' and data['trend_4h'] == 'DOWN':
            trend_multiplier = 0.5  # 双下跌趋势

        # ADX趋势强度调整
        adx = data['adx']
        if adx > 30:
            adx_multiplier = 1.2  # 强趋势
        elif adx > 20:
            adx_multiplier = 1.0
        else:
            adx_multiplier = 0.8  # 弱趋势

        # 计算最终仓位
        adjusted_size = base_size * signal_multiplier * vol_multiplier * trend_multiplier * adx_multiplier

        # 限制单仓不超过最大限制
        max_single = total_value * MAX_SINGLE_POSITION_PCT
        adjusted_size = min(adjusted_size, max_single)

        # 限制不超过可用余额
        adjusted_size = min(adjusted_size, available_usdt * 0.95)

        # 确保不低于最小交易额
        if adjusted_size < MIN_TRADE_USDT:
            return 0.0

        return adjusted_size

    def should_buy(self, data: Dict, current_positions: int) -> Tuple[bool, str, float]:
        """判断是否买入"""
        reasons = []
        score = self.calculate_coin_score(data)

        # 条件1: 综合得分足够高
        if score < 10:
            return False, "综合得分不足", 0

        # 条件2: 至少一个时间框架趋势向上
        if data['trend_1h'] == 'DOWN' and data['trend_4h'] == 'DOWN':
            if score < 25:  # 除非得分非常高
                return False, "双下跌趋势", 0

        # 条件3: RSI不能太高（避免追高）
        if data['rsi_1h'] > 75:
            return False, "RSI过高，避免追高", 0

        # 条件4: 动量为正
        if data['momentum_short'] < -1:
            return False, "短期动量为负", 0

        # 构建买入理由
        reasons.append(f"Score={score:.1f}")
        reasons.append(f"Mom={data['momentum_score']:.2f}%")
        reasons.append(f"RSI={data['rsi_1h']:.1f}")

        if data['macd_signal'] > 0:
            reasons.append("MACD+")
        if data['trend_1h'] == 'UP':
            reasons.append("Trend1H↑")
        if data['trend_4h'] == 'UP':
            reasons.append("Trend4H↑")
        if data['volume_ratio'] > 1.5:
            reasons.append(f"Vol×{data['volume_ratio']:.1f}")

        return True, ", ".join(reasons), score

    def should_sell(self, data: Dict, position: Dict) -> Tuple[bool, str]:
        """判断是否卖出"""
        pnl_pct = position['pnl_percent']
        symbol = position['symbol']
        entry_price = position.get('avg_price', data['price'])
        current_price = data['price']

        # 更新持仓最高价
        if symbol not in self.position_high_prices:
            self.position_high_prices[symbol] = current_price
        else:
            if current_price > self.position_high_prices[symbol]:
                self.position_high_prices[symbol] = current_price

        high_price = self.position_high_prices[symbol]

        # 从最高价回撤
        if high_price > 0:
            drawdown_from_high = ((high_price - current_price) / high_price) * 100
        else:
            drawdown_from_high = 0

        # 1. 硬止损
        if pnl_pct <= -HARD_STOP_LOSS_PCT:
            return True, f"HARD_STOP_LOSS (亏损 {abs(pnl_pct):.2f}% > {HARD_STOP_LOSS_PCT}%)"

        # 2. 跟踪止盈（只有盈利时才启用）
        if pnl_pct > MIN_TAKE_PROFIT_PCT:
            if drawdown_from_high > TRAILING_STOP_PCT:
                return True, f"TRAILING_STOP (从高点回撤 {drawdown_from_high:.2f}%, 锁定利润 {pnl_pct:.2f}%)"

        # 3. 激进止盈
        if pnl_pct >= AGGRESSIVE_TAKE_PROFIT_PCT:
            return True, f"AGGRESSIVE_TAKE_PROFIT (盈利 {pnl_pct:.2f}% >= {AGGRESSIVE_TAKE_PROFIT_PCT}%)"

        # 4. RSI强超买卖出
        if data['rsi_1h'] >= 80 and pnl_pct > 0:
            return True, f"RSI_OVERBOUGHT (RSI={data['rsi_1h']:.1f}, 盈利={pnl_pct:.2f}%)"

        # 5. MACD死叉且盈利时卖出
        if data['macd_signal'] == -1 and pnl_pct > 1:
            return True, f"MACD_DEATH_CROSS (盈利={pnl_pct:.2f}%)"

        # 6. 动量反转（短期动量大幅转负）
        if data['momentum_short'] < -3 and pnl_pct > 0:
            return True, f"MOMENTUM_REVERSAL (动量={data['momentum_short']:.2f}%)"

        return False, ""

    def check_rotation(self, current_positions: List[Dict], market_data: Dict[str, Dict]) -> Optional[Dict]:
        """检查是否需要轮动持仓"""
        if not current_positions:
            return None

        # 检查轮动间隔
        now = datetime.now()
        if self.last_rotation_time:
            hours_since_rotation = (now - self.last_rotation_time).total_seconds() / 3600
            if hours_since_rotation < ROTATION_INTERVAL_HOURS:
                return None

        # 计算当前持仓得分
        current_scores = {}
        for pos in current_positions:
            symbol = pos['symbol']
            if symbol in market_data:
                current_scores[symbol] = self.calculate_coin_score(market_data[symbol])

        if not current_scores:
            return None

        # 找到得分最低的持仓
        worst_symbol = min(current_scores, key=current_scores.get)
        worst_score = current_scores[worst_symbol]

        # 计算所有币种得分
        all_scores = {}
        for symbol, data in market_data.items():
            all_scores[symbol] = self.calculate_coin_score(data)

        # 找到未持有的最高分币种
        held_currencies = [p['currency'] for p in current_positions]
        best_new_symbol = None
        best_new_score = 0

        for symbol, score in all_scores.items():
            currency = symbol.split('/')[0]
            if currency not in held_currencies and score > best_new_score:
                best_new_symbol = symbol
                best_new_score = score

        # 如果有更好的选择，考虑轮动
        if best_new_symbol and best_new_score > worst_score + MIN_ROTATION_IMPROVEMENT:
            return {
                'sell_symbol': worst_symbol,
                'sell_score': worst_score,
                'buy_symbol': best_new_symbol,
                'buy_score': best_new_score,
                'improvement': best_new_score - worst_score,
            }

        return None

    def check_risk_limits(self) -> Tuple[bool, str]:
        """检查风险限制"""
        # 加载权益历史
        if not os.path.exists(EQUITY_FILE):
            return True, ""

        try:
            with open(EQUITY_FILE, 'r') as f:
                history = json.load(f)
        except:
            return True, ""

        if len(history) < 2:
            return True, ""

        values = [h['total_value'] for h in history]
        current_value = values[-1]

        # 检查最大回撤
        peak_value = max(values)
        if peak_value > 0:
            drawdown = ((peak_value - current_value) / peak_value) * 100
            if drawdown > MAX_DRAWDOWN_PCT:
                return False, f"最大回撤触发 ({drawdown:.2f}% > {MAX_DRAWDOWN_PCT}%)"

        # 检查每日亏损
        today = datetime.now().date()
        if self.daily_start_date != today:
            self.daily_start_date = today
            self.daily_starting_value = current_value

        if self.daily_starting_value and self.daily_starting_value > 0:
            daily_pnl = ((current_value - self.daily_starting_value) / self.daily_starting_value) * 100
            if daily_pnl < -DAILY_LOSS_LIMIT_PCT:
                return False, f"每日亏损限制触发 ({daily_pnl:.2f}% < -{DAILY_LOSS_LIMIT_PCT}%)"

        return True, ""

    def save_equity_snapshot(self, total_value: float):
        """保存权益快照"""
        os.makedirs('data', exist_ok=True)

        history = []
        if os.path.exists(EQUITY_FILE):
            try:
                with open(EQUITY_FILE, 'r') as f:
                    history = json.load(f)
            except:
                history = []

        snapshot = {
            'timestamp': datetime.now().isoformat(),
            'total_value': total_value,
            'mode': self.client.get_mode_str(),
        }

        history.append(snapshot)
        history = history[-2000:]  # 保留更多历史

        with open(EQUITY_FILE, 'w') as f:
            json.dump(history, f, indent=2)

    def execute_buy(self, symbol: str, usdt_amount: float) -> Optional[Dict]:
        """执行买入"""
        min_order_usdt = self.client.get_min_order_usdt(symbol)
        if usdt_amount < min_order_usdt:
            print(f"  ⚠️ 金额 ${usdt_amount:.2f} < 最小订单 ${min_order_usdt:.2f}")
            return None

        try:
            print(f"  📈 买入 {symbol}, 金额: ${usdt_amount:.2f}")
            order = self.client.create_market_buy_usdt(symbol, usdt_amount)

            # 记录入场价格
            self.position_entry_prices[symbol] = order.get('average', 0)
            self.position_high_prices[symbol] = order.get('average', 0)

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

            # 清除记录
            if symbol in self.position_entry_prices:
                del self.position_entry_prices[symbol]
            if symbol in self.position_high_prices:
                del self.position_high_prices[symbol]

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
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 激进动量策略检查")
        print(f"模式: {self.client.get_mode_str()}")
        print("=" * 70)

        result = {
            'timestamp': datetime.now().isoformat(),
            'actions': [],
            'analysis': [],
        }

        # 1. 风险检查
        can_trade, risk_msg = self.check_risk_limits()
        if not can_trade:
            print(f"\n🚨 风险熔断: {risk_msg}")
            log_action('RISK_HALT', {'reason': risk_msg})
            return result

        # 2. 获取所有币种的市场数据
        print("\n📊 市场分析:")
        market_data = {}
        for symbol in self.client.whitelist:
            data = self.get_market_data(symbol)
            if data:
                market_data[symbol] = data
                score = self.calculate_coin_score(data)
                trend = f"{data['trend_1h']}/{data['trend_4h']}"
                print(f"  {symbol}: Score={score:>6.1f} | RSI={data['rsi_1h']:>5.1f} | "
                      f"Mom={data['momentum_score']:>+6.2f}% | Trend={trend}")
                result['analysis'].append({**data, 'score': score})

        # 按得分排序
        sorted_coins = sorted(market_data.items(), key=lambda x: self.calculate_coin_score(x[1]), reverse=True)
        print(f"\n🏆 币种排名: {' > '.join([s[0].split('/')[0] for s in sorted_coins])}")

        # 3. 检查现有持仓
        positions = self.client.get_all_positions()
        sold_symbols = set()

        if positions:
            print(f"\n💼 检查持仓 ({len(positions)}):")
            for pos in positions:
                symbol = pos['symbol']
                score = self.calculate_coin_score(market_data[symbol]) if symbol in market_data else 0
                print(f"  {symbol}: {pos['amount']:.8f} @ ${pos['current_price']:,.2f} | "
                      f"盈亏: {pos['pnl_percent']:+.2f}% | Score: {score:.1f}")

                if symbol in market_data:
                    should_sell, reason = self.should_sell(market_data[symbol], pos)
                    if should_sell:
                        order = self.execute_sell(symbol, pos['amount'], reason)
                        if order and not order.get('dust'):
                            result['actions'].append({'type': 'SELL', 'symbol': symbol, 'reason': reason})
                            sold_symbols.add(symbol)

        # 4. 检查轮动机会
        remaining_positions = [p for p in positions if p['symbol'] not in sold_symbols]
        if remaining_positions and len(remaining_positions) > 0:
            rotation = self.check_rotation(remaining_positions, market_data)
            if rotation:
                print(f"\n🔄 轮动建议:")
                print(f"   卖出 {rotation['sell_symbol']} (Score: {rotation['sell_score']:.1f})")
                print(f"   买入 {rotation['buy_symbol']} (Score: {rotation['buy_score']:.1f})")
                print(f"   提升: +{rotation['improvement']:.1f}")

                # 执行轮动
                sell_pos = next((p for p in remaining_positions if p['symbol'] == rotation['sell_symbol']), None)
                if sell_pos:
                    sell_order = self.execute_sell(rotation['sell_symbol'], sell_pos['amount'],
                                                   f"ROTATION (Score: {rotation['sell_score']:.1f} -> {rotation['buy_score']:.1f})")
                    if sell_order and not sell_order.get('dust'):
                        result['actions'].append({'type': 'ROTATION_SELL', 'symbol': rotation['sell_symbol']})
                        sold_symbols.add(rotation['sell_symbol'])

                        # 使用卖出金额买入新币种
                        usdt_amount = sell_pos['current_value'] * 0.98  # 留些余量
                        buy_order = self.execute_buy(rotation['buy_symbol'], usdt_amount)
                        if buy_order:
                            result['actions'].append({'type': 'ROTATION_BUY', 'symbol': rotation['buy_symbol']})

                        self.last_rotation_time = datetime.now()

        # 5. 检查买入机会
        print("\n🔍 检查买入机会:")
        balance = self.client.get_balance()
        tickers = self.client.get_all_tickers()
        total_value = self.client.calculate_total_value_usdt(balance, tickers)
        usdt_free = self.client.get_usdt_balance()

        current_positions = len([p for p in positions if p['symbol'] not in sold_symbols])

        # 计算当前仓位比例
        position_value = sum([p['current_value'] for p in positions if p['symbol'] not in sold_symbols])
        position_ratio = position_value / total_value if total_value > 0 else 0

        print(f"  当前仓位比例: {position_ratio*100:.1f}% / {MAX_TOTAL_POSITION_PCT*100:.0f}%")

        if position_ratio >= MAX_TOTAL_POSITION_PCT:
            print(f"  ⚠️ 已达到最大总仓位限制")
        elif usdt_free < MIN_TRADE_USDT:
            print(f"  ⚠️ USDT余额不足 (${usdt_free:.2f} < ${MIN_TRADE_USDT:.2f})")
        else:
            # 按得分排序，选择最佳币种
            held_currencies = [p['currency'] for p in positions if p['symbol'] not in sold_symbols]
            buy_candidates = []

            for symbol, data in sorted_coins:
                currency = symbol.split('/')[0]
                if currency in held_currencies:
                    continue

                should_buy, reason, score = self.should_buy(data, current_positions)
                if should_buy:
                    buy_candidates.append((symbol, data, reason, score))

            if buy_candidates:
                # 选择得分最高的
                symbol, data, reason, score = buy_candidates[0]
                position_size = self.calculate_position_size(data, usdt_free, total_value, current_positions)

                if position_size >= MIN_TRADE_USDT:
                    print(f"  📈 买入候选: {symbol}")
                    print(f"     理由: {reason}")
                    print(f"     建议仓位: ${position_size:.2f} ({position_size/total_value*100:.1f}%)")

                    order = self.execute_buy(symbol, position_size)
                    if order:
                        result['actions'].append({'type': 'BUY', 'symbol': symbol, 'reason': reason})
                else:
                    print(f"  ℹ️ {symbol} 计算仓位过小，跳过")
            else:
                print("  无符合条件的买入信号")

        # 6. 总结
        if not result['actions']:
            log_action('HOLD', {'reason': 'No trading signals'})

        # 保存权益快照
        self.save_equity_snapshot(total_value)

        # 显示账户状态
        print(f"\n💰 账户状态:")
        print(f"   总资产: ${total_value:.2f}")
        print(f"   USDT可用: ${usdt_free:.2f}")
        print(f"   仓位价值: ${position_value:.2f} ({position_ratio*100:.1f}%)")

        # 计算收益
        if os.path.exists(EQUITY_FILE):
            try:
                with open(EQUITY_FILE, 'r') as f:
                    history = json.load(f)
                if len(history) > 1:
                    initial_value = history[0]['total_value']
                    total_return = ((total_value - initial_value) / initial_value) * 100
                    print(f"   累计收益: {total_return:+.2f}%")
            except:
                pass

        print("=" * 70)

        return result


def get_strategy_status() -> Dict:
    """获取策略状态（给Dashboard用）"""
    client = BinanceClient()
    strategy = AggressiveMomentumStrategy(client)

    # 获取市场数据
    analysis = []
    signals = []
    for symbol in client.whitelist:
        data = strategy.get_market_data(symbol)
        if data:
            score = strategy.calculate_coin_score(data)
            analysis.append({**data, 'score': score})

            signal = None
            if score > 20:
                signal = 'STRONG_BUY'
            elif score > 10:
                signal = 'BUY'
            elif score < -10:
                signal = 'SELL'

            signals.append({
                'symbol': symbol,
                'score': score,
                'rsi': data['rsi_1h'],
                'momentum': data['momentum_score'],
                'price': data['price'],
                'signal': signal,
            })

    positions = client.get_all_positions()
    balance = client.get_balance()
    tickers = client.get_all_tickers()
    total_value = client.calculate_total_value_usdt(balance, tickers)
    logs = get_logs(30)

    return {
        'mode': client.get_mode_str(),
        'is_live': client.is_live,
        'total_value': total_value,
        'usdt_free': client.get_usdt_balance(),
        'positions': positions,
        'signals': signals,
        'analysis': analysis,
        'tickers': tickers,
        'recent_logs': logs,
        'config': {
            'max_single_position_pct': MAX_SINGLE_POSITION_PCT * 100,
            'max_total_position_pct': MAX_TOTAL_POSITION_PCT * 100,
            'hard_stop_loss_pct': HARD_STOP_LOSS_PCT,
            'trailing_stop_pct': TRAILING_STOP_PCT,
            'aggressive_take_profit_pct': AGGRESSIVE_TAKE_PROFIT_PCT,
            'daily_loss_limit_pct': DAILY_LOSS_LIMIT_PCT,
            'max_drawdown_pct': MAX_DRAWDOWN_PCT,
        }
    }


# 运行入口
if __name__ == '__main__':
    strategy = AggressiveMomentumStrategy()
    strategy.run_once()
