"""Album catalog order, library frame bounds, deep links, and command dispatch."""

import gzip
import hashlib
import json
from importlib.resources import files
from pathlib import Path

import pytest

from agentic_av import __version__
from agentic_av.catalog import (
    ALBUMS,
    Album,
    CatalogEntry,
    Track,
    catalog_entries,
    format_catalog,
    format_clock,
    sort_entries,
    validate_catalog,
)
from agentic_av.cli import main
from agentic_av.library import (
    TRACK_START_ID,
    AlbumError,
    LibraryState,
    _library_panel_bytes,
    _resort_preserving_selection,
    album_cache_dir,
    apply_library_key,
    compose_library,
    inject_track_start,
    materialize_html,
    open_selected_and_resume,
    run_library,
    track_start_script,
    track_url,
)
from agentic_av.paint import render_ansi, render_plain
from agentic_av.palette import builtin_palettes
from agentic_av.viz.cover import load_cover

_AUTHORIZED = (
    (
        "Coupon Seance",
        "Saturn Has a Dollar Store",
        722,
        "coupon-seance-saturn.html.gz",
        (
            0,
            77.5715,
            198.7715,
            301.7715,
            418.116375,
            507.116625,
            622.831,
        ),
    ),
    (
        "Drowning Collective",
        "Are We Fish?",
        1620,
        "drowning-collective-are-we-fish.html.gz",
        (0, 268, 520, 820, 1108, 1340),
    ),
    (
        "Nurse Log",
        "The Ground Moves Anyway",
        1680,
        "nurse-log-ground-moves-anyway.html.gz",
        (0, 312, 576, 828, 1128, 1356),
    ),
    (
        "Quiet Machinery",
        "The Atlas of Unlit Rooms",
        1620,
        "quiet-machinery-atlas-unlit-rooms.html.gz",
        (0, 288, 540, 816, 1080, 1320),
    ),
    (
        "Nurse Log",
        "The Forest Has a Pocket",
        1604,
        "nurse-log-the-forest-has-a-pocket.html.gz",
        (0, 272, 532, 784, 1076, 1284),
    ),
    (
        "Drowning Collective",
        "The Shape That Stays",
        1632,
        "drowning-collective-the-shape-that-stays.html.gz",
        (0, 268, 516, 808, 1084, 1316),
    ),
    (
        "Coupon Seance",
        "Buy One, Haunt One Free",
        1603,
        "coupon-seance-buy-one-haunt-one-free.html.gz",
        (0, 271, 530, 784, 1070, 1326),
    ),
    (
        "Quiet Machinery",
        "Instruments for Measuring Dusk",
        1596,
        "quiet-machinery-instruments-for-measuring-dusk.html.gz",
        (0, 276, 546, 823, 1096, 1346),
    ),
)


_POCKET_ASSET = "nurse-log-the-forest-has-a-pocket.html.gz"
_POCKET_GZ_SHA256 = "bd7887dc5884230721fa3be9cd508697b0231fe6bdb8ced521b8f9770fec50a3"
_POCKET_HTML_SHA256 = "5b0387575231b1ef29d7c881a10f672688218b3099640399b8319690d0205a87"
_HAUNT_ASSET = "coupon-seance-buy-one-haunt-one-free.html.gz"
_HAUNT_GZ_SHA256 = "6d18ba3cd44f3ad2258907a8fc7719c372de9a7d6016e0f8fa71779d2ee96be9"
_HAUNT_HTML_SHA256 = "fa9672cdba93f7bc3a19a8689f89ebc0af865b166297baa043394274b534fced"
_DUSK_ASSET = "quiet-machinery-instruments-for-measuring-dusk.html.gz"
_DUSK_GZ_SHA256 = "881b22458e6d8bd1a04b5c330e5b276bd11a60036e559edb5841a2aff71c164b"
_DUSK_HTML_SHA256 = "9312ea491df87d3c75b0d9fe8d6011d084111682ab843120c2b7b7c37240a177"


