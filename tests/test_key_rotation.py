"""Tests for KeyRotationManager."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from cc_deep_research.key_rotation import AllKeysExhaustedError, KeyRotationManager


class TestKeyRotationManager:
    """Tests for KeyRotationManager."""

    @pytest.fixture
    def manager(self) -> KeyRotationManager:
        """Create a KeyRotationManager with test keys."""
        return KeyRotationManager(
            api_keys=["key1", "key2", "key3"],
            requests_limit=5,
            disable_duration_minutes=60,
        )

    def test_initialization(self, manager: KeyRotationManager) -> None:
        """Test manager initialization."""
        assert manager.total_count == 3
        assert manager.available_count == 3

    def test_initialization_empty_keys(self) -> None:
        """Test initialization fails with empty keys."""
        with pytest.raises(ValueError, match="At least one API key"):
            KeyRotationManager(api_keys=[])

    def test_get_available_key(self, manager: KeyRotationManager) -> None:
        """Test getting an available key."""
        key = manager.get_available_key()
        assert key == "key1"

    def test_get_available_key_rotates(self, manager: KeyRotationManager) -> None:
        """Test that getting key rotates through available keys."""
        # Use up first key's quota
        for _ in range(5):
            manager.record_usage("key1")

        # Should now return key2
        key = manager.get_available_key()
        assert key == "key2"

    def test_record_usage(self, manager: KeyRotationManager) -> None:
        """Test recording key usage."""
        manager.record_usage("key1")
        manager.record_usage("key1")
        manager.record_usage("key1")

        status = manager.get_key_status()
        assert status[0]["requests_used"] == 3
        assert status[0]["remaining"] == 2

    def test_rotation_on_exhaustion(self, manager: KeyRotationManager) -> None:
        """Test rotation when key is exhausted."""
        # Exhaust key1
        for _ in range(5):
            manager.record_usage("key1")

        # Should have rotated to key2
        key = manager.get_available_key()
        assert key == "key2"

        # Verify key1 is not available
        status = manager.get_key_status()
        assert status[0]["available"] is False

    def test_all_keys_exhausted(self, manager: KeyRotationManager) -> None:
        """Test exception when all keys are exhausted."""
        # Exhaust all keys
        for key_str in ["key1", "key2", "key3"]:
            for _ in range(5):
                manager.record_usage(key_str)

        with pytest.raises(AllKeysExhaustedError) as exc_info:
            manager.get_available_key()

        assert exc_info.value.reset_time is not None

    def test_mark_rate_limited(self, manager: KeyRotationManager) -> None:
        """Test marking a key as rate limited."""
        manager.mark_rate_limited("key1")

        # Should have rotated away from key1
        key = manager.get_available_key()
        assert key == "key2"

        # key1 should be disabled
        status = manager.get_key_status()
        assert status[0]["disabled"] is True

    def test_key_reenable_after_duration(self) -> None:
        """Test that disabled key is re-enabled after duration."""
        manager = KeyRotationManager(
            api_keys=["key1"],
            requests_limit=1,
            disable_duration_minutes=60,
        )

        # Exhaust the key
        manager.record_usage("key1")

        # Mark it as disabled with old timestamp
        with patch("cc_deep_research.key_rotation.datetime") as mock_datetime:
            # Set last_used to 2 hours ago
            old_time = datetime.utcnow() - timedelta(hours=2)
            manager._keys[0].last_used = old_time
            manager._keys[0].disabled = True

            # Mock current time
            mock_datetime.utcnow.return_value = datetime.utcnow()

            # Key should be re-enabled
            key = manager.get_available_key()
            assert key == "key1"

    def test_reset_all_counters(self, manager: KeyRotationManager) -> None:
        """Test resetting all counters."""
        # Use all keys
        for key_str in ["key1", "key2", "key3"]:
            manager.record_usage(key_str)
            manager.mark_rate_limited(key_str)

        # Reset
        manager.reset_all_counters()

        # All should be available
        assert manager.available_count == 3
        status = manager.get_key_status()
        for s in status:
            assert s["requests_used"] == 0
            assert s["disabled"] is False

    def test_get_key_status(self, manager: KeyRotationManager) -> None:
        """Test getting key status."""
        manager.record_usage("key1")

        status = manager.get_key_status()

        assert len(status) == 3
        # Keys are only 4 chars so they get fully masked
        assert status[0]["key"] == "****"  # Masked (short key)
        assert status[0]["requests_used"] == 1
        assert status[0]["requests_limit"] == 5
        assert status[0]["remaining"] == 4
        assert status[0]["available"] is True

    def test_rotation_events_logged(self, manager: KeyRotationManager) -> None:
        """Test that rotation events are logged."""
        # Exhaust key1
        for _ in range(5):
            manager.record_usage("key1")

        events = manager.get_rotation_events()
        assert len(events) > 0
        assert events[0]["type"] == "exhausted"

    def test_rate_limit_event_logged(self, manager: KeyRotationManager) -> None:
        """Test that rate limit events are logged."""
        manager.mark_rate_limited("key1")

        events = manager.get_rotation_events()
        assert len(events) > 0
        assert events[0]["type"] == "rate_limited"

    def test_key_masking(self, manager: KeyRotationManager) -> None:
        """Test that keys are masked in status output."""
        status = manager.get_key_status()

        for s in status:
            # Should not contain full key
            assert "key1" not in s["key"]
            assert "key2" not in s["key"]
            assert "key3" not in s["key"]
            # Short keys (<=8 chars) get fully masked as "****"
            assert s["key"] == "****"

    def test_key_masking_long_keys(self) -> None:
        """Test that long keys are properly masked with ellipsis."""
        manager = KeyRotationManager(
            api_keys=["long-api-key-12345", "another-long-key-99"],
            requests_limit=5,
        )
        status = manager.get_key_status()

        for s in status:
            # Long keys should show first 4 and last 4 chars with ... in between
            assert "..." in s["key"]
            assert len(s["key"]) < 20  # Masked should be shorter than original

    def test_single_key_manager(self) -> None:
        """Test manager with single key."""
        manager = KeyRotationManager(api_keys=["only-key"])

        key = manager.get_available_key()
        assert key == "only-key"

        manager.record_usage("only-key")
        assert manager.available_count == 1

    def test_available_count_with_disabled(self, manager: KeyRotationManager) -> None:
        """Test available_count with disabled keys."""
        assert manager.available_count == 3

        manager.mark_rate_limited("key1")
        assert manager.available_count == 2

        manager.mark_rate_limited("key2")
        assert manager.available_count == 1

    def test_get_earliest_reset_time(self, manager: KeyRotationManager) -> None:
        """Test getting earliest reset time."""
        # Mark all keys as used
        for key_str in ["key1", "key2", "key3"]:
            manager.record_usage(key_str)
            manager.mark_rate_limited(key_str)

        reset_time = manager._get_earliest_reset_time()
        assert reset_time is not None
        # Should be approximately 60 minutes from now
        assert reset_time > datetime.utcnow()


class TestAllKeysExhaustedError:
    """Tests for AllKeysExhaustedError."""

    def test_error_message(self) -> None:
        """Test error message."""
        error = AllKeysExhaustedError("Custom message")
        assert str(error) == "Custom message"

    def test_default_message(self) -> None:
        """Test default error message."""
        error = AllKeysExhaustedError()
        assert "exhausted" in str(error).lower()

    def test_reset_time(self) -> None:
        """Test reset_time attribute."""
        reset_time = datetime.utcnow() + timedelta(hours=1)
        error = AllKeysExhaustedError(reset_time=reset_time)
        assert error.reset_time == reset_time
