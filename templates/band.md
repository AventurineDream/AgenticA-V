<!-- Band template, spec v1 (docs/spec/band-album-spec.md §1.1, §1.3, §5). Save as
bands/B-NN-<slug>.md, replace every placeholder, and check it with
`uv run python -m agentic_av.registry`. Comments like this one are guidance; the validator ignores
them, so you may keep or delete them. -->

# Band Name

```toml
[band]
id = "B-NN"
name = "Band Name"
slug = "band-name"
status = "active"
genres = ["first genre", "second genre"]
instrumental = true
house_visual_group = "V-NN"  # optional: delete if the band has no house visual group
label = "Label Name"  # optional
house_engineer = "Engineer Name"  # optional: the label's mastering persona
production_layers = []  # optional: non-member sounds such as "rain" or "room air"

[[members]]
name = "Member One"
roles = ["musician", "composer"]
instruments = ["instrument"]
influences = ["genre or tradition", "genre or tradition"]

[[members]]
name = "Member Two"
roles = ["musician"]
instruments = ["instrument"]
influences = ["genre or tradition", "genre or tradition"]

[process]
composer_rotation = ["Member One"]
recording_order = ["Member One", "Member Two"]
refinement_order = ["Member Two", "Member One"]
```

## Members

<!-- One "### Name" per card member, in card order. Each persona is one paragraph of 60 to 140
words, present tense: how they play, how they listen, what they protect in the music. Never base a
member on a real person. -->

### Member One

Persona paragraph.

### Member Two

Persona paragraph.

## Description

<!-- One paragraph of 60 to 160 words, written after the personas and shaped by them. -->

Description paragraph.

## Sound

- **Core sound:** What the band sounds like when it is most itself.
- **Keep:** What every album keeps.
- **Avoid:** What the band does not do, such as adding an instrument nobody plays.
- **Production layers:** None.

## Discography

<!-- One row per album; "Made with" is every model, or "not recorded". A new band keeps the header
and no rows. -->

| ID | Title | Year | Length | Tracks | Made with |
|---|---|---|---|---|---|

## Provenance

- Written YYYY-MM-DD by <person or agent> with <provider/model>.
