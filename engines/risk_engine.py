"""
Risk scoring engine + Markdown/PDF reporting.

Features:
  - Multi-factor risk scoring (entropy, format anomalies, YARA hits, ML confidence)
  - Attack chain analysis
  - Credential chain detection
  - Vulnerability correlation
  - Attack chain replay
  - Markdown report generation
  - PDF report generation (via markdown -> HTML -> PDF or weasyprint)

Author: Mr-DS-ML-85
"""

import os
import re
import json
import time
import math
import hashlib
import logging
import subprocess
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("polyglot_shield.risk")


@dataclass
class RiskScore:
    total: float  # 0-100
    category: str  # critical/high/medium/low/info
    factors: Dict[str, float] = field(default_factory=dict)
    details: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class RiskScoringEngine:
    """Multi-factor risk scoring for files and payloads."""

    # Weight factors
    WEIGHTS = {
        "entropy": 15,
        "format_anomaly": 20,
        "yara_hits": 25,
        "ml_confidence": 20,
        "stego_indicators": 10,
        "archive_depth": 5,
        "obfuscation": 5,
    }

    def score_file(self, file_path: str, scan_results: Dict[str, Any]) -> RiskScore:
        """Calculate comprehensive risk score for a file."""
        factors = {}
        details = []
        recommendations = []

        # 1. Entropy analysis
        entropy = self._calc_file_entropy(file_path)
        if entropy > 7.5:
            factors["entropy"] = 1.0
            details.append(f"Very high entropy ({entropy:.2f}) — likely encrypted/compressed")
        elif entropy > 6.5:
            factors["entropy"] = 0.6
            details.append(f"High entropy ({entropy:.2f}) — possibly packed")
        elif entropy > 5.0:
            factors["entropy"] = 0.3
            details.append(f"Moderate entropy ({entropy:.2f})")
        else:
            factors["entropy"] = 0.0

        # 2. Format anomalies
        format_score = 0.0
        if scan_results.get("format_mismatches"):
            format_score = min(len(scan_results["format_mismatches"]) * 0.3, 1.0)
            details.append(f"{len(scan_results['format_mismatches'])} format mismatches detected")
        factors["format_anomaly"] = format_score

        # 3. YARA hits
        yara_hits = scan_results.get("yara_matches", [])
        if yara_hits:
            yara_score = min(len(yara_hits) * 0.2, 1.0)
            factors["yara_hits"] = yara_score
            for hit in yara_hits[:5]:
                details.append(f"YARA match: {hit.get('rule', 'unknown')}")
        else:
            factors["yara_hits"] = 0.0

        # 4. ML confidence
        ml_conf = scan_results.get("ml_confidence", 0.0)
        ml_pred = scan_results.get("ml_prediction", "unknown")
        factors["ml_confidence"] = ml_conf if ml_pred == "malicious" else 0.0
        if ml_pred == "malicious" and ml_conf > 0.8:
            details.append(f"ML model: {ml_pred} ({ml_conf:.1%} confidence)")

        # 5. Steganography indicators
        stego_findings = scan_results.get("stego_findings", [])
        if stego_findings:
            stego_score = min(len(stego_findings) * 0.25, 1.0)
            factors["stego_indicators"] = stego_score
            details.append(f"{len(stego_findings)} steganography indicators")
        else:
            factors["stego_indicators"] = 0.0

        # 6. Archive depth
        archive_depth = scan_results.get("archive_depth", 0)
        if archive_depth > 3:
            factors["archive_depth"] = 1.0
            details.append(f"Deeply nested archives (depth {archive_depth})")
        elif archive_depth > 1:
            factors["archive_depth"] = 0.5
        else:
            factors["archive_depth"] = 0.0

        # 7. Obfuscation
        obfuscation = scan_results.get("obfuscation_score", 0.0)
        factors["obfuscation"] = min(obfuscation, 1.0)

        # Calculate weighted total
        total = sum(factors.get(k, 0) * w for k, w in self.WEIGHTS.items())
        total = min(round(total, 1), 100.0)

        # Determine category
        if total >= 75:
            category = "critical"
            recommendations.append("IMMEDIATE ACTION: Quarantine file")
            recommendations.append("Run in isolated environment before processing")
        elif total >= 50:
            category = "high"
            recommendations.append("Sanitize file before use")
            recommendations.append("Verify file provenance")
        elif total >= 25:
            category = "medium"
            recommendations.append("Monitor file behavior")
            recommendations.append("Consider additional scanning")
        elif total >= 10:
            category = "low"
            recommendations.append("File appears low risk")
        else:
            category = "info"
            recommendations.append("No significant risk indicators")

        return RiskScore(
            total=total,
            category=category,
            factors=factors,
            details=details,
            recommendations=recommendations,
        )

    def _calc_file_entropy(self, filepath: str) -> float:
        """Calculate Shannon entropy of a file."""
        try:
            with open(filepath, "rb") as f:
                data = f.read()
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
        except Exception:
            return 0.0

    def score_payload(self, code: str, language: str) -> RiskScore:
        """Score a payload's detection risk."""
        factors = {}
        details = []

        code_lower = code.lower()

        # Keyword density
        danger_kw = {
            "powershell": ["invoke-expression", "iex", "downloadstring", "bypass",
                          "amsi", "mimikatz", "shellcode", "-enc"],
            "vba": ["shell", "createobject", "auto_open", "virtualalloc", "kernel32"],
            "javascript": ["eval(", "atob(", "activexobject", "wscript.shell"],
        }
        keywords = danger_kw.get(language, [])
        kw_hits = sum(1 for kw in keywords if kw in code_lower)
        factors["keyword_density"] = min(kw_hits * 0.15, 1.0)
        if kw_hits > 3:
            details.append(f"High keyword density: {kw_hits} dangerous keywords found")

        # Entropy
        entropy = self._calc_entropy_str(code)
        factors["entropy"] = min(entropy / 8.0, 1.0)
        if entropy > 5.5:
            details.append(f"High string entropy ({entropy:.2f}) — possible obfuscation")

        # Base64 patterns
        b64_matches = re.findall(r'[A-Za-z0-9+/]{20,}={0,2}', code)
        if b64_matches:
            factors["base64_presence"] = min(len(b64_matches) * 0.2, 1.0)
            details.append(f"{len(b64_matches)} base64 strings found")

        # Known evasion indicators
        evasion_kw = ["sandbox", "vmware", "virtualbox", "sleep", "delay", "wscript.sleep"]
        evasion_hits = sum(1 for kw in evasion_kw if kw in code_lower)
        factors["evasion_techniques"] = min(evasion_hits * 0.2, 1.0)

        # Calculate total
        total = sum(factors.values()) / max(len(factors), 1) * 100
        total = min(round(total, 1), 100.0)

        if total >= 75:
            category = "critical"
        elif total >= 50:
            category = "high"
        elif total >= 25:
            category = "medium"
        else:
            category = "low"

        return RiskScore(total=total, category=category, factors=factors, details=details)

    def _calc_entropy_str(self, data: str) -> float:
        """Shannon entropy for strings."""
        if not data:
            return 0.0
        freq = {}
        for c in data:
            freq[c] = freq.get(c, 0) + 1
        length = len(data)
        return -sum((count/length) * math.log2(count/length) for count in freq.values())


