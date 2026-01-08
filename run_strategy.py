#!/usr/bin/env python3
"""
策略运行器 - 持续运行RSI均值回归策略

运行方式:
    python run_strategy.py              # 正常运行，每5分钟检查一次
    python run_strategy.py --once       # 只运行一次
    python run_strategy.py --interval 60 # 自定义检查间隔（秒）
"""

import argparse
import time
import signal
import sys
from datetime import datetime

from strategy import RSIMeanReversionStrategy, log_action
from exchange import BinanceClient

# 默认检查间隔（秒）
DEFAULT_INTERVAL = 300  # 5分钟

# 控制运行状态
running = True


def signal_handler(sig, frame):
    """处理Ctrl+C信号"""
    global running
    print("\n\n⚠️ 收到停止信号，正在安全退出...")
    running = False


def print_banner():
    """打印启动横幅"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║           🤖 RSI均值回归策略 - 自动交易系统                    ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║  策略逻辑:                                                    ║
║  • RSI < 30 (超卖) → 买入信号                                 ║
║  • RSI > 70 (超买) → 卖出信号                                 ║
║  • 止损: -3%  止盈: +5%                                       ║
║                                                              ║
║  按 Ctrl+C 安全停止                                           ║
╚══════════════════════════════════════════════════════════════╝
    """)


def run_strategy_loop(interval: int = DEFAULT_INTERVAL, run_once: bool = False):
    """运行策略循环"""
    global running

    print_banner()

    # 初始化
    client = BinanceClient()
    strategy = RSIMeanReversionStrategy(client)

    print(f"📡 交易模式: {client.get_mode_str()}")
    print(f"⏱️  检查间隔: {interval} 秒")
    print(f"📅 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)

    # 记录启动
    log_action('STRATEGY_START', {
        'mode': 'live' if client.is_live else 'testnet',
        'interval': interval,
    })

    iteration = 0

    while running:
        iteration += 1

        try:
            # 执行策略
            result = strategy.run_once()

            if run_once:
                print("\n✅ 单次执行完成")
                break

            # 等待下一次检查
            print(f"\n⏳ 等待 {interval} 秒后进行下一次检查...")
            print(f"   (下次检查时间: {datetime.now().strftime('%H:%M:%S')} + {interval}s)")

            # 分段睡眠，以便及时响应Ctrl+C
            for _ in range(interval):
                if not running:
                    break
                time.sleep(1)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
            log_action('ERROR', {'error': str(e), 'iteration': iteration})

            # 发生错误后等待一段时间再重试
            print(f"⏳ 等待 60 秒后重试...")
            for _ in range(60):
                if not running:
                    break
                time.sleep(1)

    # 记录停止
    log_action('STRATEGY_STOP', {
        'iterations': iteration,
        'reason': 'user_stop',
    })

    print("\n" + "=" * 60)
    print("👋 策略已安全停止")
    print(f"   总运行次数: {iteration}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='RSI均值回归策略运行器')
    parser.add_argument('--once', action='store_true', help='只运行一次')
    parser.add_argument('--interval', type=int, default=DEFAULT_INTERVAL,
                        help=f'检查间隔（秒），默认 {DEFAULT_INTERVAL}')

    args = parser.parse_args()

    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    run_strategy_loop(interval=args.interval, run_once=args.once)


if __name__ == "__main__":
    main()
