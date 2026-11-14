"""Read Omarchy's active merged theme without changing desktop configuration.

The player uses the applied `colors.toml` first; Omarchy merges stock colors
and user overlays into that file when a theme is set. This module is read-only.
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from agentic_av.palette import Palette, PaletteError, palette_from_omarchy


@dataclass(frozen=True, slots=True)
class OmarchyTheme:
    """Resolved live theme data for rendering and change detection."""

    palette: Palette
    slug: str
    colors_path: Path
    generation: str


def slugify(value: str) -> str:
    """Convert an Omarchy display name to its lowercase directory slug."""
    return re.sub(r"[^a-z0-9]+", "-", value.strip().casefold()).strip("-")


def _state_dir(env: dict[str, str] | None = None) -> Path:
    """Resolve the XDG state location; the environment override is injectable."""
    variables = os.environ if env is None else env
    root = Path(variables.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return root / "omarchy" / "current"


def _candidate_paths(slug: str, state: Path, env: dict[str, str] | None) -> tuple[Path, ...]:
    """Return applied, user, and stock palette paths in precedence order."""
    variables = os.environ if env is None else env
    config_root = Path(variables.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    user_roots = (
        config_root / "omarchy" / "themes",
        Path.home() / ".config" / "omarchy" / "themes",
    )
    omarchy_root = Path(variables.get("OMARCHY_PATH", "/usr/share/omarchy")) / "themes"
    return (
        state / "theme" / "colors.toml",
        *(root / slug / "colors.toml" for root in (*user_roots, omarchy_root)),
    )


def generation_token(state_dir: Path | None = None) -> str:
    """Return a lightweight token that changes with Omarchy theme switches."""
    state = _state_dir() if state_dir is None else state_dir
    name = state / "theme.name"
    generation = state / "theme.generation"
    color_file = state / "theme" / "colors.toml"
    pieces: list[str] = []
    for path in (name, generation, color_file):
        try:
            stat = path.stat()
            value = path.read_text(encoding="utf-8").strip() if path.is_file() else ""
            pieces.append(f"{value}:{stat.st_mtime_ns}:{stat.st_size}")
        except OSError:
            pieces.append("missing")
    return "|".join(pieces)


def load_omarchy(
    *, state_dir: Path | None = None, env: dict[str, str] | None = None
) -> OmarchyTheme:
    """Load the active Omarchy colors and map them into player roles.

    Args:
        state_dir: Optional `current` state directory, primarily for fixtures.
        env: Optional environment mapping for XDG and OMARCHY_PATH overrides.

    Returns:
        Palette, slug, source file, and live-generation token.

    Raises:
        PaletteError: Omarchy is absent or its active palette is unusable.
    """
    state = _state_dir(env) if state_dir is None else state_dir
    try:
        slug = slugify((state / "theme.name").read_text(encoding="utf-8"))
    except OSError:
        slug = "current"
    paths = _candidate_paths(slug, state, env)
    colors_path = next((path for path in paths if path.is_file()), None)
    if colors_path is None:
        raise PaletteError("Omarchy theme not found; use --theme tungsten or a built-in theme")
    try:
        colors = tomllib.loads(colors_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise PaletteError(f"cannot read Omarchy palette {colors_path.name}: {error}") from error
    if not isinstance(colors, dict):
        raise PaletteError("Omarchy colors.toml must contain a TOML table")
    try:
        palette = palette_from_omarchy(colors, slug)
    except PaletteError as error:
        raise PaletteError(f"invalid Omarchy theme {slug}: {error}") from error
    return OmarchyTheme(palette, slug, colors_path, generation_token(state))
