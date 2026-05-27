"""
Archive recursion scanning + container nesting analysis.

Detects:
  - Nested archives (zip-in-zip, gz-in-zip, etc.)
  - Archive bombs (deeply nested compression)
  - Container-in-container polyglots
  - Decompression bomb detection
  - Path traversal attacks
  - Encrypted archive detection
  - Archive format anomalies
  - Maximum nesting depth enforcement

Author: Mr-DS-ML-85
"""

import struct
import os
import zipfile
import io
import gzip
import logging
import hashlib
import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("polyglot_shield.archive")


@dataclass
class ArchiveFinding:
    severity: str
    category: str
    description: str
    details: Dict[str, Any] = field(default_factory=dict)


class ArchiveScanner:
    """Archive recursion scanner with container nesting analysis."""

    MAX_DEPTH = 5
    MAX_UNCOMPRESSED_SIZE = 100 * 1024 * 1024  # 100MB
    MAX_ENTRIES = 10000
    BOMB_RATIO_THRESHOLD = 100  # compressed:uncompressed ratio

    # Magic bytes for archive formats
    ARCHIVE_MAGICS = {
        b"PK\x03\x04": "zip",
        b"Rar!\x1a\x07": "rar",
        b"Rar!\x1a\x07\x01": "rar5",
        b"7z\xbc\xaf\x27\x1c": "7z",
        b"\x1f\x8b": "gz",
        b"BZ": "bz2",
        b"\xfd7zXZ": "xz",
        b"\x04\x22\x4d\x18": "lz4",
        b"\x28\xb5\x2f\xfd": "zstd",
        b"MSCF": "cab",
        b"-lh": "lzh",
        b"\x1f\x9d": "z_compress",
        b"\x1f\xa0": "z_compress",
        b"\x5d\x00\x00": "lzma",
    }

    def scan(self, filepath: str) -> List[ArchiveFinding]:
        """Full archive analysis with recursion scanning."""
        findings = []

        with open(filepath, "rb") as f:
            data = f.read()

        findings.extend(self._identify_archive(data, filepath))
        findings.extend(self._scan_recursion(filepath, data, depth=0))
        findings.extend(self._check_bomb(data, filepath))
        findings.extend(self._check_path_traversal(filepath, data))
        findings.extend(self._check_nesting(filepath, data))

        return findings

    def _identify_archive(self, data: bytes, filepath: str) -> List[ArchiveFinding]:
        """Identify archive format and basic properties."""
        findings = []
        ext = os.path.splitext(filepath)[1].lower()

        detected_format = None
        for magic, fmt in self.ARCHIVE_MAGICS.items():
            if data[:len(magic)] == magic:
                detected_format = fmt
                break

        # Special cases
        if not detected_format and data[:4] == b"PK\x03\x04":
            detected_format = "zip"
        elif not detected_format:
            # Check for TAR at offset 257
            if len(data) > 263 and data[257:262] == b"ustar":
                detected_format = "tar"

        if detected_format:
            archive_exts = {".zip", ".jar", ".war", ".ear", ".apk", ".ipa", ".zipx",
                           ".rar", ".7z", ".gz", ".tgz", ".bz2", ".tbz2",
                           ".xz", ".txz", ".tar", ".cab", ".lzh", ".lz4", ".zst"}
            if ext not in archive_exts and detected_format != ext:
                findings.append(ArchiveFinding(
                    "high", "format",
                    f"Archive format ({detected_format}) in non-archive extension ({ext})",
                    {"format": detected_format, "extension": ext}))

        return findings

    def _scan_recursion(self, filepath: str, data: bytes, depth: int) -> List[ArchiveFinding]:
        """Recursively scan archives for nested content."""
        findings = []

        if depth > self.MAX_DEPTH:
            findings.append(ArchiveFinding(
                "critical", "recursion",
                f"Archive nesting depth exceeded {self.MAX_DEPTH} — possible archive bomb",
                {"depth": depth, "path": filepath}))
            return findings

        ext = os.path.splitext(filepath)[1].lower()

        # Try to open as ZIP
        if data[:4] == b"PK\x03\x04" or ext in (".zip", ".jar", ".war", ".ear", ".apk", ".ipa"):
            findings.extend(self._scan_zip(data, depth))

        # Try GZIP
        elif data[:2] == b"\x1f\x8b" or ext in (".gz", ".tgz"):
            findings.extend(self._scan_gzip(data, depth))

        return findings

    def _scan_zip(self, data: bytes, depth: int) -> List[ArchiveFinding]:
        """Scan ZIP archive for nested content."""
        findings = []
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                entries = zf.namelist()

                if len(entries) > self.MAX_ENTRIES:
                    findings.append(ArchiveFinding(
                        "critical", "bomb",
                        f"ZIP has {len(entries):,} entries — possible zip bomb",
                        {"entries": len(entries), "depth": depth}))

                total_uncompressed = 0
                nested_archives = []

                for entry in entries:
                    info = zf.getinfo(entry)
                    total_uncompressed += info.file_size

                    # Check compression ratio
                    if info.compress_size > 0 and info.file_size > 0:
                        ratio = info.file_size / info.compress_size
                        if ratio > self.BOMB_RATIO_THRESHOLD:
                            findings.append(ArchiveFinding(
                                "critical", "bomb",
                                f"Extreme compression ratio ({ratio:.0f}x): {entry}",
                                {"entry": entry, "compressed": info.compress_size,
                                 "uncompressed": info.file_size, "depth": depth}))

                    # Check for nested archives
                    entry_ext = os.path.splitext(entry)[1].lower()
                    nested_exts = {".zip", ".jar", ".gz", ".bz2", ".7z", ".rar", ".xz", ".tar", ".tgz"}
                    if entry_ext in nested_exts or entry.endswith((".zip", ".jar", ".gz")):
                        nested_archives.append(entry)

                    # Check for path traversal
                    if ".." in entry or entry.startswith("/"):
                        findings.append(ArchiveFinding(
                            "critical", "traversal",
                            f"Path traversal in ZIP: {entry}",
                            {"entry": entry, "depth": depth}))

                    # Check for encrypted entries
                    if info.flag_bits & 1:
                        findings.append(ArchiveFinding(
                            "medium", "encrypted",
                            f"Encrypted ZIP entry: {entry}",
                            {"entry": entry, "depth": depth}))

                # Overall compression ratio
                total_compressed = sum(zf.getinfo(n).compress_size for n in entries)
                if total_compressed > 0:
                    overall_ratio = total_uncompressed / total_compressed
                    if overall_ratio > self.BOMB_RATIO_THRESHOLD:
                        findings.append(ArchiveFinding(
                            "critical", "bomb",
                            f"Overall ZIP bomb ratio: {overall_ratio:.0f}x "
                            f"({total_compressed:,} -> {total_uncompressed:,})",
                            {"ratio": overall_ratio, "depth": depth}))

                # Recurse into nested archives
                for nested in nested_archives[:10]:  # Limit recursion
                    try:
                        nested_data = zf.read(nested)
                        if len(nested_data) > 0:
                            findings.append(ArchiveFinding(
                                "high", "nesting",
                                f"Nested archive: {nested} ({len(nested_data):,} bytes)",
                                {"entry": nested, "depth": depth}))
                            # Recurse
                            findings.extend(
                                self._scan_recursion(nested, nested_data, depth + 1))
                    except Exception:
                        pass

        except zipfile.BadZipFile:
            findings.append(ArchiveFinding("medium", "format", "Invalid ZIP structure"))
        except Exception as e:
            findings.append(ArchiveFinding("low", "error", f"ZIP scan error: {e}"))

        return findings

    def _scan_gzip(self, data: bytes, depth: int) -> List[ArchiveFinding]:
        """Scan GZIP archive."""
        findings = []
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as gf:
                decompressed = gf.read(self.MAX_UNCOMPRESSED_SIZE + 1)

                if len(decompressed) > self.MAX_UNCOMPRESSED_SIZE:
                    findings.append(ArchiveFinding(
                        "critical", "bomb",
                        f"GZIP decompresses to {len(decompressed):,}+ bytes (exceeds limit)",
                        {"depth": depth}))

                ratio = len(decompressed) / max(len(data), 1)
                if ratio > self.BOMB_RATIO_THRESHOLD:
                    findings.append(ArchiveFinding(
                        "critical", "bomb",
                        f"GZIP bomb ratio: {ratio:.0f}x ({len(data):,} -> {len(decompressed):,})",
                        {"ratio": ratio, "depth": depth}))

                # Check if decompressed content is another archive
                if len(decompressed) > 4:
                    findings.extend(
                        self._scan_recursion("decompressed.gz", decompressed, depth + 1))

        except Exception:
            pass

        return findings

    def _check_bomb(self, data: bytes, filepath: str) -> List[ArchiveFinding]:
        """Check for archive bomb characteristics."""
        findings = []
        ext = os.path.splitext(filepath)[1].lower()

        # Check for multiple layers of compression markers
        compression_markers = [
            (b"PK\x03\x04", "zip"),
            (b"\x1f\x8b", "gzip"),
            (b"BZ", "bzip2"),
            (b"\xfd7zXZ", "xz"),
        ]

        layers_found = []
        for marker, name in compression_markers:
            count = data.count(marker)
            if count > 1:
                layers_found.append((name, count))

        if len(layers_found) > 1:
            findings.append(ArchiveFinding(
                "high", "bomb",
                f"Multiple compression format signatures: {layers_found}",
                {"layers": layers_found}))

        return findings

    def _check_path_traversal(self, filepath: str, data: bytes) -> List[ArchiveFinding]:
        """Check for path traversal attacks in archives."""
        findings = []

        if data[:4] != b"PK\x03\x04":
            return findings

        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for entry in zf.namelist():
                    if ".." in entry:
                        findings.append(ArchiveFinding(
                            "critical", "traversal",
                            f"Path traversal: {entry}",
                            {"entry": entry}))
                    if entry.startswith("/") or (len(entry) > 1 and entry[1] == ":"):
                        findings.append(ArchiveFinding(
                            "high", "traversal",
                            f"Absolute path in ZIP: {entry}",
                            {"entry": entry}))
        except Exception:
            pass

        return findings

    def _check_nesting(self, filepath: str, data: bytes) -> List[ArchiveFinding]:
        """Analyze container nesting structure."""
        findings = []

        # Check for format nesting (non-archive formats containing archives)
        format_sigs = {
            b"%PDF": "PDF",
            b"\xff\xd8\xff": "JPEG",
            b"\x89PNG": "PNG",
            b"GIF8": "GIF",
            b"MZ": "PE",
            b"\x7fELF": "ELF",
        }

        for sig, name in format_sigs.items():
            if data[:len(sig)] == sig:
                # This is not an archive — check if it contains archive markers
                for marker, archive_name in self.ARCHIVE_MAGICS.items():
                    if marker in data[64:]:
                        findings.append(ArchiveFinding(
                            "critical", "nesting",
                            f"{name} file contains {archive_name} archive signature — container nesting",
                            {"outer": name, "inner": archive_name}))
                break

        return findings
