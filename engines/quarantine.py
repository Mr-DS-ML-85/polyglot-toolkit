"""
Auto-quarantine system.
Moves suspicious files to a secure vault with encrypted filenames,
metadata logging, restore capability, and auto-expiry.
"""

import os, json, hashlib, shutil, time, logging, fcntl
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("polyglot_shield.quarantine")

METADATA_FILE = "metadata.jsonl"


class QuarantineManager:
    """Manages quarantined files with full audit trail."""

    # NEVER auto-quarantine below these thresholds
    MIN_CONFIDENCE = 0.80   # Must be 80%+ confident
    MIN_RISK_SCORE = 70.0   # Must be 70+ risk score
    SAFE_RISK_LEVELS = {"UNKNOWN", "LOW", "CLEAN", "SAFE", "MEDIUM"}

    def __init__(self, quarantine_dir: str = "quarantine",
                 encrypt_names: bool = True, max_size_mb: int = 500,
                 retain_days: int = 30,
                 auto_quarantine: bool = False):
        self.quarantine_dir = Path(quarantine_dir)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.meta_path = self.quarantine_dir / METADATA_FILE
        self.encrypt_names = encrypt_names
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.retain_days = retain_days
        self.auto_quarantine = auto_quarantine

    def should_quarantine(self, scan_result: Dict) -> bool:
        """Check if a scan result meets quarantine thresholds.
        NEVER quarantines files with UNKNOWN risk or zero confidence."""
        conf = scan_result.get("confidence", 0.0)
        risk = scan_result.get("risk_score", 0.0)
        level = scan_result.get("risk_level", "UNKNOWN").upper()

        # NEVER quarantine if no model loaded (UNKNOWN) or zero confidence
        if level in self.SAFE_RISK_LEVELS:
            return False
        if conf < self.MIN_CONFIDENCE:
            return False
        if risk < self.MIN_RISK_SCORE:
            return False
        return True

    def quarantine(self, filepath: str, scan_result: Dict,
                   force: bool = False) -> Optional[str]:
        """
        Move file to quarantine. Returns quarantine ID or None on failure.
        scan_result should have: label, confidence, risk_score, yara_matches, etc.
        By default, refuses to quarantine if confidence/risk is too low.
        Pass force=True to override (manual quarantine from UI).
        """
        # Safety check — don't auto-quarantine low-confidence results
        if not force and not self.should_quarantine(scan_result):
            logger.info(f"SKIP quarantine (below threshold): {filepath} "
                        f"(risk={scan_result.get('risk_level','UNKNOWN')}, "
                        f"conf={scan_result.get('confidence',0):.2f})")
            return None

        src = Path(filepath)
        if not src.exists():
            logger.warning(f"File not found: {filepath}")
            return None

        if self._current_size() > self.max_size_bytes:
            logger.warning("Quarantine vault full — purging oldest entries")
            self._purge_oldest()

        # Generate quarantine ID and masked filename
        qid = hashlib.sha256(
            f"{filepath}{time.time()}".encode()
        ).hexdigest()[:16]

        if self.encrypt_names:
            dest_name = f"{qid}.quarantine"
        else:
            dest_name = f"{qid}_{src.name}.quarantine"

        dest = self.quarantine_dir / dest_name

        try:
            shutil.move(str(src), str(dest))
        except Exception as e:
            logger.error(f"Failed to quarantine {filepath}: {e}")
            return None

        # Record metadata (read size from dest — src is gone after move)
        meta = {
            "quarantine_id": qid,
            "original_path": str(src.resolve()),
            "original_name": src.name,
            "original_size": dest.stat().st_size if dest.exists() else 0,
            "quarantine_path": str(dest.resolve()),
            "timestamp": datetime.now().isoformat(),
            "label": scan_result.get("label", "unknown"),
            "confidence": scan_result.get("confidence", 0.0),
            "risk_score": scan_result.get("risk_score", 0.0),
            "risk_level": scan_result.get("risk_level", "UNKNOWN"),
            "yara_matches": scan_result.get("yara_matches", []),
            "detected_types": scan_result.get("detected_types", []),
            "restored": False,
        }
        self._append_meta(meta)
        logger.warning(f"QUARANTINED: {src.name} → {dest_name} "
                        f"(risk={meta['risk_level']}, conf={meta['confidence']:.2f})")
        return qid

    def restore(self, qid: str, dest_path: Optional[str] = None) -> Optional[str]:
        """Restore a quarantined file by ID (supports partial/prefix match)."""
        meta = self._find_meta(qid)
        if not meta:
            logger.error(f"Quarantine ID not found: {qid}")
            return None

        full_qid = meta["quarantine_id"]

        qpath = Path(meta["quarantine_path"])
        # Fallback: search quarantine dir if stored path is missing
        if not qpath.exists():
            alt = self.quarantine_dir / f"{full_qid}.quarantine"
            if alt.exists():
                qpath = alt
            else:
                matches = list(self.quarantine_dir.glob(f"{full_qid}*"))
                if matches:
                    qpath = matches[0]
                else:
                    logger.error(f"Quarantine file missing: {qpath}")
                    return None

        dest = Path(dest_path) if dest_path else Path(meta["original_path"])
        dest.parent.mkdir(parents=True, exist_ok=True)

        if dest.exists():
            dest = dest.with_stem(dest.stem + f"_restored_{full_qid[:6]}")

        try:
            shutil.move(str(qpath), str(dest))
        except Exception as e:
            logger.error(f"Failed to restore {qid}: {e}")
            return None

        meta["restored"] = True
        meta["restored_to"] = str(dest)
        meta["restored_at"] = datetime.now().isoformat()
        self._update_meta(full_qid, meta)

        logger.info(f"Restored: {full_qid} -> {dest}")
        return str(dest)

    def list_quarantined(self, include_restored: bool = False) -> List[Dict]:
        """List all quarantined entries."""
        entries = self._read_all_meta()
        if not include_restored:
            entries = [e for e in entries if not e.get("restored")]
        # Always filter out deleted entries
        entries = [e for e in entries if not e.get("deleted")]
        return sorted(entries, key=lambda e: e.get("timestamp", ""), reverse=True)

    def delete(self, qid: str) -> bool:
        """Permanently delete a quarantined file."""
        meta = self._find_meta(qid)
        if not meta:
            return False
        qpath = Path(meta["quarantine_path"])
        if qpath.exists():
            qpath.unlink()
        self._update_meta(qid, {**meta, "deleted": True})
        logger.info(f"Permanently deleted: {qid}")
        return True

    def auto_purge_expired(self) -> int:
        """Remove entries older than retain_days. Returns count purged."""
        cutoff = datetime.now() - timedelta(days=self.retain_days)
        entries = self._read_all_meta()
        purged = 0
        for entry in entries:
            try:
                ts = datetime.fromisoformat(entry["timestamp"])
                if ts < cutoff and not entry.get("restored") and not entry.get("deleted"):
                    qpath = Path(entry["quarantine_path"])
                    if qpath.exists():
                        qpath.unlink()
                    entry["expired"] = True
                    purged += 1
            except Exception:
                continue
        # Batch write once instead of per-entry
        if purged:
            with open(self.meta_path, "w", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                for entry in entries:
                    f.write(json.dumps(entry) + "\n")
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            logger.info(f"Auto-purged {purged} expired quarantine entries")
        return purged

    def get_stats(self) -> Dict:
        entries = self._read_all_meta()
        active = [e for e in entries if not e.get("restored") and not e.get("deleted")]
        return {
            "total_entries": len(entries),
            "active_quarantine": len(active),
            "restored": sum(1 for e in entries if e.get("restored")),
            "total_size_mb": round(self._current_size() / (1024 * 1024), 2),
            "vault_path": str(self.quarantine_dir.resolve()),
        }

    def restore_all(self, dest_dir: Optional[str] = None) -> List[str]:
        """Restore ALL quarantined files. Returns list of restored paths."""
        restored = []
        entries = self.list_quarantined()
        for entry in entries:
            qid = entry["quarantine_id"]
            dest = None
            if dest_dir:
                dest = os.path.join(dest_dir, entry.get("original_name", f"restored_{qid[:8]}"))
            result = self.restore(qid, dest)
            if result:
                restored.append(result)
        return restored

    def restore_by_name(self, name_substr: str, dest_dir: Optional[str] = None) -> List[str]:
        """Restore quarantined files matching a name substring."""
        restored = []
        entries = self.list_quarantined()
        for entry in entries:
            if name_substr.lower() in entry.get("original_name", "").lower():
                qid = entry["quarantine_id"]
                dest = None
                if dest_dir:
                    dest = os.path.join(dest_dir, entry.get("original_name", f"restored_{qid[:8]}"))
                result = self.restore(qid, dest)
                if result:
                    restored.append(result)
        return restored

    # ── Internal helpers ──────────────────────────────────────────────────

    def _append_meta(self, meta: Dict):
        with open(self.meta_path, "a", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            f.write(json.dumps(meta) + "\n")
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _read_all_meta(self) -> List[Dict]:
        if not self.meta_path.exists():
            return []
        entries = []
        with open(self.meta_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries

    def _find_meta(self, qid: str) -> Optional[Dict]:
        """Find quarantine entry by ID. Supports partial/prefix matching."""
        if not qid:
            return None
        qid = qid.strip().lower()
        if not qid:
            return None
        entries = self._read_all_meta()
        # Exact match first
        for entry in entries:
            if entry.get("quarantine_id") == qid:
                return entry
        # Prefix match (for truncated IDs from UI)
        matches = [e for e in entries if e.get("quarantine_id", "").startswith(qid)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            logger.warning(f"Ambiguous quarantine ID '{qid}' — {len(matches)} matches. Use more characters.")
            return None  # Refuse to guess — user must provide more specific ID
        return None

    def _update_meta(self, qid: str, updated: Dict):
        entries = self._read_all_meta()
        for i, entry in enumerate(entries):
            eid = entry.get("quarantine_id", "")
            if eid == qid or eid.startswith(qid) or qid.startswith(eid):
                entries[i] = updated
                break
        with open(self.meta_path, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _current_size(self) -> int:
        return sum(f.stat().st_size for f in self.quarantine_dir.iterdir()
                   if f.is_file() and f.name != METADATA_FILE)

    def _purge_oldest(self, count: int = 10):
        entries = sorted(self._read_all_meta(),
                         key=lambda e: e.get("timestamp", ""))
        purged_ids = []
        for entry in entries:
            if len(purged_ids) >= count:
                break
            qpath = Path(entry["quarantine_path"])
            if qpath.exists():
                qpath.unlink()
                entry["purged"] = True
                purged_ids.append(entry.get("quarantine_id"))
        # Batch update metadata for all purged entries
        if purged_ids:
            all_entries = self._read_all_meta()
            for e in all_entries:
                if e.get("quarantine_id") in purged_ids:
                    e["purged"] = True
            with open(self.meta_path, "w", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                for entry in all_entries:
                    f.write(json.dumps(entry) + "\n")
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
