<!-- Album template, spec v1 (docs/spec/band-album-spec.md §1.4–§1.9, §7). Save as
albums/B-NN-<band-slug>/A-NN-<slug>/album.md, next to a tracks/ folder of track docs. Write it last,
after every track's band decision, mastery and visuals: the title comes after the music. Check it
with `uv run python -m clangor_visualis_machina.registry`. -->

# Album Title

```toml
[album]
id = "A-NN"
band = "B-NN"
visual_group = "V-NN"
title = "Album Title"
slug = "album-title"
scope = "album"  # album: 25:00 to 30:00 in total; test: any length
status = "final"  # draft | final
date = "YYYY-MM-DD"
instrumental = true
rendered = false  # true once audio exists
recording = "by-album"  # by-album | by-track
round1_order = ["Member One", "Member Two"]
round2_order = ["Member Two", "Member One"]  # reverse of round 1 unless the band chose otherwise
visual_round1_order = ["Visual One", "Visual Two"]
visual_round2_order = ["Visual Two", "Visual One"]
mastered_by = "Member Two"  # a band member or the band's house engineer
made_with = ["provider/model"]  # every model credited on any track
harness = "Harness name"  # optional
tracks = ["tracks/01-track-title.md"]

[commission]
direction = "Up to 220 characters from the person commissioning the album; empty if none."
reviews = [{ album = "A-NN", text = "Optional: up to 220 characters per previous album." }]
```

## Concept

<!-- The band's response to the commission, in its own voice: one to three paragraphs, 80 to 300
words. Say what the direction and reviews changed. With no direction, say the band chose its own. -->

Concept paragraph.

## Tracklist

<!-- One row per track doc, copied from its card. -->

| # | Title | Length | Key | Meter | Tempo | Composers |
|---|---|---|---|---|---|---|
| 1 | Track Title | 1:05 | F major | 4/4 | 1/4=90 | Member One |

## Mastery

<!-- The mastering member's album-level decisions: sequence, gaps between tracks, loudness and
balance across tracks. House reference for rendered audio: -16 LUFS integrated, -1.2 dBTP. -->

Mastery notes.

## Cover

- **A:** One-sentence cover direction.
- **B:** One-sentence cover direction.
- **C:** One-sentence cover direction.
- **Chosen:** A — why the band chose it.

## Library blurb

One line of at most 160 characters, as the player's library shows it.

## Self-review

<!-- Check an item only when it is true. Fix the doc first; never check a box to pass. -->

- [ ] The direction and reviews are the only human input, and the concept answers them.
- [ ] Every track doc passes its own self-review.
- [ ] The tracklist matches the track cards.
- [ ] Track and album titles were chosen after the music.
- [ ] `made_with` lists every model in the track credits.
- [ ] The total length fits the scope: 25:00 to 30:00 for `album`, any length for `test`.
- [ ] The concept, cover options and blurb describe only what the music does.

## Provenance

- Made YYYY-MM-DD by <person or agent> in <harness> with <provider/model>.
