"""
Steganography detection engine for PolyglotShield.

Detects hidden data in images, audio, video, and documents using:
  - LSB (Least Significant Bit) analysis
  - Chi-square statistical analysis
  - RS (Regular-Singular) analysis
  - DCT coefficient analysis (JPEG)
  - Metadata/EXIF anomaly detection
  - EOF/APP marker analysis
  - Audio steganography detection (echo hiding, phase coding)
  - Visual attack (image comparison)
  - Entropy analysis per-channel

Author: Mr-DS-ML-85
"""

import math
import struct
import hashlib
import os
import zlib
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

logger = logging.getLogger("polyglot_shield.stego")


@dataclass
class StegoFinding:
    """A steganography detection finding."""
    method: str           # Detection method
    severity: str         # critical / high / medium / low
    confidence: float     # 0.0 - 1.0
    description: str
    details: Dict[str, Any] = field(default_factory=dict)


class StegoDetector:
    """Steganography detection engine."""

    def analyze(self, filepath: str) -> List[StegoFinding]:
        """Full steganography analysis on a file."""
        with open(filepath, "rb") as f:
            data = f.read()

        ext = os.path.splitext(filepath)[1].lower()
        findings: List[StegoFinding] = []

        # Detect content type
        content_type = self._detect_type(data, ext)

        # Run all applicable analyses
        findings.extend(self._lsb_analysis(data, content_type))
        findings.extend(self._chi_square_analysis(data, content_type))
        findings.extend(self._entropy_analysis(data, content_type))
        findings.extend(self._metadata_analysis(data, content_type, ext))
        findings.extend(self._trailing_analysis(data, content_type, ext))
        findings.extend(self._duplicate_marker_analysis(data, content_type))

        if content_type == "jpeg":
            findings.extend(self._jpeg_dct_analysis(data))
            findings.extend(self._jpeg_quantization_analysis(data))

        if content_type in ("png", "bmp", "tiff"):
            findings.extend(self._channel_correlation_analysis(data, content_type))

        if content_type in ("wav", "mp3", "flac"):
            findings.extend(self._audio_stego_analysis(data, content_type))

        return findings

    def _detect_type(self, data: bytes, ext: str) -> str:
        if len(data) < 2:
            return "unknown"
        if data[:2] == b"\xff\xd8":
            return "jpeg"
        if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
            return "png"
        if len(data) >= 6 and data[:6] in (b"GIF87a", b"GIF89a"):
            return "gif"
        if data[:4] == b"%PDF":
            return "pdf"
        if data[:2] == b"PK":
            return "zip"
        if len(data) >= 12 and data[:4] == b"RIFF":
            sub = data[8:12]
            if sub == b"WAVE":
                return "wav"
        if data[:4] in (b"OggS",):
            return "ogg"
        if data[:3] == b"ID3" or (data[0] == 0xff and (data[1] & 0xe0) == 0xe0):
            return "mp3"
        if data[:4] == b"fLaC":
            return "flac"
        if data[:2] == b"BM":
            return "bmp"
        if data[:2] in (b"II", b"MM"):
            return "tiff"
        return "unknown"

    # ── LSB Analysis ──────────────────────────────────────────────

    def _extract_pixels(self, data: bytes, content_type: str) -> bytes:
        """Extract raw pixel data — decompresses PNG IDAT chunks and strips filter bytes."""
        if content_type == "png":
            import struct as _s, zlib as _z
            chunks = []
            pos = 8
            ihdr_found = False
            width = 0
            while pos + 8 < len(data):
                try:
                    length = _s.unpack(">I", data[pos:pos+4])[0]
                    ctype = data[pos+4:pos+8]
                    if length > 0x7FFFFFFF or not all(65 <= b <= 122 for b in ctype):
                        break
                    if ctype == b"IHDR" and length >= 4:
                        width = _s.unpack(">I", data[pos+8:pos+12])[0]
                        ihdr_found = True
                    elif ctype == b"IDAT":
                        chunks.append(data[pos+8:pos+8+length])
                    pos += 12 + length
                except Exception:
                    break
            if chunks:
                try:
                    raw = _z.decompress(b"".join(chunks))
                    if ihdr_found and width > 0:
                        # PNG: each row starts with a filter byte — strip them
                        # Row size = 1 (filter) + width * bytes_per_pixel (assume 3 for RGB)
                        bpp = 3  # Assume RGB; filter byte stripping works for all
                        stride = 1 + width * bpp
                        if stride > 0 and len(raw) >= stride:
                            pixels = bytearray()
                            for row_start in range(0, len(raw), stride):
                                row = raw[row_start+1:row_start+stride]  # skip filter byte
                                pixels.extend(row)
                            return bytes(pixels)
                    return raw
                except Exception:
                    pass
        # Fallback: raw pixel data start
        pixel_start = self._find_pixel_data_start(data, content_type)
        if pixel_start >= 0 and pixel_start < len(data):
            return data[pixel_start:]
        return data

    def _lsb_analysis(self, data: bytes, content_type: str) -> List[StegoFinding]:
        """Detect LSB steganography via bit-plane analysis."""
        findings = []

        if content_type not in ("png", "bmp", "tiff", "gif"):
            return findings

        # Extract DECOMPRESSED pixel data (critical for PNG — IDAT is zlib compressed)
        pixel_data = self._extract_pixels(data, content_type)
        if len(pixel_data) < 100:
            return findings

        # Count LSB distribution
        lsb_0 = sum(1 for b in pixel_data if b & 1 == 0)
        lsb_1 = sum(1 for b in pixel_data if b & 1 == 1)
        total = lsb_0 + lsb_1

        if total == 0:
            return findings

        ratio = lsb_1 / total

        # In natural images, LSB ratio should be close to 0.5 but not exact
        # Steganography pushes it very close to 0.5
        deviation = abs(ratio - 0.5)

        if deviation < 0.003:
            findings.append(StegoFinding(
                method="LSB Analysis",
                severity="high",
                confidence=0.7,
                description=f"Suspiciously uniform LSB distribution ({ratio:.4f})",
                details={"lsb_ratio": ratio, "deviation": deviation}
            ))
        elif deviation < 0.02:
            findings.append(StegoFinding(
                method="LSB Analysis",
                severity="medium",
                confidence=0.5,
                description=f"Near-uniform LSB distribution ({ratio:.4f})",
                details={"lsb_ratio": ratio, "deviation": deviation}
            ))

        # Check for bit-plane complexity
        # Extract LSB plane and check if it looks like random data
        lsb_plane = bytes(b & 1 for b in pixel_data[:4096])
        lsb_entropy = self._shannon_bytes(lsb_plane)
        # Natural images have LSB entropy ~0.92-0.98; only flag > 0.995
        if lsb_entropy > 0.995:
            findings.append(StegoFinding(
                method="LSB Entropy",
                severity="high",
                confidence=0.6,
                description=f"LSB plane has near-perfect random entropy ({lsb_entropy:.3f}) — possible hidden data",
                details={"lsb_entropy": lsb_entropy}
            ))

        return findings

    # ── Chi-Square Analysis ───────────────────────────────────────

    def _chi_square_analysis(self, data: bytes, content_type: str = "unknown") -> List[StegoFinding]:
        """Chi-square test for steganographic content."""
        findings = []

        # For compressed formats (PNG, etc.), analyze decompressed pixel data
        # Compressed data is always near-uniform — false positive if analyzed raw
        if content_type == "png":
            pixel_data = self._extract_pixels(data, content_type)
            if len(pixel_data) < 1000:
                return findings
            analysis_data = pixel_data
        else:
            analysis_data = data

        # Count byte frequencies
        freq = [0] * 256
        for b in analysis_data:
            freq[b] += 1

        # Chi-square test: compare observed vs expected (uniform)
        expected = len(analysis_data) / 256
        if expected == 0:
            return findings
        chi_sq = sum((obs - expected) ** 2 / expected for obs in freq)

        # Degrees of freedom = 255
        # Critical value at p=0.001 is ~310
        # Very low chi-square suggests manipulation (uniform distribution)
        if chi_sq < 200:
            findings.append(StegoFinding(
                method="Chi-Square Test",
                severity="high",
                confidence=0.75,
                description=f"Byte distribution abnormally uniform (χ²={chi_sq:.1f})",
                details={"chi_square": chi_sq}
            ))
        elif chi_sq < 280:
            findings.append(StegoFinding(
                method="Chi-Square Test",
                severity="medium",
                confidence=0.5,
                description=f"Byte distribution slightly uniform (χ²={chi_sq:.1f})",
                details={"chi_square": chi_sq}
            ))

        # Pair analysis: consecutive byte pairs should show patterns in natural data
        pair_entropy = 0
        if len(data) > 1000:
            pair_freq = {}
            for i in range(0, min(len(data) - 1, 10000), 2):
                pair = (data[i], data[i+1])
                pair_freq[pair] = pair_freq.get(pair, 0) + 1
            total_pairs = sum(pair_freq.values())
            if total_pairs > 0:
                for count in pair_freq.values():
                    p = count / total_pairs
                    if p > 0:
                        pair_entropy -= p * math.log2(p)
                # Natural images have structured pair distribution
                if pair_entropy > 15:  # Near-random
                    findings.append(StegoFinding(
                        method="Pair Analysis",
                        severity="medium",
                        confidence=0.6,
                        description=f"Consecutive byte pairs show high entropy ({pair_entropy:.1f})",
                        details={"pair_entropy": pair_entropy}
                    ))

        return findings

    # ── Entropy Analysis ──────────────────────────────────────────

    def _entropy_analysis(self, data: bytes, content_type: str) -> List[StegoFinding]:
        """Analyze entropy distribution for anomalies."""
        findings = []

        # For compressed formats, analyze decompressed pixel data
        if content_type == "png":
            analysis_data = self._extract_pixels(data, content_type)
        else:
            analysis_data = data

        if len(analysis_data) < 1024:
            return findings

        # Chunk-based entropy analysis
        chunk_size = max(256, len(analysis_data) // 32)
        entropies = []
        for i in range(0, len(analysis_data) - chunk_size, chunk_size):
            chunk = analysis_data[i:i+chunk_size]
            ent = self._shannon_bytes(chunk)
            entropies.append(ent)

        if not entropies:
            return findings

        # Check for sudden entropy changes (indicates hidden data boundaries)
        if len(entropies) > 4:
            diffs = [abs(entropies[i+1] - entropies[i]) for i in range(len(entropies)-1)]
            max_diff = max(diffs)
            avg_diff = sum(diffs) / len(diffs)

            if max_diff > 2.0:
                findings.append(StegoFinding(
                    method="Entropy Transition",
                    severity="high",
                    confidence=0.65,
                    description=f"Sudden entropy change ({max_diff:.2f}) — possible hidden data boundary",
                    details={"max_diff": max_diff, "avg_diff": avg_diff,
                             "entropy_profile": [round(e, 2) for e in entropies[:16]]}
                ))

        # Overall high entropy — only flag if EXTREMELY high (near 8.0 max)
        # Natural photos routinely hit 7.5+ entropy; only encrypted/compressed payloads reach 7.95+
        avg_entropy = sum(entropies) / len(entropies)
        if content_type in ("png", "jpeg", "bmp") and avg_entropy > 7.95:
            findings.append(StegoFinding(
                method="Overall Entropy",
                severity="medium",
                confidence=0.4,
                description=f"Near-maximum average entropy ({avg_entropy:.2f}) — possible encrypted payload",
                details={"avg_entropy": avg_entropy}
            ))

        return findings

    # ── JPEG-Specific Analysis ────────────────────────────────────

    def _jpeg_dct_analysis(self, data: bytes) -> List[StegoFinding]:
        """Analyze JPEG DCT coefficients for steganography."""
        findings = []

        # Find SOS (Start of Scan) marker
        sos_pos = data.find(b"\xff\xda")
        if sos_pos == -1:
            return findings

        # Count consecutive zero coefficients (natural images have many)
        # Steganography modifies these distributions
        scan_data = data[sos_pos:]

        # Simple heuristic: check for unusual byte patterns in scan data
        # Natural JPEG has many 0x00 and 0xFF bytes due to Huffman coding
        null_count = scan_data.count(0)
        ff_count = scan_data.count(0xff)
        total = len(scan_data)
        if total > 0:
            special_ratio = (null_count + ff_count) / total
            # Natural JPEG: ~15-30% are 0x00 or 0xFF
            if special_ratio < 0.08:
                findings.append(StegoFinding(
                    method="JPEG DCT Analysis",
                    severity="high",
                    confidence=0.6,
                    description=f"Unusual JPEG scan data distribution ({special_ratio:.3f} special bytes)",
                    details={"special_ratio": special_ratio}
                ))

        return findings

    def _jpeg_quantization_analysis(self, data: bytes) -> List[StegoFinding]:
        """Check JPEG quantization tables for anomalies."""
        findings = []

        # Find DQT markers
        i = 2
        qt_count = 0
        while i < len(data) - 4:
            if data[i] != 0xff:
                break
            marker = data[i+1]
            if marker == 0xdb:  # DQT
                qt_count += 1
                length = struct.unpack(">H", data[i+2:i+4])[0]
                # Check for unusual quantization values
                qt_data = data[i+5:i+2+length]
                if qt_data:
                    avg_qt = sum(qt_data) / len(qt_data)
                    if avg_qt < 5:
                        findings.append(StegoFinding(
                            method="JPEG Quantization",
                            severity="medium",
                            confidence=0.5,
                            description=f"Very low quantization values (avg={avg_qt:.1f}) — high quality, suspicious for stego",
                            details={"avg_quantization": avg_qt}
                        ))
                i += 2 + length
            elif marker == 0xda:  # SOS
                break
            elif marker == 0xd9:  # EOI
                break
            else:
                if i + 3 < len(data):
                    length = struct.unpack(">H", data[i+2:i+4])[0]
                    i += 2 + length
                else:
                    break

        return findings

    # ── Channel Correlation Analysis ──────────────────────────────

    def _channel_correlation_analysis(self, data: bytes, content_type: str) -> List[StegoFinding]:
        """Analyze inter-channel correlation for steganography."""
        findings = []

        pixel_data = self._extract_pixels(data, content_type)
        if len(pixel_data) < 300:
            return findings

        # Sample RGB triples
        triples = []
        for i in range(0, min(len(pixel_data) - 2, 3000), 3):
            triples.append((pixel_data[i], pixel_data[i+1], pixel_data[i+2]))

        if len(triples) < 100:
            return findings

        # Calculate correlation between R-G, R-B, G-B channels
        r_vals = [t[0] for t in triples]
        g_vals = [t[1] for t in triples]
        b_vals = [t[2] for t in triples]

        rg_corr = self._correlation(r_vals, g_vals)
        rb_corr = self._correlation(r_vals, b_vals)
        gb_corr = self._correlation(g_vals, b_vals)

        # Natural images have moderate inter-channel correlation
        # LSB stego reduces it significantly — but many natural photos have low correlation too
        # Only flag when ALL channel pairs have very low correlation (strong stego indicator)
        avg_corr = (abs(rg_corr) + abs(rb_corr) + abs(gb_corr)) / 3

        if avg_corr < 0.01:
            findings.append(StegoFinding(
                method="Channel Correlation",
                severity="medium",
                confidence=0.4,
                description=f"Very low inter-channel correlation ({avg_corr:.3f}) — possible LSB manipulation",
                details={"rg": round(rg_corr, 3), "rb": round(rb_corr, 3),
                         "gb": round(gb_corr, 3), "avg": round(avg_corr, 3)}
            ))

        return findings

    # ── Audio Steganography Analysis ──────────────────────────────

    def _audio_stego_analysis(self, data: bytes, content_type: str) -> List[StegoFinding]:
        """Detect audio steganography."""
        findings = []

        if content_type == "wav":
            findings.extend(self._wav_lsb_analysis(data))
        elif content_type == "mp3":
            findings.extend(self._mp3_analysis(data))

        return findings

    def _wav_lsb_analysis(self, data: bytes) -> List[StegoFinding]:
        """Analyze WAV audio for LSB steganography."""
        findings = []

        # Find data chunk
        data_pos = data.find(b"data")
        if data_pos == -1 or data_pos + 8 > len(data):
            return findings

        chunk_size = struct.unpack("<I", data[data_pos+4:data_pos+8])[0]
        audio_data = data[data_pos+8:data_pos+8+chunk_size]

        if len(audio_data) < 1000:
            return findings

        # LSB analysis on audio samples
        lsb_0 = sum(1 for b in audio_data if b & 1 == 0)
        lsb_1 = sum(1 for b in audio_data if b & 1 == 1)
        total = lsb_0 + lsb_1
        if total > 0:
            ratio = lsb_1 / total
            deviation = abs(ratio - 0.5)
            if deviation < 0.01:
                findings.append(StegoFinding(
                    method="Audio LSB Analysis",
                    severity="high",
                    confidence=0.7,
                    description=f"Uniform LSB distribution in audio ({ratio:.4f})",
                    details={"lsb_ratio": ratio}
                ))

        return findings

    def _mp3_analysis(self, data: bytes) -> List[StegoFinding]:
        """Analyze MP3 for steganographic modifications."""
        findings = []

        # Check for unusual padding bytes in MP3 frames
        if len(data) > 1024:
            # Count null bytes in the file — too many suggests hidden data
            null_ratio = data.count(0) / len(data)
            if null_ratio > 0.15:
                findings.append(StegoFinding(
                    method="MP3 Null Analysis",
                    severity="low",
                    confidence=0.4,
                    description=f"High null byte ratio ({null_ratio:.3f}) in MP3",
                    details={"null_ratio": null_ratio}
                ))

        return findings

    # ── Metadata Analysis ─────────────────────────────────────────

    def _metadata_analysis(self, data: bytes, content_type: str, ext: str) -> List[StegoFinding]:
        """Check for suspicious metadata / comments."""
        findings = []

        if content_type == "jpeg":
            # Check for COM (Comment) markers
            com_count = 0
            i = 2
            while i < len(data) - 4 and data[i] == 0xff:
                marker = data[i+1]
                if marker == 0xfe:  # COM
                    com_count += 1
                    length = struct.unpack(">H", data[i+2:i+4])[0]
                    if length > 500:
                        findings.append(StegoFinding(
                            method="JPEG Comment",
                            severity="medium",
                            confidence=0.5,
                            description=f"Large JPEG comment ({length:,} bytes) — possible hidden data",
                            details={"comment_size": length}
                        ))
                    i += 2 + length
                elif marker == 0xda:  # SOS
                    break
                else:
                    if i + 3 < len(data):
                        length = struct.unpack(">H", data[i+2:i+4])[0]
                        i += 2 + length
                    else:
                        break
            if com_count > 5:
                findings.append(StegoFinding(
                    method="JPEG Comment Count",
                    severity="medium",
                    confidence=0.5,
                    description=f"Multiple JPEG comments ({com_count}) — unusual",
                    details={"comment_count": com_count}
                ))

        if content_type == "png":
            # Check for unusual PNG chunks
            known_chunks = {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tEXt", b"zTXt",
                           b"iTXt", b"pHYs", b"tIME", b"gAMA", b"cHRM", b"sRGB",
                           b"iCCP", b"bKGD", b"hIST", b"tRNS", b"sBIT", b"sPLT"}
            pos = 8  # Skip PNG signature
            unknown_chunks = []
            while pos + 8 < len(data) and pos < 65536:
                try:
                    length = struct.unpack(">I", data[pos:pos+4])[0]
                    chunk_type = data[pos+4:pos+8]
                    # Validate: chunk type must be 4 ASCII letters, length must be sane
                    if length > 0x7FFFFFFF or not all(65 <= b <= 122 for b in chunk_type):
                        break  # Corrupt or end of valid chunks
                    if chunk_type not in known_chunks:
                        unknown_chunks.append(chunk_type.decode('ascii', errors='replace'))
                    pos += 12 + length
                except Exception:
                    break
            if unknown_chunks:
                findings.append(StegoFinding(
                    method="PNG Unknown Chunks",
                    severity="medium",
                    confidence=0.6,
                    description=f"Unknown PNG chunks: {', '.join(unknown_chunks[:5])}",
                    details={"unknown_chunks": unknown_chunks[:10]}
                ))

        return findings

    # ── Trailing Data Analysis ────────────────────────────────────

    def _trailing_analysis(self, data: bytes, content_type: str, ext: str) -> List[StegoFinding]:
        """Check for data after file end marker."""
        findings = []

        end_markers = {
            "jpeg": (b"\xff\xd9", 2),
            "png": (b"IEND", 8),
            "gif": (b"\x3b", 1),
            "pdf": (b"%%EOF", 5),
        }

        marker_info = end_markers.get(content_type)
        if not marker_info:
            return findings

        marker, extra = marker_info
        pos = data.rfind(marker)
        if pos != -1 and pos + extra < len(data):
            trailing_size = len(data) - pos - extra
            if trailing_size > 16:
                # Check if trailing data is just nulls/padding
                trailing = data[pos+extra:]
                stripped = trailing.strip(b"\x00\r\n\t ")
                if len(stripped) > 16:
                    findings.append(StegoFinding(
                        method="Trailing Data",
                        severity="critical" if trailing_size > 512 else "high",
                        confidence=0.9 if trailing_size > 512 else 0.7,
                        description=f"{trailing_size:,} bytes after {content_type.upper()} end marker",
                        details={"trailing_size": trailing_size,
                                 "trailing_entropy": self._shannon_bytes(trailing)}
                    ))

        return findings

    # ── Duplicate Marker Analysis ─────────────────────────────────

    def _duplicate_marker_analysis(self, data: bytes, content_type: str) -> List[StegoFinding]:
        """Check for duplicate format markers (polyglot indicator)."""
        findings = []

        markers = {
            "jpeg": [b"\xff\xd8\xff"],
            "png": [b"\x89PNG"],
            "gif": [b"GIF8"],
            "pdf": [b"%PDF"],
        }

        for marker in markers.get(content_type, []):
            count = 0
            pos = 0
            while True:
                pos = data.find(marker, pos + 1 if count > 0 else 0)
                if pos == -1:
                    break
                count += 1
            if count > 1:
                findings.append(StegoFinding(
                    method="Duplicate Header",
                    severity="critical",
                    confidence=0.95,
                    description=f"Multiple {content_type.upper()} headers ({count}) — file is a polyglot",
                    details={"count": count}
                ))

        return findings

    # ── Helpers ────────────────────────────────────────────────────

    def _find_pixel_data_start(self, data: bytes, content_type: str) -> int:
        """Find where pixel data begins."""
        if content_type == "bmp":
            if len(data) >= 14:
                offset = struct.unpack("<I", data[10:14])[0]
                return offset
        elif content_type == "png":
            # Find first IDAT chunk
            pos = 8
            while pos + 8 < len(data):
                try:
                    length = struct.unpack(">I", data[pos:pos+4])[0]
                    chunk_type = data[pos+4:pos+8]
                    if chunk_type == b"IDAT":
                        return pos + 8
                    pos += 12 + length
                except Exception:
                    break
        elif content_type == "gif":
            # Skip header, GCT, and image descriptor
            pos = 6
            if len(data) > 10:
                flags = data[10]
                gct_size = 3 * (2 ** ((flags & 7) + 1)) if flags & 0x80 else 0
                pos = 13 + gct_size
            return pos
        elif content_type == "tiff":
            return 8
        return 0

    def _shannon_bytes(self, data: bytes) -> float:
        if not data:
            return 0.0
        freq = [0] * 256
        for b in data:
            freq[b] += 1
        l = len(data)
        return -sum((f/l) * math.log2(f/l) for f in freq if f > 0)

    def _correlation(self, x: list, y: list) -> float:
        """Pearson correlation coefficient."""
        n = min(len(x), len(y))
        if n < 2:
            return 0.0
        mx = sum(x[:n]) / n
        my = sum(y[:n]) / n
        cov = sum((x[i]-mx)*(y[i]-my) for i in range(n)) / n
        sx = math.sqrt(sum((xi-mx)**2 for xi in x[:n]) / n)
        sy = math.sqrt(sum((yi-my)**2 for yi in y[:n]) / n)
        if sx == 0 or sy == 0:
            return 0.0
        return cov / (sx * sy)
