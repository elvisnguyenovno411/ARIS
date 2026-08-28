from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class IntentType(StrEnum):
    """Liệt kê các loại ý định an toàn mà bộ định tuyến ARIS hiểu."""

    SELECT_MODEL = "select_model"
    FOCUS_MODEL = "focus_model"
    CLOSE_MODEL = "close_model"
    MODEL_ZOOM = "model_zoom"
    OPEN_APP = "open_app"
    CLOSE_APP = "close_app"
    OPEN_FILE = "open_file"
    GOOGLE_SEARCH = "google_search"
    CLOSE_RESEARCH = "close_research"
    PLAY_MUSIC = "play_music"
    PAUSE_MUSIC = "pause_music"
    RESUME_MUSIC = "resume_music"
    STOP_MUSIC = "stop_music"
    MUSIC_VOLUME = "music_volume"
    VOLUME = "volume"
    SCAN_HAND = "scan_hand"
    ARM_GUARD = "arm_guard"
    DISARM_GUARD = "disarm_guard"
    GUARD_STATUS = "guard_status"
    EXIT_ARIS = "exit_aris"
    CLEAR_HISTORY = "clear_history"
    HELP = "help"
    GENERAL_CHAT = "general_chat"


@dataclass(frozen=True, slots=True)
class Intent:
    """Mô tả một yêu cầu đã được phân loại cùng tham số có cấu trúc."""

    kind: IntentType
    arguments: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class ActionResult:
    """Biểu diễn kết quả thành công hoặc lỗi của một hành động local an toàn."""

    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
