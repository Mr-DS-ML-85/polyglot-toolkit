"""
Scanner — unified scan pipeline combining ML model + YARA rules + feature analysis.
Produces a single verdict with confidence, risk score, and full evidence chain.
"""

import os, time, logging
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

from .features import extract_features, extract_features_from_file, analyze_file, get_feature_names
from .model import PolyglotModel
from .yara_engine import YaraEngine
from .quarantine import QuarantineManager
from .notifications import NotificationManager, Alert

logger = logging.getLogger("polyglot_shield.scanner")


class ScanResult:
    """Complete scan result for a single file."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.file_size = 0
        self.entropy = 0.0
        self.detected_types: List[str] = []
        self.polyglot_markers: List[str] = []
        self.ml_label = "unknown"
        self.ml_confidence = 0.0
        self.ml_risk_score = 0.0
        self.ml_risk_level = "UNKNOWN"
        self.yara_matches: List[Dict] = []
        self.yara_max_severity = "none"
        self.yara_max_score = 0.0
        self.combined_risk = 0.0
        self.verdict = "UNKNOWN"
        self.scan_time_ms = 0.0
        self.evidence: List[str] = []

    def to_dict(self) -> Dict:
        return {
            "filepath": self.filepath,
            "filename": self.filename,
            "file_size": self.file_size,
            "entropy": round(self.entropy, 3),
            "detected_types": self.detected_types,
            "polyglot_markers": self.polyglot_markers,
            "ml_label": self.ml_label,
            "ml_confidence": self.ml_confidence,
            "ml_risk_score": self.ml_risk_score,
            "ml_risk_level": self.ml_risk_level,
            "yara_matches": self.yara_matches,
            "yara_max_severity": self.yara_max_severity,
            "combined_risk": round(self.combined_risk, 2),
            "verdict": self.verdict,
            "scan_time_ms": round(self.scan_time_ms, 2),
            "evidence": self.evidence,
        }


class Scanner:
    """Unified file scanner: ML + YARA + structural analysis."""

    def __init__(self, model: PolyglotModel, yara: YaraEngine,
                 quarantine: QuarantineManager, notifications: NotificationManager,
                 config: dict = None):
        self.model = model
        self.yara = yara
        self.quarantine = quarantine
        self.notifications = notifications
        self.config = config or {}
        self.thresholds = self.config.get("thresholds", {
            "detect": 0.65, "quarantine": 0.80, "alert": 0.50
        })

    def scan_file(self, filepath: str, auto_quarantine: bool = False) -> ScanResult:
        """Full scan of a single file. Returns ScanResult."""
        t0 = time.time()
        result = ScanResult(filepath)

        if not os.path.isfile(filepath):
            result.verdict = "ERROR"
            result.evidence.append("File not found")
            return result

        try:
            # 1. Feature extraction + structural analysis
            analysis = analyze_file(filepath, self.config.get("features", {}))
            result.file_size = analysis["size"]
            result.entropy = analysis["entropy"]
            result.detected_types = analysis["detected_types"]
            result.polyglot_markers = analysis["polyglot_markers"]

            # 2. ML prediction
            if self.model.is_loaded:
                features = analysis["features"]
                ml_result = self.model.predict_single(features)
                result.ml_label = ml_result["label"]
                result.ml_confidence = ml_result["confidence"]
                result.ml_risk_score = ml_result["risk_score"]
                result.ml_risk_level = ml_result["risk_level"]
            else:
                result.evidence.append("ML model not loaded — rule-based only")

            # 3. YARA scan
            with open(filepath, "rb") as yf:
                yara_data = yf.read()
            yara_matches = self.yara.scan(yara_data, result.entropy)
            result.yara_matches = [
                {"rule": m.rule_name, "severity": m.severity,
                 "score": m.score, "description": m.description,
                 "offset": m.offset}
                for m in yara_matches
            ]
            if yara_matches:
                result.yara_max_severity = max(yara_matches, key=lambda m: m.score).severity
                result.yara_max_score = max(m.score for m in yara_matches)

            # 4. Combined risk scoring
            ml_weight = 0.5
            yara_weight = 0.3
            struct_weight = 0.2

            ml_component = result.ml_risk_score * ml_weight
            yara_component = result.yara_max_score * 100.0 * yara_weight

            # Structural risk: multiple types or polyglot markers
            struct_risk = 0.0
            if len(result.detected_types) > 1:
                struct_risk += 30.0
            if result.polyglot_markers:
                struct_risk += 40.0
            if result.entropy > 7.5:
                struct_risk += 15.0
            struct_component = min(struct_risk, 100.0) * struct_weight

            result.combined_risk = ml_component + yara_component + struct_component

            # 5. Verdict
            if result.combined_risk >= 80:
                result.verdict = "CRITICAL"
                result.evidence.append(f"High-confidence threat (risk={result.combined_risk:.0f})")
            elif result.combined_risk >= 60:
                result.verdict = "THREAT"
                result.evidence.append(f"Likely threat (risk={result.combined_risk:.0f})")
            elif result.combined_risk >= 40:
                result.verdict = "SUSPICIOUS"
                result.evidence.append(f"Suspicious file (risk={result.combined_risk:.0f})")
            elif result.combined_risk >= 20:
                result.verdict = "LOW_RISK"
                result.evidence.append(f"Low risk (risk={result.combined_risk:.0f})")
            else:
                result.verdict = "CLEAN"

            # Evidence from polyglot markers
            for marker in result.polyglot_markers:
                result.evidence.append(f"Polyglot marker: {marker}")
            for m in result.yara_matches:
                result.evidence.append(f"YARA [{m['severity']}]: {m['rule']} — {m['description']}")

            # 6. Auto-quarantine
            if (auto_quarantine and
                    result.combined_risk >= self.thresholds.get("quarantine", 80)):
                qid = self.quarantine.quarantine(filepath, result.to_dict())
                if qid:
                    result.evidence.append(f"AUTO-QUARANTINED (id={qid})")

            # 7. Notification
            if result.combined_risk >= self.thresholds.get("alert", 50):
                self.notifications.send(Alert(
                    title=f"Threat Detected: {result.verdict}",
                    message=f"{result.filename} — Risk: {result.combined_risk:.0f}/100",
                    severity=result.verdict.lower(),
                    filepath=filepath,
                    risk_score=result.combined_risk,
                ))

        except Exception as e:
            result.verdict = "ERROR"
            result.evidence.append(f"Scan error: {str(e)}")
            logger.error(f"Scan failed for {filepath}: {e}", exc_info=True)

        result.scan_time_ms = (time.time() - t0) * 1000
        return result

    def scan_directory(self, dirpath: str, recursive: bool = True,
                       auto_quarantine: bool = False,
                       max_workers: int = 4) -> List[ScanResult]:
        """Scan all files in a directory."""
        path = Path(dirpath)
        if not path.exists():
            logger.error(f"Directory not found: {dirpath}")
            return []

        if recursive:
            files = [str(f) for f in path.rglob("*") if f.is_file()]
        else:
            files = [str(f) for f in path.iterdir() if f.is_file()]

        logger.info(f"Scanning {len(files)} files in {dirpath}")
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(self.scan_file, fp, auto_quarantine): fp
                for fp in files
            }
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    fp = futures[future]
                    logger.error(f"Failed scanning {fp}: {e}")

        threats = sum(1 for r in results if r.verdict in ("CRITICAL", "THREAT"))
        logger.info(f"Scan complete: {len(results)} files, {threats} threats found")
        return results

    def quick_check(self, filepath: str) -> Dict:
        """Quick structural check without ML (fast path)."""
        try:
            analysis = analyze_file(filepath, self.config.get("features", {}))
            yara_matches = self.yara.scan(
                open(filepath, "rb").read(), analysis["entropy"]
            )
            risk = 0.0
            if len(analysis["detected_types"]) > 1:
                risk += 40.0
            if analysis["polyglot_markers"]:
                risk += 30.0
            if yara_matches:
                risk += max(m.score for m in yara_matches) * 30.0
            return {
                "filepath": filepath,
                "is_suspicious": risk >= 30,
                "risk": min(risk, 100),
                "types": analysis["detected_types"],
                "polyglot_markers": analysis["polyglot_markers"],
                "yara_hits": len(yara_matches),
            }
        except Exception as e:
            return {"filepath": filepath, "error": str(e)}
