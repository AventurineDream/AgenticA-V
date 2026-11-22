# ClangorVisualisMachina

Subtitle: Agentically crafted A/V experiences in your terminal with a community-driven library of bands and albums.

## Project direction

Build a reusable creative recipe and player tools for making audio-visual band worlds. The project repository remains public throughout. Public storytelling can wait until the process is refined and there is more to show.

## Roadmap

Done: each band has terminal-friendly interpretations of its visuals, and the CLI player is built around them (eight albums bundled: every band's A-01 and A-02).

1. Continue the planned sequence through all 16 albums.
2. Once the process is refined, open-source the reusable recipe and tell the project story.

The open-source scope is the recipe and reusable tooling. Four completed A-01 albums are bundled in the player, plus the A-02 albums recorded in ADR 0002: *The Forest Has a Pocket* (Nurse Log), *The Shape That Stays* (Drowning Collective), *Buy One, Haunt One Free* (Coupon Seance), and *Instruments for Measuring Dusk* (Quiet Machinery). That is eight albums / 49 movements. The bundled albums are dedicated to the public domain under CC0 and the code is MIT-licensed (see LICENSE and LICENSE-CC0); bundling is not a listening-review approval. Other band details and albums stay outside that release.

## CLI invitation and contribution policy

The CLI can become the creator-facing path where fans make new bands and albums under their own labels for publication. This creative invitation is separate from contributions to the project code.

Code contributions are closed by default: communicate before opening a PR, and proceed only if the project owner is interested. Forks and independent experimentation are welcome; the project owner directs the main branch. See `CONTRIBUTING.md`.

## Future feature option: play along

The CLI is the priority for interactive play-along. Explore per-band instrument presets and MIDI keyboard input as the baseline, so fans can improvise over a band’s music. Computer-keyboard note input would be a welcome optional experiment if it can be made responsive and comfortable; MIDI support is sufficient on its own, so keyboard input is not a blocker.

This is technically feasible. The [RtMidi spike](../spikes/2026-11-21-rtmidi-omarchy.md) found that `python-rtmidi` builds on Omarchy and loops notes over ALSA and JACK virtual ports without root. No hardware controller has been tested, and the audio engine, instrument presets, target operating systems and input latency still need validation. The player has no MIDI input interface yet; the spike is a record, not an implementation.

## Technical references

- [RtMidi: cross-platform real-time MIDI input and output](https://github.com/thestk/rtmidi)
