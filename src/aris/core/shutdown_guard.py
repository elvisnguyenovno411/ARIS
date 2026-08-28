from __future__ import annotations

from enum import StrEnum


class ShutdownDecision(StrEnum):
    """Liệt kê quyết định cho phép shutdown hoặc yêu cầu xác nhận bằng giọng."""

    ALLOW = "allow"
    CONFIRM = "confirm"


class ShutdownGuard:
    """Ngăn một transcript sai tắt HUD khi nhạc đang phát hoặc đang được tìm."""

    def __init__(self, confirmation_seconds: float = 7.0) -> None:
        """Khởi tạo cửa sổ xác nhận hữu hạn và không giữ nội dung câu nói."""
        self.confirmation_seconds = max(2.0, float(confirmation_seconds))
        self._pending_until = 0.0

    def evaluate(
        self,
        *,
        confirmed: bool,
        music_context: bool,
        timestamp: float,
    ) -> ShutdownDecision:
        """Cho tắt trực tiếp ngoài nhạc; trong nhạc phải có câu xác nhận thứ hai rõ ràng."""
        now = float(timestamp)
        if not music_context:
            self._pending_until = 0.0
            return ShutdownDecision.ALLOW
        if confirmed:
            self._pending_until = 0.0
            return ShutdownDecision.ALLOW
        self._pending_until = now + self.confirmation_seconds
        return ShutdownDecision.CONFIRM

    def reset(self) -> None:
        """Xóa yêu cầu xác nhận cũ khi một tác vụ nhạc mới được thực thi."""
        self._pending_until = 0.0
