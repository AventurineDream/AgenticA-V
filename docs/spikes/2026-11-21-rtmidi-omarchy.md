# Spike: RtMidi MIDI input backend on Omarchy (2026-11-21)

Scope: validate that a RtMidi binding installs, enumerates ports, and loops MIDI
messages on this Omarchy box, without root and without changing system packages.
Supports the play-along MIDI input item in `docs/plans/PROJECT-ROADMAP.md`.
This is a spike record, not an implementation decision for the player.

## Environment

| Item | Value |
|---|---|
| Host | Arch/Omarchy, kernel 7.2.15-1-omarchy, x86_64 |
| Python | 3.14.8 (system); the repo requires `>=3.11` |
| Toolchain | gcc 16.2.1, uv via mise |
| Binding | `python-rtmidi` 1.5.8, bundling RtMidi 5.0.0 |
| ALSA | alsa-lib 1.2.16.1-1, alsa-utils 1.2.16-1 (`aconnect`, `amidi`, `aseqdump`) |
| JACK | pipewire-jack 1:1.6.9-1 supplies `libjack.so.0`; `jack2` not installed |
| PipeWire | pipewire 1:1.6.9-1 (`pw-link` used for JACK loopback) |

RtMidi is not an Arch package on this box; it is compiled into the Python
package at build time.

## Commands and results

Throwaway venv outside the repo: `~/.local/share/malachite/rtmidi-spike/.venv`.

1. Build from sdist, default temp dir: `uv pip install python-rtmidi` on Python 3.14
   failed with `Compiler c++ cannot compile programs`. The compiler's error was
   `Disk quota exceeded` writing to `/tmp`: `/tmp` is tmpfs with `usrquota`, and
   it is at quota on this box.
2. Same install with `TMPDIR` on the disk-backed home directory: built and installed
   `python-rtmidi==1.5.8` (about 38 s build). Linked against `libasound.so.2` and
   `libjack.so.0`.
3. Wheel resolution for Python 3.11 on `x86_64-manylinux_2_28`
   (`uv pip install --dry-run --only-binary python-rtmidi`): resolves to 1.5.8.
   Dry run only; the wheel was not installed. On 3.14 the resolver found no
   manylinux wheel and fell back to the sdist.
4. Compiled APIs: `rtmidi.get_compiled_api()` returns `ALSA` and `Jack`.
5. Port enumeration (read-only):
   - ALSA: `Midi Through:Midi Through Port-0 14:0` (kernel `snd_seq` only).
   - JACK: `Midi-Bridge:Midi Through: Port-0`, and `BLE MIDI 1` (in/out).
     The `BLE MIDI 1` port is visible in the PipeWire graph but was not opened.
   - `aconnect -l`, `amidi -l`, `aseqdump -l`: no hardware rawmidi or ALSA seq
     controller other than Midi Through and the PipeWire bridge.
6. ALSA loopback, no root: the spike opens virtual ports `aav-spike-out` (client 130)
   and `aav-spike-in` (client 128), then connects them with `aconnect 130:0 128:0`
   (exit 0). It sends Note On 60 vel 100 and Note Off 60, and receives
   `[[144, 60, 100], [128, 60, 0]]`. Result: **OK**. Virtual outputs deliver only to
   subscribers, so the connection is required.
   The 15 ms figure is the wall time from the first send to the last receive, which
   includes a 10 ms poll loop. It is not a latency measurement.
7. JACK loopback, no root: virtual ports `aav-jack-out` and `aav-jack-in` via the
   JACK API, connected with `pw-link aav-jack-out:aav-jack-out aav-jack-in:aav-jack-in`
   (exit 0). The same two messages came back. Result: **OK**.

## Not tested

- No hardware controller was tested. The `BLE MIDI 1` device is listed but was not
  opened, so its type and whether it sends notes are unknown.
- No latency or jitter measurement; callback timestamps were not compared with a
  reference clock.
- No SysEx, device hot-plug, or port-disconnect behaviour.
- No Python 3.11 install (dry-run resolution only).

## Recommendation

- Use `python-rtmidi` (RtMidi 5.0.0) for MIDI input. It is the Python binding that
  matches the repo's Python project, and ALSA virtual ports and the JACK bridge work
  without root on this box.
- Prefer the ALSA API. Under PipeWire it sees the same kernel and bridge clients.
  JACK is a secondary option.
- Installation: sdist builds need a temp directory that is not the full tmpfs `/tmp`
  (set `TMPDIR` to a disk path). Installs on Python versions without a manylinux
  wheel fall back to that sdist build.
- Next step, owned by Aven: connect a real controller and measure note-to-callback
  latency. Only then decide whether this backend is enough for play-along.
