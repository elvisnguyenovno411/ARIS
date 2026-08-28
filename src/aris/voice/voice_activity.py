from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum


class VoiceActivityEvent(StrEnum):
    """Liệt kê thay đổi trạng thái bắt đầu hoặc kết thúc một câu nói local."""

    NONE = "none"
    START = "start"
    STOP = "stop"


@dataclass(frozen=True, slots=True)
class VoiceActivityConfig:
    """Chứa ngưỡng VAD thích ứng cho block microphone 64 ms của ARIS."""

    minimum_speech_level: float = 0.012
    activation_multiplier: float = 2.8
    release_multiplier: float = 1.7
    start_blocks: int = 2
    # 620 ms đủ giữ các khoảng nghỉ ngắn trong tiếng Việt nhưng phản hồi sớm hơn 280 ms.
    silence_seconds: float = 0.62
    maximum_utterance_seconds: float = 12.0
    cooldown_seconds: float = 0.65


class VoiceActivityDetector:
    """Tự phát hiện lúc người dùng nói và dừng sau khoảng im lặng liên tục."""

    def __init__(self, config: VoiceActivityConfig | None = None) -> None:
        """Khởi tạo VAD chỉ lưu noise floor và timestamp, không giữ raw audio."""
        self.config = config or VoiceActivityConfig()
        self.noise_floor = 0.002
        self.is_speaking = False
        self._speech_blocks = 0
        self._started_at: float | None = None
        self._silence_started_at: float | None = None
        self._cooldown_until = 0.0

    def reset(self, *, cooldown: bool = False) -> None:
        """Đưa VAD về chờ và tùy chọn chặn kích hoạt lại trong một khoảng ngắn."""
        self.is_speaking = False
        self._speech_blocks = 0
        self._started_at = None
        self._silence_started_at = None
        self._cooldown_until = (
            time.monotonic() + self.config.cooldown_seconds if cooldown else 0.0
        )

    def confirm_speech(self, timestamp: float) -> None:
        """Mở trạng thái câu ngay khi một voice gate bên ngoài đã xác nhận giọng nói."""
        self.is_speaking = True
        self._speech_blocks = 0
        self._started_at = float(timestamp)
        self._silence_started_at = None
        self._cooldown_until = 0.0

    def feed(self, level: float, timestamp: float) -> VoiceActivityEvent:
        """Nhận RMS chuẩn hóa và trả sự kiện START/STOP khi trạng thái giọng nói đổi."""
        safe_level = max(0.0, min(1.0, float(level)))
        if self.is_speaking:
            return self._feed_speaking(safe_level, timestamp)
        if timestamp < self._cooldown_until:
            self._learn_noise(safe_level)
            return VoiceActivityEvent.NONE

        threshold = max(
            self.config.minimum_speech_level,
            self.noise_floor * self.config.activation_multiplier,
        )
        if safe_level >= threshold:
            self._speech_blocks += 1
        else:
            self._speech_blocks = 0
            self._learn_noise(safe_level)
        if self._speech_blocks < self.config.start_blocks:
            return VoiceActivityEvent.NONE

        self.is_speaking = True
        self._started_at = timestamp
        self._silence_started_at = None
        self._speech_blocks = 0
        return VoiceActivityEvent.START

    def _feed_speaking(self, level: float, timestamp: float) -> VoiceActivityEvent:
        """Theo dõi im lặng hoặc giới hạn thời lượng trong lúc một câu đang mở."""
        release_level = max(
            self.config.minimum_speech_level * 0.65,
            self.noise_floor * self.config.release_multiplier,
        )
        if level <= release_level:
            if self._silence_started_at is None:
                self._silence_started_at = timestamp
        else:
            self._silence_started_at = None

        silence_complete = (
            self._silence_started_at is not None
            and timestamp - self._silence_started_at >= self.config.silence_seconds
        )
        duration_complete = (
            self._started_at is not None
            and timestamp - self._started_at >= self.config.maximum_utterance_seconds
        )
        if not silence_complete and not duration_complete:
            return VoiceActivityEvent.NONE

        self.is_speaking = False
        self._started_at = None
        self._silence_started_at = None
        self._cooldown_until = timestamp + self.config.cooldown_seconds
        return VoiceActivityEvent.STOP

    def _learn_noise(self, level: float) -> None:
        """Cập nhật noise floor chậm chỉ từ block nhỏ để giọng nói không nâng ngưỡng."""
        if level <= max(0.018, self.noise_floor * 2.5):
            self.noise_floor = self.noise_floor * 0.985 + level * 0.015


@dataclass(frozen=True, slots=True)
class ExternalAudioGateConfig:
    """Chứa ngưỡng nhận giọng gần microphone khi loa đồng thời đang phát nhạc."""

    calibration_seconds: float = 0.22
    minimum_voice_level: float = 0.035
    echo_multiplier: float = 1.35
    activation_margin: float = 0.01
    trigger_blocks: int = 2
    voice_hold_seconds: float = 0.8


class ExternalAudioVoiceGate:
    """Loại tiếng nhạc tham chiếu khỏi VAD nhưng cho giọng người gần microphone đi qua."""

    def __init__(self, config: ExternalAudioGateConfig | None = None) -> None:
        """Khởi tạo ước lượng echo bằng scalar RMS, không giữ sample nhạc hay microphone."""
        self.config = config or ExternalAudioGateConfig()
        self.reset(0.0)

    def reset(self, timestamp: float) -> None:
        """Bắt đầu lại cửa sổ học tiếng loa ngắn khi bài hát bật hoặc tắt."""
        self._started_at = float(timestamp)
        self._echo_ratio = 0.22
        self._ambient_level = 0.01
        self._trigger_blocks = 0
        self._voice_until = 0.0
        self._candidate_active = False

    @property
    def candidate_active(self) -> bool:
        """Cho biết block hiện tại giống giọng gần mic để HUD có thể hạ nhạc sớm."""
        return self._candidate_active

    def feed(
        self,
        microphone_level: float,
        playback_level: float,
        timestamp: float,
    ) -> float:
        """Trả mức giọng cho VAD hoặc 0 khi block khớp mức echo dự kiến của nhạc."""
        mic = max(0.0, min(1.0, float(microphone_level)))
        playback = max(0.0, min(1.0, float(playback_level)))
        now = float(timestamp)
        self._ambient_level += (mic - self._ambient_level) * 0.035
        expected_echo = playback * self._echo_ratio
        threshold = max(
            self.config.minimum_voice_level,
            expected_echo * self.config.echo_multiplier + self.config.activation_margin,
            self._ambient_level * 1.45 + 0.012,
        )
        calibrating = now - self._started_at < self.config.calibration_seconds
        candidate = not calibrating and mic >= threshold

        if playback >= 0.025 and (calibrating or not candidate):
            observed_ratio = max(0.03, min(0.78, mic / playback))
            self._echo_ratio += (observed_ratio - self._echo_ratio) * 0.055

        if candidate:
            self._trigger_blocks += 1
            if self._trigger_blocks >= self.config.trigger_blocks:
                self._voice_until = now + self.config.voice_hold_seconds
        else:
            self._trigger_blocks = 0

        self._candidate_active = candidate or now <= self._voice_until
        if now <= self._voice_until:
            return mic
        return 0.0
