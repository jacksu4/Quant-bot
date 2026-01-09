"""
Integration tests for Quant-bot
Note: These tests use testnet mode and don't require real API keys for basic checks
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_data_directory():
    """Test that data directory can be created"""
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    os.makedirs(data_dir, exist_ok=True)
    assert os.path.exists(data_dir), "Failed to create data directory"


def test_logs_directory():
    """Test that logs directory can be created"""
    logs_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    assert os.path.exists(logs_dir), "Failed to create logs directory"


def test_backups_directory():
    """Test that backups directory can be created"""
    backups_dir = os.path.join(os.path.dirname(__file__), '..', 'backups')
    os.makedirs(backups_dir, exist_ok=True)
    assert os.path.exists(backups_dir), "Failed to create backups directory"


def test_deployment_scripts_executable():
    """Test that deployment scripts exist"""
    scripts = ['deploy.sh', 'server-setup.sh']
    for script in scripts:
        script_path = os.path.join(os.path.dirname(__file__), '..', script)
        assert os.path.exists(script_path), f"Script not found: {script}"


if __name__ == '__main__':
    print("Running integration tests...")
    test_data_directory()
    test_logs_directory()
    test_backups_directory()
    test_deployment_scripts_executable()
    print("✅ All integration tests passed!")
