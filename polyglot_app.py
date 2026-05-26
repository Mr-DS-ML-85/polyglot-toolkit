#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║  POLYGLOT TOOLKIT — Red Team Edition                     ║
║  Builder + Detector + Sanitizer + Real-Time Monitor      ║
║  Author: Mr-DS-ML-85                                     ║
╚══════════════════════════════════════════════════════════╝
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import time
import os
import json
import struct
import zlib
import math
import hashlib
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from collections import deque

# ── Notification System ────────────────────────────────────

class Notifier:
    """Cross-platform desktop notifications."""

    @staticmethod
    def send(title, message, urgency="normal"):
        """Send desktop notification."""
        try:
            subprocess.run([
                "notify-send", "-u", urgency, "-a", "Polyglot Toolkit",
                "-i", "dialog-warning" if urgency == "critical" else "dialog-information",
                title, message
            ], capture_output=True, timeout=5)
        except Exception:
            pass  # Silently fail if notify-send not available

    @staticmethod
    def play_alert():
        """Play alert sound."""
        try:
            subprocess.run(["paplay", "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"],
                         capture_output=True, timeout=3)
        except Exception:
            pass


# ── Polyglot Builder ───────────────────────────────────────

class PolyglotBuilder:
    """Constructs polyglot files — valid container + hidden payload."""

    JPEG_SOI = b'\xff\xd8'
    JPEG_EOI = b'\xff\xd9'
    PNG_SIG = b'\x89PNG\r\n\x1a\n'
    PNG_IEND = b'\x00\x00\x00\x00IEND\xaeB`\x82'
    GIF89A = b'GIF89a'

    def __init__(self):
        self.last_stats = {}

    def _entropy(self, data: bytes) -> float:
        if not data:
            return 0.0
        freq = [0] * 256
        for b in data:
            freq[b] += 1
        length = len(data)
        ent = 0.0
        for f in freq:
            if f > 0:
                p = f / length
                ent -= p * math.log2(p)
        return ent

    def _build_jpeg_payload(self, cover: bytes, payload: bytes) -> bytes:
        """JPEG polyglot — payload after EOI marker."""
        if cover[:2] != self.JPEG_SOI:
            raise ValueError("Not a valid JPEG file")
        end = cover.rfind(self.JPEG_EOI)
        if end == -1:
            raise ValueError("JPEG EOI marker not found")
        return cover[:end + 2] + b'\n' + payload

    def _build_png_payload(self, cover: bytes, payload: bytes) -> bytes:
        """PNG polyglot — payload hidden after IEND chunk."""
        if cover[:8] != self.PNG_SIG:
            raise ValueError("Not a valid PNG file")
        iend = cover.rfind(b'IEND')
        if iend == -1:
            raise ValueError("IEND chunk not found")
        end_pos = iend + 8  # IEND chunk type + CRC
        return cover[:end_pos] + payload

    def _build_gif_payload(self, cover: bytes, payload: bytes) -> bytes:
        """GIF polyglot — payload after GIF terminator (0x3B)."""
        if cover[:6] not in (b'GIF87a', b'GIF89a'):
            raise ValueError("Not a valid GIF file")
        term = cover.rfind(b'\x3b')
        if term == -1:
            raise ValueError("GIF terminator not found")
        return cover[:term + 1] + b'\x00' * 8 + payload

    def _build_pdf_payload(self, cover: bytes, payload: bytes) -> bytes:
        """PDF polyglot — payload after %%EOF marker."""
        if not cover.startswith(b'%PDF'):
            raise ValueError("Not a valid PDF file")
        eof = cover.rfind(b'%%EOF')
        if eof == -1:
            raise ValueError("PDF %%EOF marker not found")
        return cover[:eof + 5] + b'\r\n' + payload

    def _build_zip_payload(self, cover: bytes, payload: bytes) -> bytes:
        """ZIP polyglot — payload before central directory."""
        if cover[:2] not in (b'PK', b'\x50\x4b'):
            raise ValueError("Not a valid ZIP file")
        eocd_sig = b'\x50\x4b\x05\x06'
        eocd_pos = cover.rfind(eocd_sig)
        if eocd_pos == -1:
            raise ValueError("ZIP end of central directory not found")
        return cover[:eocd_pos] + payload + cover[eocd_pos:]

    def build(self, cover_path: str, payload_path: str, output_path: str,
              container_type: str = "jpeg", encrypt: bool = False) -> dict:
        """Build a polyglot file. Returns stats dict."""
        with open(cover_path, 'rb') as f:
            cover = f.read()
        with open(payload_path, 'rb') as f:
            payload = f.read()

        if encrypt:
            key = os.urandom(32)
            payload = bytes(a ^ b for a, b in zip(payload, (key * (len(payload) // len(key) + 1))[:len(payload)]))

        builders = {
            'jpeg': self._build_jpeg_payload,
            'png': self._build_png_payload,
            'gif': self._build_gif_payload,
            'pdf': self._build_pdf_payload,
            'zip': self._build_zip_payload,
        }

        builder = builders.get(container_type.lower())
        if not builder:
            raise ValueError(f"Unknown container type: {container_type}")

        polyglot = builder(cover, payload)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(polyglot)

        payload_offset = len(polyglot) - len(payload)

        self.last_stats = {
            'output': output_path,
            'container_type': container_type.upper(),
            'cover_size': len(cover),
            'payload_size': len(payload),
            'output_size': len(polyglot),
            'payload_offset': payload_offset,
            'encrypted': encrypt,
            'entropy': round(self._entropy(payload), 2),
        }
        return self.last_stats


# ── Polyglot Detector ──────────────────────────────────────

class PolyglotDetector:
    """Scans files for hidden payloads and polyglot markers."""

    def __init__(self):
        self.signatures = {
            'PE/EXE': b'MZ',
            'ELF': b'\x7fELF',
            'PDF': b'%PDF',
            'ZIP': b'PK',
            'RAR': b'Rar!',
            '7Z': b'7z',
            'GZIP': b'\x1f\x8b',
            'BZ2': b'BZh',
            'BAT': b'@echo',
            'PS1': b'powershell',
            'SH': b'#!/bin/',
            'CLASS': b'\xca\xfe\xba\xbe',
            'MACHO': b'\xfe\xed\xfa',
            'JAVASCRIPT': b'function(',
            'VBS': b'CreateObject',
            'REG': b'Windows Registry',
            'LNK': b'\x4c\x00\x00\x00',
        }

        self.markers = {
            'JPEG_EOI': (b'\xff\xd9', 'JPEG end marker — payload may follow'),
            'PNG_IEND': (b'IEND', 'PNG end marker — payload may follow'),
            'GIF_TERM': (b'\x3b', 'GIF terminator — payload may follow'),
            'PDF_EOF': (b'%%EOF', 'PDF end marker — payload may follow'),
            'SCRIPT_TAG': (b'<script', 'Embedded script tag'),
            'HTA_TAG': (b'<hta:', 'HTA application tag'),
            'POWERSHELL': (b'powershell', 'PowerShell reference'),
            'CMD_EXE': (b'cmd.exe', 'Command execution reference'),
            'BASE64': (b'base64', 'Base64 encoding reference'),
        }

    def scan_file(self, filepath: str) -> list:
        """Scan a single file. Returns list of findings."""
        findings = []
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
        except Exception as e:
            return [{'type': 'ERROR', 'detail': str(e), 'severity': 'error'}]

        fname = os.path.basename(filepath)
        ext = os.path.splitext(fname)[1].lower()

        # --- Extension vs content mismatch ---
        ext_types = {
            '.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.gif': 'GIF',
            '.bmp': 'BMP', '.pdf': 'PDF', '.doc': 'OLE', '.docx': 'ZIP',
        }
        content_type = None
        if data[:2] == b'\xff\xd8':
            content_type = 'JPEG'
        elif data[:8] == b'\x89PNG\r\n\x1a\n':
            content_type = 'PNG'
        elif data[:6] in (b'GIF87a', b'GIF89a'):
            content_type = 'GIF'
        elif data[:4] == b'%PDF':
            content_type = 'PDF'
        elif data[:2] == b'PK':
            content_type = 'ZIP'

        expected_type = ext_types.get(ext)
        if expected_type and content_type and expected_type != content_type:
            findings.append({
                'type': 'EXTENSION_MISMATCH',
                'detail': f'Extension says {expected_type}, content says {content_type}',
                'severity': 'critical',
                'offset': 0
            })

        # --- Scan for hidden signatures (skip first 64 bytes for cover sigs) ---
        for sig_name, sig_bytes in self.signatures.items():
            offset = data.find(sig_bytes, 64)
            if offset != -1:
                findings.append({
                    'type': 'HIDDEN_SIGNATURE',
                    'detail': f'{sig_name} signature at offset 0x{offset:X}',
                    'severity': 'high' if sig_name in ('PE/EXE', 'ELF', 'LNK') else 'warning',
                    'offset': offset
                })

        # --- Scan for polyglot markers ---
        for marker_name, (marker_bytes, desc) in self.markers.items():
            offsets = []
            start = 0
            count = 0
            while count < 5:
                idx = data.find(marker_bytes, start)
                if idx == -1:
                    break
                offsets.append(idx)
                start = idx + len(marker_bytes)
                count += 1
            if len(offsets) > 1:
                findings.append({
                    'type': 'DUPLICATE_MARKER',
                    'detail': f'{marker_name} found {len(offsets)} times — {desc}',
                    'severity': 'warning',
                    'offset': offsets[-1]
                })

        # --- Entropy analysis (8 sections) ---
        section_size = max(len(data) // 8, 1)
        for i in range(8):
            section = data[i * section_size:(i + 1) * section_size]
            if len(section) < 100:
                continue
            ent = self._entropy(section)
            if ent > 7.5:
                findings.append({
                    'type': 'HIGH_ENTROPY',
                    'detail': f'Section {i+1}/8: entropy {ent:.2f} (possible encrypted/compressed payload)',
                    'severity': 'info',
                    'offset': i * section_size
                })

        # --- Check for data after last known end marker ---
        if content_type == 'JPEG':
            eoi = data.rfind(b'\xff\xd9')
            if eoi != -1 and eoi + 2 < len(data):
                trailing = len(data) - eoi - 2
                findings.append({
                    'type': 'TRAILING_DATA',
                    'detail': f'{trailing} bytes after JPEG EOI — likely hidden payload',
                    'severity': 'critical',
                    'offset': eoi + 2
                })
        elif content_type == 'PNG':
            iend = data.rfind(b'IEND')
            if iend != -1 and iend + 8 < len(data):
                trailing = len(data) - iend - 8
                findings.append({
                    'type': 'TRAILING_DATA',
                    'detail': f'{trailing} bytes after PNG IEND — likely hidden payload',
                    'severity': 'critical',
                    'offset': iend + 8
                })

        return findings

    def _entropy(self, data: bytes) -> float:
        if not data:
            return 0.0
        freq = [0] * 256
        for b in data:
            freq[b] += 1
        length = len(data)
        ent = 0.0
        for f in freq:
            if f > 0:
                p = f / length
                ent -= p * math.log2(p)
        return ent


# ── Polyglot Sanitizer ─────────────────────────────────────

class PolyglotSanitizer:
    """Strips hidden payloads after end markers. Creates .bak backups."""

    def sanitize(self, filepath: str, create_backup: bool = True) -> dict:
        """Sanitize a file. Returns result dict."""
        with open(filepath, 'rb') as f:
            data = f.read()

        original_size = len(data)
        ext = os.path.splitext(filepath)[1].lower()
        cleaned = None

        if ext in ('.jpg', '.jpeg') or data[:2] == b'\xff\xd8':
            cleaned = self._sanitize_jpeg(data)
            detected_type = 'JPEG'
        elif ext == '.png' or data[:8] == b'\x89PNG\r\n\x1a\n':
            cleaned = self._sanitize_png(data)
            detected_type = 'PNG'
        elif ext == '.gif' or data[:6] in (b'GIF87a', b'GIF89a'):
            cleaned = self._sanitize_gif(data)
            detected_type = 'GIF'
        elif ext == '.pdf' or data[:4] == b'%PDF':
            cleaned = self._sanitize_pdf(data)
            detected_type = 'PDF'
        elif ext == '.zip' or data[:2] == b'PK':
            cleaned = self._sanitize_zip(data)
            detected_type = 'ZIP'
        else:
            return {'status': 'skipped', 'detail': f'Unsupported file type: {ext}'}

        if cleaned is None:
            return {
                'status': 'clean',
                'detail': f'{detected_type}: No trailing data found',
                'original_size': original_size,
                'cleaned_size': original_size,
                'removed_bytes': 0,
            }

        if len(cleaned) >= original_size:
            return {
                'status': 'clean',
                'detail': f'{detected_type}: No removable data found',
                'original_size': original_size,
                'cleaned_size': original_size,
                'removed_bytes': 0,
            }

        if create_backup:
            backup_path = filepath + '.bak'
            shutil.copy2(filepath, backup_path)

        with open(filepath, 'wb') as f:
            f.write(cleaned)

        removed = original_size - len(cleaned)
        return {
            'status': 'sanitized',
            'detail': f'{detected_type}: Removed {removed} bytes of trailing data',
            'original_size': original_size,
            'cleaned_size': len(cleaned),
            'removed_bytes': removed,
            'backup': filepath + '.bak' if create_backup else None,
        }

    def _sanitize_jpeg(self, data: bytes):
        eoi = data.rfind(b'\xff\xd9')
        if eoi == -1 or eoi + 2 >= len(data):
            return None
        return data[:eoi + 2]

    def _sanitize_png(self, data: bytes):
        iend = data.rfind(b'IEND')
        if iend == -1 or iend + 8 >= len(data):
            return None
        return data[:iend + 8]

    def _sanitize_gif(self, data: bytes):
        term = data.rfind(b'\x3b')
        if term == -1 or term + 1 >= len(data):
            return None
        return data[:term + 1]

    def _sanitize_pdf(self, data: bytes):
        eof = data.rfind(b'%%EOF')
        if eof == -1 or eof + 5 >= len(data):
            return None
        return data[:eof + 5]

    def _sanitize_zip(self, data: bytes):
        eocd_sig = b'\x50\x4b\x05\x06'
        eocd_pos = data.rfind(eocd_sig)
        if eocd_pos == -1:
            return None
        # EOCD is at least 22 bytes
        expected_end = eocd_pos + 22
        comment_len = struct.unpack('<H', data[eocd_pos + 20:eocd_pos + 22])[0]
        expected_end += comment_len
        if expected_end >= len(data):
            return None
        return data[:expected_end]


# ── Real-Time File Monitor ─────────────────────────────────

class FileMonitor:
    """Monitors a directory for new/modified files and scans them."""

    def __init__(self):
        self.watch_dir = None
        self.running = False
        self.file_hashes = {}  # path -> (mtime, size, md5)
        self.alerts = deque(maxlen=200)
        self.stats = {'scanned': 0, 'threats': 0, 'clean': 0}
        self._thread = None
        self._callback = None
        self.detector = PolyglotDetector()

    def start(self, directory: str, callback=None):
        """Start monitoring a directory."""
        if self.running:
            return
        self.watch_dir = directory
        self.running = True
        self._callback = callback
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop monitoring."""
        self.running = False

    def _monitor_loop(self):
        """Main monitoring loop."""
        scan_extensions = {
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.pdf',
            '.doc', '.docx', '.zip', '.exe', '.dll', '.scr',
            '.bat', '.cmd', '.ps1', '.vbs', '.js', '.hta',
            '.lnk', '.elf', '.so',
        }

        while self.running:
            try:
                for root, dirs, files in os.walk(self.watch_dir):
                    # Skip hidden dirs
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    for fname in files:
                        if not self.running:
                            return
                        ext = os.path.splitext(fname)[1].lower()
                        if ext not in scan_extensions:
                            continue

                        fpath = os.path.join(root, fname)
                        try:
                            stat = os.stat(fpath)
                            current = (stat.st_mtime, stat.st_size)
                        except OSError:
                            continue

                        prev = self.file_hashes.get(fpath)
                        if prev is None:
                            # New file — scan it
                            self.file_hashes[fpath] = current
                            self._scan_and_alert(fpath)
                        elif prev != current:
                            # Modified file — rescan
                            self.file_hashes[fpath] = current
                            self._scan_and_alert(fpath)

                time.sleep(2)  # Poll interval
            except Exception as e:
                self._emit('error', f'Monitor error: {e}')
                time.sleep(5)

    def _scan_and_alert(self, filepath: str):
        """Scan a file and emit alerts for findings."""
        findings = self.detector.scan_file(filepath)
        self.stats['scanned'] += 1

        if findings:
            critical = [f for f in findings if f['severity'] == 'critical']
            high = [f for f in findings if f['severity'] == 'high']
            if critical or high:
                self.stats['threats'] += 1
                severity = 'critical' if critical else 'high'
                details = '; '.join(f['detail'] for f in (critical or high)[:3])
                alert = {
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'file': os.path.basename(filepath),
                    'path': filepath,
                    'severity': severity,
                    'detail': details,
                    'findings': findings,
                }
                self.alerts.append(alert)
                self._emit('threat', alert)

                # Desktop notification
                urgency = "critical" if severity == 'critical' else "normal"
                Notifier.send(
                    f"⚠ THREAT: {os.path.basename(filepath)}",
                    details[:200],
                    urgency=urgency
                )
            else:
                self.stats['clean'] += 1
        else:
            self.stats['clean'] += 1

    def _emit(self, event_type, data):
        if self._callback:
            try:
                self._callback(event_type, data)
            except Exception:
                pass


# ── GUI Application ────────────────────────────────────────

class PolyglotApp:
    """Main GUI Application — Red Team Edition."""

    # Color scheme
    BG_DARK = '#0d1117'
    BG_PANEL = '#161b22'
    BG_CARD = '#1c2333'
    BG_INPUT = '#0d1117'
    FG_TEXT = '#c9d1d9'
    FG_DIM = '#6e7681'
    FG_ACCENT = '#ff4444'
    FG_GREEN = '#3fb950'
    FG_YELLOW = '#d29922'
    FG_BLUE = '#58a6ff'
    FG_ORANGE = '#f0883e'
    BORDER = '#30363d'

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Polyglot Toolkit — Red Team Edition")
        self.root.geometry("1100x700")
        self.root.configure(bg=self.BG_DARK)
        self.root.minsize(900, 600)

        self.builder = PolyglotBuilder()
        self.detector = PolyglotDetector()
        self.sanitizer = PolyglotSanitizer()
        self.monitor = FileMonitor()

        self._configure_styles()
        self._build_ui()

        # Start stats updater
        self._update_monitor_stats()

    def _configure_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        style.configure('Dark.TFrame', background=self.BG_DARK)
        style.configure('Panel.TFrame', background=self.BG_PANEL)
        style.configure('Card.TFrame', background=self.BG_CARD)
        style.configure('Dark.TLabel', background=self.BG_DARK, foreground=self.FG_TEXT, font=('Segoe UI', 10))
        style.configure('Title.TLabel', background=self.BG_DARK, foreground=self.FG_ACCENT, font=('Segoe UI', 18, 'bold'))
        style.configure('Subtitle.TLabel', background=self.BG_DARK, foreground=self.FG_DIM, font=('Segoe UI', 9))
        style.configure('Card.TLabel', background=self.BG_CARD, foreground=self.FG_TEXT, font=('Segoe UI', 10))
        style.configure('CardTitle.TLabel', background=self.BG_CARD, foreground=self.FG_BLUE, font=('Segoe UI', 11, 'bold'))
        style.configure('Stat.TLabel', background=self.BG_CARD, foreground=self.FG_GREEN, font=('Segoe UI', 24, 'bold'))
        style.configure('Status.TLabel', background=self.BG_PANEL, foreground=self.FG_DIM, font=('Segoe UI', 8))
        style.configure('Nav.TButton', background=self.BG_PANEL, foreground=self.FG_TEXT, font=('Segoe UI', 10),
                        borderwidth=0, padding=(15, 10))
        style.map('Nav.TButton', background=[('active', self.BG_CARD)])
        style.configure('Accent.TButton', background=self.FG_ACCENT, foreground='white', font=('Segoe UI', 10, 'bold'),
                        borderwidth=0, padding=(20, 8))
        style.map('Accent.TButton', background=[('active', '#cc0000')])
        style.configure('Green.TButton', background=self.FG_GREEN, foreground='white', font=('Segoe UI', 10, 'bold'),
                        borderwidth=0, padding=(20, 8))
        style.map('Green.TButton', background=[('active', '#2ea043')])
        style.configure('TNotebook', background=self.BG_DARK, borderwidth=0)
        style.configure('TNotebook.Tab', background=self.BG_PANEL, foreground=self.FG_TEXT,
                        font=('Segoe UI', 10), padding=(15, 8))
        style.map('TNotebook.Tab', background=[('selected', self.BG_CARD)],
                  foreground=[('selected', self.FG_ACCENT)])
        style.configure('Horizontal.TProgressbar', background=self.FG_GREEN, troughcolor=self.BG_PANEL,
                        borderwidth=0, lightcolor=self.FG_GREEN, darkcolor=self.FG_GREEN)

    def _build_ui(self):
        # Main container
        main = ttk.Frame(self.root, style='Dark.TFrame')
        main.pack(fill=tk.BOTH, expand=True)

        # Header
        header = tk.Frame(main, bg=self.BG_DARK, height=60)
        header.pack(fill=tk.X, padx=15, pady=(10, 0))
        header.pack_propagate(False)

        tk.Label(header, text="◆ POLYGLOT TOOLKIT", bg=self.BG_DARK, fg=self.FG_ACCENT,
                font=('Consolas', 16, 'bold')).pack(side=tk.LEFT)
        tk.Label(header, text="RED TEAM EDITION", bg=self.BG_DARK, fg=self.FG_DIM,
                font=('Consolas', 10)).pack(side=tk.LEFT, padx=(10, 0))

        # Status indicator
        self.status_dot = tk.Label(header, text="●", bg=self.BG_DARK, fg=self.FG_DIM,
                                   font=('Segoe UI', 12))
        self.status_dot.pack(side=tk.RIGHT, padx=5)
        self.status_label = tk.Label(header, text="IDLE", bg=self.BG_DARK, fg=self.FG_DIM,
                                     font=('Consolas', 9))
        self.status_label.pack(side=tk.RIGHT)

        # Separator
        tk.Frame(main, bg=self.BORDER, height=1).pack(fill=tk.X, padx=15, pady=5)

        # Notebook (tabs)
        self.notebook = ttk.Notebook(main, style='TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        # Build tabs
        self._build_dashboard_tab()
        self._build_builder_tab()
        self._build_detector_tab()
        self._build_sanitizer_tab()
        self._build_monitor_tab()
        self._build_log_tab()

        # Status bar
        status_bar = tk.Frame(main, bg=self.BG_PANEL, height=25)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        status_bar.pack_propagate(False)
        self.status_bar_label = tk.Label(status_bar, text=" Ready  |  v1.0  |  Author: Mr-DS-ML-85",
                                         bg=self.BG_PANEL, fg=self.FG_DIM, font=('Consolas', 8))
        self.status_bar_label.pack(side=tk.LEFT, padx=10)

    def _build_dashboard_tab(self):
        tab = ttk.Frame(self.notebook, style='Dark.TFrame')
        self.notebook.add(tab, text=" ◆ Dashboard ")

        # Stats cards row
        cards = tk.Frame(tab, bg=self.BG_DARK)
        cards.pack(fill=tk.X, padx=20, pady=15)

        self.dash_stats = {}
        stat_defs = [
            ('Files Scanned', '0', self.FG_BLUE, '🔍'),
            ('Threats Found', '0', self.FG_ACCENT, '⚠'),
            ('Files Sanitized', '0', self.FG_GREEN, '🛡'),
            ('Polyglots Built', '0', self.FG_ORANGE, '◆'),
        ]

        for i, (label, value, color, icon) in enumerate(stat_defs):
            card = tk.Frame(cards, bg=self.BG_CARD, highlightbackground=self.BORDER, highlightthickness=1)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

            tk.Label(card, text=icon, bg=self.BG_CARD, fg=color, font=('Segoe UI', 20)).pack(pady=(15, 0))
            lbl = tk.Label(card, text=value, bg=self.BG_CARD, fg=color, font=('Consolas', 28, 'bold'))
            lbl.pack(pady=(5, 0))
            tk.Label(card, text=label, bg=self.BG_CARD, fg=self.FG_DIM, font=('Segoe UI', 9)).pack(pady=(0, 15))

            self.dash_stats[label] = lbl

        # Recent alerts
        tk.Label(tab, text="Recent Alerts", bg=self.BG_DARK, fg=self.FG_TEXT,
                font=('Segoe UI', 12, 'bold')).pack(anchor=tk.W, padx=20, pady=(10, 5))

        self.dash_alerts = scrolledtext.ScrolledText(tab, bg=self.BG_CARD, fg=self.FG_TEXT,
                                                      font=('Consolas', 9), height=12,
                                                      insertbackground=self.FG_TEXT,
                                                      selectbackground=self.FG_ACCENT,
                                                      relief=tk.FLAT, state=tk.DISABLED)
        self.dash_alerts.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))

        # Quick actions
        actions = tk.Frame(tab, bg=self.BG_DARK)
        actions.pack(fill=tk.X, padx=20, pady=(0, 15))

        ttk.Button(actions, text="⚡ Quick Scan File", style='Accent.TButton',
                  command=self._quick_scan).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions, text="🛡 Quick Sanitize", style='Green.TButton',
                  command=self._quick_sanitize).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions, text="▶ Start Monitor", style='Green.TButton',
                  command=lambda: self.notebook.select(4)).pack(side=tk.LEFT, padx=5)

    def _build_builder_tab(self):
        tab = ttk.Frame(self.notebook, style='Dark.TFrame')
        self.notebook.add(tab, text=" ◆ Builder ")

        # Input section
        input_frame = tk.LabelFrame(tab, text=" Input Files ", bg=self.BG_CARD, fg=self.FG_BLUE,
                                     font=('Segoe UI', 10, 'bold'), highlightbackground=self.BORDER,
                                     highlightthickness=1, bd=1)
        input_frame.pack(fill=tk.X, padx=20, pady=15)

        # Cover file
        row1 = tk.Frame(input_frame, bg=self.BG_CARD)
        row1.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(row1, text="Cover File (JPEG/PNG/GIF/PDF/ZIP):", bg=self.BG_CARD, fg=self.FG_TEXT,
                font=('Segoe UI', 9)).pack(anchor=tk.W)
        cf = tk.Frame(row1, bg=self.BG_CARD)
        cf.pack(fill=tk.X, pady=3)
        self.builder_cover = tk.Entry(cf, bg=self.BG_INPUT, fg=self.FG_TEXT, insertbackground=self.FG_TEXT,
                                       font=('Consolas', 10), relief=tk.FLAT, highlightbackground=self.BORDER,
                                       highlightthickness=1)
        self.builder_cover.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        tk.Button(cf, text="Browse", bg=self.BG_PANEL, fg=self.FG_TEXT, font=('Segoe UI', 9),
                 relief=tk.FLAT, command=lambda: self._browse_file(self.builder_cover)).pack(side=tk.LEFT, padx=5)

        # Payload file
        row2 = tk.Frame(input_frame, bg=self.BG_CARD)
        row2.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(row2, text="Payload File (EXE/Script/Binary to hide):", bg=self.BG_CARD, fg=self.FG_TEXT,
                font=('Segoe UI', 9)).pack(anchor=tk.W)
        pf = tk.Frame(row2, bg=self.BG_CARD)
        pf.pack(fill=tk.X, pady=3)
        self.builder_payload = tk.Entry(pf, bg=self.BG_INPUT, fg=self.FG_TEXT, insertbackground=self.FG_TEXT,
                                         font=('Consolas', 10), relief=tk.FLAT, highlightbackground=self.BORDER,
                                         highlightthickness=1)
        self.builder_payload.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        tk.Button(pf, text="Browse", bg=self.BG_PANEL, fg=self.FG_TEXT, font=('Segoe UI', 9),
                 relief=tk.FLAT, command=lambda: self._browse_file(self.builder_payload)).pack(side=tk.LEFT, padx=5)

        # Options
        opt_frame = tk.LabelFrame(tab, text=" Options ", bg=self.BG_CARD, fg=self.FG_BLUE,
                                   font=('Segoe UI', 10, 'bold'), highlightbackground=self.BORDER,
                                   highlightthickness=1, bd=1)
        opt_frame.pack(fill=tk.X, padx=20, pady=5)

        opts = tk.Frame(opt_frame, bg=self.BG_CARD)
        opts.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(opts, text="Container Type:", bg=self.BG_CARD, fg=self.FG_TEXT).pack(side=tk.LEFT)
        self.builder_type = ttk.Combobox(opts, values=['JPEG', 'PNG', 'GIF', 'PDF', 'ZIP'],
                                          state='readonly', width=8, font=('Consolas', 10))
        self.builder_type.set('JPEG')
        self.builder_type.pack(side=tk.LEFT, padx=10)

        self.builder_encrypt = tk.BooleanVar()
        tk.Checkbutton(opts, text="XOR Encrypt Payload", variable=self.builder_encrypt,
                       bg=self.BG_CARD, fg=self.FG_TEXT, selectcolor=self.BG_INPUT,
                       activebackground=self.BG_CARD, font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=20)

        # Build button
        btn_frame = tk.Frame(tab, bg=self.BG_DARK)
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        ttk.Button(btn_frame, text="◆ BUILD POLYGLOT", style='Accent.TButton',
                  command=self._build_polyglot).pack(side=tk.LEFT)

        # Output
        tk.Label(tab, text="Build Log", bg=self.BG_DARK, fg=self.FG_TEXT,
                font=('Segoe UI', 11, 'bold')).pack(anchor=tk.W, padx=20, pady=(5, 3))
        self.builder_log = scrolledtext.ScrolledText(tab, bg=self.BG_CARD, fg=self.FG_GREEN,
                                                      font=('Consolas', 9), height=10,
                                                      insertbackground=self.FG_TEXT,
                                                      selectbackground=self.FG_ACCENT,
                                                      relief=tk.FLAT, state=tk.DISABLED)
        self.builder_log.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))

    def _build_detector_tab(self):
        tab = ttk.Frame(self.notebook, style='Dark.TFrame')
        self.notebook.add(tab, text=" ⚠ Detector ")

        # File selection
        sel = tk.Frame(tab, bg=self.BG_DARK)
        sel.pack(fill=tk.X, padx=20, pady=15)

        tk.Label(sel, text="Target:", bg=self.BG_DARK, fg=self.FG_TEXT,
                font=('Segoe UI', 10)).pack(side=tk.LEFT)
        self.detector_path = tk.Entry(sel, bg=self.BG_INPUT, fg=self.FG_TEXT, insertbackground=self.FG_TEXT,
                                       font=('Consolas', 10), relief=tk.FLAT, highlightbackground=self.BORDER,
                                       highlightthickness=1)
        self.detector_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, ipady=4)
        tk.Button(sel, text="Browse File", bg=self.BG_PANEL, fg=self.FG_TEXT, relief=tk.FLAT,
                 command=lambda: self._browse_file(self.detector_path)).pack(side=tk.LEFT, padx=2)
        tk.Button(sel, text="Browse Dir", bg=self.BG_PANEL, fg=self.FG_TEXT, relief=tk.FLAT,
                 command=lambda: self._browse_dir(self.detector_path)).pack(side=tk.LEFT, padx=2)
        ttk.Button(sel, text="⚠ SCAN", style='Accent.TButton',
                  command=self._run_detector).pack(side=tk.LEFT, padx=10)

        # Progress
        self.detector_progress = ttk.Progressbar(tab, mode='determinate', style='Horizontal.TProgressbar')
        self.detector_progress.pack(fill=tk.X, padx=20, pady=(0, 5))

        # Results
        self.detector_results = scrolledtext.ScrolledText(tab, bg=self.BG_CARD, fg=self.FG_TEXT,
                                                           font=('Consolas', 9), height=18,
                                                           insertbackground=self.FG_TEXT,
                                                           selectbackground=self.FG_ACCENT,
                                                           relief=tk.FLAT, state=tk.DISABLED)
        self.detector_results.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))

        # Tag configs for colored output
        self.detector_results.tag_configure('critical', foreground=self.FG_ACCENT)
        self.detector_results.tag_configure('high', foreground=self.FG_ORANGE)
        self.detector_results.tag_configure('warning', foreground=self.FG_YELLOW)
        self.detector_results.tag_configure('info', foreground=self.FG_BLUE)
        self.detector_results.tag_configure('clean', foreground=self.FG_GREEN)
        self.detector_results.tag_configure('header', foreground=self.FG_ACCENT, font=('Consolas', 10, 'bold'))

    def _build_sanitizer_tab(self):
        tab = ttk.Frame(self.notebook, style='Dark.TFrame')
        self.notebook.add(tab, text=" 🛡 Sanitizer ")

        sel = tk.Frame(tab, bg=self.BG_DARK)
        sel.pack(fill=tk.X, padx=20, pady=15)

        tk.Label(sel, text="Target:", bg=self.BG_DARK, fg=self.FG_TEXT,
                font=('Segoe UI', 10)).pack(side=tk.LEFT)
        self.sanitizer_path = tk.Entry(sel, bg=self.BG_INPUT, fg=self.FG_TEXT, insertbackground=self.FG_TEXT,
                                        font=('Consolas', 10), relief=tk.FLAT, highlightbackground=self.BORDER,
                                        highlightthickness=1)
        self.sanitizer_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, ipady=4)
        tk.Button(sel, text="Browse File", bg=self.BG_PANEL, fg=self.FG_TEXT, relief=tk.FLAT,
                 command=lambda: self._browse_file(self.sanitizer_path)).pack(side=tk.LEFT, padx=2)
        tk.Button(sel, text="Browse Dir", bg=self.BG_PANEL, fg=self.FG_TEXT, relief=tk.FLAT,
                 command=lambda: self._browse_dir(self.sanitizer_path)).pack(side=tk.LEFT, padx=2)
        ttk.Button(sel, text="🛡 SANITIZE", style='Green.TButton',
                  command=self._run_sanitizer).pack(side=tk.LEFT, padx=10)

        self.sanitizer_backup = tk.BooleanVar(value=True)
        tk.Checkbutton(sel, text="Create .bak backup", variable=self.sanitizer_backup,
                       bg=self.BG_DARK, fg=self.FG_TEXT, selectcolor=self.BG_INPUT,
                       activebackground=self.BG_DARK, font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=10)

        # Results
        self.sanitizer_results = scrolledtext.ScrolledText(tab, bg=self.BG_CARD, fg=self.FG_TEXT,
                                                            font=('Consolas', 9), height=20,
                                                            insertbackground=self.FG_TEXT,
                                                            selectbackground=self.FG_GREEN,
                                                            relief=tk.FLAT, state=tk.DISABLED)
        self.sanitizer_results.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))

        self.sanitizer_results.tag_configure('sanitized', foreground=self.FG_GREEN)
        self.sanitizer_results.tag_configure('clean', foreground=self.FG_BLUE)
        self.sanitizer_results.tag_configure('error', foreground=self.FG_ACCENT)
        self.sanitizer_results.tag_configure('header', foreground=self.FG_GREEN, font=('Consolas', 10, 'bold'))

    def _build_monitor_tab(self):
        tab = ttk.Frame(self.notebook, style='Dark.TFrame')
        self.notebook.add(tab, text=" ▶ Monitor ")

        # Controls
        ctrl = tk.Frame(tab, bg=self.BG_DARK)
        ctrl.pack(fill=tk.X, padx=20, pady=15)

        tk.Label(ctrl, text="Watch Directory:", bg=self.BG_DARK, fg=self.FG_TEXT,
                font=('Segoe UI', 10)).pack(side=tk.LEFT)
        self.monitor_dir = tk.Entry(ctrl, bg=self.BG_INPUT, fg=self.FG_TEXT, insertbackground=self.FG_TEXT,
                                     font=('Consolas', 10), relief=tk.FLAT, highlightbackground=self.BORDER,
                                     highlightthickness=1)
        self.monitor_dir.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, ipady=4)
        self.monitor_dir.insert(0, os.path.expanduser("~/Downloads"))
        tk.Button(ctrl, text="Browse", bg=self.BG_PANEL, fg=self.FG_TEXT, relief=tk.FLAT,
                 command=lambda: self._browse_dir(self.monitor_dir)).pack(side=tk.LEFT, padx=2)

        self.monitor_btn = ttk.Button(ctrl, text="▶ START", style='Green.TButton',
                                       command=self._toggle_monitor)
        self.monitor_btn.pack(side=tk.LEFT, padx=10)

        # Stats row
        stats = tk.Frame(tab, bg=self.BG_DARK)
        stats.pack(fill=tk.X, padx=20, pady=5)

        self.mon_stat_labels = {}
        for label, color in [('Scanned', self.FG_BLUE), ('Threats', self.FG_ACCENT), ('Clean', self.FG_GREEN)]:
            f = tk.Frame(stats, bg=self.BG_CARD, highlightbackground=self.BORDER, highlightthickness=1)
            f.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
            tk.Label(f, text=label, bg=self.BG_CARD, fg=self.FG_DIM, font=('Segoe UI', 8)).pack(pady=(8, 0))
            lbl = tk.Label(f, text="0", bg=self.BG_CARD, fg=color, font=('Consolas', 20, 'bold'))
            lbl.pack(pady=(0, 8))
            self.mon_stat_labels[label] = lbl

        # Alert feed
        tk.Label(tab, text="Live Alert Feed", bg=self.BG_DARK, fg=self.FG_TEXT,
                font=('Segoe UI', 11, 'bold')).pack(anchor=tk.W, padx=20, pady=(10, 3))

        self.monitor_feed = scrolledtext.ScrolledText(tab, bg=self.BG_CARD, fg=self.FG_TEXT,
                                                       font=('Consolas', 9), height=15,
                                                       insertbackground=self.FG_TEXT,
                                                       selectbackground=self.FG_ACCENT,
                                                       relief=tk.FLAT, state=tk.DISABLED)
        self.monitor_feed.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))

        self.monitor_feed.tag_configure('critical', foreground=self.FG_ACCENT, font=('Consolas', 9, 'bold'))
        self.monitor_feed.tag_configure('high', foreground=self.FG_ORANGE)
        self.monitor_feed.tag_configure('info', foreground=self.FG_BLUE)
        self.monitor_feed.tag_configure('timestamp', foreground=self.FG_DIM)

    def _build_log_tab(self):
        tab = ttk.Frame(self.notebook, style='Dark.TFrame')
        self.notebook.add(tab, text=" 📋 Log ")

        btn_frame = tk.Frame(tab, bg=self.BG_DARK)
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        tk.Button(btn_frame, text="Clear Log", bg=self.BG_PANEL, fg=self.FG_TEXT, relief=tk.FLAT,
                 command=self._clear_log).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Export Log", bg=self.BG_PANEL, fg=self.FG_TEXT, relief=tk.FLAT,
                 command=self._export_log).pack(side=tk.LEFT, padx=5)

        self.main_log = scrolledtext.ScrolledText(tab, bg=self.BG_CARD, fg=self.FG_TEXT,
                                                    font=('Consolas', 9), height=25,
                                                    insertbackground=self.FG_TEXT,
                                                    selectbackground=self.FG_ACCENT,
                                                    relief=tk.FLAT, state=tk.DISABLED)
        self.main_log.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))

        self.main_log.tag_configure('info', foreground=self.FG_BLUE)
        self.main_log.tag_configure('success', foreground=self.FG_GREEN)
        self.main_log.tag_configure('warning', foreground=self.FG_YELLOW)
        self.main_log.tag_configure('error', foreground=self.FG_ACCENT)
        self.main_log.tag_configure('header', foreground=self.FG_ACCENT, font=('Consolas', 10, 'bold'))

    # ── Helpers ────────────────────────────────────────────

    def _browse_file(self, entry_widget):
        path = filedialog.askopenfilename(title="Select File")
        if path:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, path)

    def _browse_dir(self, entry_widget):
        path = filedialog.askdirectory(title="Select Directory")
        if path:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, path)

    def _log(self, widget, text, tag=None):
        widget.configure(state=tk.NORMAL)
        widget.insert(tk.END, text + "\n", tag)
        widget.see(tk.END)
        widget.configure(state=tk.DISABLED)

    def _log_main(self, text, tag=None):
        ts = datetime.now().strftime('%H:%M:%S')
        self._log(self.main_log, f"[{ts}] {text}", tag)

    def _set_status(self, text, color=None):
        self.status_label.configure(text=text, fg=color or self.FG_DIM)
        self.status_dot.configure(fg=color or self.FG_DIM)

    # ── Builder Actions ────────────────────────────────────

    def _build_polyglot(self):
        cover = self.builder_cover.get().strip()
        payload = self.builder_payload.get().strip()
        output = filedialog.asksaveasfilename(
            title="Save Polyglot As",
            defaultextension=f".{self.builder_type.get().lower()}",
            filetypes=[("All files", "*.*")]
        )
        if not output:
            return

        if not cover or not os.path.isfile(cover):
            messagebox.showerror("Error", "Select a valid cover file")
            return
        if not payload or not os.path.isfile(payload):
            messagebox.showerror("Error", "Select a valid payload file")
            return

        self._set_status("BUILDING...", self.FG_ACCENT)
        self._log(self.builder_log, "═" * 50, 'header')
        self._log_main("Building polyglot...", 'info')

        try:
            stats = self.builder.build(
                cover, payload, output,
                container_type=self.builder_type.get().lower(),
                encrypt=self.builder_encrypt.get()
            )

            self._log(self.builder_log, f"✓ Output:  {stats['output']}", 'success')
            self._log(self.builder_log, f"  Type:    {stats['container_type']}")
            self._log(self.builder_log, f"  Cover:   {stats['cover_size']:,} bytes")
            self._log(self.builder_log, f"  Payload: {stats['payload_size']:,} bytes")
            self._log(self.builder_log, f"  Total:   {stats['output_size']:,} bytes")
            self._log(self.builder_log, f"  Offset:  0x{stats['payload_offset']:X}")
            self._log(self.builder_log, f"  Entropy: {stats['entropy']}")
            self._log(self.builder_log, f"  Encrypted: {stats['encrypted']}")
            self._log(self.builder_log, "═" * 50, 'header')

            self._log_main(f"Polyglot built: {output}", 'success')
            self._set_status("BUILD COMPLETE", self.FG_GREEN)

            # Update dashboard
            current = int(self.dash_stats['Polyglots Built'].cget('text'))
            self.dash_stats['Polyglots Built'].configure(text=str(current + 1))

            Notifier.send("Polyglot Built", f"Created: {os.path.basename(output)}")

        except Exception as e:
            self._log(self.builder_log, f"✗ ERROR: {e}", 'error')
            self._log_main(f"Build failed: {e}", 'error')
            self._set_status("BUILD FAILED", self.FG_ACCENT)

    # ── Detector Actions ───────────────────────────────────

    def _run_detector(self):
        target = self.detector_path.get().strip()
        if not target:
            messagebox.showerror("Error", "Select a file or directory to scan")
            return

        self._set_status("SCANNING...", self.FG_YELLOW)
        self._log_main(f"Scanning: {target}", 'info')

        threading.Thread(target=self._detector_thread, args=(target,), daemon=True).start()

    def _detector_thread(self, target):
        self.detector_results.configure(state=tk.NORMAL)
        self.detector_results.delete('1.0', tk.END)
        self.detector_results.configure(state=tk.DISABLED)

        if os.path.isfile(target):
            files = [target]
        elif os.path.isdir(target):
            files = []
            exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.pdf', '.doc', '.docx',
                    '.zip', '.exe', '.dll', '.bat', '.cmd', '.ps1', '.vbs', '.js'}
            for root, dirs, fnames in os.walk(target):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in fnames:
                    if os.path.splitext(f)[1].lower() in exts:
                        files.append(os.path.join(root, f))
        else:
            self.root.after(0, lambda: self._log(self.detector_results, "Invalid path", 'error'))
            return

        total = len(files)
        threats = 0

        self.root.after(0, lambda: self.detector_progress.configure(maximum=total, value=0))

        for i, fpath in enumerate(files):
            findings = self.detector.scan_file(fpath)
            self.root.after(0, lambda fp=fpath, f=findings, idx=i: self._detector_result(fp, f, idx, total))

            if findings:
                critical_high = [f for f in findings if f['severity'] in ('critical', 'high')]
                if critical_high:
                    threats += len(critical_high)

            self.root.after(0, lambda v=i+1: self.detector_progress.configure(value=v))

        self.root.after(0, lambda: self._detector_done(total, threats))

    def _detector_result(self, filepath, findings, idx, total):
        fname = os.path.basename(filepath)
        if not findings:
            self._log(self.detector_results, f"[{idx+1}/{total}] ✓ {fname} — CLEAN", 'clean')
            # Update dashboard
            current = int(self.dash_stats['Files Scanned'].cget('text'))
            self.dash_stats['Files Scanned'].configure(text=str(current + 1))
            return

        self._log(self.detector_results, f"\n[{idx+1}/{total}] ⚠ {fname}", 'header')
        for f in findings:
            tag = f['severity'] if f['severity'] in ('critical', 'high', 'warning', 'info') else 'warning'
            offset_str = f" @ 0x{f['offset']:X}" if 'offset' in f else ""
            self._log(self.detector_results, f"  [{f['severity'].upper()}] {f['type']}: {f['detail']}{offset_str}", tag)

        # Update dashboard
        current = int(self.dash_stats['Files Scanned'].cget('text'))
        self.dash_stats['Files Scanned'].configure(text=str(current + 1))
        thr = int(self.dash_stats['Threats Found'].cget('text'))
        crit = len([f for f in findings if f['severity'] in ('critical', 'high')])
        if crit:
            self.dash_stats['Threats Found'].configure(text=str(thr + crit))

    def _detector_done(self, total, threats):
        self._log(self.detector_results, f"\n{'═' * 50}", 'header')
        self._log(self.detector_results, f"SCAN COMPLETE: {total} files, {threats} threats", 'header')

        if threats > 0:
            self._set_status(f"THREATS: {threats}", self.FG_ACCENT)
            self._log_main(f"Scan complete: {threats} threats found in {total} files", 'error')
            Notifier.send("⚠ THREATS DETECTED", f"{threats} threats found in {total} files", urgency="critical")
            Notifier.play_alert()

            # Add to dashboard alerts
            self.dash_alerts.configure(state=tk.NORMAL)
            ts = datetime.now().strftime('%H:%M:%S')
            self.dash_alerts.insert(tk.END, f"[{ts}] ⚠ {threats} threats detected in {total} files scanned\n")
            self.dash_alerts.see(tk.END)
            self.dash_alerts.configure(state=tk.DISABLED)
        else:
            self._set_status("ALL CLEAR", self.FG_GREEN)
            self._log_main(f"Scan complete: {total} files, all clean", 'success')

    # ── Sanitizer Actions ──────────────────────────────────

    def _run_sanitizer(self):
        target = self.sanitizer_path.get().strip()
        if not target:
            messagebox.showerror("Error", "Select a file or directory")
            return

        self._set_status("SANITIZING...", self.FG_GREEN)
        self._log_main(f"Sanitizing: {target}", 'info')

        threading.Thread(target=self._sanitizer_thread, args=(target,), daemon=True).start()

    def _sanitizer_thread(self, target):
        self.sanitizer_results.configure(state=tk.NORMAL)
        self.sanitizer_results.delete('1.0', tk.END)
        self.sanitizer_results.configure(state=tk.DISABLED)

        if os.path.isfile(target):
            files = [target]
        elif os.path.isdir(target):
            files = []
            exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.pdf', '.zip'}
            for root, dirs, fnames in os.walk(target):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in fnames:
                    if os.path.splitext(f)[1].lower() in exts:
                        files.append(os.path.join(root, f))
        else:
            return

        total = len(files)
        sanitized_count = 0
        total_removed = 0

        self.root.after(0, lambda: self._log(self.sanitizer_results,
                                              f"Sanitizing {total} files...\n", 'header'))

        for fpath in files:
            try:
                result = self.sanitizer.sanitize(fpath, create_backup=self.sanitizer_backup.get())
                fname = os.path.basename(fpath)

                if result['status'] == 'sanitized':
                    sanitized_count += 1
                    total_removed += result['removed_bytes']
                    msg = f"✓ {fname}: {result['detail']}"
                    if result.get('backup'):
                        msg += f" (backup: {os.path.basename(result['backup'])})"
                    self.root.after(0, lambda m=msg: self._log(self.sanitizer_results, m, 'sanitized'))
                elif result['status'] == 'clean':
                    self.root.after(0, lambda m=f"○ {fname}: {result['detail']}":
                                    self._log(self.sanitizer_results, m, 'clean'))
                else:
                    self.root.after(0, lambda m=f"⊘ {fname}: {result['detail']}":
                                    self._log(self.sanitizer_results, m, 'error'))
            except Exception as e:
                self.root.after(0, lambda m=f"✗ {os.path.basename(fpath)}: {e}":
                                self._log(self.sanitizer_results, m, 'error'))

        self.root.after(0, lambda: self._sanitizer_done(total, sanitized_count, total_removed))

    def _sanitizer_done(self, total, sanitized, removed):
        self._log(self.sanitizer_results, f"\n{'═' * 50}", 'header')
        self._log(self.sanitizer_results, f"DONE: {sanitized}/{total} files sanitized, {removed:,} bytes removed", 'header')

        if sanitized > 0:
            self._set_status(f"CLEANED: {sanitized} files", self.FG_GREEN)
            self._log_main(f"Sanitized {sanitized} files, removed {removed:,} bytes", 'success')
            Notifier.send("🛡 Sanitization Complete", f"{sanitized} files cleaned, {removed:,} bytes removed")

            # Update dashboard
            current = int(self.dash_stats['Files Sanitized'].cget('text'))
            self.dash_stats['Files Sanitized'].configure(text=str(current + sanitized))
        else:
            self._set_status("ALL CLEAN", self.FG_BLUE)
            self._log_main("All files already clean", 'info')

    # ── Monitor Actions ────────────────────────────────────

    def _toggle_monitor(self):
        if self.monitor.running:
            self.monitor.stop()
            self.monitor_btn.configure(text="▶ START")
            self._set_status("MONITOR STOPPED", self.FG_DIM)
            self._log_main("File monitor stopped", 'warning')
        else:
            directory = self.monitor_dir.get().strip()
            if not os.path.isdir(directory):
                messagebox.showerror("Error", "Select a valid directory")
                return
            self.monitor_btn.configure(text="■ STOP")
            self._set_status("MONITORING", self.FG_GREEN)
            self.status_dot.configure(fg=self.FG_GREEN)
            self._log_main(f"Monitoring: {directory}", 'success')
            self._log(self.monitor_feed, f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f"▶ Monitoring started: {directory}", 'info')
            self.monitor.start(directory, callback=self._monitor_callback)

    def _monitor_callback(self, event_type, data):
        """Called from monitor thread — must use root.after for GUI updates."""
        if event_type == 'threat':
            alert = data
            ts = alert['time']
            severity = alert['severity'].upper()
            fname = alert['file']
            detail = alert['detail']

            def update_feed():
                self._log(self.monitor_feed, f"[{ts}] [{severity}] {fname}", alert['severity'])
                self._log(self.monitor_feed, f"  → {detail}\n", 'info')

                # Update dashboard alerts too
                self.dash_alerts.configure(state=tk.NORMAL)
                self.dash_alerts.insert(tk.END, f"[{ts}] ⚠ {severity}: {fname} — {detail}\n")
                self.dash_alerts.see(tk.END)
                self.dash_alerts.configure(state=tk.DISABLED)

            self.root.after(0, update_feed)

        elif event_type == 'error':
            self.root.after(0, lambda: self._log(self.monitor_feed,
                                                  f"[ERROR] {data}", 'critical'))

    def _update_monitor_stats(self):
        """Periodically update monitor stats display."""
        if self.monitor.running:
            self.mon_stat_labels['Scanned'].configure(text=str(self.monitor.stats['scanned']))
            self.mon_stat_labels['Threats'].configure(text=str(self.monitor.stats['threats']))
            self.mon_stat_labels['Clean'].configure(text=str(self.monitor.stats['clean']))
        self.root.after(1000, self._update_monitor_stats)

    # ── Quick Actions ──────────────────────────────────────

    def _quick_scan(self):
        path = filedialog.askopenfilename(title="Quick Scan File")
        if path:
            self.detector_path.delete(0, tk.END)
            self.detector_path.insert(0, path)
            self.notebook.select(2)  # Switch to detector tab
            self._run_detector()

    def _quick_sanitize(self):
        path = filedialog.askopenfilename(title="Quick Sanitize File")
        if path:
            self.sanitizer_path.delete(0, tk.END)
            self.sanitizer_path.insert(0, path)
            self.notebook.select(3)  # Switch to sanitizer tab
            self._run_sanitizer()

    # ── Log Actions ────────────────────────────────────────

    def _clear_log(self):
        self.main_log.configure(state=tk.NORMAL)
        self.main_log.delete('1.0', tk.END)
        self.main_log.configure(state=tk.DISABLED)

    def _export_log(self):
        path = filedialog.asksaveasfilename(
            title="Export Log",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if path:
            self.main_log.configure(state=tk.NORMAL)
            content = self.main_log.get('1.0', tk.END)
            self.main_log.configure(state=tk.DISABLED)
            with open(path, 'w') as f:
                f.write(content)
            Notifier.send("Log Exported", f"Saved to {os.path.basename(path)}")

    def run(self):
        self._log_main("Polyglot Toolkit — Red Team Edition started", 'header')
        self._log_main(f"Author: Mr-DS-ML-85", 'info')
        self._log_main("Builder | Detector | Sanitizer | Real-Time Monitor", 'info')
        self._log_main("═" * 50, 'info')
        self.root.mainloop()


# ── Entry Point ────────────────────────────────────────────

if __name__ == '__main__':
    app = PolyglotApp()
    app.run()
