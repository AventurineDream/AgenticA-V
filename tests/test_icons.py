"""App icon variants, saved choice, theme follow, and Linux desktop installation."""

import re
from pathlib import Path

import pytest

from agentic_av.cli import main
from agentic_av.icons import (
    _VARIANT_BODY,
    _VARIANT_PLATE,
    DEFAULT_VARIANT,
    IconError,
    IconPreferences,
    desktop_path,
    icon_root,
    install,
    installed_menubar,
    installed_variant,
    load_follow_theme,
    load_preferences,
    load_variant,
    menubar_files,
    pick_variant,
    resolve_variant,
    save_follow_theme,
    save_variant,
    sync_followed_icon,
    variant_description,
    variant_dir,
    variant_names,
)
from agentic_av.palette import PaletteError, palette_from_omarchy


def _xdg(tmp_path: Path) -> dict[str, str]:
    """Return XDG overrides pointing at throwaway config and data homes."""
    return {
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
    }


def test_variants_list_nine_with_default_first() -> None:
    names = variant_names()
    assert names[0] == DEFAULT_VARIANT
    assert len(names) == 9
    assert set(names) == {
        "default",
        "red-orange",
        "yellow-orange",
        "yellow-green",
        "blue-green",
        "blue-violet",
        "red-violet",
        "mono-dark",
        "mono-light",
    }
    for name in names:
        assert variant_description(name)
        assert variant_dir(name).is_dir()
        assert (variant_dir(name) / "AppIcon-1024.png").is_file()
        assert (variant_dir(name) / "AppIcon.svg").is_file()
        assert (variant_dir(name) / "AppIcon.icns").is_file()
    assert len(menubar_files()) == 3


def test_unknown_variant_rejected() -> None:
    with pytest.raises(IconError, match="unknown icon variant 'nope'"):
        variant_description("nope")
    with pytest.raises(IconError, match="unknown icon variant 'nope'"):
        variant_dir("nope")


def test_load_variant_falls_back_on_bad_file(tmp_path: Path) -> None:
    env = _xdg(tmp_path)
    assert load_variant(env=env) == DEFAULT_VARIANT
    target = Path(env["XDG_CONFIG_HOME"]) / "agentic-av" / "icons.toml"
    target.parent.mkdir(parents=True)
    target.write_text('variant = "nope"\n', encoding="utf-8")
    assert load_variant(env=env) == DEFAULT_VARIANT
    target.write_text("not toml at all [[[\n", encoding="utf-8")
    assert load_variant(env=env) == DEFAULT_VARIANT


def test_pick_saves_preference_and_installs(tmp_path: Path) -> None:
    env = _xdg(tmp_path)
    data = Path(env["XDG_DATA_HOME"])
    result = pick_variant("red-orange", env=env, data_home=data, refresh=False)
    assert result.variant == "red-orange"
    assert load_variant(env=env) == "red-orange"
    assert (Path(env["XDG_CONFIG_HOME"]) / "agentic-av" / "icons.toml").read_text(
        encoding="utf-8"
    ) == 'variant = "red-orange"\nfollow_theme = false\n'
    desktop = result.desktop_path
    assert desktop == data / "applications" / "agentic-av.desktop"
    text = desktop.read_text(encoding="utf-8")
    assert "Exec=" in text and text.split("Exec=")[1].splitlines()[0].endswith("aav play")
    assert "TryExec=" in text and text.split("TryExec=")[1].splitlines()[0].endswith("aav")
    assert "Terminal=true" in text
    assert "Icon=agentic-av" in text
    assert len(result.icon_paths) == 7
    for size in (16, 32, 64, 128, 256, 512, 1024):
        installed = data / "icons" / "hicolor" / f"{size}x{size}" / "apps" / "agentic-av.png"
        assert installed in result.icon_paths
        assert installed.is_file()
    source = variant_dir("red-orange") / "AppIcon-1024.png"
    installed_1024 = data / "icons" / "hicolor" / "1024x1024" / "apps" / "agentic-av.png"
    assert installed_1024.read_bytes() == source.read_bytes()
    assert installed_variant(env=env, data_home=data) == "red-orange"


def test_install_uses_saved_variant_then_default(tmp_path: Path) -> None:
    env = _xdg(tmp_path)
    data = Path(env["XDG_DATA_HOME"])
    result = install(env=env, data_home=data, refresh=False)
    assert result.variant == DEFAULT_VARIANT
    assert installed_variant(env=env, data_home=data) == DEFAULT_VARIANT
    save_variant("blue-green", env=env)
    result = install(env=env, data_home=data, refresh=False)
    assert result.variant == "blue-green"
    assert installed_variant(env=env, data_home=data) == "blue-green"


