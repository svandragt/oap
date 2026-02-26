## OAP v1 Packager Build Algorithm

This defines how to produce a **conformant `.oap`** (ZIP, STORE-only) from an input album.

### Inputs

* Track audio files (FLAC), in intended playback order
* Optional: per-track WebVTT lyric files
* Optional: cover image (JPEG/PNG) and gallery images (JPEG/PNG)
* Optional: segment groupings (e.g. Side A / Side B) expressed as track ranges or lists
* Optional: minimal album metadata (`title`, `album_artist`, `release_date`, `languages`)
* Output path: `name.oap`

---

## Step 0 — Validate source inputs

1. Confirm all audio inputs are FLAC.
2. Confirm artwork files are JPEG or PNG.
3. Confirm lyric files are WebVTT.
4. Ensure all filenames you will generate are UTF-8-safe (avoid control chars; prefer ASCII + Unicode letters).
5. Decide final track ordering (this will define the canonical playlist).

If any validation fails, abort.

---

## Step 1 — Choose deterministic internal paths

Normalize and assign internal paths (recommendations):

* Audio: `audio/01.flac`, `audio/02.flac`, …
* Lyrics: `lyrics/01.<lang>.vtt` (or `lyrics/01.vtt` if single language)
* Images:

  * Cover: `images/cover.jpg` or `images/cover.png`
  * Gallery: `images/gallery/001.jpg`, …

Rules:

* Use `/` separators.
* No spaces required, but allowed.
* No `..` segments.
* No absolute paths.

---

## Step 2 — Generate `/playlist.m3u8` (MUST)

Create a UTF-8 text file at archive root:

* First line: `#EXTM3U`
* For each track in order:

  * Optionally include `#EXTINF:<seconds>,<title>`
  * Then the relative path to the FLAC file

Example:

```text
#EXTM3U
#EXTINF:243,Track 01
audio/01.flac
#EXTINF:198,Track 02
audio/02.flac
```

Notes:

* `#EXTINF` is optional; if you include it, duration should be integer seconds (rounded).
* Playlist order is canonical.

---

## Step 3 — Generate optional segment playlists

If you support segment groupings:

For each segment `N` from `01` to `99`:

* Write `/segmentNN.m3u8` with the same M3U8 rules as above
* Include only the tracks in that segment, in the same relative paths and same order

Constraints:

* Every track referenced in any segment playlist MUST also appear in `/playlist.m3u8`.
* Segments MUST NOT introduce a different ordering than `/playlist.m3u8`.

---

## Step 4 — Generate `/manifest.json` (SHOULD)

Create a UTF-8 JSON manifest. Required fields:

* `"oap_version": "1.0"`
* `"tracks": [...]`

Recommended fields:

* `created_utc`: packaging timestamp (`YYYY-MM-DDTHH:MM:SSZ`)
* `album` minimal metadata (optional)
* `images.cover` with width/height (optional but recommended)
* per-track `lyrics` array (optional)
* optional `segments` list mapping segment number to playlist path and label

Guidance:

* Track identity key is `tracks[*].audio.path` and MUST match playlist paths.
* Do not encode playback order in the manifest; playlist is the source of truth.
* Use BCP 47 tags for all language fields.

---

## Step 5 — Assemble the staging file set

Construct a staging directory tree (or virtual set) containing exactly the files you plan to include, e.g.:

* `playlist.m3u8`
* `manifest.json` (if included)
* `segmentNN.m3u8` (if included)
* `audio/*.flac`
* `lyrics/*.vtt` (if included)
* `images/*` (if included)

At this point, you should be able to enumerate the complete set of archive files that will be included.

---

## Step 6 — Create the ZIP archive (STORE-only)

Create a ZIP file with:

* Compression method STORE for **every entry**
* Paths exactly as chosen
* UTF-8 filename encoding

Implementation details:

* Ensure your ZIP writer sets the “UTF-8 filenames” flag.
* Do not include OS-specific metadata files (e.g. `__MACOSX/`, `.DS_Store`, `Thumbs.db`).

If your ZIP tool cannot guarantee STORE-only entries, do not use it.

---

## Step 7 — Generate `/checksums.json` (MUST for Level 2 packages)

If you are producing a Level 2-capable package, you MUST include checksums.

Algorithm:

1. Enumerate `archive_files`: all file entries in the ZIP **excluding directory entries**.

2. Confirm `checksums.json` is not yet in the archive (it should be added last).

3. For each file in `archive_files`:

   * Read raw bytes of that file
   * Compute SHA-256
   * Store hex digest under the file path key

4. Create `/checksums.json` with:

```json
{
  "hash": "sha256",
  "files": {
    "<path>": "<hex sha256>",
    ...
  }
}
```

5. Add `/checksums.json` to the ZIP as STORE.

### Strict coverage validation (packager MUST ensure)

After adding `/checksums.json`, re-enumerate the final archive file set:

* `final_archive_files`

Verify:

* `keys(checksums.files) == final_archive_files - { "checksums.json" }`

If not equal, abort and rebuild.

Notes:

* Keys are case-sensitive.
* Use forward slashes.

---

## Step 8 — Final conformance checks (packager)

Before shipping:

* [ ] ZIP entries are all STORE (no compression)
* [ ] `/playlist.m3u8` exists and references only existing FLAC files
* [ ] No path contains `..` or is absolute
* [ ] Only FLAC is used for audio
* [ ] Only WebVTT is used for lyrics (if present)
* [ ] Only JPEG/PNG is used for images (if present)
* [ ] If `/manifest.json` is present, it is valid UTF-8 JSON and unknown fields are not required by readers
* [ ] If `/checksums.json` is present:

  * [ ] `hash == "sha256"`
  * [ ] strict coverage equality holds
  * [ ] all hashes verify

---

## Determinism recommendations (optional but useful)

If you want reproducible builds (same inputs → identical `.oap` bytes), standardize:

* File ordering inside ZIP (lexicographic by path)
* Fixed timestamps for ZIP entries (or all set to `created_utc`)
* Stable JSON formatting (sorted keys, consistent whitespace)

This is optional in v1, but helps testing and distribution.

---

## Suggested implementation approach (tooling)

If you build a packager script, its pipeline is:

1. normalize inputs → 2) generate playlist(s) + manifest → 3) zip STORE-only → 4) add checksums last → 5) re-verify strict coverage and hashes
