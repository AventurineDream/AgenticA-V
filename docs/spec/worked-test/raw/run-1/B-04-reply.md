PART A — PLAN

- Commission: band B-04 Quiet Machinery, visual group V-04 Quiet Machinery House Visuals, album A-03.
- Direction: a night shift at an observatory where the instruments begin measuring each other. The music is slow and exact at first and warmer by the last bar.
- Reviews: none. Scope: test, 1 track. Model: anthropic/claude-opus-5-5. Harness: omp eval completion(), one stateless message with no tools. Date: 2026-11-21.
- Roster:
  - Noor Low: centered sub-bass
  - Calder Mallet: saturated marimba
  - Vela Ring: vibraphone
  - Rook Ground: acoustic percussion
  - Merrit Reed: clarinet
  - Sela Air: flute
  - Room air is a production layer, not a member.
- Composer for track 1 (first in composer_rotation): Calder Mallet.
- Visual members: Surveyor Null, Copper Measure.
- mastered_by: The Night Operator, the band's house engineer.
- Orders:
  - round1_order: Noor Low, Calder Mallet, Vela Ring, Rook Ground, Merrit Reed, Sela Air
  - round2_order: Sela Air, Merrit Reed, Rook Ground, Vela Ring, Calder Mallet, Noor Low
  - visual_round1_order: Surveyor Null, Copper Measure
  - visual_round2_order: Copper Measure, Surveyor Null
- Track 1 plan:
  - Composer Calder Mallet, D dorian, 7/8 (3+2+2) at 1/8=140, so one bar = 7 × 60 ÷ 140 = 3.0 s.
  - Form: Intro 8, A1 12, A2 12, B 8, Feature 16, A3 12, Coda 30 s free.
  - Length: 68 bars × 3.0 s = 204 s, plus 30 s = 234 s → 3:54 (allowed 3:49–4:14).
- Test scope, so the pasted band and visual group docs are not reprinted.

PART B — TRACKS

Track 1 log

**Composition passes**
- Pass 1 (Calder Mallet): the 7/8 cell A–F–D–E, Head A (12 bars), form Intro/A1/A2/B/A3 and the chart.
- Pass 2 (Calder Mallet): adds the 16-bar Feature as open space and changes bar 8's last note from E to F. Adds Head B in long tones because Head A was all clipped.
- Pass 3 (Calder Mallet): A3's last two bars become G13 → Dmaj9 so the warmth lands only in the last bar. Adds the 30 s free coda.

**Round 1**
- Noor Low: T1 roots only; T2 the written ostinato with a fifth on eighth 6; T3 the ostinato everywhere with a swell. Calder Mallet picks T2: the fifth falls into the marimba's rest.
- Calder Mallet: T1 exact, rests empty; T2 intro drift and A2 up an octave; T3 rolls and pickups. Vela Ring picks T1: the empty rests give the bell decay somewhere to land.
- Vela Ring: T1 motor off, pedal held; T2 a one-bar-late canon, B arc and ringing Feature phrases; T3 four-mallet pads and a 16-bar solo. Rook Ground picks T2: the canon gives a second set of attacks to measure against.
- Rook Ground: T1 downbeats only; T2 layers that grow with the form and a woodblock fill at B bar 8; T3 dense from bar 1. Merrit Reed picks T2: the pulse thickens without getting louder.
- Merrit Reed: T1 a one-note-per-bar descent in A2; T2 Feature trades measured to the ring and an A3 descent; T3 continuous chalumeau. Sela Air picks T2: the top register stays open.
- Sela Air: T1 two notes at A2 bars 11–12 only; T2 late counterlines in B and a held note in the coda; T3 flutter answers and an A3 line. Merrit Reed picks T1: the room stays exact longer.

**Round 2**
- Sela Air: T1 adds coda breaths; T2 adds a rise in A3 bars 9–12 onto A; T3 three entries. Merrit Reed picks T2: her rise crosses his descent.
- Merrit Reed: T1 two-bar trades; T2 the descent moved to bars 10–12 plus breath tails; T3 clarion register. Rook Ground picks T2: his low D lands with the flute's A.
- Rook Ground: T1 rim taps in the Feature; T2 drops out for Feature bars 13–16; T3 T2 plus a struck bowl at A3 bar 12. Vela Ring picks T3: the bowl rings with her Dmaj9.
- Vela Ring: T1 motor on in A3; T2 motor on for the last chord only; T3 a half-bar canon. Calder Mallet picks T2: that one gesture is the direction.
- Calder Mallet: T1 adds the intro drift; T2 adds yarn mallets in A3; T3 drops bar 12's D. Noor Low picks T2: the softer attack meets the fifths.
- Noor Low: T1 sparser in the Feature; T2 holds the D under the Dmaj9; T3 a late entry. The band picks T2.

