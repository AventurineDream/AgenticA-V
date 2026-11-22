# Gap Dynamics

```toml
[album]
id = "A-03"
band = "B-03"
visual_group = "V-03"
title = "Gap Dynamics"
slug = "gap-dynamics"
scope = "test"
status = "final"
date = "2026-11-21"
instrumental = true
rendered = false
recording = "by-track"
round1_order = ["Briar Root", "Hollis Chord", "Oren Floor", "Mira Fern", "Tavi Reed", "Quinn Reed"]
round2_order = ["Quinn Reed", "Tavi Reed", "Mira Fern", "Oren Floor", "Hollis Chord", "Briar Root"]
visual_round1_order = ["Cedar Loom", "Spore Atlas"]
visual_round2_order = ["Spore Atlas", "Cedar Loom"]
mastered_by = "The Night Operator"
made_with = ["anthropic/claude-opus-5-5"]
harness = "omp eval completion(), one stateless message with no tools"
tracks = ["tracks/01-windthrow.md"]

[commission]
direction = ""
reviews = [{ album = "A-01", text = "Positive. It earned the band its second album." }]
```

## Concept

Nobody handed Nurse Log a direction for the third album, so the band chose its own. The review of The Ground Moves Anyway said the band had earned another record. The band read that as permission to keep the floor exactly as heavy and change who stands on it. On the first two albums the sub-bass and the fuzz guitar built the ground and everyone else moved across it. Gap Dynamics starts from the other side: the moment the ground's cover breaks and light gets in.

This test album has one track, written by Mira Fern. Windthrow takes away the fuzz guitar and both saxophones for the first half of a sixteen-bar harp feature. The harp floats in rubato over a single held low D and a rim click. At bar 9 the snare, the fuzz and the moving bass return on one downbeat, and the harp locks back to the kick. The two reeds keep separate routes. The tenor carries the head with delayed phrase endings, and the baritone answers in the gaps and takes its own eight-bar feature over the B changes. The return of the head lands on D instead of turning around, and the coda leaves the harp alone with the rain.

## Tracklist

| # | Title | Length | Key | Meter | Tempo | Composers |
|---|---|---|---|---|---|---|
| 1 | Windthrow | 3:35 | D minor | 4/4 | 1/4=76 | Mira Fern |

## Mastery

With one track, the sequence is Windthrow alone. The Night Operator lets the rain layer fade in over one and a half seconds before the first fuzz attack and lets it run three seconds past the harp's last decay, with no added silence. For a render, the house reference holds: −16 LUFS integrated, true peak at most −1.2 dBTP and a loudness range near 12 LU. The rubato half of the harp Solo stays about 6 LU under A3, so the return at bar 9 keeps its weight.

## Cover

- **A:** A fallen trunk seen from above on a near-black forest floor, with one shaft of moss-green light falling on a sapling at its center.
- **B:** Looking straight up from the forest floor through a ragged gap in a near-black canopy, with rain falling as thin grey lines toward the viewer.
- **C:** A cross-section of a log's growth rings in bark brown and fog grey, with one ring broken open where small warm points of light gather.
- **Chosen:** B — the gap seen from below is what the harp feature sounds like once the fuzz drops away, and the rain is the one layer that never leaves.

## Library blurb

Nurse Log's harp steps into a gap in the floor: a held sub D, slow fuzz, two separate reeds and a dry kit, then the canopy closes.

## Self-review

- [x] The direction and reviews are the only human input, and the concept answers them.
- [x] Every track doc passes its own self-review.
- [x] The tracklist matches the track cards.
- [x] Track and album titles were chosen after the music.
- [x] `made_with` lists every model in the track credits.
- [x] The total length fits the scope: 25:00 to 30:00 for `album`, any length for `test`.
- [x] The concept, cover options and blurb describe only what the music does.

## Provenance

- Made 2026-11-21 by the Terminally Agentic AV swarm in omp eval completion(), one stateless message with no tools with anthropic/claude-opus-5-5.
