# ARIS Beta Product Specification

Last updated: 2026-08-28

## Purpose

ARIS is a one-week Python portfolio beta for a future Mechatronics applicant. It demonstrates how AI, computer vision, desktop automation, and 3D visualization can become a foundation for later physical prototyping and 3D printing.

ARIS expands to **Augmented Reality Intelligence System**.

## Target environment

- Windows 11
- ASUS ROG Strix G614JU
- Intel Core i7-13650HX
- 32 GB RAM
- NVIDIA RTX 4050 Laptop GPU with 6 GB VRAM
- Laptop webcam first; iPad camera support is a future option
- Python 3.12 in a project-local `.venv`

## Experience

The desktop app uses a minimalist cinematic HUD instead of a permanent dashboard:

- Window: open maximized on Windows and keep a DPI-aware restore geometry fully inside the
  available work area so the title bar and resize edges never begin off-screen.

- Idle: a centered cyan/purple ARIS energy orb with the `A` at its core over a dark
  technology background; the effect is code-native rather than a copied video asset. Every orbit
  advances continuously and wraps only after its own full turn, so no shared phase reset is visible.
  Keep circuit traces and sparse light particles, but do not draw a square/perspective floor grid.
- Startup: begin almost black, illuminate the central `A`, extend thin circuit traces from the
  core, and release one radial cyan/purple light wave before settling into idle. A local optional
  cue follows the same timeline; microphone monitoring starts only after the sequence completes.
- Monitoring: a subtle purple dashed ring shows that local auto-listen/VAD is active and rotates
  with a continuous dash offset so it never snaps back at a shared phase boundary.
- Listening: a radial audio spectrum reacts to the user's live microphone level.
- Thinking: the core pulses while the command is routed or transcribed.
- Speaking: the `A` scale/glow follows the decoded playback envelope. Ordinary assistant replies
  remain voice-only over the central core; full text appears only inside an explicit research panel.
- Model active: each requested low-poly model appears as a transparent floating hologram over
  the existing HUD, initially centered over the ARIS core. Several models can remain visible and
  be dragged independently. The first viewport is compositor-prepared during startup so opening
  the first model does not hide/recreate the ARIS window. A short local materialization cue and
  camera easing accompany newly spawned models without blocking the UI thread.
- Idle model motion: each hologram auto-rotates continuously. A confirmed MOVE or TRANSFORM
  gesture pauses it immediately, and the latest active/release frame restarts a five-second idle
  countdown. Auto-rotation then resumes from the current angle without snapping or resetting.
- Selection: clicking a hologram chooses the only model that receives hand gesture input; the
  selected viewport receives the highest render priority. Voice commands such as `chọn Rasengan`
  focus an already-open hologram without creating another model.
- Close: `close <model name>` removes one hologram; `end` or `kết thúc` removes all holograms
  while the centered core remains on screen throughout.
- Precision zoom: a local voice command changes the selected or named hologram by a bounded
  percentage and animates to the result; this does not require an AI API call.

Local VAD starts recording after confirmed speech and stops/submits after sustained silence.
Clicking the logo once to start and again to stop remains a manual fallback. Auto-listen is
visible through a small illuminated ring. The raw camera feed is never shown.

A hidden developer command field may be used for offline testing, but it must not appear in
the normal portfolio HUD. The approved full logo remains suitable for README/video branding;
the in-app core uses only the simplified `A` for clearer animation at small sizes.

## Hand workflow

1. User starts a scan.
2. Camera observes one open palm facing forward with fingers slightly separated.
3. Local vision checks centering, scale, visibility, finger separation, and stability.
4. ARIS provides short guidance and automatically captures once the pose is stable.
5. Only normalized landmark-derived proportions are persisted.
6. A static low-poly left- or right-hand model is generated.
7. The default gesture controller has two mutually exclusive modes. A confirmed five-finger
   open hand moves the selected hologram across the HUD. A confirmed thumb-index pinch locks
   transform mode: horizontal palm movement rotates around one level viewing orbit, while vertical
   movement never tilts the model. Hand landmarks never control zoom; resizing is available only
   through bounded local voice commands. A short release is required before switching
   modes. The `grab_throw` and `legacy`
   controllers remain tested fallbacks. With multiple holograms, gestures affect only the most
   recently opened or clicked model.
8. The camera is requested at 640×480 and resized to 480×360 for gesture inference by default,
   with scale-aware smoothing, tolerant open-hand geometry, and a short lost-tracking grace window
   to extend usable camera range without storing raw frames.

Beta measurements are relative only. Real mm/cm calibration with a known marker or depth camera is a future feature.

## Model library

The public build uses procedural geometry. During local development, all six catalog models may
load validated, reduced NPZ files generated from user-supplied STL/3MF geometry. These local assets
are Git ignored and procedural versions remain the fallbacks until redistribution rights are
confirmed. Archive importers must select known members, reject unsafe/oversized entries, and never
extract arbitrary paths into the workspace.

Display names requested for the fan-made demo:

1. Iron Man Mask
2. Iron Man Hand
3. Spider-Man Mask
4. Web Shooter
5. Rasengan
6. Minato Kunai

