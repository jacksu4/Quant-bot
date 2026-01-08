#!/usr/bin/env python3
"""
Minimal Binance Testnet Trading Bot
验证连接并执行简单交易
"""

import os
import ccxt
from dotenv import load_dotenv

load_dotenv()

def create_exchange():
    """创建Binance Testnet连接"""
    exchange = ccxt.binance({
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_API_SECRET'),
        'enableRateLimit': True,
        'options': {
            'defaultType': 'spot',
            'adjustForTimeDifference': True,
        },
    })
    # 手动设置testnet URLs
    exchange.set_sandbox_mode(True)
    return exchange

def check_balance(exchange):
    """查询账户余额"""
    print("\n=== 账户余额 ===")
    balance = exchange.fetch_balance()
    for currency in ['BTC', 'USDT', 'ETH', 'BNB']:
        if currency in balance['total'] and balance['total'][currency] > 0:
            print(f"{currency}: {balance['total'][currency]:.8f}")
    return balance

def get_price(exchange, symbol='BTC/USDT'):
    """获取当前价格"""
    ticker = exchange.fetch_ticker(symbol)
    print(f"\n=== {symbol} 当前价格 ===")
    print(f"买一价: {ticker['bid']}")
    print(f"卖一价: {ticker['ask']}")
    print(f"最新价: {ticker['last']}")
    return ticker

def place_test_order(exchange, symbol='BTC/USDT', amount=0.001):
    """执行测试市价买单"""
    print(f"\n=== 执行测试买单 ===")
    print(f"交易对: {symbol}")
    print(f"数量: {amount} BTC")

    try:
        order = exchange.create_market_buy_order(symbol, amount)
        print(f"订单ID: {order['id']}")
        print(f"状态: {order['status']}")
        print(f"成交价: {order.get('average', 'N/A')}")
        print(f"成交额: {order.get('cost', 'N/A')} USDT")
        return order
    except Exception as e:
        print(f"下单失败: {e}")
        return None

def main():
    print("=" * 50)
    print("Binance Testnet 量化Bot")
    print("=" * 50)

    # 创建交易所连接
    exchange = create_exchange()

    # 验证连接 - 获取服务器时间
    server_time = exchange.fetch_time()
    print(f"\n连接成功! 服务器时间: {server_time}")

    # 查询余额
    check_balance(exchange)

    # 获取BTC价格
    get_price(exchange)

    # 执行一个小的测试交易
    print("\n" + "=" * 50)
    confirm = input("是否执行测试买单? (y/n): ").strip().lower()
    if confirm == 'y':
        place_test_order(exchange, 'BTC/USDT', 0.001)
        print("\n=== 交易后余额 ===")
        check_balance(exchange)

    print("\n完成! 请前往 https://testnet.binance.vision 查看您的交易记录")

if __name__ == "__main__":
    main()
