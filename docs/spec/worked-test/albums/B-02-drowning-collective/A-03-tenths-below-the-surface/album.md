# Tenths Below the Surface

```toml
[album]
id = "A-03"
band = "B-02"
visual_group = "V-02"
title = "Tenths Below the Surface"
slug = "tenths-below-the-surface"
scope = "test"
status = "final"
date = "2026-11-21"
instrumental = true
rendered = false
recording = "by-track"
round1_order = ["Iris Current", "Mica Low", "Pax Lilt"]
round2_order = ["Pax Lilt", "Mica Low", "Iris Current"]
visual_round1_order = ["Silt Index", "Nerve Current"]
visual_round2_order = ["Nerve Current", "Silt Index"]
mastered_by = "The Night Operator"
made_with = ["anthropic/claude-opus-5-5"]
harness = "omp eval completion(), one stateless message with no tools"
tracks = ["tracks/01-gill-practice.md"]

[commission]
direction = "Learning to breathe underwater: first the panic, then a long, strange calm. By the last bar the two piano hands should argue less."
reviews = [{ album = "A-01", text = "An Uneven Kindness, Current Without a Shore and Where the Downbeat Went Under landed best." }]
```

## Concept

Iris Current heard the brief on the piano first: the two hands are the argument. In head A they disagree about the 7/8, the right hand counting 2+2+3 and the left 3+2+2, over D minor with an Ebmaj7 that will not settle and an A7 that never resolves. Then comes thirty seconds of piano alone in free time, the first breath. Head B is the same contour slowed into 9/8 and moved into D major. Across its last four bars the left hand gives up its own grouping and follows the right in tenths, until both land on D an octave apart and the Coda lets that agreement ring.

The review told us which of our first tracks held up: the ones where tenderness came through unevenness, where the current had no floor and the beat slipped. So the panic keeps Pax Lilt's missing downbeat kicks and a snare that drifts off its cell. The Break is open space for Mica Low's bass to speak in whole sentences. The calm stays strange rather than sweet, with C natural over a D in the bass and a G under the head's C sharp. This is a one-track test session, not a release.

## Tracklist

| # | Title | Length | Key | Meter | Tempo | Composers |
|---|---|---|---|---|---|---|
| 1 | Gill Practice | 4:38 | D minor | 7/8 | 1/8=210 | Iris Current |

## Mastery

The Night Operator sequences Gill Practice alone.

- **Gaps:** a half-second of silence leads in. After the Coda's last D decays to the noise floor, a three-second tail follows.
- **Loudness:** the track sits at the house reference of -16 LUFS integrated, true peak at most -1.2 dBTP.
- **Loudness range:** it is left at about 13 LU, because the drop from panic to calm is the point.
- **Future tracks:** if the band grows this test into an album, other tracks will be matched to the level of the calm B sections, not the A3 peak.

## Cover

- **A:** A heavy grey mass of ink sinking through blue-black water, with two thin teal threads above it running side by side at a fixed distance.
- **B:** A cramped knot of black and grey brushstrokes in the upper left corner, the rest of the canvas deep, empty blue-black.
- **C:** A single restrained amber point low on a mineral-grey field, with two teal lines bending toward it from opposite edges.
- **Chosen:** A — it shows the whole arc of the track, the panic's body going under and the two currents ending close and parallel.

## Library blurb

A 7/8 panic gives way to a slow 9/8 calm, and the piano's two hands end a tenth, then an octave, apart.

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