def test_public_catalog_is_the_authorized_albums() -> None:
    """Band is the album artist; four A-01 albums and the approved A-02 albums are listed."""
    validate_catalog()
    assert len(ALBUMS) == 8
    assert all(album.artist == album.band for album in ALBUMS)
    found = {
        (album.artist, album.title, album.duration_s, album.asset): tuple(
            track.start_s for track in album.tracks
        )
        for album in ALBUMS
    }
    expected = {
        (artist, title, duration, asset): starts
        for artist, title, duration, asset, starts in _AUTHORIZED
    }
    assert found == expected
    names = sorted(
        path.name
        for path in files("agentic_av").joinpath("albums").iterdir()
        if not path.name.startswith(".")
    )
    assert names == sorted(album.asset for album in ALBUMS)


def test_pocket_catalog_metadata_and_archive_match_the_approved_source() -> None:
    """Nurse Log A-02 retains its exact movements and approved, unaltered page.

    The hashes come from the approved source HTML and the packaged gzip, so a replaced or
    re-encoded archive fails here before it can ship.
    """
    pocket = next(album for album in ALBUMS if album.asset == _POCKET_ASSET)
    assert (pocket.artist, pocket.band, pocket.title) == (
        "Nurse Log",
        "Nurse Log",
        "The Forest Has a Pocket",
    )
    assert pocket.duration_s == 1604
    assert [track.title for track in pocket.tracks] == [
        "A Root Learns the Offbeat",
        "Rain in the Hinges",
        "Bark, Bent Light",
        "The Canopy Has Elbows",
        "Five Spaces for a Fern",
        "The Forest Has a Pocket",
    ]
    starts = [track.start_s for track in pocket.tracks]
    ends = [*starts[1:], pocket.duration_s]
    assert [end - start for start, end in zip(starts, ends, strict=True)] == [
        272,
        260,
        252,
        292,
        208,
        320,
    ]
    data = files("agentic_av").joinpath("albums", _POCKET_ASSET).read_bytes()
    assert len(data) == 49_982_951
    assert hashlib.sha256(data).hexdigest() == _POCKET_GZ_SHA256
    html = gzip.decompress(data)
    assert len(html) == 72_058_058
    assert hashlib.sha256(html).hexdigest() == _POCKET_HTML_SHA256


def test_drowning_a02_metadata_and_archive_match_the_finished_album() -> None:
    """The new catalog entry resolves exact audio-page bytes and maker provenance."""
    asset = "drowning-collective-the-shape-that-stays.html.gz"
    album = next(a for a in ALBUMS if a.asset == asset)
    assert (album.artist, album.band, album.title, album.duration_s) == (
        "Drowning Collective",
        "Drowning Collective",
        "The Shape That Stays",
        1632,
    )
    assert [track.title for track in album.tracks] == [
        "A Handhold in Moving Water",
        "The Low Voice Keeps the Question",
        "Five Ways Past the Same Shore",
        "A Fault Held Gently",
        "Leave the Basin Unfilled",
        "The Shape That Stays",
    ]
    starts = [t.start_s for t in album.tracks]
    ends = [*starts[1:], album.duration_s]
    assert [end - start for start, end in zip(starts, ends, strict=True)] == [
        268,
        248,
        292,
        276,
        232,
        316,
    ]
    archive = files("agentic_av").joinpath("albums", asset).read_bytes()
    assert len(archive) == 38_275_169
    assert hashlib.sha256(archive).hexdigest() == (
        "e60a51ce7e5788c9a0b364c08a32e4a2ef5e81fa1a9eda6bb19e83504f090caa"
    )
    html = gzip.decompress(archive)
    assert len(html) == 53_318_791
    assert hashlib.sha256(html).hexdigest() == (
        "825ea4f55144a4ef0271c1a868034443487d776ca5730ee85005f54637067665"
    )
    source = html.decode("utf-8")
    marker = "window.DC2_ALBUM="
    data, _ = json.JSONDecoder().raw_decode(source.split(marker, 1)[1])
    assert data["made_with"]["model"] == "openai-codex/gpt-6.1-sol"
    assert data["album_duration"] == 1632
    assert [t["duration"] for t in data["tracks"]] == [268, 248, 292, 276, 232, 316]
    assert all(t["audio"].startswith("data:audio/mpeg;base64,") for t in data["tracks"])


