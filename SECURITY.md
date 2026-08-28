# Security policy

ARIS is an educational beta, not a general-purpose autonomous agent. Its security model intentionally limits what assistant commands can do.

## Supported version

Only the latest commit on the default branch is supported during beta development.

## Main security boundaries

- Common desktop commands are parsed locally into fixed intent types. Unknown natural wording may
  use one strict OpenAI function call, whose fields are validated again before becoming an intent.
- The application allowlist contains Chrome, VS Code, Discord, Codex, Edge, File Explorer,
  Notepad, Calculator, Paint, Windows Terminal, Settings, Spotify, and Snipping Tool.
- File access is restricted to approved user folders and the project directory.
- No assistant response is passed to a terminal, `eval`, or an arbitrary executable.
- Arduino input is restricted to typed `ARIS_HW` events; outgoing commands use a four-value
  allowlist. Web Search text is display-only and never becomes an action. In `ALERT`, the runtime
  chat/Web Search gates and desktop actions are disabled without changing the key stored in `.env`.
- Camera frames are processed in memory and are not persisted by ARIS.
- The always-on microphone monitor derives level, FFT bands, and local voice activity.
- Auto-listen keeps only a rolling 256 ms pre-roll in RAM so the first syllable is not lost;
  it is overwritten continuously, cleared during ARIS speech output, and never persisted.
- `Hey ARIS` gates actions for ten seconds after transcription. It is not biometric owner
  authentication, and standby utterances may still reach the configured transcription API.
- Transcription WAV data is encoded in RAM and is never written to disk by ARIS.
- Cloud use requires a local secret plus an explicit opt-in flag.
- Cloud TTS requires its own second opt-in and remains disabled by default.
- A sonar alert may be synthesized during ARMING and cached only in RAM so ALERT can keep the
  configured voice without making a new cloud request after the runtime gate closes.
- The HC-SR04/IR build is a low-voltage educational proximity alert, not authenticated access
  control. NEC remote codes are replayable; unplug USB before rewiring and never combine 5V and
  3.3V positive rails.

## Responsible reporting

Do not publish API keys, personal paths, screenshots containing secrets, or exploit details in a public issue. Contact the repository owner privately first and include:

- the affected version or commit;
- the smallest safe reproduction;
- expected and actual behavior;
- impact and a suggested mitigation, if known.

## Before every public push

Run the automated tests, `pip-audit`, and inspect the staged diff. Confirm that `.env`, local JSON state, audio, logs, personal files, and generated caches are absent. Revoke any key immediately if it may have entered Git history.