**Band decision:** all six parts take Round 2 picks: Noor R2T2, Calder R2T2, Vela R2T2, Rook R2T3, Merrit R2T2, Sela R2T2.

**Title:** "Measured in Ring". The clarinet measures its phrases by the vibraphone's ring, and the last bar is warmed by a ring, the vibraphone motor.

**Mastery:** The Night Operator keeps the bass mono, opens the canon left and right, leaves the decay uncompressed, and lets room air carry the coda. Targets: −16 LUFS, −1.2 dBTP, about 12 LU.

**Visuals, Round 1**
- Surveyor Null: T1 a dome slit; T2 six gauge arcs reading each other; T3 one horizontal scale. Copper Measure picks T2.
- Copper Measure: T1 fixed-fade dots; T2 traces as long as the ring and the slit opening on the last chord; T3 a density map. Surveyor Null picks T2.

**Visuals, Round 2**
- Copper Measure: T1 one-way lines; T2 a clocked slit opening; T3 copper held back until A3. Surveyor Null picks T3.
- Surveyor Null: T1 rotating arcs; T2 fixed arcs with pitch needles and section crosses; T3 T2 with held rests and a bare frame in Feature bars 13–16. The group picks T3.

**Group decision:** Surveyor Null R2T3, Copper Measure R2T3.

**Scene:** meridian-gauges.

File: albums/B-04-quiet-machinery/A-03-readings-under-the-turning-dome/tracks/01-measured-in-ring.md
````markdown
# Measured in Ring

```toml
[track]
album = "A-03"
band = "B-04"
number = 1
title = "Measured in Ring"
slug = "measured-in-ring"
key = "D dorian"
meter = "7/8"
tempo = "1/8=140"
length = "3:54"  # from the form: 68 bars of 7/8 at 1/8=140 (204 s) plus the 30 s coda
composers = ["Calder Mallet"]

[[credits]]
member = "Calder Mallet"
part = "composition"
model = "anthropic/claude-opus-5-5"

[[credits]]
member = "Noor Low"
part = "centered sub-bass"
model = "anthropic/claude-opus-5-5"

[[credits]]
member = "Calder Mallet"
part = "saturated marimba"
model = "anthropic/claude-opus-5-5"

[[credits]]
member = "Vela Ring"
part = "vibraphone"
model = "anthropic/claude-opus-5-5"

[[credits]]
member = "Rook Ground"
part = "acoustic percussion"
model = "anthropic/claude-opus-5-5"

[[credits]]
member = "Merrit Reed"
part = "clarinet"
model = "anthropic/claude-opus-5-5"

[[credits]]
member = "Sela Air"
part = "flute"
model = "anthropic/claude-opus-5-5"

[[credits]]
member = "The Night Operator"
part = "mastering"
model = "anthropic/claude-opus-5-5"

[[credits]]
member = "Surveyor Null"
part = "visuals"
model = "anthropic/claude-opus-5-5"

[[credits]]
member = "Copper Measure"
part = "visuals"
model = "anthropic/claude-opus-5-5"
```

## Composition passes

### Pass 1 — Calder Mallet

Wrote the reference cell in 7/8 grouped 3+2+2 at 1/8=140, three seconds a bar so every attack can be counted. The cell is A falling to F and D, then stepping back up to E, refitted to each chord. Head A is twelve bars of that cell, with the second bar of each pair clipped to a rest. The form is Intro, A1, A2, B and A3 in D dorian, with only Dm9 and Em7 for the first sixteen bars.

### Pass 2 — Calder Mallet

The form had nowhere for the instruments to measure each other, so I added a sixteen-bar Feature over the A changes plus a four-bar turnaround as open space for vibraphone and clarinet. I changed the last note of Head A bar 8 from E to F, one altered interval so the second statement reads differently. Head A was all clipped attacks, so I wrote Head B as eight bars of long tones over G13 to A7 for notes that ring.

