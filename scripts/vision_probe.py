from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication, QTimer

from aris.core.config import AppConfig
from aris.vision.tracker import VisionController


def run_probe(duration_ms: int = 4500) -> int:
    """Chạy pipeline MediaPipe với webcam thật mà không lưu hoặc hiển thị frame."""
    app = QCoreApplication(sys.argv)
    config = AppConfig.load()
    controller = VisionController(config.assets_dir / "models" / "hand_landmarker.task")
    result = {"opened": False, "error": False}

    def report_status(message: str, state: str) -> None:
        """In trạng thái rút gọn để kiểm thử pipeline camera từ terminal."""
        print(f"VISION_PROBE state={state} message={message}")
        result["error"] = result["error"] or state == "error"

    def report_running(running: bool) -> None:
        """Ghi nhận webcam đã mở và kết thúc event loop sau khi đóng."""
        print(f"VISION_PROBE running={str(running).lower()}")
        result["opened"] = result["opened"] or running
        if not running and result["opened"]:
            app.quit()

    def report_fps(fps: float) -> None:
        """In FPS MediaPipe thực đo để kiểm tra profile tối ưu trên máy hiện tại."""
        print(f"VISION_PROBE inference_fps={fps:.1f}")

    def stop_probe() -> None:
        """Dừng controller đúng hạn để webcam luôn được giải phóng."""
        controller.stop()
        app.quit()

    controller.status_changed.connect(report_status)
    controller.running_changed.connect(report_running)
    controller.fps_sampled.connect(report_fps)
    controller.set_gesture_enabled(True)
    QTimer.singleShot(duration_ms, stop_probe)
    app.exec()
    controller.stop()
    if not result["opened"] or result["error"]:
        return 1
    print("VISION_PROBE ok frames_processed_in_memory=true saved_frames=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_probe())
