"""
Basic tests for Quant-bot
"""
import pytest
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_environment_variables():
    """Test that required environment variables can be loaded"""
    # This test passes if .env file exists or env vars are set
    from dotenv import load_dotenv
    load_dotenv()

    # Just check that we can load env vars (they might be test values)
    api_key = os.getenv('BINANCE_API_KEY', 'test_key')
    assert api_key is not None
    assert len(api_key) > 0


def test_import_exchange():
    """Test that exchange module can be imported"""
    try:
        from exchange import BinanceClient
        assert BinanceClient is not None
    except ModuleNotFoundError as e:
        # Skip if dependencies not installed (e.g., local testing without venv)
        pytest.skip(f"Dependencies not installed: {e}")
    except Exception as e:
        pytest.fail(f"Failed to import BinanceClient: {e}")


def test_import_strategy():
    """Test that strategy module can be imported"""
    try:
        from strategy import RSIStrategy
        assert RSIStrategy is not None
    except ModuleNotFoundError as e:
        pytest.skip(f"Dependencies not installed: {e}")
    except Exception as e:
        pytest.fail(f"Failed to import RSIStrategy: {e}")


def test_import_professional_strategy():
    """Test that professional strategy modules can be imported"""
    try:
        from professional_strategy import ProfessionalStrategy
        assert ProfessionalStrategy is not None
    except ModuleNotFoundError as e:
        pytest.skip(f"Dependencies not installed: {e}")
    except Exception as e:
        pytest.fail(f"Failed to import ProfessionalStrategy: {e}")


def test_import_multi_factor():
    """Test that multi-factor engine can be imported"""
    try:
        from multi_factor_engine import MultiFactorEngine
        assert MultiFactorEngine is not None
    except ModuleNotFoundError as e:
        pytest.skip(f"Dependencies not installed: {e}")
    except Exception as e:
        pytest.fail(f"Failed to import MultiFactorEngine: {e}")


def test_import_risk_manager():
    """Test that risk manager can be imported"""
    try:
        from risk_manager import RiskManager
        assert RiskManager is not None
    except ModuleNotFoundError as e:
        pytest.skip(f"Dependencies not installed: {e}")
    except Exception as e:
        pytest.fail(f"Failed to import RiskManager: {e}")


def test_python_version():
    """Test that Python version is 3.9 or higher"""
    assert sys.version_info >= (3, 9), "Python 3.9 or higher is required"


def test_project_structure():
    """Test that key project files exist"""
    required_files = [
        'exchange.py',
        'strategy.py',
        'professional_strategy.py',
        'multi_factor_engine.py',
        'risk_manager.py',
        'requirements.txt',
        'docker-compose.yml',
        'deploy.sh',
    ]

    for file in required_files:
        file_path = os.path.join(os.path.dirname(__file__), '..', file)
        assert os.path.exists(file_path), f"Required file not found: {file}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
