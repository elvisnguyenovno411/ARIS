from __future__ import annotations

import difflib
import threading
import unicodedata
from pathlib import Path

import numpy as np
from PySide6.QtCore import QEasingCurve, QObject, QTimer, QUrl, QVariantAnimation, Signal
from PySide6.QtMultimedia import (
    QAudioBuffer,
    QAudioBufferOutput,
    QAudioFormat,
    QAudioOutput,
    QMediaPlayer,
)

from aris.core.types import ActionResult
from aris.media.music_query import normalize_music_query
from aris.media.youtube_stream import YouTubeAudioResolver, YouTubeMusicError, YouTubeStream

SUPPORTED_AUDIO_EXTENSIONS = frozenset({".flac", ".m4a", ".mp3", ".ogg", ".wav", ".wma"})
MAX_LIBRARY_FILES = 2500


def _plain(text: str) -> str:
    """Chuẩn hóa tên bài hát để so khớp không phân biệt dấu, hoa thường và dấu câu."""
    normalized = unicodedata.normalize("NFD", text.casefold())
    without_marks = "".join(
        character for character in normalized if unicodedata.category(character) != "Mn"
    ).replace("đ", "d")
    return " ".join(
        "".join(character if character.isalnum() else " " for character in without_marks).split()
    )


def default_music_roots(assets_dir: Path) -> tuple[Path, ...]:
    """Tắt duyệt nhạc local mặc định để ARIS không đọc media cá nhân trên máy."""
    del assets_dir
    return ()


class LocalMusicLibrary:
    """Tìm bài hát trong các thư mục local cố định mà không nhận đường dẫn từ AI."""

    def __init__(self, roots: tuple[Path, ...]) -> None:
        """Lưu các thư mục gốc đã resolve để mọi kết quả luôn nằm trong allowlist nhạc."""
        self.roots = tuple(
            Path(root).resolve(strict=False) for root in roots if Path(root).is_dir()
        )

    def tracks(self) -> tuple[Path, ...]:
        """Quét tối đa một số file hữu hạn và trả danh sách audio local hợp lệ."""
        found: list[Path] = []
        seen: set[str] = set()
        for root in self.roots:
            try:
                candidates = root.rglob("*")
                for candidate in candidates:
                    if len(found) >= MAX_LIBRARY_FILES:
                        break
                    if (
                        not candidate.is_file()
                        or candidate.suffix.casefold() not in SUPPORTED_AUDIO_EXTENSIONS
                    ):
                        continue
                    resolved = candidate.resolve(strict=True)
                    if not resolved.is_relative_to(root):
                        continue
                    key = str(resolved).casefold()
                    if key not in seen:
                        found.append(resolved)
                        seen.add(key)
            except (OSError, RuntimeError):
                continue
            if len(found) >= MAX_LIBRARY_FILES:
                break
        return tuple(found)

    def resolve(self, query: str) -> Path | None:
        """Chọn bài gần nhất với tên gọi; truy vấn trống chọn file mới nhất trong thư viện."""
        tracks = self.tracks()
        if not tracks:
            return None
        clean_query = _plain(query)
        if not clean_query:
            return max(tracks, key=self._modified_time)

        query_terms = set(clean_query.split())

        def score(path: Path) -> tuple[float, float, str]:
            """Xếp hạng tên file theo độ khớp, thời gian sửa và đường dẫn ổn định."""
            clean_stem = _plain(path.stem)
            stem_terms = set(clean_stem.split())
            if clean_stem == clean_query:
                match = 4.0
            elif clean_stem.startswith(clean_query):
                match = 3.2
            elif clean_query in clean_stem:
                match = 2.8
            elif query_terms and query_terms.issubset(stem_terms):
                match = 2.4
            else:
                match = difflib.SequenceMatcher(None, clean_query, clean_stem).ratio()
            return match, self._modified_time(path), str(path).casefold()

        best = max(tracks, key=score)
        return best if score(best)[0] >= 0.48 else None

    @staticmethod
    def _modified_time(path: Path) -> float:
        """Trả thời điểm sửa file và dùng 0 nếu metadata không đọc được."""
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0


