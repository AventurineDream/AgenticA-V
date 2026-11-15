# 0002 — Bundle four public albums and open them in the browser

## Context

The visual player in decision 0001 is a media-free instrument. Four completed A-01 albums now have self-contained offline HTML players, and those archives are authorized for public bundling. Browser autoplay is blocked, and the pages already own synchronized audio and pictures. The sources do not name distinct per-track musicians.

## Decision

Ship those four gzip HTML albums in the package. All rights remain reserved; this is not a license change. `aav play` with no show or scene opens a terminal track selector. Enter restores the terminal, materializes a cache copy, and opens the default browser at that movement. The listener clicks Play. The browser page is the full synchronized album. `aav demo`, and `aav play` with `--show` or `--scene`, keep the abstract visual player.

Album artist and band are the same credit. Do not invent performer credits. Do not add in-progress, archive, or private albums. Do not rewrite the packaged gzip files.

## Consequences

The public repository now contains authorized album media. Cache copies live under the versioned XDG cache and can be deleted without touching the package. A terminal browser or `xdg-open` must not inherit raw mode. The visual player's motion and theme contracts are unchanged.
