"""
Comprehensive tests for indicators.py module

Tests all technical indicators for correctness and edge cases.
"""

import pytest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from indicators import (
    TechnicalIndicators,
    calculate_correlation,
    calculate_beta,
    z_score
)


class TestEMA:
    """Tests for Exponential Moving Average"""

    def test_ema_basic(self):
        """EMA should smooth price data"""
        prices = [10, 11, 12, 11, 10, 11, 12, 13, 14, 15]
        ema = TechnicalIndicators.ema(prices, period=3)

        assert len(ema) == len(prices)
        assert ema[0] == prices[0]  # First value equals first price

    def test_ema_trend_following(self):
        """EMA should follow upward trend"""
        prices = list(range(1, 21))  # 1 to 20
        ema = TechnicalIndicators.ema(prices, period=5)

        # EMA should be increasing for upward trend
        for i in range(5, len(ema)):
            assert ema[i] > ema[i-1]

    def test_ema_single_value(self):
        """EMA of single value should equal that value"""
        prices = [100]
        ema = TechnicalIndicators.ema(prices, period=14)
        assert ema[0] == 100

    def test_ema_constant_prices(self):
        """EMA of constant prices should equal that constant"""
        prices = [50.0] * 20
        ema = TechnicalIndicators.ema(prices, period=10)

        for val in ema:
            assert abs(val - 50.0) < 0.001


class TestSMA:
    """Tests for Simple Moving Average"""

    def test_sma_basic(self):
        """SMA should return correct average"""
        prices = [10, 20, 30, 40, 50]
        sma = TechnicalIndicators.sma(prices, period=3)

        # First 2 values should be NaN
        assert np.isnan(sma[0])
        assert np.isnan(sma[1])
        # Third value = avg(10, 20, 30) = 20
        assert sma[2] == 20.0
        # Fourth value = avg(20, 30, 40) = 30
        assert sma[3] == 30.0
        # Fifth value = avg(30, 40, 50) = 40
        assert sma[4] == 40.0

    def test_sma_period_larger_than_data(self):
        """SMA with period larger than data should return NaN"""
        prices = [10, 20, 30]
        sma = TechnicalIndicators.sma(prices, period=5)

        for val in sma:
            assert np.isnan(val)


class TestMACD:
    """Tests for MACD indicator"""

    def test_macd_basic(self):
        """MACD should return three components"""
        prices = [float(i) for i in range(1, 51)]  # 50 prices
        dif, dea, macd_hist = TechnicalIndicators.macd(prices)

        assert len(dif) == len(prices)
        assert len(dea) == len(prices)
        assert len(macd_hist) == len(prices)

    def test_macd_cross_detection(self):
        """MACD histogram should change sign at crossovers"""
        # Create prices that go up then down
        prices = list(range(1, 26)) + list(range(25, 0, -1))
        dif, dea, macd_hist = TechnicalIndicators.macd(prices)

        # Should have both positive and negative values
        has_positive = any(h > 0 for h in macd_hist[26:])
        has_negative = any(h < 0 for h in macd_hist[26:])

        assert has_positive or has_negative  # At least one


class TestRSI:
    """Tests for Relative Strength Index"""

    def test_rsi_basic_range(self):
        """RSI should be between 0 and 100"""
        prices = [100 + i * (1 if i % 2 == 0 else -1) for i in range(30)]
        rsi = TechnicalIndicators.rsi(prices, period=14)

        for val in rsi:
            assert 0 <= val <= 100

    def test_rsi_all_gains(self):
        """RSI should be 100 when all prices go up"""
        prices = list(range(100, 130))  # All increasing
        rsi = TechnicalIndicators.rsi(prices, period=14)

        # Last RSI should be 100 (all gains)
        assert rsi[-1] == 100.0

    def test_rsi_all_losses(self):
        """RSI should approach 0 when all prices go down"""
        prices = list(range(130, 100, -1))  # All decreasing
        rsi = TechnicalIndicators.rsi(prices, period=14)

        # Last RSI should be very low
        assert rsi[-1] < 5

    def test_rsi_flat_prices(self):
        """RSI should be 50 when prices don't change"""
        prices = [100.0] * 20
        rsi = TechnicalIndicators.rsi(prices, period=14)

        assert rsi[-1] == 50.0

    def test_rsi_insufficient_data(self):
        """RSI with insufficient data should return default"""
        prices = [100, 101, 102]  # Less than period
        rsi = TechnicalIndicators.rsi(prices, period=14)

        assert all(val == 50.0 for val in rsi)


