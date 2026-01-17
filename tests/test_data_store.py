"""
Comprehensive tests for data_store.py module

Tests the data persistence and snapshot functionality.
"""

import pytest
import json
import os
import tempfile
import sys
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_store import (
    ensure_data_dir,
    load_snapshots,
    save_snapshots,
    add_snapshot,
    get_snapshots_in_range,
    get_latest_snapshot,
    get_first_snapshot,
    calculate_pnl,
    get_daily_values,
    DATA_FILE
)


class TestEnsureDataDir:
    """Tests for ensure_data_dir function"""

    def test_creates_directory(self, tmp_path):
        """Should create data directory if not exists"""
        with patch('data_store.os.makedirs') as mock_makedirs:
            ensure_data_dir()
            mock_makedirs.assert_called_once_with('data', exist_ok=True)


class TestLoadSnapshots:
    """Tests for load_snapshots function"""

    def test_load_empty_file(self, tmp_path):
        """Should return empty list when file doesn't exist"""
        with patch('data_store.DATA_FILE', str(tmp_path / 'nonexistent.json')):
            snapshots = load_snapshots()
            assert snapshots == []

    def test_load_valid_file(self, tmp_path):
        """Should load existing snapshots"""
        test_file = tmp_path / 'snapshots.json'
        test_data = [
            {'timestamp': '2024-01-01T00:00:00', 'total_value_usdt': 100}
        ]
        test_file.write_text(json.dumps(test_data))

        with patch('data_store.DATA_FILE', str(test_file)):
            snapshots = load_snapshots()
            assert len(snapshots) == 1
            assert snapshots[0]['total_value_usdt'] == 100

    def test_load_corrupted_file(self, tmp_path):
        """Should return empty list for corrupted file"""
        test_file = tmp_path / 'snapshots.json'
        test_file.write_text('not valid json{{{')

        with patch('data_store.DATA_FILE', str(test_file)):
            snapshots = load_snapshots()
            assert snapshots == []


class TestSaveSnapshots:
    """Tests for save_snapshots function"""

    def test_save_snapshots(self, tmp_path):
        """Should save snapshots to file"""
        test_file = tmp_path / 'snapshots.json'
        test_data = [
            {'timestamp': '2024-01-01T00:00:00', 'total_value_usdt': 100}
        ]

        with patch('data_store.DATA_FILE', str(test_file)):
            save_snapshots(test_data)

            with open(test_file, 'r') as f:
                loaded = json.load(f)

            assert len(loaded) == 1
            assert loaded[0]['total_value_usdt'] == 100


class TestAddSnapshot:
    """Tests for add_snapshot function"""

    def test_add_snapshot_creates_entry(self, tmp_path):
        """Should add new snapshot with timestamp"""
        test_file = tmp_path / 'snapshots.json'
        test_file.write_text('[]')

        with patch('data_store.DATA_FILE', str(test_file)):
            balance = {'USDT': {'total': 100, 'free': 100, 'used': 0}}
            prices = {'BTC/USDT': {'last': 50000}}

            snapshot = add_snapshot(100.0, balance, prices)

            assert 'timestamp' in snapshot
            assert snapshot['total_value_usdt'] == 100.0

    def test_add_snapshot_preserves_existing(self, tmp_path):
        """Should preserve existing snapshots when adding new one"""
        test_file = tmp_path / 'snapshots.json'
        existing = [{'timestamp': '2024-01-01T00:00:00', 'total_value_usdt': 90}]
        test_file.write_text(json.dumps(existing))

        with patch('data_store.DATA_FILE', str(test_file)):
            balance = {}
            prices = {}
            add_snapshot(100.0, balance, prices)

            with open(test_file, 'r') as f:
                data = json.load(f)

            assert len(data) == 2


class TestGetSnapshotsInRange:
    """Tests for get_snapshots_in_range function"""

    def test_get_recent_snapshots(self, tmp_path):
        """Should return snapshots within time range"""
        test_file = tmp_path / 'snapshots.json'
        now = datetime.now()

        snapshots = [
            {'timestamp': (now - timedelta(days=1)).isoformat(), 'total_value_usdt': 100},
            {'timestamp': (now - timedelta(days=5)).isoformat(), 'total_value_usdt': 95},
            {'timestamp': (now - timedelta(days=40)).isoformat(), 'total_value_usdt': 90},
        ]
        test_file.write_text(json.dumps(snapshots))

        with patch('data_store.DATA_FILE', str(test_file)):
            result = get_snapshots_in_range(days=7)

            # Should only return snapshots within 7 days
            assert len(result) == 2

    def test_get_all_snapshots(self, tmp_path):
        """Should return all snapshots for large range"""
        test_file = tmp_path / 'snapshots.json'
        now = datetime.now()

        snapshots = [
            {'timestamp': (now - timedelta(days=i)).isoformat(), 'total_value_usdt': 100+i}
            for i in range(10)
        ]
        test_file.write_text(json.dumps(snapshots))

        with patch('data_store.DATA_FILE', str(test_file)):
            result = get_snapshots_in_range(days=30)

            assert len(result) == 10

    def test_empty_when_no_data(self, tmp_path):
        """Should return empty list when no snapshots"""
        test_file = tmp_path / 'nonexistent.json'

        with patch('data_store.DATA_FILE', str(test_file)):
            result = get_snapshots_in_range(days=30)

            assert result == []


