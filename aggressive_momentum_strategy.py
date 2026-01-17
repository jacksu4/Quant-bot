"""
Aggressive Momentum Strategy v2.1 / 激进动量策略 v2.1
=====================================================

Target: 100% return in 2 months (high risk, high reward)
目标：2个月内实现100%收益（高风险高回报）

v2.1 Improvements / v2.1 优化 (2026-01-17):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Pullback Entry - Wait for dips in uptrends instead of chasing
   回调入场 - 在上升趋势中等待回调，而非追涨
2. RSI Divergence Detection - Spot reversals early
   RSI背离检测 - 提前发现反转信号
3. Partial Profit Taking - Scale out at 3%, 5%, 8%
   分批止盈 - 在3%、5%、8%时分批获利了结
4. OBV Confirmation - Validate price moves with volume
   OBV确认 - 用量价验证价格走势
5. Reduced Position Size - 30% max single (safer for small accounts)
   降低仓位 - 单仓最高30%（小账户更安全）
6. Time-Based Exit - Close stale positions after 48h without profit
   时间止损 - 48小时无盈利则平仓
7. Correlation Filter - Avoid highly correlated positions
   相关性过滤 - 避免高度相关的持仓

v2.0 Features (retained):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Market Regime Filter / 市场状态过滤
- ATR-Based Dynamic Stops / ATR动态止损
- Momentum Acceleration / 动量加速度
- Volume Breakout Detection / 成交量突破检测
- Volatility-Adjusted Sizing / 波动率调整仓位

Risk Controls / 风险控制:
- Market regime filter: Reduce exposure in bear markets
- ATR-based stops: 1.5-2x ATR for stop loss
- Max single position: 30% (reduced from 40%)
- Max total exposure: 65% (reduced from 70%)
- Daily loss limit: 5%
- Max drawdown: 12%

⚠️ WARNING: This is a high-risk strategy. Only use with capital you can afford to lose.
⚠️ 警告：此策略风险极高，仅使用你能承受损失的资金。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import json
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from exchange import BinanceClient
from indicators import TechnicalIndicators, calculate_correlation

# ============================================================================
# STRATEGY PARAMETERS v2.1 / 策略参数配置 v2.1
# ============================================================================

# --- Momentum Parameters / 动量参数 ---
MOMENTUM_LOOKBACK_SHORT = 6    # Short-term momentum (hours)
MOMENTUM_LOOKBACK_MEDIUM = 24  # Medium-term momentum (hours)
MOMENTUM_LOOKBACK_LONG = 72    # Long-term momentum (hours)
MOMENTUM_THRESHOLD = 0.3       # Minimum momentum to consider (%)
MOMENTUM_ACCELERATION_WEIGHT = 0.3  # Weight for momentum acceleration in scoring

# --- RSI Parameters / RSI参数 ---
RSI_PERIOD = 14
RSI_BUY_THRESHOLD = 45         # Buy threshold in uptrend
RSI_SELL_THRESHOLD = 70
RSI_STRONG_BUY = 35            # Strong buy when RSI is recovering from oversold
RSI_OVERSOLD = 30              # True oversold level
RSI_PULLBACK_ZONE = (35, 50)   # v2.1: Ideal pullback entry zone

# --- EMA Parameters / EMA参数 ---
EMA_FAST = 8
EMA_SLOW = 21
EMA_TREND = 50

# --- ATR Parameters / ATR参数 ---
ATR_PERIOD = 14
ATR_STOP_MULTIPLIER = 2.0      # Stop loss at 2x ATR
ATR_PROFIT_MULTIPLIER = 3.0    # Take profit at 3x ATR (1.5:1 risk/reward)

# --- Position Sizing v2.1 / 仓位管理 v2.1 ---
MAX_SINGLE_POSITION_PCT = 0.30   # v2.1: Reduced from 40% - safer for small accounts
MAX_TOTAL_POSITION_PCT = 0.65    # v2.1: Reduced from 70%
MIN_TRADE_USDT = 6.0
BASE_POSITION_PCT = 0.20         # v2.1: Reduced base position to 20%
VOLATILITY_TARGET = 2.0          # Target 2% daily volatility per position

# --- Stop Loss & Take Profit v2.1 / 止损止盈 v2.1 ---
HARD_STOP_LOSS_PCT = 3.5         # v2.1: Tighter stop loss
TRAILING_STOP_ATR_MULT = 1.5     # Trailing stop at 1.5x ATR (dynamic)
MIN_TAKE_PROFIT_PCT = 2.0        # v2.1: Earlier trailing activation

# v2.1: Partial profit taking levels / 分批止盈水平
PARTIAL_PROFIT_LEVELS = [
    (3.0, 0.30),   # At 3% profit, sell 30%
    (5.0, 0.35),   # At 5% profit, sell 35% of remaining
    (8.0, 0.50),   # At 8% profit, sell 50% of remaining
]
AGGRESSIVE_TAKE_PROFIT_PCT = 12.0  # v2.1: Full exit at 12% (remaining position)

# --- Risk Management v2.1 / 风控参数 v2.1 ---
DAILY_LOSS_LIMIT_PCT = 5.0
MAX_DRAWDOWN_PCT = 12.0          # Tighter drawdown limit

# --- Market Regime / 市场状态 ---
REGIME_BULL_THRESHOLD = 0.5      # BTC momentum > 0.5% = bullish
REGIME_BEAR_THRESHOLD = -0.5     # BTC momentum < -0.5% = bearish
BEAR_MARKET_POSITION_MULT = 0.5  # Reduce positions by 50% in bear market

# --- Volume Parameters / 成交量参数 ---
VOLUME_SURGE_THRESHOLD = 2.0     # Volume 2x average = surge
VOLUME_BREAKOUT_BONUS = 10       # Bonus score for volume breakout

# --- Rotation Parameters / 轮动参数 ---
ROTATION_INTERVAL_HOURS = 6      # Less frequent rotation
MIN_ROTATION_IMPROVEMENT = 3.0   # Higher threshold for rotation

# --- v2.1: Time-Based Exit / 时间止损 ---
STALE_POSITION_HOURS = 48        # Close positions without profit after 48h
STALE_POSITION_MIN_LOSS = -1.0   # Only close if loss is > -1%

# --- v2.1: Correlation Filter / 相关性过滤 ---
MAX_CORRELATION = 0.85           # Avoid positions with correlation > 85%

# --- v2.1: Pullback Entry / 回调入场 ---
PULLBACK_ENABLED = True          # Enable pullback entry logic
PULLBACK_RSI_DIP = 5             # RSI must dip by at least 5 points from recent high

# --- Data Files / 数据文件 ---
LOG_FILE = 'data/aggressive_strategy_log.json'
EQUITY_FILE = 'data/aggressive_equity_history.json'


def calculate_momentum(closes: List[float], period: int) -> float:
    """Calculate momentum (percentage change)"""
    if len(closes) < period + 1:
        return 0.0
    return ((closes[-1] - closes[-period]) / closes[-period]) * 100


def calculate_momentum_acceleration(closes: List[float], period: int) -> float:
    """Calculate momentum acceleration (rate of change of momentum)"""
    if len(closes) < period * 2 + 1:
        return 0.0
    current_mom = calculate_momentum(closes, period)
    prev_mom = calculate_momentum(closes[:-period], period)
    return current_mom - prev_mom


def calculate_volatility(closes: List[float], period: int = 20) -> float:
    """Calculate volatility (standard deviation of returns)"""
    if len(closes) < period:
        return 0.0
    returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
    if len(returns) < period:
        return 0.0
    return np.std(returns[-period:]) * 100


def calculate_atr(highs: List[float], lows: List[float], closes: List[float],
                  period: int = 14) -> float:
    """Calculate Average True Range"""
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


def detect_volume_breakout(volumes: List[float], period: int = 20) -> Tuple[bool, float]:
    """Detect volume breakout (volume surge)"""
    if len(volumes) < period + 1:
        return False, 1.0
    avg_volume = np.mean(volumes[-period-1:-1])
    if avg_volume <= 0:
        return False, 1.0
    volume_ratio = volumes[-1] / avg_volume
    return volume_ratio >= VOLUME_SURGE_THRESHOLD, volume_ratio


# ============================================================================
# v2.1 NEW HELPER FUNCTIONS / v2.1 新增辅助函数
# ============================================================================

def detect_rsi_divergence(closes: List[float], rsi_values: List[float],
                          lookback: int = 10) -> Tuple[str, float]:
    """
    Detect RSI divergence (bullish or bearish)
    检测RSI背离（看涨或看跌）

    Returns:
        (divergence_type, strength)
        divergence_type: 'BULLISH', 'BEARISH', or 'NONE'
        strength: divergence strength (0-1)
    """
    if len(closes) < lookback + 2 or len(rsi_values) < lookback + 2:
        return 'NONE', 0.0

    # Find recent price lows/highs
    recent_closes = closes[-lookback:]
    recent_rsi = rsi_values[-lookback:]

    # Find local minima and maxima
    price_low_idx = np.argmin(recent_closes)
    price_high_idx = np.argmax(recent_closes)

    # Check for bullish divergence: price making lower lows, RSI making higher lows
    if price_low_idx > lookback // 2:  # Recent low
        # Compare with earlier low
        earlier_closes = closes[-(lookback*2):-lookback]
        earlier_rsi = rsi_values[-(lookback*2):-lookback]

        if len(earlier_closes) >= lookback // 2:
            earlier_low = min(earlier_closes)
            current_low = min(recent_closes)

            earlier_rsi_at_low = min(earlier_rsi)
            current_rsi_at_low = min(recent_rsi)

            # Bullish: price lower, RSI higher
            if current_low < earlier_low and current_rsi_at_low > earlier_rsi_at_low:
                price_diff = (earlier_low - current_low) / earlier_low
                rsi_diff = current_rsi_at_low - earlier_rsi_at_low
                strength = min(1.0, (price_diff * 100 + rsi_diff) / 20)
                return 'BULLISH', strength

    # Check for bearish divergence: price making higher highs, RSI making lower highs
    if price_high_idx > lookback // 2:  # Recent high
        earlier_closes = closes[-(lookback*2):-lookback]
        earlier_rsi = rsi_values[-(lookback*2):-lookback]

        if len(earlier_closes) >= lookback // 2:
            earlier_high = max(earlier_closes)
            current_high = max(recent_closes)

            earlier_rsi_at_high = max(earlier_rsi)
            current_rsi_at_high = max(recent_rsi)

            # Bearish: price higher, RSI lower
            if current_high > earlier_high and current_rsi_at_high < earlier_rsi_at_high:
                price_diff = (current_high - earlier_high) / earlier_high
                rsi_diff = earlier_rsi_at_high - current_rsi_at_high
                strength = min(1.0, (price_diff * 100 + rsi_diff) / 20)
                return 'BEARISH', strength

    return 'NONE', 0.0


def calculate_obv_trend(closes: List[float], volumes: List[float],
                        period: int = 14) -> Tuple[str, float]:
    """
    Calculate OBV (On-Balance Volume) trend
    计算OBV能量潮趋势

    Returns:
        (trend, strength)
        trend: 'UP', 'DOWN', or 'NEUTRAL'
        strength: trend strength (0-1)
    """
    if len(closes) < period + 1 or len(volumes) < period + 1:
        return 'NEUTRAL', 0.0

    # Calculate OBV
    obv = TechnicalIndicators.obv(closes, volumes)

    if len(obv) < period:
        return 'NEUTRAL', 0.0

    # Calculate OBV EMA
    obv_ema = TechnicalIndicators.ema(obv, period)

    # Check trend
    recent_obv = obv[-1]
    recent_obv_ema = obv_ema[-1]

    # Calculate slope
    obv_slope = (obv[-1] - obv[-min(5, len(obv))]) / max(abs(obv[-min(5, len(obv))]), 1)

    if recent_obv > recent_obv_ema and obv_slope > 0:
        strength = min(1.0, abs(obv_slope) * 10)
        return 'UP', strength
    elif recent_obv < recent_obv_ema and obv_slope < 0:
        strength = min(1.0, abs(obv_slope) * 10)
        return 'DOWN', strength

    return 'NEUTRAL', 0.0


def detect_pullback_entry(rsi_history: List[float], current_rsi: float,
                          trend: str) -> Tuple[bool, str]:
    """
    Detect pullback entry opportunity in an uptrend
    检测上升趋势中的回调入场机会

    Returns:
        (is_pullback_entry, reason)
    """
    if not PULLBACK_ENABLED or trend != 'UP':
        return False, ""

    if len(rsi_history) < 10:
        return False, ""

    # Find recent RSI high
    recent_rsi_high = max(rsi_history[-10:])

    # Check if RSI has dipped from recent high
    rsi_dip = recent_rsi_high - current_rsi

    # Check if current RSI is in the pullback zone
    in_pullback_zone = RSI_PULLBACK_ZONE[0] <= current_rsi <= RSI_PULLBACK_ZONE[1]

    if in_pullback_zone and rsi_dip >= PULLBACK_RSI_DIP:
        return True, f"RSI pullback from {recent_rsi_high:.1f} to {current_rsi:.1f}"

    return False, ""


def check_position_correlation(new_symbol: str, existing_positions: List[Dict],
                               price_data: Dict[str, List[float]]) -> Tuple[bool, float]:
    """
    Check if new position would be too correlated with existing positions
    检查新仓位是否与现有仓位过度相关

    Returns:
        (is_ok, max_correlation)
    """
    if not existing_positions:
        return True, 0.0

    if new_symbol not in price_data:
        return True, 0.0

    new_prices = price_data[new_symbol]
    max_corr = 0.0

    for pos in existing_positions:
        pos_symbol = pos.get('symbol', '')
        if pos_symbol in price_data:
            pos_prices = price_data[pos_symbol]

            # Ensure same length
            min_len = min(len(new_prices), len(pos_prices))
            if min_len >= 20:
                corr = abs(calculate_correlation(new_prices[-min_len:], pos_prices[-min_len:]))
                max_corr = max(max_corr, corr)

    return max_corr <= MAX_CORRELATION, max_corr


def log_action(action: str, details: dict):
    """Log strategy action"""
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
    logs = logs[-2000:]

    with open(LOG_FILE, 'w') as f:
        json.dump(logs, f, indent=2, default=str)

    return log_entry


def get_logs(limit: int = 100) -> list:
    """Get strategy logs"""
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, 'r') as f:
            logs = json.load(f)
        return logs[-limit:]
    except:
        return []


class AggressiveMomentumStrategy:
    """Aggressive Momentum Strategy v2.1 - Optimized for higher win rate and better risk management"""

    def __init__(self, client: BinanceClient = None):
        self.client = client or BinanceClient()
        self.position_entry_prices = {}
        self.position_high_prices = {}
        self.position_atr = {}  # Store ATR at entry for dynamic stops
        self.position_entry_times = {}  # v2.1: Track entry time for time-based exit
        self.position_partial_sells = {}  # v2.1: Track partial profit levels already triggered
        self.last_rotation_time = None
        self.daily_starting_value = None
        self.daily_start_date = None
        self.market_regime = 'NEUTRAL'  # BULL, BEAR, or NEUTRAL
        self.btc_data = None  # Cache BTC data for regime detection
        self.price_history = {}  # v2.1: Cache price history for correlation checks

    def detect_market_regime(self) -> str:
        """Detect overall market regime using BTC as proxy"""
        try:
            ohlcv = self.client.get_ohlcv('BTC/USDT', '4h', limit=50)
            if len(ohlcv) < 30:
                return 'NEUTRAL'

            closes = [c[4] for c in ohlcv]

            # Calculate BTC momentum
            mom_short = calculate_momentum(closes, 6)  # 24h momentum
            mom_medium = calculate_momentum(closes, 18)  # 72h momentum

            # EMA trend
            ema_fast = TechnicalIndicators.ema(closes, 8)[-1]
            ema_slow = TechnicalIndicators.ema(closes, 21)[-1]

            # Combined score
            trend_score = mom_short * 0.5 + mom_medium * 0.3
            if ema_fast > ema_slow:
                trend_score += 1
            else:
                trend_score -= 1

            if trend_score > REGIME_BULL_THRESHOLD:
                self.market_regime = 'BULL'
            elif trend_score < REGIME_BEAR_THRESHOLD:
                self.market_regime = 'BEAR'
            else:
                self.market_regime = 'NEUTRAL'

            return self.market_regime

        except Exception as e:
            print(f"  ⚠️ Market regime detection failed: {e}")
            return 'NEUTRAL'

    def get_market_data(self, symbol: str) -> Optional[Dict]:
        """Get market data and calculate indicators"""
        try:
            # Get 1-hour candles (main analysis)
            ohlcv_1h = self.client.get_ohlcv(symbol, '1h', limit=100)
            if len(ohlcv_1h) < 50:
                return None

            # Get 15-minute candles (entry timing)
            ohlcv_15m = self.client.get_ohlcv(symbol, '15m', limit=50)
            if len(ohlcv_15m) < 20:
                return None

            # Get 4-hour candles (trend confirmation)
            ohlcv_4h = self.client.get_ohlcv(symbol, '4h', limit=50)
            if len(ohlcv_4h) < 20:
                return None

            # Extract 1h data
            closes_1h = [c[4] for c in ohlcv_1h]
            highs_1h = [c[2] for c in ohlcv_1h]
            lows_1h = [c[3] for c in ohlcv_1h]
            volumes_1h = [c[5] for c in ohlcv_1h]

            # Extract 15m data
            closes_15m = [c[4] for c in ohlcv_15m]

            # Extract 4h data
            closes_4h = [c[4] for c in ohlcv_4h]
            highs_4h = [c[2] for c in ohlcv_4h]
            lows_4h = [c[3] for c in ohlcv_4h]

            current_price = closes_1h[-1]

            # Calculate momentum
            momentum_short = calculate_momentum(closes_1h, MOMENTUM_LOOKBACK_SHORT)
            momentum_medium = calculate_momentum(closes_1h, MOMENTUM_LOOKBACK_MEDIUM)
            momentum_long = calculate_momentum(closes_1h, MOMENTUM_LOOKBACK_LONG)

            # NEW: Momentum acceleration
            momentum_accel = calculate_momentum_acceleration(closes_1h, MOMENTUM_LOOKBACK_SHORT)

            # Weighted momentum score (with acceleration bonus)
            momentum_score = (momentum_short * 0.5 + momentum_medium * 0.3 + momentum_long * 0.2)
            if momentum_accel > 0:
                momentum_score += momentum_accel * MOMENTUM_ACCELERATION_WEIGHT

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
                    macd_signal = 1  # Golden cross
                elif dif[-1] < dea[-1] and dif[-2] >= dea[-2]:
                    macd_signal = -1  # Death cross
                elif dif[-1] > dea[-1]:
                    macd_signal = 0.5  # DIF above DEA
                else:
                    macd_signal = -0.5  # DIF below DEA

            # Bollinger Bands
            upper, middle, lower = TechnicalIndicators.bollinger_bands(closes_1h, 20, 2)
            bb_position = 0.5
            if not np.isnan(upper[-1]) and not np.isnan(lower[-1]):
                bb_width = upper[-1] - lower[-1]
                if bb_width > 0:
                    bb_position = (current_price - lower[-1]) / bb_width

            # Volatility
            volatility = calculate_volatility(closes_1h, 20)

            # ATR (NEW - for dynamic stops)
            atr_1h = calculate_atr(highs_1h, lows_1h, closes_1h, ATR_PERIOD)
            atr_4h = calculate_atr(highs_4h, lows_4h, closes_4h, ATR_PERIOD)
            atr_pct = (atr_1h / current_price) * 100 if current_price > 0 else 0

            # Volume analysis (IMPROVED)
            avg_volume = np.mean(volumes_1h[-20:])
            volume_ratio = volumes_1h[-1] / avg_volume if avg_volume > 0 else 1.0
            is_volume_breakout, _ = detect_volume_breakout(volumes_1h)

            # Trend strength (ADX)
            adx_values = TechnicalIndicators.adx(highs_1h, lows_1h, closes_1h, 14)
            adx = adx_values[-1] if adx_values else 0

            # Trend direction
            trend_1h = 'UP' if ema_fast > ema_slow else 'DOWN'
            trend_4h = 'UP' if closes_4h[-1] > TechnicalIndicators.ema(closes_4h, 21)[-1] else 'DOWN'
            overall_trend = 'UP' if current_price > ema_trend else 'DOWN'

            # v2.1: OBV trend analysis
            obv_trend, obv_strength = calculate_obv_trend(closes_1h, volumes_1h)

            # v2.1: RSI divergence detection
            rsi_history = TechnicalIndicators.rsi(closes_1h, RSI_PERIOD)
            divergence_type, divergence_strength = detect_rsi_divergence(closes_1h, rsi_history)

            # v2.1: Pullback detection
            is_pullback, pullback_reason = detect_pullback_entry(rsi_history, rsi_1h, overall_trend)

            # v2.1: Store price history for correlation checks
            self.price_history[symbol] = closes_1h

            return {
                'symbol': symbol,
                'price': current_price,
                'momentum_short': momentum_short,
                'momentum_medium': momentum_medium,
                'momentum_long': momentum_long,
                'momentum_accel': momentum_accel,
                'momentum_score': momentum_score,
                'rsi_1h': rsi_1h,
                'rsi_15m': rsi_15m,
                'rsi_4h': rsi_4h,
                'rsi_history': rsi_history,  # v2.1
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
                'atr': atr_1h,
                'atr_pct': atr_pct,
                'atr_4h': atr_4h,
                'volume_ratio': volume_ratio,
                'is_volume_breakout': is_volume_breakout,
                'adx': adx,
                'trend_1h': trend_1h,
                'trend_4h': trend_4h,
                'overall_trend': overall_trend,
                # v2.1 new fields
                'obv_trend': obv_trend,
                'obv_strength': obv_strength,
                'divergence_type': divergence_type,
                'divergence_strength': divergence_strength,
                'is_pullback': is_pullback,
                'pullback_reason': pullback_reason,
            }

        except Exception as e:
            print(f"  ⚠️ Failed to get {symbol} data: {e}")
            return None

    def calculate_coin_score(self, data: Dict) -> float:
        """Calculate coin score for ranking and selection (v2.1)"""
        score = 0.0

        # 1. Momentum score (30%) - with acceleration bonus
        momentum_score = data['momentum_score']
        score += momentum_score * 3.0

        # Bonus for accelerating momentum
        if data['momentum_accel'] > 0.5:
            score += 5

        # 2. RSI score (20%) - favor recovering oversold
        rsi = data['rsi_1h']
        if RSI_OVERSOLD < rsi < RSI_STRONG_BUY:
            rsi_score = 20  # Recovering from oversold - best
        elif rsi < RSI_BUY_THRESHOLD:
            rsi_score = 15  # Still low
        elif rsi > RSI_SELL_THRESHOLD:
            rsi_score = -10  # Overbought
        else:
            rsi_score = 5  # Neutral

        # Bonus for RSI rising from oversold
        if data['rsi_15m'] > data['rsi_1h'] and rsi < RSI_BUY_THRESHOLD:
            rsi_score += 5
        score += rsi_score

        # 3. MACD score (15%)
        macd_score = data['macd_signal'] * 12
        score += macd_score

        # 4. Trend score (15%)
        trend_score = 0
        if data['trend_1h'] == 'UP':
            trend_score += 5
        if data['trend_4h'] == 'UP':
            trend_score += 5
        if data['overall_trend'] == 'UP':
            trend_score += 5
        score += trend_score

        # 5. Volume score (10%) - with breakout detection
        volume_ratio = data['volume_ratio']
        if data['is_volume_breakout']:
            volume_score = VOLUME_BREAKOUT_BONUS
        elif volume_ratio > 1.5:
            volume_score = 7
        elif volume_ratio > 1.0:
            volume_score = 3
        else:
            volume_score = 0
        score += volume_score

        # 6. ADX bonus (5%) - trend strength
        if data['adx'] > 30:
            score += 5
        elif data['adx'] > 25:
            score += 3
        elif data['adx'] < 15:
            score -= 3  # Weak/ranging market penalty

        # v2.1: OBV confirmation bonus (5%)
        obv_trend = data.get('obv_trend', 'NEUTRAL')
        if obv_trend == 'UP' and data['overall_trend'] == 'UP':
            score += 5  # Price and volume agree - bullish
        elif obv_trend == 'DOWN' and data['overall_trend'] == 'UP':
            score -= 3  # Volume diverging from price - warning

        # v2.1: RSI divergence bonus (5%)
        divergence_type = data.get('divergence_type', 'NONE')
        divergence_strength = data.get('divergence_strength', 0)
        if divergence_type == 'BULLISH':
            score += 5 * divergence_strength  # Up to +5 for strong bullish divergence
        elif divergence_type == 'BEARISH':
            score -= 5 * divergence_strength  # Penalize bearish divergence

        # v2.1: Pullback entry bonus (5%)
        if data.get('is_pullback', False):
            score += 5  # Bonus for pullback entry opportunity

        return score

    def calculate_position_size(self, data: Dict, available_usdt: float,
                                total_value: float, current_positions: int) -> float:
        """Calculate position size with volatility adjustment (v2.0)"""

        # Base position
        base_size = total_value * BASE_POSITION_PCT

        # 1. Signal strength adjustment
        coin_score = self.calculate_coin_score(data)
        if coin_score > 30:
            signal_multiplier = 1.6  # Strong signal
        elif coin_score > 20:
            signal_multiplier = 1.3
        elif coin_score > 10:
            signal_multiplier = 1.0
        else:
            signal_multiplier = 0.7

        # 2. Volatility adjustment (risk parity - NEW)
        # Target: ~2% portfolio volatility per position
        atr_pct = data['atr_pct']
        if atr_pct > 0:
            vol_adjusted_size = (VOLATILITY_TARGET / atr_pct) * base_size
            # Blend signal-based and vol-adjusted sizing
            base_size = (base_size * signal_multiplier * 0.6 + vol_adjusted_size * 0.4)
        else:
            base_size = base_size * signal_multiplier

        # 3. Market regime adjustment (NEW)
        if self.market_regime == 'BEAR':
            base_size *= BEAR_MARKET_POSITION_MULT
        elif self.market_regime == 'NEUTRAL':
            base_size *= 0.8

        # 4. Trend confirmation adjustment
        if data['trend_1h'] == 'UP' and data['trend_4h'] == 'UP':
            base_size *= 1.1  # Dual trend confirmation
        elif data['trend_1h'] == 'DOWN' and data['trend_4h'] == 'DOWN':
            base_size *= 0.5  # Avoid counter-trend

        # 5. Volume breakout bonus
        if data['is_volume_breakout'] and data['momentum_short'] > 0:
            base_size *= 1.15

        # Cap at maximum
        max_single = total_value * MAX_SINGLE_POSITION_PCT
        adjusted_size = min(base_size, max_single)

        # Don't exceed available
        adjusted_size = min(adjusted_size, available_usdt * 0.95)

        # Minimum check
        if adjusted_size < MIN_TRADE_USDT:
            return 0.0

        return adjusted_size

    def should_buy(self, data: Dict, current_positions: int,
                   existing_positions: List[Dict] = None) -> Tuple[bool, str, float]:
        """Determine if should buy (v2.1 with correlation filter and pullback preference)"""
        reasons = []
        score = self.calculate_coin_score(data)
        symbol = data['symbol']

        # Condition 1: Score threshold
        if score < 10:
            return False, "Score too low", 0

        # Condition 2: Market regime check
        if self.market_regime == 'BEAR' and score < 25:
            return False, f"Bear market, need higher score (have {score:.1f})", 0

        # Condition 3: Trend alignment
        if data['trend_1h'] == 'DOWN' and data['trend_4h'] == 'DOWN':
            if score < 25:
                return False, "Double downtrend", 0

        # Condition 4: RSI not overbought
        if data['rsi_1h'] > 75:
            return False, "RSI overbought", 0

        # Condition 5: Positive short-term momentum
        if data['momentum_short'] < -1:
            return False, "Negative momentum", 0

        # Condition 6: ADX check - prefer trending markets
        if data['adx'] < 15 and score < 20:
            return False, "Weak trend (low ADX)", 0

        # v2.1: Correlation filter - avoid highly correlated positions
        if existing_positions:
            corr_ok, max_corr = check_position_correlation(
                symbol, existing_positions, self.price_history
            )
            if not corr_ok:
                return False, f"Too correlated with existing positions ({max_corr:.2f})", 0

        # v2.1: OBV confirmation check
        obv_trend = data.get('obv_trend', 'NEUTRAL')
        if obv_trend == 'DOWN' and data['momentum_short'] < 1:
            return False, "OBV divergence (volume not confirming)", 0

        # v2.1: Bearish divergence warning
        if data.get('divergence_type') == 'BEARISH' and data.get('divergence_strength', 0) > 0.5:
            return False, "Strong bearish RSI divergence detected", 0

        # Build reasons
        reasons.append(f"Score={score:.1f}")
        reasons.append(f"Regime={self.market_regime}")
        reasons.append(f"Mom={data['momentum_score']:.2f}%")
        reasons.append(f"RSI={data['rsi_1h']:.1f}")

        if data['momentum_accel'] > 0:
            reasons.append("Accel+")
        if data['macd_signal'] > 0:
            reasons.append("MACD+")
        if data['trend_1h'] == 'UP':
            reasons.append("Trend1H↑")
        if data['is_volume_breakout']:
            reasons.append("VolBreak!")

        # v2.1: Additional signals
        if obv_trend == 'UP':
            reasons.append("OBV↑")
        if data.get('divergence_type') == 'BULLISH':
            reasons.append("BullDiv!")
        if data.get('is_pullback'):
            reasons.append("Pullback!")

        return True, ", ".join(reasons), score

    def should_sell(self, data: Dict, position: Dict) -> Tuple[bool, str, float]:
        """Determine if should sell (v2.1 with partial profit taking and time-based exit)

        Returns:
            (should_sell, reason, sell_portion)
            sell_portion: 1.0 for full exit, <1.0 for partial exit
        """
        pnl_pct = position['pnl_percent']
        symbol = position['symbol']
        entry_price = position.get('avg_price', data['price'])
        current_price = data['price']

        # Get ATR at entry (or current if not stored)
        entry_atr = self.position_atr.get(symbol, data['atr'])
        atr_pct = (entry_atr / entry_price) * 100 if entry_price > 0 else data['atr_pct']

        # Update high price tracking
        if symbol not in self.position_high_prices:
            self.position_high_prices[symbol] = current_price
        else:
            if current_price > self.position_high_prices[symbol]:
                self.position_high_prices[symbol] = current_price

        high_price = self.position_high_prices[symbol]
        drawdown_from_high = ((high_price - current_price) / high_price) * 100 if high_price > 0 else 0

        # Calculate dynamic stops based on ATR
        dynamic_stop_loss = min(atr_pct * ATR_STOP_MULTIPLIER, HARD_STOP_LOSS_PCT)
        dynamic_trailing = min(atr_pct * TRAILING_STOP_ATR_MULT, 3.0)  # Cap at 3%

        # 1. Hard stop loss (ATR-adjusted) - FULL EXIT
        if pnl_pct <= -dynamic_stop_loss:
            return True, f"STOP_LOSS (ATR-adj: {pnl_pct:.2f}% < -{dynamic_stop_loss:.2f}%)", 1.0

        # v2.1: Time-based exit for stale positions
        entry_time = self.position_entry_times.get(symbol)
        if entry_time:
            hours_held = (datetime.now() - entry_time).total_seconds() / 3600
            if hours_held >= STALE_POSITION_HOURS:
                if pnl_pct <= STALE_POSITION_MIN_LOSS:
                    return True, f"STALE_POSITION ({hours_held:.0f}h, PnL: {pnl_pct:.2f}%)", 1.0

        # v2.1: Partial profit taking - check each level
        partial_sells = self.position_partial_sells.get(symbol, set())
        for level_pct, sell_portion in PARTIAL_PROFIT_LEVELS:
            if pnl_pct >= level_pct and level_pct not in partial_sells:
                # Mark this level as triggered
                if symbol not in self.position_partial_sells:
                    self.position_partial_sells[symbol] = set()
                self.position_partial_sells[symbol].add(level_pct)
                return True, f"PARTIAL_PROFIT ({pnl_pct:.2f}% >= {level_pct}%, selling {sell_portion*100:.0f}%)", sell_portion

        # 2. Trailing stop (ATR-adjusted, only when in profit) - FULL EXIT
        if pnl_pct > MIN_TAKE_PROFIT_PCT:
            if drawdown_from_high > dynamic_trailing:
                return True, f"TRAILING_STOP (from high: -{drawdown_from_high:.2f}%, locked: {pnl_pct:.2f}%)", 1.0

        # 3. Aggressive take profit - FULL EXIT of remaining
        if pnl_pct >= AGGRESSIVE_TAKE_PROFIT_PCT:
            return True, f"TAKE_PROFIT ({pnl_pct:.2f}% >= {AGGRESSIVE_TAKE_PROFIT_PCT}%)", 1.0

        # 4. RSI extreme overbought with profit - FULL EXIT
        if data['rsi_1h'] >= 80 and pnl_pct > 0:
            return True, f"RSI_EXTREME (RSI={data['rsi_1h']:.1f}, profit={pnl_pct:.2f}%)", 1.0

        # 5. MACD death cross with profit
        if data['macd_signal'] == -1 and pnl_pct > 1:
            return True, f"MACD_BEARISH (profit={pnl_pct:.2f}%)", 1.0

        # 6. Strong momentum reversal
        if data['momentum_short'] < -3 and pnl_pct > 0:
            return True, f"MOMENTUM_REVERSAL (mom={data['momentum_short']:.2f}%)", 1.0

        # 7. Market regime shift to bear
        if self.market_regime == 'BEAR' and pnl_pct > 0:
            if data['trend_1h'] == 'DOWN' and data['trend_4h'] == 'DOWN':
                return True, f"REGIME_SHIFT (bear market, locking {pnl_pct:.2f}%)", 1.0

        # v2.1: Bearish divergence warning with profit
        if data.get('divergence_type') == 'BEARISH' and pnl_pct > 2:
            if data.get('divergence_strength', 0) > 0.6:
                return True, f"BEARISH_DIVERGENCE (locking {pnl_pct:.2f}%)", 1.0

        return False, "", 0.0

    def check_rotation(self, current_positions: List[Dict], market_data: Dict[str, Dict]) -> Optional[Dict]:
        """Check if position rotation is needed (v2.0)"""
        if not current_positions:
            return None

        # Check rotation interval
        now = datetime.now()
        if self.last_rotation_time:
            hours_since = (now - self.last_rotation_time).total_seconds() / 3600
            if hours_since < ROTATION_INTERVAL_HOURS:
                return None

        # Calculate current position scores
        current_scores = {}
        for pos in current_positions:
            symbol = pos['symbol']
            if symbol in market_data:
                current_scores[symbol] = self.calculate_coin_score(market_data[symbol])

        if not current_scores:
            return None

        # Find worst position
        worst_symbol = min(current_scores, key=current_scores.get)
        worst_score = current_scores[worst_symbol]

        # Find best alternative
        all_scores = {sym: self.calculate_coin_score(data) for sym, data in market_data.items()}
        held_currencies = [p['currency'] for p in current_positions]

        best_new_symbol = None
        best_new_score = 0

        for symbol, score in all_scores.items():
            currency = symbol.split('/')[0]
            if currency not in held_currencies and score > best_new_score:
                best_new_symbol = symbol
                best_new_score = score

        # Rotation decision (higher threshold in v2.0)
        if best_new_symbol and best_new_score > worst_score + MIN_ROTATION_IMPROVEMENT:
            # Additional check: only rotate if worst is actually underperforming
            worst_pos = next((p for p in current_positions if p['symbol'] == worst_symbol), None)
            if worst_pos and worst_pos.get('pnl_percent', 0) < 1:  # Only rotate if not profitable
                return {
                    'sell_symbol': worst_symbol,
                    'sell_score': worst_score,
                    'buy_symbol': best_new_symbol,
                    'buy_score': best_new_score,
                    'improvement': best_new_score - worst_score,
                }

        return None

    def check_risk_limits(self) -> Tuple[bool, str]:
        """Check risk limits"""
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

        # Max drawdown check
        peak_value = max(values)
        if peak_value > 0:
            drawdown = ((peak_value - current_value) / peak_value) * 100
            if drawdown > MAX_DRAWDOWN_PCT:
                return False, f"Max drawdown ({drawdown:.2f}% > {MAX_DRAWDOWN_PCT}%)"

        # Daily loss check
        today = datetime.now().date()
        if self.daily_start_date != today:
            self.daily_start_date = today
            self.daily_starting_value = current_value

        if self.daily_starting_value and self.daily_starting_value > 0:
            daily_pnl = ((current_value - self.daily_starting_value) / self.daily_starting_value) * 100
            if daily_pnl < -DAILY_LOSS_LIMIT_PCT:
                return False, f"Daily loss limit ({daily_pnl:.2f}% < -{DAILY_LOSS_LIMIT_PCT}%)"

        return True, ""

    def save_equity_snapshot(self, total_value: float):
        """Save equity snapshot"""
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
            'regime': self.market_regime,  # NEW
        }

        history.append(snapshot)
        history = history[-2000:]

        with open(EQUITY_FILE, 'w') as f:
            json.dump(history, f, indent=2)

    def execute_buy(self, symbol: str, usdt_amount: float, data: Dict = None) -> Optional[Dict]:
        """Execute buy order"""
        min_order_usdt = self.client.get_min_order_usdt(symbol)
        if usdt_amount < min_order_usdt:
            print(f"  ⚠️ Amount ${usdt_amount:.2f} < min ${min_order_usdt:.2f}")
            return None

        try:
            print(f"  📈 BUY {symbol}, amount: ${usdt_amount:.2f}")
            order = self.client.create_market_buy_usdt(symbol, usdt_amount)

            # Record entry price and ATR
            entry_price = order.get('average', 0)
            self.position_entry_prices[symbol] = entry_price
            self.position_high_prices[symbol] = entry_price

            # Store ATR for dynamic stops
            if data:
                self.position_atr[symbol] = data.get('atr', 0)

            # v2.1: Record entry time for time-based exit
            self.position_entry_times[symbol] = datetime.now()

            # v2.1: Initialize partial sells tracker
            self.position_partial_sells[symbol] = set()

            log_action('BUY', {
                'symbol': symbol,
                'usdt_amount': usdt_amount,
                'order_id': order.get('id'),
                'filled': order.get('filled'),
                'avg_price': order.get('average'),
                'regime': self.market_regime,
            })

            print(f"  ✅ Buy success! Order: {order.get('id')}")
            return order

        except Exception as e:
            print(f"  ❌ Buy failed: {e}")
            log_action('BUY_FAILED', {'symbol': symbol, 'error': str(e)})
            return None

    def execute_sell(self, symbol: str, amount: float, reason: str,
                     is_full_exit: bool = True) -> Optional[Dict]:
        """Execute sell order (v2.1: supports partial sells)"""
        min_amount = self.client.get_min_order_amount(symbol)

        if amount < min_amount:
            print(f"  ⚠️ Amount {amount:.8f} < min {min_amount:.8f} (dust)")
            log_action('DUST_POSITION', {
                'symbol': symbol,
                'amount': amount,
                'min_required': min_amount,
                'reason': reason,
            })
            return {'dust': True, 'symbol': symbol, 'amount': amount}

        try:
            print(f"  📉 SELL {symbol}, amount: {amount:.8f}, reason: {reason}")
            order = self.client.create_market_sell(symbol, amount)

            # v2.1: Only clear records on full exit
            if is_full_exit:
                if symbol in self.position_entry_prices:
                    del self.position_entry_prices[symbol]
                if symbol in self.position_high_prices:
                    del self.position_high_prices[symbol]
                if symbol in self.position_atr:
                    del self.position_atr[symbol]
                if symbol in self.position_entry_times:
                    del self.position_entry_times[symbol]
                if symbol in self.position_partial_sells:
                    del self.position_partial_sells[symbol]

            log_action('SELL', {
                'symbol': symbol,
                'amount': amount,
                'order_id': order.get('id'),
                'filled': order.get('filled'),
                'avg_price': order.get('average'),
                'reason': reason,
                'is_partial': not is_full_exit,
            })

            print(f"  ✅ Sell success! Order: {order.get('id')}")
            return order

        except Exception as e:
            print(f"  ❌ Sell failed: {e}")
            log_action('SELL_FAILED', {'symbol': symbol, 'error': str(e)})
            return None

    def run_once(self) -> Dict:
        """Execute strategy once (v2.1)"""
        print("\n" + "=" * 70)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Aggressive Momentum Strategy v2.1")
        print(f"Mode: {self.client.get_mode_str()}")
        print("=" * 70)

        result = {
            'timestamp': datetime.now().isoformat(),
            'actions': [],
            'analysis': [],
        }

        # 1. Risk check
        can_trade, risk_msg = self.check_risk_limits()
        if not can_trade:
            print(f"\n🚨 RISK HALT: {risk_msg}")
            log_action('RISK_HALT', {'reason': risk_msg})
            return result

        # 2. Detect market regime (NEW)
        self.detect_market_regime()
        regime_emoji = {'BULL': '🐂', 'BEAR': '🐻', 'NEUTRAL': '😐'}
        print(f"\n📊 Market Regime: {regime_emoji.get(self.market_regime, '')} {self.market_regime}")

        # 3. Get market data for all coins
        print("\n📊 Market Analysis:")
        market_data = {}
        for symbol in self.client.whitelist:
            data = self.get_market_data(symbol)
            if data:
                market_data[symbol] = data
                score = self.calculate_coin_score(data)
                trend = f"{data['trend_1h']}/{data['trend_4h']}"
                accel = "↗" if data['momentum_accel'] > 0 else "↘" if data['momentum_accel'] < 0 else "→"
                vol_brk = "📊" if data['is_volume_breakout'] else ""
                print(f"  {symbol}: Score={score:>6.1f} | RSI={data['rsi_1h']:>5.1f} | "
                      f"Mom={data['momentum_score']:>+6.2f}%{accel} | Trend={trend} {vol_brk}")
                result['analysis'].append({**data, 'score': score})

        # Sort by score
        sorted_coins = sorted(market_data.items(), key=lambda x: self.calculate_coin_score(x[1]), reverse=True)
        print(f"\n🏆 Ranking: {' > '.join([s[0].split('/')[0] for s in sorted_coins])}")

        # 4. Check existing positions
        positions = self.client.get_all_positions()
        sold_symbols = set()

        if positions:
            print(f"\n💼 Checking positions ({len(positions)}):")
            for pos in positions:
                symbol = pos['symbol']
                score = self.calculate_coin_score(market_data[symbol]) if symbol in market_data else 0
                print(f"  {symbol}: {pos['amount']:.8f} @ ${pos['current_price']:,.2f} | "
                      f"PnL: {pos['pnl_percent']:+.2f}% | Score: {score:.1f}")

                if symbol in market_data:
                    should_sell, reason, sell_portion = self.should_sell(market_data[symbol], pos)
                    if should_sell:
                        # v2.1: Handle partial sells
                        sell_amount = pos['amount'] * sell_portion
                        is_full_exit = sell_portion >= 1.0 or sell_amount >= pos['amount'] * 0.95

                        order = self.execute_sell(symbol, sell_amount, reason, is_full_exit=is_full_exit)
                        if order and not order.get('dust'):
                            action_type = 'SELL' if is_full_exit else 'PARTIAL_SELL'
                            result['actions'].append({'type': action_type, 'symbol': symbol, 'reason': reason})
                            if is_full_exit:
                                sold_symbols.add(symbol)

        # 5. Check rotation
        remaining_positions = [p for p in positions if p['symbol'] not in sold_symbols]
        if remaining_positions:
            rotation = self.check_rotation(remaining_positions, market_data)
            if rotation:
                print(f"\n🔄 Rotation suggested:")
                print(f"   Sell {rotation['sell_symbol']} (Score: {rotation['sell_score']:.1f})")
                print(f"   Buy {rotation['buy_symbol']} (Score: {rotation['buy_score']:.1f})")
                print(f"   Improvement: +{rotation['improvement']:.1f}")

                sell_pos = next((p for p in remaining_positions if p['symbol'] == rotation['sell_symbol']), None)
                if sell_pos:
                    sell_order = self.execute_sell(rotation['sell_symbol'], sell_pos['amount'],
                                                   f"ROTATION ({rotation['sell_score']:.1f} -> {rotation['buy_score']:.1f})")
                    if sell_order and not sell_order.get('dust'):
                        result['actions'].append({'type': 'ROTATION_SELL', 'symbol': rotation['sell_symbol']})
                        sold_symbols.add(rotation['sell_symbol'])

                        usdt_amount = sell_pos['current_value'] * 0.98
                        buy_data = market_data.get(rotation['buy_symbol'])
                        buy_order = self.execute_buy(rotation['buy_symbol'], usdt_amount, buy_data)
                        if buy_order:
                            result['actions'].append({'type': 'ROTATION_BUY', 'symbol': rotation['buy_symbol']})

                        self.last_rotation_time = datetime.now()

        # 6. Check buy opportunities
        print("\n🔍 Checking buy opportunities:")
        balance = self.client.get_balance()
        tickers = self.client.get_all_tickers()
        total_value = self.client.calculate_total_value_usdt(balance, tickers)
        usdt_free = self.client.get_usdt_balance()

        current_positions = len([p for p in positions if p['symbol'] not in sold_symbols])
        position_value = sum([p['current_value'] for p in positions if p['symbol'] not in sold_symbols])
        position_ratio = position_value / total_value if total_value > 0 else 0

        print(f"  Position ratio: {position_ratio*100:.1f}% / {MAX_TOTAL_POSITION_PCT*100:.0f}%")
        print(f"  Market regime: {self.market_regime}")

        if position_ratio >= MAX_TOTAL_POSITION_PCT:
            print(f"  ⚠️ Max position limit reached")
        elif usdt_free < MIN_TRADE_USDT:
            print(f"  ⚠️ Insufficient USDT (${usdt_free:.2f} < ${MIN_TRADE_USDT:.2f})")
        else:
            held_currencies = [p['currency'] for p in positions if p['symbol'] not in sold_symbols]
            buy_candidates = []

            # v2.1: Pass existing positions for correlation check
            remaining_positions = [p for p in positions if p['symbol'] not in sold_symbols]

            for symbol, data in sorted_coins:
                currency = symbol.split('/')[0]
                if currency in held_currencies:
                    continue

                should_buy, reason, score = self.should_buy(data, current_positions, remaining_positions)
                if should_buy:
                    buy_candidates.append((symbol, data, reason, score))

            if buy_candidates:
                symbol, data, reason, score = buy_candidates[0]
                position_size = self.calculate_position_size(data, usdt_free, total_value, current_positions)

                if position_size >= MIN_TRADE_USDT:
                    print(f"  📈 Buy candidate: {symbol}")
                    print(f"     Reason: {reason}")
                    print(f"     Size: ${position_size:.2f} ({position_size/total_value*100:.1f}%)")

                    order = self.execute_buy(symbol, position_size, data)
                    if order:
                        result['actions'].append({'type': 'BUY', 'symbol': symbol, 'reason': reason})
                else:
                    print(f"  ℹ️ {symbol} position too small, skipping")
            else:
                print("  No qualifying buy signals")

        # 7. Summary
        if not result['actions']:
            log_action('HOLD', {'reason': 'No signals', 'regime': self.market_regime})

        self.save_equity_snapshot(total_value)

        print(f"\n💰 Account Status:")
        print(f"   Total: ${total_value:.2f}")
        print(f"   USDT: ${usdt_free:.2f}")
        print(f"   Positions: ${position_value:.2f} ({position_ratio*100:.1f}%)")
        print(f"   Regime: {self.market_regime}")

        # Calculate returns
        if os.path.exists(EQUITY_FILE):
            try:
                with open(EQUITY_FILE, 'r') as f:
                    history = json.load(f)
                if len(history) > 1:
                    initial_value = history[0]['total_value']
                    total_return = ((total_value - initial_value) / initial_value) * 100
                    print(f"   Total Return: {total_return:+.2f}%")
            except:
                pass

        print("=" * 70)

        return result


def get_strategy_status() -> Dict:
    """Get strategy status for Dashboard"""
    client = BinanceClient()
    strategy = AggressiveMomentumStrategy(client)

    # Detect market regime
    regime = strategy.detect_market_regime()

    # Get market data
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
                'momentum_accel': data['momentum_accel'],
                'price': data['price'],
                'signal': signal,
                'volume_breakout': data['is_volume_breakout'],
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
        'market_regime': regime,  # NEW
        'config': {
            'max_single_position_pct': MAX_SINGLE_POSITION_PCT * 100,
            'max_total_position_pct': MAX_TOTAL_POSITION_PCT * 100,
            'hard_stop_loss_pct': HARD_STOP_LOSS_PCT,
            'atr_stop_multiplier': ATR_STOP_MULTIPLIER,
            'aggressive_take_profit_pct': AGGRESSIVE_TAKE_PROFIT_PCT,
            'daily_loss_limit_pct': DAILY_LOSS_LIMIT_PCT,
            'max_drawdown_pct': MAX_DRAWDOWN_PCT,
            'volatility_target': VOLATILITY_TARGET,
        }
    }


# Entry point
if __name__ == '__main__':
    strategy = AggressiveMomentumStrategy()
    strategy.run_once()
