# Gill Practice

```toml
[track]
album = "A-03"
band = "B-02"
number = 1
title = "Gill Practice"
slug = "gill-practice"
key = "D minor"
meter = "7/8"
tempo = "1/8=210"
length = "4:38"
composers = ["Iris Current"]

[[credits]]
member = "Iris Current"
part = "composition"
model = "anthropic/claude-opus-5-5"

[[credits]]
member = "Iris Current"
part = "acoustic piano"
model = "anthropic/claude-opus-5-5"

[[credits]]
member = "Mica Low"
part = "pitched electronic bass"
model = "anthropic/claude-opus-5-5"

[[credits]]
member = "Pax Lilt"
part = "drum kit"
model = "anthropic/claude-opus-5-5"

[[credits]]
member = "The Night Operator"
part = "mastering"
model = "anthropic/claude-opus-5-5"

[[credits]]
member = "Silt Index"
part = "visuals"
model = "anthropic/claude-opus-5-5"

[[credits]]
member = "Nerve Current"
part = "visuals"
model = "anthropic/claude-opus-5-5"
```

## Composition passes

### Pass 1 — Iris Current

Wrote head A as eight bars of 7/8 at 1/8=210. The right hand is phrased 2+2+3 and the left hand 3+2+2, so the hands disagree inside every bar, over Dm9, Ebmaj7 and an A7 that never resolves. Wrote head B in 9/8 at 1/8=135 as the same contour (A, D, C, A, F, G, E) stretched into dotted quarters and moved into D major. The first form ran A sections, a Break, then B sections.

### Pass 2 — Iris Current

The cut from A3 straight into B1 sounded like a jump, not a breath, so I added the Air section: thirty seconds of piano alone in free time between them. I changed head B bars 5–6 to C natural over Cmaj7/D, so the shape returns with a different harmonic meaning. After the review, I opened the sixteen-bar Break as space for Mica Low's bass to speak.

### Pass 3 — Iris Current

Rewrote head B bars 9–12 so that the left hand leaves its 2+2+2+3 and follows the right hand in parallel tenths, then lands on D an octave below it in bar 12. I added a four-bar Coda, Gmaj9 to Dmaj9, so the agreement has time to sound. I also opened the B-section Solo for my own two hands.

## Composition

### Form

| Section | Bars | Meter | Texture and intensity | Open space |
|---|---|---|---|---|
| Intro | 4 | 7/8 | piano left hand, bass and kit, mf, crowding | — |
| A1 | 8 | 7/8 | full band, head A, f | — |
| A2 | 8 | 7/8 | full band, head A with the bass taking the right-hand line, f | — |
| Break | 16 | 7/8 | bass and kit, piano out, mf rising to ff | Mica Low solos over the Break changes |
| A3 | 8 | 7/8 | full band, head A, ff | — |
| Air | 30s | free | piano alone, rubato, pp | the whole section, Iris Current alone |
| B1 | 12 | 9/8 @ 1/8=135 | full band, head B, p | — |
| Solo | 12 | 9/8 @ 1/8=135 | piano and bass, kit sparse, mp | Iris Current solos over the B changes |
| B2 | 12 | 9/8 @ 1/8=135 | full band, head B, p to pp | — |
| Coda | 4 | 9/8 @ 1/8=135 | piano alone, pp | — |

### Harmony

```chords
Intro | Dm9 | % | Bbmaj7 | A7sus4 |
A1    | Dm9 | Ebmaj7 | Dm9 | Bbmaj7 A7 |
      | Gm9 | Ebmaj7 | Bbmaj7 | A7sus4 A7 |
A2 = A1
Break | Dm9 | % | % | % |
      | Ebmaj7 | % | % | % |
      | Gm9 | % | Bbmaj7 | % |
      | Ebmaj7 | % | A7sus4 | A7 |
A3 = A1
B1    | Dmaj9 | % | Gmaj9 | Em9 |
      | Cmaj7/D | % | Em9 | A13 |
      | Gmaj9 | Em9 | Dmaj9 | % |
Solo = B1
B2 = B1
Coda  | Gmaj9 | % | Dmaj9 | % |
```

**Panic sections (Intro to A3).** These sit in D aeolian. Ebmaj7 is the flat-two pull that keeps them unsettled. The A7 at the end of each A section does not resolve: A3 runs into the free Air section instead of into D.

**Break.** A D pedal runs through Break bars 1–4.

**Calm sections (B1 onward).** The tonic stays D but changes meaning: D major from B1 bar 1.
- Cmaj7/D in bars 5–6 borrows C natural over the D in the bass, a mixolydian shade.
- Gmaj9 under the head's C sharp in bar 9 gives a lydian colour.
- These two colours make the calm strange rather than sweet.