def test_haunt_catalog_metadata_and_archive_match_the_built_page() -> None:
    """Coupon Seance A-02: exact movements, the unaltered built page, and its model credit.

    The hashes come from the built page and the packaged gzip, so a replaced or re-encoded
    archive fails here. The page's album JSON must keep the model that made the album.
    """
    haunt = next(album for album in ALBUMS if album.asset == _HAUNT_ASSET)
    assert (haunt.artist, haunt.band, haunt.title) == (
        "Coupon Seance",
        "Coupon Seance",
        "Buy One, Haunt One Free",
    )
    assert [track.title for track in haunt.tracks] == [
        "Doors Open at Perihelion",
        "Buy One, Haunt One Free",
        "Price Check on Aisle Infinity",
        "The Ghost in the Coin Return",
        "Layaway for a Dying Star",
        "We Kept the Change",
    ]
    starts = [track.start_s for track in haunt.tracks]
    ends = [*starts[1:], haunt.duration_s]
    assert [end - start for start, end in zip(starts, ends, strict=True)] == [
        271,
        259,
        254,
        286,
        256,
        277,
    ]
    data = files("agentic_av").joinpath("albums", _HAUNT_ASSET).read_bytes()
    assert len(data) == 38_493_904
    assert hashlib.sha256(data).hexdigest() == _HAUNT_GZ_SHA256
    html = gzip.decompress(data)
    assert len(html) == 52_431_005
    assert hashlib.sha256(html).hexdigest() == _HAUNT_HTML_SHA256
    assert b'"made_with":{"model":"anthropic/claude-opus-5-5"' in html


def test_dusk_catalog_metadata_and_archive_match_the_built_page() -> None:
    """Quiet Machinery A-02: exact movements, the unaltered built page, and its model credit.

    The hashes come from the built page and the packaged gzip, so a replaced or re-encoded
    archive fails here. The page's album JSON must keep the model that made the album.
    """
    dusk = next(album for album in ALBUMS if album.asset == _DUSK_ASSET)
    assert (dusk.artist, dusk.band, dusk.title) == (
        "Quiet Machinery",
        "Quiet Machinery",
        "Instruments for Measuring Dusk",
    )
    assert [track.title for track in dusk.tracks] == [
        "The Cell Returns at Dusk",
        "Two Reeds Cross the Sheet",
        "A Bell Learns to Wait",
        "Salt Fault, Seven Steps",
        "The Warm Room Opens a Window",
        "Antenna, Lit",
    ]
    starts = [track.start_s for track in dusk.tracks]
    ends = [*starts[1:], dusk.duration_s]
    assert [end - start for start, end in zip(starts, ends, strict=True)] == [
        276,
        270,
        277,
        273,
        250,
        250,
    ]
    data = files("agentic_av").joinpath("albums", _DUSK_ASSET).read_bytes()
    assert len(data) == 38_256_695
    assert hashlib.sha256(data).hexdigest() == _DUSK_GZ_SHA256
    html = gzip.decompress(data)
    assert len(html) == 52_814_897
    assert hashlib.sha256(html).hexdigest() == _DUSK_HTML_SHA256
    assert b'"made_with":{"model":"anthropic/claude-opus-5-5"' in html
    # The catalog's titles are the page's own track titles, punctuation included.
    for track in dusk.tracks:
        assert f'"title":"{track.title}"'.encode() in html, track.title


