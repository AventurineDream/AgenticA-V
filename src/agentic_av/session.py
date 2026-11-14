"""Mutable playback and display state shared by the TTY, painter, and CLI.

Gallery selection is a built-in index, or -1 when the active palette is not
in that list. Known seeks apply a signed delta so short shows keep direction;
the half-show adjustment is only for unseeked loop wraps. Still motion holds
field time and the selected program; transport may cross a chapter without
changing the picture.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentic_av.omarchy import OmarchyTheme
from agentic_av.palette import Palette
from agentic_av.show import Show
from agentic_av.transport import Playhead

# 0.22x is slow enough to read as reduced motion and fast enough that a
# passage still changes. Scale playhead deltas, never absolute position:
# absolute scaling rewinds the picture when the mode is selected.
_REDUCED_FIELD_SCALE = 0.22


@dataclass(slots=True)
class Session:
    """One active show and its visual controls; no disk writes or media state.

    Field time is seconds of visual sampling, not wall time. Reduced motion
    continues from the current picture; it does not rescale the show position.
    Still motion freezes field time and the program that was on screen.
    ``gallery_index`` is aligned to the active built-in on init, or -1 for a
    live palette that is not in the built-in list.
    """

    show: Show
    playhead: Playhead
    palette: Palette
    theme_id: str
    themes: tuple[Palette, ...]
    color_mode: str
    motion: str = "full"
    mode: str = "play"
    # -1 is no built-in selection. Do not modulo it onto the last palette.
    gallery_index: int = -1
    field_time_s: float = 0.0
    # Playhead seconds when field_time_s was last committed.
    motion_anchor_s: float = 0.0
    # Show seconds of the program painted while still. Field time is the
    # sampling clock and can diverge under reduced motion, so it must not
    # choose the program.
    program_hold_s: float = 0.0
    omarchy: OmarchyTheme | None = None
    omarchy_note: str = ""

    def __post_init__(self) -> None:
        self.align_gallery_index()
        # A session can start already still. Hold the program at the initial
        # playhead before transport advances, or the first frame follows it.
        self.program_hold_s = self.playhead.position

    def align_gallery_index(self) -> None:
        """Point gallery selection at the active built-in, or clear it.

        Live Omarchy palettes are not in the built-in list. ``-1`` is not a
        wrap index: the first theme key starts at the first built-in, and
        Enter must not apply the last one.
        """
        self.gallery_index = -1
        for index, theme in enumerate(self.themes):
            if theme.name == self.palette.name:
                self.gallery_index = index
                return

    def visual_program(self) -> tuple[int, str]:
        """Return the program painted on the stage.

        Still motion keeps the program selected when the picture was held.
        Transport crossing a chapter does not change it. A seek, a chapter
        skip, or leaving still selects again from the playhead.

        Returns:
            Zero-based program index and its id.
        """
        position = self.program_hold_s if self.motion == "still" else self.playhead.position
        return self.show.program_at(position)

    def advance_visual_time(self) -> float:
        """Commit unseeked playhead movement into the field clock and return it.

        Full and reduced motion update ``field_time_s`` and ``motion_anchor_s``.
        Still motion returns the held time and leaves the anchor alone, so a
        later mode change resumes from this frame instead of skipping ahead.
        The painted program is held separately; this clock does not select it.
        Known seeks apply a signed delta and reset the anchor first, so the
        half-show adjustment below only sees unseeked loop wraps.

        Returns:
            Field time in seconds.
        """
        if self.motion == "still":
            return self.field_time_s
        position = self.playhead.position
        delta = position - self.motion_anchor_s
        duration = self.show.duration
        # Unseeked playback only. A loop wrap looks like a jump past half the
        # show; known seeks never reach this adjustment.
        if delta > duration / 2:
            delta -= duration
        elif delta < -duration / 2:
            delta += duration
        scale = _REDUCED_FIELD_SCALE if self.motion == "reduced" else 1.0
        self.field_time_s += delta * scale
        self.motion_anchor_s = position
        return self.field_time_s

    def commit_motion(self, motion: str) -> None:
        """Switch motion mode without jumping the current picture.

        Entering still freezes the program on screen. Leaving still resumes
        program selection from the playhead without skipping field time.

        Args:
            motion: ``full``, ``reduced``, or ``still``.
        """
        if self.motion == "still":
            self.motion_anchor_s = self.playhead.position
        else:
            self.advance_visual_time()
        if motion == "still":
            self.program_hold_s = self.playhead.position
        self.motion = motion

    def hold_visual_time(self, time_s: float) -> None:
        """Hold the picture at `time_s` seconds while scrubbing a still.

        The held program follows the playhead after the seek, not the
        sampling clock. Transport movement alone does not call this.

        Args:
            time_s: Field time in seconds, usually the playhead after a seek.
        """
        self.field_time_s = time_s
        self.motion_anchor_s = self.playhead.position
        self.program_hold_s = self.playhead.position

    def seek_field(self, delta_s: float) -> None:
        """Seek by ``delta_s`` seconds and move the picture in that direction.

        Ordinary playback is committed before the playhead jumps. The known
        delta is then scaled into field time and the anchor is reset to the
        wrapped position, so the loop heuristic never classifies this seek.
        Still motion holds the picture and its program at the new playhead
        position instead.

        Args:
            delta_s: Signed show seconds. Positive is forward, including a wrap.
        """
        if self.motion != "still":
            self.advance_visual_time()
        self.playhead.seek(delta_s)
        if self.motion == "still":
            self.hold_visual_time(self.playhead.position)
            return
        self._finish_logical_seek(delta_s)

    def seek_chapter(self, step: int) -> None:
        """Jump to another program and follow that key's direction.

        Still motion holds the picture and its program at the new program
        start. Transport movement alone does not.

        Args:
            step: ``-1`` for the previous program, ``+1`` for the next. The
                signed delta comes from this direction, not from the wrapped
                position change ``seek_to`` would otherwise imply.
        """
        if self.motion != "still":
            self.advance_visual_time()
        target, delta_s = self.show.chapter_delta(self.playhead.position, step)
        self.playhead.seek_to(target)
        if self.motion == "still":
            self.hold_visual_time(self.playhead.position)
            return
        self._finish_logical_seek(delta_s)

    def _finish_logical_seek(self, delta_s: float) -> None:
        """Scale a known seek into field time and anchor at the wrapped position.

        Args:
            delta_s: Logical movement in seconds. Positive is forward.
        """
        scale = _REDUCED_FIELD_SCALE if self.motion == "reduced" else 1.0
        self.field_time_s += delta_s * scale
        self.motion_anchor_s = self.playhead.position