# ── Vulnerability Correlation ────────────────────────────────────────────────

class VulnCorrelator:
    """Correlate findings with known vulnerability patterns."""

    VULN_PATTERNS = {
        "CVE-2017-0144": {
            "name": "EternalBlue",
            "patterns": [b"\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00SMB"],
            "severity": "critical",
            "description": "SMBv1 remote code execution",
        },
        "CVE-2021-44228": {
            "name": "Log4Shell",
            "patterns": [b"${jndi:", b"${${", b"${lower:"],
            "severity": "critical",
            "description": "Log4j JNDI injection RCE",
        },
        "CVE-2017-11882": {
            "name": "Equation Editor RCE",
            "patterns": [b"\\x1c\\x00\\x00\\x00", b"Equation.3"],
            "severity": "critical",
            "description": "Microsoft Office Equation Editor stack buffer overflow",
        },
        "CVE-2023-36884": {
            "name": "Office/Windows HTML RCE",
            "patterns": [b"ms-msdt:", b"search:", b"ms-office:"],
            "severity": "critical",
            "description": "HTML RCE via Office documents",
        },
        "CVE-2022-30190": {
            "name": "Follina",
            "patterns": [b"ms-msdt:", b"PCWDiagnostic"],
            "severity": "critical",
            "description": "Microsoft Office MSDT RCE",
        },
        "Macro-based": {
            "name": "VBA Macro Execution",
            "patterns": [b"Auto_Open", b"Document_Open", b"Workbook_Open",
                        b"Shell(", b"WScript.Shell"],
            "severity": "high",
            "description": "Office document with VBA macros",
        },
        "DDE": {
            "name": "DDE Injection",
            "patterns": [b"DDEAUTO", b"DDE ", b"cmd.exe"],
            "severity": "high",
            "description": "Dynamic Data Exchange injection in Office docs",
        },
        "Template Injection": {
            "name": "Template Injection",
            "patterns": [b"word/_rels/settings.xml.rels", b"TargetMode=\"External\""],
            "severity": "high",
            "description": "Office template injection for remote code loading",
        },
    }

    def correlate(self, file_data: bytes) -> List[Dict[str, Any]]:
        """Scan file data for vulnerability patterns."""
        findings = []
        for cve, info in self.VULN_PATTERNS.items():
            for pattern in info["patterns"]:
                if pattern in file_data:
                    findings.append({
                        "cve": cve,
                        "name": info["name"],
                        "severity": info["severity"],
                        "description": info["description"],
                        "matched_pattern": pattern.decode("latin-1", errors="replace")[:50],
                    })
                    break
        return findings


