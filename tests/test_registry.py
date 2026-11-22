"""Band, visual group, album and track docs against docs/spec/band-album-spec.md.

The negative cases fill in the four templates as a complete fixture album (which must pass in full),
then break one rule each, the way a generated album most plausibly would.
"""

import re
from pathlib import Path

import pytest

from clangor_visualis_machina.registry import (
    KINDS,
    main,
    slugify,
    validate_roots,
    validate_template,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
WORKED_TEST = ROOT / "docs" / "spec" / "worked-test"

# 99 words: long enough for personas, descriptions, the concept and mastery prose.
PROSE = " ".join(["The member listens for the space between phrases and answers it."] * 9)
PASS_ONE = "Wrote the form and the head, keeping the coda open for the second member."
PASS_TWO = "Shortened the intro to four bars because the head needs to arrive sooner."
REASONS = "Round 2 keeps the head clear, and round 1 leaves the coda its silence."

COMMON = {
    "B-NN": "B-99",
    "V-NN": "V-99",
    "YYYY-MM-DD": "2026-11-21",
    "- [ ]": "- [x]",
    "Persona paragraph.": PROSE,
    "Description paragraph.": PROSE,
    "Concept paragraph.": PROSE,
    "Mastery notes.": PROSE,
    "What was written, and why.": PASS_ONE,
    "What changed, and why.": PASS_TWO,
    "Why the band chose this combination.": REASONS,
    "Why the group chose this combination.": REASONS,
}
FILLS = {
    "band": {"Band Name": "Fixture Band", "band-name": "fixture-band"},
    "visual-group": {
        "Visual Group Name": "Fixture Visuals",
        "visual-group-name": "fixture-visuals",
    },
    "album": {
        'id = "A-NN"': 'id = "A-02"',
        'album = "A-NN"': 'album = "A-01"',
        'scope = "album"': 'scope = "test"',
    },
    "track": {'album = "A-NN"': 'album = "A-02"'},
}
PATHS = {
    "band": "bands/B-99-fixture-band.md",
    "visual-group": "visual-groups/V-99-fixture-visuals.md",
    "album": "albums/B-99-fixture-band/A-02-album-title/album.md",
    "track": "albums/B-99-fixture-band/A-02-album-title/tracks/01-track-title.md",
}


def write_fixture(root: Path) -> dict[str, Path]:
    """Write the four templates, filled in, as a band, a visual group and a one-track album."""
    files = {}
    for kind in KINDS:
        text = (TEMPLATES / f"{kind}.md").read_text(encoding="utf-8")
        for old, new in [*FILLS[kind].items(), *COMMON.items()]:
            text = text.replace(old, new)
        path = root / PATHS[kind]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        files[kind] = path
    return files


def problems_after(root: Path, path: Path, old: str, new: str) -> list[str]:
    """Replace the first ``old`` in ``path``, then validate ``root``."""
    text = path.read_text(encoding="utf-8")
    assert old in text, f"fixture no longer contains {old!r}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return [problem.message for problem in validate_roots([root])]


def test_repository_and_worked_test_docs_meet_the_spec() -> None:
    assert [str(problem) for problem in validate_roots([ROOT, WORKED_TEST])] == []


@pytest.mark.parametrize("kind", KINDS)
def test_templates_meet_their_kind(kind: str) -> None:
    text = (TEMPLATES / f"{kind}.md").read_text(encoding="utf-8")
    assert [str(problem) for problem in validate_template(kind, text)] == []


def test_swarm_prompt_carries_every_template_verbatim() -> None:
    prompt = (ROOT / "prompts" / "swarm.md").read_text(encoding="utf-8")
    embedded = dict(
        re.findall(r"^#### Template: ([a-z-]+)\n\n````markdown\n(.*?)\n````$", prompt, re.M | re.S)
    )
    assert sorted(embedded) == sorted(KINDS)
    for kind, text in embedded.items():
        assert text + "\n" == (TEMPLATES / f"{kind}.md").read_text(encoding="utf-8"), kind


def test_filled_in_templates_pass_in_full(tmp_path: Path) -> None:
    write_fixture(tmp_path)
    assert [str(problem) for problem in validate_roots([tmp_path])] == []


@pytest.mark.parametrize(
    ("kind", "old", "new", "expected"),
    [
        pytest.param(
            "band",
            'roles = ["musician"]\ninstruments = ["instrument"]',
            'roles = ["composer"]',
            "a band needs at least two musicians",
            id="one-musician",
        ),
        pytest.param(
            "band",
            'roles = ["musician", "composer"]',
            'roles = ["musician"]',
            "at least one musician must also be a composer",
            id="no-composer",
        ),
        pytest.param(
            "band",
            'instruments = ["instrument"]',
            'instruments = ["lead vocals"]',
            "no voice parts; albums are instrumental",
            id="voice-instrument",
        ),
        pytest.param(
            "band",
            'roles = ["musician"]\ninstruments = ["instrument"]',
            'roles = ["musician"]\ninstruments = ["drum kit"]',
            "Member Two — instrument: not one of their band-card instruments",
            id="part-not-on-band-card",
        ),
        pytest.param(
            "album",
            'direction = "Up to 220 characters from the person commissioning the album; '
            'empty if none."',
            f'direction = "{"x" * 221}"',
            "the direction is 221 characters; max 220",
            id="direction-too-long",
        ),
        pytest.param(
            "album",
            'mastered_by = "Member Two"',
            'mastered_by = "Member One"',
            "mastering credit must be Member One",
            id="mastering-credit-mismatch",
        ),
        pytest.param(
            "album",
            'made_with = ["provider/model"]',
            'made_with = ["other/model"]',
            "made_with is missing provider/model",
            id="model-missing-from-made-with",
        ),
        pytest.param(
            "album",
            'scope = "test"',
            'scope = "album"',
            "the album runs 1:05; scope album needs 25:00 to 30:00",
            id="album-too-short",
        ),
        pytest.param(
            "track",
            "- Take 3: How this take differs from takes 1 and 2.\n",
            "",
            "a take block is three '- Take N:' bullets and a '- Picked by'",
            id="two-takes",
        ),
        pytest.param(
            "track",
            "- Picked by Member Two: Take 2",
            "- Picked by Member One: Take 2",
            "Member One cannot pick their own take",
            id="self-pick",
        ),
        pytest.param(
            "track",
            "- Picked by Member One: Take 1",
            "- Picked by Stranger: Take 1",
            "Stranger is not a member who can pick",
            id="outside-pick",
        ),
        pytest.param(
            "track",
            'part = "mastering"\nmodel = "provider/model"\n',
            'part = "mastering"\n',
            "is missing `model`",
            id="credit-without-model",
        ),
        pytest.param(
            "track",
            '[[credits]]\nmember = "Visual Two"\npart = "visuals"\nmodel = "provider/model"\n',
            "",
            "credit each visual group member once with part `visuals`",
            id="visual-member-uncredited",
        ),
        pytest.param(
            "track",
            "| A | 8 |",
            "| A | 7 |",
            "section A has 7 bars in the form but 8 in the chart",
            id="form-and-chart-disagree",
        ),
        pytest.param(
            "track",
            "| B2 d2 c4 | A2",
            "| B2 d2 c2 | A2",
            "holds 6 of L:1/8 but 4/4 needs 8",
            id="head-bar-short",
        ),
        pytest.param(
            "track",
            'length = "1:05"',
            'length = "3:00"',
            "length 3:00 does not match the form",
            id="length-not-from-form",
        ),
        pytest.param(
            "track",
            "## Mastery\n",
            "## Arrangement\n\nStrings double the head.\n\n## Mastery\n",
            "unknown section '## Arrangement'",
            id="unknown-section",
        ),
        pytest.param(
            "track",
            f"### Pass 2 — Member One\n\n{PASS_TWO}\n\n",
            "",
            "Member One logged 1 pass; composers do two or three",
            id="one-pass",
        ),
        pytest.param(
            "track",
            "None — instrumental.",
            "Softly, the river sings.",
            "albums are instrumental",
            id="lyrics",
        ),
        pytest.param(
            "track",
            "- Member Two — instrument: Round 1, Take 1\n",
            "",
            "Band decision has no choice for Member Two — instrument",
            id="undecided-slot",
        ),
        pytest.param(
            "track",
            " Still: the exact frame held.",
            "",
            "'**Motion:**' covers full, reduced and still motion",
            id="scene-without-still-motion",
        ),
        pytest.param(
            "track",
            "- [x] Instrumental",
            "- [ ] Instrumental",
            "unchecked self-review item",
            id="unchecked-self-review",
        ),
    ],
)
def test_each_broken_rule_is_reported(
    tmp_path: Path, kind: str, old: str, new: str, expected: str
) -> None:
    files = write_fixture(tmp_path)
    problems = problems_after(tmp_path, files[kind], old, new)
    assert any(expected in problem for problem in problems), problems


def test_cli_prints_located_problems_and_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = write_fixture(tmp_path)
    assert main([str(tmp_path)]) == 0
    problems_after(tmp_path, files["track"], 'length = "1:05"', 'length = "3:00"')
    assert main([str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert re.search(rf"^{re.escape(str(files['track']))}:\d+: length 3:00 does not", out, re.M)


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("Buy One, Haunt One Free", "buy-one-haunt-one-free"),
        ("Don't Wake the Ferns", "dont-wake-the-ferns"),
        ("Café Ångström", "cafe-angstrom"),
        ("Are We Fish?", "are-we-fish"),
    ],
)
def test_slugs(name: str, slug: str) -> None:
    assert slugify(name) == slug
