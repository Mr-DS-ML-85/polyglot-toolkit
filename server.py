#!/usr/bin/env python3
"""
PolyglotShield — Server Mode (Headless API + Web Dashboard)
Runs on servers without display. CLI + REST API + Web UI.

Usage:
  python server.py                    Start server on :8888
  python server.py --port 9999        Custom port
  python server.py --host 0.0.0.0     Bind to all interfaces

API Endpoints:
  GET  /api/status                    Server status
  POST /api/scan                      Scan file (multipart upload)
  POST /api/scan/dir                  Scan directory
  POST /api/sanitize                  Sanitize file
  POST /api/build                     Build polyglot
  GET  /api/quarantine                List quarantined files
  POST /api/quarantine/restore        Restore quarantined file
  GET  /api/yara/rules                List YARA rules
  GET  /api/stats                     Dashboard stats
  POST /api/monitor/start             Start directory monitor
  POST /api/monitor/stop              Stop monitor
  GET  /api/alerts                    Get recent alerts

Author: Mr-DS-ML-85
"""

import sys, os, json, time, logging, argparse, tempfile
from pathlib import Path
from datetime import datetime
from collections import deque
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from flask import Flask, request, jsonify, send_from_directory, Response
import numpy as np

from engines.features import extract_features, analyze_file, extract_features_from_file
from engines.model import PolyglotModel, HAS_CATBOOST
from engines.yara_engine import YaraEngine
from engines.quarantine import QuarantineManager
from engines.notifications import NotificationManager
from engines.config import Config
from engines.scanner import Scanner, ScanResult

from polyglot_tui import PolyglotBuilder, PolyglotDetector, PolyglotSanitizer

logger = logging.getLogger("polyglot_server")

app = Flask(__name__)

# ── CORS ─────────────────────────────────────────────────────
@app.after_request
def add_cors_headers(response):
    origin = request.headers.get('Origin', '*')
    response.headers['Access-Control-Allow-Origin'] = origin
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response

# ── Basic Rate Limiting ──────────────────────────────────────
from collections import defaultdict
import threading
_rate_store = defaultdict(list)
_rate_lock = threading.Lock()
RATE_LIMIT = 60  # requests per minute per IP

def check_rate_limit():
    """Simple sliding-window rate limiter. Returns True if allowed."""
    ip = request.remote_addr or '0.0.0.0'
    now = time.time()
    with _rate_lock:
        window = _rate_store[ip]
        # Remove entries older than 60s
        _rate_store[ip] = [t for t in window if now - t < 60]
        if len(_rate_store[ip]) >= RATE_LIMIT:
            return False
        _rate_store[ip].append(now)
        return True

@app.before_request
def rate_limit_check():
    if request.endpoint and not check_rate_limit():
        return jsonify({'error': 'Rate limit exceeded (60 req/min)'}), 429

# ── Security Helpers ────────────────────────────────────────
ALLOWED_SCAN_ROOTS = [
    os.path.expanduser("~"),
    "/tmp",
    "/var/tmp",
    "/opt",
]

def safe_resolve_path(user_path: str) -> str | None:
    """Resolve and validate a user-provided path. Returns None if path is unsafe."""
    if not user_path:
        return None
    try:
        expanded = os.path.expanduser(user_path)
        real = os.path.realpath(expanded)
    except (ValueError, OSError):
        return None  # Null bytes, invalid chars, etc.
    # Block /etc, /proc, /sys, /dev, /boot, /root (unless running as root)
    blocked = {'/etc', '/proc', '/sys', '/dev', '/boot', '/run', '/snap'}
    for b in blocked:
        if real == b or real.startswith(b + '/'):
            return None
    # Must be under an allowed root or be an absolute existing path
    if not os.path.isabs(real):
        return None
    return real if os.path.exists(real) else None

def sanitize_filename(filename: str) -> str:
    """Strip path components and dangerous chars from uploaded filename."""
    import re
    base = os.path.basename(filename or 'upload')
    # Remove anything not alphanumeric, dash, underscore, dot
    safe = re.sub(r'[^a-zA-Z0-9._-]', '_', base)
    return safe[:200] if safe else 'upload'

