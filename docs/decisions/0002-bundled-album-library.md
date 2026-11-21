# 0002 — Bundle public albums and open them in the browser

## Context

The visual player in decision 0001 is a media-free instrument. Four completed A-01 albums now have self-contained offline HTML players, and those archives are authorized for public bundling. Browser autoplay is blocked, and the pages already own synchronized audio and pictures. The sources do not name distinct per-track musicians.

## Decision

Ship those four gzip HTML albums in the package, plus the A-02 albums named in the dated amendments below. All rights remain reserved; this is not a license change. `aav play` with no show or scene opens a terminal track selector. Enter restores the terminal, materializes a cache copy, and opens the default browser at that movement. The listener clicks Play. The browser page is the full synchronized album. `aav demo`, and `aav play` with `--show` or `--scene`, keep the abstract visual player.

Album artist and band are the same credit. Do not invent performer credits. Do not add in-progress, archive, or private albums. Any further album needs its own dated approval recorded in this file. Do not rewrite the packaged gzip files.

## Consequences

The public repository now contains authorized album media. Cache copies live under the versioned XDG cache and can be deleted without touching the package. A terminal browser or `xdg-open` must not inherit raw mode. The visual player's motion and theme contracts are unchanged.

## Amendment 2026-11-18: one additional album

Aven approved public bundling of Nurse Log, *The Forest Has a Pocket* (A-02). The package adds exactly one asset, `albums/nurse-log-the-forest-has-a-pocket.html.gz`: gzip of the approved 72,058,058-byte player page, 49,982,951 bytes, SHA-256 `bd7887dc5884230721fa3be9cd508697b0231fe6bdb8ced521b8f9770fec50a3`. This is a single-album exception. The source archive's `album.json` still declares `public_release: false`; this approval supersedes that flag for this album only. It does not cover the source ZIP, stems, master files, candidate artwork, or other material, and it grants no open license and no listening-review approval. Cover artwork was not part of this approval; the selected cover is approved in the amendment below, which adds a second asset.

## Amendment: selected cover for A-02

Aven directly approved public bundling of the selected cover for A-02 with the album, on 2026-11-18. The package adds `artwork/nurse-log-the-forest-has-a-pocket.jpg`: the selected JPEG `05_Selected-Artwork_Photo-3.jpg` from the A-02 album folder, 1024×1024 pixels, 370,848 bytes, SHA-256 `e42821bc820a81a7f6b6e168dc772d1540aebfe256bfda23387bc9aecc9fdab6`, verified against the selection receipt. Its bytes stay identical to the receipt. EXIF metadata contains orientation, resolution, sRGB color space, and pixel dimensions; there is no GPS, XMP, or ICC data. The catalog records this cover on A-02 alone. This amendment grants no approval for candidate artwork, the source archive, stems, or other images. The four A-01 covers did not exist yet; they are recorded in the A-01 cover amendment below.

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

## Amendment 2026-11-18: Coupon Seance A-02 and its cover

Aven's 2026-11-18 run instruction directed the remaining round-two A-02 albums to be made, bundled, and opened as pull requests, one per album, for her to merge. Under that instruction this change adds Coupon Seance, *Buy One, Haunt One Free* (A-02), made by anthropic/claude-opus-5-5 and recorded as such in the page's album JSON (`made_with`). Her merge of this pull request is the publication approval; the instruction alone is not.

The package adds two assets. `albums/coupon-seance-buy-one-haunt-one-free.html.gz` is the `gzip -9 -n` of the built 52,431,005-byte player page (SHA-256 `fa9672cdba93f7bc3a19a8689f89ebc0af865b166297baa043394274b534fced`): 38,493,904 bytes, SHA-256 `6d18ba3cd44f3ad2258907a8fc7719c372de9a7d6016e0f8fa71779d2ee96be9`. `artwork/coupon-seance-buy-one-haunt-one-free.jpg` is the album's selected cover, 1024×1024 pixels, 221,166 bytes, SHA-256 `4e0418ab45a0285967c980318bf976a11cf120f1a72243f05d7d49a8b5e3047f`; it is a baseline JPEG with JFIF headers only (no EXIF, GPS, XMP, or ICC data). The cover is agent-proposed, one of three candidates generated for this album; Aven's merge approves it together with the album. If she chooses a different cover, the replacement needs a new hash here and in the catalog.
## Amendment 2026-11-18: Quiet Machinery A-02 and its cover

