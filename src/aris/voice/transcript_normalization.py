from __future__ import annotations

import re
import unicodedata

_ACOUSTIC_COMMAND_ALIASES = {
    "racing game": "Hiển thị Rasengan",
    "racing games": "Hiển thị Rasengan",
    "raising game": "Hiển thị Rasengan",
    "racing gun": "Hiển thị Rasengan",
    "raising gun": "Hiển thị Rasengan",
    "closed": "Close",
    "closing": "Close",
    "clothes": "Close",
    "clause": "Close",
    "closer": "Close",
}

_CLOSE_PREFIXES = (
    "close",
    "closed",
    "clothes",
    "clause",
    "closer",
    "end",
    "stop",
    "hide",
    "dong",
    "tat",
    "tac",
    "tach",
)

_RASENGAN_ACOUSTIC_ALIASES = (
    "rasengan",
    "rasen gan",
    "ra sen gan",
    "ra sin gan",
    "ra sing gan",
    "racing game",
    "raising game",
    "racing gun",
    "raising gun",
)

_ARIS_ACOUSTIC_ALIASES = (
    "aris",
    "ari",
    "ares",
    "aries",
    "arise",
    "iris",
    "eris",
    "a r i s",
)

_EXIT_PREFIXES = (
    "close",
    "closed",
    "closing",
    "clothes",
    "clause",
    "quit",
    "exit",
    "stop",
    "shutdown",
    "shut down",
    "turn off",
    "power down",
    "dong",
    "tat",
    "thoat",
    "dung",
    "ngung",
    "ket thuc",
)


def _plain(transcript: str) -> str:
    """Bỏ dấu và dấu câu để so khớp biến thể phiên âm song ngữ ổn định hơn."""
    normalized = unicodedata.normalize("NFD", transcript.casefold())
    without_marks = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    ).replace("đ", "d")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", without_marks).split())


def normalize_voice_command(transcript: str) -> str:
    """Sửa một số lỗi nghe tên riêng khi toàn bộ câu khớp chính xác với alias đã biết."""
    cleaned = transcript.strip()
    lookup_key = _plain(cleaned)
    has_close_prefix = any(
        lookup_key == prefix or lookup_key.startswith(f"{prefix} ")
        for prefix in _CLOSE_PREFIXES
    )
    if has_close_prefix and any(
        alias in lookup_key for alias in _RASENGAN_ACOUSTIC_ALIASES
    ):
        return "Close Rasengan"
    has_exit_prefix = any(
        lookup_key == prefix or lookup_key.startswith(f"{prefix} ")
        for prefix in _EXIT_PREFIXES
    )
    if has_exit_prefix and any(
        re.search(rf"\b{re.escape(alias)}\b", lookup_key)
        for alias in _ARIS_ACOUSTIC_ALIASES
    ):
        return "Tắt ARIS"
    return _ACOUSTIC_COMMAND_ALIASES.get(lookup_key, cleaned)
