# Developer scripts

Run these commands from the repository root with the project virtual environment. None of the
probe scripts is required for normal ARIS use.

## Setup and launch

- `setup.ps1` — create `.venv` and install runtime plus development dependencies.
- `run.ps1` — launch `python -m aris` from the correct project directory.
- `close_running_aris.py` — send a normal `WM_CLOSE` to the ARIS window during development.

## Offline/device probes

- `audio_probe.py`, `voice_activity_probe.py` — inspect microphone levels/VAD without saving audio.
- `camera_probe.py`, `vision_probe.py`, `fps_probe.py` — validate camera, MediaPipe, and render FPS;
  camera frames stay in RAM.
- `model_open_probe.py`, `model_zoom_probe.py`, `multi_model_control_probe.py` — exercise floating
  hologram lifecycle and commands.
- `hardware_probe.py` — open the configured Arduino serial port and request typed `STATUS`.
- `window_action_probe.py`, `shutdown_command_probe.py`, `music_stop_command_probe.py` — exercise
  allowlisted Windows close, ARIS shutdown, and the stop-music regression path.

## Network/API probes

- `api_probe.py` — makes one minimal OpenAI Responses request when the API opt-in is enabled.
- `web_search_probe.py` — makes one potentially billable Web Search request.
- `live_search_ui_probe.py` — validates router-to-panel behavior; add `--mock` to avoid an API call.
- `youtube_music_probe.py` — searches YouTube and briefly plays streamed audio without saving it.

## Captures and private asset import

- `capture_ui.py`, `capture_hologram.py`, `capture_research.py` — create portfolio screenshots.
- `import_sound_effects.py` — derive Git-ignored local cues from a user-owned sound file.
- `import_*` plus `archive_mesh_utils.py` — validate/optimize user-supplied meshes into
  `assets/user_models/`. Derived meshes stay Git ignored until redistribution rights are proven.

Never run a live network/audio/hardware probe during a recording without first checking its listed
side effects. Probe output must not print API keys, signed media URLs, microphone samples, or frames.