### Pass 3 — Calder Mallet

A3 was arriving warm too early, so its last two bars now go G13 to Dmaj9: the only major tonic in the piece, held back to the final bar. I added a thirty-second free coda so that chord can decay into room air instead of being cut off. I left A2 bars 11 and 12 open for a wind entry.

## Composition

### Form

| Section | Bars | Meter | Texture and intensity | Open space |
|---|---|---|---|---|
| Intro | 8 | 7/8 | the reference cell alone, pp | — |
| A1 | 12 | 7/8 | Head A over the sub-bass floor, p | — |
| A2 | 12 | 7/8 | Head A restated, mp | bars 11–12 left for a wind entry |
| B | 8 | 7/8 | Head B in long tones, mp | — |
| Feature | 16 | 7/8 | two voices trade over the A changes, mp | vibraphone and clarinet improvise, each measuring the other's phrases |
| A3 | 12 | 7/8 | Head A, fuller, mf, ending on Dmaj9 | — |
| Coda | 30s | free | decay and room air, pp | the whole coda, open to any voice |

### Harmony

```chords
Intro   | Dm9 | % | % | % | Em7 | % | Dm9 | % |
A1      | Dm9 | % | Em7 | % |
        | Fmaj7 | Em7 | Dm9 | % |
        | Cmaj7 | Bbmaj7 | Am7 | Asus4 |
A2 = A1
B       | G13 | % | Fmaj7 | % | Em7 | A7sus4 | Bbmaj7 | A7 |
Feature | Dm9 | % | Em7 | % |
        | Fmaj7 | Em7 | Dm9 | % |
        | Cmaj7 | Bbmaj7 | Am7 | Asus4 |
        | Dm9 | Em7 | Fmaj7 | G13 |
A3      | Dm9 | % | Em7 | % |
        | Fmaj7 | Em7 | Dm9 | % |
        | Cmaj7 | Bbmaj7 | G13 | Dmaj9 |
```

D dorian throughout, with the natural B as the mode's colour. The Bbmaj7 in bar 10 of each A is borrowed from D aeolian and is the one darker bar of every statement. The Asus4 at the end of A1 and A2 leaves the cadence unresolved. The A7 at the end of B leans on C sharp into the Feature. The only major tonic is the last bar of A3, where Dmaj9 replaces the Asus4 and the F natural of the mode turns to F sharp.

### Core rhythms

```rhythm
meter: 7/8 (3+2+2)  step: 1/8
marimba | X . x x . x . | X . x x . . x |
bass    | x - - . . . . | x - - . x - . |
drum    | X . . o . x . | X . . o . x o |
shaker  | . x x . x . x | . x x . x . x |
```

The marimba row is the reference cell's attack pattern: bar 2 moves its last attack one eighth later, the small change at the end of a bar. The bass row is the two-bar ostinato, root on the first eighth and the fifth on the fifth eighth of every second bar. The drum and shaker rows mark the 3+2+2 grouping.

### Heads

```abc
X:1
T:Head A
M:7/8
L:1/8
Q:1/8=140
K:D dorian
"Dm9"A2 F D2 E2 | A2 F D2 z2 | "Em7"B2 G E2 A2 | B2 G E2 z2 |
"Fmaj7"c2 A F2 G2 | "Em7"B2 G E2 D2 | "Dm9"A2 F D2 E2 | A2 F D2 F2 |
"Cmaj7"G2 E C2 E2 | "Bbmaj7"F2 D _B,2 D2 | "Am7"E2 C A,2 C2 | "Asus4"D4 z3 |]
```

```abc
X:2
T:Head B
M:7/8
L:1/8
Q:1/8=140
K:D dorian
"G13"B6-B | e3 d2 B2 | "Fmaj7"A3 c2 e2 | f4 e3 |
"Em7"d3 B2 G2 | "A7sus4"A3 d2 e2 | "Bbmaj7"f3 d2 _B2 | "A7"^c6-^c |]
```

### Lyrics

None — instrumental.

## Recording

### Round 1

#### Noor Low — centered sub-bass