def test_sort_orders_artist_band_album_then_track_number_and_title() -> None:
    """Each sort field participates, including when artist and band differ."""
    later = Album(
        "Zed",
        "Aaa",
        "Early",
        10,
        "z.html.gz",
        (Track(1, "B", 0), Track(2, "A", 1)),
    )
    band_second = Album("Aaa", "Zed", "Late", 10, "a.html.gz", (Track(1, "M", 0),))
    numbered = Album(
        "Aaa",
        "Mmm",
        "Mid",
        10,
        "m.html.gz",
        (Track(1, "Z", 0), Track(2, "A", 1), Track(1, "A", 0)),
    )
    folded = Album("aaa", "B", "Same", 10, "f.html.gz", (Track(1, "Q", 0),))
    ordered = sort_entries([later, band_second, numbered, folded])
    got = [
        (
            entry.album.artist,
            entry.album.band,
            entry.album.title,
            entry.track.number,
            entry.track.title,
        )
        for entry in ordered
    ]
    assert got == [
        ("aaa", "B", "Same", 1, "Q"),
        ("Aaa", "Mmm", "Mid", 1, "A"),
        ("Aaa", "Mmm", "Mid", 1, "Z"),
        ("Aaa", "Mmm", "Mid", 2, "A"),
        ("Aaa", "Zed", "Late", 1, "M"),
        ("Zed", "Aaa", "Early", 1, "B"),
        ("Zed", "Aaa", "Early", 2, "A"),
    ]
    public = catalog_entries()
    keys = [
        (
            entry.album.artist.casefold(),
            entry.album.band.casefold(),
            entry.album.title.casefold(),
            entry.track.number,
            entry.track.title.casefold(),
        )
        for entry in public
    ]
    assert keys == sorted(keys)
    assert len(public) == 49
    titles = [entry.track.title for entry in public]
    assert titles.index("We Kept the Receipt") < titles.index("An Uneven Kindness")
    assert titles.index("The Water Learns Major") < titles.index("Under Six Feet of Moss")
    assert titles.index("The Ground Moves Anyway") < titles.index("Copper Gravity")
    assert titles.index("We Kept the Change") < titles.index("Customs at the Edge of Saturn")
    assert titles.index("Antenna, Lit") < titles.index("Copper Gravity")


def test_library_sort_modes_keep_highlight_and_show_selected_album_details() -> None:
    """Sorting preserves the selected movement; its cover and blurb fill the side panel."""
    original = catalog_entries()
    assert all(album.description.strip() for album in ALBUMS)
    state = LibraryState(selected=17)
    highlighted = original[state.selected]
    assert apply_library_key(state, "s", count=len(original)) == "sort"
    assert state.sort_mode == "album"
    ordered, selected = _resort_preserving_selection(original, state.selected, state.sort_mode)
    assert ordered[selected] == highlighted
    titles = [entry.album.title.casefold() for entry in ordered]
    assert titles == sorted(titles)
    assert apply_library_key(state, "s", count=len(ordered)) == "sort"
    by_band, selected = _resort_preserving_selection(ordered, selected, state.sort_mode)
    assert by_band[selected] == highlighted
    bands = [entry.album.band.casefold() for entry in by_band]
    assert bands == sorted(bands)

    palette = builtin_palettes()[0]
    rows = compose_library(
        by_band, selected, 100, 30, palette, sort_mode=state.sort_mode, panel_start=62
    )
    assert all(len(row) == 100 for row in rows)
    assert "BAND SORT" in render_plain(rows)
    art = load_cover(highlighted.album.cover.asset, highlighted.album.cover.sha256)
    panel = _library_panel_bytes(
        highlighted,
        art,
        panel_start=62,
        width=100,
        height=30,
        palette=palette,
        color_mode="truecolor",
    )
    assert highlighted.album.title.encode() in panel
    assert highlighted.album.description.split()[0].encode() in panel
    assert b"[3;" in panel


def test_tracks_listing_follows_catalog_order_without_ansi(capsys) -> None:
    """`aav tracks` is a sorted plain catalog and does not need a TTY."""
    assert main(["tracks", "--theme", "made-up", "--no-color"]) == 0
    listed = capsys.readouterr().out
    assert "\x1b" not in listed
    assert listed == format_catalog() + "\n"
    positions = [
        listed.index(
            f"  {entry.track.number:02d}"
            f"  {format_clock(entry.track.start_s):>7}"
            f"  {entry.track.title}"
        )
        for entry in catalog_entries()
    ]
    assert positions == sorted(positions)
    assert "album artist: Coupon Seance" in listed
    assert "guitar" not in listed.casefold()
    assert "vocals" not in listed.casefold()


