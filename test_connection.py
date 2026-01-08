#!/usr/bin/env python3
"""
测试API连接和账户状态
"""

from exchange import BinanceClient

def main():
    print("=" * 60)
    print("Binance API 连接测试")
    print("=" * 60)

    client = BinanceClient()
    print(f"\n模式: {client.get_mode_str()}")

    # 测试余额
    print("\n--- 账户余额 ---")
    balance = client.get_balance()
    for currency, info in balance.items():
        print(f"{currency}: {info['total']:.8f} (可用: {info['free']:.8f})")

    usdt_free = client.get_usdt_balance()
    print(f"\nUSDT 可用余额: ${usdt_free:.2f}")

    # 测试价格
    print("\n--- 实时价格 ---")
    tickers = client.get_all_tickers()
    for symbol, ticker in tickers.items():
        print(f"{symbol}: ${ticker['last']:,.2f}")

    # 测试RSI
    print("\n--- RSI 指标 (1小时) ---")
    rsi_data = client.get_all_rsi('1h')
    for symbol, rsi in sorted(rsi_data.items(), key=lambda x: x[1]):
        status = "🟢超卖" if rsi < 30 else "🔴超买" if rsi > 70 else "⚪中性"
        print(f"{symbol}: RSI={rsi:.1f} {status}")

    # 计算总资产
    total = client.calculate_total_value_usdt(balance, tickers)
    print(f"\n总资产价值: ${total:.2f} USDT")

    print("\n" + "=" * 60)
    print("✅ API 连接成功!")
    print("=" * 60)

if __name__ == "__main__":
    main()
