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

## Amendment 2026-11-18: CC0 for bundled albums, MIT for code

Aven decided the repository license on 2026-11-18: code under the MIT License
(LICENSE) and the bundled albums (audio and bundled cover art) dedicated to
the public domain under CC0 (LICENSE-CC0). Material not bundled in this
repository stays out and is not covered. This amendment supersedes the "not a
license change" and "grants no open license" language above; those lines
record the position at the time this decision was written, before the license
was applied.

## Amendment 2026-11-18: Drowning Collective A-02

Aven's 2026-11-18 round-two run instruction directs the other three bands' A-02 albums to be **made, bundled and PR'd**, following Nurse Log's second-album process. This branch implements Drowning Collective, *The Shape That Stays*: six original instrumentals, 1,632 seconds (27:12), made by **`openai-codex/gpt-6.1-sol`** through omp. The model is recorded in the production module's `MADE_WITH`, the local manifest's member and track model fields, and the embedded page data. No album-direction prompt was supplied: “none supplied; the band chose its direction within its documented identity.” The recorded debut review remains positive for tracks 01, 03 and 04; 02, 05 and 06 remain pending.

The exact added media are:

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `albums/drowning-collective-the-shape-that-stays.html.gz` | 38,275,169 | `e60a51ce7e5788c9a0b364c08a32e4a2ef5e81fa1a9eda6bb19e83504f090caa` |
| Decompressed UTF-8 HTML | 53,318,791 | `825ea4f55144a4ef0271c1a868034443487d776ca5730ee85005f54637067665` |
| `artwork/drowning-collective-the-shape-that-stays.jpg` | 404,381 | `15ebebe5901876171853a20858d7f828b989bbca8c3d4fd4d78f15f2a2933d4a` |

The archive is `gzip -9 -n` of the finished offline page, which embeds the exact six tagged MP3 masters and procedural score-driven Canvas code. The cover is a baseline RGB JPEG, **1024×1024**, converted without cropping or resampling from generated candidate C, *Braided Shelf*. It contains no added typography or metadata. The image service returned provider `openai-codex`, model `gpt-image-2-codex` (catalog entry `openai-codex/gpt-image-2`), quality `low`; no unreturned seed or task identifier is inferred. This image-generation model is distinct from the album maker named above.

**Cover status: agent-proposed**, not creator-selected. Aven confirms or swaps it at merge; a swap requires the corresponding asset, catalog digest and receipt tests to change together. **Aven's merge is publication approval** for the album and retained cover, not a listening review. This amendment extends the earlier single-album scope only to these two media assets. Source archives, stems, first takes, rejected cover candidates and unrelated private band material remain unbundled. The existing CC0 amendment applies to this bundled album and cover; player code remains MIT.

The catalog adds six cumulative movement starts (0, 268, 516, 808, 1084, 1316), a hash-pinned `CoverArt`, `window.DC2_ALBUM` extraction and the separate `undertow` native family. The page owns album-second `?start=` deep links on `#album-audio`; the library's legacy `#audio` seeker is intentionally a no-op there. Digital music checks passed for both actual passes and all masters; the continuous FLAC is PCM-identical to the ordered tracks. Physical translation listening and Aven's album-two review remain pending.
