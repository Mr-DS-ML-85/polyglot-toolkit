"""
Hex editor engine with polyglot red-mark highlighting.

Features:
  - Hex dump with ASCII sidebar
  - Red-mark highlighting on extra/overlay data (polyglot markers)
  - Format-aware highlighting (known format headers in green, anomalies in red)
  - Byte offset navigation
  - Search in hex/ASCII
  - Diff view between two files
  - Entropy visualization per block

Author: Mr-DS-ML-85
"""

import os
import re
import math
import struct
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class HexRegion:
    name: str
    start: int
    end: int
    color: str  # "green" (valid), "red" (polyglot/extra), "yellow" (anomaly), "cyan" (metadata)
    description: str


class HexEditor:
    """Hex viewer with polyglot-aware red-mark highlighting."""

    # Format markers — minimum 4 bytes to avoid false positives on random binary data
    # Short sigs like BM(2), \x00\x00\x00(3), ID3(3), MZ(2) removed — too many false positives
    FORMAT_MARKERS = {
        b"\xff\xd8\xff": {"name": "JPEG", "end_markers": [b"\xff\xd9"], "color": "green"},
        b"\x89PNG\r\n\x1a\n": {"name": "PNG", "end_markers": [b"IEND"], "color": "green"},
        b"GIF87a": {"name": "GIF87a", "end_markers": [b"\x3b"], "color": "green"},
        b"GIF89a": {"name": "GIF89a", "end_markers": [b"\x3b"], "color": "green"},
        b"RIFF": {"name": "RIFF/WEBP/AVI/WAV", "end_markers": [], "color": "green"},
        b"\x00\x00\x01\x00": {"name": "ICO", "end_markers": [], "color": "green"},
        b"II\x2a\x00": {"name": "TIFF_LE", "end_markers": [], "color": "green"},
        b"MM\x00\x2a": {"name": "TIFF_BE", "end_markers": [], "color": "green"},
        b"\x1a\x45\xdf\xa3": {"name": "MKV/WebM/EBML", "end_markers": [], "color": "green"},
        b"ftyp": {"name": "MP4/MOV (ftyp)", "end_markers": [], "color": "green"},
        b"fLaC": {"name": "FLAC", "end_markers": [], "color": "green"},
        b"OggS": {"name": "OGG", "end_markers": [], "color": "green"},
        b"%PDF": {"name": "PDF", "end_markers": [b"%%EOF"], "color": "green"},
        b"PK\x03\x04": {"name": "ZIP/DOCX/XLSX/JAR", "end_markers": [b"PK\x05\x06"], "color": "green"},
        b"Rar!\x1a\x07": {"name": "RAR", "end_markers": [], "color": "green"},
        b"7z\xbc\xaf\x27\x1c": {"name": "7Z", "end_markers": [], "color": "green"},
        b"\x7fELF": {"name": "ELF", "end_markers": [], "color": "cyan"},
        b"\xca\xfe\xba\xbe": {"name": "Mach-O/Fat", "end_markers": [], "color": "cyan"},
        b"<?xml": {"name": "XML", "end_markers": [], "color": "cyan"},
        b"<html": {"name": "HTML", "end_markers": [], "color": "cyan"},
    }

    def hex_dump(self, filepath: str, offset: int = 0,
                 length: int = None, bytes_per_line: int = 16) -> Dict[str, Any]:
        """Generate hex dump with polyglot markers."""
        with open(filepath, "rb") as f:
            if offset > 0:
                f.seek(offset)
            data = f.read(length) if length else f.read()

        file_size = os.path.getsize(filepath)

        # Detect format regions
        regions = self._detect_regions(data, offset)
        extra_start = self._find_extra_data(data)

        # Generate hex lines
        lines = []
        for i in range(0, len(data), bytes_per_line):
            chunk = data[i:i + bytes_per_line]
            hex_parts = []
            ascii_parts = []
            annotations = []

            for j, byte in enumerate(chunk):
                pos = offset + i + j
                # Determine color based on region
                color = "white"
                for region in regions:
                    if region.start <= pos < region.end:
                        color = region.color
                        break

                # Red-mark for extra/overlay data
                if extra_start >= 0 and pos >= offset + extra_start:
                    color = "red"
                    if pos == offset + extra_start:
                        annotations.append(f"OVERLAY START (polyglot marker)")

                hex_val = f"{byte:02x}"
                ascii_val = chr(byte) if 32 <= byte < 127 else "."
                hex_parts.append((hex_val, color))
                ascii_parts.append((ascii_val, color))

            lines.append({
                "offset": offset + i,
                "hex": hex_parts,
                "ascii": ascii_parts,
                "annotations": annotations,
            })

        return {
            "filepath": filepath,
            "file_size": file_size,
            "offset": offset,
            "length": len(data),
            "lines": lines,
            "regions": [r.__dict__ for r in regions],
            "extra_data_offset": extra_start if extra_start >= 0 else None,
        }

    def _detect_regions(self, data: bytes, base_offset: int = 0) -> List[HexRegion]:
        """Detect known format regions in data."""
        regions = []

        for magic, info in self.FORMAT_MARKERS.items():
            pos = data.find(magic)
            if pos >= 0:
                # Find end marker
                end_pos = len(data)
                for end_marker in info["end_markers"]:
                    end = data.find(end_marker, pos)
                    if end >= 0:
                        end_pos = min(end_pos, end + len(end_marker))

                regions.append(HexRegion(
                    name=info["name"],
                    start=base_offset + pos,
                    end=base_offset + end_pos,
                    color=info["color"],
                    description=f"{info['name']} data at offset 0x{pos:x}",
                ))

        # Detect trailing data (polyglot indicator)
        primary_end = self._find_primary_end(data)
        if primary_end >= 0 and primary_end < len(data) - 16:
            regions.append(HexRegion(
                name="EXTRA DATA (POLYGLOT)",
                start=base_offset + primary_end,
                end=base_offset + len(data),
                color="red",
                description=f"Extra data after primary format end (0x{primary_end:x} - 0x{len(data):x}), "
                           f"size: {len(data) - primary_end} bytes — LIKELY POLYGLOT",
            ))

        # Detect embedded signatures (not at offset 0)
        # Embedded format sigs — only scan for distinctive patterns (5+ bytes)
        # MZ removed: 2 bytes match random binary data
        embedded_formats = [
            (b"\x7fELF", "ELF (embedded)"),
            (b"PK\x03\x04", "ZIP (embedded)"),
            (b"%PDF-", "PDF (embedded)"),
            (b"#!/bin/", "Shell script (embedded)"),
            (b"#!/usr/bin/env", "Script (embedded)"),
            (b"<script", "JavaScript (embedded)"),
            (b"WScript", "VBScript (embedded)"),
            (b"powershell", "PowerShell (embedded)"),
        ]

        for sig, name in embedded_formats:
            positions = self._find_all(data, sig)
            for pos in positions:
                if pos > 0:  # Not at start (that's the primary format)
                    regions.append(HexRegion(
                        name=name,
                        start=base_offset + pos,
                        end=base_offset + pos + 256,  # Mark 256 bytes
                        color="red",
                        description=f"{name} found at offset 0x{pos:x} — EMBEDDED PAYLOAD",
                    ))

        return sorted(regions, key=lambda r: r.start)

    def _find_extra_data(self, data: bytes) -> int:
        """Find where extra data begins after primary format."""
        return self._find_primary_end(data)

    def _find_primary_end(self, data: bytes) -> int:
        """Find the end of the primary format."""
        # JPEG
        if data[:2] == b"\xff\xd8":
            end = data.rfind(b"\xff\xd9")
            if end >= 0:
                return end + 2
        # PNG
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            end = data.find(b"IEND")
            if end >= 0:
                # IEND chunk is 4 bytes length + 4 bytes type + 4 bytes CRC
                return end + 8
        # GIF
        if data[:6] in (b"GIF87a", b"GIF89a"):
            end = data.rfind(b"\x3b")
            if end >= 0:
                return end + 1
        # PDF
        if data[:4] == b"%PDF":
            end = data.rfind(b"%%EOF")
            if end >= 0:
                return end + 5
        # ZIP
        if data[:4] == b"PK\x03\x04":
            end = data.find(b"PK\x05\x06")
            if end >= 0:
                return end + 22  # End of central directory
        # BMP
        if data[:2] == b"BM":
            if len(data) >= 10:
                size = struct.unpack("<I", data[2:6])[0]
                return size
        return -1

    def _find_all(self, data: bytes, pattern: bytes) -> List[int]:
        """Find all occurrences of pattern in data."""
        positions = []
        start = 0
        while True:
            pos = data.find(pattern, start)
            if pos < 0:
                break
            positions.append(pos)
            start = pos + 1
        return positions

    def search_hex(self, filepath: str, pattern: str) -> List[Dict[str, Any]]:
        """Search for hex pattern in file."""
        # Parse hex pattern (e.g., "FF D8 FF" or "ffd8ff")
        pattern = pattern.replace(" ", "").replace("\\x", "")
        try:
            search_bytes = bytes.fromhex(pattern)
        except ValueError:
            return [{"error": f"Invalid hex pattern: {pattern}"}]

        results = []
        with open(filepath, "rb") as f:
            data = f.read()

        start = 0
        while True:
            pos = data.find(search_bytes, start)
            if pos < 0:
                break
            context = data[max(0, pos-8):pos+len(search_bytes)+8]
            results.append({
                "offset": pos,
                "hex_offset": f"0x{pos:08x}",
                "context_hex": context.hex(),
                "context_ascii": ''.join(chr(b) if 32 <= b < 127 else '.' for b in context),
            })
            start = pos + 1
            if len(results) >= 100:
                break

        return results

    def search_ascii(self, filepath: str, pattern: str) -> List[Dict[str, Any]]:
        """Search for ASCII string in file."""
        results = []
        with open(filepath, "rb") as f:
            data = f.read()

        pattern_bytes = pattern.encode("ascii", errors="replace")
        start = 0
        while True:
            pos = data.find(pattern_bytes, start)
            if pos < 0:
                break
            context = data[max(0, pos-16):pos+len(pattern_bytes)+16]
            results.append({
                "offset": pos,
                "hex_offset": f"0x{pos:08x}",
                "context": ''.join(chr(b) if 32 <= b < 127 else '.' for b in context),
            })
            start = pos + 1
            if len(results) >= 100:
                break

        return results

    def entropy_map(self, filepath: str, block_size: int = 256) -> List[Dict[str, Any]]:
        """Generate entropy visualization map."""
        blocks = []
        with open(filepath, "rb") as f:
            offset = 0
            while True:
                data = f.read(block_size)
                if not data:
                    break
                entropy = self._calc_entropy(data)
                blocks.append({
                    "offset": offset,
                    "entropy": round(entropy, 2),
                    "bar": int(entropy * 10),  # 0-80 scale for display
                    "color": "red" if entropy > 7.0 else "yellow" if entropy > 5.5 else "green",
                })
                offset += block_size

        return blocks

    def _calc_entropy(self, data: bytes) -> float:
        """Shannon entropy of a byte block."""
        if not data:
            return 0.0
        freq = [0] * 256
        for byte in data:
            freq[byte] += 1
        entropy = 0.0
        length = len(data)
        for count in freq:
            if count > 0:
                p = count / length
                entropy -= p * math.log2(p)
        return entropy

    def diff_view(self, file1: str, file2: str, bytes_per_line: int = 16) -> Dict[str, Any]:
        """Compare two files byte-by-byte."""
        with open(file1, "rb") as f:
            data1 = f.read()
        with open(file2, "rb") as f:
            data2 = f.read()

        max_len = max(len(data1), len(data2))
        differences = []

        for i in range(0, max_len, bytes_per_line):
            chunk1 = data1[i:i + bytes_per_line]
            chunk2 = data2[i:i + bytes_per_line]

            if chunk1 != chunk2:
                differences.append({
                    "offset": i,
                    "file1_hex": chunk1.hex(),
                    "file2_hex": chunk2.hex(),
                    "diff_count": sum(1 for a, b in zip(chunk1, chunk2) if a != b),
                })

        return {
            "file1": file1,
            "file2": file2,
            "file1_size": len(data1),
            "file2_size": len(data2),
            "total_diffs": len(differences),
            "differences": differences[:200],
        }

    def format_string(self, data: bytes, fmt: str = "hex") -> str:
        """Format bytes as hex/ascii/binary string."""
        if fmt == "hex":
            return " ".join(f"{b:02x}" for b in data)
        elif fmt == "ascii":
            return ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
        elif fmt == "binary":
            return " ".join(f"{b:08b}" for b in data)
        elif fmt == "c_array":
            return ", ".join(f"0x{b:02x}" for b in data)
        elif fmt == "python":
            return repr(data)
        return data.hex()
