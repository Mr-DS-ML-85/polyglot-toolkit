"""
YARA-style rule engine for polyglot / malicious file detection.

Includes:
  - Built-in rule set targeting red-team polyglot payloads
  - Auto-rule generation from labeled samples
  - Scanning with severity scoring
"""

import os, re, hashlib, logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("polyglot_shield.yara")


@dataclass
class RuleMatch:
    rule_name: str
    severity: str          # critical / high / medium / low
    score: float           # 0.0 – 1.0
    description: str
    offset: int = -1
    matched_bytes: bytes = b""


@dataclass
class YaraRule:
    name: str
    severity: str
    description: str
    patterns: List[bytes] = field(default_factory=list)
    regex_patterns: List[re.Pattern] = field(default_factory=list)
    condition_fn: Optional[object] = None  # callable(data) -> bool
    min_entropy: float = 0.0
    max_entropy: float = 8.0

    def match(self, data: bytes, entropy: float) -> Optional[RuleMatch]:
        if entropy < self.min_entropy or entropy > self.max_entropy:
            return None
        if self.condition_fn and not self.condition_fn(data):
            return None
        for pat in self.patterns:
            idx = data.find(pat)
            if idx != -1:
                return RuleMatch(
                    rule_name=self.name, severity=self.severity,
                    score=_severity_score(self.severity),
                    description=self.description, offset=idx,
                    matched_bytes=pat,
                )
        for rp in self.regex_patterns:
            m = rp.search(data[:200000])
            if m:
                return RuleMatch(
                    rule_name=self.name, severity=self.severity,
                    score=_severity_score(self.severity),
                    description=self.description, offset=m.start(),
                    matched_bytes=m.group()[:64],
                )
        return None


def _severity_score(s: str) -> float:
    return {"critical": 1.0, "high": 0.8, "medium": 0.5, "low": 0.2}.get(s, 0.1)


# ── Built-in rule set ─────────────────────────────────────────────────────────

