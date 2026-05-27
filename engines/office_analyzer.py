"""
Office macro static analysis engine.

Detects and analyzes VBA macros in Office documents:
  - OLE2 (doc/xls/ppt) compound document analysis
  - Office Open XML (docx/xlsx/pptx) macro detection
  - VBA code extraction and analysis
  - Suspicious function detection
  - Shell command detection
  - Auto-execution triggers
  - Macro obfuscation detection
  - External reference analysis
  - DDE field detection
  - Embedded object analysis

Author: Mr-DS-ML-85
"""

import struct
import zipfile
import os
import re
import hashlib
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("polyglot_shield.office")


@dataclass
class MacroFinding:
    severity: str
    category: str
    description: str
    details: Dict[str, Any] = field(default_factory=dict)
    vba_snippet: str = ""


class OfficeAnalyzer:
    """Office document macro static analyzer."""

    # Auto-execution triggers
    AUTO_TRIGGERS = {
        "autoopen", "auto_close", "autoopen", "auto_close",
        "document_open", "document_close", "document_change",
        "workbook_open", "workbook_close", "workbook_activate",
        "workbook_deactivate", "worksheet_change", "worksheet_activate",
        "autoexec", "autoload", "autonew", "auto_exit",
        "document_beforeclose", "document_open", "thisworkbook",
    }

    # Suspicious VBA functions
    SUSPICIOUS_FUNCTIONS = {
        # Shell execution
        "shell": "high", "wscript.shell": "critical", "shell.application": "critical",
        "cmd.exe": "critical", "cmd /c": "critical", "powershell": "critical",
        "createobject": "medium", "getobject": "medium",
        # File operations
        "filesystemobject": "medium", "adodb.stream": "high",
        "savefile": "medium", "savetofile": "medium", "writebinary": "medium",
        # Network
        "msxml2.xmlhttp": "high", "microsoft.xmlhttp": "high",
        "serverxmlhttp": "high", "winhttprequest": "high",
        "urldownloadtofile": "critical", "internetopen": "high",
        "inetconnect": "high",
        # Registry
        "regwrite": "high", "regread": "medium", "regdelete": "high",
        "wscript.regread": "medium", "wscript.regwrite": "high",
        # Process
        "creatprocess": "high", "win32_process": "high",
        "terminateprocess": "high",
        # Obfuscation
        "chr(" : "medium", "chr$(" : "medium", "asc(" : "low",
        "strreverse": "medium", "replace(": "low",
        "execute": "critical", "eval(": "critical",
        "exec(": "high", "executeexcel4macro": "critical",
        # Deobfuscation
        "base64": "high", "frombase64string": "critical",
        # Crypto
        "cryptencrypt": "medium", "cryptdecrypt": "medium",
    }

    # Macro obfuscation indicators
    OBFUSCATION_PATTERNS = [
        (r"chr\(\s*\d+\s*\)\s*&\s*chr\(\s*\d+\s*\)", "string_via_chr"),
        (r"strreverse\s*\(", "string_reversal"),
        (r"replace\s*\(.+,.+,.+\)", "string_replace"),
        (r"(?:&\s*\"[^\"]{1,2}\"){3,}", "single_char_concat"),
        (r"\b[a-z]\$\s*=\s*[a-z]\$\s*&", "variable_concat_loop"),
        (r"#\s*if\s+.*then", "conditional_compilation"),
        (r"environ\s*\(", "environment_variable"),
    ]

    def analyze(self, filepath: str) -> List[MacroFinding]:
        """Analyze Office document for macros and suspicious content."""
        ext = os.path.splitext(filepath)[1].lower()
        findings = []

        if ext in (".docx", ".xlsx", ".pptx", ".docm", ".xlsm", ".pptm"):
            findings.extend(self._analyze_ooxml(filepath))
        elif ext in (".doc", ".xls", ".ppt", ".msi"):
            findings.extend(self._analyze_ole2(filepath))
        elif ext in (".rtf",):
            findings.extend(self._analyze_rtf(filepath))
        else:
            # Try both
            with open(filepath, "rb") as f:
                header = f.read(8)
            if header[:4] == b"PK\x03\x04":
                findings.extend(self._analyze_ooxml(filepath))
            elif header[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
                findings.extend(self._analyze_ole2(filepath))

        return findings

    def _analyze_ooxml(self, filepath: str) -> List[MacroFinding]:
        """Analyze Office Open XML document."""
        findings = []
        try:
            with zipfile.ZipFile(filepath, "r") as zf:
                names = zf.namelist()

                # Check for VBA project
                vba_files = [n for n in names if "vbaProject" in n]
                if vba_files:
                    findings.append(MacroFinding(
                        "critical", "macro",
                        f"Document contains VBA macro project: {', '.join(vba_files)}"))

                    # Extract and analyze VBA code
                    for vba_file in vba_files:
                        try:
                            vba_data = zf.read(vba_file)
                            findings.extend(self._analyze_vba_binary(vba_data))
                        except Exception as e:
                            findings.append(MacroFinding(
                                "medium", "macro", f"Error reading {vba_file}: {e}"))

                # Check for activeX controls
                activex = [n for n in names if "activeX" in n or "ActiveX" in n]
                if activex:
                    findings.append(MacroFinding(
                        "high", "activex",
                        f"ActiveX controls found: {', '.join(activex[:5])}"))

                # Check for embedded objects
                ole_objects = [n for n in names if "oleObject" in n or "embed" in n.lower()]
                if ole_objects:
                    findings.append(MacroFinding(
                        "high", "embedded",
                        f"Embedded objects found: {', '.join(ole_objects[:5])}"))

                # Check for external relationships
                for rel_file in [n for n in names if n.endswith(".rels")]:
                    try:
                        rel_content = zf.read(rel_file).decode("utf-8", errors="replace")
                        # External links
                        externals = re.findall(r'Target="(https?://[^"]+)"', rel_content)
                        for url in externals:
                            findings.append(MacroFinding(
                                "high", "external_ref",
                                f"External URL reference: {url[:80]}"))
                        # UNC paths
                        uncs = re.findall(r'Target="(\\\\[^"]+)"', rel_content)
                        for unc in uncs:
                            findings.append(MacroFinding(
                                "critical", "external_ref",
                                f"UNC path reference: {unc[:80]}"))
                    except Exception:
                        pass

                # Check document.xml for DDE
                for xml_file in [n for n in names if "document.xml" in n.lower() or "sheet" in n.lower()]:
                    try:
                        content = zf.read(xml_file).decode("utf-8", errors="replace")
                        if "DDE" in content.upper() or "dde" in content:
                            findings.append(MacroFinding(
                                "critical", "dde", "DDE field detected in document"))
                        # Check for dynamic data exchange
                        if "\\* DDE" in content or "ddeauto" in content.lower():
                            findings.append(MacroFinding(
                                "critical", "dde", "DDE auto-update field detected"))
                    except Exception:
                        pass

        except zipfile.BadZipFile:
            findings.append(MacroFinding("medium", "format", "Invalid ZIP structure"))
        except Exception as e:
            findings.append(MacroFinding("medium", "error", f"Analysis error: {e}"))

        return findings

    def _analyze_ole2(self, filepath: str) -> List[MacroFinding]:
        """Analyze OLE2 compound document."""
        findings = []
        try:
            with open(filepath, "rb") as f:
                data = f.read()

            if len(data) < 512:
                findings.append(MacroFinding("medium", "format", "File too small for OLE2"))
                return findings

            # Check for VBA macro signatures
            vba_markers = [b"VBA_PROJECT", b"VBA_DIR", b"_VBA_PROJECT",
                          b"Module=", b"Attribute VB_", b"Auto_Open",
                          b"Document_Open", b"ThisWorkbook", b"Workbook_Open"]

            found_markers = []
            for marker in vba_markers:
                if marker in data:
                    found_markers.append(marker.decode("ascii", errors="replace"))

            if found_markers:
                findings.append(MacroFinding(
                    "critical", "macro",
                    f"VBA macro signatures found: {', '.join(found_markers[:5])}"))

                # Extract VBA code for analysis
                vba_code = self._extract_vba_from_ole2(data)
                if vba_code:
                    findings.extend(self._analyze_vba_code(vba_code))

            # Check for embedded OLE objects
            ole_count = data.count(b"\x01\x00\x00\x00")  # OLE marker
            if ole_count > 3:
                findings.append(MacroFinding(
                    "medium", "embedded", f"Multiple OLE objects ({ole_count})"))

        except Exception as e:
            findings.append(MacroFinding("medium", "error", f"OLE2 analysis error: {e}"))

        return findings

    def _analyze_rtf(self, filepath: str) -> List[MacroFinding]:
        """Analyze RTF document for exploits."""
        findings = []
        try:
            with open(filepath, "rb") as f:
                data = f.read(100000)

            text = data.decode("latin-1", errors="replace")

            # Check for embedded objects
            if "\\objdata" in text or "\\objclass" in text:
                findings.append(MacroFinding(
                    "high", "embedded", "RTF contains embedded objects"))

            # Check for OLE exploits
            if "\\objupdate" in text:
                findings.append(MacroFinding(
                    "critical", "exploit", "RTF objupdate directive (auto-update exploit)"))

            # Check for known RTF exploit patterns
            if "\\bin" in text:
                findings.append(MacroFinding(
                    "high", "exploit", "RTF \\bin directive (binary data)"))

            # Check for equation editor (CVE-2017-11882)
            if "Equation" in text or "equation" in text:
                findings.append(MacroFinding(
                    "critical", "cve", "Equation editor reference — possible CVE-2017-11882"))

        except Exception as e:
            findings.append(MacroFinding("medium", "error", f"RTF analysis error: {e}"))

        return findings

    def _analyze_vba_binary(self, data: bytes) -> List[MacroFinding]:
        """Analyze vbaProject.bin for module names and suspicious content."""
        findings = []
        # Extract ASCII strings
        strings = re.findall(b"[\\x20-\\x7e]{6,}", data)

        # Check for module names
        for s in strings:
            decoded = s.decode("ascii", errors="replace")
            lower = decoded.lower()

            # Auto-execution triggers
            if lower in self.AUTO_TRIGGERS:
                findings.append(MacroFinding(
                    "critical", "auto_exec",
                    f"Auto-execution trigger: {decoded}"))

            # Suspicious functions
            for func, sev in self.SUSPICIOUS_FUNCTIONS.items():
                if func.lower() in lower:
                    findings.append(MacroFinding(
                        sev, "suspicious_func",
                        f"Suspicious function: {decoded[:60]}",
                        {"function": func}))

        return findings

    def _extract_vba_from_ole2(self, data: bytes) -> Optional[str]:
        """Extract VBA source code from OLE2 compound document."""
        # Look for compressed VBA streams
        code_parts = []

        # Find VBA module markers
        pos = 0
        while True:
            pos = data.find(b"Attribute VB_", pos)
            if pos == -1:
                break
            # Find end of this code block
            end = data.find(b"\x00\x00\x00", pos)
            if end == -1:
                end = min(pos + 10000, len(data))
            chunk = data[pos:end]
            try:
                decoded = chunk.decode("utf-8", errors="replace")
                code_parts.append(decoded)
            except Exception:
                pass
            pos = end

        return "\n".join(code_parts) if code_parts else None

    def _analyze_vba_code(self, code: str) -> List[MacroFinding]:
        """Analyze extracted VBA code for suspicious patterns."""
        findings = []
        code_lower = code.lower()

        # Check for suspicious functions
        for func, sev in self.SUSPICIOUS_FUNCTIONS.items():
            if func.lower() in code_lower:
                # Find context
                idx = code_lower.find(func.lower())
                start = max(0, idx - 40)
                end = min(len(code), idx + len(func) + 40)
                snippet = code[start:end].replace("\n", " ").strip()
                findings.append(MacroFinding(
                    sev, "suspicious_func",
                    f"Suspicious VBA function: {func}",
                    {"function": func},
                    vba_snippet=snippet))

        # Check for obfuscation
        for pattern, name in self.OBFUSCATION_PATTERNS:
            matches = re.findall(pattern, code_lower)
            if len(matches) > 2:
                findings.append(MacroFinding(
                    "high", "obfuscation",
                    f"VBA obfuscation detected ({name}): {len(matches)} occurrences",
                    {"pattern": name, "count": len(matches)}))

        # Check for long encoded strings (base64-like)
        encoded_strings = re.findall(r'"[A-Za-z0-9+/=]{50,}"', code)
        for s in encoded_strings[:3]:
            findings.append(MacroFinding(
                "high", "encoded",
                f"Long encoded string ({len(s)} chars) — possible encoded payload",
                {"length": len(s)}))

        return findings
