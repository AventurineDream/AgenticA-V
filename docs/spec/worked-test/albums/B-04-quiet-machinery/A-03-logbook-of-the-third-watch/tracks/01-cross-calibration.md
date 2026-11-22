# Cross-Calibration

```toml
[track]
album = "A-03"
band = "B-04"
number = 1
title = "Cross-Calibration"
slug = "cross-calibration"
key = "G dorian"
meter = "7/8"
tempo = "1/8=140"
length = "3:44"  # from the form: 64 bars of 7/8 at 1/8=140 (192 s) plus the 20 s intro and the 12 s tail
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

Wrote the cell: G, D and F struck as single eighths with rests between them, grouped 2+2+3 in 7/8 at 1/8=140. Head A is twelve bars of that cell fitted to Gm9, C9, Ebmaj7 and D7sus4, and each second bar changes only its last two eighths. The form is a free intro for the vibraphone, then A1, A2, a B section, a Feature over the A changes, A3 and an eight-bar coda ending on Gm9.

### Pass 2 — Calder Mallet

With the marimba carrying it, the B section was the same mechanism over different chords, so it went to the clarinet. Head B is a slurred, descending low line over Ebmaj7, Cm9, Bbmaj7, Am7 and D7sus4, with long values where the cell has rests, so the winds never double the mallet head. The Feature keeps the A changes and has no written melody: two-bar measurements, left open.

### Pass 3 — Calder Mallet

Changed one interval: the coda's last two bars move from Gm9 to Gmaj9. The B flat rises to B natural, so the warmth the direction asks for is one note, in the last bars. Wrote head C for the flute to carry that note, entering late on the fifth eighth of coda bar 1. Added a twelve-second free tail so the vibraphone's last ring can finish in the room.

## Composition

### Form

| Section | Bars | Meter | Texture and intensity | Open space |
|---|---|---|---|---|
| Intro | 20s | free | vibraphone and room air, ppp | the whole intro: vibraphone alone in free time |
| A1 | 12 | 7/8 | head A on marimba over sub-bass roots, pp | — |
| A2 | 12 | 7/8 | head A again, percussion marks the grouping, pp to p | — |
| B | 8 | 7/8 | head B on low clarinet, mallets thin out, mp | — |
| Feature | 12 | 7/8 | marimba and vibraphone over bass and percussion, p to mf | marimba and vibraphone trade two-bar measurements over the A changes |
| A3 | 12 | 7/8 | head A with both winds, mf | clarinet and flute free counterlines in bars 9–12 |
| Coda | 8 | 7/8 | head C on flute, the band thinning, mp | — |
| Tail | 12s | free | vibraphone decay and room air, ppp | the whole tail, the last ring left open |

### Harmony

```chords
A1      | Gm9 | % | C9 | % |
        | Gm9 | % | Ebmaj7 | D7sus4 |
        | Gm9 | C9 | Ebmaj7 | D7sus4 |
A2 = A1
B       | Ebmaj7 | % | Cm9 | % |
        | Bbmaj7 | % | Am7 | D7sus4 |
Feature = A1
A3 = A1
Coda    | Gm9 | % | Ebmaj7 | % |
        | Cm9 | D7sus4 | Gmaj9 | % |