def _build_default_rules() -> List[YaraRule]:
    rules = []

    # ── CRITICAL: Polyglot header injections ──────────────────────────────
    rules.append(YaraRule(
        name="PE_In_PDF", severity="critical",
        description="PE executable embedded inside PDF (classic red-team polyglot)",
        patterns=[b"%PDF"],
        condition_fn=lambda d: b"MZ" in d and d.find(b"%PDF") < d.find(b"MZ"),
    ))
    rules.append(YaraRule(
        name="PDF_In_PE", severity="critical",
        description="PDF content injected into PE executable",
        patterns=[b"MZ"],
        condition_fn=lambda d: b"%PDF" in d and d.find(b"MZ") < d.find(b"%PDF"),
    ))
    rules.append(YaraRule(
        name="ELF_In_ZIP", severity="critical",
        description="ELF binary hidden inside ZIP archive",
        patterns=[b"PK\x03\x04"],
        condition_fn=lambda d: b"\x7fELF" in d and d.find(b"PK\x03\x04") < d.find(b"\x7fELF"),
    ))
    rules.append(YaraRule(
        name="PE_In_ZIP", severity="critical",
        description="PE executable embedded in ZIP archive",
        patterns=[b"PK\x03\x04"],
        condition_fn=lambda d: b"MZ" in d and d.find(b"PK\x03\x04") < d.find(b"MZ"),
    ))
    rules.append(YaraRule(
        name="PE_In_HTML", severity="critical",
        description="PE executable hidden in HTML document (MIME smuggling)",
        patterns=[b"<html"],
        condition_fn=lambda d: b"MZ" in d and d.lower().find(b"<html") < d.find(b"MZ"),
    ))
    rules.append(YaraRule(
        name="PDF_In_HTML", severity="critical",
        description="PDF embedded in HTML (data-URI polyglot)",
        patterns=[b"<html"],
        condition_fn=lambda d: b"%PDF" in d and d.lower().find(b"<html") < d.find(b"%PDF"),
    ))
    rules.append(YaraRule(
        name="ELF_In_PDF", severity="critical",
        description="ELF binary hidden inside PDF",
        patterns=[b"%PDF"],
        condition_fn=lambda d: b"\x7fELF" in d and d.find(b"%PDF") < d.find(b"\x7fELF"),
    ))
    rules.append(YaraRule(
        name="Script_In_PE", severity="critical",
        description="Script payload injected into PE executable",
        patterns=[b"MZ"],
        condition_fn=lambda d: any(s in d for s in [b"<script", b"<?php", b"#!/usr"]),
    ))

    # ── HIGH: Obfuscation & evasion ──────────────────────────────────────
    rules.append(YaraRule(
        name="Double_Extension", severity="high",
        description="Double file extension used to disguise file type",
        regex_patterns=[re.compile(
            rb"[\w-]+\.(exe|scr|bat|cmd|ps1|vbs|js|wsf)\.(pdf|doc|xls|txt|jpg|png)",
            re.IGNORECASE
        )],
    ))
    rules.append(YaraRule(
        name="Embedded_PE_MZ", severity="high",
        description="Secondary MZ header found after initial file header",
        condition_fn=lambda d: d.count(b"MZ") > 1,
    ))
    rules.append(YaraRule(
        name="High_Entropy_Payload", severity="high",
        description="High entropy section indicates encrypted/compressed payload",
        min_entropy=7.5,
        condition_fn=lambda d: len(d) > 1024,
    ))
    rules.append(YaraRule(
        name="Packed_Section_UPX", severity="high",
        description="UPX packing detected (common in malware)",
        patterns=[b"UPX0", b"UPX1", b"UPX!"],
    ))
    rules.append(YaraRule(
        name="Base64_PE_Payload", severity="high",
        description="Base64-encoded PE executable found in file",
        regex_patterns=[re.compile(rb"TVqQAAMAAAAEAAAA")],  # base64("MZ\x90\x00")
    ))
    rules.append(YaraRule(
        name="Hex_Encoded_PE", severity="high",
        description="Hex-encoded MZ header (obfuscation technique)",
        regex_patterns=[re.compile(rb"[0-9a-fA-F]{8,}(?:4d5a|5045)[0-9a-fA-F]{8,}")],
    ))

    # ── HIGH: Red-team toolkit signatures ─────────────────────────────────
    rules.append(YaraRule(
        name="Shellcode_NOP_Sled", severity="high",
        description="NOP sled pattern (shellcode injection)",
        condition_fn=lambda d: b"\x90" * 32 in d,
    ))
    rules.append(YaraRule(
        name="Metasploit_Pattern", severity="high",
        description="Metasploit-framework artifact detected",
        patterns=[b"meterpreter", b"reverse_tcp", b"\\x89\\xe1",
                  b"msfvenom", b"payload/"],
    ))
    rules.append(YaraRule(
        name="Cobalt_Strike_Beacon", severity="critical",
        description="Cobalt Strike beacon configuration detected",
        patterns=[b"beacon.dll", b"cobaltstrike", b"sleep_mask",
                  b"\xe2\xa0\xa0\\x89\\xe1", b"IEX"],
    ))
    rules.append(YaraRule(
        name="Invoke_Expression", severity="high",
        description="PowerShell Invoke-Expression (common in payloads)",
        regex_patterns=[re.compile(
            rb"(?i)(invoke-expression|iex\s*\(|downloadstring|"
            rb"bypass\s+-\w+policy|hidden\s+-\w+window)",
        )],
    ))
    rules.append(YaraRule(
        name="Shellcode_API_Hash", severity="high",
        description="Windows API hash pattern (shellcode technique)",
        regex_patterns=[re.compile(
            rb"(?:\\x68\\x[a-f0-9]{2}){3,4}\\xff\\xd[0-5]",
        )],
    ))

    # ── MEDIUM: Suspicious structures ─────────────────────────────────────
    rules.append(YaraRule(
        name="VBA_Macro_Stream", severity="medium",
        description="VBA macro stream detected in OLE document",
        patterns=[b"VBA_PROJECT", b"VBA_DIR", b"Module=",
                  b"Auto_Open", b"Document_Open"],
    ))
    rules.append(YaraRule(
        name="JavaScript_In_PDF", severity="medium",
        description="JavaScript action embedded in PDF",
        patterns=[b"/JavaScript", b"/JS", b"/Launch", b"/SubmitForm"],
    ))
    rules.append(YaraRule(
        name="Embedded_URL", severity="medium",
        description="HTTP/HTTPS URL found in binary (C2 callback?)",
        regex_patterns=[re.compile(rb"https?://[\w./\-:%?=&#@]+", re.IGNORECASE)],
    ))
    rules.append(YaraRule(
        name="Suspicious_Import", severity="medium",
        description="Dangerous Windows API import detected",
        regex_patterns=[re.compile(
            rb"(?:VirtualAlloc|WriteProcessMemory|CreateRemoteThread|"
            rb"NtUnmapViewOfSection|QueueUserAPC|SetWindowsHookEx)",
        )],
    ))
    rules.append(YaraRule(
        name="Null_Padded_Section", severity="medium",
        description="Large null-padded section (code cave / hidden payload)",
        condition_fn=lambda d: b"\x00" * 4096 in d,
    ))

    # ── LOW: Informational ────────────────────────────────────────────────
    rules.append(YaraRule(
        name="Archive_Nested", severity="low",
        description="Nested archive signature detected",
        condition_fn=lambda d: (
            (b"PK\x03\x04" in d and d.count(b"PK\x03\x04") > 1) or
            (b"Rar!" in d and b"PK\x03\x04" in d)
        ),
    ))
    rules.append(YaraRule(
        name="Entire_File_Encrypted", severity="low",
        description="Very high entropy throughout (encrypted / compressed)",
        min_entropy=7.8,
        condition_fn=lambda d: len(d) > 512,
    ))
    return rules


