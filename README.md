# Polyglot Toolkit v3.0 — Red Team + Shield Edition

Red team offensive toolkit + ML-powered defensive shield in one unified application.

## Features

### ◆ Builder (Offense)
- **Standard Polyglot** — payload after end markers (JPEG/PNG/GIF/PDF/ZIP/MP4)
- **FUD Cryptor** — multi-layer obfuscation (XOR+zlib+b85) to evade AV
- **MIME-Type Confusion** — fake headers to disguise payload type
- **Covert Archive Embedding** — payload in ZIP structures
- **XOR Encryption** — random 32-byte key encryption

### ⚠ Scanner (Defense)
- **ML Detection** — CatBoost GPU classifier on 338 features
- **YARA Rules** — 26 built-in rules targeting RedTeam Builder patterns
- **Signature Scanning** — PE/ELF/script hidden signature detection
- **Entropy Analysis** — 8-section Shannon entropy for encrypted payloads
- **Trailing Data Detection** — hidden data after file end markers
- **MIME Confusion Detection** — dual-header polyglot detection

### ▶ Real-Time Monitor
- Watchdog-based folder monitoring with debounce
- Auto-scan new/modified files
- Desktop push notifications (Linux/macOS/Windows)
- Alert sounds on critical findings

### 🧠 ML Training
- Synthetic data generation (12 polyglot + 9 benign types)
- CatBoost GPU training (RTX 4060 optimized)
- Feature importance analysis
- Train/eval split with early stopping

### 🛡 Quarantine
- Encrypted vault with masked filenames
- Restore/delete/purge expired
- Full audit trail (JSONL metadata)

### 📋 YARA Rules Viewer
- 26 built-in rules with severity color-coding
- Targets: PE-in-PDF, ELF-in-ZIP, Cobalt Strike, Metasploit, UPX packing, shellcode

## Quick Start

```bash
# GUI (PyQt6 — 9 panels)
./polyglot gui

# TUI (Rich terminal)
./polyglot

# CLI commands
./polyglot build cover.jpg payload.exe --type jpeg --encrypt --fud
./polyglot scan ~/Downloads
./polyglot sanitize suspicious.jpg
./polyglot monitor ~/Downloads
```

## First Time Setup

1. Launch GUI → **ML Training** → Generate Synthetic → Train Model
2. **Scanner** → Check "Use ML Model" → Scan files
3. **Monitor** → Start watching ~/Downloads

## Requirements

- Python 3.10+ (tested on 3.14)
- UV package manager (auto-installs deps)
- PyQt6, rich, catboost, numpy, scikit-learn, watchdog, pyyaml

## Author

Mr-DS-ML-85

## License

MIT
