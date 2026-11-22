"""Player color roles and named visual treatments.

The TTY painter and Omarchy loader share this role set. Palette values are
immutable so a live sync swaps a complete set instead of half-updating a frame.
"""

from __future__ import annotations

from dataclasses import dataclass

from clangor_visualis_machina.colorutil import mix, normalize_hex


class PaletteError(ValueError):
    """A requested palette cannot provide the colors needed to render."""


@dataclass(frozen=True, slots=True)
class Palette:
    """Semantic colors consumed by every player view.

    `dark` controls the paper/ink treatment in the generative stage. All
    color fields are lowercase six-digit hex strings.
    """

    name: str
    mood: str
    dark: bool
    background: str
    stage: str
    panel: str
    foreground: str
    muted: str
    accent: str
    accent2: str
    success: str
    warning: str
    error: str
    meter: str
    progress: str
    selection: str
    border: str


_BUILTINS = (
    Palette(
        "tungsten",
        "velvet · filament",
        True,
        "#100e12",
        "#09080b",
        "#1c1720",
        "#f0e4cf",
        "#817786",
        "#efa95a",
        "#c65d79",
        "#9dc484",
        "#e8c36d",
        "#ed6a62",
        "#a7ce8c",
        "#efa95a",
        "#392a2b",
        "#483543",
    ),
    Palette(
        "phosphor",
        "green glass · afterimage",
        True,
        "#06110e",
        "#020806",
        "#0a1c17",
        "#d6f3df",
        "#638d7c",
        "#86f5ac",
        "#48c9ba",
        "#a4f09d",
        "#f1d37b",
        "#ff7776",
        "#a4f09d",
        "#86f5ac",
        "#123329",
        "#235342",
    ),
    Palette(
        "broadcast",
        "blue hour · control room",
        True,
        "#0a101c",
        "#050a12",
        "#111b2c",
        "#e2e8f0",
        "#73839a",
        "#79b8ff",
        "#cb8b5e",
        "#70d0ae",
        "#e8bd78",
        "#eb7481",
        "#79b8ff",
        "#79b8ff",
        "#1a2b42",
        "#2b405e",
    ),
    Palette(
        "newsprint",
        "warm paper · ink",
        False,
        "#f1e9d6",
        "#e5dac2",
        "#f8f1e2",
        "#262524",
        "#81776a",
        "#a84336",
        "#456a78",
        "#50734b",
        "#a85f25",
        "#a84336",
        "#50734b",
        "#a84336",
        "#d9cbb0",
        "#b5a891",
    ),
    Palette(
        "signal",
        "amber · interference",
        True,
        "#120e0b",
        "#090706",
        "#211712",
        "#f3e5ce",
        "#887465",
        "#f6aa43",
        "#ee5a8a",
        "#9ac785",
        "#f3c66e",
        "#ff685c",
        "#f6aa43",
        "#f6aa43",
        "#422719",
        "#573923",
    ),
    Palette(
        "glacier",
        "blue ice · clear air",
        False,
        "#eaf2f5",
        "#dce9ef",
        "#f4f8fa",
        "#142c3a",
        "#607b89",
        "#176a9c",
        "#337f77",
        "#397a56",
        "#976d19",
        "#ad474a",
        "#337f77",
        "#176a9c",
        "#c7dce6",
        "#a9c5d3",
    ),
    Palette(
        "carbon",
        "graphite · one spark",
        True,
        "#111213",
        "#08090a",
        "#1b1c1e",
        "#e5e5e1",
        "#777b7e",
        "#ffb45b",
        "#c7c8ca",
        "#b2cc9a",
        "#e8ce91",
        "#ed726b",
        "#ffb45b",
        "#ffb45b",
        "#34302b",
        "#46413b",
    ),
    Palette(
        "marigold",
        "cream · late sun",
        False,
        "#f8efcf",
        "#eee2b7",
        "#fff6dc",
        "#382d18",
        "#887951",
        "#b76b17",
        "#8a526d",
        "#557343",
        "#a35a1b",
        "#a6423b",
        "#718145",
        "#b76b17",
        "#e3d29e",
        "#c9b77e",
    ),
    Palette(
        "void",
        "black field · cold flare",
        True,
        "#05070c",
        "#020306",
        "#0c111c",
        "#f2f5ff",
        "#687288",
        "#84adff",
        "#d0e0ff",
        "#95e2c0",
        "#ffe38c",
        "#ff6d87",
        "#84adff",
        "#84adff",
        "#172238",
        "#293751",
    ),
)


