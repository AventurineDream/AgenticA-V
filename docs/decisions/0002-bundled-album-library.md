# 0002 — Bundle public albums and open them in the browser

## Context

The visual player in decision 0001 is a media-free instrument. Four completed A-01 albums now have self-contained offline HTML players, and those archives are authorized for public bundling. Browser autoplay is blocked, and the pages already own synchronized audio and pictures. The sources do not name distinct per-track musicians.

## Decision

Ship those four gzip HTML albums in the package, plus the single A-02 album named in the 2026-11-18 amendment below. All rights remain reserved; this is not a license change. `aav play` with no show or scene opens a terminal track selector. Enter restores the terminal, materializes a cache copy, and opens the default browser at that movement. The listener clicks Play. The browser page is the full synchronized album. `aav demo`, and `aav play` with `--show` or `--scene`, keep the abstract visual player.

Album artist and band are the same credit. Do not invent performer credits. Do not add in-progress, archive, or private albums. Any further album needs its own dated approval recorded in this file. Do not rewrite the packaged gzip files.

## Consequences

The public repository now contains authorized album media. Cache copies live under the versioned XDG cache and can be deleted without touching the package. A terminal browser or `xdg-open` must not inherit raw mode. The visual player's motion and theme contracts are unchanged.

## Amendment 2026-11-18: one additional album

Aven approved public bundling of Nurse Log, *The Forest Has a Pocket* (A-02). The package adds exactly one asset, `albums/nurse-log-the-forest-has-a-pocket.html.gz`: gzip of the approved 72,058,058-byte player page, 49,982,951 bytes, SHA-256 `bd7887dc5884230721fa3be9cd508697b0231fe6bdb8ced521b8f9770fec50a3`. This is a single-album exception. The source archive's `album.json` still declares `public_release: false`; this approval supersedes that flag for this album only. It does not cover the source ZIP, stems, master files, candidate artwork, or other material, and it grants no open license and no listening-review approval. Cover artwork was not part of this approval; the selected cover is approved in the amendment below, which adds a second asset.

## Amendment: selected cover for A-02

Aven directly approved public bundling of the selected cover for A-02 with the album, on 2026-11-18. The package adds `artwork/nurse-log-the-forest-has-a-pocket.jpg`: the selected JPEG `05_Selected-Artwork_Photo-3.jpg` from the A-02 album folder, 1024×1024 pixels, 370,848 bytes, SHA-256 `e42821bc820a81a7f6b6e168dc772d1540aebfe256bfda23387bc9aecc9fdab6`, verified against the selection receipt. Its bytes stay identical to the receipt. EXIF metadata contains orientation, resolution, sRGB color space, and pixel dimensions; there is no GPS, XMP, or ICC data. The catalog records this cover on A-02 alone. This amendment grants no approval for candidate artwork, the source archive, stems, or other images. The four A-01 selected cover images were not available to this build, so their artwork remains unbundled.
