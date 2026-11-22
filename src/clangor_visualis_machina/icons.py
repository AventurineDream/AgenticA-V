"""App icon variants, saved choice, theme follow, and Linux desktop installation.

The piano-camera icon set ships under
``assets/icons/piano-camera-icons-final/``: a ``default/`` set plus eight color
variants, each with a 1024 PNG, SVG masters, a full AppIcon.iconset, and a
macOS .icns. A separate ``menubar/`` template image has no color variants;
macOS tints it, and there is no menu-bar consumer in this repository yet.

The picker is the ``aav icons`` command. It records the user's variant in
``$XDG_CONFIG_HOME/clangor-visualis-machina/icons.toml`` and, on Linux, installs the chosen
set as the app's icon: a ``clangor-visualis-machina.desktop`` launcher plus the iconset
PNGs in the freedesktop hicolor theme under ``$XDG_DATA_HOME``, the variant's
``AppIcon.svg`` as the scalable hicolor icon, and the menu-bar template as
``clangor-visualis-machina-menubar`` at 18/36/54. Only files this app owns are written; no
desktop or Omarchy configuration is edited. macOS has no app bundle in this
repository, so install there reports the .icns location instead of
pretending to install.

``aav icons follow`` turns on theme follow: the installed variant tracks
the live Omarchy theme (an explicit theme-to-variant table first, then the
closest plate/body colors for themes with no dedicated file). A manual
``pick`` turns follow back off. Follow syncs at ``aav play`` startup and
when the live theme changes while the visual player runs.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from clangor_visualis_machina.colorutil import parse_hex, relative_luminance
from clangor_visualis_machina.omarchy import OmarchyTheme, load_omarchy
from clangor_visualis_machina.palette import Palette

DEFAULT_VARIANT = "default"

_VARIANT_DESCRIPTIONS = {
    "default": "orange body on a teal plate",
    "red-orange": "red-orange body on a deep teal plate",
    "yellow-orange": "marigold body on an indigo plate",
    "yellow-green": "lime body on a plum plate",
    "blue-green": "teal body on a rust/brick plate",
    "blue-violet": "violet body on a warm gold plate",
    "red-violet": "magenta body on a forest-green plate",
    "mono-dark": "light grey body on a near-black plate (pure greyscale)",
    "mono-light": "dark grey body on a light grey plate (pure greyscale)",
}

VARIANTS = tuple(_VARIANT_DESCRIPTIONS)

# Explicit Omarchy theme slug -> icon variant. This table wins over the
# color derivation below, so a theme with a dedicated icon file gets the
# intended match instead of the nearest colors. Fog's theme-matched icon
# files plug in here as new variant directories + mapping entries when they
# land; wiring them in is a data change, not a code change.
# TODO(fog-icons): lavender-rain -> its dedicated variant once Fog delivers it.
_THEME_VARIANT_OVERRIDES = {
    "blackwater": "mono-dark",
}

# Mid stop of each variant's `plate` gradient (the tile) and first stop of
# its `bg1` gradient (the camera body), read from the shipped AppIcon.svg
# files. The test `test_variant_plate_colors_match_svgs` pins this table to
# the SVGs, so a Fog recolor fails loudly instead of silently drifting the
# follow derivation. Plate luminance splits cleanly: every dark plate is
# below 0.1, both light plates (blue-violet, mono-light) are above 0.6.
_VARIANT_PLATE = {
    "default": "#1b4656",
    "red-orange": "#154241",
    "yellow-orange": "#2e317a",
    "yellow-green": "#511f47",
    "blue-green": "#5e2419",
    "blue-violet": "#f6b94a",
    "red-violet": "#22401a",
    "mono-dark": "#222222",
    "mono-light": "#dcdcdc",
}

_VARIANT_BODY = {
    "default": "#ffc53d",
    "red-orange": "#ed7050",
    "yellow-orange": "#ffcf4c",
    "yellow-green": "#badb68",
    "blue-green": "#51c8b8",
    "blue-violet": "#8d80f5",
    "red-violet": "#dc67a1",
    "mono-dark": "#e8e8e8",
    "mono-light": "#727272",
}

# hicolor size -> iconset file holding a PNG of exactly that pixel size.
_HICOLOR_PNGS = {
    16: "AppIcon.iconset/icon_16x16.png",
    32: "AppIcon.iconset/icon_32x32.png",
    64: "AppIcon.iconset/icon_32x32@2x.png",
    128: "AppIcon.iconset/icon_128x128.png",
    256: "AppIcon.iconset/icon_256x256.png",
    512: "AppIcon.iconset/icon_512x512.png",
    1024: "AppIcon-1024.png",
}

# Sizes the installer never writes. A copy of this app's icon at one of
# these sizes can only be a leftover hand-install; install removes it so a
# dock cannot keep showing a stale file after a pick.
_STALE_UNMANAGED_SIZES = (22, 24, 48)

# Menu-bar template size -> template file. The template has no color
# variants; it is installed identically for every variant.
_MENUBAR_HICOLOR = {
    18: "MenuBarIconTemplate.png",
    36: "MenuBarIconTemplate@2x.png",
    54: "MenuBarIconTemplate@3x.png",
}

_MENUBAR_FILES = (
    "MenuBarIconTemplate.png",
    "MenuBarIconTemplate@2x.png",
    "MenuBarIconTemplate@3x.png",
)


class IconError(ValueError):
    """An icon variant, asset, or install target is missing or unsupported."""


@dataclass(frozen=True, slots=True)
class InstallResult:
    """Files written by an icon install."""

    variant: str
    desktop_path: Path
    icon_paths: tuple[Path, ...]
    refreshed: bool
    menubar_paths: tuple[Path, ...] = ()
    svg_path: Path | None = None
    removed_stale: tuple[Path, ...] = ()


def icon_root(*, root: Path | None = None) -> Path:
    """Return the bundled piano-camera icon set directory.

    Args:
        root: Optional icon set directory override, primarily for tests.

    Returns:
        The ``assets/icons/piano-camera-icons-final`` directory.
    """
    if root is not None:
        return root
    return Path(__file__).resolve().parents[2] / "assets" / "icons" / "piano-camera-icons-final"


def variant_names() -> tuple[str, ...]:
    """Return the installable variant names, default first."""
    return VARIANTS


def variant_description(name: str) -> str:
    """Return the one-line description for a variant.

    Args:
        name: Variant name, or ``default``.

    Raises:
        IconError: The name is not a known variant.
    """
    try:
        return _VARIANT_DESCRIPTIONS[name]
    except KeyError as error:
        raise IconError(
            f"unknown icon variant {name!r}; variants: {', '.join(VARIANTS)}"
        ) from error


def variant_dir(name: str, *, root: Path | None = None) -> Path:
    """Return the asset directory for a variant.

    Args:
        name: Variant name, or ``default``.
        root: Optional icon set directory override, primarily for tests.

    Raises:
        IconError: The name is not a known variant, or its directory is absent.
    """
    variant_description(name)
    directory = icon_root(root=root) / (name if name == DEFAULT_VARIANT else f"variants/{name}")
    if not directory.is_dir():
        raise IconError(f"icon variant {name!r} is missing from {directory}")
    return directory


def menubar_files(*, root: Path | None = None) -> tuple[Path, ...]:
    """Return the menu-bar template images that exist in the icon set.

    Args:
        root: Optional icon set directory override, primarily for tests.
    """
    menubar = icon_root(root=root) / "menubar"
    return tuple(path for path in (menubar / name for name in _MENUBAR_FILES) if path.is_file())


def _config_home(env: dict[str, str] | None) -> Path:
    """Resolve the XDG config location; the environment override is injectable."""
    variables = os.environ if env is None else env
    return Path(variables.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def _data_home(env: dict[str, str] | None) -> Path:
    """Resolve the XDG data location; the environment override is injectable."""
    variables = os.environ if env is None else env
    return Path(variables.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))


def config_path(*, env: dict[str, str] | None = None, path: Path | None = None) -> Path:
    """Return the icon preference file path.

    Args:
        env: Optional environment mapping for XDG overrides.
        path: Optional explicit preference path, primarily for tests.
    """
    if path is not None:
        return path
    return _config_home(env) / "clangor-visualis-machina" / "icons.toml"


@dataclass(frozen=True, slots=True)
class IconPreferences:
    """Saved icon choice: the manual variant and whether follow is on."""

    variant: str
    follow_theme: bool


def load_preferences(
    *, env: dict[str, str] | None = None, path: Path | None = None
) -> IconPreferences:
    """Return the saved icon preferences, or the defaults when none are saved.

    A missing preference file, an unreadable one, or a hand-edited value
    that is not a known variant all fall back to the default variant with
    follow off instead of failing.

    Args:
        env: Optional environment mapping for XDG overrides.
        path: Optional explicit preference path, primarily for tests.
    """
    try:
        data = tomllib.loads(config_path(env=env, path=path).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return IconPreferences(DEFAULT_VARIANT, False)
    if not isinstance(data, dict):
        return IconPreferences(DEFAULT_VARIANT, False)
    name = data.get("variant")
    variant = name if isinstance(name, str) and name in _VARIANT_DESCRIPTIONS else DEFAULT_VARIANT
    return IconPreferences(variant, data.get("follow_theme") is True)


def save_preferences(
    variant: str,
    follow_theme: bool,
    *,
    env: dict[str, str] | None = None,
    path: Path | None = None,
) -> Path:
    """Save both icon preferences and return the preference file path.

    Args:
        variant: Variant name, or ``default``.
        follow_theme: Whether the installed icon follows the live theme.
        env: Optional environment mapping for XDG overrides.
        path: Optional explicit preference path, primarily for tests.

    Raises:
        IconError: The variant is not a known variant.
        OSError: The preference file cannot be written.
    """
    variant_description(variant)
    target = config_path(env=env, path=path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f'variant = "{variant}"\nfollow_theme = {"true" if follow_theme else "false"}\n',
        encoding="utf-8",
    )
    return target


def load_variant(*, env: dict[str, str] | None = None, path: Path | None = None) -> str:
    """Return the saved icon variant, or ``default`` when none is saved.

    A missing preference file, an unreadable one, or a hand-edited value that
    is not a known variant all fall back to the default instead of failing.

    Args:
        env: Optional environment mapping for XDG overrides.
        path: Optional explicit preference path, primarily for tests.
    """
    return load_preferences(env=env, path=path).variant


def load_follow_theme(*, env: dict[str, str] | None = None, path: Path | None = None) -> bool:
    """Return whether the installed icon follows the live Omarchy theme.

    Defaults to False: existing manual picks keep working, and a missing or
    unreadable preference file never turns follow on by surprise.

    Args:
        env: Optional environment mapping for XDG overrides.
        path: Optional explicit preference path, primarily for tests.
    """
    return load_preferences(env=env, path=path).follow_theme


def save_variant(name: str, *, env: dict[str, str] | None = None, path: Path | None = None) -> Path:
    """Save an icon variant choice, keeping the follow setting, and return the path.

    Args:
        name: Variant name, or ``default``.
        env: Optional environment mapping for XDG overrides.
        path: Optional explicit preference path, primarily for tests.

    Raises:
        IconError: The name is not a known variant.
        OSError: The preference file cannot be written.
    """
    return save_preferences(name, load_follow_theme(env=env, path=path), env=env, path=path)


def save_follow_theme(
    enabled: bool, *, env: dict[str, str] | None = None, path: Path | None = None
) -> Path:
    """Save the theme-follow setting, keeping the manual variant, and return the path.

    Args:
        enabled: Whether the installed icon follows the live Omarchy theme.
        env: Optional environment mapping for XDG overrides.
        path: Optional explicit preference path, primarily for tests.

    Raises:
        OSError: The preference file cannot be written.
    """
    return save_preferences(load_variant(env=env, path=path), enabled, env=env, path=path)


def _color_distance(left: str, right: str) -> int:
    """Return the squared RGB distance between two ``#rrggbb`` colors."""
    a = parse_hex(left)
    b = parse_hex(right)
    if a is None or b is None:
        raise IconError(f"color distance needs #rrggbb, got {left!r} and {right!r}")
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def resolve_variant(palette: Palette, slug: str) -> str:
    """Resolve the icon variant for a live Omarchy theme.

    An explicit theme-slug override wins. Otherwise the variant is the
    closest match among plates of the theme's light/dark family: the plate
    nearest the theme background plus the body nearest the theme accent.
    The family split uses plate luminance, so a dark theme never lands on
    a light plate and a light theme never lands on a dark one.

    Args:
        palette: Live Omarchy palette (background, accent, and dark flag).
        slug: Current Omarchy theme slug for the override table.

    Returns:
        The variant name for the theme.
    """
    override = _THEME_VARIANT_OVERRIDES.get(slug)
    if override is not None:
        return override
    candidates = [
        name
        for name in VARIANTS
        if (relative_luminance(_VARIANT_PLATE[name]) < 0.5) == palette.dark
    ]
    if not candidates:
        candidates = list(VARIANTS)
    return min(
        candidates,
        key=lambda name: (
            _color_distance(palette.background, _VARIANT_PLATE[name])
            + _color_distance(palette.accent, _VARIANT_BODY[name]),
            VARIANTS.index(name),
        ),
    )


