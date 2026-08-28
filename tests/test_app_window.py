from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize

from aris.app import fit_window_to_available_screen


class _FakeScreen:
    def availableGeometry(self) -> QRect:  # noqa: N802 - Qt-compatible test double
        return QRect(0, 0, 1404, 800)


class _FakeApplication:
    def primaryScreen(self) -> _FakeScreen:  # noqa: N802 - Qt-compatible test double
        return _FakeScreen()


class _FakeWindow:
    def __init__(self) -> None:
        self.size = QSize()
        self.position = QPoint()

    def minimumWidth(self) -> int:  # noqa: N802 - Qt-compatible test double
        return 960

    def minimumHeight(self) -> int:  # noqa: N802 - Qt-compatible test double
        return 600

    def resize(self, width: int, height: int) -> None:
        self.size = QSize(width, height)

    def move(self, x_value: int, y_value: int) -> None:
        self.position = QPoint(x_value, y_value)


def test_restore_geometry_fits_scaled_windows_work_area() -> None:
    """Đảm bảo cửa sổ restore không lớn hơn vùng logical ở màn hình scale 125%."""
    window = _FakeWindow()

    fit_window_to_available_screen(_FakeApplication(), window)  # type: ignore[arg-type]

    assert window.size == QSize(1236, 688)
    assert window.position == QPoint(83, 55)
