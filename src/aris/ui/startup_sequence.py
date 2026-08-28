from __future__ import annotations

import time

from PySide6.QtCore import QObject, Qt, QTimer, Signal


class StartupSequence(QObject):
    """Phát tiến độ khởi động 0–1 theo thời gian thực để đồng bộ toàn bộ HUD."""

    progress_changed = Signal(float)
    finished = Signal()

    def __init__(self, duration_ms: int = 4400, parent: QObject | None = None) -> None:
        """Khởi tạo timeline nhẹ; timer chỉ chạy sau khi cửa sổ đã được hiển thị."""
        super().__init__(parent)
        self.duration_ms = max(250, int(duration_ms))
        self._started_at = 0.0
        self._progress = 0.0
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._advance)

    @property
    def progress(self) -> float:
        """Trả tiến độ hiện tại trong khoảng 0–1 để kiểm thử và chụp từng frame."""
        return self._progress

    @property
    def is_running(self) -> bool:
        """Cho biết timeline khởi động có đang phát hay không."""
        return self._timer.isActive()

    def start(self) -> None:
        """Bắt đầu lại timeline từ màn tối và phát frame đầu ngay lập tức."""
        self._started_at = time.monotonic()
        self._progress = 0.0
        self.progress_changed.emit(0.0)
        self._timer.start()

    def stop(self) -> None:
        """Dừng timeline ngay mà không giả vờ phát signal hoàn thành."""
        self._timer.stop()

    def _advance(self) -> None:
        """Tính tiến độ bằng đồng hồ thật để animation không chậm lại khi mất frame."""
        elapsed_ms = (time.monotonic() - self._started_at) * 1000.0
        self._progress = max(0.0, min(1.0, elapsed_ms / self.duration_ms))
        self.progress_changed.emit(self._progress)
        if self._progress >= 1.0:
            self._timer.stop()
            self.finished.emit()


class ShutdownSequence(QObject):
    """Phát ngược tiến độ HUD từ sáng về tối trước khi đóng cửa sổ ARIS."""

    progress_changed = Signal(float)
    finished = Signal()

    def __init__(self, duration_ms: int = 1700, parent: QObject | None = None) -> None:
        """Khởi tạo power-down timeline mượt, độc lập với startup đã hoàn tất."""
        super().__init__(parent)
        self.duration_ms = max(300, int(duration_ms))
        self._started_at = 0.0
        self._progress = 1.0
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._advance)

    @property
    def progress(self) -> float:
        """Trả độ sáng còn lại 1–0 để kiểm thử hiệu ứng mất nguồn."""
        return self._progress

    @property
    def is_running(self) -> bool:
        """Cho biết hiệu ứng shutdown đang chạy và không được kích hoạt lần hai."""
        return self._timer.isActive()

    def start(self) -> None:
        """Bắt đầu từ HUD sáng hoàn toàn và giảm liên tục tới màn tối."""
        if self._timer.isActive():
            return
        self._started_at = time.monotonic()
        self._progress = 1.0
        self.progress_changed.emit(1.0)
        self._timer.start()

    def stop(self) -> None:
        """Dừng power-down ngay khi cửa sổ bị đóng bằng cơ chế khác."""
        self._timer.stop()

    def _advance(self) -> None:
        """Tính độ sáng còn lại bằng thời gian thật để frame drop không kéo dài shutdown."""
        elapsed_ms = (time.monotonic() - self._started_at) * 1000.0
        self._progress = max(0.0, min(1.0, 1.0 - elapsed_ms / self.duration_ms))
        self.progress_changed.emit(self._progress)
        if self._progress <= 0.0:
            self._timer.stop()
            self.finished.emit()