def sync_followed_icon(
    *,
    theme: OmarchyTheme | None = None,
    env: dict[str, str] | None = None,
    data_home: Path | None = None,
    executable: Path | None = None,
    platform: str | None = None,
    refresh: bool = True,
    root: Path | None = None,
    state_dir: Path | None = None,
) -> str | None:
    """Install the live theme's variant when follow is on and it differs.

    A no-op when follow is off (returns None) or when the resolved variant
    is already installed, so a theme poll every few seconds does not rewrite
    files or restart the launcher's icon lookup.

    Args:
        theme: Optional already-loaded Omarchy theme, to avoid reloading it.
        env: Optional environment mapping for XDG overrides.
        data_home: Optional XDG data home override, primarily for tests.
        executable: Optional `aav` entry point override, primarily for tests.
        platform: Optional platform override (``sys.platform`` by default).
        refresh: Refresh the desktop and icon caches when their tools exist.
        root: Optional icon set directory override, primarily for tests.
        state_dir: Optional Omarchy `current` state directory, for tests.

    Returns:
        The resolved variant name, or None when follow is off.

    Raises:
        PaletteError: Follow is on but no Omarchy theme can be loaded.
        IconError: The resolved variant cannot be installed.
        OSError: An installed file cannot be written.
    """
    if not load_follow_theme(env=env):
        return None
    current = theme if theme is not None else load_omarchy(state_dir=state_dir, env=env)
    resolved = resolve_variant(current.palette, current.slug)
    if installed_variant(env=env, data_home=data_home, root=root) == resolved:
        return resolved
    install(
        resolved,
        env=env,
        data_home=data_home,
        executable=executable,
        platform=platform,
        refresh=refresh,
        root=root,
    )
    return resolved