def builtin_palettes() -> tuple[Palette, ...]:
    """Return the ordered built-in palettes; callers cannot mutate the set."""
    return _BUILTINS


def builtin_palette(name: str) -> Palette:
    """Resolve a built-in palette by case-insensitive name.

    Args:
        name: Palette name such as ``phosphor``.

    Returns:
        Immutable palette.

    Raises:
        PaletteError: No built-in palette has that name.
    """
    key = name.strip().casefold()
    for palette in _BUILTINS:
        if palette.name == key:
            return palette
    names = ", ".join(p.name for p in _BUILTINS)
    raise PaletteError(f"unknown theme {name!r}; built-ins: {names}, omarchy")


def palette_from_omarchy(colors: dict[str, object], slug: str) -> Palette:
    """Map an Omarchy `colors.toml` table to player roles.

    Args:
        colors: Parsed TOML key/value pairs. Invalid color tokens are ignored.
        slug: Current Omarchy theme slug for the display name.

    Returns:
        Complete palette, filling optional roles from available colors.

    Raises:
        PaletteError: Background, foreground, or accent cannot be recovered.
    """

    def pick(*keys: str, default: str | None = None) -> str | None:
        for key in keys:
            value = colors.get(key)
            if isinstance(value, str) and (normalized := normalize_hex(value)):
                return normalized
        return default

    background = pick("background")
    foreground = pick("bright_foreground", "foreground")
    accent = pick("accent", "blue", "cyan", "magenta")
    if not background or not foreground or not accent:
        raise PaletteError(
            "Omarchy colors.toml needs usable background, foreground, and accent colors"
        )
    dark = str(colors.get("mode", "dark")).casefold() != "light"
    muted = pick("muted", "dark_foreground", default=mix(background, foreground, 0.48))
    stage = pick("darker_background", "dark_background", default=background)
    panel = pick("lighter_background", default=mix(background, foreground, 0.08))
    return Palette(
        name=f"omarchy · {slug}",
        mood=f"live · {slug}",
        dark=dark,
        background=background,
        stage=stage,
        panel=panel,
        foreground=foreground,
        muted=muted,
        accent=accent,
        accent2=pick("cyan", "magenta", "bright_blue", default=mix(accent, foreground, 0.42)),
        success=pick("green", "bright_green", default=mix(background, foreground, 0.62)),
        warning=pick("yellow", "orange", "bright_yellow", default=mix(accent, foreground, 0.50)),
        error=pick("red", "bright_red", default=mix(accent, foreground, 0.22)),
        meter=pick("bright_green", "green", default=accent),
        progress=accent,
        selection=pick("selection", default=mix(background, accent, 0.45)),
        border=muted,
    )


def monochrome_palette(palette: Palette) -> Palette:
    """Return a luminance-oriented palette marker; rendering disables ANSI color."""
    return Palette(
        name=f"{palette.name} · mono",
        mood="no color",
        dark=palette.dark,
        background=palette.background,
        stage=palette.stage,
        panel=palette.panel,
        foreground=palette.foreground,
        muted=palette.muted,
        accent=palette.accent,
        accent2=palette.accent2,
        success=palette.success,
        warning=palette.warning,
        error=palette.error,
        meter=palette.meter,
        progress=palette.progress,
        selection=palette.selection,
        border=palette.border,
    )
