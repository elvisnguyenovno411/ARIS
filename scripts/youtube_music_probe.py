from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.ffmpeg.*=false")

from PySide6.QtCore import QCoreApplication, QTimer

from aris.media import MusicPlayer


def run_probe(query: str, timeout_ms: int = 55_000) -> int:
    """Tìm và phát nhỏ một bài YouTube để xác nhận yt-dlp cùng FFmpeg hoạt động."""
    application = QCoreApplication.instance() or QCoreApplication(sys.argv)
    player = MusicPlayer((), volume=0.08, youtube_enabled=True)
    state = {"started": False, "error": "", "maximum_level": 0.0}

    def on_started(title: str) -> None:
        """Ghi nhận backend đã phát và dừng probe sau một đoạn kiểm tra ngắn."""
        state["started"] = True
        print(f"YOUTUBE_MUSIC_PROBE started=true title={title}")
        QTimer.singleShot(5000, application.quit)

    def on_error(message: str) -> None:
        """Ghi lỗi rút gọn và kết thúc probe mà không làm ứng dụng treo."""
        state["error"] = message
        print(f"YOUTUBE_MUSIC_PROBE error={message}")
        application.quit()

    def on_level(level: float) -> None:
        """Giữ mức beat lớn nhất để xác nhận PCM thực sự đến HUD pipeline."""
        state["maximum_level"] = max(float(state["maximum_level"]), float(level))

    player.stream_started.connect(on_started)
    player.error_occurred.connect(on_error)
    player.level_changed.connect(on_level)
    result = player.play(query)
    print(f"YOUTUBE_MUSIC_PROBE pending={result.success} message={result.message}")
    QTimer.singleShot(timeout_ms, application.quit)
    application.exec()
    player.stop()
    maximum_level = float(state["maximum_level"])
    print(f"YOUTUBE_MUSIC_PROBE maximum_level={maximum_level:.3f} saved_media=false")
    if state["started"] and maximum_level > 0.0 and not state["error"]:
        print("YOUTUBE_MUSIC_PROBE ok")
        return 0
    print("YOUTUBE_MUSIC_PROBE failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(run_probe(" ".join(sys.argv[1:]) or "Nơi này có anh"))