- Take 1: Plays only the root on the first eighth of each bar, held through the three-group, and stays silent for the first four bars of the Intro.
- Take 2: Plays the written two-bar ostinato from Intro bar 1, root on the first eighth and the fifth on the fifth eighth of every second bar. In B it drops to a low G held for two bars.
- Take 3: Plays the ostinato through every section, Feature included, with a slow swell from p to mf across A3.
- Picked by Calder Mallet: Take 2 — the fifth on the fifth eighth falls into the rest where my cell stops in bar 2. The floor answers the mechanism instead of sitting under it.

#### Calder Mallet — saturated marimba

- Take 1: Plays Head A exactly as written, dry, mp. The rests in bars 2, 4 and 12 stay empty, and the Intro cell repeats eight times without a single change.
- Take 2: The Intro cell drifts by one note every two bars, its last E becoming F and then G. In A2 Head A goes up an octave.
- Take 3: Rolls the long D in bar 12 and the Asus4, adds a grace-note pickup into every rest, and plays A3 at f.
- Picked by Vela Ring: Take 1 — the empty rests in bars 2 and 4 are where my decay can be heard. Take 3's rolls cover the ring completely.

#### Vela Ring — vibraphone

- Take 1: Motor off, plays Head B with the pedal held through each two-bar chord. In A1 and A2 strikes one note on the first eighth of each Dm9 bar only.
- Take 2: Motor off. In A2 answers each marimba bar one bar later with that bar's last note, left ringing. Head B grows from pp to mf at bar 7 and falls back to p on the C sharp. In the Feature plays four-bar phrases that end on a struck note left to ring.
- Take 3: Four-mallet ringing voicings through all of A1 and A2, and a continuous solo across all sixteen Feature bars.
- Picked by Rook Ground: Take 2 — the one-bar-late answers put a second row of attacks against the 3+2+2, and I can mark the gap between them. The swell in B is audible from the first bar.

#### Rook Ground — acoustic percussion

- Take 1: A frame drum accent on the first eighth of each bar and nothing else. No shaker, the Intro silent, brushes on a closed frame in A3.
- Take 2: The written grid in layers: light frame drum and shaker from A1, the ghost on the fourth eighth added in A2, the dense layer only in A3. A three-eighth woodblock fill closes B bar 8.
- Take 3: The dense layer from Intro bar 1, with a rolled frame drum fill closing every fourth bar.
- Picked by Merrit Reed: Take 2 — the layers thicken with the form, so A3 is busier without anyone playing louder. The woodblock fill at B bar 8 tells me exactly where the Feature starts.

#### Merrit Reed — clarinet

- Take 1: Silent until A2, then a low descending line from A to D across bars 1–8, one note per bar, each held for the three-group.
- Take 2: In the Feature each chalumeau phrase is timed to last as long as Vela's previous note rings. In A3 bars 9–12 a descending answer from F down to low A, independent of the head.
- Take 3: Plays continuously in the chalumeau from A1 at mf, breathy, sliding into the first eighth of every bar.
- Picked by Sela Air: Take 2 — his descent in A3 stays below the staff, which leaves the top register open for me. The Feature trades are the instruments measuring each other.

#### Sela Air — flute

- Take 1: Enters only in A2 bars 11–12, the written open space, with two soft breath-led notes, E then D, then silent until the coda.
- Take 2: A late counterline above Head B, entering on the fifth eighth of each bar. In the coda holds a high A with the air audible and releases it over eight seconds.
- Take 3: Flutter-tongued answers through the Feature, and a continuous melodic line through all of A3 at mf.
- Picked by Merrit Reed: Take 1 — those two notes in A2 are the first time air comes into the room. Keeping the flute silent after them holds the room exact for longer.

### Round 2

#### Sela Air — flute

- Take 1: Keeps the A2 bars 11–12 entry and adds three breaths in the coda, each a falling second, pp.
- Take 2: Keeps the A2 entry and enters late in A3 bar 9 with a slow rise E, F, G, landing on A as the Dmaj9 arrives. In the coda holds that A while the vibraphone decays.
- Take 3: Keeps the A2 entry and brings back the round 1 counterline over B as well, so the flute enters three times.
- Picked by Merrit Reed: Take 2 — her rise in A3 crosses my descent, and the two lines reach the Dmaj9 from opposite directions. That crossing is where the warmth comes from.

#### Merrit Reed — clarinet

