from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum


class WakeAction(StrEnum):
    """Liệt kê kết quả bỏ qua, vừa thức dậy, hoặc nhận một lệnh hợp lệ."""

    IGNORE = "ignore"
    WAKE = "wake"
    COMMAND = "command"


@dataclass(frozen=True, slots=True)
class WakeDecision:
    """Chứa quyết định wake session và câu lệnh đã bỏ phần gọi tên ARIS."""

    action: WakeAction
    command: str = ""


def _plain(text: str) -> str:
    """Chuẩn hóa dấu và ký tự để so khớp wake phrase Việt/Anh ổn định hơn."""
    normalized = unicodedata.normalize("NFD", text.casefold())
    without_marks = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    ).replace("đ", "d")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", without_marks).split())


class WakeSession:
    """Chỉ nhận lệnh sau `Hey ARIS` và tự ngủ sau một khoảng không có transcript."""

    _WAKE_PREFIXES = (
        "hey aris",
        "hey ari",
        "hey ares",
        "hey aries",
        "hey arise",
        "hay aris",
        "hay ari",
        "hi aris",
        "he aris",
        "he ari",
        "hey iris",
        "hey eris",
        "hey r s",
        "hey a r i s",
        "hey artist",
        "hey harris",
        "hey a risk",
        "hey rs",
    )

    _NAME_ONLY_WAKE_WORDS = {
        "aris",
        "ari",
        "ares",
        "aries",
        "arise",
        "iris",
        "eris",
    }

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        """Khởi tạo ở trạng thái ngủ với timeout tối thiểu một giây."""
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self._active_until = 0.0

    def is_awake(self, timestamp: float) -> bool:
        """Cho biết phiên lệnh còn hoạt động tại timestamp monotonic được cung cấp."""
        return float(timestamp) < self._active_until

    def sleep(self) -> None:
        """Đóng phiên ngay để câu tiếp theo bắt buộc gọi `Hey ARIS`."""
        self._active_until = 0.0

    def touch(self, timestamp: float) -> bool:
        """Gia hạn phiên khi VAD xác nhận giọng bắt đầu; không tự đánh thức lúc đang ngủ."""
        if not self.is_awake(timestamp):
            return False
        self._active_until = float(timestamp) + self.timeout_seconds
        return True

    def process(self, transcript: str, timestamp: float) -> WakeDecision:
        """Nhận transcript và trả lệnh chỉ khi có wake phrase hoặc phiên còn hiệu lực."""
        cleaned = transcript.strip()
        normalized = _plain(cleaned)
        if not normalized:
            return WakeDecision(WakeAction.IGNORE)

        prefix = next(
            (
                candidate
                for candidate in self._WAKE_PREFIXES
                if normalized == candidate or normalized.startswith(f"{candidate} ")
            ),
            None,
        )
        if prefix is None and normalized in self._NAME_ONLY_WAKE_WORDS:
            prefix = normalized
        if prefix is None and normalized.startswith("heyaris"):
            prefix = "heyaris"
        if prefix is not None:
            self._active_until = float(timestamp) + self.timeout_seconds
            normalized_words = normalized.split()
            prefix_word_count = len(prefix.split())
            remaining_word_count = len(normalized_words) - prefix_word_count
            if remaining_word_count <= 0:
                return WakeDecision(WakeAction.WAKE)
            original_words = cleaned.split()
            command = " ".join(original_words[-remaining_word_count:]).strip(" ,.!?:;-")
            return WakeDecision(WakeAction.COMMAND, command)

        if self.is_awake(timestamp):
            self._active_until = float(timestamp) + self.timeout_seconds
            return WakeDecision(WakeAction.COMMAND, cleaned)
        return WakeDecision(WakeAction.IGNORE)
