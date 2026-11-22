# Contributing

Terminally Agentic A/V accepts code contributions by invitation only. Code
contributions are closed by default: communicate before opening a pull request,
and proceed only if the project owner is interested. The project owner directs the
main branch.

## Before you write code

1. Open an issue that describes the problem or change, and what you would like to
   contribute.
2. Wait for the project owner's reply. A reply of interest is the only go-ahead.
3. Only then open a pull request. Pull requests opened without that agreement may
   be closed without review.

Merging is the project owner's decision and is not implied by an issue reply or
by passing checks.

## Forks

Forks and independent experiments are welcome under the license terms (see
below). You do not need permission to fork or to experiment outside this repository.

## If your pull request is accepted

- Run the full gate from `AGENTS.md` and include the command and result:
  `uv run ruff format --check && uv run ruff check && uv run pytest`.
- Keep the diff focused on one change, and put formatting-only changes in their own commit.
- Follow the code standard in `AGENTS.md`: source files start with a header comment,
  public functions have doc comments, and comments say why rather than what.
- Update `CHANGELOG.md` under Unreleased for user-visible changes.

## What is not accepted through this process

- Albums, artwork, stems, source archives, or other media. Bundled albums are
  curated by the project owner (see `AGENTS.md`, Public scope).
- Private or unpublished band material of any kind.

The creator-facing path for making new bands and albums is described in
`docs/plans/PROJECT-ROADMAP.md`. It is separate from code contributions.

## License

The code is MIT-licensed (see `LICENSE`). Bundled albums and their artwork are CC0
(see `LICENSE-CC0`).
