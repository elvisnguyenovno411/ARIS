"""Local media playback modules for ARIS."""

from aris.media.music_player import LocalMusicLibrary, MusicPlayer, default_music_roots
from aris.media.youtube_stream import YouTubeAudioResolver, YouTubeMusicError, YouTubeStream

__all__ = [
    "LocalMusicLibrary",
    "MusicPlayer",
    "YouTubeAudioResolver",
    "YouTubeMusicError",
    "YouTubeStream",
    "default_music_roots",
]
