"""Typed public album catalog for the terminal library.

`cli.py` lists this catalog with `aav tracks`. `library.py` paints it and
opens one movement. Only the four completed A-01 albums authorized for
public bundling belong here; in-progress, archive, and private albums stay
out. Each band is both the album-artist credit and the band sort field:
the sources have no distinct per-track musician credits, and none are
invented. Times are seconds from the start of the album audio.
"""

from __future__ import annotations

from dataclasses import dataclass


class CatalogError(ValueError):
    """The public album catalog is internally inconsistent."""


@dataclass(frozen=True, slots=True)
class Track:
    """One movement on a bundled album.

    Attributes:
        number: 1-based position on the album.
        title: Movement title. Not a performer credit.
        start_s: Start offset in seconds from the beginning of the album audio.
    """

    number: int
    title: str
    start_s: float


@dataclass(frozen=True, slots=True)
class Album:
    """A completed public album and the filename of its bundled player.

    Attributes:
        artist: Album-artist credit. For this catalog, the band name.
        band: Band credit used as its own sort field. Same value as `artist`
            for every bundled album.
        title: Album title.
        duration_s: Album duration in seconds.
        asset: Gzip HTML filename under ``agentic_av/albums``. Basename only.
        tracks: Movements in performance order.
    """

    artist: str
    band: str
    title: str
    duration_s: float
    asset: str
    tracks: tuple[Track, ...]


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """One sortable row: an album plus one of its movements."""

    album: Album
    track: Track


def _album(
    artist: str,
    title: str,
    duration_s: float,
    asset: str,
    tracks: tuple[tuple[float, str], ...],
) -> Album:
    """Build an album whose band credit is the album artist.

    The authorized sources do not name per-track musicians. Keeping a
    separate `band` field preserves the sort contract without inventing
    anyone else to put in it.
    """
    return Album(
        artist=artist,
        band=artist,
        title=title,
        duration_s=duration_s,
        asset=asset,
        tracks=tuple(
            Track(number=index, title=name, start_s=start)
            for index, (start, name) in enumerate(tracks, start=1)
        ),
    )


# Authorized public archives only. Do not append in-progress or private albums.
ALBUMS: tuple[Album, ...] = (
    _album(
        "Coupon Seance",
        "Saturn Has a Dollar Store",
        722,
        "coupon-seance-saturn.html.gz",
        (
            (0, "Customs at the Edge of Saturn"),
            (77.5715, "Rosin in the Subwoofer"),
            (198.7715, "Saturn Has a Dollar Store"),
            (301.7715, "Mall Cop on the Astral Plane"),
            (418.116375, "The Violin Remembers Earth"),
            (507.116625, "Return Policy for a Black Hole"),
            (622.831, "We Kept the Receipt"),
        ),
    ),
    _album(
        "Drowning Collective",
        "Are We Fish?",
        1620,
        "drowning-collective-are-we-fish.html.gz",
        (
            (0, "An Uneven Kindness"),
            (268, "The Bass Asked First"),
            (520, "Current Without a Shore"),
            (820, "Where the Downbeat Went Under"),
            (1108, "Two Notes, Then Air"),
            (1340, "The Water Learns Major"),
        ),
    ),
    _album(
        "Nurse Log",
        "The Ground Moves Anyway",
        1680,
        "nurse-log-ground-moves-anyway.html.gz",
        (
            (0, "Under Six Feet of Moss"),
            (312, "Rain Has Teeth"),
            (576, "The Root Ball Turns"),
            (828, "Cedar Lung"),
            (1128, "Nurse Log, Open Hand"),
            (1356, "The Ground Moves Anyway"),
        ),
    ),
    _album(
        "Quiet Machinery",
        "The Atlas of Unlit Rooms",
        1620,
        "quiet-machinery-atlas-unlit-rooms.html.gz",
        (
            (0, "Copper Gravity"),
            (288, "Two Shadows Pass"),
            (540, "The Bell Is a Body"),
            (816, "Salt Geometry"),
            (1080, "An Empty Room Stays Warm"),
            (1320, "Antenna for the Unlit"),
        ),
    ),
)


def bundled_assets() -> frozenset[str]:
    """Return the gzip filenames the public catalog is allowed to open."""
    return frozenset(album.asset for album in ALBUMS)


def sort_key(entry: CatalogEntry) -> tuple[str, str, str, int, str]:
    """Return the library order key for one movement.

    Order is album artist, band, album title, then track number and title.
    Casefold so a credit is not split by capitalization. Number comes before
    title so a later movement cannot sort ahead of an earlier one.

    Args:
        entry: Album and movement to order.

    Returns:
        A tuple suitable for `sorted`.
    """
    album = entry.album
    track = entry.track
    return (
        album.artist.casefold(),
        album.band.casefold(),
        album.title.casefold(),
        track.number,
        track.title.casefold(),
    )


def sort_entries(albums: tuple[Album, ...] | list[Album]) -> tuple[CatalogEntry, ...]:
    """Sort every movement of `albums` by `sort_key`.

    Args:
        albums: Catalog albums, bundled or synthetic. Not validated here so
            tests can prove each key field independently.

    Returns:
        A new tuple. The input album order is not preserved.
    """
    entries = [CatalogEntry(album, track) for album in albums for track in album.tracks]
    return tuple(sorted(entries, key=sort_key))