def desktop_path(*, env: dict[str, str] | None = None, data_home: Path | None = None) -> Path:
    """Return the launcher entry this app installs for itself.

    Args:
        env: Optional environment mapping for XDG overrides.
        data_home: Optional XDG data home override, primarily for tests.
    """
    home = data_home if data_home is not None else _data_home(env)
    return home / "applications" / "clangor-visualis-machina.desktop"


def _hicolor_path(size: int, *, env: dict[str, str] | None, data_home: Path | None) -> Path:
    """Return the hicolor destination for one icon size."""
    home = data_home if data_home is not None else _data_home(env)
    return home / "icons" / "hicolor" / f"{size}x{size}" / "apps" / "clangor-visualis-machina.png"


def _digest(path: Path) -> str:
    """Return the SHA-256 of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def installed_variant(
    *,
    env: dict[str, str] | None = None,
    data_home: Path | None = None,
    root: Path | None = None,
) -> str | None:
    """Return the variant whose 1024 PNG matches the installed icon, or None.

    The installed set is identified by content, not by a stored name, so a
    hand-edited install still reports honestly. None means no icon is
    installed or it matches no known variant.

    Args:
        env: Optional environment mapping for XDG overrides.
        data_home: Optional XDG data home override, primarily for tests.
        root: Optional icon set directory override, primarily for tests.
    """
    installed = _hicolor_path(1024, env=env, data_home=data_home)
    try:
        digest = _digest(installed)
    except OSError:
        return None
    for name in VARIANTS:
        try:
            if _digest(variant_dir(name, root=root) / "AppIcon-1024.png") == digest:
                return name
        except (IconError, OSError):
            continue
    return None


def installed_menubar(
    *,
    env: dict[str, str] | None = None,
    data_home: Path | None = None,
) -> tuple[int, ...]:
    """Return the installed menu-bar template sizes, or an empty tuple.

    Args:
        env: Optional environment mapping for XDG overrides.
        data_home: Optional XDG data home override, primarily for tests.
    """
    home = data_home if data_home is not None else _data_home(env)
    return tuple(
        size
        for size in _MENUBAR_HICOLOR
        if (
            home
            / "icons"
            / "hicolor"
            / f"{size}x{size}"
            / "apps"
            / "clangor-visualis-machina-menubar.png"
        ).is_file()
    )


def _aav_executable(*, executable: Path | None) -> Path:
    """Return the `aav` entry point for the running installation."""
    if executable is not None:
        return executable
    sibling = Path(sys.executable).parent / "aav"
    if sibling.is_file():
        return sibling
    found = shutil.which("aav")
    if found:
        return Path(found)
    raise IconError("cannot find the aav executable to launch from the desktop entry")


def _quote(value: str) -> str:
    """Quote a desktop-entry value only when it contains a space."""
    return f'"{value}"' if " " in value else value


def _refresh_caches(apps_dir: Path, icons_dir: Path) -> bool:
    """Refresh the desktop and icon caches when their tools exist.

    Missing tools or a failed refresh never fails the install; the launcher
    picks the new icon up on its next scan either way.
    """
    refreshed = True
    for tool, args in (
        ("update-desktop-database", [str(apps_dir)]),
        ("gtk-update-icon-cache", ["-q", str(icons_dir)]),
    ):
        if shutil.which(tool) is None:
            refreshed = False
            continue
        try:
            result = subprocess.run([tool, *args], check=False, capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            refreshed = False
            continue
        refreshed = refreshed and result.returncode == 0
    return refreshed


def install(
    variant: str | None = None,
    *,
    env: dict[str, str] | None = None,
    data_home: Path | None = None,
    executable: Path | None = None,
    platform: str | None = None,
    refresh: bool = True,
    root: Path | None = None,
) -> InstallResult:
    """Install a variant as the app icon on Linux and return what was written.

    Writes the ``clangor-visualis-machina.desktop`` launcher, the variant's iconset PNGs,
    and the variant's ``AppIcon.svg`` as the scalable hicolor icon into the
    hicolor theme. The scalable SVG matters because docks prefer it when
    present; an install that skipped it could leave a stale SVG on screen
    after a pick. Stale copies of this app's icon at sizes the installer
    never writes (22/24/48, left by old hand-installs) are removed for the
    same reason. Only files this app owns are written; no desktop or Omarchy
    configuration is touched.

    Args:
        variant: Variant name, or None to install the saved choice (the
            default when none is saved).
        env: Optional environment mapping for XDG overrides.
        data_home: Optional XDG data home override, primarily for tests.
        executable: Optional `aav` entry point override, primarily for tests.
        platform: Optional platform override (``sys.platform`` by default).
        refresh: Refresh the desktop and icon caches when their tools exist.
        root: Optional icon set directory override, primarily for tests.

    Raises:
        IconError: The variant is unknown, its assets are missing, the
            platform has no app bundle to install into, or the `aav`
            executable cannot be found.
        OSError: A launcher or icon file cannot be written.
    """
    name = load_variant(env=env) if variant is None else variant
    system = sys.platform if platform is None else platform
    if system != "linux":
        if system == "darwin":
            icns = variant_dir(name, root=root) / "AppIcon.icns"
            raise IconError(
                f"no macOS app bundle to install into; the {name} .icns is at {icns} — "
                "see assets/icons/piano-camera-icons-final/README.txt"
            )
        raise IconError(
            f"icon install supports Linux desktop entries; {system} has no install target"
        )
    source = variant_dir(name, root=root)
    launcher = _aav_executable(executable=executable)
    home = data_home if data_home is not None else _data_home(env)
    apps_dir = home / "applications"
    icons_dir = home / "icons" / "hicolor"
    desktop = apps_dir / "clangor-visualis-machina.desktop"
    apps_dir.mkdir(parents=True, exist_ok=True)
    desktop.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=ClangorVisualisMachina\n"
        "Comment=Terminal album library and visual player\n"
        f"Exec={_quote(str(launcher))} play\n"
        f"TryExec={_quote(str(launcher))}\n"
        "Terminal=true\n"
        "Icon=clangor-visualis-machina\n"
        "Categories=AudioVideo;Player;\n",
        encoding="utf-8",
    )
    written: list[Path] = []
    for size, relative in _HICOLOR_PNGS.items():
        target = icons_dir / f"{size}x{size}" / "apps" / "clangor-visualis-machina.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)
        written.append(target)
    svg_target = icons_dir / "scalable" / "apps" / "clangor-visualis-machina.svg"
    svg_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / "AppIcon.svg", svg_target)
    removed_stale: list[Path] = []
    for size in _STALE_UNMANAGED_SIZES:
        stale = icons_dir / f"{size}x{size}" / "apps" / "clangor-visualis-machina.png"
        try:
            stale.unlink()
        except FileNotFoundError:
            continue
        except OSError:
            continue
        removed_stale.append(stale)
    menubar_written: list[Path] = []
    for size, relative in _MENUBAR_HICOLOR.items():
        source_file = icon_root(root=root) / "menubar" / relative
        if not source_file.is_file():
            continue
        target = icons_dir / f"{size}x{size}" / "apps" / "clangor-visualis-machina-menubar.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_file, target)
        menubar_written.append(target)
    refreshed = _refresh_caches(apps_dir, icons_dir) if refresh else False
    return InstallResult(
        variant=name,
        desktop_path=desktop,
        icon_paths=tuple(written),
        menubar_paths=tuple(menubar_written),
        refreshed=refreshed,
        svg_path=svg_target,
        removed_stale=tuple(removed_stale),
    )


def pick_variant(
    name: str,
    *,
    env: dict[str, str] | None = None,
    data_home: Path | None = None,
    executable: Path | None = None,
    platform: str | None = None,
    refresh: bool = True,
    root: Path | None = None,
) -> InstallResult:
    """Save an icon variant choice and install it, returning what was written.

    The preference is saved before the install, so a platform that cannot
    install still keeps the choice for a later install. A manual pick turns
    theme follow off: an explicit choice wins over the live theme.

    Args:
        name: Variant name, or ``default``.
        env: Optional environment mapping for XDG overrides.
        data_home: Optional XDG data home override, primarily for tests.
        executable: Optional `aav` entry point override, primarily for tests.
        platform: Optional platform override (``sys.platform`` by default).
        refresh: Refresh the desktop and icon caches when their tools exist.
        root: Optional icon set directory override, primarily for tests.

    Raises:
        IconError: The name is not a known variant, or the install cannot
            run on this platform. The preference is already saved in the
            latter case.
        OSError: The preference or an installed file cannot be written.
    """
    variant_description(name)
    saved = save_preferences(name, False, env=env)
    try:
        return install(
            name,
            env=env,
            data_home=data_home,
            executable=executable,
            platform=platform,
            refresh=refresh,
            root=root,
        )
    except IconError as error:
        raise IconError(f"saved {name} in {saved}; {error}") from error
