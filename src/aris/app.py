from __future__ import annotations

import os
import sys

# Không cho backend FFmpeg in URL audio ký số hoặc metadata kết nối ra terminal.
os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.ffmpeg.*=false")

from PySide6.QtCore import Qt
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication

from aris.core.config import AppConfig
from aris.ui.hud_window import HudWindow
from aris.ui.theme import APP_STYLESHEET


def fit_window_to_available_screen(application: QApplication, window: HudWindow) -> None:
    """Đặt kích thước restore vừa vùng làm việc dù Windows đang scale 125–200%."""
    screen = application.primaryScreen()
    if screen is None:
        return
    available = screen.availableGeometry()
    width = min(1280, max(window.minimumWidth(), round(available.width() * 0.88)))
    height = min(720, max(window.minimumHeight(), round(available.height() * 0.86)))
    window.resize(width, height)
    window.move(
        available.center().x() - width // 2,
        available.center().y() - height // 2,
    )


def create_application(config: AppConfig | None = None) -> tuple[QApplication, HudWindow]:
    """Tạo QApplication và cửa sổ ARIS, có thể nhận cấu hình riêng cho QA."""
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    surface_format = QSurfaceFormat.defaultFormat()
    surface_format.setAlphaBufferSize(8)
    QSurfaceFormat.setDefaultFormat(surface_format)
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName("ARIS")
    application.setOrganizationName("ARIS Portfolio")
    application.setStyle("Fusion")
    application.setStyleSheet(APP_STYLESHEET)
    window = HudWindow(config or AppConfig.load())
    fit_window_to_available_screen(application, window)
    return application, window


def main() -> int:
    """Khởi chạy vòng lặp sự kiện của ứng dụng desktop ARIS."""
    application, window = create_application()
    window.showMaximized()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