class TestGetLatestSnapshot:
    """Tests for get_latest_snapshot function"""

    def test_get_latest(self, tmp_path):
        """Should return most recent snapshot"""
        test_file = tmp_path / 'snapshots.json'
        snapshots = [
            {'timestamp': '2024-01-01T00:00:00', 'total_value_usdt': 100},
            {'timestamp': '2024-01-02T00:00:00', 'total_value_usdt': 110},
        ]
        test_file.write_text(json.dumps(snapshots))

        with patch('data_store.DATA_FILE', str(test_file)):
            latest = get_latest_snapshot()

            assert latest['total_value_usdt'] == 110

    def test_none_when_empty(self, tmp_path):
        """Should return None when no snapshots"""
        test_file = tmp_path / 'nonexistent.json'

        with patch('data_store.DATA_FILE', str(test_file)):
            latest = get_latest_snapshot()

            assert latest is None


class TestGetFirstSnapshot:
    """Tests for get_first_snapshot function"""

    def test_get_first(self, tmp_path):
        """Should return oldest snapshot"""
        test_file = tmp_path / 'snapshots.json'
        snapshots = [
            {'timestamp': '2024-01-01T00:00:00', 'total_value_usdt': 100},
            {'timestamp': '2024-01-02T00:00:00', 'total_value_usdt': 110},
        ]
        test_file.write_text(json.dumps(snapshots))

        with patch('data_store.DATA_FILE', str(test_file)):
            first = get_first_snapshot()

            assert first['total_value_usdt'] == 100

    def test_none_when_empty(self, tmp_path):
        """Should return None when no snapshots"""
        test_file = tmp_path / 'nonexistent.json'

        with patch('data_store.DATA_FILE', str(test_file)):
            first = get_first_snapshot()

            assert first is None


class TestCalculatePnl:
    """Tests for calculate_pnl function"""

    def test_calculate_profit(self, tmp_path):
        """Should calculate positive P&L correctly"""
        test_file = tmp_path / 'snapshots.json'
        now = datetime.now()
        snapshots = [
            {'timestamp': (now - timedelta(days=5)).isoformat(), 'total_value_usdt': 100},
            {'timestamp': now.isoformat(), 'total_value_usdt': 110},
        ]
        test_file.write_text(json.dumps(snapshots))

        with patch('data_store.DATA_FILE', str(test_file)):
            result = calculate_pnl(current_value=120, period_days=7)

            assert result['has_data'] == True
            assert result['pnl'] == 20  # 120 - 100
            assert result['pnl_percent'] == 20.0  # 20/100 * 100

    def test_calculate_loss(self, tmp_path):
        """Should calculate negative P&L correctly"""
        test_file = tmp_path / 'snapshots.json'
        now = datetime.now()
        snapshots = [
            {'timestamp': (now - timedelta(days=5)).isoformat(), 'total_value_usdt': 100},
        ]
        test_file.write_text(json.dumps(snapshots))

        with patch('data_store.DATA_FILE', str(test_file)):
            result = calculate_pnl(current_value=80, period_days=7)

            assert result['has_data'] == True
            assert result['pnl'] == -20  # 80 - 100
            assert result['pnl_percent'] == -20.0

    def test_no_data_available(self, tmp_path):
        """Should return default when no data"""
        test_file = tmp_path / 'nonexistent.json'

        with patch('data_store.DATA_FILE', str(test_file)):
            result = calculate_pnl(current_value=100, period_days=7)

            assert result['has_data'] == False
            assert result['pnl'] == 0


class TestGetDailyValues:
    """Tests for get_daily_values function"""

    def test_get_daily_aggregation(self, tmp_path):
        """Should aggregate multiple snapshots per day"""
        test_file = tmp_path / 'snapshots.json'
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')

        snapshots = [
            {'timestamp': f'{today}T10:00:00', 'total_value_usdt': 100},
            {'timestamp': f'{today}T12:00:00', 'total_value_usdt': 105},
            {'timestamp': f'{today}T14:00:00', 'total_value_usdt': 110},
        ]
        test_file.write_text(json.dumps(snapshots))

        with patch('data_store.DATA_FILE', str(test_file)):
            result = get_daily_values(days=7)

            # Should have only 1 day (latest value of that day)
            assert len(result) == 1
            assert result[0]['value'] == 110  # Latest value of the day

    def test_multiple_days(self, tmp_path):
        """Should return values for multiple days"""
        test_file = tmp_path / 'snapshots.json'
        now = datetime.now()

        snapshots = [
            {'timestamp': (now - timedelta(days=2)).isoformat(), 'total_value_usdt': 100},
            {'timestamp': (now - timedelta(days=1)).isoformat(), 'total_value_usdt': 105},
            {'timestamp': now.isoformat(), 'total_value_usdt': 110},
        ]
        test_file.write_text(json.dumps(snapshots))

        with patch('data_store.DATA_FILE', str(test_file)):
            result = get_daily_values(days=7)

            # Should have 3 days
            assert len(result) == 3

    def test_sorted_by_date(self, tmp_path):
        """Should return values sorted by date"""
        test_file = tmp_path / 'snapshots.json'
        now = datetime.now()

        # Add in non-chronological order
        snapshots = [
            {'timestamp': (now - timedelta(days=1)).isoformat(), 'total_value_usdt': 105},
            {'timestamp': (now - timedelta(days=2)).isoformat(), 'total_value_usdt': 100},
            {'timestamp': now.isoformat(), 'total_value_usdt': 110},
        ]
        test_file.write_text(json.dumps(snapshots))

        with patch('data_store.DATA_FILE', str(test_file)):
            result = get_daily_values(days=7)

            # Should be sorted chronologically
            assert result[0]['value'] == 100
            assert result[1]['value'] == 105
            assert result[2]['value'] == 110

    def test_empty_when_no_data(self, tmp_path):
        """Should return empty list when no data"""
        test_file = tmp_path / 'nonexistent.json'

        with patch('data_store.DATA_FILE', str(test_file)):
            result = get_daily_values(days=7)

            assert result == []


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