# ── Credential Chain Analysis ────────────────────────────────────────────────

class CredentialChainAnalyzer:
    """Detect credential harvesting patterns in files."""

    CRED_PATTERNS = {
        "password_in_file": [
            rb"password\s*[:=]\s*['\"]?(\S+)",
            rb"passwd\s*[:=]\s*['\"]?(\S+)",
            rb"pwd\s*[:=]\s*['\"]?(\S+)",
            rb"secret\s*[:=]\s*['\"]?(\S+)",
            rb"api[_-]?key\s*[:=]\s*['\"]?(\S+)",
            rb"token\s*[:=]\s*['\"]?(\S+)",
        ],
        "hardcoded_creds": [
            rb"Basic [A-Za-z0-9+/]{20,}={0,2}",
            rb"Bearer [A-Za-z0-9_-]+\.?",
            rb"Authorization:\s*\S+",
        ],
        "aws_creds": [
            rb"AKIA[0-9A-Z]{16}",
            rb"aws_secret_access_key\s*=\s*(\S+)",
        ],
        "private_keys": [
            rb"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
            rb"-----BEGIN PGP PRIVATE KEY BLOCK-----",
        ],
        "connection_strings": [
            rb"Server=\S+;Database=\S+;User Id=\S+;Password=\S+",
            rb"mongodb(\+srv)?://\S+:\S+@\S+",
            rb"redis://\S+:\S+@\S+",
        ],
    }

    def analyze(self, file_data: bytes) -> List[Dict[str, Any]]:
        """Analyze file for credential patterns."""
        findings = []
        for category, patterns in self.CRED_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, file_data, re.IGNORECASE)
                if matches:
                    for match in matches[:5]:  # Limit
                        value = match if isinstance(match, str) else match.decode("latin-1", errors="replace")
                        # Mask sensitive values
                        masked = value[:4] + "****" if len(value) > 4 else "****"
                        findings.append({
                            "category": category,
                            "severity": "critical" if category in ("private_keys", "aws_creds") else "high",
                            "masked_value": masked,
                            "position": file_data.find(match if isinstance(match, bytes) else match.encode()),
                        })
        return findings


# ── Attack Chain Analysis ────────────────────────────────────────────────────