The geometry should be original low-poly work created for this repository. README must state that the project is unofficial, educational, non-commercial, and not affiliated with rights holders. Smooth rendering takes priority over geometric detail.

Placement behavior:

- Masks render as independent models with one level left/right viewing orbit.
- Iron Man Hand and Web Shooter align with the generated hand model.
- Rasengan floats above the palm.
- Minato Kunai aligns to a plausible grip direction.
- Iron Man Mask open/close animation is a stretch goal.

## Assistant behavior

Input:

- Say `Hey ARIS` to open a ten-second command session; silence returns it to standby
- Allow wake phrase plus command in one sentence and extend the session on confirmed user voice
- Click the central logo to start/stop voice capture as a manual fallback
- Hidden text command field for development/offline fallback only
- The beta wake phrase is post-transcription and is not speaker verification; fully local keyword
  spotting remains future work

Languages:

- Understand and respond in English or Vietnamese
- Match the user's current language

Allowed local actions:

- Open Chrome
- Open VS Code
- Open Discord
- Open Codex
- Open Microsoft Edge, File Explorer, Notepad, Calculator, Paint, Windows Terminal, Windows
  Settings, Spotify, and Snipping Tool through fixed local launch specifications
- Close supported visible app windows through the fixed executable allowlist and normal
  `WM_CLOSE`; never force-kill a process or bypass an unsaved-work prompt
- Never pass voice text, AI output, or arbitrary arguments into Windows Terminal
- Adjust Windows volume
- Search the public web through OpenAI Responses and show cited sources in independently draggable,
  animated multi-panel HUD data views
- Open files only inside Desktop, Documents, Downloads, or the ARIS project

Safety:

- No arbitrary terminal execution
- No delete, rename, install, send, or write operations from assistant commands
- No recursive full-disk file search
- Local rule routing is preferred when it can handle a request without API cost
- Optional Arduino guard uses HC-SR04 on D9/D10 and a verified IR receiver on D2
- `trạng thái sonar` arms a ten-second delay; three near readings latch ALERT
- ALERT fades the HUD red, announces locally, stops voice/gesture input, and closes the runtime
  API/action gate without deleting the configured key
- A verified IR remote clears ALERT; this is not real access control because sonar cannot identify
  an owner and NEC infrared codes can be replayed
- Cloud TTS may prepare the alert WAV in RAM during ARMING; ALERT performs no new cloud request and
  falls back to local TTS if the cache is unavailable
- Explicit named phrases such as `Hey ARIS, tắt ARIS`, `đóng ARIS`, or `power down ARIS` reverse
  the startup reveal to black before closing. This local emergency exit remains available after
  wake timeout, but unnamed commands still require an active wake session.

## OpenAI integration

The optional integration layer is implemented and has been validated locally with a private
project key; the public repository contains no key and remains functional in offline/mock mode.

Beta stack:

- Responses API with `gpt-5.6-terra` as configurable default
- `gpt-transcribe` for speech-to-text
- Preferred `vi`/`en` language and ARIS model-name keywords guide speech recognition
- Local Windows SAPI when cloud speech is disabled; optional `gpt-4o-mini-tts`/Marin otherwise
- Cloud WAV is decoded in RAM and played through one serialized `sounddevice` owner so model cues,
  TTS, and interruption cannot race inside PortAudio/CFFI; failures remain hidden from the HUD
- Adaptive local barge-in stops cloud speech after confirmed voice without saving new audio
- Project-scoped key loaded from `.env`
- Explicit `ARIS_ENABLE_OPENAI=true` opt-in prevents accidental API spending
- Additional `ARIS_ENABLE_CLOUD_TTS=true` cost opt-in is required for cloud speech output
- Additional `ARIS_ENABLE_WEB_SEARCH=true` cost opt-in, exactly one required low-context tool call
  per uncached request, a per-process request cap, and RAM-only cache are required for source-cited
  web research
- Development budget target: USD 10
- Short responses and local routing to limit API usage

## Persistence and privacy

- Save settings, model selection, scan ratios, and small action history in local JSON.
- Include a Clear History action.
- Never save webcam images or video.
- Never save raw microphone recordings during or after transcription.
- Keep VAD on-device and show a persistent visual indicator whenever auto-listen is open.
- Keep at most 256 ms of rolling pre-roll in RAM, overwrite it continuously, and encode the
  transcription WAV in memory without writing microphone audio to disk.
- Never log secrets.
- Keep downloaded sound packs and derived cue files local and Git ignored until redistribution
  permission is documented. Sound effects must fail silently and must not trigger auto-listen.

## Portfolio deliverables

- Public GitHub repository only after joint review
- English README maintained by Codex
- Modular, tested source code with Vietnamese docstrings
- Architecture diagram inside README or docs
- User records and edits a separate 1–2 minute demo video
- Python source execution first; `.exe` packaging is future work

## Future roadmap

- Fully local custom wake-word model and optional owner speaker verification
- Face tracking and mask fitting
- Accurate millimeter calibration
- Multi-view scan and higher-quality hand mesh
- Export for Blender/CAD/3D printing
- Higher-detail licensed models
- Distinct licensed sound design for each model
- Iron Man Mask animation
- iPad camera input
- Executable installer
