"""
Synthetic training data generator — creates labeled polyglot samples
that mimic RedTeam Builder's EXE→JPG/PDF/MP4, BAT→MP4, VBS→JPG wrapping,
plus benign files for balanced training.
"""

import os, struct, random, logging, hashlib, math
from pathlib import Path
from typing import List, Tuple

import numpy as np

logger = logging.getLogger("polyglot_shield.generator")


# ── Tiny valid PE header (DOS + PE stub, minimal) ─────────────────────────────
_PE_STUB = (
    b"MZ"                              # e_magic
    + b"\x00" * 58                     # padding to e_lfanew
    + struct.pack("<I", 64)            # e_lfanew = 64
    + b"PE\x00\x00"                    # PE signature
    + struct.pack("<H", 0x14c)         # Machine = IMAGE_FILE_MACHINE_I386
    + struct.pack("<H", 1)             # NumberOfSections = 1
    + b"\x00" * 16                     # rest of COFF header
    + b"\x00" * 224                    # Optional header (zeroed)
    + b".text\x00\x00\x00"            # Section name
    + b"\x00" * 32                     # Section header fields
)

_ELF_STUB = (
    b"\x7fELF"                         # magic
    + b"\x02"                          # 64-bit
    + b"\x01"                          # little-endian
    + b"\x01"                          # ELF version
    + b"\x00" * 9                      # OS/ABI + padding
    + struct.pack("<H", 2)             # ET_EXEC
    + struct.pack("<H", 0x3e)          # x86-64
    + b"\x00" * 16                     # rest
    + struct.pack("<Q", 0x400000)      # e_entry
    + struct.pack("<Q", 64)            # e_phoff
    + struct.pack("<Q", 0)             # e_shoff
    + b"\x00" * 12                     # flags + header sizes
)

_PDF_HEADER = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
_PDF_TRAILER = b"xref\n0 1\ntrailer<</Root 1 0 R>>\nstartxref\n0\n%%EOF\n"

_GIF_HEADER = b"GIF89a\x01\x00\x01\x00\x80\x00\x00"
_PNG_HEADER = b"\x89PNG\r\n\x1a\n"
_JPEG_HEADER = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00"
_MP4_HEADER = b"\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2"
_ZIP_HEADER = b"PK\x03\x04\x14\x00\x00\x00\x00\x00"

_HTML_DOC = (
    b"<!DOCTYPE html><html><head><title>Document</title></head>"
    b"<body><h1>Document</h1><p>Content</p></body></html>"
)

_SCRIPT_BAT = (
    b"@echo off\r\nrem Document viewer\r\n"
    b"echo Loading document...\r\npause\r\n"
)

_SCRIPT_VBS = (
    b"' Document viewer\r\n"
    b"WScript.Echo \"Loading document...\"\r\n"
)