```

G dorian throughout; the E natural in C9 is the mode's colour. The intro sits on a G pedal and the tail on Gmaj9. The A changes return unaltered in A2, the Feature and A3. The only harmonic change on the track is in the last two bars of the coda, where Gm9 becomes Gmaj9 and the B flat rises a half step to B natural.

### Core rhythms

```rhythm
meter: 7/8 (2+2+3)  step: 1/8
bass  | x - - . x - - | x - - . . . . |
drum  | X . o . x . . | X . o . x . o |
block | . . x . . . x | . . x . . . . |
```

### Heads

```abc
X:1
T:Head A
M:7/8
L:1/8
K:G dorian
G z d z f2 d | G z d z f e z | E z c z e2 c | E z c z e d z |
G z d z f2 d | G z d z g f z | _E z G z B2 d | D z A z c3 |
G z d z f2 d | E z c z e d z | _E z G z B d z | c2 A2 G3 |]
```

```abc
X:2
T:Head B
M:7/8
L:1/8
K:G dorian
(G4 D3) | (_E2 D2 B,3) | (C4 D2 _E) | B,6 z |
(F4 D3) | (C2 B,2 A,3) | (G,2 A,2 C3) | D6 z |]
```

```abc
X:3
T:Head C
M:7/8
L:1/8
K:G dorian
z4 d3 | f2 a2 g3 | z2 g2 d3 | _e2 d2 B3 |
c2 d2 _e3 | d2 g2 a3 | =b6 a | =b6 z |]
```

### Lyrics

None — instrumental.

## Recording

### Round 1

#### Noor Low — centered sub-bass

- Take 1: Plays the grid as written in every A section and the Feature. The root is held through the first two groups and the fifth sounds on the 3-group of every bar; silent in the intro and tail.
- Take 2: Plays roots only in bars where the chord changes, leaving every % bar of A1 and A2 empty, and plays no fifths at all. The coda's Gmaj9 gets one low G.
- Take 3: Holds a single low G pedal under A1 and A2, straight through the C9 and Ebmaj7 changes. Follows the roots only from B on and drops to the low D under the coda's D7sus4.
- Picked by Calder Mallet: Take 2 — the empty % bars leave the marimba's rests exposed in A1, so the first thing heard being measured is the cell against silence.

#### Calder Mallet — saturated marimba

- Take 1: Head A exactly as written at mp with hard mallets, every attack dead-stopped. In the Feature each two-bar measurement repeats bar 1 of the cell unchanged.
- Take 2: Head A at pp in A1 and p in A2, with the second bar's last attack moved one eighth later in A2. In the Feature each measurement alters one interval of the cell: D to E flat, then D to E, then back.
- Take 3: Plays A2 an octave up, above the vibraphone's range. In the Feature it measures by subtraction, each two-bar turn dropping one attack until bar 11 holds a single G.
- Picked by Vela Ring: Take 2 — one changed interval per measurement gives the vibraphone an exact note to answer, and the late attack in A2 makes the bar audibly re-measure itself.

#### Vela Ring — vibraphone

- Take 1: Strikes one G at mp in the intro with the motor off and lets it ring the full twenty seconds, then stays silent through A1. In A2 it plays one ringing note per chord change with the pedal down; in the Feature it holds the exact note Calder Mallet just changed.
- Take 2: Spaces G, D and A six seconds apart in the intro and enters in A1, letting each note ring across two bars. In the Feature it times each decay to the length of the marimba's rests.
- Take 3: Motor on at slow speed throughout, with a rolled Gm9 cluster swelling from pp to mp in the intro. Plays a free solo line through the Feature instead of answers.
- Picked by Rook Ground: Take 1 — the single G and the silent A1 leave the room empty enough that one drum stroke reads as a measurement, and the held changed notes in the Feature are something to count against.

#### Rook Ground — acoustic percussion

- Take 1: Plays the grid as written on frame drum and woodblock in every A section and the Feature, light layer only. A two-group fill closes bar 12 of each A.
- Take 2: Silent through A1, then enters A2 with the woodblock alone on the third and seventh eighths. Brushes the frame drum through B and plays the middle layer in the Feature and the dense layer with the fill in A3. In the coda there is one stroke on the 3-group of bar 6.
- Take 3: One accent per bar and nothing else, the accent moving from the first group to the second to the third through the whole track, coda included.
- Picked by Merrit Reed: Take 2 — the silent A1 lets bass and marimba set the bar alone, and the brushed drum in B leaves the low register clear for head B.

#### Merrit Reed — clarinet

- Take 1: Head B as written at mp, slurs as marked, one breath between bars 4 and 5. Silent outside B except for a low D held under coda bar 6.
- Take 2: Head B swells from p to mf over bars 1–4, then drops subito p at bar 5. In A3, bars 9–12, an independent answer steps down D, C, B flat, A, one note per bar entering on the 3-group against the cell.
- Take 3: Head B with klezmer bends scooped into bar 3's C and bar 6's A. In A3 it plays the marimba cell an octave down in unison rhythm.
- Picked by Sela Air: Take 2 — the descent in A3 leaves the top of the room open for a counterline, and the subito p at bar 5 is a breath an entry can answer later.

#### Sela Air — flute

- Take 1: Silent until A3, then long tones on D, F and G entering on the 3-group of bars 9–12. Head C as written in the coda at pp, the last B natural released on breath alone.
- Take 2: One soft breath tone in the last two bars of the Feature. In A3 a counterline rises F, G, B flat, C against the clarinet's descent; head C is played at p, with the B natural in bar 7 swelling to mp before a breath release.
- Take 3: Head C an octave down in the breathy low register. The A3 counterline is played as staccato replies to each marimba attack.
- Picked by Merrit Reed: Take 2 — rising against the clarinet's descent keeps the two winds on separate routes, and the swell on the B natural is where the track turns warm.

### Round 2

#### Sela Air — flute

- Take 1: Round 1's Take 2 with the A3 counterline starting a bar later. Bar 9 has the clarinet's first step alone, and the flute rises G, B flat, C over three bars.
- Take 2: Round 1's Take 2 with the Feature breath tone pitched on A and tied across the barline into A3's first bar. In the coda the final B natural is held through the written rest and into the tail, fading into the room air.
- Take 3: Head C pushed late, each note an eighth behind its written place, so the B natural lands on bar 7's second eighth and the last note is cut at the barline.
- Picked by Merrit Reed: Take 2 — the tied A carries the Feature into A3 without a new attack, and the B natural held into the tail makes the last sound breath, not a strike.

#### Merrit Reed — clarinet

- Take 1: Head B in subtone at pp throughout with no swell, and the A3 descent unchanged from round 1.
- Take 2: Keeps round 1's swell but cuts bar 4's held B flat after four eighths, so the bar's last three eighths are empty. The A3 descent steps from A down to G on the coda's downbeat and holds it under the flute's late entry.
- Take 3: Head B an octave up in the clarion register with a hard edge on every attack. The A3 descent is replaced by two long tones.
- Picked by Rook Ground: Take 2 — the three empty eighths at the end of B bar 4 are a full 3-group of silence for the room, and the held G gives the coda's first bar a floor before the flute.

#### Rook Ground — acoustic percussion

- Take 1: Round 1's Take 2 layout, with the A2 woodblock moved to the start of the 3-group only, one stroke a bar.
- Take 2: Round 1's Take 2 layout, with the Feature's closing fill reduced to a single brushed stroke in bar 12 and B bar 4's empty 3-group left untouched. Drops the coda stroke and plays nothing after coda bar 4, so the Gmaj9 bars carry no percussion.
- Take 3: Round 1's Take 2 layout, with the A3 dense layer brought down to the middle layer and a fill added across coda bar 8.
- Picked by Vela Ring: Take 2 — with the drum gone from coda bar 5, the last vibraphone strike can ring into the tail without being measured against anything.

#### Vela Ring — vibraphone

- Take 1: Round 1's Take 1 with the intro G struck at pp instead of mp, so the first sound is barely above the room air.
- Take 2: Round 1's Take 1 plus one strike on the coda's Gmaj9 in bar 7, motor off, left to ring through bar 8 and the whole twelve-second tail.
- Take 3: Take 2's coda strike with the motor switched on at its slowest speed for that one note only, so only the last chord has vibrato.
- Picked by Calder Mallet: Take 3 — the slow motor pulse on the Gmaj9 is the first thing on the track that moves without being struck, and it arrives with the last chord.

#### Calder Mallet — saturated marimba

- Take 1: Round 1's Take 2 with A3 struck harder at mf, so the return is louder than A1.
- Take 2: Round 1's Take 2 with the last attack of every A3 bar left out, thinning the head as the winds enter. Silent in the coda except for one dead-stopped G on bar 1.
- Take 3: Round 1's Take 2 with A3 dropped an octave into the marimba's low register, under the winds.
- Picked by Noor Low: Take 2 — the missing last attack in A3 leaves the end of each 3-group free for the fifth to ring, and the single coda stroke hands the room to the winds.

#### Noor Low — centered sub-bass

- Take 1: Round 1's Take 2 with the coda's low G held from bar 7 through bar 8 and into the tail.
- Take 2: Round 1's Take 2 with fifths added on the fifth eighth of every A3 bar, so the floor fills in as the winds enter. The coda's low G is held into the tail.
- Take 3: Round 1's Take 2 with every root cut to a single dry eighth, clipped to match the marimba.
- Picked by the band: Take 2 — the fifths arriving only in A3 make the floor grow at the moment the winds enter, and the held low G gives the Gmaj9 its weight.

### Band decision

- Noor Low — centered sub-bass: Round 2, Take 2
- Calder Mallet — saturated marimba: Round 2, Take 2
- Vela Ring — vibraphone: Round 2, Take 3
- Rook Ground — acoustic percussion: Round 2, Take 2
- Merrit Reed — clarinet: Round 2, Take 2
- Sela Air — flute: Round 2, Take 2

Every part comes from round 2, because round 2 is where each member adjusted to the others' readings. A1 is the cell against silence, with no drum and no bass in the held bars. The bass fifths arrive in A3 just as the marimba drops its last attack and the two winds open in contrary motion. Then the coda empties out: one marimba stroke, the clarinet's held G, no percussion after bar 4. That leaves the Gmaj9 to the flute's B natural, the low G and the one vibraphone note with the motor turning.

## Mastery

The Night Operator keeps Noor Low's sub-bass mono and centered below 120 Hz. Its level is set so the A3 fifths lift the floor by about 2 dB without masking the clarinet's chalumeau register. Calder Mallet's attacks pass with no limiting, so each dead-stopped stroke keeps its dry edge. The vibraphone ring, the flute's held B natural and the room-air layer are left untrimmed through the twelve-second tail. A small high shelf above 6 kHz on the flute alone puts its breath just above the mallets. The track is set for -16 LUFS integrated with true peak at -1.2 dBTP. The intro is left about 14 dB below the coda, so the loudness range sits near 12 LU and the warming is heard as a real change in level.

## Visuals

### Round 1

#### Surveyor Null

- Take 1: A black dome cut by one vertical slit aperture. Sub-bass roots widen the slit by one column, and marimba attacks place survey ticks around the dome's rim.
- Take 2: Six survey tripods stand in a ring around a central stone pier on a black floor. Every scored note draws a thin sight line from its player's tripod to another tripod, and the sub-bass sets the pier's height.
- Take 3: A single meridian line across a dark floor. The percussion's 2+2+3 grouping cuts tick marks of matching lengths, and head B tilts the line downward.
- Picked by Copper Measure: Take 2 — there is one sight line per written note, so every line that gets lit is a scored event, never decoration.

#### Copper Measure

- Take 1: Every sight line is drawn in oxidized blue and fades over its note's length; vibraphone lines persist exactly as long as the ring.
- Take 2: All lines stay oxidized blue until the coda's Gmaj9, where the flute's line on the B natural turns copper first.
- Take 3: Lines brighten with each marimba attack and dim between attacks.
- Picked by Surveyor Null: Take 2 — holding copper back until the B natural puts the warmth in the bar where the band wrote it, while Take 3's brightening on every attack is the flicker the group avoids.

### Round 2

#### Copper Measure

- Take 1: Round 1's Take 2, with copper spreading from the flute's line to every line across the last two bars at the vibraphone's decay rate.
- Take 2: Copper arrives in two steps. In A3 only the endpoints of the two wind lines turn copper as the fifths and winds arrive. At the Gmaj9 the flute line goes copper along its whole length, and the other lines follow over bar 8 at the vibraphone's decay rate.
- Take 3: Round 1's Take 2, with every faded trace left on the floor as a dim mark, so the floor builds up a chart of the whole track.
- Picked by Surveyor Null: Take 2 — copper arrives in the same two steps as the music: the A3 fifths and winds first, the B natural last.

#### Surveyor Null

- Take 1: Round 1's Take 2 with a small cross set at the pier's base as a navigation mark at the start of each section.
- Take 2: Round 1's Take 2 with the ring of tripods drawn one step closer to the pier at each section line, so by the coda the ring is half its first radius. The intro and tail show only the pier and the vibraphone tripod with one line between them.
- Take 3: Round 1's Take 2 with the whole ring rotating one degree per bar.
- Picked by the group: Take 2 — the ring tightens section by section as the instruments close in on each other's readings, and the pier with one tripod gives the quiet intro and tail a composed frame.

### Group decision

- Surveyor Null: Round 2, Take 2
- Copper Measure: Round 2, Take 2

The tightening ring and the two-step copper follow the same structure the band recorded. The instruments draw closer section by section. The first warmth appears only at the wind endpoints in A3, and full copper waits for the flute's B natural in the coda. Nothing lights up that the score did not play.

### Scene

- **Scene:** six-tripods
- **Label:** SIX TRIPODS / ONE PIER
- **Palette:** #06080d, #2f5672, #c8884a
- **Picture:** A black floor seen from above, with a stone pier at the center and a ring of six survey tripods around it, one per player. Each tripod appears at its player's first note, and thin sight lines run between tripods for each scored note. When the music is quiet, in the free intro and tail, the frame is the pier and the vibraphone tripod joined by a single centered line. Without color, copper lines are drawn in double-weight characters and blue lines in single dots, so the warming reads as line weight.
- **Motion:** Full: sight lines draw from tripod to tripod at each note's attack and fade over its length, and the ring steps one notch closer to the pier at each section line. Reduced: lines appear whole instead of drawing, fade at half speed, and the ring eases inward over the first bar of each section instead of stepping. Still: the frame for the current bar is held, with the ring at its section's radius and every sounding line at full length; the same bar always draws the same frame.

| Source | Visual behavior |
|---|---|
| Noor Low — centered sub-bass | Sets the pier's height: each root raises it one row and it settles over the bar; the A3 fifths add a second, shorter column beside it. |
| Calder Mallet — saturated marimba | Each attack draws a short survey tick from the marimba tripod toward the pier, cut at the attack's length; the A3 dropped attack leaves a visible gap in the tick row. |
| Vela Ring — vibraphone | Draws a sight line from its tripod to the note Calder Mallet just changed, lasting as long as the ring; the coda strike's line holds through the tail. |
| Rook Ground — acoustic percussion | Cuts three notches into the floor under each tripod for the 2+2+3 grouping; silent bars leave the notches dark. |
| Merrit Reed — clarinet | Head B draws a long descending line across the pier, each slur one unbroken segment; the A3 descent steps the line lower bar by bar. |
| Sela Air — flute | Draws the highest line from the ring's edge; its A3 endpoints turn copper first, and at the B natural the whole line turns copper. |

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