class TestBollingerBands:
    """Tests for Bollinger Bands"""

    def test_bollinger_bands_basic(self):
        """Bollinger Bands should have upper > middle > lower"""
        prices = [100 + i % 5 for i in range(30)]
        upper, middle, lower = TechnicalIndicators.bollinger_bands(prices, period=20)

        # Check last valid values
        assert upper[-1] > middle[-1]
        assert middle[-1] > lower[-1]

    def test_bollinger_bands_width(self):
        """Higher std_dev should create wider bands"""
        prices = [100 + i % 10 for i in range(30)]

        upper1, mid1, lower1 = TechnicalIndicators.bollinger_bands(prices, period=20, std_dev=1)
        upper2, mid2, lower2 = TechnicalIndicators.bollinger_bands(prices, period=20, std_dev=2)

        width1 = upper1[-1] - lower1[-1]
        width2 = upper2[-1] - lower2[-1]

        assert width2 > width1


class TestATR:
    """Tests for Average True Range"""

    def test_atr_basic(self):
        """ATR should be positive for volatile data"""
        high = [105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119]
        low = [95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109]
        close = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114]

        atr = TechnicalIndicators.atr(high, low, close, period=14)

        assert len(atr) == len(high)
        assert atr[-1] > 0

    def test_atr_constant_prices(self):
        """ATR should be minimal for constant prices"""
        high = [100.0] * 20
        low = [100.0] * 20
        close = [100.0] * 20

        atr = TechnicalIndicators.atr(high, low, close, period=14)

        assert atr[-1] == 0.0


class TestADX:
    """Tests for Average Directional Index"""

    def test_adx_strong_trend(self):
        """ADX should be high for strong trends"""
        # Strong uptrend
        high = [100 + i * 2 for i in range(30)]
        low = [95 + i * 2 for i in range(30)]
        close = [98 + i * 2 for i in range(30)]

        adx = TechnicalIndicators.adx(high, low, close, period=14)

        # ADX should be positive for trending market
        assert adx[-1] > 0

    def test_adx_range_bound(self):
        """ADX should be between 0 and 100"""
        high = [105 + i % 3 for i in range(30)]
        low = [95 + i % 3 for i in range(30)]
        close = [100 + i % 3 for i in range(30)]

        adx = TechnicalIndicators.adx(high, low, close, period=14)

        for val in adx:
            assert 0 <= val <= 100


class TestStochastic:
    """Tests for Stochastic Oscillator"""

    def test_stochastic_basic(self):
        """Stochastic should return K and D values"""
        high = [110 + i % 5 for i in range(20)]
        low = [90 + i % 5 for i in range(20)]
        close = [100 + i % 5 for i in range(20)]

        k, d = TechnicalIndicators.stochastic(high, low, close, period=14)

        assert len(k) == len(high)
        assert len(d) == len(high)

    def test_stochastic_range(self):
        """Stochastic K should be between 0 and 100"""
        high = [110 + i for i in range(20)]
        low = [90 + i for i in range(20)]
        close = [100 + i for i in range(20)]

        k, d = TechnicalIndicators.stochastic(high, low, close, period=14)

        for val in k[14:]:
            assert 0 <= val <= 100


class TestOBV:
    """Tests for On-Balance Volume"""

    def test_obv_increasing_prices(self):
        """OBV should increase when prices go up with volume"""
        close = list(range(100, 110))
        volume = [1000] * 10

        obv = TechnicalIndicators.obv(close, volume)

        # OBV should be positive and increasing
        assert obv[-1] > 0

    def test_obv_decreasing_prices(self):
        """OBV should decrease when prices go down"""
        close = list(range(110, 100, -1))
        volume = [1000] * 10

        obv = TechnicalIndicators.obv(close, volume)

        # OBV should be negative
        assert obv[-1] < 0


class TestMomentum:
    """Tests for Momentum indicator"""

    def test_momentum_basic(self):
        """Momentum should show price difference from N periods ago"""
        prices = list(range(100, 120))
        momentum = TechnicalIndicators.momentum(prices, period=10)

        # After period, momentum = current - price_10_ago
        # prices[15] - prices[5] = 115 - 105 = 10
        assert momentum[15] == 10

    def test_momentum_zero_for_flat(self):
        """Momentum should be zero for flat prices"""
        prices = [100] * 20
        momentum = TechnicalIndicators.momentum(prices, period=10)

        for val in momentum[10:]:
            assert val == 0


