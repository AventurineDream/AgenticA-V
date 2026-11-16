# 0003 — Play albums natively with the restored code-only visuals

## Context

Decision 0002 made Enter open the bundled album page in the browser, where autoplay is blocked and the listener must click Play. Aven had earlier made code-only versions of these visuals that ran natively in a terminal: the A/V.html "SHORTWAVE" curses player, with one glyph scene family per band (orbit, aquatic, forest, rooms) driven by each movement's scored note events. She asked for selecting an album in the CLI to play that version in place.

The bundled archives already hold everything that player needs: base64 MP3 audio (one album mix for Coupon Seance, one file per movement for the other three) and per-movement scene names and note events.

## Decision

Enter plays the movement in the terminal. `o` keeps the browser page as an option.

- `scenes.py` ports the original glyph scenes faithfully: same characters, geometry, motion rates, and xterm-256 palettes. Only the drawing target changed, from curses to `Cell` rows for the shared renderer. The Node canvas renderer that drew the HTML scenes as ANSI was not ported; it needs Node and is not the code-only version.
- `native.py` decodes audio and score data from the packaged `.html.gz` into the versioned XDG cache. MP3s are not bundled separately, so the package does not grow and the audio is identical to the web version.
- mpv plays the audio, and its JSON-IPC `time-pos` is the clock, so the picture follows what the listener hears. ffplay is the fallback, with a wall clock and no seeking. Neither child gets stdin, so the library stays in raw mode during playback.
- Playback keys: space pause, ←/→ seek 10 s, n/p (or j/k) movement, q/Esc back to the library. A movement ends when its file ends, or at the next movement's start in Coupon's shared mix, and playback continues into the next movement.

## Consequences

Native playback needs mpv or ffplay on PATH. Without either, the library shows a note, and `o` still works. The first play of an album decodes about 23–55 MB of MP3 into the cache, and later plays reuse it. The original player's radio layout (now-playing, scope, queue, and transport boxes), volume keys, and album keys were not ported. Playback is the full-frame scene plus a status line. The bundled archives stay read-only, and the public-scope rules in decision 0002 are unchanged.
