# Open Album Package (OAP)

Open Album Package (OAP) is an open, deterministic, hackable album container format.

OAP v1.0 defines:

* ZIP container (STORE-only)
* Canonical `playlist.m3u8`
* FLAC audio only
* WebVTT synced lyrics only
* JPEG / PNG artwork only
* Progressive enhancement via L0 / L1 / L2
* Strict SHA-256 integrity model (Level 2)

No DRM.
No signatures.
No remote media.
No compression beyond STORE.

---

## Repository Structure

```text
.
├── spec.md                    # OAP v1.0 specification
├── packaging.md               # Packager build algorithm
└── tools/
    └── oap-packager/          # Reference Python packager (uv-based)
```

---

## What OAP Is

OAP is designed for:

* Archival-grade album packaging
* Deterministic, verifiable distribution
* Progressive enhancement
* Cross-platform playback
* Long-term compatibility

It separates:

* **Playback order** → `playlist.m3u8`
* **Metadata & rich features** → `manifest.json`
* **Integrity** → `checksums.json`

---

## Conformance Levels

### Level 0 — Extract + Play

* Extract archive
* Open `playlist.m3u8`
* Play FLAC files

No manifest or checksum support required.

---

### Level 1 — Archive-Aware Audio

* Read `playlist.m3u8` inside ZIP
* Stream FLAC directly from archive (STORE)
* No extraction required

---

### Level 2 — Full Experience

* Parse `manifest.json`
* Render artwork
* Display WebVTT lyrics
* Enforce strict checksum validation

---

## Core Design Constraints (v1)

* ZIP entries MUST use STORE (no compression)
* `/playlist.m3u8` is required
* Playback order is defined exclusively by playlist
* Manifest MUST NOT redefine ordering
* `/checksums.json` MUST satisfy strict set equality rule:

```
keys(checksums.files) == archive_files - { "checksums.json" }
```

* SHA-256 only
* No digital signatures

---

## Minimal Package Example

```text
example.oap
├── playlist.m3u8
├── manifest.json
├── checksums.json
├── audio/
│   ├── 01.flac
│   └── 02.flac
├── images/
│   └── cover.jpg
└── lyrics/
    ├── 01.en.vtt
    └── 02.en.vtt
```

Optional:

```text
segment01.m3u8
segment02.m3u8
```

---

## Specification

The full specification is in:

```
spec.md
```

This document defines:

* Container rules
* File structure
* Playlist semantics
* Manifest schema
* Integrity requirements
* Conformance levels

---

## Packaging

The packaging algorithm is defined in:

```
packaging.md
```

It specifies:

* Input validation rules
* Deterministic path generation
* Playlist generation
* Manifest generation
* Strict checksum generation
* STORE-only ZIP enforcement
* Final conformance checks

---

## Reference Tool

A reference packager implementation is provided in:

```
tools/oap-packager/
```

It:

* Enforces all OAP v1 rules
* Generates manifest + checksums
* Validates strict coverage
* Uses Python + uv
* Has no third-party dependencies

See the tool’s README for usage instructions.

---

## Philosophy

OAP v1 prioritizes:

* Simplicity over feature creep
* Determinism over convenience
* Hackability over authority
* Open standards over proprietary formats
* Progressive enhancement over monolithic design

Everything in v1 is intentionally constrained to avoid ambiguity and long-term fragmentation.

---

## Future Directions (Not in v1)

Potential v2+ explorations:

* Additional image formats (AVIF/WebP)
* Additional audio codecs
* Optional compression reconsideration
* Video support
* Deterministic reproducible builds profile
* Optional signature layer

---

## Status

OAP v1.0 is stable and internally consistent.

Changes that would break v1 compatibility require a new `oap_version`.

---

If you are implementing a player, start with:

* Level 0 for minimal support
* Level 1 for archive playback
* Level 2 for full experience + integrity enforcement
