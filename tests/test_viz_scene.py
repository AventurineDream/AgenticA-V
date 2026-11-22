"""Cover immutable scene boundaries, registry failure behavior, and generic composition."""

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from clangor_visualis_machina.viz.albums import build_scene
from clangor_visualis_machina.viz.albums.generic import GenericScene
from clangor_visualis_machina.viz.audio import SILENT
from clangor_visualis_machina.viz.scene import Frame, Movement
from clangor_visualis_machina.viz.surface import Surface


def _movement():
    return Movement("unknown", 0, 1, "Test", "ribbons", "Ribbons", 60, (), None, None, 13)


def test_metadata_is_frozen():
    movement = _movement()
    with pytest.raises(FrozenInstanceError):
        movement.seed = 2
    frame = Frame(1, 2, 0.1, 1, 0.5, SILENT, None, None, None)
    with pytest.raises(FrozenInstanceError):
        frame.dt = 2


def test_unknown_registry_uses_generic():
    assert isinstance(build_scene(_movement()), GenericScene)


def test_known_import_failure_is_not_hidden(monkeypatch):
    from dataclasses import replace

    import clangor_visualis_machina.viz.albums as albums

    def broken(_module):
        raise ImportError("broken album")

    monkeypatch.setattr(albums, "import_module", broken)
    with pytest.raises(ImportError, match="broken album"):
        build_scene(replace(_movement(), family="coupon"))


def test_generic_is_deterministic_alive_and_finite():
    pictures = []
    for _ in range(2):
        surface = Surface(40, 12, 2, 4)
        scene = GenericScene(_movement())
        scene.resize(surface)
        sequence = []
        for t in (0, 1, 9):
            scene.render(surface, Frame(t, t, 0.1, 1, t / 60, SILENT, None, None, None))
            assert np.isfinite(surface.rgb).all()
            assert np.ptp(surface.rgb) > 0.01
            sequence.append(surface.rgb.copy())
        pictures.append(sequence)
    np.testing.assert_array_equal(pictures[0], pictures[1])
    assert not np.array_equal(pictures[0][0], pictures[0][-1])
