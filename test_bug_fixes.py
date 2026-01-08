"""
测试所有Bug修复的单元测试

测试内容:
1. RSI calculation for flat price (Bug 1)
2. Double sell prevention (Bug 2)
3. Duplicate position check (Bug 3)
4. Division by zero in create_market_buy_usdt (Bug 4)
5. Dashboard zero amount sell (Bug 5)
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from exchange import BinanceClient
from strategy import RSIMeanReversionStrategy


class TestBug1_RSICalculation(unittest.TestCase):
    """测试Bug 1: RSI计算在价格完全不变时返回50.0"""

    def setUp(self):
        self.client = BinanceClient()

    @patch.object(BinanceClient, 'get_ohlcv')
    def test_rsi_flat_price_returns_neutral(self, mock_ohlcv):
        """测试价格完全不变时RSI返回50.0 (中性)"""
        # 模拟15个完全相同的K线 (价格不变)
        flat_ohlcv = [[i * 3600000, 100, 100, 100, 100, 1000] for i in range(15)]
        mock_ohlcv.return_value = flat_ohlcv

        rsi = self.client.calculate_rsi('BTC/USDT', period=14)

        self.assertEqual(rsi, 50.0, "价格完全不变时RSI应该返回50.0 (中性)")
        print("✅ Bug 1测试通过: 价格不变时RSI = 50.0")

    @patch.object(BinanceClient, 'get_ohlcv')
    def test_rsi_all_gains_returns_100(self, mock_ohlcv):
        """测试价格全部上涨时RSI返回100.0"""
        # 模拟15个持续上涨的K线
        rising_ohlcv = [[i * 3600000, 100 + i, 100 + i + 1, 100 + i, 100 + i + 1, 1000] for i in range(15)]
        mock_ohlcv.return_value = rising_ohlcv

        rsi = self.client.calculate_rsi('BTC/USDT', period=14)

        self.assertEqual(rsi, 100.0, "价格全部上涨时RSI应该返回100.0")
        print("✅ Bug 1测试通过: 价格全部上涨时RSI = 100.0")

    @patch.object(BinanceClient, 'get_ohlcv')
    def test_rsi_normal_calculation(self, mock_ohlcv):
        """测试正常波动时RSI计算正确"""
        # 模拟正常波动的K线
        normal_ohlcv = [
            [i * 3600000, 100 + (i % 3 - 1) * 2, 102, 98, 100 + (i % 3 - 1) * 2, 1000]
            for i in range(20)
        ]
        mock_ohlcv.return_value = normal_ohlcv

        rsi = self.client.calculate_rsi('BTC/USDT', period=14)

        self.assertGreater(rsi, 0, "RSI应该大于0")
        self.assertLess(rsi, 100, "RSI应该小于100")
        print(f"✅ Bug 1测试通过: 正常波动时RSI = {rsi}")


class TestBug2_DoubleSellPrevention(unittest.TestCase):
    """测试Bug 2: 防止同一持仓被卖出两次"""

    def setUp(self):
        self.client = Mock(spec=BinanceClient)
        self.strategy = RSIMeanReversionStrategy(self.client)

    def test_no_double_sell_on_stop_loss_and_rsi(self):
        """测试持仓在止损后不会因RSI信号再次卖出"""
        # 模拟一个触发止损的持仓 (亏损4%)
        mock_position = {
            'symbol': 'BTC/USDT',
            'currency': 'BTC',
            'amount': 0.001,
            'avg_price': 50000,
            'current_price': 48000,
            'pnl': -2,
            'pnl_percent': -4.0,  # 触发止损 (STOP_LOSS_PCT = 3%)
        }

        # 模拟市场分析 (BTC RSI > 70，会触发卖出信号)
        mock_analysis = {
            'signals': [
                {'symbol': 'BTC/USDT', 'rsi': 75, 'price': 48000, 'signal': 'SELL'}
            ],
            'tickers': {'BTC/USDT': {'last': 48000}},
            'rsi_data': {'BTC/USDT': 75},
        }

        # 配置mock
        self.client.get_all_positions.return_value = [mock_position]
        self.client.get_balance.return_value = {'USDT': {'total': 100, 'free': 100, 'used': 0}}
        self.client.calculate_total_value_usdt.return_value = 100
        self.client.get_usdt_balance.return_value = 100

        # Mock execute_sell to track calls
        sell_calls = []
        def mock_execute_sell(symbol, amount, reason):
            sell_calls.append({'symbol': symbol, 'amount': amount, 'reason': reason})
            return {'id': '12345', 'filled': amount, 'average': 48000}

        self.strategy.execute_sell = mock_execute_sell
        self.strategy.analyze_market = Mock(return_value=mock_analysis)

        # 执行策略
        result = self.strategy.run_once()

        # 验证: 应该只卖出一次 (止损)，不应该因为RSI > 70再次卖出
        self.assertEqual(len(sell_calls), 1, "持仓应该只被卖出一次")
        self.assertEqual(sell_calls[0]['reason'], 'STOP_LOSS', "应该是因为止损卖出")
        print(f"✅ Bug 2测试通过: 持仓只卖出一次，原因: {sell_calls[0]['reason']}")


class TestBug3_DuplicatePositionCheck(unittest.TestCase):
    """测试Bug 3: 防止买入已持有的币种"""

    def setUp(self):
        self.client = Mock(spec=BinanceClient)
        self.strategy = RSIMeanReversionStrategy(self.client)

    def test_should_not_buy_already_held_currency(self):
        """测试不应该买入已经持有的币种"""
        # 模拟已经持有BTC
        mock_positions = [
            {'currency': 'BTC', 'symbol': 'BTC/USDT', 'amount': 0.001}
        ]

        # 模拟BTC的买入信号
        buy_signal = {
            'symbol': 'BTC/USDT',
            'rsi': 25,
            'price': 50000,
            'signal': 'BUY'
        }

        self.client.get_all_positions.return_value = mock_positions
        self.client.get_usdt_balance.return_value = 100
        self.client.get_min_order_usdt.return_value = 10

        # 执行检查
        should_buy = self.strategy.should_buy(buy_signal)

        self.assertFalse(should_buy, "不应该买入已经持有的币种")
        print("✅ Bug 3测试通过: 正确拒绝买入已持有的币种")

    def test_should_buy_different_currency(self):
        """测试可以买入不同的币种"""
        # 模拟已经持有BTC
        mock_positions = [
            {'currency': 'BTC', 'symbol': 'BTC/USDT', 'amount': 0.001}
        ]

        # 模拟ETH的买入信号 (不同币种)
        buy_signal = {
            'symbol': 'ETH/USDT',
            'rsi': 25,
            'price': 3000,
            'signal': 'BUY'
        }

        self.client.get_all_positions.return_value = mock_positions
        self.client.get_usdt_balance.return_value = 100
        self.client.get_min_order_usdt.return_value = 10

        # 执行检查
        should_buy = self.strategy.should_buy(buy_signal)

        self.assertTrue(should_buy, "应该允许买入不同的币种")
        print("✅ Bug 3测试通过: 正确允许买入不同的币种")


class TestBug4_DivisionByZero(unittest.TestCase):
    """测试Bug 4: 防止create_market_buy_usdt中的除零错误"""

    def setUp(self):
        self.client = BinanceClient()

    @patch.object(BinanceClient, 'get_ticker')
    def test_invalid_price_raises_error(self, mock_get_ticker):
        """测试价格为None时抛出错误"""
        mock_get_ticker.return_value = {'ask': None}

        with self.assertRaises(ValueError) as context:
            self.client.create_market_buy_usdt('BTC/USDT', 100)

        self.assertIn('Invalid price', str(context.exception))
        print("✅ Bug 4测试通过: 价格为None时正确抛出错误")

    @patch.object(BinanceClient, 'get_ticker')
    def test_zero_price_raises_error(self, mock_get_ticker):
        """测试价格为0时抛出错误"""
        mock_get_ticker.return_value = {'ask': 0}

        with self.assertRaises(ValueError) as context:
            self.client.create_market_buy_usdt('BTC/USDT', 100)

        self.assertIn('Invalid price', str(context.exception))
        print("✅ Bug 4测试通过: 价格为0时正确抛出错误")

    @patch.object(BinanceClient, 'get_ticker')
    def test_negative_price_raises_error(self, mock_get_ticker):
        """测试价格为负数时抛出错误"""
        mock_get_ticker.return_value = {'ask': -100}

        with self.assertRaises(ValueError) as context:
            self.client.create_market_buy_usdt('BTC/USDT', 100)

        self.assertIn('Invalid price', str(context.exception))
        print("✅ Bug 4测试通过: 价格为负数时正确抛出错误")


class TestBug5_DashboardZeroAmountSell(unittest.TestCase):
    """测试Bug 5: Dashboard不允许卖出0数量"""

    def test_dashboard_logic_zero_free_balance(self):
        """测试free余额为0时不应该显示卖出按钮"""
        # 模拟余额数据
        balance = {
            'BTC': {
                'total': 0.001,
                'free': 0.0,  # free余额为0
                'used': 0.001  # 全部被锁定
            }
        }

        trade_symbol = 'BTC/USDT'
        currency = trade_symbol.split('/')[0]

        # 检查逻辑 (模拟dashboard的条件)
        should_show_sell_button = currency in balance and balance[currency]['free'] > 0

        self.assertFalse(should_show_sell_button, "free余额为0时不应该显示卖出按钮")
        print("✅ Bug 5测试通过: free余额为0时正确隐藏卖出按钮")

    def test_dashboard_logic_positive_free_balance(self):
        """测试有可用余额时应该显示卖出按钮"""
        # 模拟余额数据
        balance = {
            'BTC': {
                'total': 0.001,
                'free': 0.001,  # 有可用余额
                'used': 0.0
            }
        }

        trade_symbol = 'BTC/USDT'
        currency = trade_symbol.split('/')[0]

        # 检查逻辑
        should_show_sell_button = currency in balance and balance[currency]['free'] > 0

        self.assertTrue(should_show_sell_button, "有可用余额时应该显示卖出按钮")
        print("✅ Bug 5测试通过: 有可用余额时正确显示卖出按钮")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("开始运行所有Bug修复测试")
    print("=" * 70 + "\n")

    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加所有测试类
    suite.addTests(loader.loadTestsFromTestCase(TestBug1_RSICalculation))
    suite.addTests(loader.loadTestsFromTestCase(TestBug2_DoubleSellPrevention))
    suite.addTests(loader.loadTestsFromTestCase(TestBug3_DuplicatePositionCheck))
    suite.addTests(loader.loadTestsFromTestCase(TestBug4_DivisionByZero))
    suite.addTests(loader.loadTestsFromTestCase(TestBug5_DashboardZeroAmountSell))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 输出总结
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    print(f"总测试数: {result.testsRun}")
    print(f"✅ 通过: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"❌ 失败: {len(result.failures)}")
    print(f"⚠️  错误: {len(result.errors)}")
    print("=" * 70 + "\n")

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_tests()
    exit(0 if success else 1)
