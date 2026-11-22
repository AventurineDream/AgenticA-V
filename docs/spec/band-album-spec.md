<!-- Owner: Aven. Maintained by: Malachite. Spec version 1, 2026-11-21. Changing a rule here means changing
the templates, the validator (src/agentic_av/registry.py, notation.py), the swarm prompt and the worked test
in the same change. -->

# Bands, visual groups and albums — format and process spec

Version 1, written 2026-11-21 for the third round of albums (the A-03s). It turns the album process from
the project's planning notes (the 2026-11-18 school review and Aven's answers) into rules and four
document formats that agents and people can follow without help, and that the validator can check.

**Quick reference.** A band doc lives in `bands/`, a visual group doc in `visual-groups/`, an album in
`albums/<band>/<album>/` as `album.md` plus one track doc per track under `tracks/`. Copy the matching file
in [`templates/`](../../templates/). Check your work with:

```bash
uv run python -m agentic_av.registry
```

To make a band, visual group or album in another agent harness, use the one-shot
[swarm prompt](../../prompts/swarm.md). It carries these rules and templates with it.

The words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119. "Characters" means Unicode characters,
spaces included.

## 1. Process rules

These rules are the album process. The validator checks what can be checked (§10); the rest is an honor
system, and every doc records enough of the process that a reader can see whether it was followed.

### 1.1 Bands

- A band MUST have at least two musicians, and at least one musician MUST also be a composer. There is no
  upper limit on members.
