# 0003 — Play albums natively with the restored code-only visuals

## Context

Decision 0002 made Enter open the bundled album page in the browser, where autoplay is blocked and the listener must click Play. Aven had earlier made code-only versions of these visuals that ran natively in a terminal: the A/V.html "SHORTWAVE" curses player, with one glyph scene family per band (orbit, aquatic, forest, rooms) driven by each movement's scored note events. She asked for selecting an album in the CLI to play that version in place.

The bundled archives already hold everything that player needs: base64 MP3 audio (one album mix for Coupon Seance, one file per movement for the other three) and per-movement scene names and note events.

## Decision

Enter plays the movement in the terminal. `o` keeps the browser page as an option.

- `scenes.py` ports the original glyph scenes faithfully: same characters, geometry, motion rates, and xterm-256 palettes. Only the drawing target changed, from curses to `Cell` rows for the shared renderer. The Node canvas renderer that drew the HTML scenes as ANSI was not ported; it needs Node and is not the code-only version.
- `native.py` decodes audio and score data from the packaged `.html.gz` into the versioned XDG cache. MP3s are not bundled separately, so the package does not grow and the audio is identical to the web version. A JSON sidecar keeps each movement's scene, offset, and normalized events, so later plays skip re-parsing the 70–112 MB archive.
- mpv plays the audio, and its JSON-IPC `time-pos` is the clock, so the picture follows what the listener hears. ffplay is the fallback, with a wall clock and no seeking; pausing stops and continues the ffplay process, since it has no pause input. Neither child gets stdin, so the library stays in raw mode during playback.
- Playback keys: space pause, ←/→ seek 10 s, n/p (or j/k) movement, m motion, q/Esc back to the library. A movement ends when its file ends, or at the next movement's start in Coupon's shared mix, and playback continues into the next movement.
- `--motion` applies to the picture, never the audio. `still` holds it at the movement start or the last seek, as the original motion-off did. `reduced` moves it at the visual player's 0.22×. `m` toggles still. One deliberate difference from the original: its motion-off left the aquatic family moving, because that family's image renderer animated itself. Here `still` holds every family, so the setting means what a listener who chose it expects.

## Consequences

Native playback needs mpv or ffplay on PATH. Without either, the library shows a note, and `o` still works. The first play of an album decodes about 23–55 MB of MP3 into the cache and shows a loading line; later plays reuse the cache. The original player's radio layout (now-playing, scope, queue, and transport boxes), volume keys, and album keys were not ported. Playback is the full-frame scene plus a status line, which keeps state, clock, and `q back` visible at 80 columns. The bundled archives stay read-only, and the public-scope rules in decision 0002 are unchanged.

Amended 2026-11-22: the library's `o` browser shortcut has since been removed (see CHANGELOG), so Enter's native playback is the only album path; ADR 0004 replaced the faithful glyph port described above.