def test_library_frame_bounds_keep_the_selection_visible() -> None:
    """Every frame is exactly width by height, and the selected row stays inside it."""
    entries = catalog_entries()
    palette = builtin_palettes()[0]
    sizes = ((80, 24), (64, 8), (20, 3), (1, 1), (100, 40), (48, 5))
    for width, height in sizes:
        for selected in (0, 1, 12, len(entries) - 1, -1, 10_000):
            rows = compose_library(
                entries,
                selected,
                width,
                height,
                palette,
                note="Opened in the browser - click Play",
            )
            assert len(rows) == height
            assert all(len(row) == width for row in rows)
            assert all(len(cell.char) == 1 for row in rows for cell in row)
            assert all(cell.char.isprintable() for row in rows for cell in row)
            plain = render_plain(rows)
            assert "\x1b" not in render_ansi(rows, "none")
            if width >= 2 and height >= 1:
                assert any(line.startswith(">") for line in plain.splitlines())
            if width >= 72 and height >= 1:
                title = entries[selected % len(entries)].track.title
                selected_rows = [line for line in plain.splitlines() if line.startswith(">")]
                assert len(selected_rows) == 1
                assert title in selected_rows[0]
    help_rows = compose_library(
        entries, 3, 80, 16, palette, show_help=True, note="hidden while help is open"
    )
    assert len(help_rows) == 16
    assert all(len(row) == 80 for row in help_rows)
    help_text = render_plain(help_rows)
    assert "code-only visuals" in help_text
    assert "click Play" in help_text
    assert "j / down" in help_text
    assert "enter" in help_text
    assert "q" in help_text
    colored = render_ansi(compose_library(entries, 1, 40, 8, palette), "truecolor")
    assert "\x1b[48;2;57;42;43m" in colored


def test_library_title_controls_cannot_break_the_grid() -> None:
    """ESC and CR in a title stay out of the fixed row."""
    album = Album(
        "A\x1b[2J",
        "A\x1b[2J",
        "T\r\n",
        10,
        "x.html.gz",
        (Track(1, "bad\x1b[0m", 0),),
    )
    entry = CatalogEntry(album, album.tracks[0])
    rows = compose_library([entry], 0, 36, 6, builtin_palettes()[0])
    plain = render_plain(rows)
    assert "\x1b" not in plain
    assert "\r" not in plain
    assert all(len(row) == 36 for row in rows)


def test_keys_select_wrap_and_do_not_open_from_help() -> None:
    """j/k and arrows move; Enter plays and o opens only when help is closed."""
    state = LibraryState()
    assert apply_library_key(state, "k", count=25) == "stay"
    assert state.selected == 24
    assert apply_library_key(state, "down", count=25) == "stay"
    assert state.selected == 0
    assert apply_library_key(state, "j", count=25) == "stay"
    assert state.selected == 1
    assert apply_library_key(state, "up", count=25) == "stay"
    assert state.selected == 0
    assert apply_library_key(state, "G", count=25) == "stay"
    assert state.selected == 24
    assert apply_library_key(state, "?", count=25) == "stay"
    assert state.show_help
    held = state.selected
    assert apply_library_key(state, "j", count=25) == "stay"
    assert apply_library_key(state, "enter", count=25) == "stay"
    assert apply_library_key(state, "o", count=25) == "stay"
    assert state.selected == held
    assert state.show_help
    assert apply_library_key(state, "esc", count=25) == "stay"
    assert not state.show_help
    assert apply_library_key(state, "enter", count=25) == "open"
    assert apply_library_key(state, "o", count=25) == "open_browser"
    assert apply_library_key(state, "q", count=25) == "quit"
    state.show_help = True
    assert apply_library_key(state, "quit", count=25) == "quit"


def _html_gz() -> bytes:
    html = (
        '<!DOCTYPE html><html><body><audio id="audio"></audio>'
        '<input id="seek" value="0">'
        "<script>function startAlbum(){ document.getElementById('audio').play(); }</script>"
        "</body></html>"
    )
    return gzip.compress(html.encode("utf-8"))


