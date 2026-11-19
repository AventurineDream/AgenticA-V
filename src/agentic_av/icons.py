"""App icon variants, saved choice, and Linux desktop installation.

The piano-camera icon set ships under
``assets/icons/piano-camera-icons-final/``: a ``default/`` set plus eight color
variants, each with a 1024 PNG, SVG masters, a full AppIcon.iconset, and a
macOS .icns. A separate ``menubar/`` template image has no color variants;
macOS tints it, and there is no menu-bar consumer in this repository yet.

The picker is the ``aav icons`` command. It records the user's variant in
``$XDG_CONFIG_HOME/agentic-av/icons.toml`` and, on Linux, installs the chosen
set as the app's icon: an ``agentic-av.desktop`` launcher plus the iconset
PNGs in the freedesktop hicolor theme under ``$XDG_DATA_HOME``. Only files
this app owns are written; no desktop or Omarchy configuration is edited.
macOS has no app bundle in this repository, so install there reports the
.icns location instead of pretending to install.
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
    return _config_home(env) / "agentic-av" / "icons.toml"


def load_variant(*, env: dict[str, str] | None = None, path: Path | None = None) -> str:
    """Return the saved icon variant, or ``default`` when none is saved.

    A missing preference file, an unreadable one, or a hand-edited value that
    is not a known variant all fall back to the default instead of failing.

    Args:
        env: Optional environment mapping for XDG overrides.
        path: Optional explicit preference path, primarily for tests.
    """
    try:
        data = tomllib.loads(config_path(env=env, path=path).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return DEFAULT_VARIANT
    name = data.get("variant") if isinstance(data, dict) else None
    return name if isinstance(name, str) and name in _VARIANT_DESCRIPTIONS else DEFAULT_VARIANT


def save_variant(name: str, *, env: dict[str, str] | None = None, path: Path | None = None) -> Path:
    """Save an icon variant choice and return the preference file path.

    Args:
        name: Variant name, or ``default``.
        env: Optional environment mapping for XDG overrides.
        path: Optional explicit preference path, primarily for tests.

    Raises:
        IconError: The name is not a known variant.
        OSError: The preference file cannot be written.
    """
    variant_description(name)
    target = config_path(env=env, path=path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f'variant = "{name}"\n', encoding="utf-8")
    return target


def desktop_path(*, env: dict[str, str] | None = None, data_home: Path | None = None) -> Path:
    """Return the launcher entry this app installs for itself.

    Args:
        env: Optional environment mapping for XDG overrides.
        data_home: Optional XDG data home override, primarily for tests.
    """
    home = data_home if data_home is not None else _data_home(env)
    return home / "applications" / "agentic-av.desktop"


def _hicolor_path(size: int, *, env: dict[str, str] | None, data_home: Path | None) -> Path:
    """Return the hicolor destination for one icon size."""
    home = data_home if data_home is not None else _data_home(env)
    return home / "icons" / "hicolor" / f"{size}x{size}" / "apps" / "agentic-av.png"


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

    Writes the ``agentic-av.desktop`` launcher and the variant's iconset PNGs
    into the hicolor theme. Only files this app owns are written; no desktop
    or Omarchy configuration is touched.

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
    desktop = apps_dir / "agentic-av.desktop"
    apps_dir.mkdir(parents=True, exist_ok=True)
    desktop.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Agentic A/V\n"
        "Comment=Terminal album library and visual player\n"
        f"Exec={_quote(str(launcher))} play\n"
        f"TryExec={_quote(str(launcher))}\n"
        "Terminal=true\n"
        "Icon=agentic-av\n"
        "Categories=AudioVideo;Player;\n",
        encoding="utf-8",
    )
    written: list[Path] = []
    for size, relative in _HICOLOR_PNGS.items():
        target = icons_dir / f"{size}x{size}" / "apps" / "agentic-av.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)
        written.append(target)
    refreshed = _refresh_caches(apps_dir, icons_dir) if refresh else False
    return InstallResult(
        variant=name, desktop_path=desktop, icon_paths=tuple(written), refreshed=refreshed
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
    install still keeps the choice for a later install.

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
    saved = save_variant(name, env=env)
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
