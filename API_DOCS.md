# PolyglotShield API Documentation

## Base URL
```
http://localhost:8888
```

Start server: `python polyglot.py server --port 8888`

## Authentication
None (local use only). Add auth middleware for production deployment.

## Content-Type
All POST endpoints accept `application/json`.

---

## Endpoints

### 1. GET /
**Web Dashboard** — Returns embedded HTML control panel with dark theme.

---

### 2. POST /api/scan
Scan a file for polyglot threats using signatures, YARA rules, and ML.

**Request Body:**
```json
{
  "file": "/path/to/file.jpg"
}
```

**Response (200):**
```json
{
  "status": "threats_found",
  "file": "suspicious.jpg",
  "size": 7021,
  "findings": [
    {
      "type": "HIDDEN_SIG",
      "detail": "PE/EXE @ 0x1399",
      "severity": "critical",
      "offset": 5017
    },
    {
      "type": "TRAILING_DATA",
      "detail": "2008 bytes after JPEG end — hidden payload",
      "severity": "critical",
      "offset": 5015
    }
  ],
  "ml_prediction": {
    "label": "polyglot",
    "risk_score": 94.1,
    "risk_level": "CRITICAL",
    "confidence": 0.94,
    "polyglot_probability": 0.941,
    "benign_probability": 0.059
  },
  "yara_matches": []
}
```

**Error (400):**
```json
{"error": "No file provided"}
```

---

### 3. POST /api/sanitize
Strip trailing payloads from a polyglot file.

**Request Body:**
```json
{
  "file": "/path/to/file.jpg",
  "backup": true
}
```

**Response (200):**
```json
{
  "status": "sanitized",
  "detail": "JPEG: 2008 bytes removed",
  "original_size": 7021,
  "cleaned_size": 5013,
  "backup_path": "/path/to/file.jpg.bak"
}
```

**Status values:** `clean`, `sanitized`, `danger`

---

### 4. POST /api/build
Build a polyglot file.

**Request Body:**
```json
{
  "cover": "/path/to/cover.jpg",
  "payload": "/path/to/payload.bin",
  "container_type": "jpeg",
  "payload_type": "bash",
  "target_os": "linux",
  "encrypt": true,
  "fud": false,
  "mime": true,
  "output": "/path/to/output.jpg"
}
```

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| cover | string | Yes | Path to cover file |
| payload | string | Yes | Path to payload file |
| container_type | string | No | jpeg, png, gif, pdf, zip, mp4, xlsx, docx (default: jpeg) |
| payload_type | string | No | exe, vbs, ps1, bash, sh, python, applescript, xlsx, docx (default: exe) |
| target_os | string | No | windows, linux, macos, all (default: windows) |
| encrypt | bool | No | XOR encrypt payload |
| fud | bool | No | FUD cryptor obfuscation |
| mime | bool | No | MIME-type confusion headers |
| output | string | No | Output path (default: polyglot.<ext>) |

**Payload types by platform:**
- Windows: `vbs`, `ps1`
- Linux: `bash`, `sh`
- macOS: `applescript`
- Cross-platform: `python`
- Office: `xlsx`, `docx` (VBA macro, auto-adapts to macOS via `target_os: macos`)

**Response (200):**
```json
{
  "status": "success",
  "output": "/path/to/output.jpg",
  "container_type": "JPEG",
  "payload_type": "VBS",
  "cover_size": 5013,
  "payload_size": 2004,
  "output_size": 8486,
  "payload_offset": 5017,
  "encrypted": true,
  "fud_protected": false,
  "mime_confused": true,
  "entropy": 3.32
}
```

---

### 5. GET /api/quarantine
List all quarantined files.

**Response (200):**
```json
{
  "files": [
    {
      "id": "a1b2c3d4e5f6",
      "original_name": "suspicious.jpg",
      "original_path": "/home/user/Downloads/suspicious.jpg",
      "quarantine_date": "2026-05-26T12:00:00",
      "threat_type": "HIDDEN_SIG",
      "severity": "critical",
      "file_size": 7021
    }
  ],
  "total": 1,
  "vault_path": "~/.polyglot/quarantine"
}
```

---

### 6. POST /api/quarantine/restore
Restore a quarantined file to its original location.

**Request Body:**
```json
{
  "id": "a1b2c3d4e5f6",
  "destination": "/path/to/restore/file.jpg"
}
```

**Response (200):**
```json
{
  "status": "restored",
  "path": "/path/to/restore/file.jpg"
}
```

---

### 7. POST /api/quarantine/delete
Permanently delete a quarantined file.

**Request Body:**
```json
{
  "id": "a1b2c3d4e5f6"
}
```

---

### 8. GET /api/status
Get system status and statistics.

**Response (200):**
```json
{
  "version": "3.0",
  "model_loaded": true,
  "model_accuracy": 97.7,
  "model_benign_recall": 90.2,
  "model_malicious_recall": 100.0,
  "features_count": 338,
  "yara_rules_count": 26,
  "monitor_running": false,
  "service_installed": false,
  "stats": {
    "files_scanned": 1234,
    "threats_found": 5,
    "files_sanitized": 3,
    "files_quarantined": 2
  }
}
```

---

### 9. GET /api/yara
List all built-in YARA rules.

**Response (200):**
```json
{
  "rules": [
    {
      "name": "pe_in_pdf",
      "severity": "critical",
      "description": "PE executable hidden in PDF document",
      "patterns": ["MZ", "%PDF"]
    }
  ],
  "total": 26
}
```

---

### 10. GET /api/config
Get current configuration.

**Response (200):**
```json
{
  "monitor": {
    "watch_dirs": ["~/Downloads"],
    "scan_interval": 5,
    "notify": true,
    "auto_quarantine": false
  },
  "model": {
    "path": "models/polyglot_shield.cbm",
    "features": 338
  },
  "quarantine": {
    "vault_path": "~/.polyglot/quarantine",
    "encrypt": true
  }
}
```

---

### 11. POST /api/config
Update configuration.

**Request Body:**
```json
{
  "monitor": {
    "watch_dirs": ["~/Downloads", "~/Documents"],
    "scan_interval": 10,
    "notify": true,
    "auto_quarantine": true
  }
}
```

---

### 12. POST /api/train
Start ML model training.

**Request Body:**
```json
{
  "samples": 50,
  "use_gpu": false
}
```

**Response (200):**
```json
{
  "status": "training_started",
  "samples": 50,
  "device": "CPU"
}
```

---

### 13. GET /api/logs
Get recent activity logs.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| limit | int | Max entries (default: 100) |
| severity | string | Filter: critical, high, warning, info |

**Response (200):**
```json
{
  "logs": [
    {
      "timestamp": "2026-05-26T12:00:00",
      "event": "scan",
      "file": "suspicious.jpg",
      "result": "threats_found",
      "findings": 2,
      "severity": "critical"
    }
  ]
}
```

---

### 14. POST /api/service/start
Start background monitoring service.

**Request Body:**
```json
{
  "dirs": ["~/Downloads", "~/Documents"]
}
```

### 15. POST /api/service/stop
Stop background monitoring service.

### 16. GET /api/service/status
Get background service status.

**Response (200):**
```json
{
  "running": true,
  "pid": 12345,
  "watch_dirs": ["~/Downloads"],
  "uptime": "2h 30m"
}
```

---

## Error Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad request (missing/invalid parameters) |
| 404 | Resource not found |
| 500 | Internal server error |

## Rate Limiting
None (local use only).

## CORS
Enabled for all origins (development mode).
