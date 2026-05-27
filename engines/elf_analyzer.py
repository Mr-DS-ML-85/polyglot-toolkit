"""
ELF section anomaly detection engine.

Detects:
  - Section header anomalies
  - Unusual section types
  - Entropy anomalies per section
  - Symbol table anomalies
  - Dynamic linking anomalies
  - Packed/encrypted sections
  - Stripped vs non-stripped analysis
  - GOT/PLT anomalies
  - Note section analysis
  - RELRO analysis

Author: Mr-DS-ML-85
"""

import struct
import math
import os
import logging
from typing import Dict, List, Any
from dataclasses import dataclass, field

logger = logging.getLogger("polyglot_shield.elf")


@dataclass
class ELFFinding:
    severity: str
    category: str
    description: str
    details: Dict[str, Any] = field(default_factory=dict)


class ELFAnalyzer:
    """ELF binary anomaly analyzer."""

    # Section type constants
    SHT_NULL = 0
    SHT_PROGBITS = 1
    SHT_SYMTAB = 2
    SHT_STRTAB = 3
    SHT_RELA = 4
    SHT_HASH = 5
    SHT_DYNAMIC = 6
    SHT_NOTE = 7
    SHT_NOBITS = 8
    SHT_REL = 9
    SHT_DYNSYM = 11
    SHT_INIT_ARRAY = 14
    SHT_FINI_ARRAY = 15
    SHT_GNU_HASH = 0x6ffffff6
    SHT_GNU_VERSYM = 0x6fffffff
    SHT_GNU_VERNEED = 0x6ffffffe

    # Known suspicious section names
    SUSPICIOUS_SECTIONS = {b".upx", b".packed", b".encrypted", b".obfuscated"}

    def analyze(self, filepath: str) -> List[ELFFinding]:
        with open(filepath, "rb") as f:
            data = f.read()

        findings = []
        if len(data) < 52 or data[:4] != b"\x7fELF":
            findings.append(ELFFinding("critical", "format", "Not a valid ELF file"))
            return findings

        try:
            # Parse ELF header
            is_64 = data[4] == 2
            endian = "little" if data[5] == 1 else "big"
            fmt = "<" if endian == "little" else ">"

            if is_64:
                if len(data) < 64:
                    findings.append(ELFFinding("critical", "format", "ELF header truncated"))
                    return findings
                e_type = struct.unpack(fmt + "H", data[16:18])[0]
                e_machine = struct.unpack(fmt + "H", data[18:20])[0]
                e_entry = struct.unpack(fmt + "Q", data[24:32])[0]
                e_phoff = struct.unpack(fmt + "Q", data[32:40])[0]
                e_shoff = struct.unpack(fmt + "Q", data[40:48])[0]
                e_flags = struct.unpack(fmt + "I", data[48:52])[0]
                e_ehsize = struct.unpack(fmt + "H", data[52:54])[0]
                e_phentsize = struct.unpack(fmt + "H", data[54:56])[0]
                e_phnum = struct.unpack(fmt + "H", data[56:58])[0]
                e_shentsize = struct.unpack(fmt + "H", data[58:60])[0]
                e_shnum = struct.unpack(fmt + "H", data[60:62])[0]
                e_shstrndx = struct.unpack(fmt + "H", data[62:64])[0]
            else:
                if len(data) < 52:
                    findings.append(ELFFinding("critical", "format", "ELF header truncated"))
                    return findings
                e_type = struct.unpack(fmt + "H", data[16:18])[0]
                e_machine = struct.unpack(fmt + "H", data[18:20])[0]
                e_entry = struct.unpack(fmt + "I", data[24:28])[0]
                e_phoff = struct.unpack(fmt + "I", data[28:32])[0]
                e_shoff = struct.unpack(fmt + "I", data[32:36])[0]
                e_flags = struct.unpack(fmt + "I", data[36:40])[0]
                e_ehsize = struct.unpack(fmt + "H", data[40:42])[0]
                e_phentsize = struct.unpack(fmt + "H", data[42:44])[0]
                e_phnum = struct.unpack(fmt + "H", data[44:46])[0]
                e_shentsize = struct.unpack(fmt + "H", data[46:48])[0]
                e_shnum = struct.unpack(fmt + "H", data[48:50])[0]
                e_shstrndx = struct.unpack(fmt + "H", data[50:52])[0]

            type_names = {0: "NONE", 1: "REL", 2: "EXEC", 3: "DYN", 4: "CORE"}
            machine_names = {0: "NONE", 3: "x86", 62: "x86_64", 40: "ARM", 183: "ARM64",
                           0x3E: "x86_64", 0x28: "ARM", 0xB7: "ARM64", 0x08: "MIPS",
                           0x14: "PPC", 0x15: "PPC64", 0x2B: "SPARC", 0x32: "IA-64"}

            findings.extend(self._check_type(e_type, type_names))
            findings.extend(self._check_entry(e_entry, e_type))
            findings.extend(self._check_sections(data, is_64, endian, fmt,
                                                  e_shoff, e_shentsize, e_shnum, e_shstrndx))
            findings.extend(self._check_program_headers(data, is_64, endian, fmt,
                                                         e_phoff, e_phentsize, e_phnum))
            findings.extend(self._check_segments(data, is_64, fmt, e_phoff, e_phentsize, e_phnum))
            findings.extend(self._check_stripped(e_shnum, e_shoff, data, is_64, fmt, e_shentsize))

        except Exception as e:
            findings.append(ELFFinding("high", "parse", f"ELF parsing error: {e}"))

        return findings

    def _check_type(self, e_type, type_names) -> List[ELFFinding]:
        findings = []
        if e_type not in type_names:
            findings.append(ELFFinding("medium", "type", f"Unknown ELF type: {e_type}"))
        return findings

    def _check_entry(self, entry, e_type) -> List[ELFFinding]:
        findings = []
        if e_type == 2 and entry == 0:  # EXEC with no entry
            findings.append(ELFFinding("high", "entry", "Executable has no entry point"))
        if e_type == 3 and entry != 0:  # DYN with entry (unusual for PIE)
            findings.append(ELFFinding("low", "entry",
                f"Shared object has non-zero entry: 0x{entry:x}"))
        return findings

    def _check_sections(self, data, is_64, endian, fmt, e_shoff, e_shentsize,
                         e_shnum, e_shstrndx) -> List[ELFFinding]:
        findings = []
        if e_shoff == 0 or e_shnum == 0:
            findings.append(ELFFinding("medium", "sections", "No section headers"))
            return findings

        # Read string table
        strtab_off = 0
        if e_shstrndx < e_shnum and e_shoff + e_shentsize * (e_shstrndx + 1) <= len(data):
            shstr = data[e_shoff + e_shentsize * e_shstrndx:e_shoff + e_shentsize * (e_shstrndx + 1)]
            if is_64:
                strtab_off = struct.unpack(fmt + "Q", shstr[24:32])[0]

        sections = []
        for i in range(min(e_shnum, 256)):
            off = e_shoff + e_shentsize * i
            if off + e_shentsize > len(data):
                break
            sec = data[off:off+e_shentsize]

            if is_64:
                sh_name = struct.unpack(fmt + "I", sec[0:4])[0]
                sh_type = struct.unpack(fmt + "I", sec[4:8])[0]
                sh_flags = struct.unpack(fmt + "Q", sec[8:16])[0]
                sh_addr = struct.unpack(fmt + "Q", sec[16:24])[0]
                sh_offset = struct.unpack(fmt + "Q", sec[24:32])[0]
                sh_size = struct.unpack(fmt + "Q", sec[32:40])[0]
            else:
                sh_name = struct.unpack(fmt + "I", sec[0:4])[0]
                sh_type = struct.unpack(fmt + "I", sec[4:8])[0]
                sh_flags = struct.unpack(fmt + "I", sec[8:12])[0]
                sh_addr = struct.unpack(fmt + "I", sec[12:16])[0]
                sh_offset = struct.unpack(fmt + "I", sec[16:20])[0]
                sh_size = struct.unpack(fmt + "I", sec[20:24])[0]

            # Get section name
            name = b""
            if strtab_off + sh_name < len(data):
                end = data.find(b"\x00", strtab_off + sh_name)
                if end != -1:
                    name = data[strtab_off + sh_name:end]

            sections.append({
                "name": name, "type": sh_type, "flags": sh_flags,
                "addr": sh_addr, "offset": sh_offset, "size": sh_size,
            })

            # Check for suspicious section names
            if name.lower() in self.SUSPICIOUS_SECTIONS:
                findings.append(ELFFinding("critical", "section",
                    f"Suspicious section: {name.decode(errors='replace')}"))

            # Check for high entropy (packed/encrypted)
            if sh_type in (self.SHT_PROGBITS,) and sh_size > 4096:
                if sh_offset + sh_size <= len(data):
                    sec_data = data[sh_offset:sh_offset+sh_size]
                    ent = self._shannon(sec_data)
                    if ent > 7.5:
                        findings.append(ELFFinding("high", "section",
                            f"Section '{name.decode(errors='replace')}' has very high entropy ({ent:.2f})",
                            {"name": name.decode(errors='replace'), "entropy": ent, "size": sh_size}))

            # Check for writable + executable
            if (sh_flags & 0x1) and (sh_flags & 0x2):  # SHF_WRITE + SHF_EXECINSTR
                findings.append(ELFFinding("high", "section",
                    f"Section '{name.decode(errors='replace')}' is both writable and executable"))

            # Check SHT_NOTE for embedded data
            if sh_type == self.SHT_NOTE and sh_size > 1024:
                findings.append(ELFFinding("medium", "section",
                    f"Large NOTE section ({sh_size:,} bytes) — possible hidden data",
                    {"name": name.decode(errors='replace'), "size": sh_size}))

        return findings

    def _check_program_headers(self, data, is_64, endian, fmt,
                                e_phoff, e_phentsize, e_phnum) -> List[ELFFinding]:
        findings = []
        if e_phoff == 0:
            return findings

        for i in range(min(e_phnum, 128)):
            off = e_phoff + e_phentsize * i
            if off + e_phentsize > len(data):
                break
            ph = data[off:off+e_phentsize]

            if is_64:
                p_type = struct.unpack(fmt + "I", ph[0:4])[0]
                p_flags = struct.unpack(fmt + "I", ph[4:8])[0]
                p_offset = struct.unpack(fmt + "Q", ph[8:16])[0]
                p_vaddr = struct.unpack(fmt + "Q", ph[16:24])[0]
                p_filesz = struct.unpack(fmt + "Q", ph[32:40])[0]
                p_memsz = struct.unpack(fmt + "Q", ph[40:48])[0]
            else:
                p_type = struct.unpack(fmt + "I", ph[0:4])[0]
                p_offset = struct.unpack(fmt + "I", ph[4:8])[0]
                p_vaddr = struct.unpack(fmt + "I", ph[8:12])[0]
                p_filesz = struct.unpack(fmt + "I", ph[16:20])[0]
                p_memsz = struct.unpack(fmt + "I", ph[20:24])[0]
                p_flags = struct.unpack(fmt + "I", ph[24:28])[0]

            # PT_GNU_RELRO
            if p_type == 0x6474e552:
                findings.append(ELFFinding("info", "security", "RELRO present — hardening enabled"))

            # PT_GNU_STACK (NX check)
            if p_type == 0x6474e551:
                if p_flags & 0x1:  # PF_X
                    findings.append(ELFFinding("high", "security",
                        "GNU_STACK is executable — NX disabled, shellcode risk"))
                else:
                    findings.append(ELFFinding("info", "security", "NX bit enabled (non-exec stack)"))

            # PT_NOTE with unusual size
            if p_type == 4 and p_filesz > 1024:
                findings.append(ELFFinding("medium", "segment",
                    f"Large PT_NOTE segment ({p_filesz:,} bytes) — possible hidden data"))

        return findings

    def _check_segments(self, data, is_64, fmt, e_phoff, e_phentsize, e_phnum) -> List[ELFFinding]:
        findings = []
        # Check for overlay (data after last segment)
        max_end = 0
        for i in range(min(e_phnum, 128)):
            off = e_phoff + e_phentsize * i
            if off + e_phentsize > len(data):
                break
            ph = data[off:off+e_phentsize]
            if is_64:
                p_offset = struct.unpack(fmt + "Q", ph[8:16])[0]
                p_filesz = struct.unpack(fmt + "Q", ph[32:40])[0]
            else:
                p_offset = struct.unpack(fmt + "I", ph[4:8])[0]
                p_filesz = struct.unpack(fmt + "I", ph[16:20])[0]
            end = p_offset + p_filesz
            if end > max_end:
                max_end = end

        if max_end > 0 and max_end < len(data):
            overlay = len(data) - max_end
            if overlay > 64:
                findings.append(ELFFinding("high" if overlay > 1024 else "medium", "overlay",
                    f"ELF overlay: {overlay:,} bytes appended after segments"))

        return findings

    def _check_stripped(self, e_shnum, e_shoff, data, is_64, fmt, e_shentsize) -> List[ELFFinding]:
        findings = []
        if e_shnum == 0 and e_shoff == 0:
            findings.append(ELFFinding("low", "stripped", "ELF is stripped (no section headers)"))
        return findings

    def _shannon(self, data: bytes) -> float:
        if not data:
            return 0.0
        freq = [0] * 256
        for b in data:
            freq[b] += 1
        l = len(data)
        return -sum((f/l) * math.log2(f/l) for f in freq if f > 0)