# ── Public API ────────────────────────────────────────────────────────────────

class YaraEngine:
    """YARA-style scanning engine with built-in and custom rules."""

    def __init__(self, rules_dir: str = "rules"):
        self.rules_dir = Path(rules_dir)
        self.rules: List[YaraRule] = _build_default_rules()
        self._load_custom_rules()
        logger.info(f"YaraEngine loaded {len(self.rules)} rules "
                     f"({len(_build_default_rules())} built-in)")

    def _load_custom_rules(self):
        """Load .yar/.yara rule files from rules_dir."""
        if not self.rules_dir.exists():
            return
        for rule_file in self.rules_dir.glob("*.yar"):
            self._parse_simple_rule_file(rule_file)
        for rule_file in self.rules_dir.glob("*.yara"):
            self._parse_simple_rule_file(rule_file)

    def _parse_simple_rule_file(self, path: Path):
        """Parse a simplified custom rule format:
        # RULE_NAME | severity | description
        hex_pattern
        """
        try:
            with open(path) as f:
                lines = f.readlines()
            for line in lines:
                line = line.strip()
                if line.startswith("#") and "|" in line:
                    parts = [p.strip() for p in line[1:].split("|")]
                    if len(parts) >= 3:
                        name, sev, desc = parts[0], parts[1], parts[2]
                        # Next non-empty line is hex pattern
                        idx = lines.index(line + "\n") if line + "\n" in lines else -1
                        if idx >= 0 and idx + 1 < len(lines):
                            pat_line = lines[idx + 1].strip()
                            if pat_line:
                                self.rules.append(YaraRule(
                                    name=name, severity=sev, description=desc,
                                    patterns=[pat_line.encode()],
                                ))
        except Exception as e:
            logger.warning(f"Failed to parse rule file {path}: {e}")

    def scan(self, data: bytes, entropy: float = 0.0) -> List[RuleMatch]:
        """Scan raw bytes against all rules. Returns list of matches."""
        matches = []
        for rule in self.rules:
            m = rule.match(data, entropy)
            if m is not None:
                matches.append(m)
        return matches

    def scan_file(self, path: str) -> Tuple[List[RuleMatch], float]:
        """Scan a file, return (matches, entropy)."""
        with open(path, "rb") as f:
            data = f.read()
        from .features import _shannon
        ent = _shannon(data)
        return self.scan(data, ent), ent

    def generate_rules_from_samples(self, samples: List[Tuple[str, int]]):
        """
        Auto-generate byte-pattern rules from labeled samples.
        samples: list of (filepath, label) where label 1 = malicious.
        """
        logger.info(f"Auto-generating rules from {len(samples)} samples...")
        mal_sigs = []
        for path, label in samples:
            if label != 1:
                continue
            try:
                with open(path, "rb") as f:
                    data = f.read()
                # Extract unique byte sequences from first 1KB
                for offset in range(0, min(len(data) - 4, 1024), 64):
                    chunk = data[offset:offset + 8]
                    if chunk not in mal_sigs and chunk != b"\x00" * 8:
                        mal_sigs.append(chunk)
            except Exception:
                continue

        # Create rules from top signatures
        for i, sig in enumerate(mal_sigs[:50]):
            self.rules.append(YaraRule(
                name=f"AutoRule_{i:03d}", severity="medium",
                description=f"Auto-generated signature from malicious sample",
                patterns=[sig],
            ))
        logger.info(f"Generated {min(len(mal_sigs), 50)} auto-rules")

    @property
    def rule_count(self) -> int:
        return len(self.rules)

    def get_rules_summary(self) -> List[Dict]:
        return [{"name": r.name, "severity": r.severity,
                 "description": r.description} for r in self.rules]
