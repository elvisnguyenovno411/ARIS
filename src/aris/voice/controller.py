from __future__ import annotations

import io
import threading
import time
import wave
from collections import deque

import numpy as np
from PySide6.QtCore import QObject, Signal

from aris.core.config import AppConfig
from aris.voice.audio_analysis import AudioBlockAnalyzer
from aris.voice.audio_playback import decode_wav_bytes, play_wav_bytes, stop_playback
from aris.voice.barge_in import BargeInDetector
from aris.voice.devices import choose_input_device
from aris.voice.transcript_normalization import normalize_voice_command
from aris.voice.voice_activity import (
    ExternalAudioVoiceGate,
    VoiceActivityDetector,
    VoiceActivityEvent,
)

_TRANSCRIPTION_KEYWORDS = (
    "ARIS",
    "Hey ARIS",
    "Rasengan",
    "Iron Man Mask",
    "Iron Man Hand",
    "Spider-Man Mask",
    "Web Shooter",
    "Minato Kunai",
    "Chrome",
    "VS Code",
    "Discord",
    "Codex",
    "Microsoft Edge",
    "File Explorer",
    "Notepad",
    "Calculator",
    "Microsoft Paint",
    "Windows Terminal",
    "Windows Settings",
    "Spotify",
    "Snipping Tool",
    "Sonar",
    "Trạng thái sonar",
    "Phát nhạc",
    "Tạm dừng nhạc",
    "Tiếp tục nhạc",
    "Close",
    "End",
    "Đóng",
    "Tắt",
)


