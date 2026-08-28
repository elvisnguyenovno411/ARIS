from __future__ import annotations

import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


class YouTubeMusicError(RuntimeError):
    """Biểu diễn lỗi tìm hoặc xác thực luồng nhạc YouTube an toàn cho giao diện."""


@dataclass(frozen=True, slots=True)
class YouTubeStream:
    """Chứa tiêu đề và URL audio tạm thời đã được yt-dlp chọn mà không tải file."""

    title: str
    stream_url: str


class _QuietLogger:
    def debug(self, _message: str) -> None:
        """Nuốt log debug của yt-dlp để không in URL luồng ký số ra terminal."""
        return

    def warning(self, _message: str) -> None:
        """Nuốt cảnh báo yt-dlp; resolver sẽ chuyển lỗi thành thông báo ARIS an toàn."""
        return

    def error(self, _message: str) -> None:
        """Nuốt log lỗi thô để tránh lộ metadata kết nối hoặc caption không cần thiết."""
        return


class YouTubeAudioResolver:
    """Tìm đúng một kết quả YouTube và trả luồng audio HTTPS cho FFmpeg của Qt."""

    def __init__(self, enabled: bool = True) -> None:
        """Bật hoặc khóa fallback mạng theo cấu hình runtime của ARIS."""
        self.enabled = bool(enabled)
        self._cache: dict[str, tuple[float, YouTubeStream]] = {}
        self._cache_lock = threading.Lock()
        self._cache_seconds = 300.0

    def resolve(self, query: str) -> YouTubeStream:
        """Tìm một bài theo tên bằng yt-dlp; không tải hoặc ghi nội dung xuống đĩa."""
        if not self.enabled:
            raise YouTubeMusicError("Tính năng nhạc YouTube đang bị tắt trong cấu hình.")
        clean_query = " ".join(query.replace("\r", " ").replace("\n", " ").split())[:120]
        if len(clean_query) < 2:
            raise YouTubeMusicError("Hãy nói rõ tên bài hát cần phát.")
        cache_key = clean_query.casefold()
        now = time.monotonic()
        with self._cache_lock:
            cached = self._cache.get(cache_key)
            if cached is not None and now - cached[0] <= self._cache_seconds:
                return cached[1]
        try:
            import yt_dlp
        except ImportError as error:
            raise YouTubeMusicError("Thiếu yt-dlp. Hãy cài lại dependencies của ARIS.") from error

        options: dict[str, Any] = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "logger": _QuietLogger(),
            "noplaylist": True,
            "playlist_items": "1",
            "skip_download": True,
            "writesubtitles": False,
            "writeautomaticsub": False,
            "socket_timeout": 12,
            "retries": 2,
            "fragment_retries": 1,
        }
        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(
                    f"ytsearch1:{clean_query}",
                    download=False,
                )
        except Exception as error:
            raise YouTubeMusicError("Không thể kết nối hoặc tìm bài trên YouTube.") from error
        stream = self._parse_result(info)
        with self._cache_lock:
            self._cache[cache_key] = (time.monotonic(), stream)
        return stream

    @staticmethod
    def _parse_result(info: Any) -> YouTubeStream:
        """Xác thực metadata yt-dlp và chỉ chấp nhận URL HTTPS thuộc hạ tầng YouTube."""
        entry: Mapping[str, Any] | None = None
        if isinstance(info, Mapping):
            entries = info.get("entries")
            if entries is not None:
                entry = next(
                    (item for item in entries if isinstance(item, Mapping)),
                    None,
                )
            else:
                entry = info
        if entry is None:
            raise YouTubeMusicError("Không tìm thấy kết quả YouTube phù hợp.")

        stream_url = str(entry.get("url") or "").strip()
        if not stream_url:
            requested = entry.get("requested_downloads")
            if isinstance(requested, list) and requested and isinstance(requested[0], Mapping):
                stream_url = str(requested[0].get("url") or "").strip()
        parsed = urlparse(stream_url)
        host = (parsed.hostname or "").casefold()
        trusted_host = (
            host == "youtube.com"
            or host.endswith(".youtube.com")
            or host.endswith(".googlevideo.com")
            or host.endswith(".googleusercontent.com")
        )
        if parsed.scheme != "https" or not trusted_host:
            raise YouTubeMusicError("YouTube trả về một địa chỉ audio không hợp lệ.")

        duration = entry.get("duration")
        if isinstance(duration, (int, float)) and duration > 60 * 60:
            raise YouTubeMusicError("Bản beta chỉ phát nội dung dài tối đa 60 phút.")
        raw_title = str(entry.get("title") or "YouTube Music")
        printable_title = "".join(
            character if character.isprintable() else " " for character in raw_title
        )
        safe_title = " ".join(printable_title.split())[:100]
        return YouTubeStream(safe_title or "YouTube Music", stream_url)
