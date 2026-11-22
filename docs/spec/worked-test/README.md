# Worked test: one track per band through the swarm prompt

This folder tests [the swarm prompt](../../../prompts/swarm.md) end to end. Each of the four bands made
one test track for an A-03 album from a filled-in commission, in one reply with no revision pass. The
files are kept as the model wrote them. They are test-scope docs (`scope = "test"`), not releases, so
they live here and not in `albums/`. `tests/test_registry.py` validates them with the repository docs.

```bash
uv run python -m clangor_visualis_machina.registry . docs/spec/worked-test
# 12 docs and album folders checked, 0 problems
```

## Method

- The prompt was `prompts/swarm.md` with its Commission block filled in as below. Each band's doc and
  its house visual group's doc were pasted from `bands/` and `visual-groups/`.
- Every run was one stateless call, `completion(prompt, model="slow")`, in omp's eval tool. On this
  workstation that tier is `anthropic/claude-opus-5-5`. There was no system prompt, no tools and no
  conversation: the filled prompt was the whole input. The four bands ran in parallel.
- `File:` blocks were extracted from each reply verbatim, with the last version of a path winning.
  Track files go into the album folder named in PART C, as the prompt specifies.
- The full replies, including plans, session logs, check lines and self-reviews, are in `raw/`.

## Commissions

Every commission used `ALBUM: A-03`, `SCOPE: test`, `TRACKS: 1`, `MODEL: anthropic/claude-opus-5-5`,
`HARNESS: omp eval completion(), one stateless message with no tools` and `DATE: 2026-11-21`.

| Band | Visual group | Direction | Reviews |
|---|---|---|---|
| B-01 Coupon Seance | V-01 | An all-night laundromat on the far side of the Moon: the machines keep time and the lost socks keep the memories. Start funny, end tender. | none |
| B-02 Drowning Collective | V-02 | Learning to breathe underwater: first the panic, then a long, strange calm. By the last bar the two piano hands should argue less. | A-01: An Uneven Kindness, Current Without a Shore and Where the Downbeat Went Under landed best. |
| B-03 Nurse Log | V-03 | empty, so the band chooses | A-01: Positive. It earned the band its second album. |
| B-04 Quiet Machinery | V-04 | A night shift at an observatory where the instruments begin measuring each other. Slow and exact at first, warmer by the last bar. | none |

Malachite wrote these as test inputs. The directions are invented. The two reviews paraphrase the
review status recorded in the project's vault: Drowning Collective A-01 "tracks 01, 03, 04 positive",
and Nurse Log A-01 "positive — this authorized the second album". They are not Aven's words. Nurse Log
was left without a direction to test that path.

## Run history

### Run 1: prompt revision 1

All four replies were complete in one message (29.7k to 33.0k characters, about nine minutes each),
ending in `END OF OUTPUT` with no continuation. The validator found 0 problems in the eight files.
As a control, a copy of one track had one take deleted, one part misspelled and its length moved by
two minutes; the validator reported all three faults and their knock-on errors. The run's replies are
in `raw/run-1/`; its extracted files were replaced by run 2's.

The replies and their self-reviews exposed five weaknesses in the prompt:

1. Track files were printed under full paths, which contain the album slug, so every band had to name
   the album before its first track was finished. That breaks the rule that titles come after the
   music. Nurse Log named it as the hardest item.
2. All four ticked the album self-review item "A full album runs 25:00 to 30:00" as vacuously true.
3. Drowning Collective dropped the optional rhythm grouping because the prompt didn't say what it must
   add up to.
4. "Don't reuse a previous album's scenes" can't be checked: the docs list no scene names.
5. The models invented pronouns for members (24 in the replies, 8 in the files), although the band
   docs give none, so the same member could change gender between albums.

Revision 2 fixed these. Track files are printed relative to the album folder. The self-review item now
reads "The total length fits the scope" in the album template and the prompt. The grouping rule and
the `V:` voice lines are spelled out. The reuse rule covers only discography titles. Members are
referred to by name.

### Run 2: prompt revision 2, the committed prompt

All four replies were again complete in one message (30.1k to 35.0k characters; the batch finished in
about twelve minutes), and the validator found 0 problems. All four printed track files as `tracks/…`
and named the album after the track. Pronouns dropped to four, all in Coupon Seance's reply and one of
them in its track file. The files in `albums/` are from this run.

In both runs, every one of the 108 take blocks follows the prompt's pick chain: the next other member
to record picks, and the band or group picks when nobody follows. The validator itself requires only
that the picker isn't the player, as the spec says.

## Results

| Band | Album | Track | Key, meter, tempo | Length | Composer | Recording slots |
|---|---|---|---|---|---|---|
| B-01 | Quarters for the Far Side | Rinse, Hiccup, Repeat | D dorian, 7/8, 1/8=210 | 2:20 | Sid Spindle | 4 |
| B-02 | Tenths Below the Surface | Gill Practice | D minor, 7/8, 1/8=210; 9/8 at 1/8=135 from B1 | 4:38 | Iris Current | 3 |
| B-03 | Gap Dynamics | Windthrow | D minor, 4/4, 1/4=76 | 3:35 | Mira Fern | 6 |
| B-04 | Logbook of the Third Watch | Cross-Calibration | G dorian, 7/8, 1/8=140 | 3:44 | Calder Mallet | 6 |

Each band chose its house engineer, The Night Operator, as the mastering member.

### The model's self-review

Each reply's PART D walked the checklist item by item and named what it found hardest, for the album
and for the track. Three replies named the pick chain across the round boundary. Three named keeping
the concept to what the one track does while still answering the brief. Drowning Collective also named
counting its two-voice ABC heads, and Coupon Seance named matching a title with commas to its slug.
The flags it raised:

- Coupon Seance: Sid Spindle plays both card parts, crooked keys and haunted electronics, as two
  recording slots; Vera Rosin's "bowed strings" is unused.
- Drowning Collective: the card's key is "D minor" although the calm turns to D major; the 9/8
  sections set their own tempo in the form.
- Nurse Log: rain, a production layer, is kept out of the credits and the scene's source table.
- Quiet Machinery: the album is `status = "final"` although the scope is `test`; room air is kept
  out of the scene table.

### Malachite's review

The four tracks are musically coherent, and the claims in their prose hold up against the notation:

- **Coupon Seance:** the heads use chord tones at each change: E♭–G–B♭ over Ebmaj7, C♯ on the A7.
  The 7/8 and the theremin come from the band doc ("haunted electronics" is a theremin and price-gun
  blips).
- **Drowning Collective:** the direction is written into the notes. In head A the hands group the 7/8
  differently (the left hand 3+2+2). Head B's last four bars run in parallel tenths, then thirds, then
  an octave D. C♮ appears only under Cmaj7/D. The review is answered too: the missing downbeat kicks
  stay, and the Break is open space for the bass.
- **Nurse Log:** with no direction, the concept says the band chose its own. The tenor and baritone
  share head B as two ABC voices with equal bar counts.
- **Quiet Machinery:** "warmer by the last bar" is a written change: Gm9 becomes Gmaj9 and B♭ rises to
  B♮ in head C's last bars.

Things to watch:

- Six of the eight tracks across both runs sit on D, and six are in 7/8. For Coupon Seance and
  Drowning Collective the band docs ask for odd meters; elsewhere this is the model's habit. A single
  track can't show whether a full album varies, so check the first full A-03 run.
- Nothing here is rendered. The takes are performance directions and the scenes are descriptions;
  "audibly different" is judged from the text.
