from __future__ import annotations

import sys
import time
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from aris.core.config import AppConfig
from aris.core.types import IntentType
from aris.search.models import SearchResult, SearchSource
from aris.ui.hud_window import HudWindow
from aris.ui.theme import APP_STYLESHEET

PROBE_QUERY = "Bạn hãy search thông tin về Việt Nam Thái Lan"


def main() -> int:
    """Kiểm tra một lượt router-to-panel thật mà không mở mic, camera hoặc Arduino."""
    if len(sys.argv) not in {2, 3} or (len(sys.argv) == 3 and sys.argv[2] != "--mock"):
        raise SystemExit(
            "Usage: python scripts/live_search_ui_probe.py <output.png> [--mock]"
        )
    output = Path(sys.argv[1]).resolve()
    use_mock = len(sys.argv) == 3
    output.parent.mkdir(parents=True, exist_ok=True)
    application = QApplication.instance() or QApplication(sys.argv)
    application.setStyle("Fusion")
    application.setStyleSheet(APP_STYLESHEET)
    config = replace(
        AppConfig.load(),
        cloud_tts_enabled=False,
        auto_listen=False,
        hardware_enabled=False,
    )
    if not use_mock and not config.web_search_enabled:
        print("LIVE_SEARCH_UI_PROBE enabled=false", flush=True)
        return 2

    window = HudWindow(config)
    window.voice_output = False
    window.destroyed.connect(
        lambda: print("LIVE_SEARCH_UI_PROBE event=window_destroyed", flush=True)
    )
    application.lastWindowClosed.connect(
        lambda: print("LIVE_SEARCH_UI_PROBE event=last_window_closed", flush=True)
    )
    application.aboutToQuit.connect(
        lambda: print("LIVE_SEARCH_UI_PROBE event=about_to_quit", flush=True)
    )
    if use_mock:
        window.web_search.search = lambda query: SearchResult(
            True,
            query,
            "Kết quả kiểm thử giao diện không dùng mạng.",
            (SearchSource("Probe source", "https://example.com/probe"),),
        )
    else:
        live_search = window.web_search.search

        def traced_search(query: str) -> SearchResult:
            """In metadata trước/sau lời gọi thật nhưng không in nội dung hoặc bí mật."""
            print("LIVE_SEARCH_UI_PROBE stage=api_request_started", flush=True)
            result = live_search(query)
            print(
                "LIVE_SEARCH_UI_PROBE stage=api_request_finished "
                f"success={str(result.success).lower()} "
                f"answer_chars={len(result.answer)} sources={len(result.sources)}",
                flush=True,
            )
            return result

        window.web_search.search = traced_search
    window.showMaximized()
    started_at = time.monotonic()
    result_code = 1
    print("LIVE_SEARCH_UI_PROBE stage=window_ready", flush=True)

    def freeze_startup() -> None:
        """Dừng cue khởi động để probe không phát âm thanh hoặc tự mở thiết bị input."""
        window.startup_sequence.stop()
        window.sound_effects.stop()
        window.background.set_startup_progress(1.0)
        window.core.set_startup_progress(1.0)
        print("LIVE_SEARCH_UI_PROBE stage=startup_frozen", flush=True)

    def dispatch() -> None:
        """Định tuyến đúng câu hỗn hợp Việt/Anh từng không mở bảng trong runtime."""
        intent = window.router.route(PROBE_QUERY)
        print(f"LIVE_SEARCH_UI_PROBE stage=route kind={intent.kind.value}", flush=True)
        if intent.kind is not IntentType.GOOGLE_SEARCH:
            print(
                f"LIVE_SEARCH_UI_PROBE route={intent.kind.value} success=false",
                flush=True,
            )
            finish(1)
            return
        window._dispatch_intent(intent)
        print(
            "LIVE_SEARCH_UI_PROBE stage=dispatched "
            f"panels={len(window.research_manager.panel_ids)} "
            f"pending={len(window._pending_searches)}",
            flush=True,
        )

    def inspect() -> None:
        """Chờ worker hoàn tất rồi kiểm tra panel thật đang hiện trong biên HUD."""
        nonlocal result_code
        if time.monotonic() - started_at > 28.0:
            print("LIVE_SEARCH_UI_PROBE timeout=true success=false", flush=True)
            finish(1)
            return
        if window._pending_searches:
            return
        panel_id = window.research_manager.active_id
        panel = window.research_manager.panel(panel_id or "")
        if panel is None:
            print("LIVE_SEARCH_UI_PROBE panel=false success=false", flush=True)
            finish(1)
            return
        visible = panel.isVisible()
        online = panel.state_label.text() == "GROUNDED RESPONSE · ONLINE"
        inside = window.hud_page.rect().contains(panel.geometry())
        result_code = 0 if visible and online and inside else 1
        screen = window.screen()
        screenshot_saved = bool(
            screen is not None
            and screen.grabWindow(int(window.winId())).save(str(output), "PNG")
        )
        print(
            "LIVE_SEARCH_UI_PROBE "
            "route=google_search "
            f"panel={str(panel is not None).lower()} "
            f"visible={str(visible).lower()} "
            f"online={str(online).lower()} "
            f"inside={str(inside).lower()} "
            f"screenshot={str(screenshot_saved).lower()} "
            f"success={str(result_code == 0).lower()}",
            flush=True,
        )
        finish(result_code)

    def finish(code: int) -> None:
        """Đóng controller và trả mã kết quả sau khi mọi tài nguyên được giải phóng."""
        window.close()
        application.exit(code)

    poll_timer = QTimer(window)
    poll_timer.setInterval(100)
    poll_timer.timeout.connect(inspect)
    QTimer.singleShot(100, freeze_startup)
    QTimer.singleShot(220, dispatch)
    QTimer.singleShot(260, poll_timer.start)
    event_code = application.exec()
    print(
        f"LIVE_SEARCH_UI_PROBE stage=event_loop_exit code={event_code} "
        f"result={result_code}",
        flush=True,
    )
    return result_code


if __name__ == "__main__":
    raise SystemExit(main())