- Take 1: Round 1 take 2 with the Feature trades cut to two-bar phrases, so the measuring goes back and forth twice as fast.
- Take 2: Keeps the four-bar trades but ends each one with an exhale and no tone. Moves the A3 descent one bar later, into bars 10–12, so the low D arrives on the first eighth of the last bar.
- Take 3: Plays the Feature trades in the clarion register, an octave and a fifth higher, at mf.
- Picked by Rook Ground: Take 2 — his low D now lands on the same eighth as the flute's A. The exhale at the end of each trade leaves a silence I can mark.

#### Rook Ground — acoustic percussion

- Take 1: Keeps the round 1 layering. In the Feature taps only the frame drum rim on the group starts (eighths 1, 4 and 6), measuring the trades without accenting them.
- Take 2: As take 1 but stops completely for Feature bars 13–16, leaving only room air, then comes back in A3 with the light layer, not the dense one.
- Take 3: As take 2, with a struck bowl on the first eighth of A3 bar 12 in place of any fill, ringing into the coda.
- Picked by Vela Ring: Take 3 — the four silent bars before A3 make the head's return sound like a door opening, and the bowl rings alongside the last chord without hitting it.

#### Vela Ring — vibraphone

- Take 1: Keeps the round 1 canon and Feature phrases, and turns the motor on for all of A3, voicing the Dmaj9 to ring twelve seconds into the coda.
- Take 2: Motor off for the whole track until the first eighth of A3 bar 12, then on for the Dmaj9 alone. The slow vibrato is the only movement in that bar.
- Take 3: Tightens the canon to half a bar, answering on the fourth eighth, through A2 and A3.
- Picked by Calder Mallet: Take 2 — the vibrato starting only on the last chord is the whole brief in one gesture: exact until then, warmer at the end.

#### Calder Mallet — saturated marimba

- Take 1: Head A as round 1 take 1, plus the Intro drift from round 1 take 2: the cell's last E moves to F, then to G, across bars 1–8.
- Take 2: As take 1, but switches to yarn mallets for A3 so the saturated attacks round off, and keeps the last D of bar 12 at p.
- Take 3: As take 2, but leaves out the D in A3 bar 12 so the Dmaj9 is vibraphone, bass and winds only.
- Picked by Noor Low: Take 2 — the softer mallets bring the attack down to where my fifths sit. Take 3 loses the D I tune the final root against.

#### Noor Low — centered sub-bass

- Take 1: The round 1 ostinato, but in the Feature only a root on the first eighth of every second bar, to leave the trades unweighted.
- Take 2: As take 1, and holds a centred low D under the Dmaj9 in A3 bar 12, letting it fade into the coda's room air.
- Take 3: As take 2, but enters one bar late in A1 so the head is first heard without a floor.
- Picked by the band: Take 2 — the held D gives the last chord a floor. The late entry in take 3 blurs the first clean statement of the cell.

### Band decision

- Noor Low — centered sub-bass: Round 2, Take 2
- Calder Mallet — saturated marimba: Round 2, Take 2
- Vela Ring — vibraphone: Round 2, Take 2
- Rook Ground — acoustic percussion: Round 2, Take 3
- Merrit Reed — clarinet: Round 2, Take 2
- Sela Air — flute: Round 2, Take 2

Every pick is a round 2 take because round 2 is where the parts learned to land on the same eighth. The marimba's drifting Intro and the one-bar-late vibraphone canon set up the measuring. The clarinet's Feature phrases are timed to the vibraphone's ring, and four bars of silence come before A3. Then the last bar gathers everything: the flute rising and the clarinet falling, a held centred D, a bowl, and the vibraphone motor switching on for the Dmaj9 alone.

## Mastery

The Night Operator keeps Noor Low's sub-bass mono and dead centre, with nothing else below 90 Hz. The marimba sits slightly left and the vibraphone slightly right so the one-bar canon reads as two positions. The clarinet is left of centre and the flute right of centre, so their lines in the last bars cross audibly. There is no compression on the vibraphone decay; a gentle 2:1 on the marimba keeps the saturated attacks from covering the bell. Room air stays at a constant low level and carries the coda, so the ending is the instruments decaying, not a fade. Targets: −16 LUFS integrated, true peak at most −1.2 dBTP, about 12 LU of range, so the Intro sits well below A3 and the warmth arrives in level as well as harmony.

## Visuals

