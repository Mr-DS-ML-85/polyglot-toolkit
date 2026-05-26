"""
Auto-quarantine system.
Moves suspicious files to a secure vault with encrypted filenames,
metadata logging, restore capability, and auto-expiry.
"""

import os, json, hashlib, shutil, time, logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("polyglot_shield.quarantine")

METADATA_FILE = "metadata.jsonl"


class QuarantineManager:
    """Manages quarantined files with full audit trail."""

    def __init__(self, quarantine_dir: str = "quarantine",
                 encrypt_names: bool = True, max_size_mb: int = 500,
                 retain_days: int = 30):
        self.quarantine_dir = Path(quarantine_dir)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.meta_path = self.quarantine_dir / METADATA_FILE
        self.encrypt_names = encrypt_names
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.retain_days = retain_days

    def quarantine(self, filepath: str, scan_result: Dict) -> Optional[str]:
        """
        Move file to quarantine. Returns quarantine ID or None on failure.
        scan_result should have: label, confidence, risk_score, yara_matches, etc.
        """
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

        # Record metadata
        meta = {
            "quarantine_id": qid,
            "original_path": str(src.resolve()),
            "original_name": src.name,
            "original_size": src.stat().st_size if src.exists() else 0,
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
        """Restore a quarantined file by ID. Returns restored path."""
        meta = self._find_meta(qid)
        if not meta:
            logger.error(f"Quarantine ID not found: {qid}")
            return None

        qpath = Path(meta["quarantine_path"])
        if not qpath.exists():
            logger.error(f"Quarantine file missing: {qpath}")
            return None

        dest = Path(dest_path) if dest_path else Path(meta["original_path"])
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Avoid overwrite
        if dest.exists():
            dest = dest.with_stem(dest.stem + f"_restored_{qid[:6]}")

        shutil.move(str(qpath), str(dest))
        meta["restored"] = True
        meta["restored_to"] = str(dest)
        meta["restored_at"] = datetime.now().isoformat()
        self._update_meta(qid, meta)

        logger.info(f"Restored: {qid} → {dest}")
        return str(dest)

    def list_quarantined(self, include_restored: bool = False) -> List[Dict]:
        """List all quarantined entries."""
        entries = self._read_all_meta()
        if not include_restored:
            entries = [e for e in entries if not e.get("restored")]
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
                if ts < cutoff and not entry.get("restored"):
                    qpath = Path(entry["quarantine_path"])
                    if qpath.exists():
                        qpath.unlink()
                    entry["expired"] = True
                    self._update_meta(entry["quarantine_id"], entry)
                    purged += 1
            except Exception:
                continue
        if purged:
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

    # ── Internal helpers ──────────────────────────────────────────────────

    def _append_meta(self, meta: Dict):
        with open(self.meta_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(meta) + "\n")

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
        for entry in self._read_all_meta():
            if entry.get("quarantine_id") == qid:
                return entry
        return None

    def _update_meta(self, qid: str, updated: Dict):
        entries = self._read_all_meta()
        for i, entry in enumerate(entries):
            if entry.get("quarantine_id") == qid:
                entries[i] = updated
                break
        with open(self.meta_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

    def _current_size(self) -> int:
        return sum(f.stat().st_size for f in self.quarantine_dir.iterdir()
                   if f.is_file() and f.name != METADATA_FILE)

    def _purge_oldest(self, count: int = 10):
        entries = sorted(self._read_all_meta(),
                         key=lambda e: e.get("timestamp", ""))
        purged = 0
        for entry in entries:
            if purged >= count:
                break
            qpath = Path(entry["quarantine_path"])
            if qpath.exists():
                qpath.unlink()
                purged += 1
