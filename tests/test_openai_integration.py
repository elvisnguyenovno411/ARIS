from __future__ import annotations

import io
import json
import sys
import threading
from dataclasses import replace
from types import SimpleNamespace

import numpy as np

import aris.voice.controller as voice_controller_module
from aris.ai.client import ArisAssistant
from aris.core.config import AppConfig
from aris.core.types import IntentType
from aris.models.catalog import ModelCatalog
from aris.voice.controller import VoiceController


def test_responses_request_disables_storage() -> None:
    """Đảm bảo hội thoại cloud yêu cầu không lưu Response phía API."""
    captured: dict[str, object] = {}

    class _FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(output_text="ARIS ready")

    config = replace(AppConfig.load(), openai_api_key="test-key")
    assistant = ArisAssistant(config)
    assistant._client = SimpleNamespace(responses=_FakeResponses())

    reply = assistant.reply("Hello")

    assert reply.source == "openai"
    assert captured["store"] is False
    assert captured["reasoning"] == {"effort": "none"}
    assert captured["max_output_tokens"] == 120


def test_runtime_guard_disables_cloud_without_removing_key() -> None:
    """Đảm bảo ALERT khóa API tức thời nhưng không xóa cấu hình key của người dùng."""
    config = replace(AppConfig.load(), openai_api_key="test-key")
    assistant = ArisAssistant(config)

    assistant.set_runtime_enabled(False)

    assert assistant.api_enabled is False
    assert assistant.config.openai_api_key == "test-key"


def test_transcription_upload_uses_memory_buffer(monkeypatch) -> None:
    """Đảm bảo WAV phiên âm là buffer RAM hợp lệ thay vì file ghi xuống ổ đĩa."""
    captured: dict[str, object] = {}

    class _FakeTranscriptions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(text="mở Chrome")

    fake_client = SimpleNamespace(
        audio=SimpleNamespace(transcriptions=_FakeTranscriptions()),
    )
    fake_module = SimpleNamespace(OpenAI=lambda **_kwargs: fake_client)
    monkeypatch.setitem(sys.modules, "openai", fake_module)
    config = replace(AppConfig.load(), openai_api_key="test-key")
    controller = VoiceController(config)
    transcripts: list[str] = []
    controller.transcript_ready.connect(transcripts.append)

    controller._transcribe(np.zeros((1600, 1), dtype=np.float32))

    upload = captured["file"]
    assert isinstance(upload, tuple)
    assert upload[0] == "aris-command.wav"
    assert isinstance(upload[1], io.BytesIO)
    assert upload[1].getvalue().startswith(b"RIFF")
    assert upload[2] == "audio/wav"
    assert "language" not in captured
    assert "Rasengan" in captured["keywords"]
    assert transcripts == ["mở Chrome"]


def test_transcription_repairs_exact_rasengan_acoustic_confusion(monkeypatch) -> None:
    """Đảm bảo lỗi nghe trọn câu `racing game` được sửa trước khi chuyển sang router."""

    class _FakeTranscriptions:
        def create(self, **_kwargs):
            return SimpleNamespace(text="Racing game.")

    fake_client = SimpleNamespace(
        audio=SimpleNamespace(transcriptions=_FakeTranscriptions()),
    )
    fake_module = SimpleNamespace(OpenAI=lambda **_kwargs: fake_client)
    monkeypatch.setitem(sys.modules, "openai", fake_module)
    controller = VoiceController(replace(AppConfig.load(), openai_api_key="test-key"))
    transcripts: list[str] = []
    controller.transcript_ready.connect(transcripts.append)

    controller._transcribe(np.zeros((1600, 1), dtype=np.float32))

    assert transcripts == ["Hiển thị Rasengan"]


def test_transcription_reuses_cloud_client(monkeypatch) -> None:
    """Đảm bảo nhiều câu liên tiếp không tạo lại kết nối OpenAI transcription."""
    created = 0

    class _FakeTranscriptions:
        def create(self, **_kwargs):
            return SimpleNamespace(text="mở Chrome")

    fake_client = SimpleNamespace(
        audio=SimpleNamespace(transcriptions=_FakeTranscriptions()),
    )

    def create_client(**_kwargs):
        nonlocal created
        created += 1
        return fake_client

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=create_client))
    controller = VoiceController(replace(AppConfig.load(), openai_api_key="test-key"))
    audio = np.zeros((1600, 1), dtype=np.float32)

    controller._transcribe(audio)
    controller._transcribe(audio)

    assert created == 1


def test_cloud_tts_uses_cinematic_voice_and_vietnamese_direction(monkeypatch) -> None:
    """Đảm bảo TTS cloud dùng Marin và chuyển byte RAM sang bộ phát sounddevice."""
    captured: dict[str, object] = {}
    playback: dict[str, object] = {}

    class _FakeSpeechResponse:
        content = b"RIFF-test"

    class _FakeSpeech:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _FakeSpeechResponse()

    fake_client = SimpleNamespace(audio=SimpleNamespace(speech=_FakeSpeech()))
    fake_module = SimpleNamespace(OpenAI=lambda **_kwargs: fake_client)
    monkeypatch.setitem(sys.modules, "openai", fake_module)
    monkeypatch.setattr(
        voice_controller_module,
        "decode_wav_bytes",
        lambda _audio: (np.zeros(24_000, dtype=np.float32), 24_000),
    )
    monkeypatch.setattr(
        voice_controller_module,
        "play_wav_bytes",
        lambda audio, level_callback: playback.update(
            audio=audio,
            callback=level_callback,
        ),
    )
    config = replace(
        AppConfig.load(),
        openai_api_key="test-key",
        cloud_tts_enabled=True,
    )
    controller = VoiceController(config)
    controller._speech_output_count = 1
    timings: list[tuple[str, int]] = []
    controller.speech_playback_started.connect(
        lambda text, duration: timings.append((text, duration))
    )

    controller._speak_cloud("Xin chào", "vi")

    assert captured["model"] == "gpt-4o-mini-tts"
    assert captured["voice"] == "marin"
    assert "Vietnamese" in str(captured["instructions"])
    assert "moderately brisk" in str(captured["instructions"])
    assert captured["response_format"] == "wav"
    assert playback["audio"] == b"RIFF-test"
    assert callable(playback["callback"])
    assert timings == [("Xin chào", 1000)]