**Voice leading in head B bars 9–12.** The two hands move in parallel tenths, then in thirds, and close on an octave D.

### Core rhythms

```rhythm
meter: 7/8 (2+2+3)  step: 1/8
kick  | x . . x . . . | . x . . x . . |
snare | . . X . . . o | . . . X . o . |
hat   | x o x o x . . | x o x . x o . |
bass  | x . . x . x . | x - - . . x . |
```

```rhythm
meter: 9/8 (3+3+3)  step: 1/8
kick  | x . . . . . . . . | . . . . . . x . . |
snare | . . . o . . . . . | . . . . . . . . . |
ride  | x . . x . . x . . | x . . . . . x . . |
bass  | x - - - - - x - - | . . . x - - x - - |
```

### Heads

```abc
X:1
T:Head A
M:7/8
L:1/8
Q:1/8=210
K:Dm
V:RH
A d c A F2 z | G2 E2 z3 | A d c A F2 ^G | a2 g f e3 |
d g f d B2 z | c2 A2 z3 | (3ABc d2 e3 | f2 e2 ^c3 |]
V:LH
D,3 A,2 F,2 | _E,3 B,2 G,2 | D,3 A,2 C2 | B,,3 F,2 A,,2 |
G,,3 D,2 B,2 | _E,3 B,2 D2 | B,,3 F,2 A,2 | A,,3 E,2 ^C2 |]
```

```abc
X:2
T:Head B
M:9/8
L:1/8
Q:1/8=135
K:D
V:RH
A6 d3 | c6 A3 | F6 G3 | E9 |
A6 d3 | =c6 A3 | F6 G3 | E6 z3 |
d3 c3 A3 | F3 G3 E3 | A6 F3 | D9 |]
V:LH
D,2 A,2 E2 F3 | D,2 A,2 C2 A,3 | G,,2 D,2 A,2 B,3 | E,2 B,2 D2 G3 |
D,2 G,2 =C2 E3 | D,2 G,2 B,2 =C3 | E,2 B,2 F2 G3 | A,,2 E,2 G,2 F,3 |
B,3 A,3 F,3 | D3 E3 C3 | F,6 D,3 | D,9 |]
```

### Lyrics

None — instrumental.

## Recording

### Round 1

#### Iris Current — acoustic piano

- Take 1: Plays head A as written at f, with the sustain pedal half down through A1–A3, so the two groupings smear into one wash. In the Air section the right hand plays single slow notes on A, D and C. Head B is legato with an even left hand. The Solo stays in the middle register over held left-hand chords.
- Take 2: Dry pedal in the A sections, with the left hand accenting the first eighth of each 3+2+2 group against the right hand's 2+2+3, so the argument is audible. Bar 4's high A jumps an octave higher in A3. In the Air section the right hand plays head A's contour alone three times, each slower than the last. In the Solo the left hand starts alone and the right hand waits until bar 5 to answer.
- Take 3: Plays the A sections at mp, both hands legato, leaving the panic to the kit. The Air section is nearly silent: two low Ds and one high A. The Solo is right hand only, in the high register, with the left hand silent until B2.
- Picked by Mica Low: Take 2 — the dry, accented left hand makes 3+2+2 against 2+2+3 something you can hear, and the right hand waiting until Solo bar 5 leaves the first four bars where a bass answer can sit.

#### Mica Low — pitched electronic bass

- Take 1: Doubles the piano's left-hand roots in A1 and takes the right-hand line an octave below in A2. The Break solo is four four-bar sentences, with the upper partials going rough from Break bar 9. In the B sections it holds sustained roots on every downbeat.
- Take 2: Leaves Break bars 1–2 empty, then speaks three sentences that each cadence on D. The bite stays out of the tone until Break bars 13–16, and the fundamental stays centered. In the B sections it rests under the right hand's held notes and answers in bars 4 and 8 with short three-note phrases.
- Take 3: Plays A2 in a high, clean sine register above the piano's left hand. The Break is a call-and-response with the snare, gritty from the first bar. In the B sections it glides between roots with a clean tone.
- Picked by Pax Lilt: Take 2 — the two empty bars at the top of the Break give the kit a hole to land in, and the answers in B bars 4 and 8 tell me exactly where to leave the ride out.

#### Pax Lilt — drum kit