### Round 1

#### Surveyor Null

- Take 1: A black dome interior with one vertical slit; each sub-bass root widens the slit by one character column, and six gauges stand on the floor.
- Take 2: Six graduated quarter-arcs in a shallow ring, one per instrument, each needle resting toward the arc on its left so every gauge reads its neighbour. A closed meridian slit sits above them.
- Take 3: No dome: a single long horizontal scale across the frame, with a mark placed at each attack's pitch.
- Picked by Copper Measure: Take 2 — six arcs give each part its own place for traces. The closed slit is a horizon I can open with the last chord.

#### Copper Measure

- Take 1: Every note leaves a dot on its instrument's arc at its pitch, and every dot fades at the same fixed rate.
- Take 2: Traces last as long as the note sounds: short ticks for marimba, long tails for vibraphone. During the Feature trades a thin line joins the clarinet and vibraphone arcs, its length set by the phrase. The Dmaj9 opens the slit.
- Take 3: Traces drop to the floor of the frame and stack into a density field that thickens over the track.
- Picked by Surveyor Null: Take 2 — trace length shows the difference between the marimba's clipped attacks and the bell's decay. The slit opening on the last chord is earned by the music.

### Round 2

#### Copper Measure

- Take 1: Round 1 take 2, but the joining line is drawn only when the clarinet answers the vibraphone, never the reverse.
- Take 2: Round 1 take 2, with the slit widening by one column every two seconds of the coda, so each moment of the coda draws the same frame.
- Take 3: Round 1 take 2 with take 2's timed slit, and every trace stays oxidized blue until A3 begins. Copper appears only from A3 on, and fills the slit only at the Dmaj9.
- Picked by Surveyor Null: Take 3 — holding copper back until A3 makes the picture exact first and warmer later, the same way the band plays it.

#### Surveyor Null

- Take 1: Round 1 take 2 with the whole ring of arcs rotating one tick per bar around the meridian.
- Take 2: The arcs stay fixed and the needles move by pitch. A small navigation cross at the slit steps one notch at each section boundary.
- Take 3: As take 2, but needles freeze exactly during rests. Feature bars 13–16, when the percussion stops, show only the six arcs and the closed slit.
- Picked by the group: Take 3 — the bare frame in the four silent Feature bars keeps a composed picture when the room goes quiet, and the frozen needles match the rests.

### Group decision

- Surveyor Null: Round 2, Take 3
- Copper Measure: Round 2, Take 3

The fixed ring of six gauges, each reading its neighbour, gives the scene the track's idea in one shape, and needles that freeze on rests keep it as exact as the band. Copper's trace lengths separate the clipped marimba from the bell. Holding copper back until A3, then opening the slit on the Dmaj9, means the picture warms exactly when the music does.

### Scene

- **Scene:** meridian-gauges
- **Label:** MERIDIAN / GAUGES
- **Palette:** #05070d, #2b4a63, #c8865a
- **Picture:** A black dome interior with a closed vertical slit at top centre, a small navigation cross beside it, and below it six graduated quarter-arcs in a shallow symmetric ring, one per instrument. Each needle rests toward the arc on its left, so every gauge reads its neighbour. In quiet passages the arcs, the frozen needles and the closed slit hold as a balanced frame. Parts are told apart by glyph and trace length, so the picture reads without color.
- **Motion:** Full: needles swing to each note's pitch and settle, traces run along the arcs for as long as each note sounds, and the slit opens one column every two seconds of the coda. Reduced: needles ease over twice the time, traces draw at half length, and the slit opens in four steps. Still: the frame of the current moment is held, with needles, existing traces and the slit at its current width.

| Source | Visual behavior |
|---|---|
| Noor Low — centered sub-bass | Thickens the ring's base line by one row per root. The held final D keeps it thick through the coda. |
| Calder Mallet — saturated marimba | Places short tick marks on the first arc, one per attack, at the attack's pitch; rests leave the arc bare. |
| Vela Ring — vibraphone | Draws long tails as long as each ring; the motor starting in A3 bar 12 begins the slit's opening. |
| Rook Ground — acoustic percussion | Moves the needle of the percussion arc to each group start; the silent Feature bars freeze it. |
| Merrit Reed — clarinet | Draws a line from its arc to the vibraphone arc during each trade, as long as the phrase lasts. |
| Sela Air — flute | Extends a thin line from the top of the ring toward the slit, climbing as far as each breath lasts. |