class SyntheticGenerator:
    """Generate synthetic polyglot + benign samples for training."""

    def __init__(self, output_dir: str = "samples"):
        self.output_dir = Path(output_dir)
        self.mal_dir = self.output_dir / "malware"
        self.ben_dir = self.output_dir / "benign"
        self.mal_dir.mkdir(parents=True, exist_ok=True)
        self.ben_dir.mkdir(parents=True, exist_ok=True)

    def generate_all(self, n_per_class: int = 500) -> List[Tuple[str, int]]:
        """
        Generate full balanced dataset.
        Returns: list of (filepath, label) where 0=benign, 1=polyglot.
        """
        logger.info(f"Generating synthetic dataset: {n_per_class} per class")
        samples: List[Tuple[str, int]] = []

        # ── Polyglot samples (RedTeam Builder patterns) ───────────────────
        generators = [
            ("exe_in_jpg",   self._gen_exe_in_jpg),
            ("exe_in_png",   self._gen_exe_in_png),
            ("exe_in_pdf",   self._gen_exe_in_pdf),
            ("exe_in_mp4",   self._gen_exe_in_mp4),
            ("exe_in_html",  self._gen_exe_in_html),
            ("exe_in_zip",   self._gen_exe_in_zip),
            ("bat_in_mp4",   self._gen_bat_in_mp4),
            ("vbs_in_jpg",   self._gen_vbs_in_jpg),
            ("elf_in_pdf",   self._gen_elf_in_pdf),
            ("elf_in_zip",   self._gen_elf_in_zip),
            ("script_in_doc", self._gen_script_in_doc),
            ("packed_pe",    self._gen_packed_pe),
        ]

        per_type = max(1, n_per_class // len(generators))
        for name, gen_fn in generators:
            for i in range(per_type):
                try:
                    path = gen_fn(i)
                    samples.append((str(path), 1))
                except Exception as e:
                    logger.debug(f"Failed {name}_{i}: {e}")

        # ── Benign samples ────────────────────────────────────────────────
        benign_gens = [
            ("clean_pe",    self._gen_clean_pe),
            ("clean_pdf",   self._gen_clean_pdf),
            ("clean_jpg",   self._gen_clean_jpg),
            ("clean_png",   self._gen_clean_png),
            ("clean_html",  self._gen_clean_html),
            ("clean_zip",   self._gen_clean_zip),
            ("clean_text",  self._gen_clean_text),
            ("clean_mp4",   self._gen_clean_mp4),
            ("clean_elf",   self._gen_clean_elf),
        ]
        per_benign = max(1, n_per_class // len(benign_gens))
        for name, gen_fn in benign_gens:
            for i in range(per_benign):
                try:
                    path = gen_fn(i)
                    samples.append((str(path), 0))
                except Exception as e:
                    logger.debug(f"Failed {name}_{i}: {e}")

        logger.info(f"Generated {len(samples)} samples "
                     f"({sum(1 for _, l in samples if l == 1)} malicious, "
                     f"{sum(1 for _, l in samples if l == 0)} benign)")
        return samples

    def _rand_payload(self, size_range=(500, 5000)) -> bytes:
        """Random binary payload with controlled entropy."""
        size = random.randint(*size_range)
        mode = random.choice(["high", "mid", "low", "structured"])
        if mode == "high":
            return os.urandom(size)
        elif mode == "mid":
            base = os.urandom(size // 2)
            return base + b"\x00" * (size - len(base))
        elif mode == "low":
            pattern = bytes(range(256)) * (size // 256 + 1)
            return pattern[:size]
        else:
            chunks = []
            for _ in range(size // 64):
                chunks.append(bytes([random.randint(0x20, 0x7e)] * 64))
            return b"".join(chunks)[:size]

    # ── RedTeam Builder polyglot patterns ──────────────────────────────────

    def _gen_exe_in_jpg(self, i: int) -> Path:
        """EXE payload disguised as JPEG (RedTeam Builder: EXE→JPG)."""
        payload = self._rand_payload()
        data = _JPEG_HEADER + os.urandom(64) + _PE_STUB + payload + os.urandom(128)
        p = self.mal_dir / f"exe_in_jpg_{i:04d}.jpg"
        p.write_bytes(data)
        return p

    def _gen_exe_in_png(self, i: int) -> Path:
        """EXE payload disguised as PNG (RedTeam Builder: EXE→PNG)."""
        payload = self._rand_payload()
        data = _PNG_HEADER + os.urandom(32) + _PE_STUB + payload + os.urandom(64)
        p = self.mal_dir / f"exe_in_png_{i:04d}.png"
        p.write_bytes(data)
        return p

    def _gen_exe_in_pdf(self, i: int) -> Path:
        """EXE payload inside PDF (RedTeam Builder: EXE→PDF)."""
        payload = self._rand_payload()
        data = _PDF_HEADER + b"\n" + _PE_STUB + payload + b"\n" + _PDF_TRAILER
        p = self.mal_dir / f"exe_in_pdf_{i:04d}.pdf"
        p.write_bytes(data)
        return p

    def _gen_exe_in_mp4(self, i: int) -> Path:
        """EXE payload inside MP4 (RedTeam Builder: EXE→MP4)."""
        payload = self._rand_payload()
        data = _MP4_HEADER + os.urandom(256) + _PE_STUB + payload
        p = self.mal_dir / f"exe_in_mp4_{i:04d}.mp4"
        p.write_bytes(data)
        return p

    def _gen_exe_in_html(self, i: int) -> Path:
        """EXE payload inside HTML (MIME smuggling)."""
        payload = self._rand_payload()
        data = _HTML_DOC[:80] + _PE_STUB + payload + _HTML_DOC[80:]
        p = self.mal_dir / f"exe_in_html_{i:04d}.html"
        p.write_bytes(data)
        return p

    def _gen_exe_in_zip(self, i: int) -> Path:
        """EXE inside ZIP archive."""
        payload = self._rand_payload()
        data = _ZIP_HEADER + os.urandom(64) + _PE_STUB + payload
        p = self.mal_dir / f"exe_in_zip_{i:04d}.zip"
        p.write_bytes(data)
        return p

    def _gen_bat_in_mp4(self, i: int) -> Path:
        """BAT script disguised as MP4 (RedTeam Builder: BAT→MP4)."""
        payload = self._rand_payload((200, 2000))
        data = _MP4_HEADER + os.urandom(128) + _SCRIPT_BAT + payload
        p = self.mal_dir / f"bat_in_mp4_{i:04d}.mp4"
        p.write_bytes(data)
        return p

    def _gen_vbs_in_jpg(self, i: int) -> Path:
        """VBS script disguised as JPEG (RedTeam Builder: VBS→JPG)."""
        payload = self._rand_payload((200, 2000))
        data = _JPEG_HEADER + os.urandom(32) + _SCRIPT_VBS + payload
        p = self.mal_dir / f"vbs_in_jpg_{i:04d}.jpg"
        p.write_bytes(data)
        return p

    def _gen_elf_in_pdf(self, i: int) -> Path:
        """ELF binary hidden inside PDF."""
        payload = self._rand_payload()
        data = _PDF_HEADER + b"\n" + _ELF_STUB + payload + b"\n" + _PDF_TRAILER
        p = self.mal_dir / f"elf_in_pdf_{i:04d}.pdf"
        p.write_bytes(data)
        return p

    def _gen_elf_in_zip(self, i: int) -> Path:
        """ELF binary inside ZIP."""
        payload = self._rand_payload()
        data = _ZIP_HEADER + os.urandom(64) + _ELF_STUB + payload
        p = self.mal_dir / f"elf_in_zip_{i:04d}.zip"
        p.write_bytes(data)
        return p

    def _gen_script_in_doc(self, i: int) -> Path:
        """Script payload in document-like file."""
        payload = self._rand_payload((200, 1500))
        data = (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # OLE header
                + os.urandom(64) + _SCRIPT_VBS + payload)
        p = self.mal_dir / f"script_in_doc_{i:04d}.doc"
        p.write_bytes(data)
        return p

    def _gen_packed_pe(self, i: int) -> Path:
        """PE with UPX markers (packed malware)."""
        payload = self._rand_payload((1000, 8000))
        data = _PE_STUB + b"UPX0" + b"\x00" * 64 + b"UPX1" + payload
        p = self.mal_dir / f"packed_pe_{i:04d}.exe"
        p.write_bytes(data)
        return p

    # ── Benign generators ─────────────────────────────────────────────────

    def _gen_clean_pe(self, i: int) -> Path:
        payload = self._rand_payload((2000, 15000))
        data = _PE_STUB + payload
        p = self.ben_dir / f"clean_pe_{i:04d}.exe"
        p.write_bytes(data)
        return p

    def _gen_clean_pdf(self, i: int) -> Path:
        pages = random.randint(1, 5)
        body = _PDF_HEADER
        for pg in range(pages):
            body += f"{pg + 2} 0 obj<</Type/Page/Parent 2 0 R>>endobj\n".encode()
        body += _PDF_TRAILER
        p = self.ben_dir / f"clean_pdf_{i:04d}.pdf"
        p.write_bytes(body)
        return p

    def _gen_clean_jpg(self, i: int) -> Path:
        data = _JPEG_HEADER + os.urandom(random.randint(500, 5000)) + b"\xff\xd9"
        p = self.ben_dir / f"clean_jpg_{i:04d}.jpg"
        p.write_bytes(data)
        return p

    def _gen_clean_png(self, i: int) -> Path:
        data = _PNG_HEADER + os.urandom(random.randint(500, 5000))
        p = self.ben_dir / f"clean_png_{i:04d}.png"
        p.write_bytes(data)
        return p

    def _gen_clean_html(self, i: int) -> Path:
        body = f"<html><head><title>Page {i}</title></head><body>"
        body += f"<p>Hello world {i}</p>" * random.randint(5, 50)
        body += "</body></html>"
        p = self.ben_dir / f"clean_html_{i:04d}.html"
        p.write_bytes(body.encode())
        return p

    def _gen_clean_zip(self, i: int) -> Path:
        data = _ZIP_HEADER + os.urandom(random.randint(200, 2000))
        p = self.ben_dir / f"clean_zip_{i:04d}.zip"
        p.write_bytes(data)
        return p

    def _gen_clean_text(self, i: int) -> Path:
        text = (f"Document {i}\n{'=' * 40}\n\n"
                + "Lorem ipsum dolor sit amet. " * random.randint(10, 100))
        p = self.ben_dir / f"clean_text_{i:04d}.txt"
        p.write_bytes(text.encode())
        return p

    def _gen_clean_mp4(self, i: int) -> Path:
        data = _MP4_HEADER + os.urandom(random.randint(1000, 10000))
        p = self.ben_dir / f"clean_mp4_{i:04d}.mp4"
        p.write_bytes(data)
        return p

    def _gen_clean_elf(self, i: int) -> Path:
        payload = self._rand_payload((1000, 8000))
        data = _ELF_STUB + payload
        p = self.ben_dir / f"clean_elf_{i:04d}.elf"
        p.write_bytes(data)
        return p
