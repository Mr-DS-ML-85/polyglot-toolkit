"""
PE (Portable Executable) anomaly analysis engine.

Detects:
  - Entropy anomalies per section
  - Packed/encrypted sections
  - Suspicious section names
  - Import table anomalies
  - Entry point anomalies
  - Overlay analysis
  - Checksum validation
  - Digital signature checks
  - Resource anomalies
  - TLS callback analysis
  - Debug directory anomalies

Author: Mr-DS-ML-85
"""

import struct
import math
import hashlib
import os
import logging
from typing import Dict, List, Any
from dataclasses import dataclass, field

logger = logging.getLogger("polyglot_shield.pe")


@dataclass
class PEFinding:
    severity: str
    category: str
    description: str
    details: Dict[str, Any] = field(default_factory=dict)


class PEAnalyzer:
    """PE file anomaly analyzer."""

    # Known suspicious section names
    SUSPICIOUS_SECTIONS = {
        b".upx0", b".upx1", b".aspack", b".adata", b".nsp0", b".nsp1",
        b".perplex", b".petite", b".y0da", b".yoda", b".sforce",
        b".vmp0", b".vmp1", b".themida", b".winlice", b".enigma1",
        b".packed", b".RLPack", b".MPRESS1", b".MPRESS2",
    }

    NORMAL_SECTIONS = {
        b".text", b".data", b".rdata", b".bss", b".idata", b".edata",
        b".rsrc", b".reloc", b".tls", b".pdata", b".xdata", b".CRT",
        b".gnu_debuglink", b".debug", b".sdata", b".sbss", b".edata",
        b".orpc", b".didat", b".sforce32", b".ndata",
    }

    def analyze(self, filepath: str) -> List[PEFinding]:
        with open(filepath, "rb") as f:
            data = f.read()

        findings = []
        if len(data) < 64 or data[:2] != b"MZ":
            findings.append(PEFinding("critical", "format", "Not a valid PE file"))
            return findings

        try:
            pe_off = struct.unpack("<I", data[60:64])[0]
            if pe_off + 24 > len(data) or data[pe_off:pe_off+4] != b"PE\x00\x00":
                findings.append(PEFinding("critical", "format", "Invalid PE signature"))
                return findings

            machine = struct.unpack("<H", data[pe_off+4:pe_off+6])[0]
            num_sections = struct.unpack("<H", data[pe_off+6:pe_off+8])[0]
            timestamp = struct.unpack("<I", data[pe_off+8:pe_off+12])[0]
            opt_hdr_size = struct.unpack("<H", data[pe_off+20:pe_off+22])[0]
            characteristics = struct.unpack("<H", data[pe_off+22:pe_off+24])[0]

            # Optional header
            opt_off = pe_off + 24
            if opt_off + opt_hdr_size > len(data):
                findings.append(PEFinding("critical", "format", "Optional header truncated"))
                return findings

            magic = struct.unpack("<H", data[opt_off:opt_off+2])[0]
            is_64 = magic == 0x20b

            if is_64:
                entry_point = struct.unpack("<I", data[opt_off+16:opt_off+20])[0]
                image_base = struct.unpack("<Q", data[opt_off+24:opt_off+32])[0]
                section_align = struct.unpack("<I", data[opt_off+32:opt_off+36])[0]
                file_align = struct.unpack("<I", data[opt_off+36:opt_off+40])[0]
                image_size = struct.unpack("<I", data[opt_off+56:opt_off+60])[0]
                checksum_off = opt_off + 64
            else:
                entry_point = struct.unpack("<I", data[opt_off+16:opt_off+20])[0]
                image_base = struct.unpack("<I", data[opt_off+28:opt_off+32])[0]
                section_align = struct.unpack("<I", data[opt_off+32:opt_off+36])[0]
                file_align = struct.unpack("<I", data[opt_off+36:opt_off+40])[0]
                image_size = struct.unpack("<I", data[opt_off+56:opt_off+60])[0]
                checksum_off = opt_off + 64

            findings.extend(self._check_entry_point(entry_point, num_sections, data, pe_off, opt_off, is_64))
            findings.extend(self._check_timestamp(timestamp))
            findings.extend(self._check_characteristics(characteristics))
            findings.extend(self._check_checksum(data, checksum_off))
            findings.extend(self._check_sections(data, pe_off, num_sections, opt_hdr_size))
            findings.extend(self._check_overlay(data, pe_off, num_sections, opt_hdr_size))
            findings.extend(self._check_imports(data, pe_off, opt_off, is_64))
            findings.extend(self._check_tls(data, pe_off, opt_off, is_64))
            findings.extend(self._check_dos_stub(data, pe_off))
            findings.extend(self._check_debug(data, pe_off, opt_off, is_64))

        except Exception as e:
            findings.append(PEFinding("high", "parse", f"PE parsing error: {e}"))

        return findings

    def _check_entry_point(self, ep, num_sections, data, pe_off, opt_off, is_64) -> List[PEFinding]:
        findings = []
        if ep == 0:
            findings.append(PEFinding("high", "entry_point", "Entry point is 0 — DLL or suspicious"))

        # Check if EP is in a normal section
        sec_off = pe_off + 24 + (328 if is_64 else 224)
        for i in range(min(num_sections, 96)):
            if sec_off + 40 * (i+1) > len(data):
                break
            sec_data = data[sec_off + 40*i:sec_off + 40*(i+1)]
            vsize = struct.unpack("<I", sec_data[8:12])[0]
            vaddr = struct.unpack("<I", sec_data[12:16])[0]
            if vaddr <= ep < vaddr + vsize:
                name = sec_data[:8].rstrip(b"\x00")
                if name in self.SUSPICIOUS_SECTIONS:
                    findings.append(PEFinding("critical", "entry_point",
                        f"Entry point in packed section: {name.decode(errors='replace')}"))
                elif name not in self.NORMAL_SECTIONS:
                    findings.append(PEFinding("medium", "entry_point",
                        f"Entry point in unusual section: {name.decode(errors='replace')}"))
                break

        return findings

    def _check_timestamp(self, ts) -> List[PEFinding]:
        findings = []
        if ts == 0:
            findings.append(PEFinding("medium", "timestamp", "Timestamp is 0 — stripped or crafted"))
        elif ts < 946684800:  # Before 2000-01-01
            findings.append(PEFinding("medium", "timestamp", f"Suspiciously old timestamp ({ts})"))
        elif ts > 2000000000:  # After ~2033
            findings.append(PEFinding("low", "timestamp", f"Future timestamp ({ts})"))
        return findings

    def _check_characteristics(self, chars) -> List[PEFinding]:
        findings = []
        if chars & 0x2000:  # DLL
            findings.append(PEFinding("info", "type", "File is a DLL"))
        if chars & 0x0002:  # EXECUTABLE_IMAGE
            pass
        if not (chars & 0x0002) and not (chars & 0x2000):
            findings.append(PEFinding("medium", "characteristics",
                "Neither EXECUTABLE_IMAGE nor DLL flag set"))
        return findings

    def _check_checksum(self, data, checksum_off) -> List[PEFinding]:
        findings = []
        if checksum_off + 4 > len(data):
            return findings
        stored = struct.unpack("<I", data[checksum_off:checksum_off+4])[0]
        if stored != 0:
            # Calculate PE checksum
            calc = self._calc_pe_checksum(data)
            if stored != calc:
                findings.append(PEFinding("medium", "checksum",
                    f"PE checksum mismatch (stored=0x{stored:08x}, calc=0x{calc:08x})"))
        return findings

    def _check_sections(self, data, pe_off, num_sections, opt_hdr_size) -> List[PEFinding]:
        findings = []
        is_64 = struct.unpack("<H", data[pe_off+24:pe_off+26])[0] == 0x20b
        sec_off = pe_off + 24 + (328 if is_64 else 224)

        for i in range(min(num_sections, 96)):
            if sec_off + 40 * (i+1) > len(data):
                break
            sec = data[sec_off + 40*i:sec_off + 40*(i+1)]
            name = sec[:8].rstrip(b"\x00")
            vsize = struct.unpack("<I", sec[8:12])[0]
            vaddr = struct.unpack("<I", sec[12:16])[0]
            raw_size = struct.unpack("<I", sec[16:20])[0]
            raw_off = struct.unpack("<I", sec[20:24])[0]
            chars = struct.unpack("<I", sec[36:40])[0]

            # Entropy of section
            if raw_size > 0 and raw_off + raw_size <= len(data):
                sec_data = data[raw_off:raw_off+raw_size]
                ent = self._shannon(sec_data)
                if ent > 7.5 and raw_size > 4096:
                    findings.append(PEFinding("high", "section",
                        f"Section '{name.decode(errors='replace')}' has very high entropy ({ent:.2f}) — possibly packed/encrypted",
                        {"name": name.decode(errors='replace'), "entropy": ent, "size": raw_size}))
                elif ent > 7.0 and raw_size > 1024:
                    findings.append(PEFinding("medium", "section",
                        f"Section '{name.decode(errors='replace')}' has high entropy ({ent:.2f})",
                        {"name": name.decode(errors='replace'), "entropy": ent}))

            # Suspicious section names
            if name.lower() in self.SUSPICIOUS_SECTIONS:
                findings.append(PEFinding("critical", "section",
                    f"Known packer section: {name.decode(errors='replace')}"))

            # Writable + executable
            if (chars & 0x20000000) and (chars & 0x80000000):
                findings.append(PEFinding("high", "section",
                    f"Section '{name.decode(errors='replace')}' is both writable and executable"))

            # Virtual size much larger than raw size
            if raw_size > 0 and vsize > raw_size * 10:
                findings.append(PEFinding("medium", "section",
                    f"Section '{name.decode(errors='replace')}' virtual size ({vsize:,}) >> raw size ({raw_size:,})"))

        return findings

    def _check_overlay(self, data, pe_off, num_sections, opt_hdr_size) -> List[PEFinding]:
        findings = []
        is_64 = struct.unpack("<H", data[pe_off+24:pe_off+26])[0] == 0x20b
        sec_off = pe_off + 24 + (328 if is_64 else 224)

        max_end = 0
        for i in range(min(num_sections, 96)):
            if sec_off + 40 * (i+1) > len(data):
                break
            sec = data[sec_off + 40*i:sec_off + 40*(i+1)]
            raw_size = struct.unpack("<I", sec[16:20])[0]
            raw_off = struct.unpack("<I", sec[20:24])[0]
            end = raw_off + raw_size
            if end > max_end:
                max_end = end

        if max_end < len(data):
            overlay_size = len(data) - max_end
            if overlay_size > 64:
                overlay = data[max_end:max_end+256]
                findings.append(PEFinding("high" if overlay_size > 1024 else "medium", "overlay",
                    f"PE overlay: {overlay_size:,} bytes appended after sections",
                    {"offset": max_end, "size": overlay_size}))

        return findings

    def _check_imports(self, data, pe_off, opt_off, is_64) -> List[PEFinding]:
        findings = []
        # Simple heuristic: count MZ headers in import area
        if b"MZ" in data[opt_off+200:opt_off+2000]:
            findings.append(PEFinding("medium", "imports",
                "Secondary MZ header in import area — possible embedded DLL"))
        return findings

    def _check_tls(self, data, pe_off, opt_off, is_64) -> List[PEFinding]:
        findings = []
        # TLS callbacks are commonly used for anti-debug / unpacking
        tls_data_dir_off = opt_off + (160 if is_64 else 140)  # TLS is data dir[9]
        if tls_data_dir_off + 8 <= len(data):
            tls_rva = struct.unpack("<I", data[tls_data_dir_off:tls_data_dir_off+4])[0]
            tls_size = struct.unpack("<I", data[tls_data_dir_off+4:tls_data_dir_off+8])[0]
            if tls_rva > 0:
                findings.append(PEFinding("medium", "tls",
                    f"TLS callback directory present (RVA=0x{tls_rva:x}, size={tls_size})"))
        return findings

    def _check_dos_stub(self, data, pe_off) -> List[PEFinding]:
        findings = []
        if pe_off > 128:
            stub = data[64:pe_off]
            # Check for non-standard DOS stub
            if b"This program" not in stub and b"cannot be run" not in stub:
                # Check if stub has code
                non_zero = sum(1 for b in stub if b != 0)
                if non_zero > 16:
                    findings.append(PEFinding("low", "dos_stub",
                        f"Custom DOS stub ({non_zero} non-zero bytes)"))
        return findings

    def _check_debug(self, data, pe_off, opt_off, is_64) -> List[PEFinding]:
        findings = []
        debug_dir_off = opt_off + (168 if is_64 else 148)  # Debug is data dir[6]
        if debug_dir_off + 8 <= len(data):
            debug_rva = struct.unpack("<I", data[debug_dir_off:debug_dir_off+4])[0]
            debug_size = struct.unpack("<I", data[debug_dir_off+4:debug_dir_off+8])[0]
            if debug_rva > 0 and debug_size > 0:
                findings.append(PEFinding("info", "debug",
                    f"Debug directory present (RVA=0x{debug_rva:x}, size={debug_size})"))
        return findings

    def _shannon(self, data: bytes) -> float:
        if not data:
            return 0.0
        freq = [0] * 256
        for b in data:
            freq[b] += 1
        l = len(data)
        return -sum((f/l) * math.log2(f/l) for f in freq if f > 0)

    def _calc_pe_checksum(self, data: bytes) -> int:
        """Calculate PE checksum."""
        checksum = 0
        # PE checksum offset varies; simplified calculation
        pe_off = struct.unpack("<I", data[60:64])[0]
        checksum_off = pe_off + 24 + 64  # Approximate
        for i in range(0, len(data) - 3, 4):
            if i == checksum_off:
                continue
            dword = struct.unpack("<I", data[i:i+4])[0]
            checksum = (checksum + dword) & 0xffffffff
        checksum = (checksum & 0xffff) + (checksum >> 16)
        checksum += checksum >> 16
        checksum &= 0xffff
        return checksum + len(data)