## Self-review

- [x] Composition holds only form, harmony, core rhythms, heads and lyrics.
- [x] Each composer logged two or three passes.
- [x] Every bar adds up in the form, chords, rhythms and heads, and the length matches the form.
- [x] Every recording slot has three audibly different takes per round, picked by another member.
- [x] The band decision names one take per slot, and the title came after it.
- [x] Mastery was done by the album's mastering member.
- [x] The visual group ran both rounds; the scene moves geometry and reads reduced, still and
  without color.
- [x] Every member who worked on the track is credited with a model.
- [x] Instrumental and original: no lyrics, quoted melodies or samples.
````
Check: form 68 bars (Intro 8, A1 12, A2 12, B 8, Feature 16, A3 12) + Coda 30 s = chart 68 (8+12+12+8+16+12) ✓ · head A 12 bars × 7 units ✓ · head B 8 bars × 7 units ✓ · rhythm rows 2 bars × 7 cells, grouping 3+2+2=7 ✓ · 68 × 3.0 s + 30 s = 234 s → 3:54 (allowed 3:49–4:14) ✓ · 6 parts × 2 rounds × 3 takes ✓ · picks by next non-player or the band, 12/12 ✓ · decision 6/6 ✓ · credits 1+6+1+2 ✓

PART C — ALBUM

File: albums/B-04-quiet-machinery/A-03-readings-under-the-turning-dome/album.md
````markdown
# Readings Under the Turning Dome

```toml
[album]
id = "A-03"
band = "B-04"
visual_group = "V-04"
title = "Readings Under the Turning Dome"
slug = "readings-under-the-turning-dome"
scope = "test"
status = "final"
date = "2026-11-21"
instrumental = true
rendered = false
recording = "by-track"
round1_order = ["Noor Low", "Calder Mallet", "Vela Ring", "Rook Ground", "Merrit Reed", "Sela Air"]
round2_order = ["Sela Air", "Merrit Reed", "Rook Ground", "Vela Ring", "Calder Mallet", "Noor Low"]
visual_round1_order = ["Surveyor Null", "Copper Measure"]
visual_round2_order = ["Copper Measure", "Surveyor Null"]
mastered_by = "The Night Operator"
made_with = ["anthropic/claude-opus-5-5"]
harness = "omp eval completion(), one stateless message with no tools"
tracks = ["tracks/01-measured-in-ring.md"]

[commission]
direction = "A night shift at an observatory where the instruments begin measuring each other. Slow and exact at first, warmer by the last bar."
reviews = []
```

## Concept

We heard the commission as a room full of gauges after midnight, with nobody left to read them except each other, so on this reading the instruments take turns measuring. Calder's marimba cell is the reference: three eighths, then two and two, A falling through F to D and stepping back to E, refitted to every chord and bent by one interval at the end of a bar. Vela's vibraphone answers it a bar late and lets each note ring for as long as it wants. In the Feature, Merrit times every clarinet phrase to the length of that ring, and Rook marks only where each group begins.

We took "slow and exact" to mean 7/8 at 140 eighths, three seconds to a bar, with the vibraphone motor off and the rests in the head left empty. "Warmer by the last bar" we took literally. The harmony stays in D dorian, darkened once per statement by a borrowed Bbmaj7, until the final bar turns to Dmaj9. In that bar the vibraphone motor comes on for the first time, Sela's rising flute crosses Merrit's falling clarinet onto the chord, and Noor holds a centred D under it while room air carries the decay out.

This is a one-track test, so it is a single reading rather than the whole night shift. There were no reviews to answer.

## Tracklist

| # | Title | Length | Key | Meter | Tempo | Composers |
|---|---|---|---|---|---|---|
| 1 | Measured in Ring | 3:54 | D dorian | 7/8 | 1/8=140 | Calder Mallet |

## Mastery

The Night Operator sequences this single-track test with 1.5 seconds of room air before the first marimba attack. The coda's decay is left whole, with 4 seconds of room air after the last audible ring before the end of the file. Loudness is set to −16 LUFS integrated with true peak at most −1.2 dBTP and about 12 LU of range. When the full album follows, every track will be matched to this track's A3 level rather than its quiet Intro, so the night keeps one floor.

