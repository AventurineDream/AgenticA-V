# Terminally Agentic A/V

Subtitle: to be decided.

## Project direction

Build a reusable creative recipe and player tools for making audio-visual band worlds. The project repository remains public throughout. Public storytelling can wait until the process is refined and there is more to show.

## Roadmap

1. Continue the planned sequence through all 16 albums.
2. Build a universal web viewer.
3. Have each band create terminal-friendly interpretations of its visuals.
4. Build the CLI player around those interpretations.
5. Once the process is refined, open-source the reusable recipe and tell the project story.

The open-source scope is the recipe and reusable tooling. Individual band details and albums are outside that release.

## CLI invitation and contribution policy

The CLI can become the creator-facing path where fans make new bands and albums under their own labels for publication. This creative invitation is separate from contributions to the project code.

Code contributions are closed by default: communicate before opening a PR, and proceed only if the project owner is interested. Forks and independent experimentation are welcome; the project owner directs the main branch.

## Future feature option: play along

The CLI is the priority for interactive play-along. Explore per-band instrument presets and MIDI keyboard input as the baseline, so fans can improvise over a band’s music. Computer-keyboard note input would be a welcome optional experiment if it can be made responsive and comfortable; MIDI support is sufficient on its own, so keyboard input is not a blocker.

This is technically feasible. Cross-platform MIDI input backends exist; the chosen runtime, audio engine, target operating systems, and input behavior still need validation. A web play-along path is secondary to the CLI and would face narrower MIDI support: Web Audio is broadly available, while Web MIDI has limited browser availability, requires a secure context, and asks the user for permission.

## Technical references

- [MDN: Web Audio API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API)
- [MDN: Web MIDI API](https://developer.mozilla.org/en-US/docs/Web/API/Web_MIDI_API)
- [RtMidi: cross-platform real-time MIDI input and output](https://github.com/thestk/rtmidi)
