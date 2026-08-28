from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from aris.core.config import AppConfig
from aris.search.models import SearchResult, SearchSource
from aris.ui.hud_window import HudWindow
from aris.ui.theme import APP_STYLESHEET


def main() -> int:
    """Chụp bảng Web Search bằng dữ liệu giả, không mở mic/camera/phần cứng hoặc gọi API."""
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/capture_research.py <output.png>")
    output = Path(sys.argv[1]).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    application = QApplication.instance() or QApplication(sys.argv)
    application.setStyle("Fusion")
    application.setStyleSheet(APP_STYLESHEET)
    config = replace(
        AppConfig.load(),
        openai_api_key=None,
        web_search_enabled=False,
        cloud_tts_enabled=False,
        auto_listen=False,
        hardware_enabled=False,
    )
    window = HudWindow(config)
    window.showMaximized()
    results = (
        SearchResult(
            True,
            "Robot hình người mới nhất có khả năng gì?",
            "Các hệ thống mới tập trung vào di chuyển ổn định, thao tác vật thể và học nhiệm vụ "
            "từ dữ liệu cảm biến.",
            (SearchSource("Primary research source", "https://example.com/research"),),
            request_number=1,
        ),
        SearchResult(
            True,
            "Vật liệu nhẹ cho cơ điện tử",
            "Nhôm, polymer gia cường và composite được lựa chọn dựa trên tải, độ cứng, khả năng "
            "gia công và điều kiện sử dụng.",
            (SearchSource("Materials reference", "https://example.org/materials"),),
            request_number=2,
        ),
        SearchResult(
            True,
            "Cảm biến khoảng cách hoạt động thế nào?",
            "Cảm biến phát tín hiệu, đo phản hồi và đổi thời gian truyền thành khoảng cách. "
            "Độ chính xác phụ thuộc môi trường và bề mặt mục tiêu.",
            (SearchSource("Sensor documentation", "https://example.net/sensors"),),
            request_number=3,
        ),
    )
    def populate_panels() -> None:
        """Tạo bảng sau khi maximize đã cập nhật kích thước HUD để kiểm tra đúng vị trí thật."""
        for result in results:
            panel_id = window.research_manager.open_loading(result.query)
            window.research_manager.show_result(panel_id, result, requests_remaining=17)

    def freeze_startup() -> None:
        """Chặn timeline/cue tự khởi động để probe không phát âm thanh hoặc mở microphone."""
        window.startup_sequence.stop()
        window.sound_effects.stop()
        window.background.set_startup_progress(1.0)
        window.core.set_startup_progress(1.0)
        active_id = window.research_manager.active_id
        if active_id is not None:
            panel = window.research_manager.panel(active_id)
            if panel is not None:
                panel.raise_()

    def capture() -> None:
        """Chụp đúng compositor Windows rồi đóng toàn bộ controller an toàn."""
        screen = window.screen()
        if screen is None:
            raise RuntimeError("No screen is available for visual QA.")
        screen.grabWindow(int(window.winId())).save(str(output), "PNG")
        window.close()
        application.quit()

    QTimer.singleShot(140, freeze_startup)
    QTimer.singleShot(220, populate_panels)
    QTimer.singleShot(1800, capture)
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