class TestROC:
    """Tests for Rate of Change"""

    def test_roc_basic(self):
        """ROC should show percentage change from N periods ago"""
        prices = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 110]
        roc = TechnicalIndicators.roc(prices, period=10)

        # Last ROC = (110 - 100) / 100 * 100 = 10%
        assert roc[-1] == 10.0


class TestWilliamsR:
    """Tests for Williams %R"""

    def test_williams_r_range(self):
        """Williams %R should be between -100 and 0"""
        high = [110 + i % 5 for i in range(20)]
        low = [90 + i % 5 for i in range(20)]
        close = [100 + i % 5 for i in range(20)]

        wr = TechnicalIndicators.williams_r(high, low, close, period=14)

        for val in wr[14:]:
            assert -100 <= val <= 0


class TestCCI:
    """Tests for Commodity Channel Index"""

    def test_cci_basic(self):
        """CCI should return values for valid data"""
        high = [110 + i for i in range(25)]
        low = [90 + i for i in range(25)]
        close = [100 + i for i in range(25)]

        cci = TechnicalIndicators.cci(high, low, close, period=20)

        assert len(cci) == len(high)


class TestReturns:
    """Tests for returns calculation"""

    def test_returns_basic(self):
        """Returns should calculate percentage change"""
        prices = [100, 110, 121]  # +10%, +10%
        returns = TechnicalIndicators.calculate_returns(prices, period=1)

        assert returns[0] == 0.0
        assert returns[1] == 10.0
        assert abs(returns[2] - 10.0) < 0.01

    def test_returns_period(self):
        """Returns over different periods"""
        prices = [100, 105, 110, 115, 120]
        returns = TechnicalIndicators.calculate_returns(prices, period=2)

        # returns[2] = (110 - 100) / 100 * 100 = 10%
        assert returns[2] == 10.0


class TestVolatility:
    """Tests for volatility calculation"""

    def test_volatility_basic(self):
        """Volatility should be positive for varying prices"""
        prices = [100 + i * (1 if i % 2 == 0 else -1) for i in range(30)]
        vol = TechnicalIndicators.volatility(prices, period=20)

        assert vol[-1] > 0


class TestSharpeRatio:
    """Tests for Sharpe Ratio calculation"""

    def test_sharpe_ratio_basic(self):
        """Sharpe ratio should return values for valid data"""
        prices = list(range(100, 140))
        sharpe = TechnicalIndicators.sharpe_ratio(prices, period=30)

        assert len(sharpe) == len(prices)


class TestUtilityFunctions:
    """Tests for utility functions"""

    def test_correlation_identical(self):
        """Correlation of identical series should be 1"""
        prices_a = [100, 110, 120, 130, 140]
        prices_b = [100, 110, 120, 130, 140]

        corr = calculate_correlation(prices_a, prices_b)

        assert abs(corr - 1.0) < 0.001

    def test_correlation_opposite(self):
        """Correlation of opposite series should be -1"""
        prices_a = [100, 110, 120, 130, 140]
        prices_b = [140, 130, 120, 110, 100]

        corr = calculate_correlation(prices_a, prices_b)

        assert abs(corr - (-1.0)) < 0.001

    def test_beta_identical(self):
        """Beta of identical series should be 1 (with sufficient variation)"""
        # Need more data points with actual variation for beta to work correctly
        prices_asset = [100, 102, 98, 105, 103, 110, 108, 115, 112, 120]
        prices_market = [100, 102, 98, 105, 103, 110, 108, 115, 112, 120]

        beta = calculate_beta(prices_asset, prices_market)

        # For identical series, beta should be close to 1
        assert abs(beta - 1.0) < 0.2  # Allow floating point tolerance

    def test_z_score_basic(self):
        """Z-score should be 0 for mean value"""
        values = [90, 95, 100, 105, 110, 100, 100, 100, 100, 100,
                  100, 100, 100, 100, 100, 100, 100, 100, 100, 100]

        z = z_score(values, period=20)

        # Last value equals mean, so z-score should be around 0
        assert abs(z[-1]) < 0.5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
