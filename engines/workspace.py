"""
Workspace manager — persistent state, file snapshots, session management.

Features:
  - Persistent workspace state across refresh/restart
  - File snapshots (versioning)
  - Restore deleted files
  - Recent files
  - Pinned files
  - Drag-drop upload tracking
  - Workspace export/import
  - Session manager
  - Command chain save/load
  - Markdown notes

Author: Mr-DS-ML-85
"""

import os
import re
import json
import time
import shutil
import hashlib
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("polyglot_shield.workspace")


class WorkspaceManager:
    """Persistent workspace with file management and state persistence."""

    def __init__(self, workspace_dir: str = None):
        self.workspace_dir = workspace_dir or os.path.expanduser("~/.polyglot/workspace")
        self.state_file = os.path.join(self.workspace_dir, "state.json")
        self.snapshots_dir = os.path.join(self.workspace_dir, "snapshots")
        self.notes_dir = os.path.join(self.workspace_dir, "notes")
        self.chains_dir = os.path.join(self.workspace_dir, "chains")
        self._ensure_dirs()
        self.state = self._load_state()

    def _ensure_dirs(self):
        for d in [self.workspace_dir, self.snapshots_dir, self.notes_dir, self.chains_dir]:
            os.makedirs(d, exist_ok=True)

    def _load_state(self) -> Dict[str, Any]:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "recent_files": [],
            "pinned_files": [],
            "open_tabs": [],
            "session_id": hashlib.md5(str(time.time()).encode()).hexdigest()[:8],
            "created": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "notes": "",
            "tags": {},
            "bookmarks": [],
        }

    def save_state(self):
        """Persist workspace state to disk."""
        self.state["last_active"] = datetime.now().isoformat()
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    # ── Recent Files ────────────────────────────────────────────

    def add_recent(self, filepath: str):
        """Add file to recent list."""
        abs_path = os.path.abspath(filepath)
        recent = self.state.get("recent_files", [])
        # Remove if already exists
        recent = [r for r in recent if r["path"] != abs_path]
        # Add to front
        recent.insert(0, {
            "path": abs_path,
            "name": os.path.basename(abs_path),
            "added": datetime.now().isoformat(),
            "size": os.path.getsize(abs_path) if os.path.exists(abs_path) else 0,
        })
        self.state["recent_files"] = recent[:100]  # Keep last 100
        self.save_state()

    def get_recent(self, limit: int = 20) -> List[Dict]:
        return self.state.get("recent_files", [])[:limit]

    # ── Pinned Files ────────────────────────────────────────────

    def pin_file(self, filepath: str, note: str = ""):
        """Pin a file for quick access."""
        abs_path = os.path.abspath(filepath)
        pinned = self.state.get("pinned_files", [])
        if not any(p["path"] == abs_path for p in pinned):
            pinned.append({
                "path": abs_path,
                "name": os.path.basename(abs_path),
                "note": note,
                "pinned_at": datetime.now().isoformat(),
            })
            self.state["pinned_files"] = pinned
            self.save_state()

    def unpin_file(self, filepath: str):
        """Remove file from pinned list."""
        abs_path = os.path.abspath(filepath)
        self.state["pinned_files"] = [
            p for p in self.state.get("pinned_files", []) if p["path"] != abs_path
        ]
        self.save_state()

    def get_pinned(self) -> List[Dict]:
        return self.state.get("pinned_files", [])

    # ── File Snapshots ──────────────────────────────────────────

    def create_snapshot(self, filepath: str, label: str = "") -> Dict[str, Any]:
        """Create a snapshot (version) of a file."""
        if not os.path.exists(filepath):
            return {"error": f"File not found: {filepath}"}

        abs_path = os.path.abspath(filepath)
        file_hash = self._hash_file(abs_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = os.path.basename(filepath)
        snapshot_name = f"{fname}.{timestamp}"
        snapshot_path = os.path.join(self.snapshots_dir, snapshot_name)

        shutil.copy2(abs_path, snapshot_path)

        meta = {
            "original_path": abs_path,
            "snapshot_path": snapshot_path,
            "snapshot_name": snapshot_name,
            "file_hash": file_hash,
            "label": label,
            "timestamp": datetime.now().isoformat(),
            "size": os.path.getsize(abs_path),
        }

        # Save metadata
        meta_path = snapshot_path + ".meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        return meta

    def list_snapshots(self, filepath: str = None) -> List[Dict]:
        """List all snapshots, optionally filtered by original path."""
        snapshots = []
        for meta_file in Path(self.snapshots_dir).glob("*.meta.json"):
            try:
                with open(meta_file) as f:
                    meta = json.load(f)
                if filepath is None or meta.get("original_path") == os.path.abspath(filepath):
                    snapshots.append(meta)
            except Exception:
                pass
        return sorted(snapshots, key=lambda x: x.get("timestamp", ""), reverse=True)

    def restore_snapshot(self, snapshot_name: str) -> Dict[str, Any]:
        """Restore a file from snapshot."""
        snapshot_path = os.path.join(self.snapshots_dir, snapshot_name)
        if not os.path.exists(snapshot_path):
            return {"error": f"Snapshot not found: {snapshot_name}"}

        meta_path = snapshot_path + ".meta.json"
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            original_path = meta.get("original_path", "")
        else:
            original_path = snapshot_name.rsplit(".", 2)[0]

        # Create backup of current file before restoring
        if os.path.exists(original_path):
            backup = original_path + ".bak"
            shutil.copy2(original_path, backup)

        shutil.copy2(snapshot_path, original_path)
        return {"restored": original_path, "from_snapshot": snapshot_name}

    # ── Restore Deleted Files ───────────────────────────────────

    def track_file(self, filepath: str):
        """Track a file for potential restoration."""
        if not os.path.exists(filepath):
            return
        abs_path = os.path.abspath(filepath)
        cache_dir = os.path.join(self.workspace_dir, "file_cache")
        os.makedirs(cache_dir, exist_ok=True)

        file_hash = self._hash_file(abs_path)
        cache_path = os.path.join(cache_dir, file_hash)
        if not os.path.exists(cache_path):
            shutil.copy2(abs_path, cache_path)

        # Save mapping
        mapping_file = os.path.join(cache_dir, "mapping.json")
        mapping = {}
        if os.path.exists(mapping_file):
            with open(mapping_file) as f:
                mapping = json.load(f)
        mapping[file_hash] = {
            "original_path": abs_path,
            "cached_at": datetime.now().isoformat(),
            "size": os.path.getsize(abs_path),
        }
        with open(mapping_file, "w") as f:
            json.dump(mapping, f, indent=2)

    def restore_deleted(self, original_path: str) -> Optional[str]:
        """Attempt to restore a deleted file from cache."""
        cache_dir = os.path.join(self.workspace_dir, "file_cache")
        mapping_file = os.path.join(cache_dir, "mapping.json")
        if not os.path.exists(mapping_file):
            return None

        with open(mapping_file) as f:
            mapping = json.load(f)

        for file_hash, info in mapping.items():
            if info["original_path"] == os.path.abspath(original_path):
                cache_path = os.path.join(cache_dir, file_hash)
                if os.path.exists(cache_path):
                    shutil.copy2(cache_path, original_path)
                    return original_path
        return None

    # ── Command Chains ──────────────────────────────────────────

    def save_chain(self, name: str, commands: List[str], description: str = ""):
        """Save a command chain for replay."""
        chain = {
            "name": name,
            "description": description,
            "commands": commands,
            "created": datetime.now().isoformat(),
        }
        chain_file = os.path.join(self.chains_dir, f"{name}.json")
        with open(chain_file, "w") as f:
            json.dump(chain, f, indent=2)

    def load_chain(self, name: str) -> Optional[Dict]:
        """Load a saved command chain."""
        chain_file = os.path.join(self.chains_dir, f"{name}.json")
        if os.path.exists(chain_file):
            with open(chain_file) as f:
                return json.load(f)
        return None

    def list_chains(self) -> List[Dict]:
        """List all saved command chains."""
        chains = []
        for chain_file in Path(self.chains_dir).glob("*.json"):
            try:
                with open(chain_file) as f:
                    chain = json.load(f)
                chains.append({
                    "name": chain.get("name", chain_file.stem),
                    "description": chain.get("description", ""),
                    "commands": len(chain.get("commands", [])),
                    "created": chain.get("created", ""),
                })
            except Exception:
                pass
        return chains

    # ── Markdown Notes ──────────────────────────────────────────

    def save_note(self, name: str, content: str):
        """Save a markdown note."""
        note_file = os.path.join(self.notes_dir, f"{name}.md")
        with open(note_file, "w") as f:
            f.write(content)

    def load_note(self, name: str) -> Optional[str]:
        """Load a markdown note."""
        note_file = os.path.join(self.notes_dir, f"{name}.md")
        if os.path.exists(note_file):
            with open(note_file) as f:
                return f.read()
        return None

    def list_notes(self) -> List[Dict]:
        """List all notes."""
        notes = []
        for note_file in Path(self.notes_dir).glob("*.md"):
            try:
                stat = note_file.stat()
                with open(note_file) as f:
                    preview = f.read(200)
                notes.append({
                    "name": note_file.stem,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "preview": preview[:100],
                })
            except Exception:
                pass
        return sorted(notes, key=lambda x: x.get("modified", ""), reverse=True)

    # ── Workspace Export/Import ──────────────────────────────────

    def export_workspace(self, output_path: str) -> Dict[str, Any]:
        """Export entire workspace to a zip file."""
        import zipfile
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # State
            zf.write(self.state_file, "state.json")

            # Snapshots
            for snap in Path(self.snapshots_dir).glob("*"):
                if snap.is_file():
                    zf.write(snap, f"snapshots/{snap.name}")

            # Notes
            for note in Path(self.notes_dir).glob("*.md"):
                zf.write(note, f"notes/{note.name}")

            # Chains
            for chain in Path(self.chains_dir).glob("*.json"):
                zf.write(chain, f"chains/{chain.name}")

        size = os.path.getsize(output_path)
        return {"exported": output_path, "size": size}

    def import_workspace(self, zip_path: str) -> Dict[str, Any]:
        """Import workspace from zip file."""
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(self.workspace_dir)
        self.state = self._load_state()
        return {"imported": self.workspace_dir}

    # ── Utility ─────────────────────────────────────────────────

    def _hash_file(self, filepath: str) -> str:
        """SHA-256 hash of file content."""
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()[:16]

    def get_stats(self) -> Dict[str, Any]:
        """Get workspace statistics."""
        return {
            "recent_files": len(self.state.get("recent_files", [])),
            "pinned_files": len(self.state.get("pinned_files", [])),
            "snapshots": len(list(Path(self.snapshots_dir).glob("*.meta.json"))),
            "notes": len(list(Path(self.notes_dir).glob("*.md"))),
            "chains": len(list(Path(self.chains_dir).glob("*.json"))),
            "session_id": self.state.get("session_id", ""),
            "last_active": self.state.get("last_active", ""),
        }


# ── Session Manager ──────────────────────────────────────────────────────────

class SessionManager:
    """Manage scan sessions with full state persistence."""

    def __init__(self, sessions_dir: str = None):
        self.sessions_dir = sessions_dir or os.path.expanduser("~/.polyglot/sessions")
        os.makedirs(self.sessions_dir, exist_ok=True)

    def create_session(self, name: str = "") -> Dict[str, Any]:
        """Create a new session."""
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        session = {
            "id": session_id,
            "name": name or session_id,
            "created": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "events": [],
            "files_scanned": 0,
            "threats": 0,
            "status": "active",
        }
        self._save_session(session)
        return session

    def add_event(self, session_id: str, event: Dict[str, Any]):
        """Add event to session."""
        session = self.load_session(session_id)
        if session:
            event["timestamp"] = datetime.now().isoformat()
            session["events"].append(event)
            session["last_active"] = datetime.now().isoformat()
            self._save_session(session)

    def load_session(self, session_id: str) -> Optional[Dict]:
        """Load a session."""
        path = os.path.join(self.sessions_dir, f"{session_id}.json")
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return None

    def list_sessions(self, limit: int = 20) -> List[Dict]:
        """List recent sessions."""
        sessions = []
        for f in Path(self.sessions_dir).glob("*.json"):
            try:
                with open(f) as fh:
                    sessions.append(json.load(fh))
            except Exception:
                pass
        sessions.sort(key=lambda s: s.get("last_active", ""), reverse=True)
        return sessions[:limit]

    def close_session(self, session_id: str):
        """Close a session."""
        session = self.load_session(session_id)
        if session:
            session["status"] = "closed"
            session["closed"] = datetime.now().isoformat()
            self._save_session(session)

    def _save_session(self, session: Dict):
        path = os.path.join(self.sessions_dir, f"{session['id']}.json")
        with open(path, "w") as f:
            json.dump(session, f, indent=2)


# ── Regex Tester ─────────────────────────────────────────────────────────────

class RegexTester:
    """Quick regex testing utility."""

    def test(self, pattern: str, test_string: str) -> Dict[str, Any]:
        """Test regex pattern against string."""
        try:
            compiled = re.compile(pattern)
            matches = list(compiled.finditer(test_string))
            return {
                "pattern": pattern,
                "valid": True,
                "match_count": len(matches),
                "matches": [
                    {"text": m.group(), "start": m.start(), "end": m.end(),
                     "groups": list(m.groups())}
                    for m in matches[:20]
                ],
            }
        except re.error as e:
            return {"pattern": pattern, "valid": False, "error": str(e)}

    def replace(self, pattern: str, replacement: str,
                test_string: str) -> Dict[str, Any]:
        """Test regex replacement."""
        try:
            result = re.sub(pattern, replacement, test_string)
            return {"pattern": pattern, "replacement": replacement,
                    "result": result, "changed": result != test_string}
        except re.error as e:
            return {"pattern": pattern, "error": str(e)}
