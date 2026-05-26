# Polyglot Toolkit

**Educational tools for understanding, detecting, and defending against polyglot file attacks.**

A **polyglot file** is a file that is simultaneously valid as two different formats. For example, a file that is both a valid JPEG image AND contains a hidden executable payload after the JPEG end-of-image marker.

This toolkit provides three tools for working with polyglot files:

## 📦 Tools

### 1. Polyglot Builder (`builder/`)

Constructs polyglot files by appending payload data after a cover file's format-specific end markers. For **educational and authorized penetration testing** purposes only.

```bash
# Build a JPEG polyglot with an embedded script
python3 builder/polyglot_builder.py cover.jpg payload.exe -o polyglot.jpg -v

# List supported cover formats
python3 builder/polyglot_builder.py --list-formats
```

**Supported cover formats:**
- JPEG — payload after EOI marker (FF D9)
- PNG — payload after IEND chunk
- GIF — payload after GIF trailer (3B)
- PDF — payload after %%EOF marker
- ZIP — payload after End of Central Directory
- BMP — payload after pixel data

### 2. Polyglot Detector (`detector/`)

Scans files for polyglot indicators without modifying them. Detects:
- Data after format end markers
- Embedded executable headers (MZ, ELF, Mach-O)
- Suspicious script patterns (PowerShell, VBScript, JavaScript)
- High-entropy payloads (encrypted/packed data)
- Double extensions and null byte injection
- Format mismatches (extension vs content)

```bash
# Scan a single file
python3 detector/polyglot_detector.py suspicious.jpg -v

# Scan a directory recursively
python3 detector/polyglot_detector.py ~/Downloads -r -v

# Quiet mode — only CRITICAL and HIGH findings
python3 detector/polyglot_detector.py /tmp/files -r -q

# JSON output for integration with other tools
python3 detector/polyglot_detector.py files/ -r --json
```

**Exit codes:**
- `0` — all files clean
- `1` — HIGH severity findings
- `2` — CRITICAL severity findings

### 3. Polyglot Sanitizer (`sanitizer/`)

Strips hidden payloads from files by removing data after format end markers. Creates `.bak` backups by default.

```bash
# Sanitize a file (creates .bak backup)
python3 sanitizer/polyglot_sanitizer.py suspicious.jpg -v

# Sanitize without backup
python3 sanitizer/polyglot_sanitizer.py file.jpg --no-backup

# Dry run — see what would be removed
python3 sanitizer/polyglot_sanitizer.py files/ -r -n

# Output to a different directory
python3 sanitizer/polyglot_sanitizer.py files/ -r -o cleaned/
```

## 🔬 How Polyglot Attacks Work

### The Technique

1. **Cover file** — A legitimate file (JPEG, PNG, PDF, MP4) that renders normally
2. **Payload** — An executable, script, or other malicious content
3. **Injection** — The payload is appended after the cover file's natural end marker

```
[Valid JPEG data] [FF D9 end marker] [Hidden EXE payload]
                  ^^^^^^^^^^^^^^^^^   ^^^^^^^^^^^^^^^^^^^^
                  Image displays      Runs when triggered
                  normally here       (right-click, social eng)
```

### Why It Works

- **JPEG viewers** stop reading at `FF D9` — they never see the payload
- **Windows Explorer** may show the file as an image (icon/thumbnail)
- **Antivirus** may only scan up to the end marker
- **File size** looks normal for a high-res image

### Common Cover Formats

| Format | End Marker | Technique |
|--------|-----------|-----------|
| JPEG | FF D9 | Payload after EOI |
| PNG | IEND chunk | Payload after IEND |
| GIF | 3B | Payload after trailer |
| PDF | %%EOF | Payload after EOF |
| ZIP | EOCD | Payload after Central Dir |

## 🛡️ Defense Strategies

### For Users
1. **Don't trust file extensions** — Use the detector to verify suspicious files
2. **Check file properties** — Right-click → Properties → look for unusual size
3. **Scan before opening** — Use the detector on downloaded files
4. **Sanitize received files** — Run the sanitizer on files from untrusted sources

### For Organizations
1. **Email gateway scanning** — Integrate the detector into mail servers
2. **File upload filters** — Check uploads for polyglot indicators
3. **Endpoint protection** — Deploy the sanitizer as a file processing step
4. **Security awareness** — Train staff on polyglot file risks

### Detection Integration

```python
from detector.polyglot_detector import scan_file

# In your file processing pipeline
detections = scan_file(filepath)
for det in detections:
    if det.severity in ('CRITICAL', 'HIGH'):
        quarantine(filepath)
        alert_security_team(det)
```

## ⚠️ Legal Disclaimer

This toolkit is provided for **educational purposes** and **authorized security testing** only.

- Only use the builder on systems you own or have explicit written authorization to test
- Unauthorized use of polyglot techniques may violate computer fraud laws
- The detector and sanitizer are defensive tools with no restrictions
- By using this toolkit, you agree to comply with all applicable laws

## 📋 Requirements

- Python 3.8+
- No external dependencies (stdlib only)

## 📄 License

MIT License — See [LICENSE](LICENSE) for details.
