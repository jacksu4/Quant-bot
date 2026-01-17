"""
Comprehensive tests for exchange.py module

Tests the BinanceClient class for all trading operations.
Uses mocking to avoid actual API calls.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from exchange import BinanceClient, WHITELIST_SYMBOLS


class TestBinanceClientInit:
    """Tests for BinanceClient initialization"""

    @patch.dict(os.environ, {'TRADING_MODE': 'testnet'})
    def test_init_testnet_mode(self):
        """Client should be in testnet mode when TRADING_MODE=testnet"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange

            client = BinanceClient()

            assert client.is_live == False
            mock_exchange.set_sandbox_mode.assert_called_once_with(True)

    @patch.dict(os.environ, {'TRADING_MODE': 'live'})
    def test_init_live_mode(self):
        """Client should be in live mode when TRADING_MODE=live"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange

            client = BinanceClient()

            assert client.is_live == True
            mock_exchange.set_sandbox_mode.assert_not_called()

    def test_whitelist_loaded(self):
        """Client should have whitelist symbols loaded"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange

            client = BinanceClient()

            assert len(client.whitelist) == len(WHITELIST_SYMBOLS)
            assert 'BTC/USDT' in client.whitelist


class TestGetModeStr:
    """Tests for get_mode_str method"""

    def test_mode_str_testnet(self):
        """Should return testnet indicator when not live"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange

            client = BinanceClient()
            client.is_live = False

            mode_str = client.get_mode_str()

            assert "测试网" in mode_str

    def test_mode_str_live(self):
        """Should return live indicator when in live mode"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange

            client = BinanceClient()
            client.is_live = True

            mode_str = client.get_mode_str()

            assert "真实交易" in mode_str


class TestGetBalance:
    """Tests for get_balance method"""

    def test_get_balance_filters_zero(self):
        """Should only return non-zero balances"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_exchange.fetch_balance.return_value = {
                'total': {'USDT': 100, 'BTC': 0, 'ETH': 0.5},
                'free': {'USDT': 100, 'BTC': 0, 'ETH': 0.5},
                'used': {'USDT': 0, 'BTC': 0, 'ETH': 0},
            }
            mock_binance.return_value = mock_exchange

            client = BinanceClient()
            balance = client.get_balance()

            assert 'USDT' in balance
            assert 'ETH' in balance
            assert 'BTC' not in balance  # Zero balance should be excluded

    def test_get_balance_structure(self):
        """Balance should have total, free, used keys"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_exchange.fetch_balance.return_value = {
                'total': {'USDT': 100},
                'free': {'USDT': 80},
                'used': {'USDT': 20},
            }
            mock_binance.return_value = mock_exchange

            client = BinanceClient()
            balance = client.get_balance()

            assert balance['USDT']['total'] == 100
            assert balance['USDT']['free'] == 80
            assert balance['USDT']['used'] == 20


class TestGetUsdtBalance:
    """Tests for get_usdt_balance method"""

    def test_get_usdt_balance(self):
        """Should return free USDT balance"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_exchange.fetch_balance.return_value = {
                'free': {'USDT': 150.5}
            }
            mock_binance.return_value = mock_exchange

            client = BinanceClient()
            usdt = client.get_usdt_balance()

            assert usdt == 150.5

    def test_get_usdt_balance_zero(self):
        """Should return 0 if no USDT"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_exchange.fetch_balance.return_value = {
                'free': {}
            }
            mock_binance.return_value = mock_exchange

            client = BinanceClient()
            usdt = client.get_usdt_balance()

            assert usdt == 0


