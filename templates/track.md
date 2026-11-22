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
