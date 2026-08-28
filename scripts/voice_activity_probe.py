from __future__ import annotations

import sys
from dataclasses import replace

from PySide6.QtCore import QCoreApplication, QTimer

from aris.core.config import AppConfig
from aris.voice.controller import VoiceController


def run_probe(duration_ms: int = 12_000) -> int:
    """Kiểm tra nói–im lặng với VAD thật, ép cloud tắt và không lưu file âm thanh."""
    app = QCoreApplication(sys.argv)
    config = replace(AppConfig.load(), openai_api_key=None, auto_listen=True)
    controller = VoiceController(config)
    result = {"started": False, "stopped": False, "error": False}

    def on_recording(recording: bool) -> None:
        """Ghi nhận hai cạnh START/STOP của một câu nói tự động."""
        if recording:
            result["started"] = True
            print("VOICE_ACTIVITY_PROBE speech_started=true")
        elif result["started"]:
            result["stopped"] = True
            print("VOICE_ACTIVITY_PROBE speech_stopped=true")

    def on_status(message: str, state: str) -> None:
        """In trạng thái thiết bị nhưng không in hoặc giữ nội dung câu nói."""
        if state == "error":
            result["error"] = True
            print(f"VOICE_ACTIVITY_PROBE error={message}")
        elif state == "monitoring":
            print(f"VOICE_ACTIVITY_PROBE {message}")

    def finish() -> None:
        """Đóng microphone đúng hạn và kết thúc bằng mã phản ánh đủ START/STOP."""
        controller.close()
        app.quit()

    controller.recording_changed.connect(on_recording)
    controller.status_changed.connect(on_status)
    controller.start_monitoring()
    print("VOICE_ACTIVITY_PROBE ready say_one_sentence=true saved_audio=false")
    QTimer.singleShot(duration_ms, finish)
    app.exec()
    if result["started"] and result["stopped"] and not result["error"]:
        print("VOICE_ACTIVITY_PROBE ok")
        return 0
    print(
        "VOICE_ACTIVITY_PROBE failed "
        f"started={str(result['started']).lower()} "
        f"stopped={str(result['stopped']).lower()}"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(run_probe())
