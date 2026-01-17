"""
Exchange API Wrapper Module / 交易所API封装模块

Supports both live trading and testnet modes for Binance exchange.
支持Binance交易所的真实交易和测试网模式。

Key Features / 核心功能:
- Automatic testnet/live mode switching based on TRADING_MODE env var
- RSI calculation for trading signals
- Position management and P&L tracking
- Market order execution (buy/sell)
- Balance and ticker queries

Usage / 使用方法:
    from exchange import BinanceClient
    client = BinanceClient()
    print(client.get_mode_str())  # Check current mode
    balance = client.get_balance()  # Get account balance
"""

import os
import ccxt
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# 白名单交易对
WHITELIST_SYMBOLS = ['BTC/USDT', 'SOL/USDT', 'XRP/USDT', 'BNB/USDT', 'ETH/USDT']


class BinanceClient:
    """Binance 客户端 - 支持真实交易和测试网"""

    def __init__(self):
        trading_mode = os.getenv('TRADING_MODE', 'testnet')

        self.exchange = ccxt.binance({
            'apiKey': os.getenv('BINANCE_API_KEY'),
            'secret': os.getenv('BINANCE_API_SECRET'),
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'adjustForTimeDifference': True,
            },
        })

        self.is_live = trading_mode == 'live'

        if not self.is_live:
            self.exchange.set_sandbox_mode(True)

        self.whitelist = WHITELIST_SYMBOLS

    def get_mode_str(self) -> str:
        """返回当前模式字符串"""
        return "🔴 真实交易" if self.is_live else "🟢 测试网"

    def get_balance(self) -> dict:
        """获取账户余额"""
        balance = self.exchange.fetch_balance()
        result = {}

        # 获取所有非零余额
        for currency in balance['total']:
            if balance['total'][currency] > 0:
                result[currency] = {
                    'total': balance['total'][currency],
                    'free': balance['free'][currency],
                    'used': balance['used'][currency],
                }
        return result

    def get_usdt_balance(self) -> float:
        """获取USDT可用余额"""
        balance = self.exchange.fetch_balance()
        return balance['free'].get('USDT', 0)

    def get_ticker(self, symbol: str) -> dict:
        """获取当前价格"""
        return self.exchange.fetch_ticker(symbol)

    def get_all_tickers(self) -> dict:
        """获取白名单交易对价格"""
        return {
            symbol: ticker
            for symbol in self.whitelist
            if (ticker := self._safe_call(lambda s=symbol: self.exchange.fetch_ticker(s))) is not None
        }

    def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> list:
        """
        获取K线数据
        timeframe: '1m', '5m', '15m', '1h', '4h', '1d'
        返回: [[timestamp, open, high, low, close, volume], ...]
        """
        try:
            return self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        except Exception as e:
            print(f"获取K线失败 {symbol}: {e}")
            return []

    def calculate_rsi(self, symbol: str, period: int = 14, timeframe: str = '1h') -> float:
        """计算RSI指标"""
        ohlcv = self.get_ohlcv(symbol, timeframe, limit=period + 10)
        if len(ohlcv) < period + 1:
            return 50.0

        closes = [candle[4] for candle in ohlcv]
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]

        gains = [max(d, 0) for d in deltas[-period:]]
        losses = [abs(min(d, 0)) for d in deltas[-period:]]

        avg_gain, avg_loss = sum(gains) / period, sum(losses) / period

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rsi = 100 - (100 / (1 + avg_gain / avg_loss))
        return round(rsi, 2)

    def get_all_rsi(self, timeframe: str = '1h') -> dict:
        """获取所有白名单币种的RSI"""
        rsi_data = {}
        for symbol in self.whitelist:
            rsi_data[symbol] = self._safe_call(
                lambda s=symbol: self.calculate_rsi(s, timeframe=timeframe),
                default=50.0
            )
        return rsi_data

    def _safe_call(self, func, default=None):
        """安全执行函数，失败时返回默认值"""
        try:
            return func()
        except Exception:
            return default

    def get_trades(self, symbol: str, limit: int = 50) -> list:
        """获取交易历史"""
        return self._safe_call(lambda: self.exchange.fetch_my_trades(symbol, limit=limit), [])

    def get_all_trades(self, limit: int = 50) -> list:
        """获取所有交易对的交易历史"""
        all_trades = [
            trade
            for symbol in self.whitelist
            if (trades := self._safe_call(lambda s=symbol: self.exchange.fetch_my_trades(s, limit=limit), []))
            for trade in trades
        ]
        return sorted(all_trades, key=lambda x: x['timestamp'], reverse=True)

    def get_open_orders(self, symbol: str = None) -> list:
        """获取未成交订单"""
        return self._safe_call(
            lambda: self.exchange.fetch_open_orders(symbol) if symbol else self.exchange.fetch_open_orders(),
            []
        )

    def create_market_buy(self, symbol: str, amount: float) -> dict:
        """市价买入（按币种数量）"""
        return self.exchange.create_market_buy_order(symbol, amount)

    def create_market_buy_usdt(self, symbol: str, usdt_amount: float) -> dict:
        """市价买入（按USDT金额）"""
        ticker = self.get_ticker(symbol)
        price = ticker.get('ask')  # 使用卖一价

        # 验证价格有效
        if price is None or price <= 0:
            raise ValueError(f"Invalid price for {symbol}: {price}")

        amount = usdt_amount / price

        # 获取交易对精度
        market = self.exchange.market(symbol)
        amount = self.exchange.amount_to_precision(symbol, amount)

        return self.exchange.create_market_buy_order(symbol, float(amount))

    def create_market_sell(self, symbol: str, amount: float) -> dict:
        """市价卖出"""
        market = self.exchange.market(symbol)
        amount = self.exchange.amount_to_precision(symbol, amount)
        return self.exchange.create_market_sell_order(symbol, float(amount))

    def calculate_total_value_usdt(self, balance: dict = None, tickers: dict = None) -> float:
        """计算总资产价值（USDT计价）"""
        if balance is None:
            balance = self.get_balance()
        if tickers is None:
            tickers = self.get_all_tickers()

        total = 0.0

        for currency, info in balance.items():
            amount = info['total']
            if currency == 'USDT':
                total += amount
            elif currency == 'BUSD':
                total += amount
            else:
                symbol = f"{currency}/USDT"
                if symbol in tickers:
                    price = tickers[symbol]['last']
                    total += amount * price

        return total

    def get_position(self, symbol: str) -> dict:
        """
        获取某个交易对的持仓信息
        返回: {currency, amount, avg_price, current_price, pnl, pnl_percent}
        """
        currency = symbol.split('/')[0]
        balance = self.get_balance()

        if currency not in balance or balance[currency]['total'] <= 0:
            return None

        amount = balance[currency]['total']
        ticker = self.get_ticker(symbol)
        current_price = ticker['last']

        # 从最近交易估算平均成本
        trades = self.get_trades(symbol, limit=10)
        buy_trades = [t for t in trades if t['side'] == 'buy']

        if buy_trades:
            # 加权平均价格
            total_cost = sum(t['cost'] for t in buy_trades)
            total_amount = sum(t['amount'] for t in buy_trades)
            avg_price = total_cost / total_amount if total_amount > 0 else current_price
        else:
            avg_price = current_price

        current_value = amount * current_price
        cost_value = amount * avg_price
        pnl = current_value - cost_value
        pnl_percent = (pnl / cost_value * 100) if cost_value > 0 else 0

        return {
            'currency': currency,
            'symbol': symbol,
            'amount': amount,
            'avg_price': avg_price,
            'current_price': current_price,
            'current_value': current_value,
            'pnl': pnl,
            'pnl_percent': pnl_percent,
        }

    def get_all_positions(self) -> list:
        """获取所有持仓"""
        positions = []
        for symbol in self.whitelist:
            pos = self.get_position(symbol)
            if pos and pos['amount'] > 0:
                positions.append(pos)
        return positions

    def get_min_order_amount(self, symbol: str) -> float:
        """获取最小下单数量"""
        market = self.exchange.market(symbol)
        return market['limits']['amount']['min']

    def get_min_order_usdt(self, symbol: str) -> float:
        """获取最小下单金额(USDT)"""
        market = self.exchange.market(symbol)
        min_cost = market['limits']['cost']['min'] if market['limits']['cost']['min'] else 5.0
        return min_cost
