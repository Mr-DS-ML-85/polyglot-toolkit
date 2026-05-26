# Polyglot Toolkit — Red Team Edition

Red team security toolkit for building, detecting, and sanitizing polyglot files — valid documents that secretly contain hidden payloads.

## Features

### ◆ Builder — Attack Vectors
- **Standard Polyglot** — payload hidden after file end markers (JPEG, PNG, GIF, PDF, ZIP, MP4)
- **FUD Cryptor** — multi-layer obfuscation (XOR + zlib + b85 encoding) to evade AV detection
- **MIME-Type Confusion** — prepend fake headers to disguise payload type
- **Covert Archive Embedding** — embed payloads inside ZIP/archive structures
- **XOR Encryption** — optional payload encryption with random 32-byte key
- **EXE→Image wrapping** — hide executables inside image files
- **Script→Media disguise** — BAT→MP4, VBS→JPG script-to-media conversion
- **Icon manipulation** — replace EXE icons with cover file icons

### ⚠ Detector
- Extension vs content-type mismatch detection
- Hidden PE/ELF/script signature scanning
- Trailing data detection after file end markers
- Entropy analysis (8-section) for encrypted/compressed payloads
- MIME confusion attack detection
- Recursive directory scanning

### 🛡 Sanitizer
- Strip hidden data after JPEG EOI, PNG IEND, GIF terminator, PDF %%EOF
- ZIP trimming to end of central directory
- Automatic `.bak` backup creation

### ▶ Real-Time Monitor
- Directory watching for new/modified files
- Desktop notifications (Linux/macOS/Windows)
- Alert sounds on threat detection

## Quick Start

```bash
# Interactive TUI (terminal)
./polyglot

# PyQt6 GUI
./polyglot gui

# Direct CLI commands
./polyglot build cover.jpg payload.exe --type jpeg --encrypt
./polyglot scan ~/Downloads
./polyglot sanitize suspicious_image.jpg
./polyglot monitor ~/Downloads

# Help
./polyglot help
```

## Requirements

- Python 3.10+ (tested on 3.14)
- UV package manager (auto-installs deps)
- PyQt6 (for GUI — auto-installed by launcher)
- rich (for TUI — auto-installed by launcher)
- `notify-send` on Linux, `osascript` on macOS, PowerShell on Windows

## Project Structure

```
polyglot-toolkit/
├── polyglot           # Launcher script (./polyglot gui|tui|build|scan|sanitize|monitor)
├── polyglot_app.py    # PyQt6 GUI application
├── polyglot_tui.py    # TUI + CLI application
├── README.md
├── LICENSE
└── .venv/             # UV-managed virtual environment
```

## Defense Strategies

1. **Scan before opening** — Use the Detector to check any suspicious file
2. **Sanitize received images** — Run the Sanitizer on downloaded files
3. **Monitor download folders** — Use the Real-Time Monitor on ~/Downloads
4. **Check file signatures** — Content-type vs extension mismatch = red flag
5. **Audit with YARA** — Complement with YARA rules for known polyglot patterns
6. **Sandbox execution** — Never run untrusted binaries directly

## Author

Mr-DS-ML-85

## License

MIT
