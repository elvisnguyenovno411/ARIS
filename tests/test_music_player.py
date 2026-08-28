from __future__ import annotations

import os
import struct
import time

import pytest
from PySide6.QtMultimedia import QAudioBuffer, QAudioFormat

from aris.media.music_player import (
    LocalMusicLibrary,
    MusicPlayer,
    audio_buffer_level,
    default_music_roots,
)
from aris.media.youtube_stream import YouTubeAudioResolver, YouTubeMusicError, YouTubeStream


def test_music_library_matches_names_without_accents(tmp_path) -> None:
    """Đảm bảo tên nói không dấu vẫn tìm đúng file nhạc Unicode trong allowlist."""
    expected = tmp_path / "Bầu Trời Mới.mp3"
    expected.write_bytes(b"test")
    (tmp_path / "Different Song.mp3").write_bytes(b"test")
    library = LocalMusicLibrary((tmp_path,))

    assert library.resolve("bau troi moi") == expected.resolve()


def test_empty_music_query_selects_newest_file(tmp_path) -> None:
    """Đảm bảo lệnh phát nhạc trống chọn bài mới nhất một cách xác định."""
    older = tmp_path / "Older.mp3"
    newer = tmp_path / "Newer.flac"
    older.write_bytes(b"old")
    newer.write_bytes(b"new")
    os.utime(older, (10.0, 10.0))
    os.utime(newer, (20.0, 20.0))

    assert LocalMusicLibrary((tmp_path,)).resolve("") == newer.resolve()


def test_runtime_music_roots_do_not_scan_personal_files(tmp_path) -> None:
    """Đảm bảo HUD mặc định không lấy nhạc từ Downloads, Music hay thư mục dự án."""
    (tmp_path / "personal_music").mkdir()

    assert default_music_roots(tmp_path) == ()


def test_audio_buffer_level_normalizes_pcm_for_hud() -> None:
    """Đảm bảo PCM từ Qt được đổi thành mức beat hữu hạn mà không lưu file."""
    audio_format = QAudioFormat()
    audio_format.setSampleRate(44_100)
    audio_format.setChannelCount(1)
    audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
    payload = struct.pack("<hhhh", 0, 12_000, -12_000, 24_000)
    buffer = QAudioBuffer(payload, audio_format)

    level = audio_buffer_level(buffer)

    assert 0.5 < level <= 1.0


def test_youtube_result_accepts_valid_google_audio_stream() -> None:
    """Đảm bảo resolver chỉ lấy kết quả đầu và giữ tiêu đề gọn cho phản hồi ARIS."""
    stream = YouTubeAudioResolver._parse_result(
        {
            "entries": [
                {
                    "title": "Nơi Này Có Anh - Official Music Video",
                    "url": "https://rr1---sn.example.googlevideo.com/videoplayback?id=test",
                    "duration": 268,
                }
            ]
        }
    )

    assert stream.title == "Nơi Này Có Anh - Official Music Video"
    assert stream.stream_url.startswith("https://")


def test_youtube_result_rejects_untrusted_stream_host() -> None:
    """Đảm bảo metadata mạng không thể khiến FFmpeg gọi sang host tùy ý."""
    with pytest.raises(YouTubeMusicError, match="không hợp lệ"):
        YouTubeAudioResolver._parse_result(
            {
                "entries": [
                    {
                        "title": "Untrusted",
                        "url": "https://example.com/audio.mp3",
                    }
                ]
            }
        )


def test_youtube_resolver_reuses_recent_stream_from_ram(monkeypatch) -> None:
    """Đảm bảo cùng bài trong năm phút dùng cache RAM và không tìm YouTube lần nữa."""
    resolver = YouTubeAudioResolver()
    stream = YouTubeStream(
        "Cached Song",
        "https://rr1---sn.example.googlevideo.com/videoplayback?id=cached",
    )
    resolver._cache["cached song"] = (time.monotonic(), stream)  # noqa: SLF001

    def fail_import(_name: str):
        raise AssertionError("yt-dlp must not load for a fresh RAM cache hit")

    monkeypatch.setattr("builtins.__import__", fail_import)

    assert resolver.resolve("Cached Song") == stream


def test_music_volume_is_bounded_and_independent(qtbot, tmp_path) -> None:
    """Đảm bảo gain nhạc nhận mức đích/tương đối nhưng luôn nằm trong 0–100%."""
    player = MusicPlayer((tmp_path,), volume=0.72, youtube_enabled=False)

    assert player.change_volume("set", 55).data["music_volume"] == 55
    assert player.change_volume("up", 80).data["music_volume"] == 100
    assert player.change_volume("down", 130).data["music_volume"] == 0
    assert player.volume_percent == 0
    qtbot.wait(250)
    player.stop()


def test_music_ducking_drops_quickly_to_voice_safe_level(qtbot, tmp_path) -> None:
    """Đảm bảo pre-duck hạ nhạc sâu và nhanh để wake word không bị âm thanh che lấp."""
    player = MusicPlayer((tmp_path,), volume=0.75, youtube_enabled=False)

    player.set_ducked(True)

    assert player._volume_animation.duration() == 90  # noqa: SLF001
    assert float(player._volume_animation.endValue()) == pytest.approx(0.12)  # noqa: SLF001
    qtbot.wait(120)
    assert float(player._audio_output.volume()) == pytest.approx(0.12, abs=0.02)  # noqa: SLF001
    player.stop()


def test_stop_playback_clears_track_and_prevents_resume(tmp_path) -> None:
    """Đảm bảo lệnh tắt xóa bài hiện tại thay vì chỉ pause rồi tự phát lại."""
    player = MusicPlayer((tmp_path,), volume=0.5, youtube_enabled=False)
    player._current_title = "Test Song"  # noqa: SLF001

    result = player.stop_playback()

    assert result.success
    assert not player.has_music_context
    assert player.current_track_name is None
    assert not player.resume().success
