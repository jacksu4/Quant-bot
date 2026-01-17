"""
Comprehensive tests for strategy modules

Tests RSIMeanReversionStrategy, RobustRSIStrategy, and AggressiveMomentumStrategy.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# =============================================================================
# Tests for RSI Mean Reversion Strategy
# =============================================================================

class TestRSIMeanReversionStrategy:
    """Tests for the simple RSI strategy"""

    @pytest.fixture
    def mock_client(self):
        """Create a mock BinanceClient"""
        client = MagicMock()
        client.whitelist = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
        return client

    @pytest.fixture
    def strategy(self, mock_client):
        """Create strategy instance with mock client"""
        from strategy import RSIMeanReversionStrategy
        return RSIMeanReversionStrategy(mock_client)

    def test_analyze_market_returns_signals(self, strategy, mock_client):
        """analyze_market should return signals for all whitelisted symbols"""
        mock_client.get_all_tickers.return_value = {
            'BTC/USDT': {'last': 50000},
            'ETH/USDT': {'last': 3000},
            'SOL/USDT': {'last': 100},
        }
        mock_client.get_all_rsi.return_value = {
            'BTC/USDT': 45,
            'ETH/USDT': 25,  # Oversold
            'SOL/USDT': 75,  # Overbought
        }

        analysis = strategy.analyze_market()

        assert 'signals' in analysis
        assert 'tickers' in analysis
        assert 'rsi_data' in analysis
        assert len(analysis['signals']) == 3

    def test_check_stop_loss_triggers(self, strategy):
        """Should trigger stop loss when loss exceeds threshold"""
        position = {'pnl_percent': -4.0}  # 4% loss (stop loss is 3%)

        result = strategy.check_stop_loss_take_profit(position)

        assert result == 'STOP_LOSS'

    def test_check_take_profit_triggers(self, strategy):
        """Should trigger take profit when gain exceeds threshold"""
        position = {'pnl_percent': 6.0}  # 6% gain (take profit is 5%)

        result = strategy.check_stop_loss_take_profit(position)

        assert result == 'TAKE_PROFIT'

    def test_check_no_action_needed(self, strategy):
        """Should return None when within normal range"""
        position = {'pnl_percent': 2.0}  # 2% gain (within thresholds)

        result = strategy.check_stop_loss_take_profit(position)

        assert result is None

    def test_should_buy_on_oversold(self, strategy, mock_client):
        """Should buy when RSI is oversold and conditions met"""
        mock_client.get_all_positions.return_value = []
        mock_client.get_usdt_balance.return_value = 100
        mock_client.get_min_order_usdt.return_value = 5

        signal = {
            'symbol': 'ETH/USDT',
            'rsi': 25,
            'price': 3000,
            'signal': 'BUY'
        }

        result = strategy.should_buy(signal)

        assert result == True

    def test_should_not_buy_without_signal(self, strategy, mock_client):
        """Should not buy when no buy signal"""
        signal = {
            'symbol': 'ETH/USDT',
            'rsi': 50,
            'price': 3000,
            'signal': None
        }

        result = strategy.should_buy(signal)

        assert result == False

    def test_should_not_buy_max_positions(self, strategy, mock_client):
        """Should not buy when max positions reached"""
        mock_client.get_all_positions.return_value = [
            {'currency': 'BTC', 'amount': 0.001},
            {'currency': 'ETH', 'amount': 0.1},
        ]

        signal = {
            'symbol': 'SOL/USDT',
            'rsi': 25,
            'price': 100,
            'signal': 'BUY'
        }

        result = strategy.should_buy(signal)

        assert result == False

    def test_should_not_buy_already_held(self, strategy, mock_client):
        """Should not buy coin already held"""
        mock_client.get_all_positions.return_value = [
            {'currency': 'ETH', 'amount': 0.1}
        ]
        mock_client.get_usdt_balance.return_value = 100
        mock_client.get_min_order_usdt.return_value = 5

        signal = {
            'symbol': 'ETH/USDT',
            'rsi': 25,
            'price': 3000,
            'signal': 'BUY'
        }

        result = strategy.should_buy(signal)

        assert result == False


# =============================================================================
# Tests for Robust RSI Strategy
# =============================================================================

class TestRobustRSIStrategy:
    """Tests for the Robust RSI strategy"""

    @pytest.fixture
    def mock_client(self):
        """Create a mock BinanceClient"""
        client = MagicMock()
        client.whitelist = ['BTC/USDT', 'ETH/USDT']
        return client

    @pytest.fixture
    def strategy(self, mock_client):
        """Create strategy instance with mock client"""
        from robust_strategy import RobustRSIStrategy
        return RobustRSIStrategy(mock_client)

    def test_get_market_data_returns_dict(self, strategy, mock_client):
        """get_market_data should return dictionary with indicators"""
        mock_client.get_ohlcv.return_value = [
            [i, 100+i, 105+i, 95+i, 100+i, 1000] for i in range(100)
        ]
        mock_client.calculate_rsi.return_value = 45

        result = strategy.get_market_data('BTC/USDT')

        assert result is not None
        assert 'symbol' in result
        assert 'rsi_1h' in result
        assert 'rsi_4h' in result
        assert 'trend_1h' in result
        assert 'trend_4h' in result
        assert 'atr' in result

    def test_calculate_position_size_basic(self, strategy):
        """Should calculate position size based on data"""
        data = {
            'atr_pct': 2.0,
            'rsi_1h': 30
        }

        size = strategy.calculate_position_size(data, available_usdt=100)

        assert size > 0
        assert size <= 15  # Max position

    def test_calculate_position_size_high_volatility(self, strategy):
        """High volatility should reduce position size"""
        data_low_vol = {'atr_pct': 1.0, 'rsi_1h': 30}
        data_high_vol = {'atr_pct': 4.0, 'rsi_1h': 30}

        size_low = strategy.calculate_position_size(data_low_vol, 100)
        size_high = strategy.calculate_position_size(data_high_vol, 100)

        assert size_high < size_low

    def test_should_buy_oversold_with_good_trend(self, strategy):
        """Should buy when RSI oversold and trend not both down"""
        data = {
            'rsi_1h': 30,
            'rsi_4h': 45,
            'trend_1h': 'UP',
            'trend_4h': 'DOWN',
            'atr_pct': 2.0
        }

        should_buy, reason = strategy.should_buy(data)

        assert should_buy == True

    def test_should_not_buy_4h_rsi_high(self, strategy):
        """Should not buy when 4H RSI is too high"""
        data = {
            'rsi_1h': 30,
            'rsi_4h': 65,  # Too high
            'trend_1h': 'UP',
            'trend_4h': 'UP',
            'atr_pct': 2.0
        }

        should_buy, reason = strategy.should_buy(data)

        assert should_buy == False

    def test_should_not_buy_double_downtrend(self, strategy):
        """Should not buy when both timeframes show downtrend (unless extremely oversold)"""
        data = {
            'rsi_1h': 32,  # Oversold but not extremely
            'rsi_4h': 45,
            'trend_1h': 'DOWN',
            'trend_4h': 'DOWN',
            'atr_pct': 2.0
        }

        should_buy, reason = strategy.should_buy(data)

        assert should_buy == False

    def test_should_sell_on_stop_loss(self, strategy):
        """Should sell when stop loss triggered"""
        # With ATR=1 and entry_price=100, stop_pct = (1*2)/100*100 = 2% (min is 1.5%, so it's 2%)
        # A loss of -6% should trigger the stop loss (max stop is 5%)
        data = {'rsi_1h': 50, 'atr': 1, 'price': 94}
        position = {'pnl_percent': -6.0, 'avg_price': 100}

        should_sell, reason = strategy.should_sell(data, position)

        assert should_sell == True
        assert 'STOP_LOSS' in reason

    def test_should_sell_on_take_profit(self, strategy):
        """Should sell when take profit triggered"""
        # With ATR=1 and entry_price=100, profit_pct = (1*3)/100*100 = 3% (min is 2%, so it's 3%)
        # A gain of 9% should trigger the take profit (max profit is 8%)
        data = {'rsi_1h': 50, 'atr': 1, 'price': 109}
        position = {'pnl_percent': 9.0, 'avg_price': 100}

        should_sell, reason = strategy.should_sell(data, position)

        assert should_sell == True
        assert 'TAKE_PROFIT' in reason

    def test_should_sell_on_rsi_overbought(self, strategy):
        """Should sell when RSI is strongly overbought"""
        data = {'rsi_1h': 80, 'atr': 10, 'price': 102}
        position = {'pnl_percent': 2.0, 'avg_price': 100}

        should_sell, reason = strategy.should_sell(data, position)

        assert should_sell == True
        assert 'RSI_OVERBOUGHT' in reason


# =============================================================================
# Tests for Aggressive Momentum Strategy
# =============================================================================

class TestAggressiveMomentumStrategy:
    """Tests for the Aggressive Momentum strategy"""

    @pytest.fixture
    def mock_client(self):
        """Create a mock BinanceClient"""
        client = MagicMock()
        client.whitelist = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
        client.get_mode_str.return_value = "Test Mode"
        return client

    @pytest.fixture
    def strategy(self, mock_client):
        """Create strategy instance with mock client"""
        from aggressive_momentum_strategy import AggressiveMomentumStrategy
        return AggressiveMomentumStrategy(mock_client)

    def test_calculate_coin_score_momentum_weight(self, strategy):
        """Momentum should heavily influence coin score"""
        data_high_momentum = {
            'momentum_score': 10.0,
            'rsi_1h': 50,
            'macd_signal': 0.5,
            'trend_1h': 'UP',
            'trend_4h': 'UP',
            'overall_trend': 'UP',
            'volume_ratio': 1.0
        }
        data_low_momentum = {
            'momentum_score': 1.0,
            'rsi_1h': 50,
            'macd_signal': 0.5,
            'trend_1h': 'UP',
            'trend_4h': 'UP',
            'overall_trend': 'UP',
            'volume_ratio': 1.0
        }

        score_high = strategy.calculate_coin_score(data_high_momentum)
        score_low = strategy.calculate_coin_score(data_low_momentum)

        assert score_high > score_low

    def test_calculate_coin_score_rsi_impact(self, strategy):
        """RSI should impact coin score"""
        data_oversold = {
            'momentum_score': 5.0,
            'rsi_1h': 25,  # Strong oversold
            'macd_signal': 0,
            'trend_1h': 'UP',
            'trend_4h': 'UP',
            'overall_trend': 'UP',
            'volume_ratio': 1.0
        }
        data_overbought = {
            'momentum_score': 5.0,
            'rsi_1h': 75,  # Overbought
            'macd_signal': 0,
            'trend_1h': 'UP',
            'trend_4h': 'UP',
            'overall_trend': 'UP',
            'volume_ratio': 1.0
        }

        score_oversold = strategy.calculate_coin_score(data_oversold)
        score_overbought = strategy.calculate_coin_score(data_overbought)

        assert score_oversold > score_overbought

    def test_should_buy_high_score(self, strategy):
        """Should buy when score is high enough"""
        data = {
            'momentum_score': 8.0,
            'rsi_1h': 45,
            'macd_signal': 1,
            'trend_1h': 'UP',
            'trend_4h': 'UP',
            'overall_trend': 'UP',
            'volume_ratio': 1.5,
            'momentum_short': 2.0
        }

        should_buy, reason, score = strategy.should_buy(data, current_positions=0)

        assert should_buy == True
        assert score > 10

    def test_should_not_buy_low_score(self, strategy):
        """Should not buy when score is too low"""
        data = {
            'momentum_score': 0.5,
            'rsi_1h': 50,
            'macd_signal': 0,
            'trend_1h': 'DOWN',
            'trend_4h': 'DOWN',
            'overall_trend': 'DOWN',
            'volume_ratio': 0.8,
            'momentum_short': -1.0
        }

        should_buy, reason, score = strategy.should_buy(data, current_positions=0)

        assert should_buy == False

    def test_should_not_buy_rsi_too_high(self, strategy):
        """Should not buy when RSI is overbought"""
        data = {
            'momentum_score': 10.0,
            'rsi_1h': 80,  # Too high
            'macd_signal': 1,
            'trend_1h': 'UP',
            'trend_4h': 'UP',
            'overall_trend': 'UP',
            'volume_ratio': 2.0,
            'momentum_short': 5.0
        }

        should_buy, reason, score = strategy.should_buy(data, current_positions=0)

        assert should_buy == False
        assert "RSI过高" in reason

    def test_should_sell_hard_stop_loss(self, strategy):
        """Should sell when hard stop loss triggered"""
        data = {'rsi_1h': 50, 'macd_signal': 0, 'momentum_short': 0, 'price': 96}
        position = {'pnl_percent': -4.0, 'symbol': 'BTC/USDT', 'avg_price': 100}

        should_sell, reason = strategy.should_sell(data, position)

        assert should_sell == True
        assert "HARD_STOP_LOSS" in reason

    def test_should_sell_aggressive_take_profit(self, strategy):
        """Should sell when aggressive take profit triggered"""
        data = {'rsi_1h': 60, 'macd_signal': 0, 'momentum_short': 1, 'price': 109}
        position = {'pnl_percent': 9.0, 'symbol': 'BTC/USDT', 'avg_price': 100}  # > 8%

        should_sell, reason = strategy.should_sell(data, position)

        assert should_sell == True
        assert "AGGRESSIVE_TAKE_PROFIT" in reason

    def test_should_sell_rsi_overbought_with_profit(self, strategy):
        """Should sell when RSI overbought and position profitable"""
        data = {'rsi_1h': 82, 'macd_signal': 0, 'momentum_short': 0, 'price': 102}
        position = {'pnl_percent': 2.0, 'symbol': 'BTC/USDT', 'avg_price': 100}

        should_sell, reason = strategy.should_sell(data, position)

        assert should_sell == True
        assert "RSI_OVERBOUGHT" in reason

    def test_trailing_stop_activates_after_profit(self, strategy):
        """Trailing stop should activate after minimum profit"""
        # Set high price in tracking
        strategy.position_high_prices['BTC/USDT'] = 110  # High was 110

        data = {'rsi_1h': 50, 'macd_signal': 0, 'momentum_short': 0, 'price': 105}  # Now 105
        position = {
            'pnl_percent': 5.0,  # > 3% min profit
            'symbol': 'BTC/USDT',
            'avg_price': 100
        }

        should_sell, reason = strategy.should_sell(data, position)

        # Drawdown from high = (110-105)/110 = 4.5% > 2%
        assert should_sell == True
        assert "TRAILING_STOP" in reason

    def test_calculate_position_size_strong_signal(self, strategy, mock_client):
        """Strong signal should use higher position size"""
        data_strong = {
            'momentum_score': 10.0,
            'rsi_1h': 35,
            'macd_signal': 1,
            'trend_1h': 'UP',
            'trend_4h': 'UP',
            'overall_trend': 'UP',
            'volume_ratio': 2.0,
            'volatility': 2.0,
            'adx': 35
        }
        data_weak = {
            'momentum_score': 2.0,
            'rsi_1h': 50,
            'macd_signal': 0,
            'trend_1h': 'DOWN',
            'trend_4h': 'DOWN',
            'overall_trend': 'DOWN',
            'volume_ratio': 0.8,
            'volatility': 2.0,
            'adx': 15
        }

        size_strong = strategy.calculate_position_size(data_strong, 100, 100, 0)
        size_weak = strategy.calculate_position_size(data_weak, 100, 100, 0)

        assert size_strong > size_weak

    def test_check_rotation(self, strategy):
        """Should suggest rotation when better coin available"""
        strategy.last_rotation_time = None  # Allow rotation

        current_positions = [
            {'symbol': 'ETH/USDT', 'currency': 'ETH', 'amount': 0.1}
        ]

        market_data = {
            'ETH/USDT': {
                'momentum_score': 2.0,
                'rsi_1h': 50,
                'macd_signal': 0,
                'trend_1h': 'DOWN',
                'trend_4h': 'DOWN',
                'overall_trend': 'DOWN',
                'volume_ratio': 0.8
            },
            'BTC/USDT': {
                'momentum_score': 10.0,
                'rsi_1h': 40,
                'macd_signal': 1,
                'trend_1h': 'UP',
                'trend_4h': 'UP',
                'overall_trend': 'UP',
                'volume_ratio': 2.0
            }
        }

        rotation = strategy.check_rotation(current_positions, market_data)

        assert rotation is not None
        assert rotation['sell_symbol'] == 'ETH/USDT'
        assert rotation['buy_symbol'] == 'BTC/USDT'


# =============================================================================
# Tests for Log Functions
# =============================================================================

class TestLogFunctions:
    """Tests for logging functions in strategies"""

    def test_log_action_creates_entry(self, tmp_path):
        """log_action should create log entry with timestamp"""
        log_file = tmp_path / 'test_log.json'

        with patch('strategy.LOG_FILE', str(log_file)):
            from strategy import log_action
            entry = log_action('TEST', {'key': 'value'})

            assert 'timestamp' in entry
            assert entry['action'] == 'TEST'
            assert entry['details']['key'] == 'value'

    def test_get_logs_returns_recent(self, tmp_path):
        """get_logs should return most recent entries"""
        log_file = tmp_path / 'test_log.json'
        logs = [
            {'timestamp': f'2024-01-{i:02d}T00:00:00', 'action': 'TEST', 'details': {}}
            for i in range(1, 11)
        ]
        log_file.write_text(json.dumps(logs))

        with patch('strategy.LOG_FILE', str(log_file)):
            from strategy import get_logs
            result = get_logs(limit=5)

            assert len(result) == 5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