- Take 1: Plays the core grids as written, with the ghost snare on the last eighth of each 7/8 bar and short fills closing A1 and A2. In the B sections the ride plays cells 1, 4 and 7, with kick on odd bars only.
- Take 2: Drops the kick from every other downbeat in the A sections. In A3 the snare accent drifts from cell 3 to cell 4, so the bar feels like it slips. Silent through the Air section. In B1 the ride plays alone, with no kick at all until Solo bar 7.
- Take 3: Plays the A sections on floor tom and rack tom instead of snare, low and thudding, with the hats closed tight. In the B sections the cymbals are out and only snare ghosts remain, with the 9/8 marked by the kick alone.
- Picked by Mica Low: Take 2 — the missing downbeat kicks leave my roots exposed so they read as the floor, and the slipping snare in A3 peaks the panic without anyone playing louder.

### Round 2

#### Pax Lilt — drum kit

- Take 1: Keeps round 1 take 2's missing downbeats but starts the snare drift at A2 bar 5, so the panic builds over twelve bars instead of eight. The B sections are as in round 1 take 2.
- Take 2: Plays the Break only in the bars where Mica rests, so kit and bass alternate sentence by sentence. B2 thins to one kick every two bars, and the kit is silent for the Coda.
- Take 3: Keeps round 1 take 2's A sections. In the B sections the kick follows head B's left-hand 2+2+2+3 for bars 1–8, then switches to 3+3+3 at bar 9 along with the hands. The last B2 fill, in bar 8, is just two ghost notes, and the Coda is empty.
- Picked by Mica Low: Take 3 — the switch to 3+3+3 at B2 bar 9 puts the floor under the hands' agreement, so the change in the piano becomes a change the whole band feels.

#### Mica Low — pitched electronic bass

- Take 1: The Break's third sentence carries head A's contour (A, D, C, A, F) two octaves down, with the bite only in Break bars 15–16. It keeps the bar 4 and bar 8 answers in the B sections and adds a held low D under the Coda.
- Take 2: Plays the whole Break an octave lower in two-bar sentences, each followed by an empty bar, with a clean tone throughout. It keeps the B2 answers in bars 4 and 8 and stays silent in the Coda.
- Take 3: Takes A2's right-hand line one eighth late, so the bass speaks just after the piano. The Break is as in round 1 take 2. In B2 bars 9–12 it drops to whole-bar roots on G, E, D and D, and it stays silent in the Coda.
- Picked by Iris Current: Take 3 — the whole-bar roots under B2 bars 9–12 leave the tenths between my hands clear, and the late entry in A2 makes the line sound as if it changes speaker mid-phrase.

#### Iris Current — acoustic piano

- Take 1: Keeps round 1 take 2's dry, accented A sections, but in A3 bar 8 both hands land together on the downbeat, a sudden agreement. B2 bars 9–12 are played with equal weight in both hands, with the pedal held into Coda octaves struck mf.
- Take 2: Keeps round 1 take 2's A sections. In the Air section the left hand plays head A's contour at a third of its speed while the right hand holds a single high A. In the Solo the hands trade three-bar phrases, left hand first, and the right hand's last phrase echoes the left a tenth above. The Coda octaves are ppp, with the last D held until it vanishes.
- Take 3: Plays the right hand an octave higher throughout the A sections. The Air section is rubato chords in both hands. The Coda octaves are rolled, left hand first, so the hands still sound a fraction apart.
- Picked by the band: Take 2 — the slow left-hand contour under one held A turns the panic figure into breathing, and the Solo ends with the hands a tenth apart, which sets up the convergence in B2.

### Band decision

- Iris Current — acoustic piano: Round 2, Take 2
- Mica Low — pitched electronic bass: Round 2, Take 3
- Pax Lilt — drum kit: Round 2, Take 3

All three chosen takes aim at the same moment, B2 bar 9. There, Iris Current's hands move into parallel tenths, Pax Lilt's kick leaves 2+2+2+3 for 3+3+3, and Mica Low drops to whole-bar roots, so the hands' agreement lands as an arrival rather than a coincidence. Before that, the panic is three voices disagreeing about where bar one is: the dry accented left hand against the right, kicks missing from every other downbeat, and a bass line one eighth late. The Air section, with its slowed contour under a held A, is the breath between the two halves.

## Mastery

The Night Operator sets the balance, tone, space, dynamics and loudness for this track.

- **Bass:** the fundamental is kept centered and mono below 120 Hz, with its upper partials slightly wide, so Mica Low's bite in Break bars 13–16 never blurs the floor.
- **Piano image:** it starts wide, with the right hand a little right and the left hand a little left, and narrows to the centre across B2 bars 9–12, so the final octave lands in one place.
- **Kit:** it stays dry and close in the A sections.
- **Air section:** it keeps its full decay and gets no compression.
- **Dynamics:** the A3 peaks are held by a slow limiter rather than flattened. This leaves about 13 LU of loudness range against the house 12 LU, because the drop from panic to calm is the track.
- **Loudness:** the rendering reference is -16 LUFS integrated, true peak at most -1.2 dBTP.