def require_api_key(f):
    """Optional API key decorator — if POLYGLOT_API_KEY env is set, checks it."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        expected = os.environ.get('POLYGLOT_API_KEY')
        if expected:
            provided = request.headers.get('X-API-Key', '')
            if provided != expected:
                return jsonify({'error': 'Invalid or missing API key'}), 401
        return f(*args, **kwargs)
    return decorated

@app.errorhandler(Exception)
def handle_exception(e):
    """Global error handler — prevents unhandled crashes."""
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e  # Let Flask handle 404, 405, etc. normally
    logger.error(f"Unhandled exception: {e}", exc_info=True)
    return jsonify({'error': str(e)}), 500

# ── Global State ─────────────────────────────────────────────

class ServerState:
    def __init__(self):
        self.config = Config.load(str(Path(SCRIPT_DIR) / "config.yaml"))
        self.builder = PolyglotBuilder()
        self.detector = PolyglotDetector()
        self.sanitizer = PolyglotSanitizer()
        self.model = PolyglotModel(self.config.model)
        self.yara = YaraEngine()
        self.quarantine = QuarantineManager(
            quarantine_dir=self.config.quarantine.get("dir", "quarantine"))
        self.monitor_thread = None
        self.monitor_running = False
        self.alerts = deque(maxlen=200)
        self.stats = {'scanned': 0, 'threats': 0, 'sanitized': 0, 'built': 0}

        # Try to load model
        model_path = "models/polyglot_shield.cbm"
        if Path(model_path).exists():
            try:
                self.model.load(model_path)
                logger.info("ML model loaded")
            except Exception as e:
                logger.warning(f"Model load failed: {e}")

state = ServerState()


# ── API Endpoints ────────────────────────────────────────────

@app.route('/')
def index():
    """Serve the web dashboard."""
    return DASHBOARD_HTML

@app.route('/api/status')
def api_status():
    return jsonify({
        'status': 'running',
        'version': '3.0',
        'model_loaded': state.model.is_loaded,
        'model_type': state.config.model.get('task_type', 'CPU'),
        'yara_rules': len(state.yara.rules),
        'monitor_running': state.monitor_running,
        'timestamp': datetime.now().isoformat(),
    })

@app.route('/api/scan', methods=['POST'])
@require_api_key
def api_scan():
    """Scan an uploaded file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    f = request.files['file']
    safe_name = sanitize_filename(f.filename)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f'_{safe_name}')
    f.save(tmp.name)
    tmp.close()

    try:
        # Signature scan
        findings = state.detector.scan_file(tmp.name)

        # ML scan
        ml_result = None
        if state.model.is_loaded:
            try:
                feats = extract_features_from_file(tmp.name)
                ml_result = state.model.predict_single(feats)
                # Boost ML score when rule-based findings exist
                if findings:
                    sev_map = {'critical': 95, 'high': 80, 'warning': 50, 'info': 20}
                    max_finding = max(sev_map.get(f2['severity'], 0) for f2 in findings)
                    if max_finding > ml_result.get('risk_score', 0):
                        ml_result['risk_score'] = float(max_finding)
                        ml_result['label'] = 'polyglot'
                        ml_result['risk_level'] = 'critical' if max_finding >= 90 else 'high' if max_finding >= 70 else 'warning' if max_finding >= 40 else 'info'
            except Exception as ml_err:
                logger.warning(f"ML prediction failed: {ml_err}")

        # YARA scan
        try:
            yara_matches, _entropy = state.yara.scan_file(tmp.name)
        except Exception as yr_err:
            logger.warning(f"YARA scan failed: {yr_err}")
            yara_matches = []

        state.stats['scanned'] += 1
        crit = [f2 for f2 in findings if f2['severity'] in ('critical', 'high')]
        if crit or (ml_result and ml_result.get('risk_score', 0) >= 50):
            state.stats['threats'] += 1
            alert = {
                'time': datetime.now().strftime('%H:%M:%S'),
                'file': safe_name,
                'severity': 'critical' if any(f2['severity'] == 'critical' for f2 in crit) else 'high',
                'detail': '; '.join(f2['detail'] for f2 in crit[:3]),
            }
            state.alerts.appendleft(alert)
            # Write to audit log so TUI/CLI/GUI can see it
            try:
                audit_path = os.path.expanduser("~/.polyglot/audit.jsonl")
                os.makedirs(os.path.dirname(audit_path), exist_ok=True)
                import json
                with open(audit_path, "a") as af:
                    for ff in crit:
                        entry = {"time": datetime.now().isoformat(), "file": safe_name,
                                 "severity": ff.get("severity","warning"), "type": ff.get("type",""),
                                 "detail": ff.get("detail",""), "offset": ff.get("offset",0),
                                 "source": "webui"}
                        af.write(json.dumps(entry) + "\n")
            except Exception:
                pass

        result = {
            'filename': safe_name,
            'findings': findings,
            'ml': ml_result,
            'yara_matches': [{'rule': m.rule_name, 'severity': m.severity,
                             'description': m.description, 'offset': m.offset}
                            for m in yara_matches],
            'threat': bool(crit) or (ml_result and ml_result.get('risk_score', 0) >= 50),
        }
        return jsonify(result)
    finally:
        os.unlink(tmp.name)

@app.route('/api/scan/dir', methods=['POST'])
@require_api_key
def api_scan_dir():
    """Scan a directory."""
    data = request.get_json() or {}
    directory = data.get('path', '')
    directory = os.path.expanduser(directory) if directory else directory
    safe_dir = safe_resolve_path(directory)
    if not directory or not safe_dir or not os.path.isdir(safe_dir):
        return jsonify({'error': 'Invalid or blocked directory path'}), 400

    exts = {'.jpg','.jpeg','.png','.gif','.bmp','.pdf','.doc','.docx',
            '.zip','.exe','.dll','.bat','.cmd','.ps1','.vbs','.js','.mp4'}
    files = []
    for root, dirs, fnames in os.walk(safe_dir):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in fnames:
            if os.path.splitext(f)[1].lower() in exts:
                files.append(os.path.join(root, f))

    results = []
    threats = 0
    for fpath in files[:100]:  # Limit to 100 files per request
        findings = state.detector.scan_file(fpath)
        crit = [f for f in findings if f['severity'] in ('critical', 'high')]
        if crit:
            threats += 1  # Count files, not findings
        results.append({
            'file': os.path.basename(fpath),
            'path': fpath,
            'findings': len(findings),
            'critical': len(crit),
            'threat': bool(crit),
        })

    state.stats['scanned'] += len(results)
    state.stats['threats'] += threats

    return jsonify({
        'directory': directory,
        'total': len(results),
        'threats': threats,
        'results': results,
    })

