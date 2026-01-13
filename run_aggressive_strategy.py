#!/usr/bin/env python3
"""
激进动量策略运行器 - 高收益追求版本

运行方式:
    python run_aggressive_strategy.py              # 正常运行，每60秒检查一次
    python run_aggressive_strategy.py --once       # 只运行一次
    python run_aggressive_strategy.py --interval 120 # 自定义检查间隔（秒）

目标: 2个月100%收益（高风险高回报）
"""

import argparse
import time
import signal
import sys
from datetime import datetime

from aggressive_momentum_strategy import AggressiveMomentumStrategy, log_action
from exchange import BinanceClient

# 默认检查间隔（秒）- 更频繁以捕捉更多机会
DEFAULT_INTERVAL = 60  # 1分钟

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
╔══════════════════════════════════════════════════════════════════════════╗
║                                                                          ║
║      ⚡ 激进动量策略 - 高收益追求版本                                      ║
║                                                                          ║
╠══════════════════════════════════════════════════════════════════════════╣
║  策略特点:                                                                ║
║  • 动量追踪 - 追涨最强势币种                                              ║
║  • 多因子选币 - 动量+RSI+MACD+趋势综合评分                                ║
║  • 激进仓位 - 高确定性信号时最高50%仓位                                    ║
║  • 快速轮动 - 每4小时评估换入更强币种                                      ║
║  • 跟踪止盈 - 锁定利润，最大化收益                                         ║
║                                                                          ║
║  目标: 月收益30-50%, 2个月翻倍                                            ║
║                                                                          ║
║  ⚠️  警告: 此策略风险极高，仅适用于能承受高风险的投资者                      ║
║                                                                          ║
║  按 Ctrl+C 安全停止                                                       ║
╚══════════════════════════════════════════════════════════════════════════╝
    """)


def run_strategy_loop(interval: int = DEFAULT_INTERVAL, run_once: bool = False):
    """运行策略循环"""
    global running

    print_banner()

    # 初始化
    client = BinanceClient()
    strategy = AggressiveMomentumStrategy(client)

    print(f"📡 交易模式: {client.get_mode_str()}")
    print(f"⏱️  检查间隔: {interval} 秒")
    print(f"📅 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 起始资金: ${client.get_usdt_balance():.2f} USDT")

    # 获取初始总资产
    balance = client.get_balance()
    tickers = client.get_all_tickers()
    total_value = client.calculate_total_value_usdt(balance, tickers)
    print(f"💎 总资产: ${total_value:.2f}")
    print("-" * 70)

    # 记录启动
    log_action('STRATEGY_START', {
        'strategy': 'aggressive_momentum',
        'mode': 'live' if client.is_live else 'testnet',
        'interval': interval,
        'initial_value': total_value,
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
            next_check = datetime.now().strftime('%H:%M:%S')
            print(f"   (下次检查时间: {next_check} + {interval}s)")

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
            print(f"⏳ 等待 30 秒后重试...")
            for _ in range(30):
                if not running:
                    break
                time.sleep(1)

    # 记录停止
    log_action('STRATEGY_STOP', {
        'strategy': 'aggressive_momentum',
        'iterations': iteration,
        'reason': 'user_stop',
    })

    print("\n" + "=" * 70)
    print("👋 策略已安全停止")
    print(f"   总运行次数: {iteration}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description='激进动量策略运行器')
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