Aven's 2026-11-18 run instruction directed the remaining round-two A-02 albums to be made, bundled, and opened as pull requests, one per album, for her to merge. Under that instruction this change adds Quiet Machinery, *Instruments for Measuring Dusk* (A-02), made by anthropic/claude-opus-5-5 and recorded as such in the page's album JSON (`made_with`). Her merge of this pull request is the publication approval; the instruction alone is not.

The package adds two assets. `albums/quiet-machinery-instruments-for-measuring-dusk.html.gz` is the `gzip -9 -n` of the built 52,814,897-byte player page (SHA-256 `9312ea491df87d3c75b0d9fe8d6011d084111682ab843120c2b7b7c37240a177`): 38,256,695 bytes, SHA-256 `881b22458e6d8bd1a04b5c330e5b276bd11a60036e559edb5841a2aff71c164b`. `artwork/quiet-machinery-instruments-for-measuring-dusk.jpg` is the album's selected cover, 1024×1024 pixels, 134,913 bytes, SHA-256 `cd29193cde9fc0a53e40fd8b37fda8fa845ffc397dd0c39451fb19bf1db4c81a`; it is a baseline JPEG with JFIF headers only (no EXIF, GPS, XMP, or ICC data). The cover is agent-proposed candidate A ("measuring instrument") of three candidates generated for this album; Aven's merge approves it together with the album. If she chooses a different cover, the replacement needs a new hash here and in the catalog.

This amendment does not cover the source package, stems, masters, the other cover candidates, or any listening-review approval; the album's listening review is pending. Both assets are covered by the CC0 amendment above.

## Amendment 2026-11-18: selected covers for the four A-01 albums

No selected A-01 cover existed, so Malachite generated four candidates per A-01 album with `openai-codex/gpt-image-2` (`gpt-image-2-codex` through omp's image tool): 1024×1024, no typography, saved as JPEG quality 95 (4:4:4). On 2026-11-18 Aven chose one per album, in her own words: "Saturn 4, Fish 1, Ground 3, Atlas 4". These covers are **creator-selected**, not agent-proposed. Each album's Drive folder `03_Files/Artwork/` holds the selected file `05_Selected-Artwork_Candidate-N.jpg`, its receipt `06_Selection-Receipt.json` (same shape as A-02's: exact prompt, generator PNG hash, SHA-256, bytes, dimensions, format, and the remotely verified Drive copy), and every candidate under `Candidate-Archive/` with its manifest. The package adds four JPEGs, byte-identical to those receipts, each 1024×1024 RGB with JFIF headers only (no EXIF, GPS, XMP, or ICC data):

| Album | Asset | Candidate | Bytes | SHA-256 |
| --- | --- | ---: | ---: | --- |
| Coupon Seance, *Saturn Has a Dollar Store* | `artwork/coupon-seance-saturn.jpg` | 4 | 402,633 | `b44173b91ff51c4bada8fb601180858a414c931d049e429f4205049d608d1dbe` |
| Drowning Collective, *Are We Fish?* | `artwork/drowning-collective-are-we-fish.jpg` | 1 | 416,511 | `07eb2ef0caa9977f9f4f905dce13bb92fece2e6f0a049468c609dcff72c38385` |
| Nurse Log, *The Ground Moves Anyway* | `artwork/nurse-log-ground-moves-anyway.jpg` | 3 | 779,334 | `76762a94a87b14db5f5b8a1cb2576fe3784cb9012eba710a33cad57c2ed8cbbd` |
| Quiet Machinery, *The Atlas of Unlit Rooms* | `artwork/quiet-machinery-atlas-unlit-rooms.jpg` | 4 | 315,007 | `d479b0d15146192fa17fe76f4929c3e520b4bc1c56861a4ed9bc06294901244f` |

Each A-01 catalog record names its own hash-pinned `CoverArt`. Unselected candidates, the generator's PNG output, contact sheets, and receipts stay out of the package. The four covers are covered by the CC0 amendment above; player code remains MIT.