def test_materialize_injects_before_body_and_leaves_source(tmp_path: Path) -> None:
    """The cache copy seeks from the query string and does not rewrite the gzip."""
    source = tmp_path / "coupon-seance-saturn.html.gz"
    payload = _html_gz()
    source.write_bytes(payload)
    before = source.read_bytes()
    stamp = source.stat().st_mtime_ns
    cached = materialize_html(before, source.name, tmp_path / "cache")
    assert source.read_bytes() == before
    assert source.stat().st_mtime_ns == stamp
    text = cached.read_text(encoding="utf-8")
    script_at = text.index(f'id="{TRACK_START_ID}"')
    body_at = text.lower().rfind("</body>")
    assert script_at < body_at
    script = text[script_at:body_at]
    assert "currentTime" in script
    assert "loadedmetadata" in script
    assert 'getElementById("audio")' in script
    assert 'getElementById("seek")' in script
    assert "URLSearchParams" in script
    assert ".play(" not in script
    assert "autoplay" not in script.casefold()
    assert ".partial" not in cached.name
    assert not list(cached.parent.glob("*.partial"))
    assert materialize_html(before, source.name, tmp_path / "cache") == cached
    assert __version__ in cached.parts
    assert "track-start-1" in cached.parts
    other = materialize_html(
        gzip.compress(b"<html><body></body></html>"),
        source.name,
        tmp_path / "cache",
    )
    assert other != cached


def test_track_url_and_browser_wait_for_canonical_mode(tmp_path: Path) -> None:
    """The browser sees a numeric start only after raw mode has been left."""
    entry = next(e for e in catalog_entries() if e.track.title == "Rosin in the Subwoofer")
    assert track_url(tmp_path / "album.html", entry.track.start_s).endswith("?start=77.5715")
    assert track_url(tmp_path / "album.html", 0).endswith("?start=0")
    assert track_url(tmp_path / "album.html", 418.116375).endswith("?start=418.116375")

    class Gate:
        """Fake terminal that records raw-mode leave and re-entry."""

        def __init__(self) -> None:
            self.raw = True
            self.log: list[str] = []

        def leave(self) -> None:
            """Record that canonical mode was restored."""
            self.raw = False
            self.log.append("leave")

        def enter(self) -> None:
            """Record that raw mode was entered again."""
            self.raw = True
            self.log.append("enter")

    gate = Gate()
    opened: list[str] = []

    def opener(url: str) -> bool:
        assert gate.raw is False
        opened.append(url)
        return True

    url = open_selected_and_resume(
        gate,
        entry,
        cache_home=tmp_path / "cache",
        opener=opener,
        source=_html_gz(),
    )
    assert gate.log == ["leave", "enter"]
    assert gate.raw is True
    assert opened == [url]
    assert "start=77.5715" in url
    cached = list((tmp_path / "cache").rglob("*.html"))
    assert len(cached) == 1
    assert TRACK_START_ID in cached[0].read_text(encoding="utf-8")


def test_failed_materialize_does_not_open_or_leave_a_partial(tmp_path: Path) -> None:
    """A document without </body> never reaches the browser or the final cache name."""
    entry = catalog_entries()[0]

    class Gate:
        """Fake terminal that records raw-mode leave and re-entry."""

        def __init__(self) -> None:
            self.log: list[str] = []

        def leave(self) -> None:
            """Record that canonical mode was restored."""
            self.log.append("leave")

        def enter(self) -> None:
            """Record that raw mode was entered again."""
            self.log.append("enter")

    gate = Gate()

    def opener(url: str) -> bool:
        raise AssertionError(url)

    with pytest.raises(AlbumError):
        open_selected_and_resume(
            gate,
            entry,
            cache_home=tmp_path / "cache",
            opener=opener,
            source=gzip.compress(b"<html><body>no end"),
        )
    assert gate.log == ["leave", "enter"]
    cache = tmp_path / "cache"
    assert not cache.exists() or list(cache.rglob("*.html")) == []
    assert not cache.exists() or list(cache.rglob("*.partial")) == []
    with pytest.raises(AlbumError):
        materialize_html(b"not gzip", "coupon-seance-saturn.html.gz", tmp_path / "cache")
    with pytest.raises(AlbumError):
        materialize_html(_html_gz(), "../escape.html.gz", tmp_path / "cache")


