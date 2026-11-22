"""Bar arithmetic for track docs: meters, tempos, form tables, chord charts, rhythms, ABC heads."""

from fractions import Fraction

import pytest

from agentic_av import notation


def abc(body: str, meter: str = "4/4") -> list[str]:
    """Check an ABC head with a standard header (the body starts on line 6)."""
    return notation.check_abc(f"X:1\nT:Head\nM:{meter}\nL:1/8\nK:F\n{body}\n")


@pytest.mark.parametrize(
    ("text", "length"),
    [
        ("4/4", Fraction(1)),
        ("7/8", Fraction(7, 8)),
        ("2+2+3/8", Fraction(7, 8)),
        ("C", Fraction(1)),
        ("C|", Fraction(1)),
    ],
)
def test_meters_read_as_bar_lengths(text: str, length: Fraction) -> None:
    assert notation.parse_meter(text).length == length


@pytest.mark.parametrize("text", ["4/3", "0/4", "seven/8", "4/4/4"])
def test_meters_that_are_not_time_signatures_are_rejected(text: str) -> None:
    with pytest.raises(notation.NotationError):
        notation.parse_meter(text)


def test_bar_seconds_follow_the_beat_unit() -> None:
    def seconds(meter: str, tempo: str) -> Fraction:
        return notation.bar_seconds(notation.parse_meter(meter), notation.parse_tempo(tempo))

    assert seconds("4/4", "1/4=88") == Fraction(30, 11)
    assert seconds("7/8", "1/8=208") == Fraction(105, 52)
    assert seconds("6/8", "3/8=60") == 2


@pytest.mark.parametrize("text", ["88", "1/4=0", "q=88"])
def test_tempos_need_a_unit_and_a_rate(text: str) -> None:
    with pytest.raises(notation.NotationError):
        notation.parse_tempo(text)


def test_form_seconds_add_bars_tempo_changes_and_free_time() -> None:
    form = [
        notation.parse_form_section("A", "8", "4/4", "—"),
        notation.parse_form_section("B", "4", "4/4 @ 1/4=60", "keys solo"),
        notation.parse_form_section("Coda", "20s", "free", "—"),
    ]
    assert notation.form_seconds(form, notation.parse_tempo("1/4=120")) == 16 + 16 + 20


@pytest.mark.parametrize(("bars", "meter"), [("4", "free"), ("0", "4/4"), ("4.5", "4/4")])
def test_form_rows_reject_unreadable_lengths(bars: str, meter: str) -> None:
    with pytest.raises(notation.NotationError):
        notation.parse_form_section("A", bars, meter, "")


def test_clock_lengths() -> None:
    assert notation.parse_clock("4:31") == 271
    for text in ("4:61", "271", "4.31"):
        with pytest.raises(notation.NotationError):
            notation.parse_clock(text)


def test_chord_chart_counts_repeats_continuations_and_aliases() -> None:
    chart = (
        "Intro | Fmaj7 | % |\n"
        "A | Fmaj7 | Bbmaj7 | Am7 D7 | Gm7 C7 |\n"
        "  | Fmaj7 | N.C. |\n"
        "Solo = A\n"
    )
    bars, problems = notation.check_chord_chart(chart)
    assert problems == []
    assert bars == {"Intro": 2, "A": 6, "Solo": 6}


def test_chord_chart_reports_bad_tokens_and_unset_aliases() -> None:
    _, problems = notation.check_chord_chart("A | Fmaj7 | x7 |\nB = C\n")
    assert problems == [
        "chord line 1: 'x7' is not a chord, % or N.C.",
        "chord line 2: B = C, but C is unset",
    ]


def test_rhythm_grid_needs_whole_bars_of_steps() -> None:
    assert notation.check_rhythm("meter: 7/8 (2+2+3)  step: 1/8\nkick | x . x . x . . |") == []
    assert notation.check_rhythm("meter: 7/8 (2+2+3)  step: 1/8\nkick | x . x . x . |") == [
        "rhythm line 2 (kick), bar 1: 6 cells, needs 7"
    ]
    grouped = notation.check_rhythm("meter: 7/8 (2+2+2)  step: 1/8\nkick | x . x . x . . |")
    assert grouped == ["rhythm line 1: grouping (2+2+2) does not add up to 7"]


@pytest.mark.parametrize(
    "body",
    [
        "c2 A2 F2 A2 | B2 d2 c4 | (3cdc B2 A4 | F8 |]",
        "c>A F<A B2 c2 | F8 |]",
        "[CEG]4 z4 | Z | F8 |]",
        "!fermata!c2 .A2 ~F2 A2 | {g}F8 |]",
        "c2 A2 F2 A2 | [M:7/8] c2 A2 F3 | [M:4/4] F8 |]",
        "Z4 | F8 |]",
    ],
)
def test_abc_bars_that_add_up(body: str) -> None:
    assert abc(body) == []


def test_abc_reports_the_bar_that_does_not_add_up() -> None:
    assert abc("c2 A2 F2 A2 | B2 d2 c2 |]") == [
        "abc (Head), bar 2 (line 6): holds 6 of L:1/8 but 4/4 needs 8"
    ]


def test_abc_pickup_must_be_completed_by_the_last_bar() -> None:
    assert abc("C2 | F2 A2 c2 A2 | F6 |]") == []
    problems = abc("C2 | F2 A2 c2 A2 | F8 |]")
    assert len(problems) == 1
    assert "the last bar must hold the rest of a 4/4 bar" in problems[0]


def test_abc_counts_each_voice_and_compares_them() -> None:
    assert abc("V:RH\nc2 A2 F2 A2 | F8 |]\nV:LH\nF,8 | C,8 |]") == []
    assert abc("V:RH\nc2 A2 F2 A2 | F8 |]\nV:LH\nF,8 |]") == [
        "abc (Head): voices have different bar counts (RH 2, LH 1)"
    ]


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("c2 A2 F2 A2 & F8 |]", "'&' voice overlays are not allowed"),
        ("Tc2 A2 F2 A2 |]", "'T' is not allowed in music"),
        ("c2 A2 F2 A2 |]\nw: la la la la", "lyrics lines are not allowed"),
    ],
)
def test_abc_rejects_what_the_subset_leaves_out(body: str, message: str) -> None:
    assert any(message in problem for problem in abc(body))


def test_abc_header_must_be_complete() -> None:
    assert notation.check_abc("X:1\nM:4/4\nL:1/8\nK:F\nc8 |]") == [
        "abc: header needs X:, T:, M:, L: and K: (missing T:)"
    ]
