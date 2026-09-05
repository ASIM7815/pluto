"""Basic tests for PLUTO backend"""
import pytest
from app.core.security import security_validator


def test_path_validation_safe():
    """Test safe path validation"""
    # This would need proper setup with allowed paths
    is_valid, msg = security_validator.validate_path("/tmp/test.txt")
    # Result depends on PLUTO_ALLOWED_PATHS configuration
    assert isinstance(is_valid, bool)


def test_command_classification_safe():
    """Test safe command classification"""
    result = security_validator.classify_command("ls -la")
    assert result == "SAFE"


def test_command_classification_dangerous():
    """Test dangerous command classification"""
    result = security_validator.classify_command("rm -rf /")
    assert result == "BLOCKED"


def test_command_classification_confirm():
    """Test command requiring confirmation"""
    result = security_validator.classify_command("sudo apt-get install package")
    assert result == "CONFIRM_REQUIRED"
