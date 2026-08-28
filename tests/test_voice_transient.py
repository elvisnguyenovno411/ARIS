from dataclasses import replace

import numpy as np

import aris.voice.controller as controller_module
from aris.core.config import AppConfig
from aris.voice.controller import VoiceController


def test_two_speech_blocks_start_auto_recording_with_preroll() -> None:
    """Kiểm tra VAD mở câu tự động và giữ pre-roll ngắn để không mất âm đầu."""
    controller = VoiceController(replace(AppConfig.load(), auto_listen=True))
    timeline = np.arange(1024, dtype=np.float32) / 16_000
    speech = (0.06 * np.sin(2 * np.pi * 220 * timeline)).astype(np.float32)
    block = speech.reshape(-1, 1)

    controller._audio_callback(block, 1024, None, None)  # noqa: SLF001
    controller._audio_callback(block, 1024, None, None)  # noqa: SLF001

    assert controller.is_recording
    assert len(controller._frames) == 2  # noqa: SLF001
    controller.cancel_recording()


def test_auto_listen_can_be_disabled_for_manual_only_mode() -> None:
    """Kiểm tra override local tắt VAD vẫn để microphone visualizer hoạt động an toàn."""
    controller = VoiceController(replace(AppConfig.load(), auto_listen=False))
    block = np.full((1024, 1), 0.08, dtype=np.float32)

    controller._audio_callback(block, 1024, None, None)  # noqa: SLF001
    controller._audio_callback(block, 1024, None, None)  # noqa: SLF001

    assert not controller.is_recording


def test_auto_listen_detects_near_voice_while_music_is_playing(monkeypatch) -> None:
    """Kiểm tra Hey ARIS có thể mở VAD trên nền nhạc mà echo đơn thuần không kích hoạt."""
    clock = [100.0]
    monkeypatch.setattr(controller_module.time, "monotonic", lambda: clock[0])
    controller = VoiceController(
        replace(AppConfig.load(), auto_listen=True, openai_api_key=None)
    )
    timeline = np.arange(1024, dtype=np.float32) / 16_000
    music_echo = (0.02 * np.sin(2 * np.pi * 220 * timeline)).astype(np.float32)
    near_voice = (0.08 * np.sin(2 * np.pi * 220 * timeline)).astype(np.float32)
    controller.set_external_audio_active(True)
    controller.set_external_audio_level(0.35)
    candidates: list[bool] = []
    controller.music_voice_candidate.connect(lambda: candidates.append(True))

    for timestamp in (100.4, 100.6, 100.8, 101.0):
        clock[0] = timestamp
        controller._audio_callback(music_echo.reshape(-1, 1), 1024, None, None)
    assert not controller.is_recording

    clock[0] = 101.1
    controller._audio_callback(near_voice.reshape(-1, 1), 1024, None, None)
    assert candidates == [True]
    assert not controller.is_recording

    clock[0] = 101.164
    controller._audio_callback(near_voice.reshape(-1, 1), 1024, None, None)

    assert controller.is_recording
    # Pre-roll tối đa bốn block chủ động giữ cả âm đầu đã đến trong lúc gate xác nhận.
    assert len(controller._frames) == 4  # noqa: SLF001

    clock[0] = 102.1
    controller._audio_callback(music_echo.reshape(-1, 1), 1024, None, None)
    clock[0] = 102.75
    controller._audio_callback(music_echo.reshape(-1, 1), 1024, None, None)

    assert not controller.is_recording
