from __future__ import annotations

import re
import unicodedata


def _plain(text: str) -> str:
    """Chuẩn hóa truy vấn nhạc để so khớp được cả tiếng Việt có dấu và không dấu."""
    normalized = unicodedata.normalize("NFD", text.casefold())
    without_marks = "".join(
        character for character in normalized if unicodedata.category(character) != "Mn"
    ).replace("đ", "d")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", without_marks).split())


def normalize_music_query(query: str) -> str:
    """Bỏ phần lệnh thừa và sửa các biến thể STT đã biết thành tên bài chính xác."""
    normalized = _plain(query)[:160]
    normalized = re.sub(
        r"^(?:(?:lam on|please|cho toi|cho minh)\s+)*"
        r"(?:(?:bat|mo|phat|play|start|open)\s+)?"
        r"(?:nhac|music|bai hat|bai|song|track)\s+",
        "",
        normalized,
    ).strip()
    tokens = set(normalized.split())
    # Hai bài `Mình Anh Nơi Này` và `Nơi Này Có Anh` có từ gần giống nhau.
    # Chỉ từ `có` mới được phép chọn bài của Sơn Tùng; thiếu `có` phải giữ bài NIT/SING.
    has_ambiguous_title_words = (
        "nay" in tokens
        and bool(tokens.intersection({"noi", "oi"}))
        and bool(tokens.intersection({"anh", "minh"}))
    )
    if has_ambiguous_title_words:
        if "co" in tokens:
            return "Nơi này có anh Sơn Tùng M-TP official audio"
        if "remix" in tokens:
            return "Mình Anh Nơi Này Remix NIT ft Sing"
        return "Mình Anh Nơi Này NIT ft Sing official"
    return normalized