class TestGetOhlcv:
    """Tests for get_ohlcv method"""

    def test_get_ohlcv_success(self):
        """Should return OHLCV data"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_ohlcv = [
                [1234567890000, 100, 105, 95, 102, 1000],
                [1234567890001, 102, 108, 100, 106, 1200],
            ]
            mock_exchange.fetch_ohlcv.return_value = mock_ohlcv
            mock_binance.return_value = mock_exchange

            client = BinanceClient()
            ohlcv = client.get_ohlcv('BTC/USDT', '1h', 100)

            assert len(ohlcv) == 2
            assert ohlcv[0][4] == 102  # Close price

    def test_get_ohlcv_failure(self):
        """Should return empty list on failure"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_exchange.fetch_ohlcv.side_effect = Exception("API Error")
            mock_binance.return_value = mock_exchange

            client = BinanceClient()
            ohlcv = client.get_ohlcv('BTC/USDT', '1h', 100)

            assert ohlcv == []


class TestCalculateRSI:
    """Tests for calculate_rsi method"""

    def test_rsi_normal_calculation(self):
        """RSI should be calculated correctly"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            # Create OHLCV with increasing prices
            mock_ohlcv = [
                [i, 100+i, 105+i, 95+i, 100+i, 1000] for i in range(25)
            ]
            mock_exchange.fetch_ohlcv.return_value = mock_ohlcv
            mock_binance.return_value = mock_exchange

            client = BinanceClient()
            rsi = client.calculate_rsi('BTC/USDT', period=14)

            # RSI for all-gains should be 100
            assert rsi == 100.0

    def test_rsi_flat_prices(self):
        """RSI should be 50 for flat prices"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            # All prices are 100
            mock_ohlcv = [
                [i, 100, 100, 100, 100, 1000] for i in range(25)
            ]
            mock_exchange.fetch_ohlcv.return_value = mock_ohlcv
            mock_binance.return_value = mock_exchange

            client = BinanceClient()
            rsi = client.calculate_rsi('BTC/USDT', period=14)

            assert rsi == 50.0

    def test_rsi_insufficient_data(self):
        """RSI should return 50 with insufficient data"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_ohlcv = [
                [i, 100, 100, 100, 100, 1000] for i in range(5)
            ]
            mock_exchange.fetch_ohlcv.return_value = mock_ohlcv
            mock_binance.return_value = mock_exchange

            client = BinanceClient()
            rsi = client.calculate_rsi('BTC/USDT', period=14)

            assert rsi == 50.0


class TestMarketOrders:
    """Tests for market order methods"""

    def test_create_market_buy_usdt_valid_price(self):
        """Should create buy order with valid price"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_exchange.fetch_ticker.return_value = {'ask': 50000}
            mock_exchange.market.return_value = {}
            mock_exchange.amount_to_precision.return_value = '0.002'
            mock_exchange.create_market_buy_order.return_value = {
                'id': '12345',
                'filled': 0.002,
                'average': 50000
            }
            mock_binance.return_value = mock_exchange

            client = BinanceClient()
            order = client.create_market_buy_usdt('BTC/USDT', 100)

            assert order['id'] == '12345'
            mock_exchange.create_market_buy_order.assert_called_once()

    def test_create_market_buy_usdt_invalid_price_none(self):
        """Should raise error when price is None"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_exchange.fetch_ticker.return_value = {'ask': None}
            mock_binance.return_value = mock_exchange

            client = BinanceClient()

            with pytest.raises(ValueError) as exc_info:
                client.create_market_buy_usdt('BTC/USDT', 100)

            assert 'Invalid price' in str(exc_info.value)

    def test_create_market_buy_usdt_invalid_price_zero(self):
        """Should raise error when price is 0"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_exchange.fetch_ticker.return_value = {'ask': 0}
            mock_binance.return_value = mock_exchange

            client = BinanceClient()

            with pytest.raises(ValueError) as exc_info:
                client.create_market_buy_usdt('BTC/USDT', 100)

            assert 'Invalid price' in str(exc_info.value)

    def test_create_market_buy_usdt_invalid_price_negative(self):
        """Should raise error when price is negative"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_exchange.fetch_ticker.return_value = {'ask': -100}
            mock_binance.return_value = mock_exchange

            client = BinanceClient()

            with pytest.raises(ValueError) as exc_info:
                client.create_market_buy_usdt('BTC/USDT', 100)

            assert 'Invalid price' in str(exc_info.value)

    def test_create_market_sell(self):
        """Should create sell order"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_exchange.market.return_value = {}
            mock_exchange.amount_to_precision.return_value = '0.002'
            mock_exchange.create_market_sell_order.return_value = {
                'id': '67890',
                'filled': 0.002,
                'average': 51000
            }
            mock_binance.return_value = mock_exchange

            client = BinanceClient()
            order = client.create_market_sell('BTC/USDT', 0.002)

            assert order['id'] == '67890'


