"""Verify conservative terminal detection, ioctl aspect, and image budgets."""

import struct

import pytest

from clangor_visualis_machina.viz import caps
from clangor_visualis_machina.viz.glyphs import TIERS


@pytest.mark.parametrize("tier", TIERS)
def test_explicit_tier_wins(tier):
    assert caps.detect_tier({"AAV_GLYPHS": tier, "TERM": "linux"}) == tier


@pytest.mark.parametrize("value", ["", "auto", "not-a-tier"])
def test_invalid_override(value):
    with pytest.raises(ValueError):
        caps.detect_tier({"AAV_GLYPHS": value})


@pytest.mark.parametrize(
    "env,expected",
    [
        ({}, "half"),
        ({"TERM": "linux"}, "ascii"),
        ({"TERM": "dumb"}, "ascii"),
        ({"TERM": "xterm-kitty"}, "octant"),
        ({"TERM_PROGRAM": "kitty"}, "octant"),
        ({"TERM_PROGRAM": "WezTerm"}, "half"),
        ({"TERM_PROGRAM": "ghostty"}, "half"),
        ({"TERM": "foot"}, "half"),
    ],
)
def test_terminal_defaults(env, expected):
    assert caps.detect_tier(env) == expected


def test_aspect(monkeypatch):
    monkeypatch.setattr(caps.fcntl, "ioctl", lambda *_: struct.pack("HHHH", 45, 190, 1330, 707))
    assert caps.cell_aspect(1) == pytest.approx(707 * 190 / (1330 * 45))
    monkeypatch.setattr(caps.fcntl, "ioctl", lambda *_: b"\0" * 8)
    assert caps.cell_aspect(1) == 2
    assert caps.cell_aspect(-1) == 2


def test_budget():
    assert caps.budget_tier("octant", 190, 45) == "octant"
    assert caps.budget_tier("octant", 300, 80) == "quadrant"
    assert caps.budget_tier("quadrant", 400, 100) == "half"
    assert caps.budget_tier("ascii", 400, 100) == "ascii"
    assert caps.budget_tier("half", 1000, 1000) == "half"
    with pytest.raises(ValueError):
        caps.budget_tier("octant", -1, 20)
