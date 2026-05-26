"""
Real-time folder monitoring using watchdog.
Watches configured directories (Downloads by default), auto-scans new files,
triggers quarantine + push notifications on threat detection.
"""

import os, time, logging, threading
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set
from collections import defaultdict

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

logger = logging.getLogger("polyglot_shield.monitor")


if HAS_WATCHDOG:
    class _ScanHandler(FileSystemEventHandler):
        """Handles file system events and triggers scans."""

        def __init__(self, scanner, delay: float = 1.5,
                     extensions: Optional[Set[str]] = None,
                     on_result: Optional[Callable] = None):
            super().__init__()
            self.scanner = scanner
            self.delay = delay
            self.extensions = extensions  # None = scan all
            self.on_result = on_result
            self._pending: Dict[str, float] = {}
            self._lock = threading.Lock()
            self._debounce_thread = threading.Thread(target=self._debounce_loop,
                                                      daemon=True)
            self._debounce_thread.start()

        def on_created(self, event):
            if not event.is_directory:
                self._queue(event.src_path)

        def on_modified(self, event):
            if not event.is_directory:
                self._queue(event.src_path)

        def _queue(self, path: str):
            ext = Path(path).suffix.lower()
            if self.extensions and ext not in self.extensions:
                return
            with self._lock:
                self._pending[path] = time.time() + self.delay

        def _debounce_loop(self):
            """Process queued files after debounce delay."""
            while True:
                time.sleep(0.5)
                now = time.time()
                to_scan = []
                with self._lock:
                    for path, ready_at in list(self._pending.items()):
                        if now >= ready_at:
                            to_scan.append(path)
                            del self._pending[path]
                for path in to_scan:
                    if os.path.isfile(path):
                        self._process(path)

        def _process(self, path: str):
            try:
                result = self.scanner.scan_file(path, auto_quarantine=True)
                if self.on_result:
                    self.on_result(result)
            except Exception as e:
                logger.error(f"Monitor scan failed for {path}: {e}")


class FolderMonitor:
    """Real-time folder monitor with auto-scan and quarantine."""

    def __init__(self, scanner, watch_dirs: List[str] = None,
                 recursive: bool = True, scan_delay: float = 1.5,
                 extensions: Optional[Set[str]] = None):
        if not HAS_WATCHDOG:
            raise ImportError("watchdog not installed: pip install watchdog")

        self.scanner = scanner
        self.watch_dirs = watch_dirs or [os.path.expanduser("~/Downloads")]
        self.recursive = recursive
        self.scan_delay = scan_delay
        self.extensions = extensions
        self.observer: Optional[Observer] = None
        self._running = False
        self._result_callback: Optional[Callable] = None
        self._stats = {"files_scanned": 0, "threats_found": 0, "quarantined": 0}

    def set_result_callback(self, callback: Callable):
        """Set callback for scan results: callback(scan_result)"""
        self._result_callback = callback

    def start(self):
        """Start monitoring configured directories."""
        if self._running:
            logger.warning("Monitor already running")
            return

        self.observer = Observer()
        handler = _ScanHandler(
            scanner=self.scanner,
            delay=self.scan_delay,
            extensions=self.extensions,
            on_result=self._on_result,
        )

        for watch_dir in self.watch_dirs:
            path = Path(watch_dir)
            if path.exists():
                self.observer.schedule(handler, str(path), recursive=self.recursive)
                logger.info(f"Monitoring: {path}")
            else:
                logger.warning(f"Watch directory not found: {watch_dir}")

        self.observer.start()
        self._running = True
        logger.info(f"Folder monitor started — watching {len(self.watch_dirs)} directories")

    def stop(self):
        """Stop monitoring."""
        if self.observer and self._running:
            self.observer.stop()
            self.observer.join(timeout=5)
            self._running = False
            logger.info("Folder monitor stopped")

    def _on_result(self, result):
        self._stats["files_scanned"] += 1
        if result.verdict in ("CRITICAL", "THREAT", "SUSPICIOUS"):
            self._stats["threats_found"] += 1
        if "AUTO-QUARANTINED" in str(result.evidence):
            self._stats["quarantined"] += 1
        if self._result_callback:
            try:
                self._result_callback(result)
            except Exception:
                pass

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def stats(self) -> Dict:
        return dict(self._stats)

    def add_watch_dir(self, path: str):
        """Add a new directory to watch (runtime)."""
        if not self._running or not self.observer:
            return
        p = Path(path)
        if p.exists():
            handler = _ScanHandler(
                scanner=self.scanner, delay=self.scan_delay,
                extensions=self.extensions, on_result=self._on_result,
            )
            self.observer.schedule(handler, str(p), recursive=self.recursive)
            if path not in self.watch_dirs:
                self.watch_dirs.append(path)
            logger.info(f"Added watch: {path}")