def test_install_replaces_previous_variant(tmp_path: Path) -> None:
    env = _xdg(tmp_path)
    data = Path(env["XDG_DATA_HOME"])
    pick_variant("red-orange", env=env, data_home=data, refresh=False)
    first = (data / "icons" / "hicolor" / "1024x1024" / "apps" / "agentic-av.png").read_bytes()
    pick_variant("blue-green", env=env, data_home=data, refresh=False)
    second = (data / "icons" / "hicolor" / "1024x1024" / "apps" / "agentic-av.png").read_bytes()
    assert first != second
    assert installed_variant(env=env, data_home=data) == "blue-green"


def test_installed_variant_none_when_absent(tmp_path: Path) -> None:
    env = _xdg(tmp_path)
    assert installed_variant(env=env, data_home=Path(env["XDG_DATA_HOME"])) is None


def test_install_without_cache_tools_still_succeeds(tmp_path: Path, monkeypatch) -> None:
    env = _xdg(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path))
    result = install(env=env, data_home=Path(env["XDG_DATA_HOME"]), refresh=True)
    assert result.refreshed is False
    assert result.desktop_path.is_file()


def test_install_on_macos_reports_unsupported(tmp_path: Path) -> None:
    env = _xdg(tmp_path)
    data = Path(env["XDG_DATA_HOME"])
    with pytest.raises(IconError, match="no macOS app bundle"):
        install("default", env=env, data_home=data, platform="darwin")
    with pytest.raises(IconError, match="saved mono-dark"):
        pick_variant("mono-dark", env=env, data_home=data, platform="darwin")
    assert load_variant(env=env) == "mono-dark"


