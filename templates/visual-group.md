<!-- Visual group template, spec v1 (docs/spec/band-album-spec.md §1.2, §1.3, §1.8, §6). Save
as visual-groups/V-NN-<slug>.md, replace every placeholder, and check it with
`uv run python -m agentic_av.registry`. A visual group has two or three members. -->

# Visual Group Name

```toml
[visual_group]
id = "V-NN"
name = "Visual Group Name"
slug = "visual-group-name"
status = "active"
house_band = "B-NN"  # optional: delete if the group is nobody's house group

[[members]]
name = "Visual One"
medium = "tool or medium"
responsibility = "what this member owns in a scene"
influences = ["genre or tradition", "genre or tradition"]

[[members]]
name = "Visual Two"
medium = "tool or medium"
responsibility = "what this member owns in a scene"
influences = ["genre or tradition", "genre or tradition"]

[process]
order = ["Visual One", "Visual Two"]
```

## Members

<!-- One "### Name" per card member, in card order; each persona is one paragraph of 60 to 140
words: how they see music, what they draw, what they protect. Never base a member on a real
person. -->

### Visual One

Persona paragraph.

### Visual Two

Persona paragraph.

## Description

<!-- One paragraph of 60 to 160 words, written after the personas and shaped by them. -->

Description paragraph.

## Visual language

- **Motifs:** The forms this group returns to.
- **Palette:** The color families its palettes come from.
- **Motion:** How sound and score move the picture; audio moves geometry, never flashes light.
- **Avoid:** What this group does not draw.

## Discography

| Band | ID | Title | Year | Scenes |
|---|---|---|---|---|

## Provenance

- Written YYYY-MM-DD by <person or agent> with <provider/model>.