def test_inject_is_idempotent_and_script_does_not_play() -> None:
    script = track_start_script()
    assert ".play(" not in script
    html = "<html><body><p>ok</p></body></html>"
    once = inject_track_start(html)
    twice = inject_track_start(once)
    assert twice == once
    assert once.lower().count("</body>") == 1


def test_cache_dir_is_versioned_under_xdg(tmp_path: Path) -> None:
    assert album_cache_dir(env={"XDG_CACHE_HOME": str(tmp_path)}) == (
        tmp_path / "agentic-av" / __version__ / "track-start-1"
    )
    fallback = Path.home() / ".cache" / "agentic-av" / __version__ / "track-start-1"
    assert album_cache_dir(env={}) == fallback


def test_bundled_album_materialize_does_not_touch_the_archive(tmp_path: Path) -> None:
    """The packaged gzip stays byte-for-byte identical after a cache publish."""
    asset = "coupon-seance-saturn.html.gz"
    resource = files("agentic_av").joinpath("albums", asset)
    before = resource.read_bytes()
    cached = materialize_html(before, asset, tmp_path)
    assert resource.read_bytes() == before
    with cached.open("rb") as handle:
        handle.seek(-4096, 2)
        tail = handle.read().decode("utf-8")
    assert f'id="{TRACK_START_ID}"' in tail
    assert tail.index(TRACK_START_ID) < tail.lower().rfind("</body>")


def test_command_dispatch_separates_library_and_visual_player(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    """Bare play is the library; demo, --show, and --scene stay on the visual player."""
    calls: list[str] = []

    def library(*_args, **_kwargs) -> int:
        calls.append("library")
        return 0

    def visual(*_args, **_kwargs) -> int:
        calls.append("visual")
        return 0

    monkeypatch.setattr("agentic_av.library.run_library", library)
    monkeypatch.setattr("agentic_av.tty.run_player", visual)
    assert main(["play", "--theme", "void", "--no-color"]) == 0
    assert main([]) == 0
    show = tmp_path / "show.toml"
    show.write_text(
        'title = "Reel"\ndetail = "study"\nduration = 12\nprograms = ["garden"]\n',
        encoding="utf-8",
    )
    assert main(["play", "--show", str(show), "--no-color"]) == 0
    assert main(["play", "--scene", "garden", "--theme", "phosphor", "--no-color"]) == 0
    assert main(["demo", "--theme", "newsprint", "--no-color"]) == 0
    assert calls == ["library", "library", "visual", "visual", "visual"]
    assert main(["preview", "--theme", "void", "--no-color", "--width", "20", "--height", "8"]) == 0
    assert "AAV" in capsys.readouterr().out


def test_library_and_visual_tty_errors_name_the_fallback(capsys) -> None:
    """A non-interactive play tells the listener which command still works."""
    assert main(["play", "--theme", "void", "--no-color"]) == 2
    assert "aav tracks" in capsys.readouterr().err
    assert main(["demo", "--no-color"]) == 2
    assert "aav preview" in capsys.readouterr().err
    assert main(["play", "--scene", "tide", "--no-color"]) == 2
    assert "aav preview" in capsys.readouterr().err


def test_motion_flag_reaches_native_playback(monkeypatch) -> None:
    """`aav play --motion still` holds the native picture, not just the demo's."""
    seen: list[str] = []

    def library(*_args, **kwargs) -> int:
        seen.append(kwargs["motion"])
        return 0

    monkeypatch.setattr("agentic_av.library.run_library", library)
    assert main(["play", "--motion", "still", "--no-color"]) == 0
    assert main(["play", "--no-color"]) == 0
    assert seen == ["still", "full"]


def test_library_sort_keeps_highlighted_song_for_native_playback(
    monkeypatch, tmp_path: Path
) -> None:
    """Sort on a PTY, then ensure Enter keeps the song and reports playback errors."""
    import fcntl
    import os
    import pty
    import struct
    import termios
    import threading

    from agentic_av.native import NativeError

    master, slave = pty.openpty()
    calls: list[str] = []

    def fake_native(entry, *_args, **kwargs) -> str:
        calls.append(f"{entry.track.title}:{kwargs['motion']}")
        assert kwargs["glyphs"] == "braille"
        raise NativeError("no audio player found; install mpv or ffplay")

    monkeypatch.setattr("agentic_av.native.play_native", fake_native)
    output = bytearray()
    first = catalog_entries()[0].track.title
    visible: list[bytes] = []
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))

    def drain() -> None:
        cues = [first.encode("utf-8"), b"ALBUM SORT", b"install mpv or ffplay"]
        keys = [b"s", b"\r", b"q"]
        while True:
            try:
                output.extend(os.read(master, 65536))
            except OSError:
                return
            if cues and cues[0] in output:
                visible.append(cues.pop(0))
                del output[:]
                os.write(master, keys.pop(0))

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    timed_out = threading.Event()

    def rescue() -> None:
        timed_out.set()
        os.write(master, b"q")

    watchdog = threading.Timer(5.0, rescue)
    watchdog.start()
    try:
        with (
            open(slave, "rb", buffering=0, closefd=False) as tty_in,
            open(slave, "w", encoding="utf-8", closefd=False) as tty_out,
        ):
            result = run_library(
                builtin_palettes()[0],
                "none",
                motion="reduced",
                glyphs="braille",
                input_stream=tty_in,
                output_stream=tty_out,
                cache_home=tmp_path,
            )
    finally:
        watchdog.cancel()
        os.close(slave)
        reader.join(timeout=2)
        os.close(master)
    assert result == 0
    assert calls == [f"{first}:reduced"]
    assert b"install mpv or ffplay" in visible
    assert not timed_out.is_set()


