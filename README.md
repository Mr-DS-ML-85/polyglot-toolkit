# Polyglot Toolkit — Red Team Edition

Red team security toolkit for building, detecting, and sanitizing polyglot files — valid documents that secretly contain hidden payloads.

## Features

### ◆ Builder
Create polyglot files with hidden payloads in:
- **JPEG** — payload after EOI marker
- **PNG** — payload after IEND chunk
- **GIF** — payload after terminator
- **PDF** — payload after %%EOF
- **ZIP** — payload before central directory

Optional XOR encryption for payload obfuscation.

### ⚠ Detector
Scan files for:
- Extension vs content type mismatches
- Hidden PE/ELF/script signatures after end markers
- Trailing data after file format end markers
- High entropy sections (encrypted/compressed payloads)
- Duplicate end markers (multiple polyglot payloads)
- Malicious patterns (PowerShell, cmd.exe, scripts)

Supports single file and recursive directory scanning.

### 🛡 Sanitizer
Strip hidden payloads by:
- Removing trailing data after JPEG EOI
- Removing data after PNG IEND
- Removing data after GIF terminator (0x3B)
- Removing data after PDF %%EOF
- Trimming ZIP to end of central directory + comment

Automatic `.bak` backup creation before cleaning.

### ▶ Real-Time Monitor
- Watches directories for new/modified files
- Automatic polyglot detection on file changes
- Desktop notifications for threats (notify-send)
- Alert sound on critical findings
- Live threat feed in the GUI

### 📋 Dashboard
- Live stats: files scanned, threats found, files sanitized
- Recent alerts feed
- Quick scan/sanitize buttons

## Requirements

- Python 3.6+
- tkinter (usually pre-installed on Linux)
- `notify-send` for desktop notifications (optional)
- No external pip packages needed

## Usage

```bash
# GUI Application (all-in-one)
python3 polyglot_app.py
```

## Defense Strategies

1. **Scan before opening** — Use the Detector to check any suspicious file
2. **Sanitize received images** — Run the Sanitizer on downloaded files
3. **Monitor download folders** — Use the Real-Time Monitor on ~/Downloads
4. **Check file signatures** — Content-type vs extension mismatch is a red flag
5. **Audit with YARA** — Complement with YARA rules for known polyglot patterns
6. **Sandbox execution** — Never run untrusted binaries directly

## Author

Mr-DS-ML-85

## License

MIT
