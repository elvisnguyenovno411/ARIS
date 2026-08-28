from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
ASSETS_DIR = PROJECT_ROOT / "assets"


def bounded_environment_int(
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    """Đọc số nguyên từ biến môi trường rồi kẹp trong khoảng hiệu năng an toàn."""
    try:
        value = int(os.getenv(name, str(default)).strip())
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


def environment_flag(name: str, default: bool) -> bool:
    """Đọc cờ true/false từ môi trường và dùng mặc định nếu giá trị không hợp lệ."""
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def default_safe_roots() -> tuple[Path, ...]:
    """Trả về các thư mục chỉ-đọc mà ARIS được phép tìm và mở file."""
    home = Path.home()
    candidates = (
        home / "Desktop",
        home / "Documents",
        home / "Downloads",
        home / "OneDrive" / "Desktop",
        home / "OneDrive" / "Documents",
        home / "OneDrive" / "Downloads",
        PROJECT_ROOT,
    )
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        key = os.path.normcase(str(resolved))
        if candidate.exists() and key not in seen:
            unique.append(resolved)
            seen.add(key)
    return tuple(unique)


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Chứa cấu hình runtime; bí mật chỉ được đọc từ biến môi trường hoặc `.env`."""

    project_root: Path
    data_dir: Path
    assets_dir: Path
    state_file: Path
    openai_api_key: str | None
    openai_model: str
    web_search_enabled: bool
    web_search_model: str
    web_search_request_limit: int
    web_search_cache_seconds: int
    transcription_model: str
    transcription_language: str | None
    cloud_tts_enabled: bool
    youtube_music_enabled: bool
    tts_model: str
    tts_voice: str
    tts_instructions: str
    default_language: str
    gesture_mode: str
    audio_input_device: str | None
    auto_listen: bool
    hardware_enabled: bool
    hardware_port: str | None
    render_fps: int
    vision_fps: int
    vision_width: int
    vision_height: int
    safe_roots: tuple[Path, ...]

    @property
    def api_enabled(self) -> bool:
        """Cho biết OpenAI API key đã được cấu hình hay chưa mà không làm lộ key."""
        return bool(self.openai_api_key)

    @classmethod
    def load(cls) -> AppConfig:
        """Nạp cấu hình ứng dụng và tạo thư mục dữ liệu local khi cần."""
        # Ưu tiên `.env` của chính dự án để không vô tình dùng nhầm key toàn hệ thống.
        load_dotenv(PROJECT_ROOT / ".env", override=True)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        api_opt_in = os.getenv("ARIS_ENABLE_OPENAI", "false").strip().casefold()
        api_enabled = api_opt_in in {"1", "true", "yes", "on"}
        api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        web_search_opt_in = environment_flag("ARIS_ENABLE_WEB_SEARCH", False)
        language = os.getenv("ARIS_LANGUAGE", "en").strip().lower()
        if language not in {"en", "vi"}:
            language = "en"
        transcription_language = os.getenv(
            "ARIS_TRANSCRIPTION_LANGUAGE",
            "auto",
        ).strip().lower()
        if transcription_language == "auto":
            transcription_language = None
        elif transcription_language not in {"en", "vi"}:
            transcription_language = language
        gesture_mode = os.getenv("ARIS_GESTURE_MODE", "spatial").strip().casefold()
        if gesture_mode not in {"spatial", "grab_throw", "legacy"}:
            gesture_mode = "spatial"
        return cls(
            project_root=PROJECT_ROOT,
            data_dir=DATA_DIR,
            assets_dir=ASSETS_DIR,
            state_file=DATA_DIR / "aris_state.json",
            openai_api_key=(api_key or None) if api_enabled else None,
            openai_model=os.getenv("ARIS_OPENAI_MODEL", "gpt-5.6-terra"),
            web_search_enabled=api_enabled and web_search_opt_in and bool(api_key),
            web_search_model=os.getenv(
                "ARIS_WEB_SEARCH_MODEL",
                os.getenv("ARIS_OPENAI_MODEL", "gpt-5.6-terra"),
            ).strip()
            or "gpt-5.6-terra",
            web_search_request_limit=bounded_environment_int(
                "ARIS_WEB_SEARCH_SESSION_LIMIT",
                20,
                1,
                100,
            ),
            web_search_cache_seconds=bounded_environment_int(
                "ARIS_WEB_SEARCH_CACHE_SECONDS",
                300,
                0,
                3600,
            ),
            transcription_model=os.getenv("ARIS_TRANSCRIPTION_MODEL", "gpt-transcribe"),
            transcription_language=transcription_language,
            cloud_tts_enabled=(
                api_enabled and environment_flag("ARIS_ENABLE_CLOUD_TTS", False)
            ),
            youtube_music_enabled=environment_flag("ARIS_ENABLE_YOUTUBE_MUSIC", True),
            tts_model=os.getenv("ARIS_TTS_MODEL", "gpt-4o-mini-tts"),
            tts_voice=os.getenv("ARIS_TTS_VOICE", "marin"),
            tts_instructions=os.getenv(
                "ARIS_TTS_INSTRUCTIONS",
                "Speak in a calm, low-pitched feminine voice with a warm, futuristic tone "
                "at a moderately brisk pace. Be concise, precise, composed, and quietly "
                "authoritative. Use clean Vietnamese diction, restrained emotion, and avoid "
                "long pauses. Do not imitate any real person or fictional character.",
            ),
            default_language=language,
            gesture_mode=gesture_mode,
            audio_input_device=os.getenv("ARIS_AUDIO_INPUT_DEVICE") or None,
            auto_listen=environment_flag("ARIS_AUTO_LISTEN", True),
            hardware_enabled=environment_flag("ARIS_ENABLE_HARDWARE", False),
            hardware_port=(os.getenv("ARIS_HARDWARE_PORT") or "").strip() or None,
            render_fps=bounded_environment_int("ARIS_RENDER_FPS", 60, 30, 120),
            vision_fps=bounded_environment_int("ARIS_VISION_FPS", 24, 12, 30),
            vision_width=bounded_environment_int("ARIS_VISION_WIDTH", 480, 320, 640),
            vision_height=bounded_environment_int("ARIS_VISION_HEIGHT", 360, 240, 480),
            safe_roots=default_safe_roots(),
        )
