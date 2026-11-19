"""App icon variants, saved choice, and Linux desktop installation."""

from pathlib import Path

import pytest

from agentic_av.cli import main
from agentic_av.icons import (
    DEFAULT_VARIANT,
    IconError,
    desktop_path,
    install,
    installed_variant,
    load_variant,
    menubar_files,
    pick_variant,
    save_variant,
    variant_description,
    variant_dir,
    variant_names,
)


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
    ) == 'variant = "red-orange"\n'
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