## Visuals

### Round 1

#### Silt Index

- Take 1: One thick mineral-grey body sits centre-left, compressed by the bass's pressure. Voids open on every omitted kick, and in the 9/8 sections the body widens to fill the lower third.
- Take 2: The body is pressed against the top edge through the A sections, crowded and asymmetric. It sinks during the Air section to rest low and right, leaving the Air section nearly all black with one void edge.
- Take 3: Many small bodies jostle through the A sections and merge into one wide body by B2. Each omitted kick cuts a void through them.
- Picked by Nerve Current: Take 2 — the sinking body empties the upper half of the screen for the two hand currents, and an Air section that is mostly black gives the silence weight on screen.

#### Nerve Current

- Take 1: The right hand is a teal current and the left hand a grey current. They cross wherever the 2+2+3 and 3+2+2 accents disagree, while the bass bends the field and the kit cracks small fractures. In B2 bars 9–12 the currents run parallel and meet at bar 12.
- Take 2: Both hands are one braided line, told apart only by thickness. The kit's fractures are drawn large, across a quarter of the screen.
- Take 3: The currents appear only on note onsets and fade with each decay, so the Air section shows short-lived dashes. The bass's pressure is shown as the density of a dot field.
- Picked by Silt Index: Take 1 — two separate currents that cross on every disagreement and run parallel from B2 bar 9 show the argument ending without any change in light.

### Round 2

#### Nerve Current

- Take 1: Round 1 take 1, now drawn above Silt's sinking body: in the A sections the currents bounce off its upper edge, and in the B sections they settle above it. The piano's decay leaves faint traces for about four seconds.
- Take 2: As take 1, but the vertical gap between the currents equals the interval between the hands. It is wide and jagged in the A sections, a fixed tenth through B2 bars 9–11, and nearly touching at the octave in bar 12.
- Take 3: As take 1 with the currents drawn twice as long. The kit's fractures are drawn only on accents; ghost notes draw nothing.
- Picked by Silt Index: Take 2 — mapping the gap between the currents to the gap between the hands turns the tenths into a steady distance and the last octave into a near touch, so a viewer can see the hands agree.

#### Silt Index

- Take 1: Round 1 take 2's body, but its sink through the Air section is paced by Iris Current's slowed left-hand contour, one step down per note. The body's top surface flattens across B2 bars 9–12.
- Take 2: As take 1, but in the A sections the bass's pressure dents the body's top edge only on Mica Low's late entries in A2.
- Take 3: The body does not sink but thins in place, and the void around it grows instead.
- Picked by the group: Take 1 — a body that sinks one step per left-hand note ties the picture to the first breath, and its flattening surface under the parallel currents gives the calm a floor.

### Group decision

- Silt Index: Round 2, Take 1
- Nerve Current: Round 2, Take 2

The sinking body and the interval-mapped currents tell the same story in two layers. Silt Index's body goes down one step per breath in the Air section and lies flat and asymmetric from B1 on. Above it, Nerve Current's two currents stop crossing and hold a fixed tenth apart, until they nearly touch on the final octave. Nothing flashes: the calm is drawn as distance closing.

### Scene

- **Scene:** gill-practice
- **Label:** GILL / PRACTICE
- **Palette:** #050a10, #4a575e, #3f9c94
- **Picture:** A black ink field holds a thick mineral-grey body that crowds the upper left through the A sections, sinks during the Air section, and lies as an asymmetric shelf low and right from B1 on. Above it run two fine currents: the right hand thin and teal, the left hand thicker and grey. The vertical gap between them is the interval between the hands. In quiet passages the picture holds a composed frame: mostly black, the body partway down, one slow left-hand line and the held right-hand A as a single still point. Without color it reads by value and line weight: a mid-grey body, a thin bright line, a thick dim line and pure-black voids.
- **Motion:** Full: the currents trace at score speed, kit fractures crack and heal within half a bar, and the bass dents and lifts the body's edge. Reduced: the currents move at half speed with their traces held, fractures become static hairlines that fade, and the body moves only at section boundaries. Still: each section holds the frame drawn at its first bar, and the same score position always draws the same frame.

| Source | Visual behavior |
|---|---|
| Iris Current — acoustic piano | The right hand moves the teal current and the left hand the grey current. Their vertical gap follows the interval between the hands, and the piano's decay leaves faint traces for about four seconds. |
| Mica Low — pitched electronic bass | Pressure that bends the field and dents the body's top edge; a rest lets the dent lift back. |
| Pax Lilt — drum kit | A small fracture at each scored hit, wider on accents, healing within half a bar. An omitted hit draws no fracture. |

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
