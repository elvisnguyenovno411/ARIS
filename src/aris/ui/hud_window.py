from __future__ import annotations

import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QGridLayout,
    QLineEdit,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from aris.ai.client import ArisAssistant, AssistantResolution
from aris.ai.language import detect_language
from aris.ai.router import IntentRouter
from aris.core.config import AppConfig
from aris.core.shutdown_guard import ShutdownDecision, ShutdownGuard
from aris.core.types import ActionResult, Intent, IntentType
from aris.desktop.actions import (
    DesktopActions,
    localize_close_app_result,
    localize_open_app_result,
)
from aris.desktop.safe_paths import SafePathPolicy
from aris.hardware import GuardState, HardwareController
from aris.media import MusicPlayer, default_music_roots
from aris.models.catalog import ModelCatalog
from aris.models.external_mesh import preload_local_meshes
from aris.search import ArisWebSearch, SearchResult
from aris.storage.json_store import JsonStore
from aris.ui.floating_models import FloatingModelManager
from aris.ui.hud_state import HudMode, HudStateMachine
from aris.ui.hud_widgets import AudioCoreWidget, TechBackground
from aris.ui.research_manager import ResearchPanelManager
from aris.ui.sound_effects import SoundEffectPlayer
from aris.ui.startup_sequence import ShutdownSequence, StartupSequence
from aris.ui.typewriter_label import TypewriterLabel
from aris.vision.hand_geometry import HandProfile
from aris.vision.spatial_gesture import SpatialGestureFrame
from aris.vision.tracker import VisionController
from aris.voice.controller import VoiceController
from aris.voice.wake_session import WakeAction, WakeSession

GUARD_ALERT_CACHE_KEY = "guard_alert_vi"
WAKE_READY_CACHE_KEY = "wake_ready_vi"
WAKE_READY_MESSAGE = "ARIS đã sẵn sàng."
GUARD_ALERT_MESSAGE = (
    "Cảnh báo. Phát hiện vật thể trong phạm vi bảo vệ. "
    "API và mọi tác vụ đã bị khóa. Hãy dùng điều khiển hồng ngoại để mở khóa."
)


