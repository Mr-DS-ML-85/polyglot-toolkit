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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)
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

@app.errorhandler(Exception)
def handle_exception(e):
    """Global error handler — prevents unhandled crashes."""
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
def api_scan():
    """Scan an uploaded file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    f = request.files['file']
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f'_{f.filename}')
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
                'file': f.filename,
                'severity': 'critical' if any(f2['severity'] == 'critical' for f2 in crit) else 'high',
                'detail': '; '.join(f2['detail'] for f2 in crit[:3]),
            }
            state.alerts.appendleft(alert)

        result = {
            'filename': f.filename,
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
def api_scan_dir():
    """Scan a directory."""
    data = request.get_json() or {}
    directory = data.get('path', '')
    if not directory or not os.path.isdir(directory):
        return jsonify({'error': 'Invalid directory'}), 400

    exts = {'.jpg','.jpeg','.png','.gif','.bmp','.pdf','.doc','.docx',
            '.zip','.exe','.dll','.bat','.cmd','.ps1','.vbs','.js','.mp4'}
    files = []
    for root, dirs, fnames in os.walk(directory):
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
            threats += len(crit)
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
def api_sanitize():
    """Sanitize an uploaded file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    f = request.files['file']
    backup = request.form.get('backup', 'true') == 'true'
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f'_{f.filename}')
    f.save(tmp.name)
    tmp.close()

    try:
        result = state.sanitizer.sanitize(tmp.name, backup)
        state.stats['sanitized'] += 1 if result['status'] == 'sanitized' else 0
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/build', methods=['POST'])
def api_build():
    """Build a polyglot file."""
    data = request.get_json() or {}
    cover = data.get('cover', '')
    payload = data.get('payload', '')
    container = data.get('container', data.get('container_type', 'jpeg'))
    payload_type = data.get('payload_type', None)
    target_os = data.get('target_os', 'windows')
    encrypt = data.get('encrypt', False)
    fud = data.get('fud', False)
    mime = data.get('mime', False)
    output = data.get('output', f'polyglot.{container}')

    if not cover or not os.path.isfile(cover):
        return jsonify({'error': 'Invalid cover file'}), 400
    if not payload or not os.path.isfile(payload):
        return jsonify({'error': 'Invalid payload file'}), 400

    try:
        stats = state.builder.build(cover, payload, output, container, encrypt, fud, mime,
                                     payload_type=payload_type, target_os=target_os)
        state.stats['built'] += 1
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/quarantine')
def api_quarantine():
    """List quarantined files."""
    meta_path = Path(state.config.quarantine.get("dir", "quarantine")) / "metadata.jsonl"
    items = []
    if meta_path.exists():
        with open(meta_path) as f:
            for line in f:
                try:
                    items.append(json.loads(line.strip()))
                except:
                    pass
    return jsonify({'items': items, 'total': len(items)})

@app.route('/api/quarantine/restore', methods=['POST'])
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

@app.route('/api/monitor/start', methods=['POST'])
def api_monitor_start():
    """Start directory monitor."""
    data = request.get_json() or {}
    directory = data.get('path', str(Path.home() / "Downloads"))
    if not os.path.isdir(directory):
        return jsonify({'error': 'Invalid directory'}), 400

    from engines.monitor import FolderMonitor, HAS_WATCHDOG
    if not HAS_WATCHDOG:
        return jsonify({'error': 'watchdog not installed'}), 500

    # Use threading for non-blocking monitor
    import threading
    from polyglot_tui import MonitorWorker

    if state.monitor_running:
        return jsonify({'error': 'Monitor already running'}), 400

    state.monitor_thread = MonitorWorker()
    state.monitor_thread.alert.connect(lambda a: state.alerts.appendleft(a))
    state.monitor_thread.stats.connect(lambda s: state.stats.update(s))
    state.monitor_thread.start_watch(directory)
    state.monitor_running = True

    return jsonify({'status': 'started', 'directory': directory})

@app.route('/api/monitor/stop', methods=['POST'])
def api_monitor_stop():
    """Stop directory monitor."""
    if state.monitor_thread and state.monitor_running:
        state.monitor_thread.stop_watch()
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
      <h3>&#128276; Recent Alerts</h3>
      <div id="alerts" style="max-height:600px;overflow-y:auto"><div class="alert warning">No alerts yet</div></div>
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
    if(a.alerts&&a.alerts.length){
      el.innerHTML=a.alerts.map(x=>`<div class="alert ${x.severity||''}">[${x.time||''}] ${x.file||''}: ${x.detail||''}</div>`).join('');
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
    document.getElementById('results').textContent=JSON.stringify(r,null,2);
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
          body:JSON.stringify({id:item.quarantine_id})});restored++}catch(e){}
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
      tb.innerHTML=r.rules.map(x=>`<tr><td>${x.name}</td><td class="${x.severity==='critical'?'threat':''}">${(x.severity||'').toUpperCase()}</td><td>${x.description||''}</td></tr>`).join('');
    }
  }catch(e){}
}
refresh();loadYara();setInterval(refresh,5000);
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
