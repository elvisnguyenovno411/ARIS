from __future__ import annotations

import re
import unicodedata

from aris.core.types import Intent, IntentType
from aris.models.catalog import ModelCatalog


def _plain(text: str) -> str:
    """Chuẩn hóa chữ thường, bỏ dấu và dấu câu để định tuyến lệnh ổn định hơn."""
    normalized = unicodedata.normalize("NFD", text.casefold())
    without_marks = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    without_marks = without_marks.replace("đ", "d")
    without_punctuation = re.sub(r"[^a-z0-9]+", " ", without_marks)
    return " ".join(without_punctuation.split())


_POLITE_PREFIXES = (
    "can you please",
    "could you please",
    "would you please",
    "i would like you to",
    "i want you to",
    "can you",
    "could you",
    "would you",
    "please",
    "lam on",
    "vui long",
    "ban co the",
    "minh muon ban",
    "toi muon ban",
    "minh muon",
    "toi muon",
    "giup minh",
    "giup toi",
    "hay",
)


def _strip_polite_prefixes(text: str) -> str:
    """Bỏ nhiều lời dẫn lịch sự liên tiếp nhưng giữ nguyên phần tác vụ phía sau."""
    result = text
    changed = True
    while changed:
        changed = False
        for prefix in _POLITE_PREFIXES:
            if result == prefix:
                return ""
            if result.startswith(f"{prefix} "):
                result = result[len(prefix) + 1 :]
                changed = True
                break
    return result


def _raw_suffix_for_plain(raw: str, normalized_suffix: str) -> str:
    """Khôi phục đuôi câu gốc có dấu/chấm khi regex chạy trên bản đã chuẩn hóa."""
    raw_words = raw.split()
    for index in range(len(raw_words)):
        candidate = " ".join(raw_words[index:])
        if _plain(candidate) == normalized_suffix:
            return candidate.strip("\"'")
    return normalized_suffix


def _is_non_action_context(raw: str, normalized: str) -> bool:
    """Nhận câu phủ định/giả định/trích dẫn để luật từ khóa không chạy nhầm action."""
    deferred_prefixes = (
        "do not ",
        "dont ",
        "don t ",
        "never ",
        "what happens if ",
        "what if ",
        "how do i ",
        "how to ",
        "should i ",
        "can aris ",
        "khong ",
        "chua can ",
        "neu ",
        "gia su ",
        "cach ",
    )
    raw_prefix = raw.strip().casefold()
    raw_lowered = raw.casefold()
    negated_anywhere = (
        "đừng" in raw_lowered
        or any(
            phrase in normalized
            for phrase in (
                "do not ",
                "don t ",
                "dont ",
                "never ",
                "khong muon ",
                "khong duoc ",
                "khong can ",
                "chua can ",
            )
        )
    )
    ambiguous_unaccented_negations = (
        "dung mo ",
        "dung bat ",
        "dung dong ",
        "dung tat ",
        "dung thoat ",
        "dung xoa ",
    )
    if (
        negated_anywhere
        or raw_prefix.startswith("đừng ")
        or normalized.startswith(deferred_prefixes)
        or normalized.startswith(ambiguous_unaccented_negations)
    ):
        return True
    quoted = any(mark in raw for mark in ('"', "'", "“", "”"))
    quoted_context = normalized.startswith(
        ("say ", "repeat ", "translate ", "vi du ", "doc cau ", "nhac lai ")
    )
    return quoted and quoted_context


