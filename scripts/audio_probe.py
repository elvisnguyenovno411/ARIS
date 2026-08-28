from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication, QTimer

from aris.core.config import AppConfig
from aris.voice.controller import VoiceController


def run_probe(duration_ms: int = 3200) -> int:
    """Kiểm tra monitor mic và spectrum local mà không ghi hoặc lưu sample âm thanh."""
    app = QCoreApplication(sys.argv)
    controller = VoiceController(AppConfig.load())
    result = {"monitoring": False, "frames": 0, "maximum": 0.0, "error": False}

    def on_monitoring(enabled: bool) -> None:
        """Ghi nhận stream PortAudio đã mở thành công."""
        result["monitoring"] = result["monitoring"] or enabled

    def on_level(level: float) -> None:
        """Chỉ lưu thống kê số học, không giữ block microphone."""
        result["frames"] += 1
        result["maximum"] = max(result["maximum"], float(level))

    def on_status(message: str, state: str) -> None:
        """Đánh dấu lỗi thiết bị nhưng không in dữ liệu âm thanh nhạy cảm."""
        if state == "error":
            result["error"] = True
            print(f"AUDIO_PROBE error={message}")

    def finish() -> None:
        """Đóng stream đúng hạn rồi kết thúc Qt event loop."""
        controller.close()
        app.quit()

    controller.monitoring_changed.connect(on_monitoring)
    controller.audio_level_changed.connect(on_level)
    controller.status_changed.connect(on_status)
    controller.start_monitoring()
    QTimer.singleShot(duration_ms, finish)
    app.exec()
    print(
        "AUDIO_PROBE "
        f"monitoring={result['monitoring']} frames={result['frames']} "
        f"maximum_level={result['maximum']:.3f} saved_audio=false"
    )
    return 0 if result["monitoring"] and result["frames"] > 0 and not result["error"] else 1


if __name__ == "__main__":
    raise SystemExit(run_probe())
