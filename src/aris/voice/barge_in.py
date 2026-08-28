from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BargeInConfig:
    """Chứa ngưỡng thích nghi để giọng người dùng cắt audio mà không nhầm tiếng vọng loa."""

    guard_seconds: float = 0.30
    minimum_interrupt_level: float = 0.035
    activation_multiplier: float = 1.20
    activation_margin: float = 0.006
    trigger_blocks: int = 3


class BargeInDetector:
    """Phát hiện giọng cắt ngang bằng RMS local và không giữ bất kỳ raw audio nào."""

    def __init__(self, config: BargeInConfig | None = None) -> None:
        """Khởi tạo bộ học mức tiếng vọng và số block giọng liên tiếp."""
        self.config = config or BargeInConfig()
        self._started_at: float | None = None
        self._echo_level = 0.01
        self._trigger_blocks = 0
        self._triggered = False

    def reset(self, timestamp: float | None = None) -> None:
        """Bắt đầu cửa sổ học tiếng vọng mới khi audio cloud chuẩn bị phát."""
        self._started_at = timestamp
        self._echo_level = 0.01
        self._trigger_blocks = 0
        self._triggered = False

    def feed(self, level: float, timestamp: float) -> bool:
        """Nhận RMS chuẩn hóa và trả True một lần khi người dùng nói cắt ngang."""
        if self._triggered:
            return False
        safe_level = max(0.0, min(1.0, float(level)))
        if self._started_at is None:
            self._started_at = timestamp
        if timestamp - self._started_at < self.config.guard_seconds:
            self._echo_level = self._echo_level * 0.74 + safe_level * 0.26
            self._trigger_blocks = 0
            return False

        threshold = max(
            self.config.minimum_interrupt_level,
            self._echo_level * self.config.activation_multiplier
            + self.config.activation_margin,
        )
        if safe_level >= threshold:
            self._trigger_blocks += 1
            self._echo_level += (safe_level - self._echo_level) * 0.35
        else:
            self._trigger_blocks = 0
            self._echo_level = self._echo_level * 0.96 + safe_level * 0.04
        if self._trigger_blocks < self.config.trigger_blocks:
            return False
        self._triggered = True
        self._trigger_blocks = 0
        return True