def validate_catalog(albums: tuple[Album, ...] | list[Album] = ALBUMS) -> None:
    """Reject a catalog that could not drive the library safely.

    Args:
        albums: Albums to check. Defaults to the bundled public catalog.

    Raises:
        CatalogError: A credit, asset name, track number, or start time is
            missing or out of order. Start times are seconds and must stay
            inside the album duration.
    """
    seen: set[str] = set()
    for album in albums:
        if not album.artist.strip() or not album.band.strip() or not album.title.strip():
            raise CatalogError("album artist, band, and title are required")
        if album.duration_s <= 0:
            raise CatalogError(f"{album.title} needs a positive duration in seconds")
        asset = album.asset
        if asset != asset.replace("\\", "/") or "/" in asset or asset != asset.strip():
            raise CatalogError(f"album asset must be a basename, not {asset!r}")
        if not asset.endswith(".html.gz"):
            raise CatalogError(f"album asset must be gzip HTML, not {asset!r}")
        if asset in seen:
            raise CatalogError(f"duplicate album asset {asset}")
        seen.add(asset)
        if not album.tracks:
            raise CatalogError(f"{album.title} has no movements")
        previous = -1.0
        for index, track in enumerate(album.tracks, start=1):
            if track.number != index:
                raise CatalogError(
                    f"{album.title} track {track.number} is not in performance order"
                )
            if not track.title.strip():
                raise CatalogError(f"{album.title} has an empty movement title")
            if track.start_s < previous or track.start_s >= album.duration_s:
                raise CatalogError(
                    f"{album.title} movement {track.title!r} starts at {track.start_s}s, "
                    f"outside 0..{album.duration_s}"
                )
            previous = track.start_s
        if album.tracks[0].start_s != 0:
            raise CatalogError(f"{album.title} must start at 0 seconds")


def catalog_entries() -> tuple[CatalogEntry, ...]:
    """Return the bundled movements in library order.

    Raises:
        CatalogError: The bundled catalog failed `validate_catalog`.
    """
    validate_catalog(ALBUMS)
    return sort_entries(ALBUMS)


def credit_line(album: Album) -> str:
    """Return the listener-facing album credit.

    Bundled albums use the band as the album artist, so the line is one
    credit. A synthetic album with two different credits shows both rather
    than dropping a sort field.

    Args:
        album: Album whose credits are displayed.

    Returns:
        A single line, without a trailing newline.
    """
    if album.artist.casefold() == album.band.casefold():
        return f"{album.artist} - {album.title}"
    return f"{album.artist} / {album.band} - {album.title}"


def format_clock(seconds: float) -> str:
    """Format a non-negative offset as M:SS or H:MM:SS, truncating toward zero.

    Args:
        seconds: Offset in seconds. Negative values are treated as zero so a
            bad row cannot print a minus sign into the fixed grid.

    Returns:
        A clock label. Fractional seconds are not shown; the deep link keeps
        the exact start.
    """
    whole = max(0, int(seconds))
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def movement_duration_s(album: Album, track: Track) -> float:
    """Return the movement length in seconds.

    The last movement runs to the album duration. Earlier movements run to
    the next listed start. The library shows it; native playback also uses
    it to clamp seeks and to end a movement in a shared album mix.

    Args:
        album: Album that owns the movement.
        track: Movement to measure. Matched by number and title.

    Returns:
        Duration in seconds, or 0 when the track is not on the album.
    """
    for index, item in enumerate(album.tracks):
        if item.number == track.number and item.title == track.title:
            if index + 1 < len(album.tracks):
                return album.tracks[index + 1].start_s - item.start_s
            return album.duration_s - item.start_s
    return 0.0


def format_catalog(entries: tuple[CatalogEntry, ...] | None = None) -> str:
    """Render the sorted catalog as plain text for `aav tracks`.

    Args:
        entries: Movements to list. Defaults to the bundled catalog. The
            caller is responsible for sort order; this function does not
            reorder, so a test can tell a sorting bug from a printing bug.

    Returns:
        A trailing-newline-free listing. No ANSI sequences.
    """
    chosen = catalog_entries() if entries is None else entries
    albums = {(entry.album.artist, entry.album.band, entry.album.title) for entry in chosen}
    lines = [f"AAV TRACKS    {len(albums)} albums · {len(chosen)} tracks", ""]
    current: tuple[str, str, str] | None = None
    for entry in chosen:
        album = entry.album
        identity = (album.artist, album.band, album.title)
        if identity != current:
            if current is not None:
                lines.append("")
            current = identity
            lines.append(credit_line(album))
            lines.append(f"  album artist: {album.artist}")
            if album.artist.casefold() != album.band.casefold():
                lines.append(f"  band: {album.band}")
            lines.append(f"  duration: {format_clock(album.duration_s)}")
        clock = format_clock(entry.track.start_s)
        lines.append(f"  {entry.track.number:02d}  {clock:>7}  {entry.track.title}")
    lines.append("")
    lines.append("Play a movement with `aav play` and Enter, or press o there for the browser.")
    return "\n".join(lines)