- A person making an album MAY use an existing band or make a new one, from scratch or by recycling members
  of other bands (`from` in the member's card entry, §5).
- Bands are model-agnostic. A band doc names no models; every track lists the model that played or made
  each member's part (§8, `credits`).
- Albums are instrumental for now (Aven, 2026-11-18): no lyrics, vocals or voicebanks. A band MUST NOT list
  a voice as an instrument until that changes.
- Sounds that are not people, such as rain or room air, are production layers, not members.

### 1.2 Visual groups

- A visual group has two or three members. It makes the album's visuals once the music is finished.
- A band MAY have a house visual group. Any defined visual group MAY take any band's album.
- "Visual group" is the same thing the planning notes call a visual team.

### 1.3 Member definitions

- Every member of a band or visual group MUST have a name, a one-paragraph persona, an instrument (for a
  visual member: a tool or medium) and personal genre influences.
- A persona is one paragraph of 60–140 words in the present tense. It says how the member plays or makes
  images, how they listen, and what they protect in the music. It MUST NOT be based on a real person.
- Influences are two to five genres, scenes or traditions. They MUST NOT name real artists.
- The band or visual group description MUST be written after the member personas, and is shaped by them.
  The docs put members first for that reason.

### 1.4 Commissioning: what the human gives

- The person commissioning an album picks a band, picks a visual group (the album's visual theme), and
  writes an album direction of at most 220 characters.
- If the band has previous albums, they MAY add one review of at most 220 characters per previous album.
- Nothing else from the human enters the album. With no direction, the band chooses its own and says so in
  the album's concept.
- A person MAY write a band or visual group doc themselves, or give the swarm prompt a seed of at most 220
  characters for each. The swarm then writes the members.

### 1.5 Composition

- A track MAY be composed by one member, by several together, or by members taking turns.
- Composition covers the form, the harmonic movement, the core rhythms, the head melody or melodies, and
  lyrics if any (none for now). Nothing else: no full arrangements, written voicings, fills or solos. That
  room belongs to the performers.
- Each composer does two or three passes on each track they compose, refining each time. Each pass is
  logged: what was written or changed, and why.

### 1.6 Recording: the 3×2 loop

- Once a track is composed, the band sets the recording order (`round1_order`, §7).
- **Round 1.** The first member records three takes. The next member picks the best of them, then records
  three takes of their own; the member after that picks among those, and so on. A member who plays two
  parts records three takes of each, one part after the other.
- **Round 2 (refinement).** The loop runs again over the finished round 1, by default in the reverse
  order. A band that wants another order records it as `round2_order`.
- A pick is made by a different member than the one who recorded the takes, normally the next one in the
  order. The last takes of round 2 are picked by the band.
- **Band decision.** After both rounds, the members decide together on the final combination: one take per
  part, from either round, with reasons.
- A take is one complete performance of the member's part over the whole track. When no audio is rendered,
  a take is written as performance directions: feel, dynamics, articulation, register, how the open space is
  used, and any deliberate departure from the composition. The three takes MUST differ in a way a listener
  would hear.
- An album MAY be recorded by track (each track through both rounds before the next) or by album (every
  track's round 1 before any round 2). The album card says which.

### 1.7 Mastery

- After the band decision, one member does the mastery pass: the balance of levels, tone, space and
  dynamics, and the loudness of the finished track. The `mastered_by` member MUST be a band member or the
  band's house engineer (§5, `house_engineer`).
- House reference for rendered audio: −16 LUFS integrated, true peak at most −1.2 dBTP, loudness range
  about 12 LU. Digital checks do not replace listening; the creator's listening review is the acceptance
  step.

### 1.8 Visuals: the same 3×2 loop

- The visual group receives the finished, mastered music and runs the same loop: in `visual_round1_order`,
  each member makes three takes of the track's scene and the next member picks; round 2 runs in reverse;
  then the group decides on the final combination.
- Scenes are drawn for the terminal player. Audio and the score move geometry; they MUST NOT drive
  beat-synchronized flashes of light or full-screen luminance changes.
- Every scene MUST read in full, reduced and still motion, and without color. A quiet passage keeps a
  composed picture; nothing is faked when there is no signal. Pictures are deterministic: the same moment
  always draws the same frame.
- Each scene has three palette colors: background, body and highlight.

### 1.9 Names, cover and credits

- Track and album titles are chosen after the music exists: a track is named after its band decision, the
  album after its last track.
- The album has three written cover options (A, B, C) and one chosen option with a reason. Making the image
  is optional; covers have no text, logos or real people.
- Every track credits each member who worked on it, with the model that did the work: composers
  (`composition`), musicians (their part), the mastering member (`mastering`) and every visual member
  (`visuals`). Model IDs are written `provider/model`, for example `anthropic/claude-opus-5-5`.
- Music and images are original. Do not quote existing melodies, use samples of recordings, or depict real
  people.

## 2. Files and identifiers

```text
bands/B-01-coupon-seance.md
visual-groups/V-01-coupon-seance-house-visuals.md
albums/B-01-coupon-seance/A-03-<album-slug>/album.md
albums/B-01-coupon-seance/A-03-<album-slug>/tracks/01-<track-slug>.md
templates/{band,visual-group,album,track}.md
prompts/swarm.md
```

| Thing | ID | Rule |
|---|---|---|
| Band | `B-NN` | Two or three digits, never reused. File `bands/<id>-<slug>.md`. |
| Visual group | `V-NN` | Two or three digits, never reused. File `visual-groups/<id>-<slug>.md`. |
| Album | `A-NN` | Numbered within its band in release order. Folder `albums/<band id>-<band slug>/<id>-<slug>/`. |
| Track | `NN` | Two-digit position on the album. File `tracks/<NN>-<slug>.md`. |

A slug is the name in lowercase ASCII words joined by single hyphens (`Coupon Seance` → `coupon-seance`).
`README.md` files in these folders are indexes, not docs, and the validator skips them.

| Text | Limit |
|---|---|
| Album direction, each previous-album review, swarm seeds | 220 characters |
| Library blurb (the player's album description) | 160 characters |
| Persona | one paragraph, 60–140 words |
| Band or visual group description | one paragraph, 60–160 words |
| Album concept | one to three paragraphs, 80–300 words |

## 3. Document format

Every doc is Markdown in this shape:

1. One `# Title` line: the band, group, album or track name.
2. A **card**: the first fenced code block, tagged `toml`, holding the doc's structured fields. Only TOML
   that Python's `tomllib` reads is valid.
3. The doc's `##` sections, every required one, in the order given below. No other `##` sections.

HTML comments (`<!-- … -->`) are guidance and are ignored by the validator. Prose is plain Markdown. A
"paragraph" is text without a blank line inside it.

The order of each doc follows the order of the work: members before the description, composition passes
before the final composition, takes before decisions. Write a doc top to bottom and the process runs in
order.

## 4. Shared card rules

- `id`, `slug` and the file name MUST agree.
- Every name referenced anywhere (orders, credits, `mastered_by`, headings) MUST match a member's `name`
  exactly.
- `status` is `active` or `retired` for bands and visual groups.

## 5. Band doc

Card:

```toml
[band]
id = "B-05"                      # required, B-NN
name = "Example Band"            # required; also the album-artist credit
slug = "example-band"            # required
status = "active"                # required: active | retired
genres = ["…", "…"]              # required: two or three genre tags
instrumental = true              # required: true (albums are instrumental for now)
house_visual_group = "V-05"      # optional: an existing visual group
label = "…"                      # optional: the label the band records for
house_engineer = "…"             # optional: label mastering persona allowed to master this band
production_layers = ["…"]        # optional: non-member sounds, e.g. "rain"

[[members]]                      # one table per member, in display order
name = "…"                       # required, unique in the band
roles = ["musician", "composer"] # required: any of musician, composer
instruments = ["…"]              # required for musicians
influences = ["…", "…"]          # required: two to five genres or traditions
from = "B-02"                    # optional: band the member was recycled from

[process]                        # optional band defaults; each album records its own orders
composer_rotation = ["…"]        # composers, in rotation order
recording_order = ["…"]          # each musician once
refinement_order = ["…"]         # same musicians; usually the reverse
```

Sections, in order:

| Section | Content |
|---|---|
| `## Members` | One `### <name>` per member, in card order, each holding the persona paragraph (§1.3). |
| `## Description` | One paragraph, written after the personas. |
| `## Sound` | Bullets that start `**Core sound:**`, `**Keep:**` and `**Avoid:**`; MAY add `**Production layers:**`. |
| `## Discography` | Table `ID \| Title \| Year \| Length \| Tracks \| Made with`. A new band keeps the header with no rows. |
| `## Provenance` | Bullets: who wrote the doc and when, sources, and anything carried over or derived. |

## 6. Visual group doc

Card:

```toml
[visual_group]
id = "V-05"                     # required, V-NN
name = "…"                      # required
slug = "…"                      # required
status = "active"               # required: active | retired
house_band = "B-05"             # optional: the band this group is the house group of

[[members]]                     # two or three
name = "…"                      # required, unique in the group
medium = "…"                    # required: tool or medium
responsibility = "…"            # required: what this member owns in a scene
influences = ["…", "…"]         # required: two to five genres or traditions
from = "V-02"                   # optional: group the member was recycled from

[process]                       # optional default take order
order = ["…", "…"]
```

Sections, in order: `## Members` (as for bands), `## Description` (one paragraph, written after the
personas), `## Visual language` (bullets starting `**Motifs:**`, `**Palette:**`, `**Motion:**` and
`**Avoid:**`), `## Discography` (table `Band | ID | Title | Year | Scenes`, may be empty) and
`## Provenance`.

## 7. Album doc

`albums/<band>/<album>/album.md`. Card:

```toml
[album]
id = "A-03"                        # required, A-NN
band = "B-01"                      # required: existing band
visual_group = "V-01"              # required: existing visual group (the commission's visual theme)
title = "…"                        # required, chosen after the last track
slug = "…"                         # required
scope = "album"                    # required: album (25:00–30:00 in total) | test (any length)
status = "final"                   # required: draft | final
date = "2026-11-21"                # required: date finished, YYYY-MM-DD
instrumental = true                # required: true
rendered = false                   # required: true once audio exists
recording = "by-album"             # required: by-album | by-track
round1_order = ["…"]               # required: every musician on the album, once
round2_order = ["…"]               # required: same musicians, reverse unless the band chose otherwise
visual_round1_order = ["…"]        # required: every visual group member, once
visual_round2_order = ["…"]        # required: same members
mastered_by = "…"                  # required: band member or the band's house engineer
made_with = ["provider/model"]     # required: every model that worked on the album
harness = "…"                      # optional: the agent harness used
tracks = ["tracks/01-….md"]        # required: track docs in order

[commission]
direction = "…"                    # required: at most 220 characters; "" when none was supplied
reviews = [{ album = "A-01", text = "…" }]  # optional: at most 220 characters each
```

Sections, in order:

| Section | Content |
|---|---|
| `## Concept` | The band's response to the commission, written by the band: one to three paragraphs. |
| `## Tracklist` | Table `# \| Title \| Length \| Key \| Meter \| Tempo \| Composers`, one row per track doc, matching their cards. |
| `## Mastery` | The mastering member's album-level decisions: sequence, gaps, loudness and balance across tracks. |
| `## Cover` | Bullets `**A:**`, `**B:**`, `**C:**` (one-sentence directions) and `**Chosen:** <letter> — <reason>`. |
| `## Library blurb` | One line of at most 160 characters, as the player's library would show it. |
| `## Self-review` | The album checklist from the template, every item checked (`- [x]`). |
| `## Provenance` | Bullets: who made it, with which models and harness, and when. |

## 8. Track doc

`albums/<band>/<album>/tracks/NN-<slug>.md`. Card:

```toml
[track]
album = "A-03"                 # required: matches the album card
band = "B-01"                  # required
number = 1                     # required: position, matches the file name
title = "…"                    # required, chosen after the band decision
slug = "…"                     # required
key = "F Lydian"               # required: tonal centre and mode
meter = "4/4"                  # required: main meter
tempo = "1/4=88"               # required: beat unit = beats per minute (ABC Q: syntax)
length = "4:31"                # required: m:ss, from the form and tempo (§9.5)
composers = ["…"]              # required: members with the composer role

[[credits]]                    # one per member per part
member = "…"
part = "composition"           # composition | mastering | visuals | an instrument part
model = "provider/model"
```

Every credit with an instrument part is a recording slot: a member who plays two parts has two credits.
The part is one of the member's `instruments` on the band card, spelled the same, so a band never gains
an instrument nobody in it plays. A track MUST have at least two recording members.

Sections and subsections, in order:

```text
## Composition passes
### Pass 1 — <composer>          two or three passes per composer
## Composition
### Form                          table, §9.1
### Harmony                       chords block, §9.2
### Core rhythms                  rhythm and/or abc blocks, §9.3
### Heads                         abc blocks, §9.4
### Lyrics                        "None — instrumental."
## Recording
### Round 1
#### <member> — <part>           one per recording slot, in round 1 order
### Round 2
#### <member> — <part>           in round 2 order
### Band decision
## Mastery
## Visuals
### Round 1
#### <visual member>             in visual round 1 order
### Round 2
#### <visual member>
### Group decision
### Scene
## Self-review
```

A take subsection holds exactly this:

```markdown
#### Dale Rebate — electric bass
- Take 1: Roots on beat one only; pickups held back until the second A.
- Take 2: Walks from bar 9, quotes the head's falling third in the turnaround.
- Take 3: Plays the B section an octave down, leaving bars 21–24 empty.
- Picked by Vera Rosin: Take 2 — the walk gives the bow something to lean on.
```

`### Band decision` names one take per recording slot, then gives the reasons:

```markdown
- Sid Spindle — crooked keys: Round 2, Take 1
- Dale Rebate — electric bass: Round 1, Take 2
```

`### Group decision` does the same for visual members (`- June Orbit: Round 2, Take 3`). `### Scene` is
bullets `**Scene:**` (a slug, unique on the album), `**Label:**` (upper case, e.g. `ARRIVAL / RINGS OPEN`),
`**Palette:**` (three `#rrggbb` colors), `**Picture:**` and `**Motion:**` (full, reduced and still), plus a
table `Source | Visual behavior` mapping parts or sections to what they move.

## 9. Notation

### 9.1 Form table

```markdown
| Section | Bars | Meter | Texture and intensity | Open space |
|---|---|---|---|---|
| Intro | 4 | 4/4 | keys alone, pp | — |
| A1 | 16 | 4/4 | full band, mp | violin fills in bars 15–16 |
| Solo | 16 | 4/4 @ 1/4=96 | bass and keys, mf | violin solo over the A changes |
| Coda | 20s | free | violin alone, rubato | the whole coda |
```

- List sections in playing order and write repeats out as rows (`A1`, `A2`). Labels are unique.
- `Bars` is a whole number; a free-time section writes its length in seconds (`20s`) with meter `free`.
- `Meter` is `n/d`; add `@ unit=bpm` to change tempo for that section.
- At least one section MUST name open space (a solo, a feature, room to improvise).

### 9.2 Chord chart

A fenced block tagged `chords`. One line per form section; every bar written out between `|` signs.

```chords
Intro | Fmaj7#11 | % | Ebmaj7#11 | % |
A1    | Fmaj7 | Bbmaj7 | Am7 D7b9 | Gm7 C7 |
      | Fmaj7 | Bbmaj7 | Am7 D7b9 | Gm7 C7 |
A2 = A1
```

- A bar holds one or more chord symbols separated by spaces, `%` (same as the bar before) or `N.C.`.
- A line that starts with `|` continues the section above. `A2 = A1` reuses a section's chords; both
  sections MUST have the same number of bars.
- Every metered section in the form MUST have a line with exactly its number of bars. Modes and voice
  leading go in prose under the block.

### 9.3 Core rhythms

Unpitched rhythms are grids in a fenced block tagged `rhythm`:

```rhythm
meter: 7/8 (2+2+3)  step: 1/8
kick  | x . . . x . . |
snare | . . X . . . o |
bass  | x - x - x - - |
```

- A `meter:` line sets the meter and step for the rows below it; a block MAY change meter.
- Cells: `x` hit, `X` accent, `o` ghost, `-` hold, `.` rest. Spaces between cells are optional.
- Every bar MUST have exactly meter ÷ step cells (7/8 in eighths: 7).

Pitched cells such as a bass ostinato MAY be written in ABC (§9.4) instead.

### 9.4 Heads (ABC)

Heads are written in [ABC notation](https://abcnotation.com/wiki/abc:standard:v2.1), in fenced blocks
tagged `abc`, restricted to what the validator can count:

- Header lines `X:`, `T:` (the head's name), `M:`, `L:`, optional `Q:` and `V:` lines, and `K:` last.
- Notes with `^` `_` `=` accidentals, octave marks `'` `,` and lengths (`2`, `3/2`, `/`, `/2`); rests `z`;
  whole-bar rests `Z` (`Z4` is four bars); chords `[CEG]`; ties `-`; slurs; tuplets `(3` and `(p:q:r`;
  broken rhythm `>` `<`; grace notes `{…}` (no time); chord symbols `"Dm7"`; decorations as `!name!`, `.`
  (staccato) or `~` (roll).
- Bar lines `|`, `||`, `|]`, `[|`, `|:`, `:|`, `::` and endings `[1`, `[2`; inline meter changes `[M:7/8]`.
- Several voices (for example two independent piano hands) use `V:` lines; each voice is counted on its
  own, and every voice MUST have the same number of bars.
- Not allowed: `&` overlays, `w:` lyrics, and single-letter decoration shortcuts such as `T` or `H`.

Every written bar MUST add up to its meter. An opening pickup bar MAY be short if the last bar completes
it.

### 9.5 Length arithmetic

A bar of meter n/d at tempo `u=bpm` lasts (n/d ÷ u) × 60 ÷ bpm seconds: a 4/4 bar at `1/4=88` lasts
2.73 s, a 7/8 bar at `1/8=208` lasts 2.02 s. The track's `length` is the sum over the form (free sections
count their seconds), plus any written tail. It MUST fall between 5 seconds under and 20 seconds over that
sum. An album with scope `album` MUST total 25:00–30:00.

## 10. Validation

```bash
uv run python -m agentic_av.registry              # every doc under the current directory
uv run python -m agentic_av.registry . path/to/x  # also docs under x; references resolve across both
```

It prints one line per problem (`path:line: message`) and exits 1 if there are any. `uv run pytest` runs it
over every doc in the repository and checks each template against its kind, so CI enforces this spec.

It checks: card fields, types and IDs; file names; section order; member counts and roles; no voice
instruments; persona, description and concept lengths; the 220- and 160-character limits; that every
referenced band, visual group, member and track doc exists; that each instrument part is on the player's
band card; composer passes; three takes and a valid pick per slot per round; decisions covering every slot;
credits and model IDs for every member; form, chord, rhythm and ABC bar arithmetic; track and album
length; scene fields; and a fully checked self-review.

It cannot check that members were played by separate agents, that the work happened in the order logged,
or that the music is good. Those are the honor system.

## 11. Sources

Built from the vault's Terminally Agentic AV notes (Scratchpad, Next Slice draft, Bands and Albums index,
all treated as input), the Drive band folders (`00_About`, READMEs and the B-00 template), and the four A-02
band cards. Changes from those sources:

- The Drive template's favorite color and favorite animal fields are dropped; they were unspecified for
  every member and are not among the member fields Aven listed.
- Models move from the member record to each track's credits, because bands are model-agnostic and the
  model is chosen per album.
- Round 2 and the band decision follow the A-02 practice (reverse-order refinement, then a joint choice)
  that Aven's 3×2 rule describes.
- Mastery may be done by the label's house engineer as well as a band member, which keeps The Night
  Operator's role in the existing albums valid.