def test_cli_icons_list_show_and_unknown(tmp_path: Path, monkeypatch, capsys) -> None:
    env = _xdg(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", env["XDG_CONFIG_HOME"])
    monkeypatch.setenv("XDG_DATA_HOME", env["XDG_DATA_HOME"])
    assert main(["icons", "list"]) == 0
    listed = capsys.readouterr().out
    for name in variant_names():
        assert name in listed
    assert "← saved" in listed
    assert main(["icons"]) == 0
    assert "AAV ICONS" in capsys.readouterr().out
    assert main(["icons", "show"]) == 0
    shown = capsys.readouterr().out
    assert "Saved icon: default" in shown
    assert "Installed icon: none" in shown
    assert main(["icons", "pick", "nope"]) == 2
    assert "unknown icon variant 'nope'" in capsys.readouterr().err


def test_cli_icons_pick_installs_and_shows(tmp_path: Path, monkeypatch, capsys) -> None:
    env = _xdg(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", env["XDG_CONFIG_HOME"])
    monkeypatch.setenv("XDG_DATA_HOME", env["XDG_DATA_HOME"])
    assert main(["icons", "pick", "mono-dark"]) == 0
    picked = capsys.readouterr().out
    assert "Icon set to mono-dark." in picked
    assert main(["icons", "show"]) == 0
    shown = capsys.readouterr().out
    assert "Saved icon: mono-dark" in shown
    assert "Installed icon: mono-dark" in shown
    assert "present" in shown
    assert desktop_path(env=env).is_file()


def test_install_also_installs_menubar_template(tmp_path: Path) -> None:
    env = _xdg(tmp_path)
    data = Path(env["XDG_DATA_HOME"])
    result = pick_variant("default", env=env, data_home=data, refresh=False)
    assert len(result.menubar_paths) == 3
    expected = {
        18: "MenuBarIconTemplate.png",
        36: "MenuBarIconTemplate@2x.png",
        54: "MenuBarIconTemplate@3x.png",
    }
    for size, filename in expected.items():
        installed = (
            data / "icons" / "hicolor" / f"{size}x{size}" / "apps" / "agentic-av-menubar.png"
        )
        assert installed in result.menubar_paths
        assert installed.is_file()
        assert installed.read_bytes() == (icon_root() / "menubar" / filename).read_bytes()
    assert installed_menubar(env=env, data_home=data) == (18, 36, 54)


def test_menubar_absent_reports_none(tmp_path: Path) -> None:
    env = _xdg(tmp_path)
    assert installed_menubar(env=env, data_home=Path(env["XDG_DATA_HOME"])) == ()


def test_cli_icons_show_reports_menubar(tmp_path: Path, monkeypatch, capsys) -> None:
    env = _xdg(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", env["XDG_CONFIG_HOME"])
    monkeypatch.setenv("XDG_DATA_HOME", env["XDG_DATA_HOME"])
    assert main(["icons", "show"]) == 0
    assert "Menu-bar template: none" in capsys.readouterr().out
    assert main(["icons", "pick", "default"]) == 0
    assert main(["icons", "show"]) == 0
    shown = capsys.readouterr().out
    assert "Menu-bar template: installed (18, 36, 54 px)" in shown


def _omarchy_state(tmp_path: Path, *, slug: str, colors: dict[str, str]) -> Path:
    """Build a fake Omarchy `current` state dir and return it."""
    state = tmp_path / "omarchy" / "current"
    (state / "theme").mkdir(parents=True)
    (state / "theme.name").write_text(slug, encoding="utf-8")
    lines = [f'{key} = "{value}"' for key, value in colors.items()]
    (state / "theme" / "colors.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return state


_BLACKWATER_COLORS = {
    "mode": "dark",
    "background": "#141312",
    "foreground": "#E6D8CF",
    "accent": "#E4D0C5",
}

_LAVENDER_RAIN_COLORS = {
    "mode": "dark",
    "background": "#0B1210",
    "foreground": "#DFE7DA",
    "accent": "#C9B8E0",
}

_LIGHT_COLORS = {
    "mode": "light",
    "background": "#f1e9d6",
    "foreground": "#262524",
    "accent": "#a84336",
}


def test_preferences_default_follow_off_and_round_trip(tmp_path: Path) -> None:
    env = _xdg(tmp_path)
    assert load_preferences(env=env) == IconPreferences(DEFAULT_VARIANT, False)
    assert load_follow_theme(env=env) is False
    target = save_follow_theme(True, env=env)
    assert load_follow_theme(env=env) is True
    assert load_variant(env=env) == DEFAULT_VARIANT
    assert target.read_text(encoding="utf-8") == 'variant = "default"\nfollow_theme = true\n'
    save_variant("blue-green", env=env)
    assert load_preferences(env=env) == IconPreferences("blue-green", True)


def test_pick_disables_follow(tmp_path: Path) -> None:
    env = _xdg(tmp_path)
    data = Path(env["XDG_DATA_HOME"])
    save_follow_theme(True, env=env)
    result = pick_variant("red-orange", env=env, data_home=data, refresh=False)
    assert result.variant == "red-orange"
    assert load_follow_theme(env=env) is False
    assert load_variant(env=env) == "red-orange"


def test_resolve_variant_override_blackwater() -> None:
    palette = palette_from_omarchy(_BLACKWATER_COLORS, "blackwater")
    assert resolve_variant(palette, "blackwater") == "mono-dark"


def test_resolve_variant_fallback_dark_themes() -> None:
    palette = palette_from_omarchy(_LAVENDER_RAIN_COLORS, "lavender-rain")
    assert palette.dark is True
    assert resolve_variant(palette, "lavender-rain") == "mono-dark"


def test_resolve_variant_fallback_light_theme() -> None:
    palette = palette_from_omarchy(_LIGHT_COLORS, "newsprint")
    assert palette.dark is False
    assert resolve_variant(palette, "newsprint") == "mono-light"


def test_resolve_variant_prefers_closest_plate() -> None:
    palette = palette_from_omarchy(
        {
            "mode": "dark",
            "background": "#5e2419",
            "foreground": "#f2f1e5",
            "accent": "#51c8b8",
        },
        "rusty",
    )
    assert resolve_variant(palette, "rusty") == "blue-green"


def _gradient_stops(svg: str, gradient_id: str) -> list[str]:
    """Return the stop colors of one SVG gradient, in order."""
    match = re.search(
        rf'<(?:linear|radial)Gradient id="{gradient_id}"[^>]*>(.*?)</(?:linear|radial)Gradient>',
        svg,
        re.S,
    )
    assert match is not None, f"missing gradient {gradient_id}"
    return re.findall(r'stop-color="([^"]+)"', match.group(1))


def test_variant_plate_colors_match_svgs() -> None:
    """The follow tables stay pinned to the shipped SVG masters."""
    for name in variant_names():
        svg = (variant_dir(name) / "AppIcon.svg").read_text(encoding="utf-8")
        plate = _gradient_stops(svg, "plate")
        assert len(plate) == 3
        assert plate[1].lower() == _VARIANT_PLATE[name]
        body = _gradient_stops(svg, "bg1")
        assert body[0].lower() == _VARIANT_BODY[name]


def test_install_writes_scalable_svg(tmp_path: Path) -> None:
    env = _xdg(tmp_path)
    data = Path(env["XDG_DATA_HOME"])
    result = pick_variant("mono-dark", env=env, data_home=data, refresh=False)
    svg = data / "icons" / "hicolor" / "scalable" / "apps" / "agentic-av.svg"
    assert result.svg_path == svg
    assert svg.is_file()
    assert svg.read_bytes() == (variant_dir("mono-dark") / "AppIcon.svg").read_bytes()


def test_install_removes_stale_unmanaged_sizes(tmp_path: Path) -> None:
    env = _xdg(tmp_path)
    data = Path(env["XDG_DATA_HOME"])
    stale_paths = []
    for size in (22, 24, 48):
        stale = data / "icons" / "hicolor" / f"{size}x{size}" / "apps" / "agentic-av.png"
        stale.parent.mkdir(parents=True)
        stale.write_bytes(b"stale")
        stale_paths.append(stale)
    result = install(env=env, data_home=data, refresh=False)
    assert result.removed_stale == tuple(stale_paths)
    for stale in stale_paths:
        assert not stale.exists()
    for size in (16, 32, 64, 128, 256, 512, 1024):
        assert (data / "icons" / "hicolor" / f"{size}x{size}" / "apps" / "agentic-av.png").is_file()


def test_sync_followed_icon_installs_and_skips_when_current(tmp_path: Path) -> None:
    env = _xdg(tmp_path)
    data = Path(env["XDG_DATA_HOME"])
    state = _omarchy_state(tmp_path, slug="blackwater", colors=_BLACKWATER_COLORS)
    save_follow_theme(True, env=env)
    resolved = sync_followed_icon(env=env, data_home=data, refresh=False, state_dir=state)
    assert resolved == "mono-dark"
    assert installed_variant(env=env, data_home=data) == "mono-dark"
    target = data / "icons" / "hicolor" / "1024x1024" / "apps" / "agentic-av.png"
    mtime = target.stat().st_mtime_ns
    resolved = sync_followed_icon(env=env, data_home=data, refresh=False, state_dir=state)
    assert resolved == "mono-dark"
    assert target.stat().st_mtime_ns == mtime


def test_sync_followed_icon_returns_none_when_off(tmp_path: Path) -> None:
    env = _xdg(tmp_path)
    data = Path(env["XDG_DATA_HOME"])
    state = _omarchy_state(tmp_path, slug="blackwater", colors=_BLACKWATER_COLORS)
    assert sync_followed_icon(env=env, data_home=data, refresh=False, state_dir=state) is None
    assert installed_variant(env=env, data_home=data) is None


def test_sync_followed_icon_raises_without_omarchy(tmp_path: Path) -> None:
    env = _xdg(tmp_path)
    data = Path(env["XDG_DATA_HOME"])
    save_follow_theme(True, env=env)
    with pytest.raises(PaletteError, match="Omarchy theme not found"):
        sync_followed_icon(env=env, data_home=data, refresh=False, state_dir=tmp_path / "no-state")


def test_cli_icons_follow_show_and_pick(tmp_path: Path, monkeypatch, capsys) -> None:
    env = _xdg(tmp_path)
    _omarchy_state(tmp_path, slug="blackwater", colors=_BLACKWATER_COLORS)
    monkeypatch.setenv("XDG_CONFIG_HOME", env["XDG_CONFIG_HOME"])
    monkeypatch.setenv("XDG_DATA_HOME", env["XDG_DATA_HOME"])
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert main(["icons", "follow"]) == 0
    followed = capsys.readouterr().out
    assert "Icon follow is on: mono-dark matches the live Omarchy theme (blackwater)." in followed
    assert load_follow_theme(env=env) is True
    assert installed_variant(env=env, data_home=Path(env["XDG_DATA_HOME"])) == "mono-dark"
    assert main(["icons", "list"]) == 0
    assert "← followed (live theme)" in capsys.readouterr().out
    assert main(["icons", "show"]) == 0
    shown = capsys.readouterr().out
    assert "Follow theme: on" in shown
    assert "Followed variant: mono-dark (live theme: blackwater)" in shown
    assert "Installed icon: mono-dark" in shown
    assert main(["icons", "pick", "blue-green"]) == 0
    assert "Theme follow is off" in capsys.readouterr().out
    assert load_follow_theme(env=env) is False
    assert main(["icons", "show"]) == 0
    assert "Follow theme: off" in capsys.readouterr().out


def test_cli_icons_follow_without_omarchy(tmp_path: Path, monkeypatch, capsys) -> None:
    env = _xdg(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", env["XDG_CONFIG_HOME"])
    monkeypatch.setenv("XDG_DATA_HOME", env["XDG_DATA_HOME"])
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "empty-state"))
    assert main(["icons", "follow"]) == 0
    assert "No Omarchy theme is available right now" in capsys.readouterr().out
    assert load_follow_theme(env=env) is True
