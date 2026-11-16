"""Album catalog order, library frame bounds, deep links, and command dispatch."""

import gzip
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
    album_cache_dir,
    apply_library_key,
    compose_library,
    inject_track_start,
    materialize_html,
    open_selected_and_resume,
    track_start_script,
    track_url,
)
from agentic_av.paint import render_ansi, render_plain
from agentic_av.palette import builtin_palettes

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
)


def test_public_catalog_is_the_four_authorized_albums() -> None:
    """Band is the album artist, and only the completed A-01 albums are listed."""
    validate_catalog()
    assert len(ALBUMS) == 4
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
    assert len(public) == 25
    titles = [entry.track.title for entry in public]
    assert titles.index("We Kept the Receipt") < titles.index("An Uneven Kindness")
    assert titles.index("The Water Learns Major") < titles.index("Under Six Feet of Moss")
    assert titles.index("The Ground Moves Anyway") < titles.index("Copper Gravity")


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
    """j/k and arrows move; Enter opens only when help is closed."""
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
    assert state.selected == held
    assert state.show_help
    assert apply_library_key(state, "esc", count=25) == "stay"
    assert not state.show_help
    assert apply_library_key(state, "enter", count=25) == "open"
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
    entry = catalog_entries()[1]
    assert entry.track.title == "Rosin in the Subwoofer"
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
