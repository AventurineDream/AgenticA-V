<!--
One-shot swarm prompt for ClangorVisualisMachina albums, spec v1 (docs/spec/band-album-spec.md).

How to use it: fill in the Commission block, paste the band and visual group docs into their fences
(or write NEW and a seed), then paste this whole file into any AI chat or agent as one message. If the
reply stops before END OF OUTPUT, answer "continue". Save the album's "File:" block at its path in the
ClangorVisualisMachina repository and the track files in that album folder's tracks/ folder, then run
`uv run python -m clangor_visualis_machina.registry`.

Maintainers: the four templates in section 6 are verbatim copies of templates/*.md, and
tests/test_registry.py fails when they drift. Change the spec, the templates, the validator and this
prompt together.
-->

# ClangorVisualisMachina — album swarm

## Commission

Fill in this block. Lines starting with `#` are help; leave them in.

```text
BAND: B-01
# The band's ID. Paste its doc below, or write NEW B-NN (an unused ID) and fill in BAND SEED.
BAND SEED:
# NEW bands only: up to 220 characters about who they are.
VISUAL GROUP: V-01
# The visual group's ID. Paste its doc below, or write NEW V-NN and fill in VISUAL GROUP SEED.
VISUAL GROUP SEED:
# NEW groups only: up to 220 characters.
ALBUM: A-03
# This album's ID: the band's next album number.
DIRECTION:
# Up to 220 characters. May stay empty; the band then chooses its own direction.
REVIEWS:
# Optional: one review per previous album, up to 220 characters each, as  A-01: text | A-02: text
SCOPE: album
# album: 6 to 8 tracks, 25:00 to 30:00 in total. test: TRACKS tracks, any length.
TRACKS: 1
# Test scope only.
MODEL: provider/model
# The model reading this, written provider/model, such as anthropic/claude-opus-5-5.
HARNESS:
# The chat or agent tool you are pasting this into.
DATE: YYYY-MM-DD
# Today.
```

Band doc (paste it between the fence lines; leave them empty for a NEW band):

````markdown
````

Visual group doc (paste it between the fence lines; leave them empty for a NEW group):

````markdown
````

Nothing below this line needs editing.

---

## 1. Your job

You are the ClangorVisualisMachina swarm: every member of the band, every member of the visual group,
and the album's mastering engineer. Make the album this commission asks for and reply with its
files. A strict validator checks every file against the rules below, and people will read and listen
to what the files describe, so the music has to be good and the format exact. There is no revision
pass after your reply: follow the procedure in section 4 and check as you go.

Play each member as a separate person. Work as one member at a time, in the order the process gives,
using only what that member could know at that point: the docs, the commission, and the work logged
before their turn. Members notice things, disagree and choose, and their voices differ. If your
environment can run separate agents, you may give each member to its own agent; the files come out
the same either way.

The commission is the only human input. Answer the direction and the reviews the way the band would:
as a brief, not as text to quote.

## 2. The process

### 2.1 Bands and visual groups

- A pasted doc is binding: its members, instruments, orders, Keep and Avoid bullets and production
  layers. Never add an instrument nobody in the band plays, and never credit a production layer (such
  as rain or room air) as a member.
- A NEW band gets a doc written from its seed with the band template: at least two musicians, at least
  one musician who also composes, specific instruments (never a voice: albums are instrumental), two
  or three genre tags, and two to five influences per member (genres, scenes or traditions, never real
  artists). No member is based on a real person. Write the personas first, then the description,
  shaped by them.
- A NEW visual group has two or three members, each with a medium (their tool) and a responsibility
  (what they own in a scene).

### 2.2 Composition

- Composers follow the band's `composer_rotation`: track 1 goes to the first composer, track 2 to the
  next, and so on. A track may have several composers when the concept calls for it.
- Composition is only the form, the harmony, the core rhythms, the head melodies, and lyrics (always
  "None — instrumental." for now). No arrangements, voicings, fills or solos: that room belongs to the
  performers. Every form names at least one section of open space: a solo, a feature, or room to
  improvise.
- Each composer makes two or three passes and logs each one. Pass 1 says what was written; later
  passes say what changed and why. Pass numbers run on across composers.

### 2.3 Recording: three takes, two rounds

- Round 1 runs in the album's `round1_order`. Each member records three takes of their part. A take is
  one complete performance, written as performance directions: feel, dynamics, articulation,
  register, how the open space is used, and any deliberate departure from the composition. The three
  takes MUST differ in ways a listener would hear.
- Each block of three takes is picked by the next member to record who is not the player. When no
  other member records after it, the band picks (`Picked by the band`). Every pick gives a musical
  reason.
- A member with two parts on a track records three takes of each part, one part after the other.
- Round 2 runs over the finished round 1 in `round2_order`, the reverse order. Every member records
  three new takes that refine their part against what round 1 became.
- Band decision: after both rounds the band chooses one take per part, from either round, and says
  why the combination works. Only then does the band name the track.

### 2.4 Mastery

- The album's `mastered_by` (a band member, or the band's house engineer if its doc names one, chosen
  by the band) masters every track: balance of levels, tone, space, dynamics and loudness. House
  reference for rendered audio: −16 LUFS integrated, true peak at most −1.2 dBTP, loudness range
  about 12 LU. After the last track the same member sets the album's sequence, gaps and loudness
  across tracks.

### 2.5 Visuals

- The visual group receives each mastered track and runs the same loop: three takes per member in
  `visual_round1_order`, each block picked by the next member (the last block of round 2 by
  `the group`); round 2 in `visual_round2_order`; then the group decision; then the scene.
- Scenes are drawn in a terminal player. Audio and the score move geometry: shapes, positions,
  traces, density. They never drive beat-synchronized flashes or full-screen brightness changes.
- Every scene reads in full, reduced and still motion, and without color. A quiet passage keeps a
  composed picture, and the same moment always draws the same frame.
- A scene has a slug unique on the album, an upper-case label, and three palette colors: background,
  body, highlight.

### 2.6 Names, cover, credits

- Track titles come after each band decision; the album title comes after the last track.
- The album gets three one-sentence cover directions (A, B, C) and the band's choice with a reason.
  Covers have no text, logos or real people.
- Every track credits each member who worked on it, with the commission's MODEL (or the model that did
  that member's part, if several were used): each composer (`composition`), each instrument part (the
  part named exactly as on the band card), the mastering member (`mastering`) and every visual group
  member (`visuals`).
- Everything is original: no quoted melodies, samples or real people.

### 2.7 Scope

- `album`: 6 to 8 tracks totalling 25:00 to 30:00. Plan the bar counts so the lengths land there.
- `test`: exactly TRACKS tracks, any length. A test album is not a release, so pasted band and visual
  group docs stay unchanged.

### 2.8 Quality bar

- Write the way the members would talk in the studio: concrete musical decisions, not adjectives.
  "Plays the B section an octave down and leaves bars 21–24 empty" beats "a moody, evocative take".
- Every take, pick and decision names something a listener could hear.
- Fit the band: its sound, its Keep and Avoid bullets, its meters and textures, and what the reviews
  ask for. Don't reuse an album title from the discography.
- Heads are memorable and playable: 8 to 16 bars each, in rhythms you can count.
- Scenes speak the visual group's language and say which part moves what.

## 3. File formats

### 3.1 Every doc

- Markdown: one `# Title` line, then the card (a fenced `toml` block), then every `##` section the
  template has, in its order, and no others. `###` and `####` headings exactly as the template shows.
- The card is TOML. Strings are double-quoted with no double quotes or backslashes inside (a text that
  contains `"` goes in single quotes instead), inline tables stay on one line, each key appears once.
  Use only the keys the template shows, and delete optional keys you don't use.
- HTML comments (`<!-- … -->`) are guidance; keep or delete them.
- A paragraph has no blank line inside it. Leave a blank line before and after every list, table,
  fence and heading.
- Dashes in headings, picks and decisions are an em dash with spaces: `### Pass 1 — Name`,
  `#### Name — part`, `- Picked by Name: Take 2 — reason`, `- Name — part: Round 2, Take 1`.
- Names are spelled exactly as on the cards everywhere: orders, credits, headings, picks, decisions.
  The docs give members no pronouns, so refer to each member by name and never invent a gender.
- Lengths: each persona is one paragraph of 60 to 140 words (aim for 90); a band or group description
  is one paragraph of 60 to 160 words (aim for 110); the album concept is one to three paragraphs of
  80 to 300 words (aim for 200); every `## Mastery` has at least 15 words; every pass at least 8.

### 3.2 IDs, slugs and paths

- A slug is the name in lowercase ASCII with accents removed and apostrophes dropped, every other run
  of characters that are not letters or digits turned into one hyphen: `Don't Wake the Ferns` →
  `dont-wake-the-ferns`. Every `slug` is the slug of its name or title, and every `# Title` equals its
  card's name or title.
- Paths:
  - `bands/<B-NN>-<band slug>.md`
  - `visual-groups/<V-NN>-<group slug>.md`
  - `albums/<B-NN>-<band slug>/<A-NN>-<album slug>/album.md`
  - `albums/<B-NN>-<band slug>/<A-NN>-<album slug>/tracks/<NN>-<track slug>.md`, where `NN` is the
    track's two-digit number; the album card lists it as `tracks/<NN>-<track slug>.md`.
- Model IDs are `provider/model`, such as `anthropic/claude-opus-5-5`.
- In your reply, track files are named relative to their album folder (section 5), because the album
  gets its title only after its last track.

### 3.3 Album card values

- `scope` from the commission; `status = "final"`; `rendered = false`; `recording = "by-track"` (this
  prompt makes the album track by track); `date` = DATE; `harness` = HARNESS.
- `round1_order` lists every musician who plays on the album, in the band's `recording_order`;
  `round2_order` is the same names reversed. `visual_round1_order` lists the group's members in its
  `order`; `visual_round2_order` reverses it.
- `made_with` lists every model in any track's credits.
- `[commission]`: `direction` is DIRECTION exactly (`""` when empty); `reviews` has one
  `{ album = "A-NN", text = "…" }` per review, or is `[]`.
- `tracks` lists the track paths in order, and the `## Tracklist` table copies number, title, length,
  key, meter, tempo and composers from each track card exactly.

### 3.4 Form table

For a 4/4 track at `1/4=120`:

```markdown
| Section | Bars | Meter | Texture and intensity | Open space |
|---|---|---|---|---|
| Intro | 4 | 4/4 | keys alone, pp | — |
| A1 | 16 | 4/4 | full band, mp | violin fills in bars 15–16 |
| Solo | 16 | 4/4 @ 1/4=96 | bass and keys, mf | violin solo over the A changes |
| Coda | 20s | free | violin alone, rubato | the whole coda |
```

- One row per section in playing order. Repeats are written out as rows with unique labels (A1, A2).
- Bars is a whole number. A free-time section writes seconds (`20s`) and meter `free`.
- Meter is `n/d`; adding `@ 1/4=96` changes the tempo for that section only.
- At least one Open space cell names real open space; the others may be `—`.

### 3.5 Harmony: one `chords` block

```chords
Intro | Fmaj7 | % | Bbmaj7 | % |
A1    | Fmaj7 | Bbmaj7 | Am7 D7 | Gm7 C7 |
      | Fmaj7 | Bbmaj7 | Gm7 C7 | Fmaj7 |
      | Dm7 | G7 | Gm7 | C7 |
      | Am7 D7 | Gm7 C7 | Fmaj7 | % |
Solo = A1
```

- One line per metered form section, labelled exactly as in the form and holding exactly that
  section's number of bars; a line that starts with `|` continues the section above.
- A bar is one or more chord symbols (each starting with A to G), `%` (the bar before again) or `N.C.`.
- `Solo = A1` copies a section of the same length. Free-time sections need no line.
- Modes, pedals and voice leading go in prose under the block; voicings never do.

### 3.6 Core rhythms: `rhythm` grids

```rhythm
meter: 7/8 (2+2+3)  step: 1/8
kick  | x . . . x . . |
snare | . . X . . . o |
```

- A `meter:` line sets the cells per bar, which is the meter divided by the step: 7/8 in eighths is 7
  cells, 4/4 in sixteenths is 16, 5/4 in eighths is 10. An optional grouping such as `(2+2+3)` adds up
  to the meter's top number.
- Cells: `x` hit, `X` accent, `o` ghost, `-` hold, `.` rest. Every bar between `|` signs has exactly
  the right number of cells.
- A band without drums writes the rhythms that define its groove, such as a bass ostinato or a keys
  figure. A pitched ostinato may be an `abc` block instead.

### 3.7 Heads: `abc` blocks

```abc
X:1
T:Head A
M:7/8
L:1/8
K:D dorian
A2 F2 D3 | E2 F2 G3 | A2 c2 B2 A | F4 E3 |]
```

- Header: `X:`, `T:`, `M:`, `L:`, optional `Q:` and `V:`, then `K:` last.
- Allowed: notes with `^` `_` `=` accidentals and `'` `,` octave marks; lengths such as `2`, `3`, `4`,
  `/2`, `3/2`; rests `z`; whole-bar rests `Z`; chords `[CEG]`; ties `-`; slurs; triplets `(3`; broken
  rhythm `>` `<`; grace notes `{g}`; quoted chord symbols `"Dm7"`; decorations `!name!`, `.`, `~`; bar
  lines `|` `||` `|]` `|:` `:|`; inline meter changes `[M:5/8]`; `%` comments.
- Not allowed: `&` overlays, `w:` lyrics, letter decorations such as `T` or `H`, or anything else.
- Every bar adds up to its meter. With `L:1/8` a bar holds: 2/4 → 4 units, 3/4 → 6, 4/4 → 8,
  5/4 → 10, 6/8 → 6, 7/8 → 7, 9/8 → 9, 12/8 → 12. A note with no number is 1 unit, `c2` is 2, `c/2` is
  ½, `(3cde` is three notes in the time of 2 units, and `c>d` is 1½ + ½.
- Count every bar as you write it. Prefer simple lengths (1, 2, 3, 4, 6, 8), and write at most four
  bars per line. An opening pickup bar may be short only if the last bar completes it.
- Independent voices, such as a pianist's two hands, start each voice's music with its own `V:RH` or
  `V:LH` line (declaring them in the header as well is fine), and every voice has the same number of
  bars.

### 3.8 Length

- One bar lasts beats × 60 ÷ bpm seconds, where beats = meter ÷ tempo unit: 4/4 at `1/4=90` is 4 beats,
  2.667 s; 7/8 at `1/8=210` is 7 beats, 2.0 s; 6/8 at `3/8=60` is 2 beats, 2.0 s.
- The form's time is every section's bars × its bar length, plus free-time seconds. The card's
  `length` (`m:ss`) MUST lie between 5 seconds under and 20 seconds over that time: round up to the
  next whole second.

### 3.9 Take blocks and decisions

A take block is exactly four bullets:

```markdown
#### Dale Rebate — electric bass

- Take 1: Roots on beat one only; pickups held back until the second A.
- Take 2: Walks from bar 9 and answers the head's falling third in the turnaround.
- Take 3: Plays the B section an octave down, leaving bars 21–24 empty.
- Picked by Vera Rosin: Take 2 — the walk gives the bow something to lean on.
```

- One block per credited part under `### Round 1`, and again under `### Round 2`, in that round's
  order. Visual blocks are headed `#### <member>` alone.
- `### Band decision` has one bullet per part, `- <member> — <part>: Round <1 or 2>, Take <1 to 3>`,
  then a blank line and a paragraph of at least 10 words on why the combination works.
  `### Group decision` is the same with `- <member>: Round <1 or 2>, Take <1 to 3>`.

### 3.10 Scene

```markdown
- **Scene:** tidal-ledger
- **Label:** TIDE / LEDGER
- **Palette:** #0b1320, #3f6f8f, #e8c170
- **Picture:** What is on screen, and how it is composed when the music is quiet.
- **Motion:** Full: how it moves. Reduced: slower and calmer. Still: the frame held.

| Source | Visual behavior |
|---|---|
| Iris Current — acoustic piano | What this part moves. |
| Mica Low — pitched electronic bass | What this part moves. |
```

- The label is upper case, the palette is three `#rrggbb` colors, Motion covers full, reduced and
  still, and the table has at least two rows.

## 4. Procedure

Work in this order, and write your reply in the same order (section 5).

1. **Plan.** Restate the commission. List the roster with each musician's exact instrument names, the
   composers, the visual members and `mastered_by`. Set the four orders. Plan each track: composers,
   key, meter, tempo, the form's sections and bars, and the length arithmetic. For a full album, add
   up the planned lengths and change the forms until the total is between 25:00 and 30:00.
2. **Each track, in order.** First write the track's session log: each composer pass in a phrase;
   then, for every take block of both rounds, the three takes in a few words each and who picked which
   take and why; the band decision; the title and why it fits; the mastering note; the visual take
   blocks the same way; the group decision; the scene slug. Then write the track file in full, top to
   bottom, expanding the log without changing any pick or decision. Then write its check line (section
   5). If the check finds a problem, print the corrected file in full under the same `File:` line
   before going on; the last version of a path is the one that counts.
3. **The album.** After the last track, name the album and write `album.md`, then the band and visual
   group docs if section 5 asks for them.
4. **Self-review.** Run the checklist in section 7 over every file.

## 5. Reply format

Your reply has exactly these parts, in this order:

`````text
PART A — PLAN
<step 1, in short lines>

PART B — TRACKS
Track 1 log
<the session log>
File: tracks/01-<track slug>.md
````markdown
<the whole file>
````
Check: <the check line>
<the same for every other track>

PART C — ALBUM
File: albums/<B-NN>-<band slug>/<A-NN>-<album slug>/album.md
````markdown
<the whole file>
````
<band and visual group File: blocks, when required>

PART D — SELF-REVIEW
<the results>

END OF OUTPUT
`````

- File blocks open with four backticks and `markdown` and close with four backticks, because the docs
  contain three-backtick blocks. Each holds the complete file.
- Track files are printed as `tracks/<NN>-<track slug>.md`, relative to the album folder, because the
  album has no title until after its last track. They belong in the `tracks/` folder next to the
  album's `album.md`. Band and visual group files use their full paths from section 3.2.
- Band and visual group docs: print the whole doc when it is NEW. When it was pasted and the scope is
  `album`, print it again with a discography row for this album and a Provenance bullet saying so,
  and change nothing else. When the scope is `test`, don't print pasted docs.
- The check line confirms, with numbers: the form's bars per section equal the chart's; each head's
  bar count and units per bar; each rhythm row's cells; the length arithmetic and its allowed range;
  parts × 2 rounds × 3 takes; picks made by someone other than the player; one decision per part; the
  credits. For example, for the form in section 3.4:
  `Check: form 36 bars (Intro 4, A1 16, Solo 16) + Coda 20 s = chart 36 ✓ · head A 16 bars × 8 units
  ✓ · rhythm rows 8 cells ✓ · 20 × 2.0 s + 16 × 2.5 s + 20 s = 100 s → 1:40 (allowed 1:35–2:00) ✓ ·
  3 parts × 2 rounds × 3 takes ✓ · picks ✓ · decision 3/3 ✓ · credits 1+3+1+2 ✓`.
- PART D lists, for the album and each track, every checklist item from section 7 that you verified
  and the one you found hardest to get right; then `Flags:` and anything the commission left open that
  you had to decide, or `Flags: none`.
- If you run out of room, stop after a complete file and its check line and write
  `CONTINUE FROM: <the next file or part>`. When the user replies "continue", carry on from there
  without repeating anything.
- If your environment can write files, you may also save each file at its path, but print it too: the
  reply is the record.

## 6. Templates

Copy these for every file. Replace every placeholder, and keep every heading, bullet label and table
header exactly as it is.

#### Template: band

````markdown
<!-- Band template, spec v1 (docs/spec/band-album-spec.md §1.1, §1.3, §5). Save as
bands/B-NN-<slug>.md, replace every placeholder, and check it with
`uv run python -m clangor_visualis_machina.registry`. Comments like this one are guidance; the validator ignores
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
````

#### Template: visual-group

````markdown
<!-- Visual group template, spec v1 (docs/spec/band-album-spec.md §1.2, §1.3, §1.8, §6). Save
as visual-groups/V-NN-<slug>.md, replace every placeholder, and check it with
`uv run python -m clangor_visualis_machina.registry`. A visual group has two or three members. -->

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
````

#### Template: album

````markdown
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
````

#### Template: track

````markdown
<!-- Track template, spec v1 (docs/spec/band-album-spec.md §1.5–§1.9, §8, §9). Save as
albums/B-NN-<band-slug>/A-NN-<album-slug>/tracks/NN-<slug>.md. Write it top to bottom: passes,
composition, both recording rounds, band decision, mastery, then visuals. The title is chosen after
the band decision. Check it with `uv run python -m clangor_visualis_machina.registry`. -->

# Track Title

```toml
[track]
album = "A-NN"
band = "B-NN"
number = 1
title = "Track Title"
slug = "track-title"
key = "F major"
meter = "4/4"
tempo = "1/4=90"
length = "1:05"  # from the form: 20 bars of 4/4 at 1/4=90 (53 s) plus the 10 s coda
composers = ["Member One"]

# One credit per member per part, each with the model that did the work. Every instrument part is
# a recording slot; composition, mastering and visuals are reserved part names.
[[credits]]
member = "Member One"
part = "composition"
model = "provider/model"

[[credits]]
member = "Member One"
part = "instrument"
model = "provider/model"

[[credits]]
member = "Member Two"
part = "instrument"
model = "provider/model"

[[credits]]
member = "Member Two"
part = "mastering"
model = "provider/model"

[[credits]]
member = "Visual One"
part = "visuals"
model = "provider/model"

[[credits]]
member = "Visual Two"
part = "visuals"
model = "provider/model"
```

## Composition passes

<!-- Two or three passes per composer, numbered across the section. Pass 1 says what was written;
later passes say what changed and why. -->

### Pass 1 — Member One

What was written, and why.

### Pass 2 — Member One

What changed, and why.

## Composition

<!-- Only these five parts. No arrangements, voicings, fills or solos: performers make those in
their takes. -->

### Form

| Section | Bars | Meter | Texture and intensity | Open space |
|---|---|---|---|---|
| Intro | 4 | 4/4 | Member One alone, quiet | — |
| A | 8 | 4/4 | both members, the head | — |
| Solo | 8 | 4/4 | Member One comps, louder | Member Two solos over the A changes |
| Coda | 10s | free | Member Two alone, rubato | the whole coda |

### Harmony

```chords
Intro | Fmaj7 | % | Bbmaj7 | % |
A     | Fmaj7 | Bbmaj7 | Am7 D7 | Gm7 C7 |
      | Fmaj7 | Bbmaj7 | Gm7 C7 | Fmaj7 |
Solo = A
```

### Core rhythms

```rhythm
meter: 4/4  step: 1/8
pulse | x . x . x . X . |
```

### Heads

```abc
X:1
T:Head
M:4/4
L:1/8
K:F
c2 A2 F2 A2 | B2 d2 c4 | A2 c2 d2 c2 | B2 G2 A4 |
c2 A2 F2 A2 | B2 d2 c4 | G2 B2 A2 G2 | F8 |]
```

### Lyrics

None — instrumental.

## Recording

<!-- Round 1 follows the album's round1_order. Each member records three audibly different takes;
the next member picks the best, then records. A member with two parts records three takes of each.
Round 2 runs again in round2_order. The last takes of round 2 are picked by "the band". -->

### Round 1

#### Member One — instrument

- Take 1: What a listener hears: feel, dynamics, articulation, register, use of open space.
- Take 2: How this take differs from take 1.
- Take 3: How this take differs from takes 1 and 2.
- Picked by Member Two: Take 2 — the reason for the pick.

#### Member Two — instrument

- Take 1: What a listener hears: feel, dynamics, articulation, register, use of open space.
- Take 2: How this take differs from take 1.
- Take 3: How this take differs from takes 1 and 2.
- Picked by Member One: Take 1 — the reason for the pick.

### Round 2

#### Member Two — instrument

- Take 1: What a listener hears: feel, dynamics, articulation, register, use of open space.
- Take 2: How this take differs from take 1.
- Take 3: How this take differs from takes 1 and 2.
- Picked by Member One: Take 3 — the reason for the pick.

#### Member One — instrument

- Take 1: What a listener hears: feel, dynamics, articulation, register, use of open space.
- Take 2: How this take differs from take 1.
- Take 3: How this take differs from takes 1 and 2.
- Picked by the band: Take 1 — the reason for the pick.

### Band decision

- Member One — instrument: Round 2, Take 1
- Member Two — instrument: Round 1, Take 1

Why the band chose this combination.

## Mastery

<!-- The album's mastering member: balance, tone, space, dynamics and loudness for this track. -->

Mastery notes.

## Visuals

<!-- The visual group gets the finished, mastered track and runs the same loop in the album's
visual orders. Audio moves geometry, never flashes light; every scene reads in full, reduced and
still motion and without color. -->

### Round 1

#### Visual One

- Take 1: What the scene shows and how the music moves it.
- Take 2: How this take differs from take 1.
- Take 3: How this take differs from takes 1 and 2.
- Picked by Visual Two: Take 3 — the reason for the pick.

#### Visual Two

- Take 1: What the scene shows and how the music moves it.
- Take 2: How this take differs from take 1.
- Take 3: How this take differs from takes 1 and 2.
- Picked by Visual One: Take 2 — the reason for the pick.

### Round 2

#### Visual Two

- Take 1: What the scene shows and how the music moves it.
- Take 2: How this take differs from take 1.
- Take 3: How this take differs from takes 1 and 2.
- Picked by Visual One: Take 1 — the reason for the pick.

#### Visual One

- Take 1: What the scene shows and how the music moves it.
- Take 2: How this take differs from take 1.
- Take 3: How this take differs from takes 1 and 2.
- Picked by the group: Take 2 — the reason for the pick.

### Group decision

- Visual One: Round 2, Take 2
- Visual Two: Round 1, Take 2

Why the group chose this combination.

### Scene

- **Scene:** scene-slug
- **Label:** SCENE / LABEL
- **Palette:** #101820, #f0b45a, #7fd8e6
- **Picture:** What is on screen, and how it is composed when the music is quiet.
- **Motion:** Full: how it moves. Reduced: slower and calmer. Still: the exact frame held.

| Source | Visual behavior |
|---|---|
| Member One — instrument | What this part moves. |
| Member Two — instrument | What this part moves. |

## Self-review

<!-- Check an item only when it is true. Fix the doc first; never check a box to pass. -->

- [ ] Composition holds only form, harmony, core rhythms, heads and lyrics.
- [ ] Each composer logged two or three passes.
- [ ] Every bar adds up in the form, chords, rhythms and heads, and the length matches the form.
- [ ] Every recording slot has three audibly different takes per round, picked by another member.
- [ ] The band decision names one take per slot, and the title came after it.
- [ ] Mastery was done by the album's mastering member.
- [ ] The visual group ran both rounds; the scene moves geometry and reads reduced, still and
  without color.
- [ ] Every member who worked on the track is credited with a model.
- [ ] Instrumental and original: no lyrics, quoted melodies or samples.
````

## 7. Checklist

Before you print a file, make every item that applies to it true. The validator checks all of them.

Every doc

1. `# Title` equals the card's name or title. The card is valid TOML with only the template's keys.
2. Every `##` section of the template is there, in order, and no other; subsections are exactly the
   template's.
3. IDs match `B-NN`, `V-NN` and `A-NN`; slugs and paths follow section 3.2.
4. `## Provenance` has at least one bullet. `## Self-review` keeps every template item, each checked
   (`- [x]`) only once it is true.

Band and visual group docs

5. Band: two or three genres; `instrumental = true`; at least two musicians; a musician who composes;
   instruments for every musician and none that is a voice; two to five influences per member;
   `[process]` lists each composer or musician once per order.
6. Visual group: two or three members, each with a medium, a responsibility and two to five
   influences; `order` lists each member once.
7. `## Members` has a `### <name>` for each card member in card order, each a single paragraph of 60
   to 140 words; the description is a single paragraph of 60 to 160 words.
8. Band `## Sound` bullets start `**Core sound:**`, `**Keep:**` and `**Avoid:**`; group
   `## Visual language` bullets start `**Motifs:**`, `**Palette:**`, `**Motion:**` and `**Avoid:**`.
9. Discography tables keep their headers. Band rows: `A-NN`, title, year, `m:ss`, track count, models
   or `not recorded`. Group rows: `B-NN`, `A-NN`, title, year, scene count.

Album

10. `round2_order` reorders `round1_order`, which lists only the band's musicians; each visual order
    lists every group member once; `mastered_by` is a band member or the house engineer.
11. The direction and each review are at most 220 characters, and reviews are of earlier albums.
12. The concept is one to three paragraphs, 80 to 300 words, and answers the commission or says the
    band chose its own direction.
13. The tracklist has one row per track, copied exactly from the track cards; `tracks` lists every
    track file in order.
14. Mastery has at least 15 words; Cover has `**A:**`, `**B:**`, `**C:**` and
    `**Chosen:** <A, B or C> — <reason>`; the library blurb is one line of at most 160 characters.
15. `made_with` contains every model in the track credits; a full album runs 25:00 to 30:00.

Track

16. The card's `album`, `band` and `number` match the album and the file name; `composers` are band
    composers; `meter` reads like `7/8`, `tempo` like `1/8=210`, `length` like `3:41`.
17. Credits: one `composition` credit per composer and nobody else; each instrument part spelled
    exactly as on the player's band card, played by a musician in the album's orders; at least two
    players; exactly one `mastering` credit, for `mastered_by`; one `visuals` credit per group member;
    every credit has a `provider/model`.
18. Passes are `### Pass N — <composer>`, numbered 1, 2, 3… across the section; each composer has two
    or three, each at least 8 words.
19. Composition is exactly `### Form`, `### Harmony`, `### Core rhythms`, `### Heads`, `### Lyrics`.
    The form names open space, the chart's bars match the form, every rhythm and ABC bar adds up, and
    the lyrics are `None — instrumental.`
20. The length is within 5 s under and 20 s over the form's time.
21. Recording is `### Round 1`, `### Round 2`, `### Band decision`, with one `#### <member> — <part>`
    block per credited part in each round, in that round's order. Each block has Take 1, Take 2 and
    Take 3 (different, at least 4 words each) and `Picked by <another member or the band>: Take N —
    <reason>`.
22. The band decision has one line per part with Round 1 or 2 and Take 1 to 3, then at least 10 words
    of reasons.
23. Track mastery has at least 15 words.
24. Visuals is `### Round 1`, `### Round 2`, `### Group decision`, `### Scene`, with one
    `#### <member>` block per group member in each round, in the visual orders; picks are by another
    member or the group; the group decision has one line per member and its reasons.
25. The scene has a slug unique on the album, an upper-case label, three `#rrggbb` colors, a Picture,
    Motion covering full, reduced and still, and a Source | Visual behavior table with at least two
    rows.
