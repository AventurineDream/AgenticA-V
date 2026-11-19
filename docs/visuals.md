# Native scene guide

Native album art is a new numpy-painted interpretation, not a port of the web
player or the former terminal glyph scenes. The 31 movements across five albums
share album-specific materials and palettes. Audio bands and instrument notes move geometry; seeds
keep repeat renders deterministic. Quiet passages and missing analysis retain
composed scenes rather than substituting fabricated signals.

## Coupon Seance — *Saturn Has a Dollar Store*

Deep space as a discount store: a parallax starfield, forward travel, and a
receipt-barcode spectrum connect seven movements. This album has no note score;
its seven-band audio analysis supplies the musical layers.

1. **Arrival:** approach a shaded ringed planet; Keplerian particles arrange the
   spectrum into concentric rings.
2. **Friction:** a rosin-dusted speaker cone draws changing Chladni nodal figures
   beneath bowed strings.
3. **Commerce:** advance between seven spectral shelf rows toward a distant planet.
4. **Pursuit:** the aisle becomes a rolling chase with travelling patrol beams,
   rather than blinking alternating lights.
5. **Memory:** one seven-partial string crosses the dark toward a small Earth.
6. **Gravity:** an asymmetric accretion disc lenses the stars and receipt strip.
7. **Return:** recede above Saturn while roughly forty seconds of spectrum travel
   outward through its receipt-like rings.

## Drowning Collective — *Are We Fish?*

Ink suspended in a water column: piano voices place pigment, bass heaves the
lower membrane, percussion disturbs grains, and slow light reveals the flow.
These are abstract water paintings, not literal fish.

1. **An Uneven Kindness:** a branching plume with an uneven passage in the current.
2. **The Bass Asked First:** a left-hand bass question answered by pigment and a
   turning shoal of small dashes.
3. **Current Without a Shore:** long lateral streaklines cross boundless water.
4. **Where the Downbeat Went Under:** opposing vertical currents meet along a
   sinuous shear seam.
5. **Two Notes, Then Air:** two small notes leave an unfinished contour and bubbles
   in a mostly empty composition.
6. **The Water Learns Major:** the first water returns, gradually admitting amber
   from above after the score's major marker.

## Nurse Log — *The Ground Moves Anyway*

Weighted rainforest layers sit above a heaving ground. Fog separates trunks;
harp and reeds trace small lights, and the score's sections shape density.

1. **Root:** a branching cutaway grows beneath compressed, gently heaving soil.
2. **Rain:** three rain depths pass ferns, splash crowns, and ground ripples.
3. **Spiral:** an irregular trunk cross-section turns against its outer root ring.
4. **Canopy:** branching crowns open around an off-center breathing sky gap.
5. **Spores:** seedlings grow from a fallen log beneath one shaft and spore tails.
6. **River:** the ground becomes a braided flow between breathing fern-lined banks.

## Quiet Machinery — *The Atlas of Unlit Rooms*

Mostly black sculptural rooms: copper carries warm strikes, glass cool sustained
rims, wind bends space, and bass supplies weight. Dust belongs inside light.

1. **Aperture:** torn light and a damped copper pendulum.
2. **Crossing:** two seven-panel folded screens and multiplied overlap shadows.
3. **Orbit:** a flared, engraved bell with decaying rim modes.
4. **Lattice:** oblique Voronoi salt plates, widening faults, and halite vertices.
5. **Void:** an almost empty plaster room holds one small warm light.
6. **Dawn:** a seven-fork aerial opens a copper horizon, then closes to one point.

## Nurse Log — *The Forest Has a Pocket*

A pocket of the same forest, drawn as a groove-locked picture: a root lattice, hinged
rain, a bent bark spiral, elbowed canopy branches, fern spaces, and a braided river.
Geometry follows picture time and smoothed envelopes; score notes place only small marks.

1. **A Root Learns the Offbeat:** a rectilinear root lattice grows, and the bass takes root
   at its nodes.
2. **Rain in the Hinges:** slanted rain passes seven hinges whose knuckles flex with the snare.
3. **Bark, Bent Light:** a three-arm spiral unwinds and bends with the guitar's weight.
4. **The Canopy Has Elbows:** branches hang from the top edge and turn at right angles on a
   shared grid.
5. **Five Spaces for a Fern:** five fern spaces sway on a five-beat cycle while spores climb.
6. **The Forest Has a Pocket:** nine strands braid toward one horizon, locked to a four-beat pocket.

## Cover panel

*The Forest Has a Pocket* shows its approved cover, a 1024×1024 photo, in a panel at the left of the stage. The panel keeps the photo's proportions, uses at most 40% of the width, and is vertically centered on the canvas rows. It is omitted if fewer than six canvas rows or a 30-column stage cannot fit. With square art and 2:1 terminal cells, it appears from 44 columns; taller cells may need more. Half blocks draw it on every tier except ASCII, which uses printable characters. Color follows the color mode; `NO_COLOR` and `--no-color` draw it in glyphs with no color. The four A-01 cover images were not available to this build, so those albums keep the full-width stage.

## Display and motion

`aav play --glyphs auto` detects the terminal. `AAV_GLYPHS` overrides auto; an
explicit `--glyphs octant|sextant|quadrant|half|braille|ascii` wins over it. Use `g`
to cycle if a font lacks a glyph. Large mosaics step down resolution to bound
sub-pixel work. `--no-color` uses ordered monochrome patterns; interactive cursor
controls are still emitted. The UI theme colors transport, not album palettes.

`--motion reduced` uses 0.22× picture time and reduced reactive gain. `--motion
still` holds a complete composition; `m` holds/releases during playback. Pause
also retains exact pixels, while transport can update. Seeks and movement changes
refresh the composition. Playback targets 30 fps; held transport targets 5 fps.

## Preview and measurement

The dedicated native preview is separate from the abstract `aav preview`:

```bash
uv run python -m agentic_av.viz.preview coupon 1 --at 12,60 --out /tmp/coupon.png
uv run python -m agentic_av.viz.preview forest 2 --sheet 6 --size 190x45 --out /tmp/rain.png
uv run python -m agentic_av.viz.preview rooms 3 --tier half --bench
uv run python -m agentic_av.viz.preview aquatic 6 --live --from 144
uv run python -m agentic_av.viz.preview coupon 4 --safety
```

Movement numbers are one-based. Preview uses real cached extraction, score, and
analysis, with silent fallback and a warning when analysis is unavailable. PNGs
need no pixel terminal protocol. Benchmarks report local costs; they do not
establish a universal frame rate. The live preview follows wall time without
playing audio.

The regional flash meter is a conservative regression heuristic over displayed
cells, with assumed region size and viewing geometry. It checks luminance and
saturated-red reversals plus a whole-canvas guard; it is **not WCAG certification
or a guarantee of flash safety**. Synthetic fixtures and real-audio runs must be
reported separately from visual inspection. No certification is claimed here.
