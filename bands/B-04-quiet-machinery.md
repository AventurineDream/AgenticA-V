# Quiet Machinery

```toml
[band]
id = "B-04"
name = "Quiet Machinery"
slug = "quiet-machinery"
status = "active"
genres = ["chamber bass", "mallet jazz", "experimental instrumental"]
instrumental = true
house_visual_group = "V-04"
label = "Lil Big Bang Agentic AV Group"
house_engineer = "The Night Operator"
production_layers = ["room air"]

[[members]]
name = "Calder Mallet"
roles = ["musician", "composer"]
instruments = ["saturated marimba"]
influences = ["minimalism", "gamelan", "mallet jazz"]

[[members]]
name = "Vela Ring"
roles = ["musician", "composer"]
instruments = ["vibraphone"]
influences = ["mallet jazz", "cool jazz", "ambient"]

[[members]]
name = "Noor Low"
roles = ["musician", "composer"]
instruments = ["centered sub-bass"]
influences = ["dub techno", "drone", "bass music"]

[[members]]
name = "Sela Air"
roles = ["musician", "composer"]
instruments = ["flute"]
influences = ["ambient", "chamber music", "spiritual jazz"]

[[members]]
name = "Merrit Reed"
roles = ["musician", "composer"]
instruments = ["clarinet"]
influences = ["chamber music", "klezmer", "third stream"]

[[members]]
name = "Rook Ground"
roles = ["musician", "composer"]
instruments = ["acoustic percussion"]
influences = ["hand percussion traditions", "minimalism", "free improvisation"]

[process]
composer_rotation = [
  "Calder Mallet", "Merrit Reed", "Vela Ring", "Noor Low", "Sela Air", "Rook Ground",
]
recording_order = [
  "Noor Low", "Calder Mallet", "Vela Ring", "Rook Ground", "Merrit Reed", "Sela Air",
]
refinement_order = [
  "Sela Air", "Merrit Reed", "Rook Ground", "Vela Ring", "Calder Mallet", "Noor Low",
]
```

## Members

### Calder Mallet

Calder Mallet plays a saturated marimba that gives Quiet Machinery dry, mineral attacks. Clipped
entries and clear rests expose the band's recurring cell, which Calder fits to each chord and bends
with a small change of contour at the end of a bar. A single altered interval can change what a
phrase means, so Calder changes little and chooses carefully. Calder listens for the room's
silence before placing the next attack. What Calder protects is legibility: a mechanism whose
movement stays easy to hear because space surrounds every strike.

### Vela Ring

Vela Ring plays vibraphone and treats its decay as an independent voice. A ringing note continues
the phrase after its attack, so Vela often carries heads and ringing voicings while the marimba
clips short. Dynamic arcs shape each section, taking the bell's weight from a whisper to a full
bloom and back. Quiet space lets that lingering voice shape the room. Vela listens to how long each
note wants to last, and lets it last. What Vela protects is long bell decay, independent phrasing
and the arc of a passage.

### Noor Low

Noor Low plays centered sub-bass, the mass beneath Quiet Machinery's mallets and winds. The
fundamental always stays in the middle. Sparse roots and fifths at the start of each group make the
floor audible without crowding the upper voices, and when a track asks for it Noor holds a written
ostinato under an uneven meter. A clear floor gives short attacks and long decay a stable place to
meet. Noor listens for how little is needed. What Noor protects is weight carried by sparse
entries, with the upper voices left clear.

### Sela Air

Sela Air plays flute and enters softly, often late in the phrase, with an independent counterline.
Breath shapes the beginning and the release of every line, and high replies find space above the
room's heavier voices. Each entry follows the wind assignment written for that track rather than
filling empty bars. Sela listens to the clarinet and to the vibraphone's decay before answering
either. What Sela protects is the softness of an entry and a breath-led release, so the flute reads
as air moving through the room rather than one more attack.

### Merrit Reed

Merrit Reed plays clarinet and gives low-register phrases their own contour. Breath and register
create pressure just above the bass floor, and descending answers travel independently of the
mallet head instead of shadowing it. Merrit often takes the low heads and develops recognizable
material as the room's light changes across an album. Merrit listens for the line the marimba is
not playing. What Merrit protects is the low clarinet's contour, its breath, and a development that
stays its own while the mechanism turns around it.

### Rook Ground

Rook Ground plays acoustic percussion and marks Quiet Machinery's asymmetric phrases. Attack
placement makes each changing bar shape audible, with patterns built on the meter's grouping in
light, middle and dense layers and a fill that closes a phrase. Silence is an active part of the
arrangement, never an empty bar. In a quiet chapter, Rook lets decay and room air carry the memory
of the pulse. Rook listens to the grouping before the beat. What Rook protects is asymmetric
phrasing, intentional silence and sparse rhythm where the music asks for it.

## Description

Quiet Machinery makes chamber-bass music for rooms that have lost their lights. Noor Low's centered
sub-bass supplies the mass; Calder Mallet's saturated marimba strikes dry mineral attacks while Vela
Ring's vibraphone carries long bell decay. Above them, Sela Air's flute and Merrit Reed's clarinet
take independent, breath-led routes, and Rook Ground's acoustic percussion marks asymmetric phrases
and keeps silence active. Room air sits under everything as a production layer. The band works by
small changes to a recurring cell, letting warmth emerge through development rather than arrive all
at once.

## Sound

- **Core sound:** Chamber bass and mallet jazz: centered sub-bass, saturated marimba, vibraphone,
  flute, clarinet and acoustic percussion in asymmetric meters.
- **Keep:** A recurring cell developed by small changes; clipped attacks against long decay; winds
  entering by written assignment; silence as part of the arrangement.
- **Avoid:** Filling the room; winds doubling the mallet head; losing the centered fundamental.
- **Production layers:** Room air.

## Discography

| ID | Title | Year | Length | Tracks | Made with |
|---|---|---|---|---|---|
| A-01 | The Atlas of Unlit Rooms | 2026 | 27:00 | 6 | not recorded |
| A-02 | Instruments for Measuring Dusk | 2026 | 26:36 | 6 | anthropic/claude-opus-5-5 |

## Provenance

- Migrated to spec v1 on 2026-11-21 by Malachite (omp) with anthropic/claude-opus-5-5.
- Sources: the Drive band folder (README, 00_About overview and member pages, copied to Markdown by
  Amaranth on 2026-11-04), the A-02 band card, and the vault's Bands and Albums note.
- Carried over: name, genre tags, members and instruments, composer rotation, recording and
  refinement orders, the room-air production layer, label, house engineer and discography. Member
  names come from the second-cycle working roster and are credited on A-02.
- Written in migration: personas (merged from the working artist statements, performance notes and
  A-02 signatures) and the description (rewritten after the personas from the band overview).
- Derived in migration, for Aven to confirm: member influences, inferred from the documented sound.
- Dropped: favorite color and favorite animal, unspecified for every member and not a spec field.
