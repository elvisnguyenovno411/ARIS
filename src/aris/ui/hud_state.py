from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class HudMode(StrEnum):
    """Liệt kê các trạng thái hình ảnh hợp lệ của HUD tối giản."""

    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    MODEL = "model"
    ERROR = "error"
    ALERT = "alert"


@dataclass(slots=True)
class HudStateMachine:
    """Quản lý chuyển trạng thái HUD để UI và controller không tự mâu thuẫn."""

    mode: HudMode = HudMode.IDLE
    active_model: str | None = None
    open_models: list[str] = field(default_factory=list)

    def begin_listening(self) -> HudMode:
        """Chuyển sang nghe lệnh nhưng giữ model hiện tại nếu đang hiển thị."""
        self.mode = HudMode.LISTENING
        return self.mode

    def begin_thinking(self) -> HudMode:
        """Chuyển sang trạng thái xử lý sau khi người dùng kết thúc ghi âm."""
        self.mode = HudMode.THINKING
        return self.mode

    def begin_speaking(self) -> HudMode:
        """Chuyển lõi sang animation phát giọng mà không thay đổi model đang nhớ."""
        self.mode = HudMode.SPEAKING
        return self.mode

    def show_model(self, model_key: str) -> HudMode:
        """Thêm/chọn model trong lớp hologram nổi và giữ các model đã mở trước đó."""
        if model_key not in self.open_models:
            self.open_models.append(model_key)
        self.active_model = model_key
        self.mode = HudMode.MODEL
        return self.mode

    def select_model(self, model_key: str) -> HudMode:
        """Chọn model đã mở để nhận gesture mà không tạo thêm bản sao."""
        if model_key in self.open_models:
            self.active_model = model_key
            self.mode = HudMode.MODEL
        return self.mode

    def close_model(self, model_key: str | None = None) -> HudMode:
        """Đóng model theo khóa hoặc model đang chọn rồi chọn model gần nhất còn lại."""
        target = model_key or self.active_model
        if target in self.open_models:
            self.open_models.remove(target)
        self.active_model = self.open_models[-1] if self.open_models else None
        self.mode = HudMode.MODEL if self.active_model is not None else HudMode.IDLE
        return self.mode

    def close_all_models(self) -> HudMode:
        """Xóa toàn bộ model nổi khi người dùng kết thúc phiên hologram."""
        self.open_models.clear()
        self.active_model = None
        self.mode = HudMode.IDLE
        return self.mode

    def fail(self) -> HudMode:
        """Đưa HUD sang trạng thái lỗi để hiển thị phản hồi tạm thời."""
        self.mode = HudMode.ERROR
        return self.mode

    def reset(self) -> HudMode:
        """Khôi phục trạng thái nhìn phù hợp mà không xóa các model đang mở."""
        self.mode = HudMode.MODEL if self.active_model is not None else HudMode.IDLE
        return self.mode