@app.route('/api/sanitize', methods=['POST'])
@require_api_key
def api_sanitize():
    """Sanitize an uploaded file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    f = request.files['file']
    backup = request.form.get('backup', 'true') == 'true'
    safe_name = sanitize_filename(f.filename)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f'_{safe_name}')
    f.save(tmp.name)
    tmp.close()

    try:
        result = state.sanitizer.sanitize(tmp.name, backup)
        state.stats['sanitized'] += 1 if result['status'] == 'sanitized' else 0
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try: os.unlink(tmp.name)
        except: pass

@app.route('/api/build', methods=['POST'])
@require_api_key
def api_build():
    """Build a polyglot file. Supports both JSON and FormData."""
    # Handle FormData (file uploads from dashboard)
    if request.content_type and 'multipart' in request.content_type:
        cover_file = request.files.get('cover')
        payload_file = request.files.get('payload')
        if not cover_file or not payload_file:
            return jsonify({'error': 'Cover and payload files required'}), 400
        cover_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f'_{sanitize_filename(cover_file.filename)}')
        cover_file.save(cover_tmp.name); cover_tmp.close()
        payload_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f'_{sanitize_filename(payload_file.filename)}')
        payload_file.save(payload_tmp.name); payload_tmp.close()
        cover, payload = cover_tmp.name, payload_tmp.name
        container = request.form.get('container_type', 'jpeg')
        payload_type = request.form.get('payload_type', '') or None
        target_os = request.form.get('target_os', 'windows')
        arch = request.form.get('arch', 'x86-64').lower()
        encrypt = request.form.get('encrypt', 'false') == 'true'
        fud = request.form.get('fud', 'false') == 'true'
        mime = request.form.get('mime', 'false') == 'true'
        stealth = request.form.get('stealth', 'false') == 'true'
        # Validate container type — whitelist only
        allowed_containers = {'jpeg','jpg','png','gif','bmp','pdf','zip','docx','xlsx','mp4','webm'}
        if container not in allowed_containers:
            return jsonify({'error': f'Invalid container: {container}'}), 400
        allowed_os = {'windows','macos','linux'}
        if target_os not in allowed_os:
            return jsonify({'error': f'Invalid target_os: {target_os}'}), 400
        allowed_archs = {'x86-64','arm64','arm32'}
        if arch not in allowed_archs:
            return jsonify({'error': f'Invalid arch: {arch}. Valid: {",".join(allowed_archs)}'}), 400
        if arch == 'arm32' and target_os != 'linux':
            return jsonify({'error': 'ARM32 only supported on Linux'}), 400
        # Sanitize output filename
        safe_output = sanitize_filename(f'polyglot_output.{container}')
        output = safe_output
    else:
        data = request.get_json() or {}
        cover = data.get('cover', '')
        payload = data.get('payload', '')
        container = data.get('container', data.get('container_type', 'jpeg'))
        payload_type = data.get('payload_type', None)
        target_os = data.get('target_os', 'windows')
        arch = data.get('arch', 'x86-64').lower()
        encrypt = data.get('encrypt', False)
        fud = data.get('fud', False)
        mime = data.get('mime', False)
        stealth = data.get('stealth', False)
        # Validate container, OS, and arch
        allowed_containers = {'jpeg','jpg','png','gif','bmp','pdf','zip','docx','xlsx','mp4','webm'}
        if container not in allowed_containers:
            return jsonify({'error': f'Invalid container: {container}'}), 400
        allowed_os = {'windows','macos','linux'}
        if target_os not in allowed_os:
            return jsonify({'error': f'Invalid target_os: {target_os}'}), 400
        allowed_archs = {'x86-64','arm64','arm32'}
        if arch not in allowed_archs:
            return jsonify({'error': f'Invalid arch: {arch}. Valid: {",".join(allowed_archs)}'}), 400
        if arch == 'arm32' and target_os != 'linux':
            return jsonify({'error': 'ARM32 only supported on Linux'}), 400
        output = sanitize_filename(data.get('output', f'polyglot.{container}'))

    # Validate paths
    safe_cover = safe_resolve_path(cover)
    safe_payload = safe_resolve_path(payload)
    if not safe_cover or not os.path.isfile(safe_cover):
        return jsonify({'error': 'Invalid cover file'}), 400
    if not safe_payload or not os.path.isfile(safe_payload):
        return jsonify({'error': 'Invalid payload file'}), 400

    try:
        stats = state.builder.build(safe_cover, safe_payload, output, container, encrypt, fud, mime,
                                     payload_type=payload_type, target_os=target_os,
                                     arch=arch, stealth=stealth)
        state.stats['built'] += 1
        # Generate a temp ID for download
        import uuid
        dl_id = str(uuid.uuid4())[:8]
        if not hasattr(state, 'build_downloads'):
            state.build_downloads = {}
        state.build_downloads[dl_id] = output
        stats['download_url'] = f'/api/build/download/{dl_id}'
        stats['download_name'] = f'polyglot.{container}'
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        # Clean up temp files from multipart uploads
        if request.content_type and 'multipart' in request.content_type:
            for tmp_path in [cover, payload]:
                try:
                    if tmp_path and tmp_path.startswith(tempfile.gettempdir()):
                        os.unlink(tmp_path)
                except: pass

@app.route('/api/build/download/<dl_id>')
@require_api_key
def api_build_download(dl_id):
    """Download a built polyglot file."""
    if not hasattr(state, 'build_downloads') or dl_id not in state.build_downloads:
        return jsonify({'error': 'Download not found or expired'}), 404
    filepath = state.build_downloads[dl_id]
    if not os.path.exists(filepath):
        del state.build_downloads[dl_id]
        return jsonify({'error': 'File not found'}), 404
    from flask import send_file
    import threading
    def cleanup():
        import time
        time.sleep(60)  # Clean up after 60 seconds
        try:
            if os.path.exists(filepath): os.unlink(filepath)
        except: pass
        if dl_id in state.build_downloads:
            del state.build_downloads[dl_id]
    threading.Thread(target=cleanup, daemon=True).start()
    return send_file(filepath, as_attachment=True,
                     download_name=f'polyglot.{filepath.split(".")[-1]}',
                     mimetype='application/octet-stream')

@app.route('/api/quarantine')
def api_quarantine():
    """List quarantined files."""
    items = state.quarantine.list_quarantined()
    return jsonify({'items': items, 'total': len(items)})

@app.route('/api/quarantine/add', methods=['POST'])
@require_api_key
def api_quarantine_add():
    """Quarantine a file by path."""
    data = request.get_json() or {}
    filepath = data.get('path', '')
    if not filepath:
        return jsonify({'error': 'Missing path'}), 400
    safe_path = safe_resolve_path(filepath)
    if not safe_path or not os.path.exists(safe_path):
        return jsonify({'error': 'File not found or path blocked'}), 404
    # Scan the file first
    findings = state.detector.scan_file(safe_path)
    sev_map = {'critical': 95, 'high': 80, 'warning': 50, 'info': 20, 'error': 0}
    max_sev = max((sev_map.get(f.get('severity', 'info'), 0) for f in findings), default=0)
    max_sev_name = 'CRITICAL' if max_sev >= 90 else 'HIGH' if max_sev >= 70 else 'MEDIUM' if max_sev >= 40 else 'LOW'
    sorted_f = sorted(findings, key=lambda f: sev_map.get(f.get('severity','info'),0), reverse=True)
    primary_label = sorted_f[0].get('type','UNKNOWN') if sorted_f else 'UNKNOWN'
    scan_result = {
        'label': primary_label, 'confidence': max_sev/100.0,
        'risk_score': float(max_sev), 'risk_level': max_sev_name,
        'yara_matches': [], 'detected_types': list({f.get('type','UNKNOWN') for f in findings}),
    }
    qid = state.quarantine.quarantine(safe_path, scan_result, force=True)
    if qid:
        return jsonify({'quarantine_id': qid, 'file': os.path.basename(filepath)})
    return jsonify({'error': 'Quarantine failed'}), 500

@app.route('/api/quarantine/delete', methods=['POST'])
@require_api_key
def api_quarantine_delete():
    """Permanently delete a quarantined file."""
    data = request.get_json() or {}
    qid = data.get('id', '')
    if not qid:
        return jsonify({'error': 'Missing quarantine ID'}), 400
    if state.quarantine.delete(qid):
        return jsonify({'deleted': qid})
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/quarantine/restore', methods=['POST'])
@require_api_key
def api_quarantine_restore():
    """Restore a quarantined file."""
    data = request.get_json() or {}
    qid = data.get('id', '')
    dest = data.get('dest', '')
    if not qid:
        return jsonify({'error': 'Missing quarantine ID'}), 400
    result = state.quarantine.restore(qid, dest or None)
    if result:
        return jsonify({'restored': result})
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/yara/rules')
def api_yara_rules():
    """List YARA rules."""
    rules = []
    for r in state.yara.rules:
        rules.append({
            'name': r.name, 'severity': r.severity,
            'description': r.description,
            'patterns': len(r.patterns) + len(r.regex_patterns),
        })
    return jsonify({'rules': rules, 'total': len(rules)})

@app.route('/api/stats')
def api_stats():
    """Dashboard statistics."""
    return jsonify(state.stats)

@app.route('/api/alerts')
def api_alerts():
    """Recent alerts."""
    return jsonify({'alerts': list(state.alerts)[:50]})

@app.route('/api/train', methods=['POST'])
@require_api_key
def api_train():
    """Train the ML model."""
    data = request.get_json() or {}
    n_samples = data.get('samples', 50)
    use_gpu = data.get('use_gpu', True)

    # Validate n_samples is a positive integer
    try:
        n_samples = int(n_samples)
        if n_samples < 1 or n_samples > 100000:
            return jsonify({'error': 'samples must be 1-100000'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'samples must be a positive integer'}), 400

    try:
        import subprocess as sp
        device_flag = '--gpu' if use_gpu else '--cpu'
        cmd = [sys.executable, 'train_model.py', '--samples', str(n_samples), device_flag]
        result = sp.run(cmd, capture_output=True, text=True, timeout=600,
                       cwd=os.path.dirname(os.path.abspath(__file__)))
        # Parse output for accuracy
        output = result.stdout + result.stderr
        accuracy = None
        benign_recall = None
        malicious_recall = None
        for line in output.split('\n'):
            if 'Accuracy' in line and '%' in line:
                try: accuracy = float(line.split('%')[0].split()[-1])
                except: pass
            if 'Benign recall' in line and '%' in line:
                try: benign_recall = float(line.split('%')[0].split()[-1])
                except: pass
            if 'Malicious recall' in line and '%' in line:
                try: malicious_recall = float(line.split('%')[0].split()[-1])
                except: pass
        # Reload model
        try:
            model_path = os.path.join('models', 'polyglot_shield.cbm')
            if os.path.exists(model_path):
                state.model.load(model_path)
        except: pass
        return jsonify({
            'status': 'success',
            'accuracy': accuracy,
            'benign_recall': benign_recall,
            'malicious_recall': malicious_recall,
            'train_samples': n_samples * 87,  # 87 types
            'output': output[-2000:],
        })
    except sp.TimeoutExpired:
        return jsonify({'error': 'Training timed out (10min limit)'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/monitor/start', methods=['POST'])
@require_api_key
def api_monitor_start():
    """Start directory monitor."""
    data = request.get_json() or {}
    directory = data.get('path', str(Path.home() / "Downloads"))
    directory = os.path.expanduser(directory)
    safe_dir = safe_resolve_path(directory)
    if not safe_dir or not os.path.isdir(safe_dir):
        return jsonify({'error': 'Invalid or blocked directory'}), 400

    from engines.monitor import FolderMonitor, HAS_WATCHDOG
    if not HAS_WATCHDOG:
        return jsonify({'error': 'watchdog not installed'}), 500

    # Use threading for non-blocking monitor (no QThread in Flask)
    import threading
    from polyglot_tui import PolyglotDetector

    if state.monitor_running:
        return jsonify({'error': 'Monitor already running'}), 400

    detector = PolyglotDetector()
    file_hashes = {}

    def _monitor_loop():
        exts = {'.jpg','.jpeg','.png','.gif','.bmp','.pdf','.doc','.docx',
                '.zip','.exe','.dll','.scr','.bat','.cmd','.ps1','.vbs',
                '.js','.hta','.lnk','.elf','.so','.mp4'}
        while getattr(state, 'monitor_running', False):
            try:
                for root, dirs, files in os.walk(safe_dir):
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    for fname in files:
                        if not state.monitor_running: return
                        if os.path.splitext(fname)[1].lower() not in exts: continue
                        fpath = os.path.join(root, fname)
                        try:
                            st = os.stat(fpath); cur = (st.st_mtime, st.st_size)
                        except: continue
                        prev = file_hashes.get(fpath)
                        if prev is None or prev != cur:
                            file_hashes[fpath] = cur
                            try:
                                findings = detector.scan_file(fpath)
                                crit = [f for f in findings if f['severity'] in ('critical','high')]
                                if crit:
                                    state.stats['threats'] += 1
                                    state.alerts.appendleft({
                                        'time': time.strftime('%H:%M:%S'),
                                        'file': fname, 'severity': 'critical',
                                        'detail': '; '.join(f['detail'] for f in crit[:3])
                                    })
                                state.stats['scanned'] += 1
                            except: pass
                time.sleep(3)
            except: time.sleep(5)

    state.monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
    state.monitor_thread.start()
    state.monitor_running = True

    return jsonify({'status': 'started', 'directory': directory})

@app.route('/api/monitor/stop', methods=['POST'])
@require_api_key
def api_monitor_stop():
    """Stop directory monitor."""
    if state.monitor_running:
        state.monitor_running = False
        return jsonify({'status': 'stopped'})
    return jsonify({'error': 'Monitor not running'}), 400


# ── Web Dashboard (embedded HTML) ────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>PolyglotShield v3.0 — Server Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0e14;color:#c5d0db;font-family:'Segoe UI',system-ui,-apple-system,sans-serif;font-size:15px}
.header{background:#111822;padding:16px 20px;border-bottom:1px solid #1e2d3d;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px}
.header h1{color:#ff3333;font-size:18px;font-family:Consolas,monospace}
.header .status{color:#22cc55;font-size:13px}
.container{max-width:1200px;margin:0 auto;padding:12px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin:12px 0}
.stat{background:#1a2233;border:1px solid #1e2d3d;border-radius:10px;padding:14px;text-align:center}
.stat .icon{font-size:22px}.stat .value{font-size:26px;font-weight:bold;font-family:Consolas,monospace;margin:4px 0}
.stat .label{color:#556677;font-size:10px;text-transform:uppercase;letter-spacing:1px}
.stat.blue .value{color:#3399ff}.stat.red .value{color:#ff3333}
.stat.green .value{color:#22cc55}.stat.orange .value{color:#f0883e}
.grid{display:grid;grid-template-columns:1fr;gap:12px;margin:12px 0}
@media(min-width:768px){.grid{grid-template-columns:2fr 1fr}}
.card{background:#1a2233;border:1px solid #1e2d3d;border-radius:10px;padding:14px}
.card h3{color:#3399ff;margin-bottom:10px;font-size:13px}
.btn{background:#ff3333;color:white;border:none;border-radius:6px;padding:12px 20px;font-weight:bold;cursor:pointer;font-size:13px;min-height:44px;width:100%;margin:4px 0}
.btn:hover{opacity:0.85}.btn:active{transform:scale(0.98)}
.btn.green{background:#22cc55}.btn.blue{background:#3399ff}.btn.dim{background:#556677}
.btn:disabled{opacity:0.5;cursor:not-allowed}
.btn-row{display:flex;gap:8px;margin:4px 0}
.btn-row .btn{flex:1}
input[type=file],input[type=text]{background:#0d1520;color:#c5d0db;border:1px solid #1e2d3d;border-radius:6px;padding:12px;font-family:Consolas,monospace;width:100%;margin:4px 0;font-size:14px}
label.chk{display:flex;align-items:center;gap:6px;font-size:13px;color:#c5d0db;margin:6px 0;cursor:pointer}
label.chk input{width:18px;height:18px;accent-color:#3399ff}
.alert{padding:8px 10px;border-left:3px solid #ff3333;margin:4px 0;background:#1a2233;border-radius:0 6px 6px 0;font-size:11px;font-family:Consolas,monospace;word-break:break-word}
.alert.high{border-color:#f0883e}.alert.warning{border-color:#ddaa22}
pre{background:#0d1520;padding:10px;border-radius:8px;font-size:11px;overflow-x:auto;max-height:350px;overflow-y:auto;white-space:pre-wrap;word-break:break-word}
table{width:100%;border-collapse:collapse;font-size:12px}th,td{padding:6px 8px;text-align:left;border-bottom:1px solid #1e2d3d}
th{color:#3399ff;font-weight:bold}.threat{color:#ff3333}.clean{color:#22cc55}
.spinner{display:inline-block;width:14px;height:14px;border:2px solid #556677;border-top-color:#3399ff;border-radius:50%;animation:spin .6s linear infinite;margin-right:6px;vertical-align:middle}
@keyframes spin{to{transform:rotate(360deg)}}
.toast{position:fixed;bottom:20px;right:20px;background:#1a2233;border:1px solid #3399ff;border-radius:8px;padding:12px 18px;font-size:13px;z-index:999;opacity:0;transition:opacity .3s;max-width:90vw}
.toast.show{opacity:1}.toast.error{border-color:#ff3333}.toast.success{border-color:#22cc55}
hr{border-color:#1e2d3d;margin:12px 0}
</style>
</head>
<body>
<div class="header">
  <h1>&diams; POLYGLOTSHIELD v3.0</h1>
  <span class="status" id="status">&#9679; Connecting...</span>
</div>
<div class="container">
  <div class="stats">
    <div class="stat blue"><div class="icon">&#128269;</div><div class="value" id="s-scanned">0</div><div class="label">Scanned</div></div>
    <div class="stat red"><div class="icon">&#9888;</div><div class="value" id="s-threats">0</div><div class="label">Threats</div></div>
    <div class="stat green"><div class="icon">&#128737;</div><div class="value" id="s-sanitized">0</div><div class="label">Sanitized</div></div>
    <div class="stat orange"><div class="icon">&#9670;</div><div class="value" id="s-built">0</div><div class="label">Built</div></div>
  </div>

  <div id="alerts" style="margin-top:12px"></div>

  <div class="grid">
    <div class="card">
      <h3>&#9888; File Scanner</h3>
      <input type="file" id="scan-file">
      <button class="btn" onclick="scanFile()" id="btn-scan">&#9888; SCAN FILE</button>

      <hr>
      <h3>&#128737; Sanitizer</h3>
      <input type="file" id="san-file">
      <label class="chk"><input type="checkbox" id="san-dryrun"> Dry-run (preview only)</label>
      <button class="btn green" onclick="sanFile()" id="btn-san">&#128737; SANITIZE</button>

      <hr>
      <h3>&#9654; Directory Scanner</h3>
      <input type="text" id="scan-dir" placeholder="/path/to/scan">
      <button class="btn blue" onclick="scanDir()" id="btn-dir">&#9654; SCAN DIRECTORY</button>

      <hr>
      <h3>&#128065; Monitor</h3>
      <input type="text" id="mon-dir" placeholder="~/Downloads">
      <div class="btn-row">
        <button class="btn green" onclick="startMon()">&#9654; START</button>
        <button class="btn dim" onclick="stopMon()">&#9632; STOP</button>
      </div>

      <hr>
      <h3>&#128274; Recovery</h3>
      <input type="text" id="recover-dir" placeholder="/path/to/search">
      <button class="btn blue" onclick="recoverFiles()" id="btn-rec">&#128260; RESTORE .BAK FILES</button>
    </div>

    <div class="card">
      <h3>&#128295; Polyglot Builder</h3>
      <label class="chk" style="font-size:11px;color:#556677">Cover file (image/document)</label>
      <input type="file" id="build-cover">
      <label class="chk" style="font-size:11px;color:#556677">Payload file</label>
      <input type="file" id="build-payload">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:6px 0">
        <select id="build-container" style="background:#0d1520;color:#c5d0db;border:1px solid #1e2d3d;border-radius:6px;padding:8px;font-size:12px">
          <option value="jpeg">JPEG</option><option value="png">PNG</option><option value="gif">GIF</option>
          <option value="pdf">PDF</option><option value="zip">ZIP</option><option value="mp4">MP4</option>
          <option value="xlsx">XLSX</option><option value="docx">DOCX</option>
        </select>
        <select id="build-payload-type" style="background:#0d1520;color:#c5d0db;border:1px solid #1e2d3d;border-radius:6px;padding:8px;font-size:12px">
          <option value="">exe (raw)</option>
          <option value="bash">bash (Linux/macOS)</option><option value="sh">sh (POSIX)</option>
          <option value="python">python (All OS)</option><option value="applescript">AppleScript (macOS)</option>
          <option value="vbs">VBS (Windows)</option><option value="ps1">PS1 (Windows)</option>
          <option value="xlsx">Excel Macro</option><option value="docx">Word Macro</option>
        </select>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:4px 0">
        <select id="build-target-os" style="background:#0d1520;color:#c5d0db;border:1px solid #1e2d3d;border-radius:6px;padding:8px;font-size:12px;width:100%">
          <option value="windows">Target: Windows</option><option value="linux">Target: Linux</option>
          <option value="macos">Target: macOS</option><option value="all">Target: All (3 variants)</option>
        </select>
        <select id="build-arch" style="background:#0d1520;color:#c5d0db;border:1px solid #1e2d3d;border-radius:6px;padding:8px;font-size:12px;width:100%">
          <option value="x86-64">Arch: x86-64</option><option value="arm64">Arch: ARM64 (AArch64)</option>
          <option value="arm32">Arch: ARM32 (Linux only)</option>
        </select>
      </div>
      <div style="display:flex;gap:6px;margin:6px 0">
        <label class="chk"><input type="checkbox" id="build-encrypt"> Encrypt</label>
        <label class="chk"><input type="checkbox" id="build-fud"> FUD</label>
        <label class="chk"><input type="checkbox" id="build-mime"> MIME</label>
        <label class="chk"><input type="checkbox" id="build-stealth"> Stealth</label>
      </div>
      <button class="btn orange" onclick="buildPolyglot()" id="btn-build">&#9889; BUILD POLYGLOT</button>

      <hr>
      <h3>&#129504; ML Training</h3>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:6px 0">
        <div>
          <label class="chk" style="font-size:11px;color:#556677">Samples per type</label>
          <input type="number" id="train-samples" value="50" min="10" max="500" style="background:#0d1520;color:#c5d0db;border:1px solid #1e2d3d;border-radius:6px;padding:8px;font-size:12px;width:100%">
        </div>
        <div>
          <label class="chk" style="font-size:11px;color:#556677">Compute</label>
          <select id="train-device" style="background:#0d1520;color:#c5d0db;border:1px solid #1e2d3d;border-radius:6px;padding:8px;font-size:12px;width:100%">
            <option value="GPU">GPU (CUDA)</option><option value="CPU">CPU</option>
          </select>
        </div>
      </div>
      <button class="btn blue" onclick="trainModel()" id="btn-train">&#129504; TRAIN MODEL</button>
      <div id="train-status" style="margin-top:6px;font-size:11px;color:#556677"></div>

      <hr>
      <h3>&#128203; YARA Rules</h3>
      <div style="overflow-x:auto">
        <table id="builder-yara-table"><thead><tr><th>Rule</th><th>Severity</th><th>Description</th></tr></thead><tbody></tbody></table>
      </div>
    </div>
  </div>

  <div class="card" style="margin-top:12px">
    <h3>&#128202; Results</h3>
    <pre id="results">No scans yet.</pre>
  </div>

  <div class="card" style="margin-top:12px">
    <h3>&#128203; YARA Rules</h3>
    <div style="overflow-x:auto">
      <table id="yara-table"><thead><tr><th>Rule</th><th>Severity</th><th>Description</th></tr></thead><tbody></tbody></table>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
function escHtml(s){if(!s)return'';return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function showToast(msg,type='info'){
  const t=document.getElementById('toast');
  t.textContent=msg;t.className='toast show '+(type||'');
  setTimeout(()=>t.className='toast',3000);
}
function setLoading(id,on){
  const b=document.getElementById(id);if(!b)return;
  if(on){b.disabled=true;b.dataset.orig=b.innerHTML;b.innerHTML='<span class="spinner"></span> Processing...'}
  else{b.disabled=false;if(b.dataset.orig)b.innerHTML=b.dataset.orig;}
}
async function api(path,opts){
  try{const r=await fetch('/api/'+path,opts);if(!r.ok)throw new Error(r.statusText);return r.json()}
  catch(e){showToast('API error: '+e.message,'error');throw e}
}
async function refresh(){
  try{
    const [s,a,st]=await Promise.all([api('stats'),api('alerts'),api('status')]);
    document.getElementById('s-scanned').textContent=s.scanned||0;
    document.getElementById('s-threats').textContent=s.threats||0;
    document.getElementById('s-sanitized').textContent=s.sanitized||0;
    document.getElementById('s-built').textContent=s.built||0;
    const el=document.getElementById('alerts');
    if(el&&a.alerts&&a.alerts.length){
      el.innerHTML=a.alerts.map(x=>`<div class="alert ${x.severity||''}">[${escHtml(x.time||'')}] ${escHtml(x.file||'')}: ${escHtml(x.detail||'')}</div>`).join('');
    }
    document.getElementById('status').innerHTML='&#9679; '+(st.model_loaded?'ML Loaded':'No Model');
    document.getElementById('status').style.color=st.model_loaded?'#22cc55':'#ddaa22';
  }catch(e){}
}
async function scanFile(){
  const f=document.getElementById('scan-file').files[0];if(!f){showToast('Select a file first','error');return}
  setLoading('btn-scan',true);
  try{
    const fd=new FormData();fd.append('file',f);
    const r=await fetch('/api/scan',{method:'POST',body:fd}).then(r=>r.json());
    // Build rich result display with ML confidence
    let html='<div style="margin:8px 0">';
    html+='<div style="font-size:16px;font-weight:bold;margin-bottom:8px">Scan: '+escHtml(r.filename)+'</div>';
    // ML Result with confidence bar
    if(r.ml){
      const pct=Math.round(r.ml.confidence*100);
      const risk=Math.round(r.ml.risk_score||0);
      const color=risk>=80?'#ff3333':risk>=60?'#f0883e':risk>=40?'#ddaa22':'#22cc55';
      html+='<div style="background:#0d1520;border-radius:8px;padding:12px;margin:8px 0">';
      html+='<div style="display:flex;justify-content:space-between;margin-bottom:6px"><span>ML Prediction: <b style="color:'+color+'">'+escHtml(r.ml.label.toUpperCase())+'</b></span><span>Confidence: <b>'+pct+'%</b></span></div>';
      html+='<div style="background:#1e2d3d;border-radius:4px;height:20px;overflow:hidden"><div style="background:'+color+';height:100%;width:'+pct+'%;transition:width 0.5s;border-radius:4px"></div></div>';
      html+='<div style="display:flex;justify-content:space-between;margin-top:6px;font-size:12px;color:#556677"><span>Risk Score: <b style="color:'+color+'">'+risk+'/100</b></span><span>Risk Level: <b>'+escHtml(r.ml.risk_level||'N/A')+'</b></span></div>';
      html+='<div style="font-size:11px;color:#556677;margin-top:4px">Polyglot Prob: '+((r.ml.polyglot_probability||0)*100).toFixed(1)+'% | Benign Prob: '+((r.ml.benign_probability||0)*100).toFixed(1)+'%</div>';
      html+='</div>';
    } else {
      html+='<div class="alert warning">ML model not loaded — rule-based detection only</div>';
    }
    // YARA matches
    if(r.yara_matches&&r.yara_matches.length){
      html+='<div style="margin:8px 0"><b style="color:#3399ff">YARA Rules Matched ('+r.yara_matches.length+')</b></div>';
      r.yara_matches.forEach(m=>{
        const sev=m.severity==='critical'?'#ff3333':m.severity==='high'?'#f0883e':'#ddaa22';
        html+='<div class="alert" style="border-color:'+sev+'"><b>'+escHtml(m.rule)+'</b> ['+escHtml((m.severity||'').toUpperCase())+'] — '+escHtml(m.description||'')+'</div>';
      });
    }
    // Findings
    if(r.findings&&r.findings.length){
      html+='<div style="margin:8px 0"><b style="color:#f0883e">Findings ('+r.findings.length+')</b></div>';
      r.findings.forEach(f2=>{
        html+='<div class="alert '+((f2.severity==='critical'||f2.severity==='high')?'':'high')+'">'+escHtml(f2.detail||'')+'</div>';
      });
    }
    // Verdict
    const verdict=r.threat?'THREAT DETECTED':'CLEAN';
    const vc=r.threat?'#ff3333':'#22cc55';
    html+='<div style="text-align:center;padding:12px;margin-top:8px;font-size:20px;font-weight:bold;color:'+vc+';border:2px solid '+vc+';border-radius:8px">'+verdict+'</div>';
    html+='</div>';
    document.getElementById('results').innerHTML=html;
    showToast(r.threat?'Threat detected!':'File clean',r.threat?'error':'success');
  }catch(e){showToast('Scan failed: '+e.message,'error')}
  finally{setLoading('btn-scan',false);refresh()}
}
async function sanFile(){
  const f=document.getElementById('san-file').files[0];if(!f){showToast('Select a file first','error');return}
  setLoading('btn-san',true);
  try{
    const fd=new FormData();fd.append('file',f);
    fd.append('backup','true');
    const r=await fetch('/api/sanitize',{method:'POST',body:fd}).then(r=>r.json());
    document.getElementById('results').textContent=JSON.stringify(r,null,2);
    showToast(r.status==='sanitized'?'Sanitized: '+r.detail:'No threats found','success');
  }catch(e){showToast('Sanitize failed: '+e.message,'error')}
  finally{setLoading('btn-san',false);refresh()}
}
async function scanDir(){
  const d=document.getElementById('scan-dir').value;if(!d){showToast('Enter a directory path','error');return}
  setLoading('btn-dir',true);
  try{
    const r=await api('scan/dir',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:d})});
    document.getElementById('results').textContent=JSON.stringify(r,null,2);
    showToast(r.threats?r.threats+' threats found':'All clean',r.threats?'error':'success');
  }catch(e){showToast('Scan failed: '+e.message,'error')}
  finally{setLoading('btn-dir',false);refresh()}
}
async function startMon(){
  const d=document.getElementById('mon-dir').value||'~/Downloads';
  try{await api('monitor/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:d})});
  showToast('Monitor started','success');}catch(e){showToast('Monitor failed: '+e.message,'error')}
  refresh();
}
async function stopMon(){
  try{await api('monitor/stop',{method:'POST'});showToast('Monitor stopped','success')}
  catch(e){showToast('Stop failed: '+e.message,'error')}
  refresh();
}
async function recoverFiles(){
  const d=document.getElementById('recover-dir').value;if(!d){showToast('Enter a directory path','error');return}
  setLoading('btn-rec',true);
  try{
    const r=await api('quarantine');
    if(r.items&&r.items.length){
      let restored=0;
      for(const item of r.items){
        try{await api('quarantine/restore',{method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({id:item.quarantine_id, dest:d})});restored++}catch(e){}
      }
      document.getElementById('results').textContent='Restored '+restored+'/'+r.total+' quarantined files';
      showToast('Restored '+restored+' files','success');
    }else{
      document.getElementById('results').textContent='No quarantined files found.';
      showToast('No quarantined files','info');
    }
  }catch(e){showToast('Recovery failed: '+e.message,'error')}
  finally{setLoading('btn-rec',false);refresh()}
}
async function loadYara(){
  try{
    const r=await api('yara/rules');
    const tb=document.querySelector('#yara-table tbody');
    if(r.rules&&r.rules.length){
      tb.innerHTML=r.rules.map(x=>`<tr><td>${escHtml(x.name)}</td><td class="${x.severity==='critical'?'threat':''}">${escHtml((x.severity||'').toUpperCase())}</td><td>${escHtml(x.description||'')}</td></tr>`).join('');
    }
  }catch(e){}
}
refresh();loadYara();setInterval(refresh,5000);

async function buildPolyglot(){
  const cover=document.getElementById('build-cover').files[0];
  const payload=document.getElementById('build-payload').files[0];
  if(!cover||!payload){showToast('Select cover and payload files','error');return}
  setLoading('btn-build',true);
  try{
    const fd=new FormData();
    fd.append('cover',cover);fd.append('payload',payload);
    fd.append('container_type',document.getElementById('build-container').value);
    fd.append('payload_type',document.getElementById('build-payload-type').value);
    fd.append('target_os',document.getElementById('build-target-os').value);
    fd.append('arch',document.getElementById('build-arch').value);
    fd.append('encrypt',document.getElementById('build-encrypt').checked);
    fd.append('fud',document.getElementById('build-fud').checked);
    fd.append('mime',document.getElementById('build-mime').checked);
    fd.append('stealth',document.getElementById('build-stealth').checked);
    const r=await fetch('/api/build',{method:'POST',body:fd}).then(r=>r.json());
    if(r.error){showToast('Build error: '+r.error,'error');return}
    let html='<div style="margin:8px 0">';
    html+='<div style="font-size:16px;font-weight:bold;color:#22cc55;margin-bottom:8px">Build Successful</div>';
    html+='<div style="background:#0d1520;border-radius:8px;padding:12px;font-family:Consolas,monospace;font-size:12px">';
    html+='<div>Container: <b>'+escHtml(r.container_type)+'</b></div>';
    if(r.payload_type)html+='<div>Payload Type: <b>'+escHtml(r.payload_type)+'</b></div>';
    html+='<div>Cover Size: <b>'+Number(r.cover_size).toLocaleString()+'</b> bytes</div>';
    html+='<div>Payload Size: <b>'+Number(r.payload_size).toLocaleString()+'</b> bytes</div>';
    html+='<div>Output Size: <b>'+Number(r.output_size).toLocaleString()+'</b> bytes</div>';
    html+='<div>Offset: <b>0x'+(r.payload_offset||0).toString(16).toUpperCase()+'</b></div>';
    html+='<div>Entropy: <b>'+r.entropy+'</b></div>';
    html+='<div>Encrypted: <b>'+(r.encrypted?'Yes':'No')+'</b> | FUD: <b>'+(r.fud_protected?'Yes':'No')+'</b> | MIME: <b>'+(r.mime_confused?'Yes':'No')+'</b></div>';
    html+='</div></div>';
    document.getElementById('results').innerHTML=html;
    showToast('Polyglot built successfully','success');
    // Auto-download the built file
    if(r.download_url){
      const a=document.createElement('a');
      a.href=r.download_url;
      a.download=r.download_name||'polyglot.bin';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
  }catch(e){showToast('Build failed: '+e.message,'error')}
  finally{setLoading('btn-build',false);refresh()}
}

async function trainModel(){
  const samples=parseInt(document.getElementById('train-samples').value)||50;
  const device=document.getElementById('train-device').value;
  setLoading('btn-train',true);
  document.getElementById('train-status').innerHTML='<span class="spinner"></span> Training model... This may take a few minutes.';
  try{
    const r=await api('train',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({samples:samples,use_gpu:device==='GPU'})});
    let html='<div style="background:#0d1520;border-radius:8px;padding:12px;font-size:12px;margin-top:8px">';
    html+='<div style="color:#22cc55;font-weight:bold">Training Complete</div>';
    if(r.accuracy)html+='<div>Accuracy: <b>'+r.accuracy+'%</b></div>';
    if(r.benign_recall)html+='<div>Benign Recall: <b>'+r.benign_recall+'%</b></div>';
    if(r.malicious_recall)html+='<div>Malicious Recall: <b>'+r.malicious_recall+'%</b></div>';
    if(r.train_samples)html+='<div>Training Samples: <b>'+r.train_samples+'</b></div>';
    if(r.training_time_sec)html+='<div>Training Time: <b>'+r.training_time_sec+'s</b></div>';
    html+='</div>';
    document.getElementById('train-status').innerHTML=html;
    showToast('Model trained successfully','success');
    refresh();
  }catch(e){document.getElementById('train-status').innerHTML='<div class="alert">Training failed: '+escHtml(e.message)+'</div>';showToast('Training failed','error')}
  finally{setLoading('btn-train',false)}
}
</script>
</body></html>"""


# ── Entry Point ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PolyglotShield Server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address")
    parser.add_argument("--port", type=int, default=8888, help="Port")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  POLYGLOTSHIELD v3.0 — Server Mode                           ║
║  Author: Mr-DS-ML-85                                         ║
╚══════════════════════════════════════════════════════════════╝

  Dashboard:  http://{args.host}:{args.port}
  API:        http://{args.host}:{args.port}/api/status
  Model:      {'Loaded' if state.model.is_loaded else 'Not loaded'}
  YARA Rules: {len(state.yara.rules)}
""")

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
