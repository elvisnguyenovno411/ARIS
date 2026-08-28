from __future__ import annotations

import re
import unicodedata

_VIETNAMESE_MARKED = set(
    "ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ"
)
_VIETNAMESE_WORDS = {
    "anh",
    "am",
    "ban",
    "bai",
    "bat",
    "cho",
    "chup",
    "cua",
    "dieu",
    "dong",
    "giup",
    "hien",
    "khien",
    "khong",
    "kiem",
    "lam",
    "len",
    "luong",
    "minh",
    "mo",
    "muon",
    "nhac",
    "nho",
    "phat",
    "phong",
    "quet",
    "tat",
    "thong",
    "thu",
    "tim",
    "toi",
    "tra",
    "xem",
    "xuong",
}
_ENGLISH_WORDS = {
    "can",
    "close",
    "could",
    "display",
    "find",
    "help",
    "launch",
    "lower",
    "music",
    "open",
    "pause",
    "play",
    "please",
    "raise",
    "search",
    "show",
    "start",
    "stop",
    "the",
    "volume",
    "what",
    "would",
    "you",
}


def detect_language(text: str, default: str = "en") -> str:
    """Ước lượng `vi`/`en` từ dấu và từ khóa, kể cả câu tiếng Việt không dấu."""
    lowered = text.casefold()
    if any(char in _VIETNAMESE_MARKED for char in lowered):
        return "vi"
    decomposed = unicodedata.normalize("NFD", lowered).replace("đ", "d")
    plain = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    words = set(re.findall(r"[a-z]+", plain))
    vi_score = len(words & _VIETNAMESE_WORDS)
    en_score = len(words & _ENGLISH_WORDS)
    if vi_score > en_score:
        return "vi"
    if en_score > vi_score:
        return "en"
    return default if default in {"vi", "en"} else "en"
