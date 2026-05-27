# PolyglotShield v3.0 — Red Team + Shield Edition

> **FOR EDUCATIONAL & AUTHORIZED SECURITY TESTING ONLY**
> Unauthorized use against systems you don't own is illegal.

Red team offensive toolkit + ML-powered defensive shield in one unified application. Build polyglot files, detect hidden threats, monitor directories in real-time, train ML models, run payload evasion, and investigate incidents — all from a single binary with 18 interactive menus.

## Table of Contents

- [Quick Start](#quick-start)
- [Features](#features)
- [TUI Menus (18 Panels)](#tui-menus-18-panels)
- [Engines](#engines)
- [CLI Reference](#cli-reference)
- [API Documentation](#api-documentation)
- [Detection Accuracy](#detection-accuracy)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Credits](#credits)
- [License](#license)

## Quick Start

```bash
# Install
pip install -r requirements.txt

# TUI (Rich terminal) — 18 interactive panels
python polyglot.py

# GUI (PyQt6)
python polyglot.py gui

# CLI
python polyglot.py scan suspicious.jpg
python polyglot.py build cover.jpg payload.exe --type jpeg --fud
python polyglot.py build cover.jpg payload.exe --type jpeg --payload-type ps1 --encrypt --mime

# Cross-platform payloads
python polyglot.py build cover.jpg payload.bin --type jpeg --payload-type bash --target-os linux
python polyglot.py build cover.jpg payload.bin --type jpeg --payload-type python --target-os all

# Server mode (web dashboard + REST API)
python polyglot.py server --port 8888

# Background service
python polyglot.py service install
python polyglot.py service start --dir ~/Downloads
```

## Features

### Builder (Offense)

Build polyglot files that are valid in one format but contain hidden payloads.

**Container Types:** JPEG, PNG, GIF, PDF, ZIP, MP4, XLSX, DOCX

**Payload Types:** `exe`, `vbs`, `ps1`, `bash`, `sh`, `python`, `applescript`, `xlsx`, `docx`

**Target Platform (`--target-os`):** `windows`, `linux`, `macos`, `all`

**Obfuscation Flags:** `--encrypt`, `--fud`, `--mime`, `--payload-type`

### Scanner (Defense)

- ML Detection — CatBoost classifier on 354 features (CPU/GPU)
- YARA Rules — 49 built-in rules targeting RedTeam patterns
- Format Parser Differential Analysis — 104 media formats
- Steganography Detection — LSB, chi-square, histogram, entropy
- PE/ELF Anomaly Analysis — section entropy, packing, import anomalies
- Office Macro Static Analysis — 41 suspicious VBA functions
- Archive Recursion Scanning — bomb detection, container nesting, path traversal

### Sanitizer

Strips trailing payloads from polyglot files with `.bak` backup support.

### Real-Time Monitor

Watchdog-based folder monitoring with auto-scan and desktop notifications.

### Background Service

Systemd/launchd/Scheduled Task daemon for persistent monitoring.

### ML Training

Synthetic data generation (76 polyglot types), CatBoost CPU/GPU training, feature importance analysis.

## TUI Menus (18 Panels)

### Menu 1: Polyglot Builder
Build polyglot files with 8 container types, 9 payload types, 3 obfuscation modes, target OS selection.

### Menu 2: File Detector
ML-powered scan with 354 features, 49 YARA rules, signature scanning, entropy analysis, trailing data detection.

### Menu 3: File Sanitizer
Strip trailing payloads, create backups, warn about extension/content mismatches.

### Menu 4: Real-Time Monitor
Watchdog-based directory monitoring with debounce, auto-scan, notifications.

### Menu 5: Dashboard & Stats
Scan statistics, threat breakdown, ML model info, system status.

### Menu 6: Activity Log
Full scan history with filtering and search.

### Menu 7: Recover .bak Files
Restore sanitized files from backup.

### Menu 8: Server Mode
Flask REST API + embedded web dashboard with 12 endpoints.

### Menu 9: Deep Analysis
- Format Parser + Differential Analysis (104 formats)
- Steganography Detection (LSB, chi-square, histogram, entropy)
- PE Anomaly Analysis (section entropy, packing, imports, entry point)
- ELF Section Anomaly Detection (types, entropy, symbols, dynamic linking)
- Office Macro Static Analysis (41 suspicious functions, auto-triggers, obfuscation)
- Archive Recursion + Container Nesting (bomb detection, path traversal)
- ONNX Model Export
- Full Analysis (all engines combined)

### Menu 10: Monitoring Panel
- Live Logs Panel
- Realtime Events
- Process Viewer
- Connection Viewer
- Alerts Panel
- File Change Monitor
- Terminal Activity Feed
- Workspace Audit Log
- Session Replay

### Menu 11: Investigation Panel
- Searchable Logs (full-text search across all logs)
- Timeline View (chronological event timeline)
- Compare Snapshots (directory state diff)
- Request Correlation (cross-file finding correlation)
- Tagged Events
- Bookmark Incidents
- Export Investigation (JSON)
- Notes Sidebar (markdown notes)
- Evidence Folder

### Menu 12: Benchmark & ONNX
- Generate Benchmark Dataset (clean images, PE polyglots, script polyglots)
- CI Regression Testing (automated detection verification)
- ONNX Model Export + Validation

### Menu 13: Session & Workspace
- Session Manager (create, view, close sessions with full event logging)
- Pinned Files (quick access)
- Recent Files (last 100)
- File Snapshots (versioning with restore)
- Restore Deleted Files (from cache)
- Markdown Notes (persistent notes)
- Command Chains (save/load/replay command sequences)
- Workspace Export/Import (zip-based)
- Regex Tester (pattern matching with groups)
- Auto-detect URLs/IPs/Domains/Emails from text

### Menu 14: Network Tools
- DNS Lookup (A, AAAA, MX, NS, TXT, CNAME, SOA via raw socket)
- Whois Lookup (direct socket to whois servers, parsed fields)
- TCP Connect Tester (single port or common ports scan)
- Raw Request Editor (build, parse, send raw HTTP requests)
- Request History (persistent JSONL log)
- Auto-detect URLs/IPs/Emails from text

### Menu 15: Hex Editor
- Hex Dump with polyglot red-mark highlighting (overlay/extra data in red)
- Hex Pattern Search
- ASCII String Search
- Entropy Map Visualization (per-block entropy with color coding)
- File Diff (byte-by-byte comparison)
- Format Detection (30+ format signatures with region highlighting)

### Menu 16: Blue Side Monitoring
- Network Logs
- Request History
- WebSocket Monitor
- DNS Lookup
- Whois Lookup
- TCP Connect Tester
- Connection Viewer
- Process Viewer
- File Change Monitor

### Menu 17: Quarantine Vault
- View quarantined files with threat details
- Restore quarantined files
- Delete quarantined files permanently
- Search quarantine history
- Export quarantine log

### Menu 18: Comprehensive Report
- Runs all major analysis engines on a target
- File Detector (rule-based + ML)
- File Sanitizer
- Deep Analysis (format, stego, PE, ELF, office, archive)
- Network IOCs (IPs, domains, URLs)
- Blue Side Indicators
- Quarantine Threats
- Generates unified report file in ~/.polyglot/reports/

## Engines

```
engines/
  features.py          — 354-feature extraction from raw bytes
  model.py             — CatBoost ML classifier (CPU/GPU)
  yara_engine.py       — Custom YARA-like rule engine (49 rules)
  scanner.py           — Unified scan pipeline
  generator.py         — Synthetic training data (76 polyglot types)
  quarantine.py        — Encrypted quarantine vault
  config.py            — YAML configuration
  monitor.py           — Watchdog folder monitoring
  notifications.py     — Desktop notifications
  format_parser.py     — 104 media format parser + differential analysis
  stego_detector.py    — Steganography detection (LSB, chi-square, histogram, entropy)
  pe_analyzer.py       — PE anomaly analysis (sections, packing, imports, entry point)
  elf_analyzer.py      — ELF section anomaly detection
  office_analyzer.py   — Office macro static analysis (41 suspicious functions)
  archive_scanner.py   — Archive recursion + container nesting scanning
  onnx_export.py       — ONNX export, benchmark datasets, CI regression, fuzzing
  payload_mutator.py   — Payload mutation engine (PS/VBA/JS obfuscation, fileless, sandbox)
  network_tools.py     — DNS, whois, TCP tester, raw request editor, request history
  risk_engine.py       — Risk scoring, vuln correlation, credential chains, attack chains, reporting
  workspace.py         — Persistent workspace, snapshots, notes, chains, regex, session manager
  hex_editor.py        — Hex editor with polyglot red-mark highlighting
```

## CLI Reference

```bash
# Builder
polyglot build <cover> <payload> [options]
  --type <jpeg|png|gif|pdf|zip|mp4|xlsx|docx>
  --payload-type <exe|vbs|ps1|bash|sh|python|applescript|xlsx|docx>
  --target-os <windows|linux|macos|all>
  --encrypt --fud --mime --output <path>

# Scanner
polyglot scan <file_or_dir>

# Sanitizer
polyglot sanitize <file_or_dir>

# ML Training
polyglot train --data <csv> [--cpu|--gpu] [--samples N]

# Monitor
polyglot monitor <directory>

# Background service
polyglot service start|stop|status|install|uninstall

# Server
polyglot server [--port 8888]

# Modes
polyglot gui          # PyQt6 GUI
polyglot tui          # Rich TUI (18 panels)
polyglot              # Auto-detect (GUI if display, else TUI)
```

## API Documentation

REST API at `http://localhost:8888` when running `polyglot server`.

**Endpoints:**
- `POST /api/scan` — Scan file for polyglot threats
- `POST /api/sanitize` — Sanitize file (remove trailing payloads)
- `POST /api/build` — Build polyglot file
- `GET /api/quarantine` — List quarantined files
- `POST /api/quarantine/restore` — Restore quarantined file
- `GET /api/status` — System status + model accuracy
- `GET /api/yara` — List YARA rules
- `GET /api/config` — Get configuration
- `POST /api/config` — Update configuration
- `POST /api/train` — Start ML training
- `GET /api/logs` — Recent scan/activity logs
- `GET /` — Web dashboard (embedded HTML)

## Detection Accuracy

| Test Case | Scanner | Sanitizer | ML |
|-----------|---------|-----------|-----|
| Clean JPEG | clean | clean | 75% |
| JPEG + trailing PE | THREAT | sanitized | 79% |
| JPEG + embedded PE | THREAT | clean* | 79% |
| JPEG + bash dropper | THREAT | — | 99% |
| JPEG + Python dropper | CRIT | — | 98% |
| Clean PDF | clean | clean | 82% |

**Model Performance:** 97.7% accuracy, 90.2% benign recall, 100% malicious recall, 354 features, 1,980 training samples.

*Embedded payloads can't be removed without corrupting host file.

## Sanitizer Limitations

**CAN:** Remove trailing data after format end markers, detect extension/content mismatches, create .bak backups.

**CANNOT:** Reconstruct corrupted covers, remove embedded payloads, fix extension mismatches, guarantee 100% clean for sophisticated polyglots.

## Architecture

```
polyglot.py          — Single entry point (CLI/TUI/GUI/server/service)
polyglot_tui.py      — Rich TUI (18 interactive panels, 2900+ lines)
polyglot_app.py      — PyQt6 GUI (9 panels)
server.py            — Flask API + embedded web dashboard
daemon.py            — Cross-platform background monitor service
engines/             — 21 engine modules (see Engines section)
models/              — Trained CatBoost model
training_dataset.csv — Training data
Makefile             — Build targets: install, dist, release, test
```

## Requirements

```
# Core ML
catboost>=1.2
scikit-learn>=1.3
numpy>=1.24
pandas>=2.0

# Server
flask>=3.0
pyyaml>=6.0

# TUI
rich>=13.0

# GUI (optional — skip on headless servers)
# PyQt6>=6.5

# Real-time monitoring (optional)
watchdog>=3.0

# Network
requests>=2.31
```

## Credits

### Author
**Mr-DS-ML-85** — [GitHub](https://github.com/Mr-DS-ML-85)

### Research & Sources
- Polydet/polyglot-database — polyglot file format research
- mindcrypt/polyglot — polyglot attack techniques
- berylliumsec/polyglots — PNG+script polyglots
- michenriksen/xss-polyglots — XSS polyglot vectors
- PortSwigger — RCE polyglot research
- Trail of Bits — polyglot security research
- Ange Albertini (angie) — file format polyglot pioneer

### Technologies
CatBoost, PyQt6, Rich, Flask, Watchdog, NumPy/SciPy, scikit-learn

## License

MIT
