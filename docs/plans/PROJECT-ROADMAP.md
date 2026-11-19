# Terminally Agentic A/V

Subtitle: Agentically crafted A/V experiences in your terminal with a community-driven library of bands and albums.

## Project direction

Build a reusable creative recipe and player tools for making audio-visual band worlds. The project repository remains public throughout. Public storytelling can wait until the process is refined and there is more to show.

## Roadmap

Done: each band has terminal-friendly interpretations of its visuals, and the CLI player is built around them (4 A-01 albums bundled).

1. Continue the planned sequence through all 16 albums.
2. Once the process is refined, open-source the reusable recipe and tell the project story.

The open-source scope is the recipe and reusable tooling. Four completed A-01 albums and Nurse Log A-02 (*The Forest Has a Pocket*) are bundled under the recorded approvals. Drowning Collective A-02 adds six movements under Aven's 2026-11-18 make/bundle/PR instruction; merge is publication approval, with its agent-proposed cover awaiting confirmation or swap. That is six albums / 37 movements on this branch. Bundled albums and covers are CC0, code is MIT (LICENSE and LICENSE-CC0); publication is not listening-review approval. Other band details, source archives, stems and candidate artwork stay outside the release.

## CLI invitation and contribution policy

The CLI can become the creator-facing path where fans make new bands and albums under their own labels for publication. This creative invitation is separate from contributions to the project code.

Code contributions are closed by default: communicate before opening a PR, and proceed only if the project owner is interested. Forks and independent experimentation are welcome; the project owner directs the main branch.

## Future feature option: play along

The CLI is the priority for interactive play-along. Explore per-band instrument presets and MIDI keyboard input as the baseline, so fans can improvise over a band’s music. Computer-keyboard note input would be a welcome optional experiment if it can be made responsive and comfortable; MIDI support is sufficient on its own, so keyboard input is not a blocker.

This is technically feasible. Cross-platform MIDI input backends exist; the chosen runtime, audio engine, target operating systems, and input behavior still need validation.

## Technical references

- [RtMidi: cross-platform real-time MIDI input and output](https://github.com/thestk/rtmidi)
