# ARIS repository guidance

## Product goal

Build a Windows-first Python desktop portfolio project named **ARIS — Augmented Reality Intelligence System**. The beta combines a safe desktop assistant, a holographic low-poly 3D model viewer, one-hand scanning, and gesture-based model controls.

## Non-negotiable decisions

- Use Python 3.12 and PySide6.
- Open the main HUD maximized and calculate its restore geometry from Qt's available logical screen
  bounds so Windows display scaling never pushes the title bar or resize handles off-screen.
- Keep features in small, focused modules rather than a monolithic file.
- Use English identifiers and repository documentation.
- Every public function and class must include a concise Vietnamese docstring explaining its purpose and relevant inputs/outputs.
- Camera frames are processed in memory and must never be saved.
- Store only derived hand proportions and local preferences in JSON.
- Desktop actions use an allowlist. Never execute arbitrary shell commands from model output.
- Keep common Vietnamese/English command variants in the fast local router. Unknown natural
  phrasing may use one strict OpenAI function call that returns only a typed action; validate its
  app/model/action/operation/amount fields again in Python before dispatch. Questions, negated
  commands, quoted examples, and hypothetical discussion must remain non-executable conversation.
- Never commit `.env`, API keys, audio recordings, personal paths, or user data.
- Keep user-supplied meshes under Git-ignored `assets/user_models/` until their source and
  redistribution license are documented; public builds must retain procedural fallbacks.
- The app must work in mock/offline mode until an OpenAI API key is configured.
- OpenAI calls require both a key and the explicit `ARIS_ENABLE_OPENAI=true` opt-in.
- Default transcription language to automatic detection so one session can accept Vietnamese and
  English; allow `vi` or `en` overrides for single-language installations.
- OpenAI Web Search requires the additional `ARIS_ENABLE_WEB_SEARCH=true` cost opt-in, uses a
  bounded per-session request count, keeps its cache only in RAM, and never converts web content
  into desktop/model/hardware actions.
- Cloud TTS requires the additional `ARIS_ENABLE_CLOUD_TTS=true` cost opt-in and remains optional.
- Arduino input must use typed `ARIS_HW` events and a fixed outgoing command allowlist; never pass
  Serial content to a shell, file action, or AI-generated executable path.
- Cloud TTS decodes WAV in RAM and plays through `sounddevice`; failures stay hidden from the HUD
  and never trigger Windows system sounds or SAPI.
- During cloud playback, local adaptive barge-in stops speech after confirmed user voice while
  guarding against speaker echo; no interruption audio is stored or uploaded.
- Do not push to GitHub until the owner and Codex complete a joint security and portfolio review.

## Beta scope

- The default HUD shows a centered ARIS energy orb with the `A` at its core, cyan/purple
  orbital traces, and a clean dark technology background. Keep sparse particles and circuit
  traces, but never restore a square/perspective floor grid. Debug controls stay hidden normally.
- Startup reveals the `A` first, then spreads a radial light wave and thin circuit paths into the
  HUD. Optional local cues run off the UI thread, stay Git ignored without a documented license,
  and delay microphone monitoring until playback is over.
- Clicking the logo once starts command recording; clicking it again stops and submits.
- Keep a lightweight local microphone monitor active with a visible ring indicator. Local VAD
  captures confirmed speech and stops after sustained silence, but voice intents require a
  `Hey ARIS` wake phrase. The active command session lasts ten seconds and confirmed voice extends
  it. Be explicit that beta wake filtering is post-transcription, not offline speaker identity.
- A rolling pre-roll may hold at most 256 ms of raw audio in RAM; overwrite it continuously,
  clear it during ARIS speech output, and never persist it to disk.
- A model request adds a background-free floating hologram over the existing ARIS HUD. Multiple
  models may stay open and be dragged independently without creating native Windows windows.
- Prepare the transparent OpenGL compositor before the window is shown and build the requested
  model only once so the first hologram never hides/recreates the ARIS window. Newly created models
  may use a short local cue while VAD is suspended.
- The selected hologram receives gesture input at the highest render rate; inactive holograms use
  a lower render rate to protect total frame time.
- Holograms auto-rotate while idle. Confirmed hand interaction pauses rotation; after five seconds
  without an active gesture, resume smoothly from the current angle. Never reset orientation when
  switching between gesture control and idle rotation.
- `close <model name>` closes only that model; `end` / `kết thúc` closes the whole hologram session;
  `Esc` closes the selected model as a hidden debug fallback.
- Keep opening and focusing separate: `show/open` may create a hologram, while
  `select/chọn/điều khiển <model>` only focuses an already-open hologram. Unnamed gesture and
  voice-zoom input always targets that single focused model.
- Voice zoom commands run through the local router without API cost. Support named or selected
  holograms with bounded percentages, for example `phóng to Rasengan 30%` and
  `thu nhỏ model 20%`; animate smoothly toward the exact visual-size target.
- Open Chrome, VS Code, Discord, Codex, Edge, File Explorer, Notepad, Calculator, Paint,
  Windows Terminal, Settings, Spotify, and Snipping Tool through fixed launch specifications.
  Opening Terminal must never forward voice text, AI output, or arbitrary arguments. Supported
  close commands must use normal `WM_CLOSE` only for a fixed executable allowlist, never force-kill.
