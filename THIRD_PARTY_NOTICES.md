# Third-party notices

ARIS depends on open-source Python packages listed in `pyproject.toml`. Each dependency remains subject to its own license and notices.

## yt-dlp and YouTube playback

- Project: [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- License: The Unlicense (see the installed project's license and third-party notices)
- Use in ARIS: resolve one explicitly requested YouTube audio stream with `download=False`

ARIS does not bundle or redistribute YouTube media. Availability and permitted playback remain
subject to the media owner's rights and YouTube's applicable terms. Users are responsible for
playing only content they are allowed to access.

## MediaPipe Hand Landmarker

- Project: [Google AI Edge MediaPipe](https://github.com/google-ai-edge/mediapipe)
- API documentation: [Hand Landmarker options](https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/vision/HandLandmarkerOptions)
- Local asset: `assets/models/hand_landmarker.task`
- Asset source: `https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task`
- Downloaded: 2026-08-24
- SHA-256: `FBC2A30080C3C557093B5DDFC334698132EB341044CCEE322CCF8BCF3607CDE1`
- MediaPipe repository license: Apache License 2.0

The bundled task asset and MediaPipe software are not relicensed under ARIS's MIT License. Their original terms and provider policies continue to apply.

## Optional local mesh conversion

- `trimesh` 4.12.2 — MIT License
- `fast-simplification` 0.1.13 — MIT License

These packages are optional development tools used to convert user-supplied STL/3MF geometry into
the compact NPZ format consumed by ARIS. They are not required to run the procedural
public-repository build. Generated user meshes have their own source licenses and are excluded from
Git until redistribution rights are confirmed.

The four ZIP archives supplied for Iron Man Mask, Iron Man Hand, Rasengan, and Minato Kunai on
2026-08-25 contained geometry but no license or attribution document. Their derived NPZ files are
therefore private local test inputs, not MIT-licensed repository assets. A filename, preview, or
download availability does not establish redistribution permission.

## Optional local sound pack

The private development machine uses a user-supplied file tagged `Sci Fi UI Sounds`, artist
`Parag Oswal`, to derive short startup and model-materialization WAV cues. No license or
redistribution grant was supplied with the file. The source MP3 and derived WAV files are therefore
Git ignored, are not covered by ARIS's MIT License, and must not be included in a public release
unless their original source, author, attribution requirements, and redistribution terms are
verified. The public code keeps a silent fallback when these files are absent.

- Local source SHA-256: `8F9C93933CC79FBFE9769C518F3E42446F87EA59150DC9B8AB43CA05B49A5624`
- Derived startup cue SHA-256: `036FA78BFE03EC95464CF2931944BB93AB72CF2B582555D84B8C4DA1BEE9752C`
- Derived model cue SHA-256: `CE54F1312337C14C5CDA21015AA4A6B82D7A3795339B3AAAF8B6D9A52725A937`

## Fictional names

Iron Man, Spider-Man, Naruto, Rasengan, Minato, and related names are the property of their respective rights holders. They are referenced only as inspiration in an unofficial, non-commercial educational demonstration. No extracted franchise assets are distributed in this repository.
