"""
Integration tests for Quant-bot

Tests the interaction between different modules and end-to-end workflows.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# =============================================================================
# Directory and File Structure Tests
# =============================================================================

class TestProjectStructure:
    """Tests for project structure and directories"""

    def test_data_directory(self):
        """Test that data directory can be created"""
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        os.makedirs(data_dir, exist_ok=True)
        assert os.path.exists(data_dir)

    def test_logs_directory(self):
        """Test that logs directory can be created"""
        logs_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        assert os.path.exists(logs_dir)

    def test_deployment_scripts_exist(self):
        """Test that deployment scripts exist"""
        scripts = ['deploy.sh', 'healthcheck.sh']
        for script in scripts:
            script_path = os.path.join(os.path.dirname(__file__), '..', script)
            assert os.path.exists(script_path), f"Script not found: {script}"

    def test_required_python_files_exist(self):
        """Test that all required Python files exist"""
        required_files = [
            'exchange.py',
            'strategy.py',
            'robust_strategy.py',
            'aggressive_momentum_strategy.py',
            'indicators.py',
            'data_store.py',
            'dashboard.py'
        ]
        for file in required_files:
            file_path = os.path.join(os.path.dirname(__file__), '..', file)
            assert os.path.exists(file_path), f"File not found: {file}"


# =============================================================================
# Strategy and Client Integration Tests
# =============================================================================

class TestStrategyClientIntegration:
    """Tests for strategy and exchange client integration"""

    @pytest.fixture
    def mock_exchange(self):
        """Create mock exchange with realistic responses"""
        exchange = MagicMock()
        exchange.fetch_balance.return_value = {
            'total': {'USDT': 100, 'BTC': 0.002, 'ETH': 0.05},
            'free': {'USDT': 100, 'BTC': 0.002, 'ETH': 0.05},
            'used': {'USDT': 0, 'BTC': 0, 'ETH': 0}
        }
        exchange.fetch_ticker.return_value = {
            'last': 50000,
            'ask': 50010,
            'bid': 49990
        }
        exchange.fetch_ohlcv.return_value = [
            [i * 3600000, 50000 + i * 10, 50100 + i * 10, 49900 + i * 10, 50050 + i * 10, 1000]
            for i in range(100)
        ]
        exchange.market.return_value = {
            'limits': {
                'amount': {'min': 0.0001},
                'cost': {'min': 5.0}
            }
        }
        exchange.amount_to_precision.return_value = '0.002'
        exchange.fetch_my_trades.return_value = [
            {'side': 'buy', 'cost': 100, 'amount': 0.002, 'price': 50000, 'timestamp': 1234567890000}
        ]
        return exchange

    def test_strategy_run_once_complete_cycle(self, mock_exchange):
        """Test complete strategy execution cycle"""
        with patch('exchange.ccxt.binance', return_value=mock_exchange):
            from exchange import BinanceClient
            from strategy import RSIMeanReversionStrategy

            client = BinanceClient()
            strategy = RSIMeanReversionStrategy(client)

            # Mock analyze_market to return specific signals
            strategy.analyze_market = Mock(return_value={
                'signals': [
                    {'symbol': 'SOL/USDT', 'rsi': 28, 'price': 100, 'signal': 'BUY'}
                ],
                'tickers': {'BTC/USDT': {'last': 50000}},
                'rsi_data': {'BTC/USDT': 45}
            })

            # Run strategy
            result = strategy.run_once()

            assert 'timestamp' in result
            assert 'actions' in result
            assert 'analysis' in result

    def test_robust_strategy_market_analysis(self, mock_exchange):
        """Test Robust RSI strategy market analysis"""
        with patch('exchange.ccxt.binance', return_value=mock_exchange):
            from exchange import BinanceClient
            from robust_strategy import RobustRSIStrategy

            client = BinanceClient()
            strategy = RobustRSIStrategy(client)

            # Get market data for a symbol
            data = strategy.get_market_data('BTC/USDT')

            assert data is not None
            assert 'rsi_1h' in data
            assert 'rsi_4h' in data
            assert 'trend_1h' in data
            assert 'trend_4h' in data

    def test_aggressive_strategy_scoring_system(self, mock_exchange):
        """Test aggressive momentum strategy scoring"""
        with patch('exchange.ccxt.binance', return_value=mock_exchange):
            from exchange import BinanceClient
            from aggressive_momentum_strategy import AggressiveMomentumStrategy

            client = BinanceClient()
            strategy = AggressiveMomentumStrategy(client)

            # Get market data
            data = strategy.get_market_data('BTC/USDT')

            if data:
                # Calculate score
                score = strategy.calculate_coin_score(data)
                assert isinstance(score, float)


# =============================================================================
# Data Store Integration Tests
# =============================================================================

class TestDataStoreIntegration:
    """Tests for data storage integration with strategies"""

    def test_strategy_saves_snapshots(self, tmp_path):
        """Strategy should save equity snapshots"""
        test_file = tmp_path / 'equity_history.json'

        with patch('aggressive_momentum_strategy.EQUITY_FILE', str(test_file)):
            from aggressive_momentum_strategy import AggressiveMomentumStrategy

            # Create strategy with mock client
            mock_client = MagicMock()
            mock_client.get_mode_str.return_value = "Test"

            strategy = AggressiveMomentumStrategy(mock_client)
            strategy.save_equity_snapshot(1000.0)

            # Verify snapshot was saved
            with open(test_file, 'r') as f:
                history = json.load(f)

            assert len(history) == 1
            assert history[0]['total_value'] == 1000.0


# =============================================================================
# Indicators Integration Tests
# =============================================================================

class TestIndicatorsIntegration:
    """Tests for indicators integration with strategies"""

    def test_strategy_uses_technical_indicators(self):
        """Strategy should correctly use technical indicators"""
        from indicators import TechnicalIndicators

        # Create sample price data
        prices = [100 + i for i in range(50)]

        # Calculate indicators
        ema_fast = TechnicalIndicators.ema(prices, 8)
        ema_slow = TechnicalIndicators.ema(prices, 21)
        rsi = TechnicalIndicators.rsi(prices, 14)

        # Verify indicators are usable
        assert len(ema_fast) == len(prices)
        assert len(ema_slow) == len(prices)
        assert len(rsi) == len(prices)

        # Trend should be up (prices increasing)
        assert ema_fast[-1] > ema_slow[-1]

    def test_macd_signal_detection(self):
        """Test MACD signal detection logic"""
        from indicators import TechnicalIndicators

        # Create prices that should generate signals
        prices = [100] * 30 + list(range(100, 130))

        dif, dea, macd_hist = TechnicalIndicators.macd(prices)

        # Should have valid MACD values
        assert len(dif) == len(prices)
        assert len(dea) == len(prices)
        assert len(macd_hist) == len(prices)


# =============================================================================
# Risk Management Integration Tests
# =============================================================================

class TestRiskManagementIntegration:
    """Tests for risk management integration"""

    def test_stop_loss_prevents_large_losses(self):
        """Stop loss should trigger before excessive loss"""
        from strategy import RSIMeanReversionStrategy

        mock_client = MagicMock()
        strategy = RSIMeanReversionStrategy(mock_client)

        # Position with 4% loss (> 3% stop loss threshold)
        position = {'pnl_percent': -4.0}
        result = strategy.check_stop_loss_take_profit(position)

        assert result == 'STOP_LOSS'

    def test_take_profit_locks_gains(self):
        """Take profit should trigger to lock in gains"""
        from strategy import RSIMeanReversionStrategy

        mock_client = MagicMock()
        strategy = RSIMeanReversionStrategy(mock_client)

        # Position with 6% gain (> 5% take profit threshold)
        position = {'pnl_percent': 6.0}
        result = strategy.check_stop_loss_take_profit(position)

        assert result == 'TAKE_PROFIT'

    def test_aggressive_strategy_risk_limits(self):
        """Test aggressive strategy risk limit checking"""
        from aggressive_momentum_strategy import AggressiveMomentumStrategy

        mock_client = MagicMock()
        strategy = AggressiveMomentumStrategy(mock_client)

        # Check risk limits (should pass with no history)
        can_trade, msg = strategy.check_risk_limits()

        # With no history, should allow trading
        assert can_trade == True


# =============================================================================
# End-to-End Workflow Tests
# =============================================================================

class TestEndToEndWorkflow:
    """End-to-end workflow tests"""

    def test_buy_to_sell_workflow(self):
        """Test complete buy to sell workflow"""
        from strategy import RSIMeanReversionStrategy

        mock_client = MagicMock()
        mock_client.whitelist = ['BTC/USDT']
        mock_client.get_all_positions.return_value = []
        mock_client.get_usdt_balance.return_value = 100
        mock_client.get_min_order_usdt.return_value = 5
        mock_client.get_min_order_amount.return_value = 0.0001
        mock_client.create_market_buy_usdt.return_value = {
            'id': '12345',
            'filled': 0.002,
            'average': 50000
        }
        mock_client.create_market_sell.return_value = {
            'id': '67890',
            'filled': 0.002,
            'average': 51000
        }

        strategy = RSIMeanReversionStrategy(mock_client)

        # Test buy condition
        buy_signal = {
            'symbol': 'BTC/USDT',
            'rsi': 25,
            'price': 50000,
            'signal': 'BUY'
        }
        assert strategy.should_buy(buy_signal) == True

        # Execute buy
        order = strategy.execute_buy('BTC/USDT', 50)
        assert order is not None
        assert order['id'] == '12345'

        # Check take profit condition
        position = {'pnl_percent': 6.0}
        assert strategy.check_stop_loss_take_profit(position) == 'TAKE_PROFIT'

        # Execute sell
        order = strategy.execute_sell('BTC/USDT', 0.002, 'TAKE_PROFIT')
        assert order is not None
        assert order['id'] == '67890'


# =============================================================================
# Module Import Tests
# =============================================================================

class TestModuleImports:
    """Tests for module import and compatibility"""

    def test_all_strategy_modules_import(self):
        """All strategy modules should import without errors"""
        try:
            from strategy import RSIMeanReversionStrategy
            from robust_strategy import RobustRSIStrategy
            from aggressive_momentum_strategy import AggressiveMomentumStrategy

            assert RSIMeanReversionStrategy is not None
            assert RobustRSIStrategy is not None
            assert AggressiveMomentumStrategy is not None
        except ImportError as e:
            pytest.fail(f"Failed to import strategy modules: {e}")

    def test_all_support_modules_import(self):
        """All support modules should import without errors"""
        try:
            from exchange import BinanceClient
            from indicators import TechnicalIndicators
            from data_store import load_snapshots, save_snapshots

            assert BinanceClient is not None
            assert TechnicalIndicators is not None
            assert load_snapshots is not None
        except ImportError as e:
            pytest.fail(f"Failed to import support modules: {e}")

    def test_get_strategy_status_functions(self):
        """Test strategy status functions for dashboard"""
        # Mock the exchange client
        mock_exchange = MagicMock()
        mock_exchange.fetch_balance.return_value = {
            'total': {'USDT': 100},
            'free': {'USDT': 100},
            'used': {'USDT': 0}
        }
        mock_exchange.fetch_ticker.return_value = {'last': 50000}
        mock_exchange.fetch_ohlcv.return_value = [
            [i, 100, 100, 100, 100, 1000] for i in range(100)
        ]
        mock_exchange.fetch_my_trades.return_value = []

        with patch('exchange.ccxt.binance', return_value=mock_exchange):
            from strategy import get_strategy_status

            status = get_strategy_status()

            assert 'mode' in status
            assert 'total_value' in status
            assert 'positions' in status
            assert 'signals' in status


# =============================================================================
# Configuration Validation Tests
# =============================================================================

class TestConfigurationValidation:
    """Tests for configuration validation"""

    def test_strategy_parameters_are_valid(self):
        """Strategy parameters should have valid values"""
        from strategy import (
            RSI_OVERSOLD,
            RSI_OVERBOUGHT,
            RSI_PERIOD,
            MAX_POSITIONS,
            MAX_POSITION_USDT
        )

        assert 0 < RSI_OVERSOLD < 50
        assert 50 < RSI_OVERBOUGHT < 100
        assert RSI_PERIOD > 0
        assert MAX_POSITIONS > 0
        assert MAX_POSITION_USDT > 0

    def test_robust_strategy_parameters(self):
        """Robust strategy parameters should be valid"""
        from robust_strategy import (
            RSI_OVERSOLD,
            RSI_OVERBOUGHT,
            RSI_STRONG_OVERSOLD,
            RSI_STRONG_OVERBOUGHT,
            MAX_POSITIONS
        )

        assert RSI_STRONG_OVERSOLD < RSI_OVERSOLD
        assert RSI_OVERBOUGHT < RSI_STRONG_OVERBOUGHT
        assert MAX_POSITIONS > 0

    def test_aggressive_strategy_parameters(self):
        """Aggressive strategy parameters should be valid"""
        from aggressive_momentum_strategy import (
            MAX_SINGLE_POSITION_PCT,
            MAX_TOTAL_POSITION_PCT,
            HARD_STOP_LOSS_PCT,
            DAILY_LOSS_LIMIT_PCT,
            MAX_DRAWDOWN_PCT
        )

        assert 0 < MAX_SINGLE_POSITION_PCT <= 1.0
        assert MAX_SINGLE_POSITION_PCT <= MAX_TOTAL_POSITION_PCT
        assert HARD_STOP_LOSS_PCT > 0
        assert DAILY_LOSS_LIMIT_PCT > HARD_STOP_LOSS_PCT
        assert MAX_DRAWDOWN_PCT > DAILY_LOSS_LIMIT_PCT


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
