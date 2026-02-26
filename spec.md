Below is the cleaned-up **Open Album Package (OAP) v1.0 Specification** incorporating all agreed decisions.

---

# Open Album Package (OAP)

Version 1.0

---

## 1. Overview

Open Album Package (OAP) is an open, hackable, deterministic album container format designed for progressive enhancement.

An OAP package:

* Is a ZIP archive
* Uses STORE compression only
* Contains a canonical M3U8 playlist
* Uses FLAC for audio
* Uses WebVTT for synced lyrics
* Uses JPEG and/or PNG for artwork
* Supports progressive enhancement via conformance levels
* Uses SHA-256 checksums for integrity verification (Level 2)

OAP v1 explicitly excludes:

* DRM
* Digital signatures
* Video
* Remote media references
* Multiple audio codecs
* Multiple lyric formats

---

## 2. Container Format

### 2.1 Archive

* Container: **ZIP**
* Compression method: **STORE only**
* All entries MUST use STORE (no compression).
* Any compressed entry renders the package **non-conformant to OAP v1**.
* Filenames MUST be UTF-8 encoded.
* Path separator MUST be `/`.
* All paths MUST be relative.
* Paths MUST NOT contain `..`.
* Absolute paths are forbidden.

Directory entries MAY exist but are not required.

---

## 3. Required and Optional Files

### 3.1 Required (All Packages)

```
/playlist.m3u8
```

### 3.2 Optional

```
/manifest.json
/checksums.json
/segmentNN.m3u8      (NN = 01–99)
/audio/*.flac
/images/*
/lyrics/*.vtt
```

---

## 4. Conformance Levels

### Level 0 — Extract + Play

* MUST support `/playlist.m3u8`
* MUST play referenced FLAC files
* MUST ignore `/manifest.json`
* MUST ignore `/checksums.json`
* MUST ignore unknown files

---

### Level 1 — Archive-Aware Audio

* MUST read `/playlist.m3u8` from within the ZIP
* MUST stream FLAC entries from within the ZIP (STORE)
* MAY use `/segmentNN.m3u8` for grouping
* MAY ignore `/manifest.json`
* MAY ignore `/checksums.json`

---

### Level 2 — Full Experience

* MUST support `/manifest.json`
* MUST support WebVTT lyrics
* MUST support JPEG and PNG images
* MUST validate `/checksums.json`
* MUST reject packages failing checksum validation

---

## 5. Playlists

### 5.1 Canonical Playlist

The package MUST contain:

```
/playlist.m3u8
```

Rules:

* UTF-8 encoded
* Extended M3U format (`#EXTM3U`)
* Relative paths only
* Defines canonical playback order

Track order in `/playlist.m3u8` is authoritative.

Manifest MUST NOT redefine playback order.

---

### 5.2 Segment Playlists (Optional)

Optional grouping playlists MAY exist:

```
/segment01.m3u8
...
/segment99.m3u8
```

Rules:

* Informational only
* MUST NOT change canonical ordering
* MUST reference tracks already present in `/playlist.m3u8`

---

## 6. Audio

* Codec: **FLAC only**
* Per-track FLAC files only
* All audio files MUST be referenced in `/playlist.m3u8`
* Manifest track entries MUST correspond to playlist entries

No other audio codecs are allowed in v1.

---

## 7. Lyrics

### 7.1 Format

* **MUST support:** WebVTT
* No other lyric formats supported in v1

### 7.2 Mapping

Lyrics MUST be defined in `/manifest.json`.

Playlist files MUST NOT contain lyric metadata.

### 7.3 Timing

* WebVTT timestamps are relative to track start (`t=0`)
* Millisecond precision allowed

### 7.4 Multiple Languages

Lyrics are defined as an array per track:

```json
"lyrics": [
  { "path": "lyrics/01.en.vtt", "format": "webvtt", "language": "en" }
]
```

Rules:

* `format` MUST be `"webvtt"`
* `language` MUST be a valid BCP 47 tag
* Players MAY offer language selection
* If multiple exist, players SHOULD select based on user/system language

---

## 8. Images

### 8.1 Supported Formats

* **MUST support:** JPEG (baseline)
* **MUST support:** PNG
* SVG not supported in v1

### 8.2 Recommendations

* Cover art SHOULD be square (1:1)
* Recommended cover size: 3000–4096 px per side
* DPI metadata MUST be ignored
* Gallery images MAY vary in aspect ratio and resolution

### 8.3 Rendering Requirements (Level 2)

* Players MUST render images inside a stable viewport
* Default scaling mode SHOULD be `contain`
* Players SHOULD avoid holding multiple full-resolution images in memory simultaneously

---

## 9. Manifest

### 9.1 Presence

* MUST NOT be required for Level 0
* SHOULD be included
* MUST be supported for Level 2

### 9.2 Encoding

* UTF-8 JSON
* Unknown fields MUST be ignored

### 9.3 Required Fields

```json
{
  "oap_version": "1.0",
  "tracks": [...]
}
```

### 9.4 Album Metadata (Minimal v1)

```json
"album": {
  "title": "Example Album",
  "album_artist": "Example Artist",
  "release_date": "2026-02-01",
  "languages": ["en"]
}
```

Rules:

* `release_date` is ISO 8601 date (`YYYY-MM-DD`)
* `created_utc` (optional) is ISO 8601 UTC timestamp
* `languages` is an array of BCP 47 language tags
* All metadata fields except `oap_version` and `tracks` are OPTIONAL

---

## 10. Checksums

### 10.1 Presence

* OPTIONAL for Level 0 and Level 1
* **MUST for Level 2**

### 10.2 Location

```
/checksums.json
```

### 10.3 Format

* UTF-8 JSON
* Hash algorithm: SHA-256 only
* MUST list every file in the archive except `/checksums.json`

Example:

```json
{
  "hash": "sha256",
  "files": {
    "playlist.m3u8": "4f3c...",
    "manifest.json": "9ab1...",
    "audio/01.flac": "a91e..."
  }
}
```

### 10.4 Strict Coverage Rule

Let:

* `archive_files` = set of all file entries in the ZIP (excluding directory entries)
* `checksum_keys` = `keys(checksums.files)`

Then Level 2 implementations MUST enforce:

```
checksum_keys == archive_files - { "checksums.json" }
```

Path comparison is case-sensitive.

### 10.5 Validation Requirements (Level 2)

Level 2 implementations MUST:

1. Confirm `/checksums.json` exists
2. Confirm strict coverage rule
3. Compute SHA-256 for each listed file
4. Reject the package if any mismatch occurs

Verification MAY occur before or during file use.

---

## 11. Forward Compatibility

* `oap_version` is required
* Unknown manifest fields MUST be ignored
* Future versions MAY introduce additional codecs and formats
* v1 players MUST ignore unsupported fields gracefully

---

## 12. Design Principles

OAP v1 prioritizes:

* Determinism
* Simplicity
* Hackability
* Progressive enhancement
* Open standards
* Cross-platform implementation

---
This spec has been created with the help of ChatGPT under instruction of the author.
