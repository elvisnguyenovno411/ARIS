# Assets

- `models/hand_landmarker.task` is the bundled MediaPipe task documented in
  `THIRD_PARTY_NOTICES.md`.
- `user_models/` holds optional locally converted meshes. Only `.gitkeep` is public.
- `user_audio/` holds optional local UI cues. Only `.gitkeep` is public.

User-provided franchise meshes and downloaded sound packs are intentionally excluded from Git.
The application always keeps procedural model fallbacks and silent sound fallbacks so a clean
clone remains usable without private assets.
