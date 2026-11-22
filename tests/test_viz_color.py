"""Check Paint's exact transfer function, perceptual interpolation, and palette contracts."""

import numpy as np
import pytest

from clangor_visualis_machina.viz import color


def test_linear_exact_transfer_and_dtype():
    np.testing.assert_array_equal(color.linear("#000000"), np.zeros(3, np.float32))
    np.testing.assert_allclose(color.linear("#ffffff"), 1, atol=1e-7)
    encoded = np.array([10, 11, 128], np.float32) / 255
    expected = np.where(encoded <= 0.04045, encoded / 12.92, ((encoded + 0.055) / 1.055) ** 2.4)
    result = color.linear("#0a0B80")
    assert result.dtype == np.float32
    np.testing.assert_allclose(result, expected, rtol=1e-6)


@pytest.mark.parametrize("value", ["red", "fff", "#fff", "#gg0000", "#00000000", None])
def test_linear_rejects_malformed_hex(value):
    with pytest.raises(ValueError):
        color.linear(value)


def test_oklab_roundtrip_for_images_and_hdr():
    rgb = np.random.default_rng(7).uniform(-0.02, 3, (11, 17, 3)).astype(np.float32)
    lab = color.to_oklab(rgb)
    assert lab.shape == rgb.shape
    assert lab.dtype == np.float32
    np.testing.assert_allclose(color.from_oklab(lab), rgb, rtol=1e-4, atol=5e-6)
    np.testing.assert_allclose(color.to_oklab([1, 1, 1]), [1, 0, 0], atol=2e-7)


def test_mix_broadcasts_in_oklab_not_rgb():
    t = np.linspace(0, 1, 15, dtype=np.float32).reshape(3, 5)
    result = color.mix("#000000", "#ffffff", t)
    assert result.shape == (3, 5, 3)
    np.testing.assert_allclose(result[..., 0], t**3, atol=1e-6)
    np.testing.assert_allclose(result[0, 0], 0, atol=1e-7)
    np.testing.assert_allclose(result[-1, -1], 1, atol=1e-6)


def test_ramp_endpoints_nonuniform_stops_and_owned_result():
    stops = ["#123456", "#ff8811", "#eeeeff"]
    result = color.ramp(stops, n=21, positions=[0, 0.25, 1])
    assert result.shape == (21, 3)
    assert result.dtype == np.float32
    np.testing.assert_array_equal(result[0], color.linear(stops[0]))
    np.testing.assert_allclose(result[5], color.linear(stops[1]), atol=1e-6)
    np.testing.assert_array_equal(result[-1], color.linear(stops[-1]))


@pytest.mark.parametrize("positions", [[0, 0, 1], [0.1, 0.5, 1], [0, 0.5, 0.9], [0, 1]])
def test_ramp_rejects_invalid_positions(positions):
    with pytest.raises(ValueError):
        color.ramp(["#000000", "#555555", "#ffffff"], positions=positions)


def test_shade_scales_lightness_and_chroma():
    rgb = color.linear("#996633")
    lab = color.to_oklab(rgb)
    result = color.to_oklab(color.shade(rgb, lightness=0.8, chroma=0.3))
    np.testing.assert_allclose(result, lab * [0.8, 0.3, 0.3], atol=1e-6)
    with pytest.raises(ValueError):
        color.shade(rgb, chroma=-1)