class IntentRouter:
    """Phân loại các lệnh chính bằng luật local trước khi cân nhắc gọi API."""

    APP_ALIASES = {
        "chrome": "chrome",
        "google chrome": "chrome",
        "trinh duyet chrome": "chrome",
        "chrome browser": "chrome",
        "vs code": "vscode",
        "vscode": "vscode",
        "visual studio code": "vscode",
        "code editor": "vscode",
        "trinh soan thao code": "vscode",
        "trinh soan thao ma": "vscode",
        "discord": "discord",
        "codex": "codex",
        "microsoft edge": "edge",
        "edge": "edge",
        "file explorer": "file_explorer",
        "windows explorer": "file_explorer",
        "trinh quan ly tep": "file_explorer",
        "quan ly tep": "file_explorer",
        "explorer": "file_explorer",
        "notepad": "notepad",
        "so ghi chu": "notepad",
        "text editor": "notepad",
        "trinh soan thao van ban": "notepad",
        "calculator": "calculator",
        "calc": "calculator",
        "may tinh": "calculator",
        "trinh tinh toan": "calculator",
        "microsoft paint": "paint",
        "paint": "paint",
        "drawing app": "paint",
        "ung dung ve": "paint",
        "windows terminal": "terminal",
        "terminal": "terminal",
        "command terminal": "terminal",
        "cua so lenh": "terminal",
        "windows settings": "settings",
        "cai dat windows": "settings",
        "settings": "settings",
        "system settings": "settings",
        "cai dat he thong": "settings",
        "spotify": "spotify",
        "snipping tool": "snipping_tool",
        "cong cu chup man hinh": "snipping_tool",
        "screenshot tool": "snipping_tool",
        "screen capture": "snipping_tool",
    }

    def __init__(self, catalog: ModelCatalog) -> None:
        """Khởi tạo bộ định tuyến với thư viện model dùng để nhận diện tên."""
        self.catalog = catalog

    def route(self, text: str, *, music_context: bool = False) -> Intent:
        """Chuyển câu thành intent; `music_context` cho phép hiểu đại từ tắt bài hiện tại."""
        raw = text.strip()
        normalized = _strip_polite_prefixes(_plain(raw))
        if not raw:
            return Intent(IntentType.HELP, confidence=1.0)
        if _is_non_action_context(raw, normalized):
            return Intent(IntentType.GENERAL_CHAT, {"message": raw}, confidence=0.35)

        exit_intent = self._route_exit(normalized)
        if exit_intent is not None:
            return exit_intent

        guard_intent = self._route_guard(normalized)
        if guard_intent is not None:
            return guard_intent

        close_all_commands = {
            "end",
            "end session",
            "end the session",
            "ending session",
            "close all",
            "close all models",
            "close session",
            "stop session",
            "dismiss all models",
            "remove all models",
            "ket thuc",
            "ket thuc phien",
            "dong het model",
            "tat het model",
        }
        if normalized in close_all_commands:
            return Intent(IntentType.CLOSE_MODEL, {"all": True})

        if normalized in {
            "end model",
            "ending model",
            "close",
            "close model",
            "stop model",
            "dong model",
            "dong hologram",
            "dong lai",
            "tat model",
            "an model",
            "hide model",
            "dismiss model",
            "remove model",
        }:
            return Intent(IntentType.CLOSE_MODEL)

        if any(
            term in normalized
            for term in ("clear history", "delete history", "xoa lich su", "xoa nhat ky")
        ):
            return Intent(IntentType.CLEAR_HISTORY)

        if normalized in {
            "close all research",
            "close all information",
            "dong tat ca tra cuu",
            "dong tat ca thong tin",
            "tat tat ca thong tin",
            "dismiss all research",
            "remove all information panels",
            "dong het bang thong tin",
        }:
            return Intent(IntentType.CLOSE_RESEARCH, {"all": True})

        if normalized in {
            "close research",
            "close information",
            "close search",
            "dong tra cuu",
            "dong tim kiem",
            "dong thong tin",
            "tat thong tin",
            "hide research",
            "dismiss information",
            "an bang thong tin",
        }:
            return Intent(IntentType.CLOSE_RESEARCH)

        if any(
            term in normalized
            for term in (
                "scan hand",
                "scan my hand",
                "measure hand",
                "create hand model",
                "create a hand model",
                "quet tay",
                "quet ban tay",
                "do ban tay",
                "tao model ban tay",
            )
        ):
            return Intent(IntentType.SCAN_HAND)

        # Câu có ý định tra cứu rõ ràng phải thắng model/chat, kể cả có lời dẫn lịch sự
        # hoặc tên một model như Rasengan nằm trong truy vấn.
        search = self._route_search(raw, normalized)
        if search:
            return search

        music = self._route_music(normalized, music_context=music_context)
        if music:
            return music

        close_app = self._route_close_app(normalized)
        if close_app:
            return close_app
        if normalized in {
            "stop it",
            "turn it off",
            "shut it off",
            "tat no",
            "tat di",
            "dung lai",
            "ngung lai",
        }:
            return Intent(IntentType.GENERAL_CHAT, {"message": raw}, confidence=0.35)

        model = self.catalog.match(raw)
        close_model_verbs = (
            "close",
            "end",
            "stop",
            "hide",
            "dismiss",
            "remove",
            "dong",
            "tat",
            "an",
            "bo",
        )
        starts_with_close = any(
            normalized.startswith(f"{verb} ") for verb in close_model_verbs
        )
        is_audio_command = normalized.startswith(("tat tieng", "tat am luong"))
        if starts_with_close and not is_audio_command:
            arguments = {"model_key": model.key} if model is not None else {}
            return Intent(IntentType.CLOSE_MODEL, arguments)

        model_zoom = self._route_model_zoom(normalized, model.key if model else None)
        if model_zoom:
            return model_zoom

        focus_verbs = (
            "select",
            "choose",
            "focus",
            "control",
            "switch to",
            "interact with",
            "chon",
            "dieu khien",
            "chuyen sang",
            "tuong tac voi",
        )
        if model and any(verb in normalized for verb in focus_verbs):
            return Intent(IntentType.FOCUS_MODEL, {"model_key": model.key})

        model_verbs = (
            "show",
            "display",
            "load",
            "open",
            "spawn",
            "render",
            "summon",
            "bring up",
            "put on screen",
            "hien",
            "hien thi",
            "xuat hien",
            "tao",
            "goi ra",
            "dua ra",
            "cho xem",
            "cho toi xem",
            "cho minh xem",
        )
        if model and (
            any(verb in normalized for verb in model_verbs) or len(normalized.split()) <= 5
        ):
            return Intent(IntentType.SELECT_MODEL, {"model_key": model.key})

        volume = self._route_volume(raw, normalized)
        if volume:
            return volume

        file_intent = self._route_file(raw, normalized)
        if file_intent:
            return file_intent

        app = self._route_app(normalized)
        if app:
            return app

        if normalized in {
            "help",
            "commands",
            "what can you do",
            "show commands",
            "tro giup",
            "ban lam duoc gi",
            "co nhung lenh gi",
            "huong dan su dung",
        }:
            return Intent(IntentType.HELP)

        return Intent(IntentType.GENERAL_CHAT, {"message": raw}, confidence=0.5)

    @staticmethod
    def _route_exit(normalized: str) -> Intent | None:
        """Nhận nhiều cách tắt có gọi rõ ARIS và đánh dấu đây là xác nhận trực tiếp."""
        confirmed_commands = {
            "xac nhan tat aris",
            "xac nhan dong aris",
            "xac nhan thoat aris",
            "confirm shutdown aris",
            "confirm close aris",
            "confirm exit aris",
        }
        if normalized in confirmed_commands:
            return Intent(IntentType.EXIT_ARIS, {"confirmed": True})

        aris_names = (
            "aris",
            "ari",
            "ares",
            "aries",
            "arise",
            "iris",
            "eris",
            "a r i s",
        )
        exit_phrases = (
            "tat",
            "tat nguon",
            "dong",
            "dong lai",
            "thoat",
            "thoat khoi",
            "dung",
            "dung lai",
            "ngung",
            "ngung lai",
            "nghi",
            "ket thuc",
            "shutdown",
            "shut",
            "shut down",
            "turn off",
            "power off",
            "power down",
            "close",
            "quit",
            "exit",
            "stop",
            "terminate",
        )
        has_name = any(
            re.search(rf"\b{re.escape(name)}\b", normalized) for name in aris_names
        )
        has_exit_phrase = any(
            re.search(rf"\b{re.escape(phrase)}\b", normalized)
            for phrase in exit_phrases
        )
        if has_name and has_exit_phrase:
            return Intent(IntentType.EXIT_ARIS, {"confirmed": True})
        return None

    @staticmethod
    def _route_guard(normalized: str) -> Intent | None:
        """Nhận diện lệnh sonar cục bộ trước mọi model, desktop action hoặc API cloud."""
        canonical = normalized
        for alias in ("so na", "so nar", "sonna", "sona"):
            canonical = re.sub(rf"\b{re.escape(alias)}\b", "sonar", canonical)
        if "sonar" not in canonical.split():
            return None

        arm_commands = {
            "trang thai sonar",
            "trang thai cua sonar",
            "bat sonar",
            "bat trang thai sonar",
            "bat che do sonar",
            "kich hoat sonar",
            "arm sonar",
            "activate sonar",
            "enable sonar",
        }
        disarm_commands = {
            "tat sonar",
            "dung sonar",
            "huy sonar",
            "disarm sonar",
            "deactivate sonar",
            "disable sonar",
            "stop sonar",
        }
        status_commands = {
            "kiem tra sonar",
            "sonar status",
            "sonar dang the nao",
            "sonar dang o trang thai nao",
        }
        if canonical in disarm_commands or any(
            term in canonical
            for term in ("tat sonar", "dung sonar", "huy sonar", "disarm sonar")
        ):
            return Intent(IntentType.DISARM_GUARD)
        if canonical in status_commands or any(
            term in canonical for term in ("kiem tra sonar", "sonar dang the nao")
        ):
            return Intent(IntentType.GUARD_STATUS)
        if canonical in arm_commands or any(
            term in canonical
            for term in ("trang thai sonar", "trang thai cua sonar", "kich hoat sonar")
        ):
            return Intent(IntentType.ARM_GUARD)
        return None

    def _route_model_zoom(self, normalized: str, model_key: str | None) -> Intent | None:
        """Nhận diện lệnh phóng/thu model theo phần trăm mà không gọi AI cloud."""
        zoom_in_terms = (
            "zoom in",
            "enlarge",
            "make bigger",
            "make larger",
            "bigger",
            "larger",
            "phong to",
            "phong lon",
            "lam lon",
            "lon hon",
            "mo rong",
            "tang kich thuoc",
            "scale up",
        )
        zoom_out_terms = (
            "zoom out",
            "shrink",
            "make smaller",
            "smaller",
            "thu nho",
            "lam nho",
            "nho hon",
            "giam kich thuoc",
            "scale down",
        )
        zoom_out = any(term in normalized for term in zoom_out_terms)
        zoom_in = any(term in normalized for term in zoom_in_terms) or (
            "zoom" in normalized.split() and not zoom_out
        )
        if zoom_in == zoom_out:
            return None
        number_match = re.search(r"(\d{1,3})", normalized)
        percent = int(number_match.group(1)) if number_match else 30
        arguments: dict[str, object] = {
            "operation": "in" if zoom_in else "out",
            "percent": max(1, min(100, percent)),
        }
        if model_key is not None:
            arguments["model_key"] = model_key
        return Intent(IntentType.MODEL_ZOOM, arguments)

    def _route_app(self, normalized: str) -> Intent | None:
        """Nhận diện yêu cầu mở một ứng dụng nằm trong allowlist."""
        app_verbs = (
            "open",
            "launch",
            "start",
            "run",
            "bring up",
            "go to",
            "mo",
            "bat",
            "khoi dong",
            "chay",
            "truy cap",
        )
        if not any(verb in normalized for verb in app_verbs):
            return None
        for alias, key in sorted(self.APP_ALIASES.items(), key=lambda item: -len(item[0])):
            if alias in normalized:
                return Intent(IntentType.OPEN_APP, {"app": key})
        return None

    def _route_close_app(self, normalized: str) -> Intent | None:
        """Nhận lệnh đóng app allowlist trước luật đóng model để tránh định tuyến nhầm."""
        close_verbs = (
            "close",
            "quit",
            "exit",
            "stop",
            "end",
            "terminate",
            "turn off",
            "shut down",
            "shutdown",
            "shut",
            "dong",
            "tat",
            "thoat",
            "dung",
            "ngung",
            "ket thuc",
        )
        if not any(
            re.search(rf"\b{re.escape(verb)}\b", normalized) for verb in close_verbs
        ):
            return None
        for alias, key in sorted(self.APP_ALIASES.items(), key=lambda item: -len(item[0])):
            if re.search(rf"\b{re.escape(alias)}\b", normalized):
                return Intent(IntentType.CLOSE_APP, {"app": key})
        return None

    @staticmethod
    def _route_music(normalized: str, *, music_context: bool = False) -> Intent | None:
        """Nhận lệnh phát local/YouTube, tạm dừng và tiếp tục mà không gọi AI cloud."""
        music_volume = IntentRouter._route_music_volume(normalized)
        if music_volume is not None:
            return music_volume
        stop_commands = {
            "stop music",
            "stop the music",
            "turn off music",
            "turn the music off",
            "shut off music",
            "end music",
            "tat nhac",
            "tat bai hat",
            "ngung phat nhac",
            "dung phat nhac",
            "ngung nhac",
            "ngung bai hat",
            "dung nhac",
            "dung bai hat",
            "ket thuc nhac",
        }
        contextual_stop_commands = {
            "stop it",
            "turn it off",
            "shut it off",
            "tat no",
            "tat di",
            "dung lai",
            "ngung lai",
        }
        if normalized in stop_commands or (
            music_context and normalized in contextual_stop_commands
        ):
            return Intent(IntentType.STOP_MUSIC)
        pause_commands = {
            "pause",
            "pause music",
            "tam dung",
            "tam dung nhac",
            "hold the music",
        }
        resume_commands = {
            "continue",
            "continue music",
            "resume",
            "resume music",
            "tiep tuc",
            "tiep tuc nhac",
            "phat tiep",
            "phat tiep nhac",
            "keep playing",
            "continue the song",
            "cho nhac chay tiep",
        }
        if normalized in pause_commands:
            return Intent(IntentType.PAUSE_MUSIC)
        if normalized in resume_commands:
            return Intent(IntentType.RESUME_MUSIC)

        # Tên bài này rất gần một câu tiếng Việt thông thường. Nhận local cả khi
        # người dùng nói `mở <tên bài>` mà không chèn từ `nhạc`, tránh một lượt AI.
        title_tokens = set(normalized.split())
        known_minh_anh_title = (
            "nay" in title_tokens
            and bool(title_tokens.intersection({"noi", "oi"}))
            and bool(title_tokens.intersection({"anh", "minh"}))
            and "co" not in title_tokens
        )
        starts_with_play_verb = normalized.startswith(
            ("mo ", "bat ", "phat ", "nghe ", "play ", "put on ")
        )
        if known_minh_anh_title and starts_with_play_verb:
            query = re.sub(
                r"^(?:mo|bat|phat|nghe|play|put on)\s+(?:nhac\s+)?",
                "",
                normalized,
            )
            return Intent(IntentType.PLAY_MUSIC, {"query": query})

        match = re.match(
            r"^(?:phat|play|mo|bat|nghe|listen to|put on|start playing|cho nghe)\s+"
            r"(?:nhac|music|bai hat|bai|song|track)"
            r"(?:\s+(.*))?$",
            normalized,
        )
        if match is None:
            return None
        query = (match.group(1) or "").strip()
        query = re.sub(r"^(?:bai|bai hat|nhac|song|track)\s+", "", query)
        return Intent(IntentType.PLAY_MUSIC, {"query": query})

    @staticmethod
    def _route_music_volume(normalized: str) -> Intent | None:
        """Tách âm lượng nhạc khỏi âm lượng Windows và giữ phần trăm chính xác."""
        has_music_volume = (
            "am luong nhac" in normalized
            or "music volume" in normalized
            or "volume nhac" in normalized
            or (
                any(word in normalized for word in ("tang", "giam", "raise", "lower"))
                and any(word in normalized.split() for word in ("nhac", "music"))
            )
        )
        if not has_music_volume:
            return None
        number_match = re.search(r"(\d{1,3})", normalized)
        percent = max(0, min(100, int(number_match.group(1)))) if number_match else 10
        if any(word in normalized for word in ("giam", "lower", "down", "nho")):
            operation = "down"
        elif any(word in normalized for word in ("tang", "raise", "up", "to hon")):
            operation = "up"
        else:
            operation = "set"
        return Intent(IntentType.MUSIC_VOLUME, {"operation": operation, "percent": percent})

    def _route_volume(self, raw: str, normalized: str) -> Intent | None:
        """Nhận diện bước, phần trăm tương đối hoặc mức âm lượng đích mà không cần API."""
        natural_volume = any(
            phrase in normalized
            for phrase in (
                "turn it up",
                "turn it down",
                "make it louder",
                "make it quieter",
                "louder",
                "quieter",
                "to hon",
                "nho hon",
            )
        )
        if not natural_volume and not any(
            word in normalized for word in ("volume", "sound", "am luong", "tieng")
        ):
            return None
        if any(word in normalized for word in ("mute", "tat tieng", "im lang")):
            return Intent(IntentType.VOLUME, {"operation": "mute", "steps": 1})
        number_match = re.search(r"(\d{1,3})", normalized)
        has_percent_unit = (
            "%" in raw or "percent" in normalized or "phan tram" in normalized
        )
        is_down = any(
            word in normalized
            for word in ("down", "decrease", "lower", "quieter", "giam", "xuong", "nho hon")
        )
        is_up = any(
            word in normalized
            for word in ("up", "increase", "raise", "louder", "tang", "len", "to hon")
        )
        if number_match and has_percent_unit:
            percent = max(0, min(100, int(number_match.group(1))))
            if is_down:
                return Intent(IntentType.VOLUME, {"operation": "down", "percent": percent})
            if is_up:
                return Intent(IntentType.VOLUME, {"operation": "up", "percent": percent})
            return Intent(IntentType.VOLUME, {"operation": "set", "percent": percent})
        if number_match and any(word in normalized for word in ("set", "dat", "chinh")):
            percent = max(0, min(100, int(number_match.group(1))))
            return Intent(IntentType.VOLUME, {"operation": "set", "percent": percent})
        steps_match = re.search(r"(\d{1,2})", normalized)
        steps = max(1, min(20, int(steps_match.group(1)))) if steps_match else 3
        if is_down:
            return Intent(IntentType.VOLUME, {"operation": "down", "steps": steps})
        return Intent(IntentType.VOLUME, {"operation": "up", "steps": steps})

    def _route_search(self, raw: str, normalized: str) -> Intent | None:
        """Trích xuất truy vấn tra cứu có chủ đích để không tự gọi cloud mọi câu hỏi."""
        patterns = (
            r"(?:search(?:ing)?(?: google)?(?: for)?|google|look up|research|find information"
            r"(?: about| on)?|tell me the latest about)\s+"
            r"(?:(?:information|thong tin)(?: moi nhat)?(?: about| ve)?\s+)?(.+)$",
            r"(?:tim kiem(?:(?: tren)? google)?|tra google|tra cuu|tim thong tin(?: ve)?|"
            r"tim hieu(?: ve)?|kiem tra thong tin(?: ve)?|cap nhat thong tin(?: ve)?|"
            r"thong tin ve|thong tin moi nhat ve|tin moi nhat ve)\s+(.+)$",
        )
        for pattern in patterns:
            match = re.search(pattern, normalized, flags=re.IGNORECASE)
            if match:
                query = _raw_suffix_for_plain(raw, match.group(1))
                return Intent(IntentType.GOOGLE_SEARCH, {"query": query})
        return None

    def _route_file(self, raw: str, normalized: str) -> Intent | None:
        """Trích xuất tên file cần mở; kiểm tra đường dẫn được thực hiện ở lớp desktop."""
        patterns = (
            r"^(?:open|find|locate|show me)\s+(?:the\s+)?file\s+(.+)$",
            r"^(?:mo|tim|kiem|tim giup)\s+(?:tep|file)\s+(.+)$",
        )
        for pattern in patterns:
            match = re.match(pattern, normalized, flags=re.IGNORECASE)
            if match:
                query = _raw_suffix_for_plain(raw, match.group(1))
                return Intent(IntentType.OPEN_FILE, {"query": query})
        return None