## Cover

- **A:** A black observatory dome seen from inside, its slit just opened to a thin copper band of horizon above six brass gauges standing in a ring.
- **B:** A vibraphone bar and a marimba bar laid across each other like the arms of a measuring instrument, lit along one edge in oxidized blue.
- **C:** Long-exposure copper star trails curving over a dark dome, with six small instrument needles in the foreground all pointing at one another.
- **Chosen:** A — the slit opening to copper above the gauges is what the last bar does, when the vibraphone motor comes on and the Dmaj9 arrives.

## Library blurb

Quiet Machinery's night shift in 7/8: six instruments read each other, exact at first, until the last bar turns to D major.

## Self-review

- [x] The direction and reviews are the only human input, and the concept answers them.
- [x] Every track doc passes its own self-review.
- [x] The tracklist matches the track cards.
- [x] Track and album titles were chosen after the music.
- [x] `made_with` lists every model in the track credits.
- [x] A full album runs 25:00 to 30:00.
- [x] The concept, cover options and blurb describe only what the music does.

## Provenance

- Made 2026-11-21 by the Terminally Agentic AV swarm in omp eval completion(), one stateless message with no tools, with anthropic/claude-opus-5-5.
````

PART D — SELF-REVIEW

**Album (album.md)**
- Item 1: the title equals the card's title, and the card has only template keys. The harness and direction strings contain no double quotes.
- Item 2: all sections are present in template order.
- Item 3: A-03, B-04 and V-04 are valid IDs; the slug and path follow section 3.2.
- Item 4: Provenance has a bullet, and every Self-review item is kept and checked.
- Item 10: round2_order reverses round1_order, the visual orders are reversed, and mastered_by is the house engineer.
- Item 11: the direction is 139 characters, copied exactly; reviews is `[]`.
- Item 12: the concept is 3 paragraphs, about 230 words, and answers the direction.
- Item 13: the tracklist row is copied exactly from the track card, and `tracks` lists the one file.
- Item 14: Mastery has more than 15 words, the Cover has A/B/C plus Chosen, and the blurb is 124 characters.
- Item 15: made_with contains the only model credited.
- Hardest: matching the concept to the actual takes without inventing anything the music doesn't do.

**Track 1 (Measured in Ring)**
- Items 1–4: title, card, path and slug are correct, and all Self-review items are checked.
- Item 16: album, band and number match; the composer is a band composer; meter, tempo and length are well formed.
- Item 17: one composition credit, six instrument parts spelled exactly as on the band card, one mastering credit for mastered_by, two visuals credits, and every credit has a model.
- Item 18: Passes 1–3 are all by Calder Mallet, each over 8 words.
- Item 19: there are exactly five composition subsections, and the form names open space in A2, the Feature and the Coda.
  - The chart matches 8/12/12/8/16/12 bars.
  - Both heads have 7 units in every bar.
  - All rhythm rows have 7 cells per bar.
  - Lyrics are `None — instrumental.`
- Item 20: 234 s → 3:54, which lies inside 3:49–4:14.
- Item 21: 6 blocks per round in round order, each with three distinct takes and a non-player pick. The last Round 2 block is picked by the band.
- Item 22: the band decision is 6/6 with reasons.
- Item 23: track Mastery has more than 15 words.
- Item 24: visual rounds follow the visual orders, the last block is picked by the group, and the group decision is 2/2 with reasons.
- Item 25: the slug is unique, the label is upper case, there are three hex colors, Motion covers full, reduced and still, and the table has 6 rows.
- Hardest: ABC bar arithmetic in 7/8.
  - I used `B6-B` and `^c6-^c` ties instead of 7-unit notes.
  - I reworked Head A bar 3, ending on A rather than F, to avoid a flat-nine clash over Em7.

**Flags:**
- `mastered_by` is The Night Operator, the band's house engineer, chosen instead of a band member.
- The track has one composer, Calder Mallet, per the rotation.
- The album self-review item "A full album runs 25:00 to 30:00" is checked as vacuously true, because this is a 1-track test, not a full album.
- The album title and scene avoid A-01 and A-02 titles and the A-02 room set. The scene introduces a new gauge-ring form within the group's black, oxidized blue and copper language.
- Pasted band and visual group docs are not reprinted, per test scope.

END OF OUTPUT
