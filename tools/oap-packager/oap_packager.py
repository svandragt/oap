#!/usr/bin/env python3
"""
OAP v1 packager (ZIP + STORE-only)

Creates:
- playlist.m3u8 (required)
- manifest.json (optional but recommended; we generate it)
- segmentNN.m3u8 (optional if you provide segments)
- checksums.json (generated; required for Level 2)

Notes:
- Audio: FLAC only
- Lyrics: WebVTT only (optional)
- Images: JPEG/PNG only (optional)
- ZIP entries: STORE only (no compression)
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path
from typing import Iterable, Optional


# ---------------------------
# Magic / validation helpers
# ---------------------------

def _read_prefix(p: Path, n: int = 16) -> bytes:
    with p.open("rb") as f:
        return f.read(n)


def is_flac(p: Path) -> bool:
    return _read_prefix(p, 4) == b"fLaC"


def is_webvtt(p: Path) -> bool:
    # WebVTT signature must appear at start (allow UTF-8 BOM).
    data = _read_prefix(p, 64)
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.startswith(b"WEBVTT")


def image_kind(p: Path) -> Optional[str]:
    data = _read_prefix(p, 16)
    # PNG signature
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    # JPEG SOI marker
    if data.startswith(b"\xff\xd8"):
        return "jpeg"
    return None


def bcp47_tag_ok(tag: str) -> bool:
    # Pragmatic check (not a full validator): alphanum segments separated by '-'
    # Examples: en, en-GB, zh-Hans, ja-Latn, pt-BR
    return bool(re.fullmatch(r"[A-Za-z]{2,3}([\-][A-Za-z0-9]{2,8})*", tag))


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------
# OAP internal path helpers
# ---------------------------

def zpath(*parts: str) -> str:
    # ZIP uses forward slashes
    return "/".join(part.strip("/").replace("\\", "/") for part in parts if part is not None)


def pad2(n: int) -> str:
    return f"{n:02d}"


def sanitize_title(s: str) -> str:
    return " ".join(s.strip().split())


# ---------------------------
# Models
# ---------------------------

@dataclasses.dataclass
class TrackInput:
    audio_path: Path
    title: str
    lyrics: list[tuple[str, Path]]  # (language_tag, file_path)


@dataclasses.dataclass
class SegmentDef:
    number: int
    label: str
    tracks: list[int]  # 1-based track numbers


# ---------------------------
# Parsing inputs
# ---------------------------

def parse_segments_arg(s: str, track_count: int) -> list[SegmentDef]:
    """
    Format:
      "1:Side A:1-5;2:Side B:6-10"
      "1:Disc 1:1-8;2:Disc 2:9-16"
    tracks can be comma list and/or ranges: 1-3,7,9-10
    """
    segments: list[SegmentDef] = []
    for seg in s.split(";"):
        seg = seg.strip()
        if not seg:
            continue
        try:
            num_str, label, tracks_expr = seg.split(":", 2)
        except ValueError:
            raise ValueError(f"Invalid segment spec '{seg}'. Expected 'N:Label:tracks'.")
        number = int(num_str)
        label = sanitize_title(label)
        tracks = expand_track_expr(tracks_expr, track_count)
        segments.append(SegmentDef(number=number, label=label, tracks=tracks))
    # Basic checks
    if any(not (1 <= seg.number <= 99) for seg in segments):
        raise ValueError("Segment numbers must be 1..99.")
    if len({seg.number for seg in segments}) != len(segments):
        raise ValueError("Duplicate segment numbers.")
    return sorted(segments, key=lambda x: x.number)


def expand_track_expr(expr: str, track_count: int) -> list[int]:
    out: list[int] = []
    parts = [p.strip() for p in expr.split(",") if p.strip()]
    for p in parts:
        if "-" in p:
            a, b = p.split("-", 1)
            start = int(a)
            end = int(b)
            if start > end:
                start, end = end, start
            out.extend(range(start, end + 1))
        else:
            out.append(int(p))
    # de-dup, preserve order
    seen = set()
    res: list[int] = []
    for t in out:
        if t < 1 or t > track_count:
            raise ValueError(f"Track number {t} out of range (1..{track_count}).")
        if t not in seen:
            seen.add(t)
            res.append(t)
    return res


def parse_lyrics_dir(lyrics_dir: Path, track_count: int) -> dict[int, list[tuple[str, Path]]]:
    """
    Accept filenames like:
      01.en.vtt
      01.vtt  (language 'und')
    Returns mapping track_no -> [(lang, path), ...]
    """
    mapping: dict[int, list[tuple[str, Path]]] = {i: [] for i in range(1, track_count + 1)}
    if not lyrics_dir:
        return mapping
    if not lyrics_dir.exists():
        raise FileNotFoundError(f"Lyrics dir not found: {lyrics_dir}")

    for p in sorted(lyrics_dir.glob("*.vtt")):
        name = p.name
        m = re.fullmatch(r"(\d{2})\.([A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*)\.vtt", name)
        if m:
            track_no = int(m.group(1))
            lang = m.group(2)
        else:
            m2 = re.fullmatch(r"(\d{2})\.vtt", name)
            if not m2:
                raise ValueError(f"Unsupported lyrics filename: {name} (expected 01.vtt or 01.en.vtt)")
            track_no = int(m2.group(1))
            lang = "und"

        if track_no < 1 or track_no > track_count:
            raise ValueError(f"Lyrics file {name} track_no out of range 1..{track_count}")

        if lang != "und" and not bcp47_tag_ok(lang):
            raise ValueError(f"Lyrics language tag looks invalid: {lang} in {name}")

        if not is_webvtt(p):
            raise ValueError(f"Not a valid WebVTT (missing WEBVTT header): {p}")

        mapping[track_no].append((lang, p))

    # stable order: put 'und' last
    for t in mapping:
        mapping[t].sort(key=lambda x: (x[0] == "und", x[0], x[1].name))
    return mapping


# ---------------------------
# Writing OAP
# ---------------------------

def write_text_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def build_playlist(tracks: list[TrackInput]) -> str:
    lines = ["#EXTM3U"]
    for i, tr in enumerate(tracks, start=1):
        # EXTINF optional; we include title only (duration unknown unless you add a FLAC parser)
        lines.append(f"#EXTINF:-1,{tr.title}")
        lines.append(zpath("audio", f"{pad2(i)}.flac"))
    return "\n".join(lines) + "\n"


def build_segment_playlist(tracks: list[TrackInput], seg: SegmentDef) -> str:
    lines = ["#EXTM3U"]
    for tno in seg.tracks:
        tr = tracks[tno - 1]
        lines.append(f"#EXTINF:-1,{tr.title}")
        lines.append(zpath("audio", f"{pad2(tno)}.flac"))
    return "\n".join(lines) + "\n"


def zip_add_file(zf: zipfile.ZipFile, src: Path, arc_path: str) -> None:
    # Enforce STORE-only
    info = zipfile.ZipInfo(arc_path)
    # Normalize timestamp (optional). Keep deterministic-ish but not required.
    info.date_time = (1980, 1, 1, 0, 0, 0)
    info.compress_type = zipfile.ZIP_STORED

    with src.open("rb") as f:
        data = f.read()
    zf.writestr(info, data)


def zip_add_bytes(zf: zipfile.ZipFile, arc_path: str, data: bytes) -> None:
    info = zipfile.ZipInfo(arc_path)
    info.date_time = (1980, 1, 1, 0, 0, 0)
    info.compress_type = zipfile.ZIP_STORED
    zf.writestr(info, data)


def list_zip_files(zf: zipfile.ZipFile) -> set[str]:
    files = set()
    for info in zf.infolist():
        if info.is_dir():
            continue
        files.add(info.filename)
    return files


def sha256_zip_entry(zf: zipfile.ZipFile, arc_path: str) -> str:
    h = hashlib.sha256()
    with zf.open(arc_path, "r") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Build an OAP v1 .oap package (ZIP STORE-only).")
    ap.add_argument("--out", required=True, type=Path, help="Output .oap path")
    ap.add_argument("--audio-dir", required=True, type=Path, help="Directory containing FLAC tracks")
    ap.add_argument("--lyrics-dir", type=Path, default=None, help="Directory containing .vtt lyrics (optional)")
    ap.add_argument("--cover", type=Path, default=None, help="Cover image (jpg/png) (optional)")
    ap.add_argument("--gallery-dir", type=Path, default=None, help="Gallery images dir (jpg/png) (optional)")
    ap.add_argument("--title", default=None, help="Album title (optional)")
    ap.add_argument("--album-artist", default=None, help="Album artist (optional)")
    ap.add_argument("--release-date", default=None, help="Release date YYYY-MM-DD (optional)")
    ap.add_argument("--languages", default=None, help="Comma-separated BCP47 tags (optional)")
    ap.add_argument("--segments", default=None, help="Segment spec: '1:Side A:1-5;2:Side B:6-10' (optional)")

    args = ap.parse_args(argv)

    audio_dir: Path = args.audio_dir
    if not audio_dir.exists():
        raise FileNotFoundError(f"audio-dir not found: {audio_dir}")

    # Gather audio files: prefer already numbered filenames, else sort lexicographically.
    audio_files = sorted([p for p in audio_dir.iterdir() if p.is_file()], key=lambda p: p.name)
    if not audio_files:
        raise ValueError("No audio files found in audio-dir.")

    # Validate all are FLAC
    for p in audio_files:
        if not is_flac(p):
            raise ValueError(f"Not FLAC (missing fLaC header): {p}")

    track_count = len(audio_files)

    # Titles: default from filename
    tracks: list[TrackInput] = []
    lyrics_map = parse_lyrics_dir(args.lyrics_dir, track_count) if args.lyrics_dir else {i: [] for i in range(1, track_count + 1)}

    for i, p in enumerate(audio_files, start=1):
        default_title = sanitize_title(p.stem)
        # Avoid empty titles
        title = default_title if default_title else f"Track {pad2(i)}"
        tracks.append(TrackInput(audio_path=p, title=title, lyrics=lyrics_map.get(i, [])))

    # Validate cover/gallery
    cover_info = None
    if args.cover:
        kind = image_kind(args.cover)
        if kind not in {"jpeg", "png"}:
            raise ValueError(f"Cover must be JPEG or PNG: {args.cover}")
        cover_info = {"path": None, "mime": "image/jpeg" if kind == "jpeg" else "image/png"}

    gallery_files: list[Path] = []
    if args.gallery_dir:
        if not args.gallery_dir.exists():
            raise FileNotFoundError(f"gallery-dir not found: {args.gallery_dir}")
        gallery_files = sorted([p for p in args.gallery_dir.iterdir() if p.is_file()], key=lambda p: p.name)
        for p in gallery_files:
            kind = image_kind(p)
            if kind not in {"jpeg", "png"}:
                raise ValueError(f"Gallery image must be JPEG or PNG: {p}")

    # Segments
    segments: list[SegmentDef] = []
    if args.segments:
        segments = parse_segments_arg(args.segments, track_count)

    # Minimal album metadata (all optional)
    album = {}
    if args.title:
        album["title"] = sanitize_title(args.title)
    if args.album_artist:
        album["album_artist"] = sanitize_title(args.album_artist)
    if args.release_date:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.release_date):
            raise ValueError("release-date must be YYYY-MM-DD")
        album["release_date"] = args.release_date
    if args.languages:
        langs = [x.strip() for x in args.languages.split(",") if x.strip()]
        for lang in langs:
            if not bcp47_tag_ok(lang):
                raise ValueError(f"Invalid language tag: {lang}")
        album["languages"] = langs

    created_utc = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    # Build playlist contents
    playlist_text = build_playlist(tracks)

    # Build segments playlist contents
    segment_texts: dict[str, str] = {}
    for seg in segments:
        seg_name = f"segment{pad2(seg.number)}.m3u8"
        segment_texts[seg_name] = build_segment_playlist(tracks, seg)

    # Build manifest
    manifest: dict = {
        "oap_version": "1.0",
        "created_utc": created_utc,
        "tracks": [],
    }
    if album:
        manifest["album"] = album

    # Images in manifest (optional)
    images_obj = {}
    if args.cover:
        kind = image_kind(args.cover)
        cover_path = "images/cover.jpg" if kind == "jpeg" else "images/cover.png"
        images_obj["cover"] = {"path": cover_path, "mime": "image/jpeg" if kind == "jpeg" else "image/png"}
    if gallery_files:
        gallery_entries = []
        for idx, p in enumerate(gallery_files, start=1):
            kind = image_kind(p)
            ext = "jpg" if kind == "jpeg" else "png"
            gallery_entries.append({"path": f"images/gallery/{idx:03d}.{ext}", "mime": "image/jpeg" if kind == "jpeg" else "image/png"})
        images_obj["gallery"] = gallery_entries
    if images_obj:
        manifest["images"] = images_obj

    # Segments in manifest (optional)
    if segments:
        manifest["segments"] = [
            {"number": seg.number, "playlist_path": f"segment{pad2(seg.number)}.m3u8", "label": seg.label}
            for seg in segments
        ]

    # Tracks in manifest
    for i, tr in enumerate(tracks, start=1):
        entry = {
            "audio": {"path": zpath("audio", f"{pad2(i)}.flac"), "codec": "flac"},
            "title": tr.title,
            "track_no": i,
        }
        if tr.lyrics:
            entry["lyrics"] = [
                {"path": zpath("lyrics", f"{pad2(i)}.{lang}.vtt") if lang != "und" else zpath("lyrics", f"{pad2(i)}.vtt"),
                 "format": "webvtt",
                 "language": lang}
                for (lang, _p) in tr.lyrics
            ]
        manifest["tracks"].append(entry)

    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    playlist_bytes = playlist_text.encode("utf-8")
    segment_bytes = {name: text.encode("utf-8") for name, text in segment_texts.items()}

    # Prepare output
    out_path: Path = args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    # Create zip (without checksums first)
    with zipfile.ZipFile(out_path, "w") as zf:
        # Required playlist
        zip_add_bytes(zf, "playlist.m3u8", playlist_bytes)

        # Optional segments
        for name in sorted(segment_bytes.keys()):
            zip_add_bytes(zf, name, segment_bytes[name])

        # Manifest (we generate it; Level 0 will ignore)
        zip_add_bytes(zf, "manifest.json", manifest_bytes)

        # Audio
        for i, p in enumerate(audio_files, start=1):
            zip_add_file(zf, p, zpath("audio", f"{pad2(i)}.flac"))

        # Lyrics
        if args.lyrics_dir:
            for i in range(1, track_count + 1):
                for (lang, p) in lyrics_map.get(i, []):
                    arc = zpath("lyrics", f"{pad2(i)}.{lang}.vtt") if lang != "und" else zpath("lyrics", f"{pad2(i)}.vtt")
                    zip_add_file(zf, p, arc)

        # Images
        if args.cover:
            kind = image_kind(args.cover)
            arc = "images/cover.jpg" if kind == "jpeg" else "images/cover.png"
            zip_add_file(zf, args.cover, arc)

        if gallery_files:
            for idx, p in enumerate(gallery_files, start=1):
                kind = image_kind(p)
                ext = "jpg" if kind == "jpeg" else "png"
                arc = f"images/gallery/{idx:03d}.{ext}"
                zip_add_file(zf, p, arc)

    # Compute checksums and add checksums.json (Level 2 requirement)
    with zipfile.ZipFile(out_path, "a") as zf:
        archive_files = list_zip_files(zf)
        if "checksums.json" in archive_files:
            raise RuntimeError("Internal error: checksums.json already present before generation")

        files_map = {}
        for arc in sorted(archive_files):
            files_map[arc] = sha256_zip_entry(zf, arc)

        checksums = {"hash": "sha256", "files": files_map}
        checksums_bytes = (json.dumps(checksums, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

        zip_add_bytes(zf, "checksums.json", checksums_bytes)

    # Strict coverage check (keys == archive_files - {checksums.json})
    with zipfile.ZipFile(out_path, "r") as zf:
        final_files = list_zip_files(zf)
        if "checksums.json" not in final_files:
            raise RuntimeError("Failed to write checksums.json")

        # Re-read and validate
        raw = zf.read("checksums.json")
        obj = json.loads(raw.decode("utf-8"))
        if obj.get("hash") != "sha256":
            raise RuntimeError("checksums.json hash field must be 'sha256'")
        checksum_keys = set(obj.get("files", {}).keys())
        expected = final_files - {"checksums.json"}
        if checksum_keys != expected:
            missing = sorted(expected - checksum_keys)
            extra = sorted(checksum_keys - expected)
            raise RuntimeError(
                "Strict coverage rule failed:\n"
                f"Missing from checksums.json: {missing}\n"
                f"Extra keys in checksums.json: {extra}\n"
            )

        # Verify hashes
        for arc, expected_hex in obj["files"].items():
            actual = sha256_zip_entry(zf, arc)
            if actual != expected_hex:
                raise RuntimeError(f"Checksum mismatch for {arc}: expected {expected_hex} got {actual}")

        # Verify STORE-only
        for info in zf.infolist():
            if info.is_dir():
                continue
            if info.compress_type != zipfile.ZIP_STORED:
                raise RuntimeError(f"Non-conformant compression for {info.filename}: {info.compress_type}")

    print(f"Wrote OAP v1 package: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