class HudWindow(QMainWindow):
    """Điều phối HUD logo tối giản, hologram model, voice, vision và safe actions."""

    async_reply_ready = Signal(str, str)
    async_semantic_ready = Signal(object)
    async_search_ready = Signal(str, object)

    def __init__(self, config: AppConfig) -> None:
        """Khởi tạo controller hiện có nhưng thay dashboard bằng state machine điện ảnh."""
        super().__init__()
        self.config = config
        self.store = JsonStore(config.state_file)
        self.saved_state = self.store.load()
        self.language = self.saved_state["settings"].get("language", config.default_language)
        self.voice_output = bool(self.saved_state["settings"].get("voice_output", True))
        self.catalog = ModelCatalog()
        self.router = IntentRouter(self.catalog)
        self.actions = DesktopActions(SafePathPolicy(config.safe_roots))
        self.assistant = ArisAssistant(config)
        self.web_search = ArisWebSearch(config)
        self.voice = VoiceController(config)
        self.wake_session = WakeSession(timeout_seconds=10.0)
        self.hardware = HardwareController(
            enabled=config.hardware_enabled,
            configured_port=config.hardware_port,
            parent=self,
        )
        self.guard_state = GuardState.OFF
        self.guard_distance_cm: float | None = None
        self._hardware_state_seen = False
        self._startup_finished = False
        self._closing = False
        self._shutting_down = False
        self._wake_was_awake = False
        self._music_ducked = False
        self._music_candidate_ducked = False
        self.shutdown_guard = ShutdownGuard()
        self._pending_searches: dict[str, str] = {}
        self._gesture_target = "model"
        self.vision = VisionController(
            config.assets_dir / "models" / "hand_landmarker.task",
            gesture_mode=config.gesture_mode,
            target_fps=config.vision_fps,
            inference_size=(config.vision_width, config.vision_height),
        )
        self.vision.set_language(self.language)
        self.hud_state = HudStateMachine()
        self.hand_profile: HandProfile | None = None
        if isinstance(self.saved_state.get("hand_scan"), dict):
            self.hand_profile = HandProfile.from_dict(self.saved_state["hand_scan"])
        self._shortcuts: list[QShortcut] = []
        self._build_ui()
        self.sound_effects = SoundEffectPlayer(
            {
                "startup": config.assets_dir / "user_audio" / "startup_local.wav",
                "model_spawn": config.assets_dir
                / "user_audio"
                / "model_spawn_local.wav",
                "research_spawn": config.assets_dir
                / "user_audio"
                / "model_spawn_local.wav",
                "research_close": config.assets_dir
                / "user_audio"
                / "model_spawn_local.wav",
            },
            self,
        )
        try:
            music_volume = int(self.saved_state["settings"].get("music_volume", 72))
        except (TypeError, ValueError):
            music_volume = 72
        self.music = MusicPlayer(
            default_music_roots(config.assets_dir),
            self,
            volume=max(0, min(100, music_volume)) / 100.0,
            youtube_enabled=config.youtube_music_enabled,
        )
        self.startup_sequence = StartupSequence(4400, self)
        self.shutdown_sequence = ShutdownSequence(1800, self)
        self.wake_timer = QTimer(self)
        self.wake_timer.setInterval(250)
        self.wake_timer.timeout.connect(self._update_wake_session)
        self.music_duck_release_timer = QTimer(self)
        self.music_duck_release_timer.setSingleShot(True)
        self.music_duck_release_timer.setInterval(1400)
        self.music_duck_release_timer.timeout.connect(self._release_music_candidate_duck)
        self.vision_watchdog = QTimer(self)
        self.vision_watchdog.setInterval(1800)
        self.vision_watchdog.timeout.connect(self._ensure_vision_running)
        self.background.set_startup_progress(0.0)
        self.core.set_startup_progress(0.0)
        self._connect_signals()
        # Nạp MediaPipe sớm để model đầu tiên không phải chờ 15-20 giây mới nhận tay.
        self.vision.preload()
        self.vision_watchdog.start()
        # Mesh được đọc vào cache ở worker; OpenGL item vẫn luôn được tạo đúng UI thread.
        threading.Thread(
            target=preload_local_meshes,
            name="aris-mesh-preload",
            daemon=True,
        ).start()
        # Startup chỉ chạy khi event loop sẵn sàng để frame tối đầu tiên thật sự được vẽ.
        QTimer.singleShot(90, self._start_startup)

    def _build_ui(self) -> None:
        """Dựng HUD logo duy nhất cùng lớp hologram nổi trong suốt phía trên."""
        self.setWindowTitle("ARIS — Augmented Reality Intelligence System")
        self.setMinimumSize(960, 600)
        self.resize(1280, 720)

        self.background = TechBackground()
        self.background.setObjectName("AppRoot")
        root_layout = QVBoxLayout(self.background)
        root_layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(self.background)

        self.hud_page = QWidget()
        root_layout.addWidget(self.hud_page)
        hud_layout = QGridLayout(self.hud_page)
        hud_layout.setContentsMargins(36, 24, 36, 24)
        hud_layout.setSpacing(8)
        self.status_label = TypewriterLabel()
        self.status_label.setObjectName("TransientStatus")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        self.core = AudioCoreWidget(animation_fps=min(60, self.config.render_fps))
        self.debug_input = QLineEdit()
        self.debug_input.setObjectName("DebugCommand")
        self.debug_input.setPlaceholderText("Developer command — press Enter")
        self.debug_input.setMaximumWidth(720)
        self.debug_input.hide()
        # Text và core cùng một ô để message không đẩy logo lệch tâm hoặc đổi kích thước.
        hud_layout.addWidget(self.core, 0, 0)
        hud_layout.addWidget(
            self.status_label,
            0,
            0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
        )
        hud_layout.addWidget(self.debug_input, 1, 0, Qt.AlignmentFlag.AlignHCenter)
        hud_layout.setRowStretch(0, 1)
        self.model_manager = FloatingModelManager(
            self.hud_page,
            self.catalog,
            render_fps=self.config.render_fps,
        )
        self.model_manager.prepare_compositor()
        self.research_manager = ResearchPanelManager(self.hud_page)
        self.status_label.raise_()
        self.debug_input.raise_()

    def _connect_signals(self) -> None:
        """Kết nối logo, auto-listen, model và camera mà không tạo vòng gọi chéo."""
        self.core.clicked.connect(self._toggle_voice_command)
        self.debug_input.returnPressed.connect(self._submit_debug_command)

        self.voice.monitoring_changed.connect(self.core.set_monitoring)
        self.voice.audio_level_changed.connect(self.core.set_audio_level)
        self.voice.spectrum_changed.connect(self.core.set_spectrum)
        self.voice.speech_level_changed.connect(self.core.set_speech_level)
        self.voice.recording_changed.connect(self._on_recording_changed)
        self.voice.speaking_changed.connect(self._on_speaking_changed)
        self.voice.speech_playback_started.connect(self._on_speech_playback_started)
        self.voice.speech_playback_failed.connect(self._on_speech_playback_failed)
        self.voice.music_voice_candidate.connect(self._on_music_voice_candidate)
        self.voice.status_changed.connect(self._on_voice_status)
        self.voice.transcript_ready.connect(self._on_transcript)

        self.hardware.connection_changed.connect(self._on_hardware_connection_changed)
        self.hardware.state_changed.connect(self._on_guard_state_changed)
        self.hardware.distance_changed.connect(self._on_guard_distance_changed)
        self.hardware.remote_received.connect(self._on_hardware_remote)
        self.hardware.status_changed.connect(self._on_hardware_status)

        self.vision.status_changed.connect(self._on_vision_status)
        self.vision.scan_progress.connect(self._on_scan_progress)
        self.vision.scan_completed.connect(self._on_scan_completed)
        self.vision.gesture_delta.connect(self.model_manager.apply_gesture)
        self.vision.grab_gesture.connect(self.model_manager.apply_grab_gesture)
        self.vision.spatial_gesture.connect(self._on_spatial_gesture)
        self.vision.running_changed.connect(self._on_vision_running_changed)
        self.model_manager.selection_changed.connect(self._on_model_selected)
        self.async_reply_ready.connect(self._on_async_reply)
        self.async_semantic_ready.connect(self._on_semantic_resolution)
        self.async_search_ready.connect(self._on_async_search_result)
        self.research_manager.panel_closed.connect(self._on_research_panel_closed)
        self.research_manager.selection_changed.connect(self._on_research_panel_selected)
        self.research_manager.dismissal_started.connect(self._play_research_close_effect)
        self.startup_sequence.progress_changed.connect(self.background.set_startup_progress)
        self.startup_sequence.progress_changed.connect(self.core.set_startup_progress)
        self.startup_sequence.finished.connect(self._finish_startup)
        self.shutdown_sequence.progress_changed.connect(self.background.set_startup_progress)
        self.shutdown_sequence.progress_changed.connect(self.core.set_startup_progress)
        self.shutdown_sequence.finished.connect(self.close)
        self.sound_effects.level_changed.connect(self.core.set_effect_level)
        self.music.playing_changed.connect(self._on_music_playing_changed)
        self.music.level_changed.connect(self.core.set_music_level)
        self.music.level_changed.connect(self.background.set_music_level)
        self.music.playback_reference_changed.connect(self.voice.set_external_audio_level)
        self.music.error_occurred.connect(self._on_music_error)
        self.music.stream_started.connect(self._on_music_stream_started)

        debug_shortcut = QShortcut(QKeySequence("F2"), self)
        debug_shortcut.activated.connect(self._toggle_debug_input)
        close_shortcut = QShortcut(QKeySequence("Esc"), self)
        close_shortcut.activated.connect(self._handle_escape)
        self._shortcuts.extend((debug_shortcut, close_shortcut))

    def _start_startup(self) -> None:
        """Phát opening timeline và cue local trước khi cho auto-listen mở microphone."""
        if self.startup_sequence.is_running or self.startup_sequence.progress >= 1.0:
            return
        self.startup_sequence.start()
        self.sound_effects.play("startup")

    def _finish_startup(self) -> None:
        """Khóa HUD ở frame sáng cuối và chỉ lúc này mới mở monitor microphone."""
        self.background.set_startup_progress(1.0)
        self.core.set_startup_progress(1.0)
        self._startup_finished = True
        self.voice.start_monitoring()
        # Chuẩn bị câu wake trong RAM để Hey ARIS được xác nhận gần như tức thì.
        self.voice.prepare_cloud_speech(
            WAKE_READY_CACHE_KEY,
            WAKE_READY_MESSAGE,
            self.language,
        )
        self.hardware.start()
        self.wake_timer.start()

    def _play_model_spawn_effect(self) -> None:
        """Phát cue materialize ngắn và chặn VAD nghe lại âm thanh từ loa."""
        duration_ms = self.sound_effects.duration_ms("model_spawn")
        if duration_ms > 0:
            self.voice.suspend_auto_listen(duration_ms / 1000.0 + 0.35)
            self.sound_effects.play("model_spawn")

    def _play_research_spawn_effect(self) -> None:
        """Phát cue khi bảng dữ liệu materialize và tạm chặn VAD nghe lại loa."""
        duration_ms = self.sound_effects.duration_ms("research_spawn")
        if duration_ms > 0:
            self.voice.suspend_auto_listen(duration_ms / 1000.0 + 0.25)
            self.sound_effects.play("research_spawn")

    def _play_research_close_effect(self) -> None:
        """Phát cùng cue theo chiều ngược trong RAM để báo bảng đang de-materialize."""
        duration_ms = self.sound_effects.duration_ms("research_close")
        if duration_ms > 0:
            self.voice.suspend_auto_listen(duration_ms / 1000.0 + 0.25)
            self.sound_effects.play("research_close", reverse=True)

    def _toggle_voice_command(self) -> None:
        """Nhấn logo lần một để nghe và lần hai để dừng/gửi lệnh."""
        if self._shutting_down:
            return
        if self.guard_state is GuardState.ALERT:
            self._show_status("SECURITY LOCK · USE IR REMOTE", 2600)
            return
        if self.voice.is_recording:
            self.hud_state.begin_thinking()
            self.core.set_mode(HudMode.THINKING)
            self.voice.stop_recording()
            return
        self.voice.start_recording()

    def _on_recording_changed(self, recording: bool) -> None:
        """Đồng bộ animation logo/panel với trạng thái ghi từ voice controller."""
        self._sync_music_ducking()
        if self.guard_state is GuardState.ALERT:
            self.core.set_mode(HudMode.ALERT)
            return
        if recording:
            if self.wake_session.touch(time.monotonic()):
                self._wake_was_awake = True
            self.hud_state.begin_listening()
            self.core.set_mode(HudMode.LISTENING)
        else:
            self.core.set_mode(HudMode.THINKING)

    def _on_speaking_changed(self, speaking: bool) -> None:
        """Đồng bộ animation SPEAKING với vòng đời phát giọng mà không ảnh hưởng model."""
        self._sync_music_ducking()
        if self.guard_state is GuardState.ALERT:
            self.core.set_mode(HudMode.ALERT)
            return
        if speaking:
            self.hud_state.begin_speaking()
            self.core.set_mode(HudMode.SPEAKING)
        elif self.hud_state.mode is HudMode.SPEAKING:
            self._return_to_resting_mode()

    def _on_speech_playback_started(self, message: str, duration_ms: int) -> None:
        """Giữ HUD không chữ khi phát giọng; nội dung dài chỉ hiện trong bảng tra cứu."""
        del message, duration_ms
        self._hide_status()

    def _on_speech_playback_failed(self, message: str) -> None:
        """Không làm lộ transcript lên HUD nếu TTS lỗi trong chế độ voice-only."""
        del message
        self._hide_status()

    def _submit_debug_command(self) -> None:
        """Gửi lệnh text ẩn để kiểm thử offline mà không làm HUD thường bị rối."""
        command = self.debug_input.text().strip()
        if not command:
            return
        self.debug_input.clear()
        self.debug_input.hide()
        self._dispatch_intent(
            self.router.route(command, music_context=self.music.has_music_context)
        )

    def _toggle_debug_input(self) -> None:
        """Hiện/ẩn command field F2 dành riêng cho phát triển khi API chưa bật."""
        visible = not self.debug_input.isVisible()
        self.debug_input.setVisible(visible)
        if visible:
            self.debug_input.setFocus()

    def _handle_escape(self) -> None:
        """Đóng debug field hoặc hologram như fallback phục hồi trong lúc phát triển."""
        if self.debug_input.isVisible():
            self.debug_input.hide()
        elif self.research_manager.has_panels:
            self._close_research()
        elif self.hud_state.active_model is not None:
            self._close_model()

    def _dispatch_intent(self, intent: Intent) -> None:
        """Thực thi intent qua module allowlist và không bao giờ chạy shell từ AI."""
        if intent.kind in {
            IntentType.ARM_GUARD,
            IntentType.DISARM_GUARD,
            IntentType.GUARD_STATUS,
        }:
            self._handle_guard_intent(intent.kind)
            return
        if self.guard_state is GuardState.ALERT:
            self._show_status("SECURITY LOCK · API AND ACTIONS DISABLED", 3000)
            return
        if intent.kind is IntentType.EXIT_ARIS:
            decision = self.shutdown_guard.evaluate(
                confirmed=bool(intent.arguments.get("confirmed", False)),
                music_context=self.music.has_music_context,
                timestamp=time.monotonic(),
            )
            if decision is ShutdownDecision.ALLOW:
                self._begin_shutdown()
            else:
                self._respond(
                    "Để tránh tắt nhầm khi đang phát nhạc, hãy nói xác nhận tắt ARIS."
                )
            return
        if intent.kind is IntentType.SELECT_MODEL:
            self._open_model(str(intent.arguments["model_key"]))
            return
        if intent.kind is IntentType.FOCUS_MODEL:
            self._focus_model(str(intent.arguments["model_key"]))
            return
        if intent.kind is IntentType.MODEL_ZOOM:
            self._zoom_model(
                operation=str(intent.arguments["operation"]),
                percent=int(intent.arguments["percent"]),
                model_key=str(intent.arguments["model_key"])
                if "model_key" in intent.arguments
                else None,
            )
            return
        if intent.kind is IntentType.CLOSE_MODEL:
            self._handle_close_intent(intent)
            return
        if intent.kind is IntentType.OPEN_APP:
            self._report_action("open_app", self.actions.open_app(str(intent.arguments["app"])))
            return
        if intent.kind is IntentType.CLOSE_APP:
            self._report_action("close_app", self.actions.close_app(str(intent.arguments["app"])))
            return
        if intent.kind is IntentType.GOOGLE_SEARCH:
            self._start_web_search(str(intent.arguments["query"]))
            return
        if intent.kind is IntentType.CLOSE_RESEARCH:
            self._close_research(close_all=bool(intent.arguments.get("all", False)))
            return
        if intent.kind in {
            IntentType.PLAY_MUSIC,
            IntentType.PAUSE_MUSIC,
            IntentType.RESUME_MUSIC,
            IntentType.STOP_MUSIC,
            IntentType.MUSIC_VOLUME,
        }:
            self._handle_music_intent(intent)
            return
        if intent.kind is IntentType.VOLUME:
            self._report_action("volume", self.actions.change_volume(**intent.arguments))
            return
        if intent.kind is IntentType.OPEN_FILE:
            self._open_safe_file(str(intent.arguments["query"]))
            return
        if intent.kind is IntentType.SCAN_HAND:
            self._request_scan()
            return
        if intent.kind is IntentType.CLEAR_HISTORY:
            self.store.clear_history()
            self.hand_profile = None
            self._show_status("LOCAL HISTORY CLEARED")
            self._return_to_resting_mode()
            return
        if intent.kind is IntentType.HELP:
            self._respond(
                "Speak naturally and ARIS listens automatically. "
                "Click the core for manual control, close a named model, or say end to close all."
            )
            return

        self.hud_state.begin_thinking()
        self.core.set_mode(HudMode.THINKING)
        threading.Thread(
            target=self._request_assistant_reply,
            args=(str(intent.arguments.get("message", "")),),
            name="aris-chat",
            daemon=True,
        ).start()

    def _open_model(self, key: str) -> None:
        """Thêm/chọn hologram tách nền trên HUD và bật camera gesture khi cần."""
        is_new = key not in self.model_manager.model_keys
        self.model_manager.open_model(key, self.hand_profile)
        self.hud_state.show_model(key)
        self.store.update(selected_model=key)
        self.core.set_mode(HudMode.MODEL)
        self.status_label.raise_()
        self.debug_input.raise_()
        # Webcam chỉ mở khi có ít nhất một hologram và tự đóng khi model cuối biến mất.
        self.vision.set_gesture_enabled(True)
        if is_new:
            QTimer.singleShot(30, self._play_model_spawn_effect)

    def _zoom_model(
        self,
        operation: str,
        percent: int,
        model_key: str | None = None,
    ) -> None:
        """Phóng/thu hologram bằng lệnh giọng local và phản hồi model đã được đổi."""
        changed_key = self.model_manager.adjust_model_zoom(operation, percent, model_key)
        if changed_key is None:
            message = (
                "Hãy mở hoặc chọn model trước khi phóng to hoặc thu nhỏ."
                if self.language == "vi"
                else "Open or select a model before changing its size."
            )
            self._respond(message)
            self._return_to_resting_mode()
            return
        display_name = (
            "Scanned Hand"
            if changed_key == "hand_scan"
            else self.catalog.get(changed_key).display_name
        )
        direction_vi = "phóng to" if operation == "in" else "thu nhỏ"
        direction_en = "enlarged" if operation == "in" else "reduced"
        message = (
            f"Đã {direction_vi} {display_name} {percent}%."
            if self.language == "vi"
            else f"{display_name} {direction_en} by {percent}%."
        )
        self._respond(message)
        self._return_to_resting_mode()

    def _focus_model(self, model_key: str) -> None:
        """Chuyển quyền điều khiển tới model đang mở mà không tạo hologram mới."""
        spec = self.catalog.get(model_key)
        if not self.model_manager.select_model(model_key):
            message = (
                f"{spec.display_name} chưa được mở."
                if self.language == "vi"
                else f"{spec.display_name} is not open."
            )
            self._respond(message)
            self._return_to_resting_mode()
            return
        self.vision.set_gesture_enabled(True)
        message = (
            f"Đã chọn {spec.display_name}."
            if self.language == "vi"
            else f"Selected {spec.display_name}."
        )
        self._respond(message)
        self._return_to_resting_mode()

    def _close_model(
        self,
        model_key: str | None = None,
        close_all: bool = False,
    ) -> None:
        """Đóng model được gọi tên, model đang chọn hoặc toàn bộ phiên hologram."""
        if not self.model_manager.has_models:
            self._return_to_resting_mode()
            return
        if close_all:
            self.model_manager.close_all()
            self.hud_state.close_all_models()
        else:
            target = model_key or self.hud_state.active_model
            if not self.model_manager.close_model(target):
                self._show_status("MODEL IS NOT OPEN")
                self._return_to_resting_mode()
                return
            self.hud_state.close_model(target)

        if self.model_manager.has_models:
            active_key = self.model_manager.active_key
            if active_key is not None:
                self.hud_state.select_model(active_key)
            self.core.set_mode(HudMode.MODEL)
            return
        self.vision.set_gesture_enabled(self.research_manager.has_panels)
        self.hud_state.close_all_models()
        self._return_to_resting_mode()

    def _handle_close_intent(self, intent: Intent) -> None:
        """Đóng panel đang focus với lệnh trống, nếu không thì đóng model được yêu cầu."""
        unnamed_close = "model_key" not in intent.arguments and not bool(
            intent.arguments.get("all", False)
        )
        if unnamed_close and self.research_manager.has_panels and (
            self._gesture_target == "research" or not self.model_manager.has_models
        ):
            self._close_research()
            return
        self._close_model(
            model_key=str(intent.arguments["model_key"])
            if "model_key" in intent.arguments
            else None,
            close_all=bool(intent.arguments.get("all", False)),
        )

    def _on_model_selected(self, model_key: str) -> None:
        """Đồng bộ model người dùng vừa nhấn với state và đích nhận gesture."""
        if not model_key:
            return
        self._gesture_target = "model"
        self.hud_state.select_model(model_key)
        self.store.update(selected_model=model_key)
        self.core.set_mode(HudMode.MODEL)
        self.vision.set_gesture_enabled(True)

    def _request_scan(self) -> None:
        """Quét lòng bàn tay ngay trên HUD mà không mở panel hoặc camera preview."""
        self._show_status("HAND SCAN · PLACE ONE OPEN PALM")
        self.vision.request_scan()

    def _on_scan_progress(self, progress: int) -> None:
        """Hiện phần trăm scan dạng text ngắn mà không làm dịch chuyển logo ARIS."""
        rounded = max(0, min(100, int(progress)))
        if rounded == 100 or rounded % 20 == 0:
            self._show_status(f"HAND SCAN · {rounded}%")

    def _on_scan_completed(self, profile: HandProfile) -> None:
        """Lưu tỷ lệ tay và thêm model tay như một hologram nổi mới."""
        self.hand_profile = profile
        self.store.update(hand_scan=profile.to_dict())
        self.model_manager.open_model("hand_scan", profile)
        self.hud_state.show_model("hand_scan")
        self.core.set_mode(HudMode.MODEL)
        self.vision.set_gesture_enabled(True)
        QTimer.singleShot(30, self._play_model_spawn_effect)

    def _on_vision_status(self, message: str, state: str) -> None:
        """Chỉ đưa lỗi hoặc hướng dẫn scan quan trọng lên HUD logo tối giản."""
        if state == "error":
            self.hud_state.fail()
            self.core.set_mode(HudMode.ERROR)
            self._show_status(message, 4200)

    def _on_vision_running_changed(self, running: bool) -> None:
        """Báo ngắn trạng thái webcam nền khi một hologram đang cần điều khiển tay."""
        if self._closing or not (self.model_manager.has_models or self.research_manager.has_panels):
            return
        if running:
            self._show_status("GESTURE CAMERA · READY", 1500)
        else:
            self._show_status("GESTURE CAMERA · RECONNECTING", 1800)

    def _ensure_vision_running(self) -> None:
        """Khởi động lại vision nếu worker từng lỗi trong lúc model hoặc bảng còn mở."""
        needs_camera = self.model_manager.has_models or self.research_manager.has_panels
        if needs_camera and not self.vision.is_running:
            self.vision.set_gesture_enabled(True)

    def _on_voice_status(self, message: str, state: str) -> None:
        """Cập nhật phản hồi voice nhưng giữ màn hình nghỉ chỉ có logo và vòng mic."""
        if self.guard_state is GuardState.ALERT:
            self.core.set_mode(HudMode.ALERT)
            return
        if state == "monitoring":
            return
        if state == "error":
            self.hud_state.fail()
            self.core.set_mode(HudMode.ERROR)
            self._show_status(message, 4200)
            return
        if state in {"waiting", "idle"}:
            self._show_status(message)
            self._return_to_resting_mode()

    def _on_transcript(self, transcript: str) -> None:
        """Định tuyến transcript qua cùng luật local an toàn như debug command."""
        if self.guard_state is GuardState.ALERT:
            return
        decision = self.wake_session.process(transcript, time.monotonic())
        self._wake_was_awake = self.wake_session.is_awake(time.monotonic())
        if decision.action is WakeAction.IGNORE:
            direct_intent = self.router.route(
                transcript,
                music_context=self.music.has_music_context,
            )
            if direct_intent.kind is IntentType.EXIT_ARIS and bool(
                direct_intent.arguments.get("confirmed", False)
            ):
                self._dispatch_intent(direct_intent)
                return
            self._return_to_resting_mode()
            return
        if decision.action is WakeAction.WAKE:
            self._respond(WAKE_READY_MESSAGE, cache_key=WAKE_READY_CACHE_KEY)
            self._return_to_resting_mode()
            return
        self.hud_state.begin_thinking()
        self.core.set_mode(HudMode.THINKING)
        self._dispatch_intent(
            self.router.route(
                decision.command,
                music_context=self.music.has_music_context,
            )
        )

    def _handle_music_intent(self, intent: Intent) -> None:
        """Thực thi phát, tạm dừng, tiếp tục hoặc chỉnh gain nhạc rồi đọc xác nhận."""
        if intent.kind is IntentType.PLAY_MUSIC:
            self.shutdown_guard.reset()
            result = self.music.play(str(intent.arguments.get("query", "")))
        elif intent.kind is IntentType.PAUSE_MUSIC:
            result = self.music.pause()
        elif intent.kind is IntentType.STOP_MUSIC:
            result = self.music.stop_playback()
        elif intent.kind is IntentType.MUSIC_VOLUME:
            result = self.music.change_volume(
                str(intent.arguments.get("operation", "set")),
                int(intent.arguments.get("percent", 10)),
            )
            self.store.update_settings(music_volume=self.music.volume_percent)
        else:
            result = self.music.resume()
        self.store.append_action("music", result.success, result.message)
        youtube_pending = bool(
            result.data.get("source") == "youtube" and result.data.get("pending")
        )
        if not youtube_pending:
            self._respond(result.message)
        self._return_to_resting_mode()

    def _on_music_playing_changed(self, playing: bool) -> None:
        """Đồng bộ nền tím, vòng beat và khóa VAD để loa không tiêu token phiên âm."""
        self.core.set_music_active(playing)
        self.background.set_music_active(playing)
        self.voice.set_external_audio_active(playing)
        if not playing:
            self.music_duck_release_timer.stop()
            self._music_candidate_ducked = False
            self.music.set_ducked(False)
            self.core.set_music_level(0.0)
            self.background.set_music_level(0.0)

    def _on_music_voice_candidate(self) -> None:
        """Pre-duck nhạc ngay khi mic thấy giọng gần để âm tiết wake tiếp theo rõ hơn."""
        if not self.music.is_playing:
            return
        self._music_candidate_ducked = True
        self._sync_music_ducking()
        self.music_duck_release_timer.start()

    def _release_music_candidate_duck(self) -> None:
        """Bỏ pre-duck nếu giọng không thành câu; recording/speech vẫn giữ nhạc thấp."""
        self._music_candidate_ducked = False
        self._sync_music_ducking()

    def _sync_music_ducking(self) -> None:
        """Hạ nhạc khi nghe/nói và học lại echo ngắn khi loa trở về âm lượng thường."""
        ducked = (
            self._music_candidate_ducked
            or self.voice.is_recording
            or self.voice.is_speaking
        )
        was_ducked = self._music_ducked
        self._music_ducked = ducked
        self.music.set_ducked(ducked)
        if was_ducked and not ducked and self.music.is_playing:
            self.voice.set_external_audio_active(True)

    def _on_music_error(self, message: str) -> None:
        """Báo lỗi codec/file bằng giọng ARIS nhưng không phát âm báo Windows."""
        if self.music.is_playing:
            return
        self.store.append_action("music", False, message)
        self._respond(f"Không thể phát bài nhạc này. {message}")
        self._return_to_resting_mode()

    def _on_music_stream_started(self, _title: str) -> None:
        """Ghi nhận YouTube đã phát nhưng không đọc tiêu đề/caption gây gián đoạn nhạc."""
        self.store.append_action("youtube_music", True, "Started a YouTube music stream.")
        self._return_to_resting_mode()

    def _open_safe_file(self, query: str) -> None:
        """Chỉ mở file khi truy vấn có đúng một kết quả nằm trong safe roots."""
        result = self.actions.find_files(query)
        if result.success and len(result.data.get("matches", [])) == 1:
            result = self.actions.open_file(Path(result.data["matches"][0]))
        elif result.success:
            result = ActionResult(False, "Multiple safe matches found; refine the file name.")
        self._report_action("open_file", result)

    def _start_web_search(self, query: str) -> None:
        """Tạo bảng loading riêng và gọi Web Search trên worker để HUD không bị đứng."""
        clean_query = " ".join(query.strip().split())[:500]
        panel_id = self.research_manager.open_loading(clean_query)
        self._pending_searches[panel_id] = clean_query
        self.vision.set_gesture_enabled(True)
        self.hud_state.begin_thinking()
        self.core.set_mode(HudMode.THINKING)
        self._play_research_spawn_effect()
        threading.Thread(
            target=self._request_web_search,
            args=(panel_id, clean_query),
            name=f"aris-web-search-{panel_id}",
            daemon=True,
        ).start()

    def _request_web_search(self, panel_id: str, query: str) -> None:
        """Thực hiện yêu cầu mạng trong worker và chỉ chuyển dataclass thuần về UI thread."""
        if self.guard_state is GuardState.ALERT:
            return
        self.async_search_ready.emit(panel_id, self.web_search.search(query))

    def _on_async_search_result(self, panel_id: str, result: SearchResult) -> None:
        """Đưa response về đúng bảng, kể cả khi nhiều lượt tra cứu chạy đồng thời."""
        if self.guard_state is GuardState.ALERT:
            return
        expected_query = self._pending_searches.pop(panel_id, None)
        if expected_query != result.query:
            return
        if not self.research_manager.show_result(
            panel_id,
            result,
            self.web_search.requests_remaining,
        ):
            return
        stored_message = "Web research completed." if result.success else "Web research failed."
        self.store.append_action("web_search", result.success, stored_message)
        self._respond(self._spoken_search_summary(result))
        if not result.success:
            self.core.set_mode(HudMode.ERROR)
        self._return_to_resting_mode()

    def _close_research(self, close_all: bool = False) -> None:
        """Đóng bảng đang chọn hoặc mọi bảng mà không ảnh hưởng các model đang mở."""
        if close_all:
            self.research_manager.close_all()
        else:
            self.research_manager.close_panel()
        self._return_to_resting_mode()

    def _on_research_panel_closed(self, panel_id: str) -> None:
        """Bỏ worker mapping khi bảng đóng để response mạng đến muộn không hiện trở lại."""
        self._pending_searches.pop(panel_id, None)
        if not self.research_manager.has_panels:
            self._gesture_target = "model"
            self.vision.set_gesture_enabled(self.model_manager.has_models)

    def _on_research_panel_selected(self, panel_id: str) -> None:
        """Chuyển tay mở sang bảng vừa chọn; pinch không được dùng để đổi bảng."""
        if panel_id:
            self._gesture_target = "research"

    def _on_spatial_gesture(self, frame: SpatialGestureFrame) -> None:
        """Chỉ chuyển một frame cử chỉ tới bảng hoặc model đang sở hữu focus tương tác."""
        if self._gesture_target == "research" and self.research_manager.has_panels:
            self.research_manager.apply_spatial_gesture(frame)
            return
        self.model_manager.apply_spatial_gesture(frame)

    @staticmethod
    def _spoken_search_summary(result: SearchResult) -> str:
        """Rút phản hồi nói còn khoảng hai câu; nội dung đầy đủ và nguồn vẫn nằm trên panel."""
        if not result.success:
            return result.answer
        sentences = result.answer.replace("!", ".").replace("?", ".").split(".")
        selected = [sentence.strip() for sentence in sentences if sentence.strip()][:2]
        summary = ". ".join(selected)
        if summary:
            summary += "."
        return summary[:360] or "Đã hoàn tất tra cứu và hiển thị nguồn trên bảng thông tin."

    def _report_action(self, action: str, result: ActionResult) -> None:
        """Lưu kết quả rút gọn, phát phản hồi và quay về trạng thái phù hợp."""
        if action == "open_app":
            result = localize_open_app_result(result, self.language)
        elif action == "close_app":
            result = localize_close_app_result(result, self.language)
        self.store.append_action(action, result.success, result.message)
        self._respond(result.message)
        self._return_to_resting_mode()

    def _request_assistant_reply(self, message: str) -> None:
        """Nhờ AI hiểu câu lạ hoặc trả lời chat trong worker mà không khóa animation HUD."""
        if self.guard_state is GuardState.ALERT:
            return
        resolution = self.assistant.resolve(
            message,
            self._detect_language(message),
            self.catalog,
        )
        self.async_semantic_ready.emit(resolution)

    def _on_semantic_resolution(self, resolution: AssistantResolution) -> None:
        """Thực thi Intent AI đã được allowlist hoặc đọc câu chat từ cùng một response."""
        if self.guard_state is GuardState.ALERT:
            return
        if resolution.intent is not None:
            self._dispatch_intent(resolution.intent)
            return
        if resolution.reply is not None:
            self._on_async_reply(resolution.reply.text, resolution.reply.source)

    def _on_async_reply(self, message: str, source: str) -> None:
        """Đọc phản hồi cloud/mock và phục hồi model hoặc logo đang dùng trước đó."""
        if self.guard_state is GuardState.ALERT:
            return
        self._respond(message)
        if source == "error":
            self.core.set_mode(HudMode.ERROR)
        self._return_to_resting_mode()

    def _respond(self, message: str, *, cache_key: str | None = None) -> None:
        """Hiện phản hồi ngắn và phát giọng mà không để loa kích hoạt auto-listen."""
        if self.voice_output:
            self._hide_status()
            self.voice.suspend_auto_listen(2.5)
            self.voice.speak(message, self.language, cache_key=cache_key)
            return
        self._show_status(message, 3600)

    def _respond_local(self, message: str) -> None:
        """Đọc thông báo bảo vệ bằng TTS local để ALERT không phát sinh API cloud."""
        if self.voice_output:
            self._hide_status()
            self.voice.suspend_auto_listen(2.5)
            self.voice.speak(message, self.language, allow_cloud=False)
            return
        self._show_status(message, 4200)

    def _respond_guard_alert(self, message: str = GUARD_ALERT_MESSAGE) -> None:
        """Phát cảnh báo từ WAV cache RAM; chỉ fallback local nếu cache chưa sẵn sàng."""
        if self.voice_output:
            self._hide_status()
            self.voice.speak(
                message,
                self.language,
                allow_cloud=False,
                cache_key=GUARD_ALERT_CACHE_KEY,
            )
            return
        self._show_status(message, 5200)

    def _return_to_resting_mode(self) -> None:
        """Giữ các hologram đang mở và đưa animation lõi về trạng thái phù hợp."""
        if self.guard_state is GuardState.ALERT:
            self.hud_state.mode = HudMode.ALERT
            self.core.set_mode(HudMode.ALERT)
            return
        if self.model_manager.has_models:
            self.hud_state.mode = HudMode.MODEL
            self.core.set_mode(HudMode.MODEL)
            return
        if self.voice.is_speaking:
            self.hud_state.begin_speaking()
            self.core.set_mode(HudMode.SPEAKING)
            return
        self.hud_state.reset()
        self.core.set_mode(HudMode.IDLE)

    def _show_status(self, message: str, duration_ms: int = 2600) -> None:
        """Giữ HUD logo-only; trạng thái tạm không còn được vẽ thành chữ trên màn hình."""
        _ = message, duration_ms
        self.status_label.hide_message()

    def _hide_status(self) -> None:
        """Ẩn phản hồi đã hết hạn và trả lại bố cục logo-only."""
        self.status_label.hide_message()

    def _handle_guard_intent(self, intent_type: IntentType) -> None:
        """Gửi lệnh sonar local; ALERT chỉ cho remote vật lý mở khóa trong beta."""
        if intent_type is IntentType.GUARD_STATUS:
            distance = (
                f", khoảng cách gần nhất {self.guard_distance_cm:.1f} centimet"
                if self.guard_distance_cm is not None and self.guard_distance_cm >= 0.0
                else ""
            )
            self._respond(f"Trạng thái sonar: {self.guard_state.value}{distance}.")
            return
        if self.guard_state is GuardState.ALERT:
            self._show_status("SECURITY LOCK · PHYSICAL REMOTE REQUIRED", 3200)
            return
        command = "ARM" if intent_type is IntentType.ARM_GUARD else "DISARM"
        if not self.hardware.send_command(command):
            self._respond("Không tìm thấy kết nối Arduino. Sonar chưa thay đổi.")

    def _on_hardware_connection_changed(self, connected: bool, port: str) -> None:
        """Hiện trạng thái COM và giữ khóa đỏ nếu phần cứng mất kết nối khi đang bảo vệ."""
        if self._closing:
            return
        if connected:
            self._show_status(f"ARDUINO GUARD CONNECTED · {port}", 1800)
            return
        if self.guard_state in {GuardState.ARMED, GuardState.ALERT}:
            if self.music.is_playing:
                self.music.pause()
            self.guard_state = GuardState.ALERT
            self.assistant.set_runtime_enabled(False)
            self.web_search.set_runtime_enabled(False)
            self._pending_searches.clear()
            self.research_manager.dispose()
            self.background.set_security_alert(True)
            self.core.set_mode(HudMode.ALERT)
            self.voice.stop_monitoring()
            self._respond_guard_alert("Cảnh báo. Kết nối Arduino đã bị gián đoạn.")

    def _on_guard_state_changed(self, value: str) -> None:
        """Đồng bộ state Arduino với HUD, TTS, camera và khóa runtime của API."""
        state = GuardState(value)
        previous = self.guard_state if self._hardware_state_seen else None
        self._hardware_state_seen = True
        self.guard_state = state
        alert = state is GuardState.ALERT
        self.assistant.set_runtime_enabled(not alert)
        self.web_search.set_runtime_enabled(not alert)
        self.background.set_security_alert(alert)

        if state is GuardState.ALERT:
            if self.music.is_playing:
                self.music.pause()
            self._pending_searches.clear()
            self.research_manager.dispose()
            self.voice.stop_monitoring()
            self.vision.set_gesture_enabled(False)
            self.hud_state.mode = HudMode.ALERT
            self.core.set_mode(HudMode.ALERT)
            self._respond_guard_alert()
            return

        if self._startup_finished and not self.voice.is_monitoring:
            self.voice.start_monitoring()
        if self.model_manager.has_models or self.research_manager.has_panels:
            self.vision.set_gesture_enabled(True)

        if state is GuardState.ARMING:
            self.voice.prepare_cloud_speech(
                GUARD_ALERT_CACHE_KEY,
                GUARD_ALERT_MESSAGE,
                self.language,
            )
            self._respond("Trạng thái sonar sẽ được kích hoạt sau 10 giây.")
        elif state is GuardState.ARMED:
            self._respond("Sonar đã được kích hoạt.")
        elif state is GuardState.OFF and previous is GuardState.ALERT:
            self.wake_session.sleep()
            self._wake_was_awake = False
            self._respond(
                "Đã xác nhận điều khiển vật lý. Cảnh báo và khóa API đã được tắt."
            )
        elif state is GuardState.OFF and previous in {GuardState.ARMING, GuardState.ARMED}:
            self._respond("Sonar đã được tắt.")
        self._return_to_resting_mode()

    def _update_wake_session(self) -> None:
        """Đưa ARIS về standby im lặng sau 10 giây không có transcript người dùng."""
        awake = self.wake_session.is_awake(time.monotonic())
        if self._wake_was_awake and not awake and self.guard_state is not GuardState.ALERT:
            self._show_status("STANDBY · SAY HEY ARIS", 1800)
        self._wake_was_awake = awake

    def _begin_shutdown(self) -> None:
        """Đọc xác nhận, tắt input và làm HUD tối dần trước khi đóng cửa sổ."""
        if self._shutting_down or self.guard_state is GuardState.ALERT:
            return
        self._shutting_down = True
        self._pending_searches.clear()
        self.research_manager.close_all()
        self.wake_timer.stop()
        self.vision_watchdog.stop()
        self.music.stop()
        self.voice.stop_monitoring()
        self.vision.set_gesture_enabled(False)
        self._respond("Đang tắt ARIS.")
        QTimer.singleShot(180, self.shutdown_sequence.start)

    def _on_guard_distance_changed(self, distance_cm: float) -> None:
        """Giữ số đo sonar mới nhất trong RAM để trả lời lệnh trạng thái local."""
        self.guard_distance_cm = float(distance_cm)

    def _on_hardware_remote(self, command: str) -> None:
        """Hiện nút remote vừa nhận; thông báo giọng được phát theo state kế tiếp."""
        self._show_status(f"IR REMOTE · {command}", 1100)

    def _on_hardware_status(self, message: str, state: str) -> None:
        """Chỉ hiển thị lỗi kết nối phần cứng, không phát giọng lặp khi reconnect."""
        if state == "warning" and self.guard_state is not GuardState.ALERT:
            self._show_status(message, 2600)

    def _detect_language(self, message: str) -> str:
        """Ước lượng Việt/Anh có dấu hoặc không dấu và dùng ngôn ngữ HUD khi hòa điểm."""
        return detect_language(message, self.language)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API name
        """Giải phóng webcam và microphone monitor trước khi ứng dụng đóng."""
        self._closing = True
        self.startup_sequence.stop()
        self.shutdown_sequence.stop()
        self.wake_timer.stop()
        self.vision_watchdog.stop()
        self.sound_effects.stop()
        self.music.stop()
        self.research_manager.dispose()
        self.model_manager.dispose()
        self.vision.stop()
        self.hardware.stop()
        self.voice.close()
        event.accept()
