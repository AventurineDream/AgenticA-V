"""Audio-reactive album visualizers drawn with terminal mosaic cells.

A scene paints linear-light RGB onto a sub-pixel `Surface` with numpy. The
cell fitter turns each block of sub-pixels into one glyph plus two colors
(octant, sextant, quadrant, half-block, braille, or shape-matched ASCII),
and the encoder serializes the cells as ANSI for native album playback.

Scenes read two signal sources at the playback clock: audio features
analyzed once from the decoded movement (`audio`), and the album's own
scored notes and sections (`score`). Motion modes and the no-color renderer
are honored here, not by callers. numpy is the only runtime dependency.
"""
