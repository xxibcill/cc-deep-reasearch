"""API key rotation manager for Tavily."""

import logging
from datetime import datetime, timedelta
from typing import Any

from cc_deep_research.models import APIKey

logger = logging.getLogger(__name__)


class AllKeysExhaustedError(Exception):
    """Raised when all API keys are exhausted."""

    def __init__(
        self,
        message: str = "All API keys are exhausted",
        reset_time: datetime | None = None,
    ) -> None:
        super().__init__(message)
        self.reset_time = reset_time


class KeyRotationManager:
    """Manages multiple API keys with automatic rotation."""

    def __init__(
        self,
        api_keys: list[str],
        requests_limit: int = 1000,
        disable_duration_minutes: int = 60,
    ) -> None:
        """Initialize the key rotation manager.

        Args:
            api_keys: List of API key strings.
            requests_limit: Maximum requests per key before rotation.
            disable_duration_minutes: How long to disable exhausted keys.
        """
        if not api_keys:
            raise ValueError("At least one API key is required")

        self._keys: list[APIKey] = [
            APIKey(key=key, requests_limit=requests_limit) for key in api_keys
        ]
        self._current_index = 0
        self._disable_duration = timedelta(minutes=disable_duration_minutes)
        self._rotation_events: list[dict[str, Any]] = []

    def get_available_key(self) -> str:
        """Get an available API key.

        Returns:
            An available API key string.

        Raises:
            AllKeysExhaustedError: If all keys are exhausted.
        """
        # Try to find an available key starting from current index
        for _ in range(len(self._keys)):
            key = self._keys[self._current_index]

            if self._is_key_available(key):
                return key.key

            # Try next key
            self._rotate_to_next()

        # All keys exhausted
        reset_time = self._get_earliest_reset_time()
        raise AllKeysExhaustedError(
            "All API keys are exhausted. Please try again later.",
            reset_time=reset_time,
        )

    def _is_key_available(self, key: APIKey) -> bool:
        """Check if a key is available for use.

        Args:
            key: APIKey to check.

        Returns:
            True if key is available, False otherwise.
        """
        if key.disabled:
            # Check if disable duration has passed
            if key.last_used:
                if datetime.utcnow() - key.last_used > self._disable_duration:
                    self._reenable_key(key)
                    return True
            return False

        return key.is_available

    def _reenable_key(self, key: APIKey) -> None:
        """Re-enable a disabled key.

        Args:
            key: APIKey to re-enable.
        """
        key.disabled = False
        key.requests_used = 0
        logger.info(f"Re-enabled API key: {self._mask_key(key.key)}")
        self._log_rotation_event("reenable", key.key)

    def record_usage(self, key_str: str) -> None:
        """Record usage of a key.

        Args:
            key_str: The API key that was used.
        """
        for key in self._keys:
            if key.key == key_str:
                key.requests_used += 1
                key.last_used = datetime.utcnow()

                # Check if we need to rotate
                if not key.is_available:
                    self._rotate_to_next()
                    self._log_rotation_event("exhausted", key.key)
                break

    def mark_rate_limited(self, key_str: str) -> None:
        """Mark a key as rate limited (temporarily disabled).

        Args:
            key_str: The API key that was rate limited.
        """
        for key in self._keys:
            if key.key == key_str:
                key.disabled = True
                key.last_used = datetime.utcnow()
                self._rotate_to_next()
                self._log_rotation_event("rate_limited", key.key)
                logger.warning(f"API key rate limited, rotating: {self._mask_key(key.key)}")
                break

    def _rotate_to_next(self) -> None:
        """Rotate to the next key in the list."""
        old_index = self._current_index
        self._current_index = (self._current_index + 1) % len(self._keys)

        if old_index != self._current_index:
            old_key = self._keys[old_index]
            new_key = self._keys[self._current_index]
            logger.debug(
                f"Rotated from {self._mask_key(old_key.key)} to {self._mask_key(new_key.key)}"
            )

    def _get_earliest_reset_time(self) -> datetime | None:
        """Get the earliest time a key might become available.

        Returns:
            Datetime when a key might become available, or None.
        """
        earliest: datetime | None = None
        for key in self._keys:
            if key.last_used:
                reset_time = key.last_used + self._disable_duration
                if earliest is None or reset_time < earliest:
                    earliest = reset_time
        return earliest

    def _mask_key(self, key: str) -> str:
        """Mask a key for logging.

        Args:
            key: API key string.

        Returns:
            Masked key string.
        """
        if len(key) <= 8:
            return "****"
        return f"{key[:4]}...{key[-4:]}"

    def _log_rotation_event(self, event_type: str, key: str) -> None:
        """Log a rotation event.

        Args:
            event_type: Type of rotation event.
            key: The affected key.
        """
        self._rotation_events.append(
            {
                "type": event_type,
                "key": self._mask_key(key),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    def reset_all_counters(self) -> None:
        """Reset all key counters (e.g., for daily reset)."""
        for key in self._keys:
            key.requests_used = 0
            key.disabled = False
        logger.info("Reset all API key counters")

    @property
    def available_count(self) -> int:
        """Get count of available keys."""
        return sum(1 for key in self._keys if self._is_key_available(key))

    @property
    def total_count(self) -> int:
        """Get total count of keys."""
        return len(self._keys)

    def get_key_status(self) -> list[dict[str, Any]]:
        """Get status of all keys.

        Returns:
            List of key status dictionaries.
        """
        return [
            {
                "key": self._mask_key(key.key),
                "available": self._is_key_available(key),
                "requests_used": key.requests_used,
                "requests_limit": key.requests_limit,
                "remaining": key.remaining_requests,
                "disabled": key.disabled,
            }
            for key in self._keys
        ]

    def get_rotation_events(self) -> list[dict[str, Any]]:
        """Get all rotation events.

        Returns:
            List of rotation event dictionaries.
        """
        return self._rotation_events.copy()


__all__ = ["KeyRotationManager", "AllKeysExhaustedError"]