- Do not scan or select personal local audio/video, including Music, Downloads, OneDrive, and
  Documents. When `ARIS_ENABLE_YOUTUBE_MUSIC=true`, use embedded yt-dlp search with `download=False`
  and play only the validated HTTPS audio stream through Qt's FFmpeg backend. Never invoke a
  shell or persist YouTube media. Cache recent signed stream metadata only in RAM for at most five
  minutes so replay does not repeat yt-dlp search. One selected track loops
  indefinitely; pause/resume preserves its position, and requesting another title replaces the old
  source and loop. Music volume is a persisted ARIS-only gain, distinct from Windows volume;
  `tắt nhạc`/`dừng nhạc`/`stop music` must stop immediately and clear the current source, while
  `tạm dừng`/pause and resume preserve position. When a track or YouTube lookup is active,
  contextual `tắt nó`/`stop it` resolves locally to stop music instead of model close or cloud
  chat. Duck and restore music with a smooth envelope instead of abrupt jumps. While playing,
  fade the background to purple-black and drive a strong but smoothed core/ring beat envelope from
  decoded PCM held only in memory. Feed only its scalar RMS
  into a local playback-aware voice gate so speaker echo is suppressed while a nearby `Hey ARIS`
  can still start auto recording. Feed the gate a volume-adjusted playback reference distinct from
  the amplified HUD beat envelope; pre-duck rapidly on the first near-voice candidate, keep the
  deep duck through recording/speech, and restore slowly. Preserve the manual logo fallback for
  unusually loud rooms.
- YouTube lookup and playback are silent UI transitions: never speak the video title, caption, or
  a searching/started message. Debounce QMediaPlayer errors and ignore stale/transient errors while
  the current source is still playing.
- Source-cited OpenAI Web Search, allowlisted file opening, and volume adjustment.
- Each explicit research request creates its own in-HUD data panel. Keep up to six panels open,
  selectable, independently draggable and clamped to the HUD. Opening/closing uses short local
  materialize/de-materialize animation and optional cues; closing a panel must never cancel,
  move, or hide 3D holograms. Selecting a research panel transfers five-finger MOVE to that panel;
  vertical pinch/TRANSFORM scrolls its content without moving the panel or rotating a 3D model.
- Static low-poly hand scan from an open palm.
- Gesture controls default to an exclusive two-mode local state machine. A confirmed five-finger
  open hand moves the selected floating hologram in the HUD. A confirmed thumb-index pinch locks
  transform mode: hand X rotates the model around one horizontal viewing orbit; hand Y must not
  tilt it. Camera landmarks must never change zoom; only local voice commands may resize models.
  Require a short release before switching modes so position and rotation never overlap.
  Capture the laptop camera at 640×480 but use 480×360 inference by default, moderate MediaPipe
  confidence thresholds, scale-aware smoothing, and a three-frame tracking-loss grace period so
  distant/angled hands remain usable without jumps.
  Every newly requested model starts centered over the ARIS core. Preserve
  `ARIS_GESTURE_MODE=grab_throw` and `ARIS_GESTURE_MODE=legacy` as tested fallbacks.
- Model library display names: Iron Man Mask, Iron Man Hand, Spider-Man Mask, Web Shooter, Rasengan, and Minato Kunai.
- Holographic cyan rendering; smooth performance is more important than geometric detail.
- Spoken responses start their typewriter reveal with audio playback and use the decoded WAV
  duration so text does not race ahead. The core `A` follows the emitted playback envelope.
- The optional UNO guard uses HC-SR04 TRIG/ECHO on D9/D10 and IR signal on D2. The local phrase
  `trạng thái sonar` arms a ten-second delay. ALERT fades the HUD red, speaks from a RAM-cached
  matching voice or local fallback, stops microphone/gesture input, and disables API/desktop
  actions without modifying `.env`.
  Only the verified physical IR remote clears ALERT in beta; describe it as a replayable
  proximity-alert prototype rather than authenticated security.
- When cloud TTS is enabled, prepare the sonar alert WAV in RAM during ARMING so ALERT uses the
  same voice without a new API request; never persist the cache. Explicit commands that name ARIS
  may bypass an expired wake session as a local emergency exit; they run a reverse power-down
  animation, then close the window and release resources. A wake prefix such as `Hey ARIS` must be
  removed before routing so `Hey ARIS, dừng nhạc` can never be mistaken for app shutdown.
- Keep transient status text hidden so idle, wake, voice failure, camera readiness, and hardware
  connection states never add text around the logo. Research panel content remains visible. All visual energy
  transitions use a smooth envelope and idle retains a subtle breathing animation. Orbital phase
  is continuous; individual elements may wrap only after completing their own full cycle. The
  purple dashed monitoring ring must use a continuous dash offset with no modulo reset.
- Transparent floating OpenGL views require an alpha buffer plus `WA_AlwaysStackOnTop` on Windows;
  validate them through the real screen compositor because `QWidget.grab()` can hide black boxes.
- No face tracking, real-world millimeter measurements, executable packaging, or GitHub push in beta.

## Validation

- Add or update tests for routing, safe paths, persistence, and geometry logic.
- Run `pytest` before handoff.
- Run the application in mock mode and inspect the rendered window before declaring UI work complete.
- Keep README's computer-impact measurements honest and labeled as machine-specific baselines.
- At project completion, re-test installation on a clean Windows account and replace the beta setup
  note with a beginner-friendly guide covering prerequisites, setup, optional API, permissions,
  first-run checks, troubleshooting, updates, and complete removal.