class VoiceController(QObject):
    """Giám sát âm thanh local, tự nhận biết câu nói và phiên âm khi câu kết thúc."""

    recording_changed = Signal(bool)
    monitoring_changed = Signal(bool)
    audio_level_changed = Signal(float)
    spectrum_changed = Signal(object)
    status_changed = Signal(str, str)
    transcript_ready = Signal(str)
    speaking_changed = Signal(bool)
    speech_playback_started = Signal(str, int)
    speech_playback_failed = Signal(str)
    speech_level_changed = Signal(float)
    music_voice_candidate = Signal()

    def __init__(self, config: AppConfig, sample_rate: int = 16_000) -> None:
        """Khởi tạo monitor local; thiết bị chỉ mở khi HUD gọi `start_monitoring`."""
        super().__init__()
        self.config = config
        self.sample_rate = sample_rate
        self._stream = None
        self._recording = False
        self._recording_origin: str | None = None
        self._frames: list[np.ndarray] = []
        # Bốn block tương đương khoảng 256 ms, chỉ sống trong RAM và luôn bị ghi đè.
        self._pre_roll: deque[np.ndarray] = deque(maxlen=4)
        self._lock = threading.Lock()
        self._audio_analyzer = AudioBlockAnalyzer(sample_rate)
        self._vad = VoiceActivityDetector()
        self._barge_in = BargeInDetector()
        self._barge_in_active = False
        self._auto_listen_suspended_until = 0.0
        self._external_audio_active = False
        self._external_audio_level = 0.0
        self._external_audio_gate = ExternalAudioVoiceGate()
        self._music_voice_candidate_active = False
        self._speech_output_count = 0
        self._speech_generation = 0
        self._last_speech_text = ""
        self._last_speech_requested_at = 0.0
        self._local_speech_engine: object | None = None
        self._speech_cache: dict[str, bytes] = {}
        self._speech_cache_pending: set[str] = set()
        # Giữ kết nối HTTP sống giữa các lượt để tránh bắt tay TLS lại cho từng câu.
        self._api_client_lock = threading.Lock()
        self._transcription_client: object | None = None
        self._speech_client: object | None = None

    @property
    def is_recording(self) -> bool:
        """Cho biết ARIS có đang giữ sample RAM cho một lệnh giọng nói hay không."""
        with self._lock:
            return self._recording

    @property
    def is_monitoring(self) -> bool:
        """Cho biết monitor âm lượng và auto-listen local có đang mở hay không."""
        return self._stream is not None

    @property
    def is_speaking(self) -> bool:
        """Cho biết một hoặc nhiều phản hồi đang được phát qua loa local hay cloud."""
        with self._lock:
            return self._speech_output_count > 0

    def start_monitoring(self) -> None:
        """Mở stream local nhẹ cho visualizer và VAD tự động, không lưu file âm thanh."""
        if self.is_monitoring:
            return
        try:
            import sounddevice as sd

            devices = sd.query_devices()
            default_input = int(sd.default.device[0]) if sd.default.device[0] is not None else None
            device_index = choose_input_device(
                devices,
                default_input,
                self.config.audio_input_device,
            )
            if device_index is None:
                raise RuntimeError("No input microphone is available.")
            self._stream = sd.InputStream(
                device=device_index,
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=1024,
                callback=self._audio_callback,
            )
            self._stream.start()
            self.monitoring_changed.emit(True)
            device_name = str(devices[device_index].get("name", f"device {device_index}"))
            self.status_changed.emit(f"Auto-listen active: {device_name}", "monitoring")
        except Exception as error:
            stream = self._stream
            self._stream = None
            if stream is not None:
                stream.close()
            self.monitoring_changed.emit(False)
            self.status_changed.emit(f"Microphone unavailable: {error}", "error")

    def stop_monitoring(self) -> None:
        """Đóng stream local và hủy mọi audio lệnh còn trong RAM."""
        stream = self._stream
        self._stream = None
        with self._lock:
            was_recording = self._recording
            self._recording = False
            self._recording_origin = None
            self._frames = []
            self._pre_roll.clear()
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()
        self._vad.reset()
        if was_recording:
            self.recording_changed.emit(False)
        self.monitoring_changed.emit(False)

    def toggle_recording(self) -> None:
        """Bật hoặc dừng ghi âm tùy theo trạng thái hiện tại."""
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self) -> None:
        """Bắt đầu phiên nghe thủ công khi người dùng nhấn logo dự phòng."""
        if self.is_recording:
            return
        if not self.is_monitoring:
            self.start_monitoring()
        if not self.is_monitoring:
            return
        with self._lock:
            self._frames = []
            self._pre_roll.clear()
            self._recording = True
            self._recording_origin = "manual"
        self._vad.reset()
        self.recording_changed.emit(True)
        self.status_changed.emit("Listening… click the ARIS core again to send.", "recording")

    def stop_recording(self) -> None:
        """Dừng câu hiện tại, gửi phiên âm nếu bật API rồi tiếp tục auto-listen."""
        if not self.is_recording:
            return
        with self._lock:
            self._recording = False
            origin = self._recording_origin
            self._recording_origin = None
            frames = self._frames
            self._frames = []
            self._pre_roll.clear()
        if origin == "manual":
            self._vad.reset(cooldown=True)
        self.recording_changed.emit(False)
        if not frames:
            self.status_changed.emit("No audio was recorded.", "waiting")
            return
        if not self.config.api_enabled:
            # VAD/visualizer vẫn hoạt động offline, còn speech-to-text chờ opt-in API rõ ràng.
            self.status_changed.emit(
                "Cloud transcription is disabled. Use the hidden F2 command field for testing.",
                "waiting",
            )
            return
        audio = np.concatenate(frames, axis=0)
        threading.Thread(
            target=self._transcribe,
            args=(audio,),
            name="aris-transcription",
            daemon=True,
        ).start()

    def cancel_recording(self) -> None:
        """Hủy lệnh đang ghi và xóa sample RAM mà không gọi API."""
        with self._lock:
            was_recording = self._recording
            self._recording = False
            self._recording_origin = None
            self._frames = []
            self._pre_roll.clear()
        self._vad.reset(cooldown=True)
        if was_recording:
            self.recording_changed.emit(False)
        self.status_changed.emit("Voice command canceled.", "idle")

    def suspend_auto_listen(self, seconds: float = 2.0) -> None:
        """Tạm khóa VAD khi ARIS phát giọng để loa không tự tạo một lệnh mới."""
        self._auto_listen_suspended_until = max(
            self._auto_listen_suspended_until,
            time.monotonic() + max(0.0, float(seconds)),
        )
        with self._lock:
            self._pre_roll.clear()
        self._vad.reset(cooldown=True)

    def set_external_audio_active(self, enabled: bool) -> None:
        """Bật bộ lọc echo nhạc để Hey ARIS vẫn hoạt động mà không nghe nhầm lời bài hát."""
        with self._lock:
            self._external_audio_active = bool(enabled)
            self._music_voice_candidate_active = False
            if not enabled:
                self._external_audio_level = 0.0
            self._pre_roll.clear()
        self._external_audio_gate.reset(time.monotonic())
        self._vad.reset(cooldown=True)

    def set_external_audio_level(self, level: float) -> None:
        """Nhận duy nhất mức RMS nhạc làm tham chiếu echo, không nhận hoặc giữ PCM nguồn."""
        with self._lock:
            self._external_audio_level = max(0.0, min(1.0, float(level)))

    def interrupt_speech(self) -> None:
        """Dừng audio cloud ngay khi barge-in local xác nhận người dùng đang nói."""
        with self._lock:
            if not self._barge_in_active:
                return
            self._barge_in_active = False
            self._pre_roll.clear()
        self._barge_in.reset()
        threading.Thread(
            target=stop_playback,
            name="aris-stop-speech",
            daemon=True,
        ).start()
        self.status_changed.emit("Speech interrupted.", "idle")

    def close(self) -> None:
        """Đóng monitor ngay khi thoát và không gửi bản ghi dở lên cloud."""
        with self._lock:
            local_engine = self._local_speech_engine
            self._speech_generation += 1
            self._speech_output_count = 0
            self._local_speech_engine = None
            self._speech_cache.clear()
            self._speech_cache_pending.clear()
        with self._api_client_lock:
            api_clients = (self._transcription_client, self._speech_client)
            self._transcription_client = None
            self._speech_client = None
        stop_playback()
        if local_engine is not None:
            try:
                local_engine.stop()
            except Exception:
                pass
        for client in api_clients:
            close_client = getattr(client, "close", None)
            if callable(close_client):
                try:
                    close_client()
                except Exception:
                    pass
        self.stop_monitoring()

    def _get_api_client(self, purpose: str):
        """Tạo lười và tái sử dụng client STT/TTS để giảm độ trễ kết nối cloud."""
        attribute = "_transcription_client" if purpose == "transcription" else "_speech_client"
        with self._api_client_lock:
            client = getattr(self, attribute)
            if client is None:
                from openai import OpenAI

                client = OpenAI(
                    api_key=self.config.openai_api_key,
                    timeout=35.0,
                    max_retries=1,
                )
                setattr(self, attribute, client)
            return client

    def speak(
        self,
        text: str,
        language: str = "en",
        *,
        allow_cloud: bool = True,
        cache_key: str | None = None,
    ) -> None:
        """Đọc một câu; cache RAM cho phép cảnh báo dùng cùng giọng mà không gọi API mới."""
        cleaned = text.strip()[:900]
        if not cleaned:
            return
        requested_at = time.monotonic()
        with self._lock:
            duplicate_active = (
                self._speech_output_count > 0
                and cleaned == self._last_speech_text
                and requested_at - self._last_speech_requested_at < 1.5
            )
            if duplicate_active:
                return
            had_active_speech = self._speech_output_count > 0
            local_engine = self._local_speech_engine
            self._speech_generation += 1
            generation = self._speech_generation
            self._speech_output_count = 1
            self._local_speech_engine = None
            self._barge_in_active = False
            self._last_speech_text = cleaned
            self._last_speech_requested_at = requested_at
            self._pre_roll.clear()
        if had_active_speech:
            # Cloud sounddevice và SAPI cũ đều phải im trước khi worker mới được phép nói.
            stop_playback()
            if local_engine is not None:
                try:
                    local_engine.stop()
                except Exception:
                    pass
        else:
            self.speaking_changed.emit(True)
        self._vad.reset(cooldown=True)
        with self._lock:
            cached_audio = self._speech_cache.get(cache_key) if cache_key else None
        if cached_audio is not None:
            target = self._speak_cached
            arguments = (cleaned, language, generation, cached_audio)
        else:
            target = (
                self._speak_cloud
                if allow_cloud and self.config.cloud_tts_enabled
                else self._speak_local
            )
            arguments = (cleaned, language, generation)
        threading.Thread(
            target=target,
            args=arguments,
            name="aris-speech",
            daemon=True,
        ).start()

    def prepare_cloud_speech(self, cache_key: str, text: str, language: str = "en") -> bool:
        """Chuẩn bị WAV cloud trong RAM trước ALERT; không phát và không ghi xuống đĩa."""
        key = cache_key.strip()[:80]
        cleaned = text.strip()[:900]
        if not key or not cleaned or not self.config.cloud_tts_enabled:
            return False
        with self._lock:
            if key in self._speech_cache or key in self._speech_cache_pending:
                return True
            self._speech_cache_pending.add(key)
        threading.Thread(
            target=self._prepare_cloud_speech,
            args=(key, cleaned, language),
            name="aris-speech-cache",
            daemon=True,
        ).start()
        return True

    def _is_speech_current(self, generation: int | None) -> bool:
        """Cho biết worker TTS còn là câu mới nhất được phép phát hay đã lỗi thời."""
        if generation is None:
            return True
        with self._lock:
            return generation == self._speech_generation

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        """Suy ra level/spectrum/VAD và chỉ giữ raw block trong pre-roll hoặc câu hiện tại."""
        del frames, time_info
        if status:
            return
        mono = np.asarray(indata[:, 0], dtype=np.float32)
        analysis = self._audio_analyzer.analyze(mono)
        normalized_level = max(0.0, min(1.0, analysis.rms * 5.5))
        self.audio_level_changed.emit(normalized_level)
        self.spectrum_changed.emit(list(analysis.bands))

        now = time.monotonic()
        with self._lock:
            playback_active = self._speech_output_count > 0
            external_audio_active = self._external_audio_active
            external_audio_level = self._external_audio_level
            barge_in_active = self._barge_in_active
            recording = self._recording
            recording_origin = self._recording_origin

        if barge_in_active:
            if self._barge_in.feed(normalized_level, now):
                self.interrupt_speech()
            return

        auto_suspended = playback_active or now < self._auto_listen_suspended_until
        if auto_suspended:
            with self._lock:
                self._pre_roll.clear()
            self._vad.reset(cooldown=True)
            return

        if recording:
            with self._lock:
                self._frames.append(indata.copy())
            if recording_origin == "auto":
                vad_level = normalized_level
                if external_audio_active:
                    # Tiếp tục loại echo trong cả câu. Nếu dùng RMS thô ở đây, nhạc nền
                    # có thể giữ VAD mở đến giới hạn 12 giây và khiến người dùng nói lại.
                    vad_level = self._external_audio_gate.feed(
                        normalized_level,
                        external_audio_level,
                        now,
                    )
                event = self._vad.feed(vad_level, now)
                if event is VoiceActivityEvent.STOP:
                    self.stop_recording()
            return

        if not self.config.auto_listen:
            return

        with self._lock:
            self._pre_roll.append(indata.copy())
        vad_level = normalized_level
        if external_audio_active:
            vad_level = self._external_audio_gate.feed(
                normalized_level,
                external_audio_level,
                now,
            )
            candidate_active = self._external_audio_gate.candidate_active
            if candidate_active and not self._music_voice_candidate_active:
                self.music_voice_candidate.emit()
            self._music_voice_candidate_active = candidate_active
            if vad_level > 0.0:
                # Voice gate đã tự kiểm tra hai block liên tiếp. Mở bản ghi ngay tại đây
                # để VAD không đòi thêm hai block rồi làm mất một câu lệnh ngắn.
                self._vad.confirm_speech(now)
                self._start_auto_recording()
                return
        event = self._vad.feed(vad_level, now)
        if event is VoiceActivityEvent.START:
            self._start_auto_recording()

    def _start_auto_recording(self) -> None:
        """Chuyển pre-roll ngắn thành đầu câu và phát trạng thái nghe tự động."""
        with self._lock:
            if self._recording:
                return
            self._frames = list(self._pre_roll)
            self._pre_roll.clear()
            self._recording = True
            self._recording_origin = "auto"
        self.recording_changed.emit(True)
        self.status_changed.emit("Listening automatically…", "recording")

    def _finish_speech_output(self, generation: int | None = None) -> None:
        """Giảm bộ đếm loa và chỉ mở lại VAD sau một cooldown chống echo."""
        with self._lock:
            if generation is not None and generation != self._speech_generation:
                return
            if generation is None:
                self._speech_output_count = max(0, self._speech_output_count - 1)
            else:
                self._speech_output_count = 0
            playback_finished = self._speech_output_count == 0
        if playback_finished:
            self._auto_listen_suspended_until = time.monotonic() + 0.65
            self._vad.reset(cooldown=True)
            self.speech_level_changed.emit(0.0)
            self.speaking_changed.emit(False)

    def _transcribe(self, audio: np.ndarray) -> None:
        """Mã hóa WAV trong RAM, gọi transcription API và không ghi câu nói xuống đĩa."""
        try:
            pcm = np.clip(audio, -1.0, 1.0)
            pcm = (pcm * 32767).astype(np.int16)
            audio_buffer = io.BytesIO()
            with wave.open(audio_buffer, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(pcm.tobytes())
            audio_buffer.seek(0)
            client = self._get_api_client("transcription")
            request: dict[str, object] = {
                "model": self.config.transcription_model,
                "file": ("aris-command.wav", audio_buffer, "audio/wav"),
            }
            if self.config.transcription_language is not None:
                request["language"] = self.config.transcription_language
            if self.config.transcription_model == "gpt-transcribe":
                request["keywords"] = _TRANSCRIPTION_KEYWORDS
            result = client.audio.transcriptions.create(
                **request,
            )
            transcript = normalize_voice_command(result.text or "")
            if transcript:
                self.transcript_ready.emit(transcript)
                self.status_changed.emit("Voice command transcribed.", "ready")
            else:
                self.status_changed.emit("No speech was recognized.", "waiting")
        except Exception as error:
            self.status_changed.emit(f"Transcription failed: {type(error).__name__}.", "error")

    def _speak_cloud(
        self,
        text: str,
        language: str,
        generation: int | None = None,
    ) -> None:
        """Tạo WAV cloud và phát thẳng từ RAM, không tạo file hay âm báo Windows."""
        try:
            audio = self._request_cloud_speech_bytes(text, language)
            if not self._is_speech_current(generation):
                return
            self._play_cloud_audio(text, audio)
        except Exception as error:
            if self._is_speech_current(generation):
                self.status_changed.emit(
                    f"Speech output failed: {type(error).__name__}.",
                    "error",
                )
                self.speech_playback_failed.emit(text)
        finally:
            self._finish_speech_output(generation)

    def _speak_cached(
        self,
        text: str,
        language: str,
        generation: int | None,
        audio: bytes,
    ) -> None:
        """Phát WAV đã cache trong RAM bằng cùng pipeline envelope của cloud TTS."""
        del language
        try:
            if not self._is_speech_current(generation):
                return
            self._play_cloud_audio(text, audio)
        except Exception as error:
            if self._is_speech_current(generation):
                self.status_changed.emit(
                    f"Cached speech failed: {type(error).__name__}.",
                    "error",
                )
                self.speech_playback_failed.emit(text)
        finally:
            self._finish_speech_output(generation)

    def _prepare_cloud_speech(self, key: str, text: str, language: str) -> None:
        """Tải một cảnh báo TTS vào RAM ở worker và bỏ qua lỗi để giữ fallback local."""
        try:
            audio = self._request_cloud_speech_bytes(text, language)
            with self._lock:
                self._speech_cache[key] = audio
        except Exception:
            pass
        finally:
            with self._lock:
                self._speech_cache_pending.discard(key)

    def _request_cloud_speech_bytes(self, text: str, language: str) -> bytes:
        """Gọi TTS cloud một lần và trả WAV bytes để phát ngay hoặc giữ tạm trong RAM."""
        client = self._get_api_client("speech")
        instructions = self.config.tts_instructions
        if language == "vi":
            instructions += " Pronounce Vietnamese naturally and clearly."
        instructions += (
            " Speak at a moderately brisk pace and avoid long pauses so the voice stays "
            "aligned with the on-screen text."
        )
        request: dict[str, object] = {
            "model": self.config.tts_model,
            "voice": self.config.tts_voice,
            "input": text,
            "response_format": "wav",
        }
        if self.config.tts_model == "gpt-4o-mini-tts":
            request["instructions"] = instructions
        response = client.audio.speech.create(**request)
        return bytes(response.content)

    def _play_cloud_audio(self, text: str, audio: bytes) -> None:
        """Phát WAV RAM, phát duration/envelope và phục hồi barge-in sau khi xong."""
        samples, sample_rate = decode_wav_bytes(audio)
        duration_ms = max(400, round(len(samples) / sample_rate * 1000))
        self.speech_playback_started.emit(text, duration_ms)
        with self._lock:
            self._barge_in_active = True
        self._barge_in.reset(time.monotonic())
        try:
            play_wav_bytes(audio, self.speech_level_changed.emit)
        finally:
            with self._lock:
                self._barge_in_active = False
            self._barge_in.reset()

    def _speak_local(
        self,
        text: str,
        language: str,
        generation: int | None = None,
    ) -> None:
        """Dùng giọng SAPI nam local làm fallback khi API chưa được cấu hình."""
        del language
        engine = None
        try:
            import pyttsx3

            engine = pyttsx3.init()
            voices = engine.getProperty("voices")
            preferred = next(
                (
                    voice
                    for voice in voices
                    if any(token in voice.name.casefold() for token in ("david", "mark", "male"))
                ),
                voices[0] if voices else None,
            )
            if preferred is not None:
                engine.setProperty("voice", preferred.id)
            engine.setProperty("rate", 165)
            engine.setProperty("volume", 0.92)
            if not self._is_speech_current(generation):
                return
            with self._lock:
                if generation is not None and generation != self._speech_generation:
                    return
                self._local_speech_engine = engine
            word_count = max(1, len(text.split()))
            duration_ms = max(700, min(16_000, round(word_count / 2.75 * 1000 + 350)))
            self.speech_playback_started.emit(text, duration_ms)
            engine.say(text)
            engine.runAndWait()
        except Exception as error:
            if self._is_speech_current(generation):
                self.status_changed.emit(
                    f"Local voice unavailable: {type(error).__name__}.",
                    "error",
                )
                self.speech_playback_failed.emit(text)
        finally:
            with self._lock:
                if self._local_speech_engine is engine:
                    self._local_speech_engine = None
            self._finish_speech_output(generation)