def test_library_browser_key_dispatches_on_a_pty(monkeypatch, tmp_path: Path) -> None:
    """Drive `o` through the real library input loop and verify its visible note."""
    import fcntl
    import os
    import pty
    import struct
    import termios
    import threading

    master, slave = pty.openpty()
    calls: list[str] = []
    opened: list[CatalogEntry] = []

    def fake_opener(url: str) -> bool:
        calls.append("browser")
        return True

    def fake_open(terminal, entry, *, cache_home, opener, source=None) -> str:
        opened.append(entry)
        terminal.leave()
        try:
            opener("file:///fake-album.html?start=0")
        finally:
            terminal.enter()
        return "file:///fake-album.html?start=0"

    monkeypatch.setattr("agentic_av.library.open_selected_and_resume", fake_open)

    output = bytearray()
    visible: list[bytes] = []
    entries = tuple(
        entry for entry in catalog_entries() if entry.album.asset == "coupon-seance-saturn.html.gz"
    )
    first = entries[0].track.title
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))

    def drain() -> None:
        cues = [first.encode("utf-8"), b"click Play"]
        keys = [b"o", b"q"]
        while True:
            try:
                output.extend(os.read(master, 65536))
            except OSError:
                return
            if cues and cues[0] in output:
                visible.append(cues.pop(0))
                del output[:]
                os.write(master, keys.pop(0))

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    timed_out = threading.Event()

    def rescue() -> None:
        timed_out.set()
        os.write(master, b"q")

    watchdog = threading.Timer(5.0, rescue)
    watchdog.start()
    try:
        with (
            open(slave, "rb", buffering=0, closefd=False) as tty_in,
            open(slave, "w", encoding="utf-8", closefd=False) as tty_out,
        ):
            result = run_library(
                builtin_palettes()[0],
                "none",
                input_stream=tty_in,
                output_stream=tty_out,
                opener=fake_opener,
                cache_home=tmp_path,
                entries=entries,
            )
    finally:
        watchdog.cancel()
        os.close(slave)
        reader.join(timeout=2)
        os.close(master)
    assert result == 0
    assert calls == ["browser"]
    assert len(opened) == 1 and opened[0].track.title == first
    assert b"click Play" in visible
    assert not timed_out.is_set()
