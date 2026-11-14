"""Omarchy resolution precedence, partial fills, and error handling."""

import os
import shutil
from pathlib import Path

import pytest

from agentic_av.omarchy import generation_token, load_omarchy, slugify
from agentic_av.palette import PaletteError

FIXTURE = Path(__file__).parent / "fixtures" / "omarchy"


def _state(tmp_path: Path, palette: str) -> tuple[Path, dict[str, str]]:
    state = tmp_path / "state" / "omarchy" / "current"
    (state / "theme").mkdir(parents=True, exist_ok=True)
    (state / "theme.name").write_text("sample-theme\n", encoding="utf-8")
    shutil.copyfile(FIXTURE / palette, state / "theme" / "colors.toml")
    (state / "theme.generation").write_text("7", encoding="utf-8")
    return state, {
        "XDG_STATE_HOME": str(tmp_path / "state"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
    }


def test_applied_palette_maps_exact_and_partial_roles(tmp_path: Path) -> None:
    state, env = _state(tmp_path, "full.toml")
    full = load_omarchy(state_dir=state, env=env)
    assert full.slug == "sample-theme"
    assert full.palette.accent == "#974780"
    assert full.palette.foreground == "#fff5c8"
    assert full.colors_path == state / "theme" / "colors.toml"

    state, env = _state(tmp_path, "partial.toml")
    partial = load_omarchy(state_dir=state, env=env)
    assert partial.palette.dark is False
    assert partial.palette.accent == "#205ea6"
    assert partial.palette.warning
    assert partial.palette.border


def test_missing_or_malformed_omarchy_fails_closed(tmp_path: Path) -> None:
    absent = tmp_path / "missing"
    with pytest.raises(PaletteError, match="not found"):
        load_omarchy(state_dir=absent, env={"XDG_CONFIG_HOME": str(tmp_path / "empty")})

    state, env = _state(tmp_path, "empty.toml")
    with pytest.raises(PaletteError, match="background, foreground, and accent"):
        load_omarchy(state_dir=state, env=env)


def test_theme_search_falls_back_to_user_or_stock_slug(tmp_path: Path) -> None:
    state = tmp_path / "state" / "omarchy" / "current"
    state.mkdir(parents=True)
    (state / "theme.name").write_text("Flexoki Light", encoding="utf-8")
    user_root = tmp_path / "config" / "omarchy" / "themes" / "flexoki-light"
    user_root.mkdir(parents=True)
    shutil.copyfile(FIXTURE / "partial.toml", user_root / "colors.toml")
    theme = load_omarchy(state_dir=state, env={"XDG_CONFIG_HOME": str(tmp_path / "config")})
    assert theme.slug == "flexoki-light"
    assert theme.colors_path == user_root / "colors.toml"


def test_generation_token_changes_on_color_update(tmp_path: Path) -> None:
    state, _ = _state(tmp_path, "full.toml")
    before = generation_token(state)
    colors = state / "theme" / "colors.toml"
    colors.write_text(colors.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
    assert generation_token(state) != before


def test_user_fallback_edit_changes_generation_token(tmp_path: Path) -> None:
    """Editing a user fallback palette must move the token the live sync compares."""
    state = tmp_path / "state" / "omarchy" / "current"
    state.mkdir(parents=True)
    (state / "theme.name").write_text("Flexoki Light\n", encoding="utf-8")
    colors = tmp_path / "config" / "omarchy" / "themes" / "flexoki-light" / "colors.toml"
    colors.parent.mkdir(parents=True)
    shutil.copyfile(FIXTURE / "partial.toml", colors)
    env = {
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "OMARCHY_PATH": str(tmp_path / "missing-stock"),
    }
    before = load_omarchy(state_dir=state, env=env)
    assert before.colors_path == colors
    direct = generation_token(state, env=env)
    assert direct == before.generation
    colors.write_text(colors.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
    after = load_omarchy(state_dir=state, env=env)
    assert after.colors_path == colors
    assert after.generation != before.generation
    assert generation_token(state, env=env) == after.generation


def test_stock_fallback_edit_changes_generation_token(tmp_path: Path) -> None:
    """A stock fallback is part of the token when no applied or user palette exists."""
    state = tmp_path / "state" / "omarchy" / "current"
    state.mkdir(parents=True)
    (state / "theme.name").write_text("aav-stock-fixture\n", encoding="utf-8")
    colors = tmp_path / "share" / "themes" / "aav-stock-fixture" / "colors.toml"
    colors.parent.mkdir(parents=True)
    shutil.copyfile(FIXTURE / "partial.toml", colors)
    env = {
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "OMARCHY_PATH": str(tmp_path / "share"),
    }
    before = load_omarchy(state_dir=state, env=env)
    assert before.colors_path == colors
    colors.write_text(colors.read_text(encoding="utf-8") + "\n# stock edit\n", encoding="utf-8")
    after = load_omarchy(state_dir=state, env=env)
    assert after.generation != before.generation


def test_slugify_display_name() -> None:
    assert slugify("Tokyo Night") == "tokyo-night"
    assert slugify(" take3 ") == "take3"


def test_live_omarchy_palette_when_installed() -> None:
    path = (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
        / "omarchy/current/theme/colors.toml"
    )
    if not path.is_file():
        pytest.skip("no active Omarchy theme on this machine")
    assert load_omarchy().palette.accent.startswith("#")
