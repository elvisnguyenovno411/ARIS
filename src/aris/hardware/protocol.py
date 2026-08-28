from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class GuardState(StrEnum):
    """Liệt kê trạng thái bảo vệ mà firmware Arduino được phép gửi."""

    OFF = "OFF"
    ARMING = "ARMING"
    ARMED = "ARMED"
    ALERT = "ALERT"


class HardwareEventType(StrEnum):
    """Liệt kê loại sự kiện phần cứng hợp lệ sau khi kiểm tra protocol."""

    READY = "READY"
    STATE = "STATE"
    ARMING_SECONDS = "ARMING_SECONDS"
    DISTANCE_CM = "DISTANCE_CM"
    REMOTE = "REMOTE"
    ERROR = "ERROR"
    PONG = "PONG"


@dataclass(frozen=True, slots=True)
class HardwareEvent:
    """Chứa một sự kiện Arduino đã parse cùng giá trị dạng chuỗi an toàn."""

    kind: HardwareEventType
    value: str


ALLOWED_COMMANDS = frozenset({"ARM", "DISARM", "STOP", "STATUS"})


def normalize_hardware_command(command: str) -> str | None:
    """Chuẩn hóa lệnh gửi Arduino và từ chối mọi giá trị ngoài allowlist."""
    normalized = command.strip().upper()
    return normalized if normalized in ALLOWED_COMMANDS else None


def parse_hardware_line(line: str) -> HardwareEvent | None:
    """Parse một dòng `ARIS_HW|TYPE|VALUE`; trả None nếu sai cấu trúc hoặc kiểu."""
    cleaned = line.strip()
    parts = cleaned.split("|")
    if len(parts) < 3 or parts[0] != "ARIS_HW":
        return None
    try:
        kind = HardwareEventType(parts[1])
    except ValueError:
        return None
    value = "|".join(parts[2:]).strip()
    if not value or len(value) > 80:
        return None
    if kind is HardwareEventType.STATE:
        try:
            GuardState(value)
        except ValueError:
            return None
    elif kind is HardwareEventType.DISTANCE_CM:
        try:
            distance = float(value)
        except ValueError:
            return None
        if not -1.0 <= distance <= 1000.0:
            return None
    elif kind is HardwareEventType.ARMING_SECONDS:
        try:
            seconds = int(value)
        except ValueError:
            return None
        if not 0 <= seconds <= 120:
            return None
    return HardwareEvent(kind, value)