def audio_buffer_level(buffer: QAudioBuffer) -> float:
    """Đổi PCM Qt thành RMS 0–1 để HUD phản ứng theo nhạc mà không lưu audio."""
    if not buffer.isValid() or buffer.byteCount() <= 0:
        return 0.0
    sample_format = buffer.format().sampleFormat()
    raw = buffer.constData()
    if sample_format is QAudioFormat.SampleFormat.UInt8:
        samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sample_format is QAudioFormat.SampleFormat.Int16:
        samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sample_format is QAudioFormat.SampleFormat.Int32:
        samples = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    elif sample_format is QAudioFormat.SampleFormat.Float:
        samples = np.frombuffer(raw, dtype="<f4").astype(np.float32)
    else:
        return 0.0
    if samples.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
    return max(0.0, min(1.0, rms * 3.4))


class MusicPlayer(QObject):
    """Phát nhạc local hoặc YouTube bằng FFmpeg và gửi nhịp PCM trực tiếp cho HUD."""

    playing_changed = Signal(bool)
    level_changed = Signal(float)
    playback_reference_changed = Signal(float)
    track_changed = Signal(str)
    stream_started = Signal(str)
    error_occurred = Signal(str)
    _stream_resolved = Signal(int, object)
    _stream_failed = Signal(int, str)

    def __init__(
        self,
        roots: tuple[Path, ...],
        parent: QObject | None = None,
        volume: float = 0.72,
        youtube_enabled: bool = True,
    ) -> None:
        """Tạo player FFmpeg riêng và cấu hình fallback YouTube không lưu file."""
        super().__init__(parent)
        self.library = LocalMusicLibrary(roots)
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._buffer_output = QAudioBufferOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._player.setAudioBufferOutput(self._buffer_output)
        self._player.setLoops(QMediaPlayer.Loops.Infinite)
        self._base_volume = max(0.0, min(1.0, float(volume)))
        self._audio_output.setVolume(self._base_volume)
        self._volume_animation = QVariantAnimation(self)
        self._volume_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._volume_animation.valueChanged.connect(self._on_volume_animation_value)
        self._buffer_output.audioBufferReceived.connect(self._on_audio_buffer)
        self._player.errorOccurred.connect(self._on_error)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._stream_resolved.connect(self._on_stream_resolved)
        self._stream_failed.connect(self._on_stream_failed)
        self.youtube = YouTubeAudioResolver(youtube_enabled)
        self._current_track: Path | None = None
        self._current_title: str | None = None
        self._pending_stream_title: str | None = None
        self._stream_lookup_pending = False
        self._request_generation = 0
        self._playing = False
        self._ducked = False
        self._baseline_level = 0.0

    @property
    def is_playing(self) -> bool:
        """Cho biết bài hiện tại đang chạy, không tính trạng thái tạm dừng."""
        return self._playing

    @property
    def current_track_name(self) -> str | None:
        """Trả tên file không có đuôi để phản hồi mà không làm lộ đường dẫn cá nhân."""
        return self._current_title

    @property
    def has_music_context(self) -> bool:
        """Cho biết có bài đang phát, tạm dừng hoặc chờ YouTube để hiểu lệnh `tắt nó`."""
        return self._current_title is not None or self._stream_lookup_pending

    @property
    def volume_percent(self) -> int:
        """Trả mức âm lượng nhạc riêng của ARIS dưới dạng phần trăm nguyên."""
        return round(self._base_volume * 100)

    def play(self, query: str = "") -> ActionResult:
        """Phát lặp bài được gọi tên; bài mới tự hủy vòng lặp của bài cũ."""
        clean_query = normalize_music_query(query)
        if not clean_query and self._current_title is not None:
            return self.resume()
        track = self.library.resolve(clean_query)
        if track is None:
            if not clean_query:
                return ActionResult(False, "Chưa có bài nhạc local nào để phát hoặc tiếp tục.")
            if not self.youtube.enabled:
                return ActionResult(
                    False,
                    "Không tìm thấy file local và tính năng nhạc YouTube đang tắt.",
                )
            self._request_generation += 1
            generation = self._request_generation
            self._pending_stream_title = None
            self._stream_lookup_pending = True
            self._player.stop()
            self._player.setSource(QUrl())
            self._current_track = None
            self._current_title = None
            self._set_playing(False)
            self.level_changed.emit(0.0)
            threading.Thread(
                target=self._resolve_stream,
                args=(generation, clean_query),
                name="aris-youtube-music",
                daemon=True,
            ).start()
            return ActionResult(
                True,
                f"Đang tìm {clean_query} trên YouTube.",
                {"query": clean_query, "source": "youtube", "pending": True},
            )
        self._request_generation += 1
        self._pending_stream_title = None
        self._stream_lookup_pending = False
        changing_track = self._current_track != track
        self._current_track = track
        self._current_title = track.stem
        if changing_track:
            self._player.stop()
            self._player.setSource(QUrl.fromLocalFile(str(track)))
            self.track_changed.emit(track.stem)
        self._player.setLoops(QMediaPlayer.Loops.Infinite)
        self._set_playing(True)
        self._player.play()
        return ActionResult(
            True,
            f"Đang phát lặp lại {track.stem}.",
            {"track": track.stem},
        )

    def pause(self) -> ActionResult:
        """Tạm dừng bài hiện tại nhưng giữ nguyên vị trí và vòng lặp."""
        if self._current_title is None:
            return ActionResult(False, "Chưa có bài nhạc nào đang được chọn.")
        self._player.pause()
        self._set_playing(False)
        self.level_changed.emit(0.0)
        return ActionResult(True, f"Đã tạm dừng {self._current_title}.")

    def resume(self) -> ActionResult:
        """Tiếp tục bài đang tạm dừng tại đúng vị trí trước đó."""
        if self._current_title is None:
            return ActionResult(False, "Chưa có bài nhạc nào để tiếp tục.")
        self._set_playing(True)
        self._player.play()
        return ActionResult(True, f"Đang tiếp tục {self._current_title}.")

    def stop_playback(self) -> ActionResult:
        """Tắt hẳn bài/lookup hiện tại và xóa vị trí để `tiếp tục` không phát lại."""
        if not self.has_music_context:
            return ActionResult(False, "Không có bài nhạc nào để tắt.")
        self.stop()
        return ActionResult(True, "Đã tắt nhạc.")

    def set_ducked(self, enabled: bool) -> None:
        """Hạ nhạc rất nhanh khi nghe giọng và phục hồi chậm để câu lệnh không bị lấn."""
        value = bool(enabled)
        if self._ducked == value:
            return
        self._ducked = value
        self._animate_output_volume(90 if value else 480)

    def change_volume(self, operation: str, percent: int) -> ActionResult:
        """Đặt hoặc tăng/giảm âm lượng nhạc độc lập với âm lượng Windows."""
        amount = max(0, min(100, int(percent)))
        current = self.volume_percent
        if operation == "up":
            target = min(100, current + amount)
        elif operation == "down":
            target = max(0, current - amount)
        else:
            target = amount
        self._base_volume = target / 100.0
        self._animate_output_volume(220)
        return ActionResult(
            True,
            f"Âm lượng nhạc đã đặt ở {target}%.",
            {"music_volume": target},
        )

    def stop(self) -> None:
        """Dừng và giải phóng source khi ứng dụng đóng hoặc bảo vệ được kích hoạt."""
        self._request_generation += 1
        self._pending_stream_title = None
        self._stream_lookup_pending = False
        self._player.stop()
        self._player.setSource(QUrl())
        self._current_track = None
        self._current_title = None
        self._set_playing(False)
        self.level_changed.emit(0.0)
        self.playback_reference_changed.emit(0.0)

    def _resolve_stream(self, generation: int, query: str) -> None:
        """Tìm URL audio trong worker để yt-dlp không làm đứng animation giao diện."""
        try:
            stream = self.youtube.resolve(query)
        except YouTubeMusicError as error:
            self._stream_failed.emit(generation, str(error))
            return
        self._stream_resolved.emit(generation, stream)

    def _animate_output_volume(self, duration_ms: int) -> None:
        """Nội suy gain đầu ra để chỉnh âm lượng và ducking không tạo bước nhảy."""
        duck_gain = 0.16 if self._ducked else 1.0
        target = max(0.0, min(1.0, self._base_volume * duck_gain))
        self._volume_animation.stop()
        self._volume_animation.setDuration(max(80, int(duration_ms)))
        self._volume_animation.setStartValue(float(self._audio_output.volume()))
        self._volume_animation.setEndValue(target)
        self._volume_animation.start()

    def _on_volume_animation_value(self, value: object) -> None:
        """Áp một frame gain đã nội suy vào QAudioOutput trên UI thread."""
        self._audio_output.setVolume(max(0.0, min(1.0, float(value))))

    def _on_stream_resolved(self, generation: int, payload: object) -> None:
        """Đưa URL YouTube hợp lệ vào QMediaPlayer trên đúng UI thread."""
        if generation != self._request_generation or not isinstance(payload, YouTubeStream):
            return
        self._stream_lookup_pending = False
        self._player.stop()
        self._current_track = None
        self._current_title = payload.title
        self._pending_stream_title = payload.title
        self._player.setSource(QUrl(payload.stream_url))
        self._player.setLoops(QMediaPlayer.Loops.Infinite)
        self.track_changed.emit(payload.title)
        self._player.play()

    def _on_stream_failed(self, generation: int, message: str) -> None:
        """Báo lỗi tìm YouTube hiện hành và bỏ qua response cũ đã bị đổi bài."""
        if generation != self._request_generation:
            return
        self._stream_lookup_pending = False
        self._set_playing(False)
        self.level_changed.emit(0.0)
        self.error_occurred.emit(message[:180])

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        """Chỉ xác nhận YouTube sau khi backend FFmpeg thật sự chuyển sang phát."""
        if state is not QMediaPlayer.PlaybackState.PlayingState:
            return
        self._set_playing(True)
        if self._pending_stream_title is not None:
            title = self._pending_stream_title
            self._pending_stream_title = None
            self.stream_started.emit(title)

    def _set_playing(self, playing: bool) -> None:
        """Chỉ phát signal khi trạng thái visual thực sự thay đổi."""
        value = bool(playing)
        if self._playing == value:
            return
        self._playing = value
        self.playing_changed.emit(value)

    def _on_audio_buffer(self, buffer: QAudioBuffer) -> None:
        """Suy ra transient theo nền RMS động để vòng HUD nảy mạnh tại nhịp trống."""
        if not self._playing:
            return
        level = audio_buffer_level(buffer)
        playback_reference = min(1.0, level * float(self._audio_output.volume()))
        self.playback_reference_changed.emit(playback_reference)
        self._baseline_level += (level - self._baseline_level) * 0.055
        transient = max(0.0, level - self._baseline_level * 0.9)
        visual_level = min(1.0, level * 0.7 + transient * 3.8)
        self.level_changed.emit(visual_level)

    def _on_error(self, _error: QMediaPlayer.Error, message: str) -> None:
        """Chờ xác nhận lỗi để bỏ qua cảnh báo tạm hoặc lỗi thuộc source đã thay."""
        generation = self._request_generation
        source_url = self._player.source().toString()
        safe_message = message.strip()[:180] or "Định dạng nhạc không thể phát trên máy này."
        QTimer.singleShot(
            750,
            lambda: self._finalize_error(generation, source_url, safe_message),
        )

    def _finalize_error(self, generation: int, source_url: str, message: str) -> None:
        """Chỉ phát lỗi nếu đúng source hiện tại đã thực sự ngừng sau khoảng chờ."""
        if generation != self._request_generation:
            return
        if not source_url or source_url != self._player.source().toString():
            return
        if self._player.playbackState() is QMediaPlayer.PlaybackState.PlayingState:
            return
        self._pending_stream_title = None
        self._set_playing(False)
        self.level_changed.emit(0.0)
        self.error_occurred.emit(message)
