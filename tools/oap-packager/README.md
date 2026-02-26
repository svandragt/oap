# OAP Packager (v1)

Reference packager for building **OAP v1.0** (`.oap`) archives.

This tool produces fully conformant Open Album Package files:

* ZIP container
* **STORE-only** entries (no compression)
* Required `playlist.m3u8`
* Optional `segmentNN.m3u8`
* `manifest.json`
* Strict `checksums.json` (SHA-256, full coverage rule)
* FLAC audio only
* WebVTT lyrics only
* JPEG/PNG artwork only

No external dependencies. Python standard library only.

---

## Features

* Enforces **OAP v1 structural rules**
* Generates canonical playlist
* Supports optional segment groupings
* Validates:

  * FLAC headers
  * WebVTT headers
  * JPEG/PNG magic bytes
  * BCP 47 language tags (basic validation)
* Enforces strict checksum set equality
* Verifies ZIP entries are STORE-only
* Fails hard on any non-conformance

---

## Requirements

* Python 3.10+
* [`uv`](https://github.com/astral-sh/uv)

---

## Setup

```bash
uv init oap-packager
cd oap-packager
# add oap_packager.py
uv run python oap_packager.py --help
```

No additional dependencies required.

---

## Quick Start

Minimal build (audio only):

```bash
uv run python oap_packager.py \
  --out ExampleAlbum.oap \
  --audio-dir ./input/audio
```

This produces a valid OAP v1 package with:

* `playlist.m3u8`
* `manifest.json`
* `checksums.json`
* `audio/*.flac`

---

## Full Example

```bash
uv run python oap_packager.py \
  --out ExampleAlbum.oap \
  --audio-dir ./input/audio \
  --lyrics-dir ./input/lyrics \
  --cover ./input/cover.jpg \
  --gallery-dir ./input/gallery \
  --title "Example Album" \
  --album-artist "Example Artist" \
  --release-date 2026-02-01 \
  --languages en,ja \
  --segments "1:Side A:1-5;2:Side B:6-10"
```

---

## Input Expectations

### Audio (Required)

* Directory containing FLAC files
* Files are sorted lexicographically for canonical order
* Valid FLAC header required (`fLaC`)

Example:

```
input/audio/
├── 01.flac
├── 02.flac
└── 03.flac
```

---

### Lyrics (Optional)

Directory containing WebVTT files.

Supported filename patterns:

```
01.vtt
01.en.vtt
01.ja.vtt
```

Rules:

* Must begin with `WEBVTT`
* Track numbers must be two digits
* Language tags must be valid BCP 47 (basic validation)

Multiple language variants per track supported.

---

### Cover (Optional)

Single JPEG or PNG:

```
--cover ./input/cover.jpg
```

---

### Gallery (Optional)

Directory of JPEG/PNG files:

```
--gallery-dir ./input/gallery
```

Images are ordered lexicographically.

---

### Segments (Optional)

Format:

```
"N:Label:tracks;N:Label:tracks"
```

Examples:

```
"1:Side A:1-5;2:Side B:6-10"
"1:Disc 1:1-8;2:Disc 2:9-16"
```

Track expressions support:

* Single numbers: `3`
* Ranges: `1-5`
* Mixed: `1-3,7,9-10`

Generates:

```
segment01.m3u8
segment02.m3u8
```

Canonical playback order is always defined by `playlist.m3u8`.

---

## Output Structure

Generated `.oap` contains:

```
playlist.m3u8        (required)
manifest.json        (Level 2)
checksums.json       (Level 2)
segmentNN.m3u8       (optional)
audio/*.flac
lyrics/*.vtt         (optional)
images/*             (optional)
```

All ZIP entries:

* Use STORE compression
* Use UTF-8 filenames
* Use forward slashes

Any compressed entry would violate OAP v1.

---

## Integrity

The tool generates `checksums.json` with:

* SHA-256 digests
* Strict coverage rule:

```
keys(checksums.files) == archive_files - { "checksums.json" }
```

After writing the archive, the tool:

* Verifies strict coverage
* Recomputes and validates all hashes
* Confirms all ZIP entries use STORE

Build fails on any mismatch.

---

## Design Notes

* Playback order is defined exclusively by `playlist.m3u8`.
* `manifest.json` adds metadata only.
* No signatures are generated (OAP v1 is intentionally hackable).
* No compression beyond STORE is allowed.

---

## Limitations (Intentional)

* No video support
* No additional audio codecs
* No additional lyric formats
* No embedded duration parsing (playlist uses `#EXTINF:-1`)
* No image dimension extraction (manifest does not auto-fill width/height)

---

## Roadmap Ideas

Possible extensions (outside OAP v1):

* FLAC duration extraction for accurate `#EXTINF`
* Image dimension extraction
* Deterministic ZIP entry ordering guarantees
* Reproducible build mode
* JSON Schema validation for manifest

---

## License

?