class AttackChainAnalyzer:
    """Analyze and replay attack chains from scan results."""

    CHAIN_STAGES = [
        "delivery",      # How the payload reaches the target
        "execution",     # How the payload executes
        "persistence",   # How it maintains access
        "privilege_escalation",  # How it elevates privileges
        "defense_evasion",       # How it avoids detection
        "credential_access",     # How it steals credentials
        "lateral_movement",      # How it spreads
        "exfiltration",          # How data leaves the network
    ]

    def analyze_chain(self, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Map findings to MITRE ATT&CK-style chain."""
        chain = {stage: [] for stage in self.CHAIN_STAGES}

        for finding in findings:
            detail = finding.get("detail", "").lower()
            ftype = finding.get("type", "").lower()

            # Map to chain stages
            if any(k in detail for k in ["macro", "dde", "template injection", "phishing"]):
                chain["delivery"].append(finding)
            if any(k in detail for k in ["shell", "execute", "cmd", "powershell", "runcalc"]):
                chain["execution"].append(finding)
            if any(k in detail for k in ["registry", "scheduled", "startup", "persistence"]):
                chain["persistence"].append(finding)
            if any(k in detail for k in ["uac", "bypass", "token", "privilege"]):
                chain["privilege_escalation"].append(finding)
            if any(k in detail for k in ["obfuscate", "encrypt", "stego", "evasion", "amsi"]):
                chain["defense_evasion"].append(finding)
            if any(k in detail for k in ["credential", "password", "key", "hash"]):
                chain["credential_access"].append(finding)
            if any(k in detail for k in ["network", "beacon", "download", "webclient"]):
                chain["lateral_movement"].append(finding)
            if any(k in detail for k in ["exfil", "upload", "post", "send"]):
                chain["exfiltration"].append(finding)

        # Remove empty stages
        chain = {k: v for k, v in chain.items() if v}

        return {
            "chain": chain,
            "stages_activated": len(chain),
            "total_activities": sum(len(v) for v in chain.values()),
            "mitre_mapping": self._map_to_mitre(chain),
        }

    def _map_to_mitre(self, chain: Dict[str, list]) -> Dict[str, str]:
        """Map chain stages to MITRE ATT&CK techniques."""
        mapping = {
            "delivery": "T1566 (Phishing), T1195 (Supply Chain)",
            "execution": "T1059 (Command & Scripting), T1204 (User Execution)",
            "persistence": "T1547 (Boot/Logon Autostart), T1053 (Scheduled Task)",
            "privilege_escalation": "T1548 (Abuse Elevation), T1134 (Token Manipulation)",
            "defense_evasion": "T1027 (Obfuscated Files), T1140 (Deobfuscate)",
            "credential_access": "T1003 (OS Credential Dumping), T1555 (Password Stores)",
            "lateral_movement": "T1021 (Remote Services), T1570 (Lateral Tool Transfer)",
            "exfiltration": "T1048 (Exfiltration Over C2), T1567 (Exfil Over Web)",
        }
        return {stage: mapping.get(stage, "") for stage in chain}


# ── Report Generator ─────────────────────────────────────────────────────────

class ReportGenerator:
    """Generate Markdown and PDF reports."""

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or os.path.expanduser("~/.polyglot/reports")
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_markdown(self, scan_results: Dict[str, Any],
                         risk_score: RiskScore = None,
                         chain_analysis: Dict[str, Any] = None,
                         vuln_findings: List[Dict] = None,
                         cred_findings: List[Dict] = None) -> str:
        """Generate comprehensive Markdown report."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report = []

        report.append("# PolyglotShield Security Report")
        report.append(f"**Generated:** {timestamp}")
        report.append(f"**Tool:** PolyglotShield v3.0")
        report.append("")

        # Risk Score
        if risk_score:
            report.append("## Risk Assessment")
            report.append(f"**Overall Score:** {risk_score.total}/100 ({risk_score.category.upper()})")
            report.append("")
            report.append("### Score Breakdown")
            for factor, value in sorted(risk_score.factors.items(), key=lambda x: -x[1]):
                bar = "█" * int(value * 10) + "░" * (10 - int(value * 10))
                report.append(f"- **{factor}:** {bar} {value:.0%}")
            report.append("")

            if risk_score.details:
                report.append("### Findings")
                for detail in risk_score.details:
                    report.append(f"- {detail}")
                report.append("")

            if risk_score.recommendations:
                report.append("### Recommendations")
                for rec in risk_score.recommendations:
                    report.append(f"- {rec}")
                report.append("")

        # Vulnerability Correlation
        if vuln_findings:
            report.append("## Vulnerability Correlation")
            for vuln in vuln_findings:
                icon = "🔴" if vuln["severity"] == "critical" else "🟡"
                report.append(f"- {icon} **{vuln['cve']}** ({vuln['name']}): {vuln['description']}")
            report.append("")

        # Credential Analysis
        if cred_findings:
            report.append("## Credential Analysis")
            for cred in cred_findings:
                report.append(f"- ⚠️ **{cred['category']}**: {cred['masked_value']}")
            report.append("")

        # Attack Chain
        if chain_analysis and chain_analysis.get("chain"):
            report.append("## Attack Chain Analysis")
            report.append(f"**Stages Activated:** {chain_analysis['stages_activated']}")
            report.append(f"**Total Activities:** {chain_analysis['total_activities']}")
            report.append("")
            for stage, activities in chain_analysis["chain"].items():
                report.append(f"### {stage.replace('_', ' ').title()}")
                for act in activities[:5]:
                    report.append(f"- {act.get('detail', 'Unknown')}")
                mitre = chain_analysis.get("mitre_mapping", {}).get(stage, "")
                if mitre:
                    report.append(f"  - *MITRE: {mitre}*")
                report.append("")

        # Scan Details
        report.append("## Scan Details")
        report.append(f"- Files scanned: {scan_results.get('files_scanned', 'N/A')}")
        report.append(f"- Threats found: {scan_results.get('threats', 0)}")
        report.append(f"- Scan duration: {scan_results.get('duration', 'N/A')}s")
        report.append("")

        report.append("---")
        report.append("*Report generated by PolyglotShield v3.0 — Mr-DS-ML-85*")

        content = "\n".join(report)

        # Save
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w") as f:
            f.write(content)

        return filepath

    def generate_pdf(self, markdown_path: str) -> Optional[str]:
        """Convert markdown report to PDF."""
        try:
            # Try using pandoc
            pdf_path = markdown_path.replace(".md", ".pdf")
            result = subprocess.run(
                ["pandoc", markdown_path, "-o", pdf_path, "--pdf-engine=xelatex",
                 "-V", "geometry:margin=1in", "-V", "monofont=DejaVu Sans Mono"],
                capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and os.path.exists(pdf_path):
                return pdf_path
        except Exception:
            pass

        try:
            # Fallback: markdown -> HTML -> use wkhtmltopdf or similar
            with open(markdown_path) as f:
                md_content = f.read()

            # Simple markdown to HTML conversion
            html = self._md_to_html(md_content)
            html_path = markdown_path.replace(".md", ".html")
            pdf_path = markdown_path.replace(".md", ".pdf")

            with open(html_path, "w") as f:
                f.write(html)

            # Try wkhtmltopdf
            result = subprocess.run(
                ["wkhtmltopdf", "--enable-local-file-access", html_path, pdf_path],
                capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and os.path.exists(pdf_path):
                os.remove(html_path)
                return pdf_path

            return html_path  # Return HTML if PDF conversion fails

        except Exception as e:
            logger.warning(f"PDF generation failed: {e}")
            return None

    def _md_to_html(self, md: str) -> str:
        """Minimal markdown to HTML."""
        html = md
        # Headers
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        # Bold
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        # Italic
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        # Lists
        html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        # HR
        html = re.sub(r'^---$', r'<hr>', html, flags=re.MULTILINE)
        # Line breaks
        html = html.replace('\n\n', '</p><p>')

        return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>PolyglotShield Report</title>
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; }}
h1 {{ color: #c0392b; border-bottom: 2px solid #c0392b; }}
h2 {{ color: #2c3e50; }}
h3 {{ color: #34495e; }}
li {{ margin: 4px 0; }}
hr {{ border: 1px solid #bdc3c7; }}
strong {{ color: #e74c3c; }}
</style>
</head><body><p>{html}</p></body></html>"""