class TestCalculateTotalValue:
    """Tests for calculate_total_value_usdt method"""

    def test_total_value_usdt_only(self):
        """Should return USDT amount when only USDT"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange

            client = BinanceClient()
            balance = {'USDT': {'total': 100, 'free': 100, 'used': 0}}
            tickers = {}

            total = client.calculate_total_value_usdt(balance, tickers)

            assert total == 100.0

    def test_total_value_with_crypto(self):
        """Should include crypto value"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange

            client = BinanceClient()
            balance = {
                'USDT': {'total': 100, 'free': 100, 'used': 0},
                'BTC': {'total': 0.001, 'free': 0.001, 'used': 0}
            }
            tickers = {'BTC/USDT': {'last': 50000}}

            total = client.calculate_total_value_usdt(balance, tickers)

            # 100 USDT + 0.001 BTC * 50000 = 100 + 50 = 150
            assert total == 150.0


class TestGetPosition:
    """Tests for get_position method"""

    def test_get_position_exists(self):
        """Should return position info when holding"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_exchange.fetch_balance.return_value = {
                'total': {'BTC': 0.001},
                'free': {'BTC': 0.001},
                'used': {'BTC': 0}
            }
            mock_exchange.fetch_ticker.return_value = {'last': 52000}
            mock_exchange.fetch_my_trades.return_value = [
                {'side': 'buy', 'cost': 50, 'amount': 0.001}
            ]
            mock_binance.return_value = mock_exchange

            client = BinanceClient()
            pos = client.get_position('BTC/USDT')

            assert pos is not None
            assert pos['currency'] == 'BTC'
            assert pos['amount'] == 0.001
            assert pos['current_price'] == 52000

    def test_get_position_not_exists(self):
        """Should return None when not holding"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_exchange.fetch_balance.return_value = {
                'total': {'BTC': 0},
                'free': {'BTC': 0},
                'used': {'BTC': 0}
            }
            mock_binance.return_value = mock_exchange

            client = BinanceClient()
            pos = client.get_position('BTC/USDT')

            assert pos is None


class TestGetMinOrder:
    """Tests for minimum order methods"""

    def test_get_min_order_amount(self):
        """Should return minimum order amount"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_exchange.market.return_value = {
                'limits': {'amount': {'min': 0.0001}}
            }
            mock_binance.return_value = mock_exchange

            client = BinanceClient()
            min_amount = client.get_min_order_amount('BTC/USDT')

            assert min_amount == 0.0001

    def test_get_min_order_usdt(self):
        """Should return minimum order in USDT"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_exchange.market.return_value = {
                'limits': {'cost': {'min': 10.0}}
            }
            mock_binance.return_value = mock_exchange

            client = BinanceClient()
            min_usdt = client.get_min_order_usdt('BTC/USDT')

            assert min_usdt == 10.0

    def test_get_min_order_usdt_default(self):
        """Should return default 5.0 when not specified"""
        with patch('exchange.ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_exchange.market.return_value = {
                'limits': {'cost': {'min': None}}
            }
            mock_binance.return_value = mock_exchange

            client = BinanceClient()
            min_usdt = client.get_min_order_usdt('BTC/USDT')

            assert min_usdt == 5.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