def test_cloud_tts_failure_does_not_fall_back_to_windows_voice(monkeypatch) -> None:
    """Đảm bảo lỗi cloud chỉ phát signal thất bại và không tự dùng giọng SAPI."""

    class _FailingSpeech:
        def create(self, **_kwargs):
            raise RuntimeError("simulated cloud failure")

    fake_client = SimpleNamespace(audio=SimpleNamespace(speech=_FailingSpeech()))
    fake_module = SimpleNamespace(OpenAI=lambda **_kwargs: fake_client)
    monkeypatch.setitem(sys.modules, "openai", fake_module)
    config = replace(
        AppConfig.load(),
        openai_api_key="test-key",
        cloud_tts_enabled=True,
    )
    controller = VoiceController(config)
    controller._speech_output_count = 1
    monkeypatch.setattr(
        controller,
        "_speak_local",
        lambda *_args: (_ for _ in ()).throw(AssertionError("SAPI fallback was called")),
    )

    controller._speak_cloud("Xin chào", "vi")

    assert controller.is_speaking is False


def test_cached_guard_voice_plays_without_a_new_cloud_request(monkeypatch) -> None:
    """Đảm bảo ALERT dùng WAV RAM cùng giọng và không gọi cloud sau khi API bị khóa."""
    controller = VoiceController(AppConfig.load())
    controller._speech_cache["guard"] = b"RIFF-cached"
    played = threading.Event()
    captured: dict[str, object] = {}

    def fake_cached(text, language, generation, audio) -> None:
        captured.update(text=text, language=language, audio=audio)
        controller._finish_speech_output(generation)
        played.set()

    monkeypatch.setattr(controller, "_speak_cached", fake_cached)
    monkeypatch.setattr(
        controller,
        "_speak_cloud",
        lambda *_args: (_ for _ in ()).throw(AssertionError("cloud was called")),
    )
    monkeypatch.setattr(
        controller,
        "_speak_local",
        lambda *_args: (_ for _ in ()).throw(AssertionError("local fallback was called")),
    )

    controller.speak("Cảnh báo", "vi", allow_cloud=False, cache_key="guard")

    assert played.wait(1.0)
    assert captured == {
        "text": "Cảnh báo",
        "language": "vi",
        "audio": b"RIFF-cached",
    }


def test_semantic_resolution_maps_free_phrase_to_safe_action() -> None:
    """Đảm bảo AI có thể hiểu câu lạ nhưng chỉ trả Intent mang khóa app allowlist."""
    captured: dict[str, object] = {}

    class _FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                output=[
                    SimpleNamespace(
                        type="function_call",
                        name="execute_aris_action",
                        arguments=json.dumps(
                            {
                                "action": "open_app",
                                "target": "vscode",
                                "operation": None,
                                "amount": None,
                                "unit": None,
                            }
                        ),
                    )
                ],
                output_text="",
            )

    assistant = ArisAssistant(replace(AppConfig.load(), openai_api_key="test-key"))
    assistant._client = SimpleNamespace(responses=_FakeResponses())

    resolution = assistant.resolve(
        "Bring up the app I use for writing Python",
        "en",
        ModelCatalog(),
    )

    assert resolution.reply is None
    assert resolution.intent is not None
    assert resolution.intent.kind is IntentType.OPEN_APP
    assert resolution.intent.arguments == {"app": "vscode"}
    assert captured["parallel_tool_calls"] is False
    assert captured["store"] is False
    assert captured["tools"][0]["strict"] is True


def test_semantic_resolution_rejects_non_allowlisted_app_target() -> None:
    """Đảm bảo function call không thể biến target lạ thành shell hoặc executable path."""

    class _FakeResponses:
        def create(self, **_kwargs):
            return SimpleNamespace(
                output=[
                    SimpleNamespace(
                        type="function_call",
                        name="execute_aris_action",
                        arguments=json.dumps(
                            {
                                "action": "open_app",
                                "target": "powershell -EncodedCommand unsafe",
                                "operation": None,
                                "amount": None,
                                "unit": None,
                            }
                        ),
                    )
                ],
                output_text="",
            )

    assistant = ArisAssistant(replace(AppConfig.load(), openai_api_key="test-key"))
    assistant._client = SimpleNamespace(responses=_FakeResponses())

    resolution = assistant.resolve("Run this command", "en", ModelCatalog())

    assert resolution.intent is None
    assert resolution.reply is not None
    assert resolution.reply.source == "safety"


def test_semantic_resolution_keeps_normal_question_as_chat() -> None:
    """Đảm bảo câu hỏi thông thường vẫn có câu trả lời thay vì bị biến thành action."""

    class _FakeResponses:
        def create(self, **_kwargs):
            return SimpleNamespace(output=[], output_text="Rasengan is a fictional technique.")

    assistant = ArisAssistant(replace(AppConfig.load(), openai_api_key="test-key"))
    assistant._client = SimpleNamespace(responses=_FakeResponses())

    resolution = assistant.resolve("What is Rasengan?", "en", ModelCatalog())

    assert resolution.intent is None
    assert resolution.reply is not None
    assert resolution.reply.source == "openai"
