from __future__ import annotations

import math

from PySide6.QtCore import QElapsedTimer, QTimer
from PySide6.QtWidgets import QLabel, QWidget


class TypewriterLabel(QLabel):
    """Hiện thông báo theo hiệu ứng gõ và tự ẩn sau khi gõ hoàn tất."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Khởi tạo hai timer độc lập cho nhịp gõ 60 FPS và thời gian giữ nội dung."""
        super().__init__(parent)
        self._full_text = ""
        self._position = 0
        self._step = 1
        self._typing_duration_ms = 0
        self._visible_duration_ms = 2600
        self._typing_clock = QElapsedTimer()
        self._typing_timer = QTimer(self)
        self._typing_timer.setInterval(16)
        self._typing_timer.timeout.connect(self._advance_typing)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_message)

    def show_typed(
        self,
        message: str,
        duration_ms: int = 2600,
        typing_duration_ms: int | None = None,
    ) -> None:
        """Gõ message trong thời lượng tùy chọn rồi giữ lại trước khi tự ẩn."""
        self._typing_timer.stop()
        self._hide_timer.stop()
        self._full_text = message.strip()
        self._position = 0
        self._step = max(1, (len(self._full_text) + 119) // 120)
        natural_ticks = max(1, (len(self._full_text) + self._step - 1) // self._step)
        natural_duration = natural_ticks * self._typing_timer.interval()
        self._typing_duration_ms = (
            natural_duration
            if typing_duration_ms is None
            else max(120, int(typing_duration_ms))
        )
        self._visible_duration_ms = max(500, int(duration_ms))
        if not self._full_text:
            self.hide_message()
            return
        self.setText("▌")
        self.show()
        self._typing_clock.start()
        self._typing_timer.start()

    def hide_message(self) -> None:
        """Dừng cả hai timer, bỏ con trỏ gõ và ẩn label ngay lập tức."""
        self._typing_timer.stop()
        self._hide_timer.stop()
        self.setText("")
        self.hide()

    def _advance_typing(self) -> None:
        """Nội suy số ký tự theo thời gian để text bám sát thời lượng giọng nói."""
        progress = min(1.0, self._typing_clock.elapsed() / self._typing_duration_ms)
        timed_position = math.ceil(len(self._full_text) * progress)
        self._position = min(
            len(self._full_text),
            max(self._position, timed_position),
        )
        visible_text = self._full_text[: self._position]
        if self._position < len(self._full_text):
            self.setText(f"{visible_text}▌")
            return
        self._typing_timer.stop()
        self.setText(self._full_text)
        self._hide_timer.start(self._visible_duration_ms)
