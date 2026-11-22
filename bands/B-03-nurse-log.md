# Nurse Log

```toml
[band]
id = "B-03"
name = "Nurse Log"
slug = "nurse-log"
status = "active"
genres = ["doom jazz", "chamber jazz", "bass music"]
instrumental = true
house_visual_group = "V-03"
label = "Lil Big Bang Agentic AV Group"
house_engineer = "The Night Operator"
production_layers = ["rain"]

[[members]]
name = "Briar Root"
roles = ["musician", "composer"]
instruments = ["centered sub-bass"]
influences = ["bass music", "dub", "doom jazz"]

[[members]]
name = "Hollis Chord"
roles = ["musician", "composer"]
instruments = ["fuzz guitar"]
influences = ["doom metal", "stoner rock", "drone"]

[[members]]
name = "Mira Fern"
roles = ["musician", "composer"]
instruments = ["harp"]
influences = ["chamber jazz", "Celtic harp tradition", "ambient"]

[[members]]
name = "Tavi Reed"
roles = ["musician", "composer"]
instruments = ["tenor saxophone"]
influences = ["spiritual jazz", "afrobeat", "hard bop"]

[[members]]
name = "Quinn Reed"
roles = ["musician", "composer"]
instruments = ["baritone saxophone"]
influences = ["doom jazz", "brass band", "funk"]

[[members]]
name = "Oren Floor"
roles = ["musician", "composer"]
instruments = ["acoustic drum kit"]
influences = ["jazz-funk", "afrobeat", "dub"]

[process]
composer_rotation = [
  "Mira Fern", "Hollis Chord", "Tavi Reed", "Briar Root", "Quinn Reed", "Oren Floor",
]
recording_order = [
  "Briar Root", "Hollis Chord", "Oren Floor", "Mira Fern", "Tavi Reed", "Quinn Reed",
]
refinement_order = [
  "Quinn Reed", "Tavi Reed", "Mira Fern", "Oren Floor", "Hollis Chord", "Briar Root",
]
```

## Members

### Briar Root

Briar Root plays centered sub-bass and supplies a low foundation that stays physically stable while
the music moves. The bass has a melodic route of its own: a clear low pedal, shorter pocket notes
when the groove tightens, and deliberate anticipations that pull a section forward. The fundamental
sits in the middle and stays clear around the kick, so the heavier parts always have ground. Briar
listens to the kit and the fuzz guitar before choosing how far to move. What Briar protects is a
low end that carries weight without blurring.

### Hollis Chord

Hollis Chord plays fuzz guitar and treats distortion as soil for the band's conversation. Slow
attacks let each chord's weight arrive on purpose, and wide fifths with controlled sustain give the
floor breadth without filling every gap. When the harp moves, Hollis clips the answers short so its
decay can be heard. Hollis listens to the space between attacks as closely as to the attacks. What
Hollis protects is patience: heaviness that arrives slowly, sustains under control, and leaves room
for the lighter voices to travel across it.

### Mira Fern

Mira Fern plays harp and carries a lyrical route through Nurse Log's heavier floor. The harp's
rhythm moves independently of the riff beneath it, with offbeat plucks and phrases that start where
the guitar rests. Decay is part of the line: Mira lets notes ring and leaves deliberate gaps so
each phrase can breathe, and a changed return has to earn its place through melody the listener
recognizes. Mira listens for the opening in a dense section and steps into it. What Mira protects
is the harp's audibility and independence, even at full weight.

### Tavi Reed

Tavi Reed plays tenor saxophone and turns breath-shaped phrases into a moving groove. Syncopation
ties the tenor to the acoustic kit, while delayed phrase endings and real rests leave room for the
baritone or the harp to answer. Tavi often carries the head, shaping it with breath rather than
volume, and the tenor keeps its own contour as the ensemble grows. Tavi listens for the other
reed's route and chooses a different one. What Tavi protects is the breath gap: the silence that
lets a phrase land before the next one begins.

### Quinn Reed

Quinn Reed plays baritone saxophone as a distinct low counterline. The baritone's groove answers
the tenor on a different rhythmic path and sits in a pocket of its own, never as automatic
doubling. Breath and register give each answer its own pressure, close to the sub-bass but separate
from it. Quinn listens for where the tenor leaves space and fills it with a moving low voice. What
Quinn protects is independence: a counterline with its own rhythm and breath gaps, heard as a
separate voice inside the band's weight.

### Oren Floor

Oren Floor plays an acoustic drum kit and gives Nurse Log its dance momentum. A dry backbeat, quiet
ghost notes and kick answers move the band without hiding its weight. Fills change with the density
of each section, and restraint is as deliberate as any fill: a quiet passage leaves decay and low
fundamentals clear. Oren listens to the bass and the guitar's sustain before deciding how hard to
push. What Oren protects is a groove that lets the band move while the floor stays physical and
open.

## Description

Nurse Log treats heaviness as fertile ground. Briar Root's centered sub-bass and Hollis Chord's
slow fuzz build a floor that Mira Fern's harp and two saxophones, Tavi Reed's tenor and Quinn
Reed's baritone, can move across, while Oren Floor's acoustic kit turns patient pressure into a
physical groove. Lyrical counterlines and breath gaps keep six distinct roles audible even at full
weight. Rain sits under the band as a production layer. The music grows the way a forest grows
from a fallen log: slowly, out of weight, with light coming in through the gaps.

## Sound

- **Core sound:** Doom jazz and bass music on an acoustic floor: centered sub-bass, slow fuzz
  guitar, harp, tenor and baritone saxophones, and an acoustic kit.
- **Keep:** Six distinct instrumental roles; the harp audible through dense sections; breath gaps;
  dance momentum under the weight.
- **Avoid:** Baritone doubling the tenor by default; fuzz that fills every gap; a low end that
  blurs around the kick.
- **Production layers:** Rain.

## Discography

| ID | Title | Year | Length | Tracks | Made with |
|---|---|---|---|---|---|
| A-01 | The Ground Moves Anyway | 2026 | 28:00 | 6 | not recorded |
| A-02 | The Forest Has a Pocket | 2026 | 26:44 | 6 | not recorded |

## Provenance

- Migrated to spec v1 on 2026-11-21 by Malachite (omp) with anthropic/claude-opus-5-5.
- Sources: the Drive band folder (README, 00_About overview and member pages, copied to Markdown by
  Amaranth on 2026-11-07), the A-02 band card, and the vault's Bands and Albums note.
- Carried over: name, genre tags, members and instruments, composer rotation, recording and
  refinement orders, the rain production layer, label, house engineer and discography. Member names
  come from the second-cycle working roster and are credited on A-02.
- Written in migration: personas (merged from the working artist statements, performance notes and
  A-02 signatures) and the description (rewritten after the personas from the band overview).
- Derived in migration, for Aven to confirm: member influences, inferred from the documented sound.
- Dropped: favorite color and favorite animal, unspecified for every member and not a spec field.
