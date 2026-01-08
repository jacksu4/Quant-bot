"""
数据存储模块 - 记录资产快照用于计算收益
使用JSON文件存储，简单可靠
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional

DATA_FILE = 'data/snapshots.json'


def ensure_data_dir():
    """确保数据目录存在"""
    os.makedirs('data', exist_ok=True)


def load_snapshots() -> list:
    """加载所有快照数据"""
    ensure_data_dir()
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_snapshots(snapshots: list):
    """保存快照数据"""
    ensure_data_dir()
    with open(DATA_FILE, 'w') as f:
        json.dump(snapshots, f, indent=2, default=str)


def add_snapshot(total_value_usdt: float, balance: dict, prices: dict):
    """添加一条资产快照"""
    snapshots = load_snapshots()

    snapshot = {
        'timestamp': datetime.now().isoformat(),
        'total_value_usdt': total_value_usdt,
        'balance': balance,
        'prices': {k: v.get('last', 0) if isinstance(v, dict) else v for k, v in prices.items()},
    }

    snapshots.append(snapshot)
    save_snapshots(snapshots)
    return snapshot


def get_snapshots_in_range(days: int = 30) -> list:
    """获取指定天数内的快照"""
    snapshots = load_snapshots()
    if not snapshots:
        return []

    cutoff = datetime.now() - timedelta(days=days)

    result = []
    for snap in snapshots:
        try:
            ts = datetime.fromisoformat(snap['timestamp'])
            if ts >= cutoff:
                result.append(snap)
        except (ValueError, KeyError):
            continue

    return result


def get_latest_snapshot() -> Optional[dict]:
    """获取最新快照"""
    snapshots = load_snapshots()
    if not snapshots:
        return None
    return snapshots[-1]


def get_first_snapshot() -> Optional[dict]:
    """获取第一条快照"""
    snapshots = load_snapshots()
    if not snapshots:
        return None
    return snapshots[0]


def calculate_pnl(current_value: float, period_days: int) -> dict:
    """
    计算指定周期的盈亏

    返回:
    - pnl: 盈亏金额
    - pnl_percent: 盈亏百分比
    - start_value: 期初价值
    """
    snapshots = get_snapshots_in_range(period_days)

    if not snapshots:
        return {
            'pnl': 0,
            'pnl_percent': 0,
            'start_value': current_value,
            'has_data': False,
        }

    start_value = snapshots[0]['total_value_usdt']
    pnl = current_value - start_value
    pnl_percent = (pnl / start_value * 100) if start_value > 0 else 0

    return {
        'pnl': pnl,
        'pnl_percent': pnl_percent,
        'start_value': start_value,
        'has_data': True,
    }


def get_daily_values(days: int = 30) -> list:
    """
    获取每日资产价值（用于绘制曲线图）
    返回每天最后一条快照的价值
    """
    snapshots = get_snapshots_in_range(days)

    if not snapshots:
        return []

    # 按日期分组，取每天最后一条
    daily = {}
    for snap in snapshots:
        try:
            ts = datetime.fromisoformat(snap['timestamp'])
            date_key = ts.strftime('%Y-%m-%d')
            daily[date_key] = {
                'date': date_key,
                'value': snap['total_value_usdt'],
                'timestamp': snap['timestamp'],
            }
        except (ValueError, KeyError):
            continue

    # 按日期排序
    result = sorted(daily.values(), key=lambda x: x['date'])
    return result
