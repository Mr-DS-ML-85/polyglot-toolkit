#!/usr/bin/env python3
"""
Polyglot Detector — Scans files for polyglot indicators.

Detects files that claim to be one format (e.g., JPEG) but contain
hidden data after format-specific end markers, embedded executable
headers, double extensions, or other suspicious structures.

Author: Mr-DS-ML-85
License: MIT
"""

import argparse
import os
import sys
import struct
import math
from pathlib import Path
from collections import namedtuple

Detection = namedtuple('Detection', ['severity', 'indicator', 'details'])

# ============================================================
# Magic bytes and signatures
# ============================================================

# Executable signatures
EXE_SIGNATURES = {
    b'MZ': 'PE/DOS Executable (MZ header)',
    b'\x7fELF': 'ELF Executable',
    b'\xfe\xed\xfa\xce': 'Mach-O 32-bit',
    b'\xfe\xed\xfa\xcf': 'Mach-O 64-bit',
    b'\xcf\xfa\xed\xfe': 'Mach-O 64-bit (reversed)',
    b'\xce\xfa\xed\xfe': 'Mach-O 32-bit (reversed)',
    b'#!': 'Shell script (shebang)',
    b'\x00asm': 'WebAssembly module',
}

# Script signatures (inside polyglots)
SCRIPT_SIGNATURES = {
    b'<script': 'HTML/JavaScript script tag',
    b'<iframe': 'HTML iframe tag',
    b'<object': 'HTML object tag',
    b'<embed': 'HTML embed tag',
    b'powershell': 'PowerShell reference',
    b'cmd.exe': 'cmd.exe reference',
    b'wscript': 'Windows Script Host reference',
    b'cscript': 'CScript reference',
    b'CreateObject': 'VBScript COM object creation',
    b'WScript.Shell': 'WScript Shell execution',
    b'ActiveXObject': 'ActiveX object creation',
    b'eval(': 'JavaScript eval()',
    b'Function(': 'JavaScript Function constructor',
    b'XMLHttpRequest': 'XHR request',
    b'fetch(': 'JavaScript fetch API',
}

# Format end markers
FORMAT_MARKERS = {
    'jpeg': {
        'magic': b'\xff\xd8\xff',
        'name': 'JPEG',
        'end_marker': b'\xff\xd9',
        'end_name': 'EOI (FF D9)',
    },
    'png': {
        'magic': b'\x89PNG\r\n\x1a\n',
        'name': 'PNG',
        'end_marker': b'IEND',
        'end_name': 'IEND chunk',
    },
    'gif': {
        'magic': b'GIF8',
        'name': 'GIF',
        'end_marker': b'\x3b',
        'end_name': 'GIF trailer (3B)',
    },
    'pdf': {
        'magic': b'%PDF',
        'name': 'PDF',
        'end_marker': b'%%EOF',
        'end_name': '%%EOF marker',
    },
}


def calculate_entropy(data: bytes) -> float:
    """Calculate Shannon entropy of data (0-8). High entropy = compressed/encrypted."""
    if not data:
        return 0.0
    freq = [0] * 256
    for byte in data:
        freq[byte] += 1
    entropy = 0.0
    length = len(data)
    for count in freq:
        if count > 0:
            p = count / length
            entropy -= p * math.log2(p)
    return entropy


def detect_format(data: bytes) -> str:
    """Detect the declared format of a file."""
    for fmt_name, fmt_info in FORMAT_MARKERS.items():
        if data[:len(fmt_info['magic'])] == fmt_info['magic']:
            return fmt_name
    # Check EXE
    if data[:2] == b'MZ':
        return 'exe'
    if data[:4] == b'\x7fELF':
        return 'elf'
    return 'unknown'


def find_marker(data: bytes, marker: bytes) -> int:
    """Find the LAST occurrence of a marker (end markers should be at the end)."""
    return data.rfind(marker)


def _validate_pe_at(data: bytes, pos: int) -> bool:
    """Validate that MZ at pos is a real PE header (not random bytes).
    Checks for PE\x00\x00 signature at e_lfanew offset."""
    try:
        if pos + 64 > len(data):
            return False
        e_lfanew = struct.unpack_from('<I', data, pos + 60)[0]
        pe_sig_pos = pos + e_lfanew
        if pe_sig_pos + 4 > len(data):
            return False
        return data[pe_sig_pos:pe_sig_pos + 4] == b'PE\x00\x00'
    except Exception:
        return False


def _validate_elf_at(data: bytes, pos: int) -> bool:
    """Validate that ELF magic at pos has valid header structure."""
    try:
        if pos + 20 > len(data):
            return False
        elf_class = data[pos + 4]
        if elf_class not in (1, 2):
            return False
        elf_data = data[pos + 5]
        if elf_data not in (1, 2):
            return False
        elf_type = struct.unpack_from('<H' if elf_data == 1 else '>H', data, pos + 16)[0]
        return elf_type in (1, 2, 3, 4)
    except Exception:
        return False


def scan_file(filepath: str, verbose: bool = False) -> list:
    """
    Scan a file for polyglot indicators.

    Returns a list of Detection namedtuples.
    """
    detections = []
    data = Path(filepath).read_bytes()
    filename = os.path.basename(filepath)
    filesize = len(data)

    if filesize == 0:
        return [Detection('LOW', 'EMPTY_FILE', 'File is empty')]

    if filesize < 16:
        return [Detection('LOW', 'TINY_FILE', f'File is only {filesize} bytes')]

    # 1. Detect declared format
    declared_format = detect_format(data)

    # 2. Check file extension vs content
    ext = os.path.splitext(filename)[1].lower()
    ext_format_map = {
        '.jpg': 'jpeg', '.jpeg': 'jpeg', '.png': 'png', '.gif': 'gif',
        '.pdf': 'pdf', '.exe': 'exe', '.elf': 'elf', '.mp4': 'mp4',
        '.avi': 'avi', '.mkv': 'mkv', '.doc': 'doc', '.docx': 'docx',
        '.bat': 'bat', '.vbs': 'vbs', '.js': 'js', '.ps1': 'ps1',
    }
    expected_format = ext_format_map.get(ext, 'unknown')

    if declared_format != 'unknown' and expected_format != 'unknown':
        if declared_format != expected_format:
            detections.append(Detection(
                'HIGH', 'FORMAT_MISMATCH',
                f'Extension {ext} suggests {expected_format}, but content is {declared_format}'
            ))

    # 3. Check for data after end marker (polyglot indicator)
    if declared_format in FORMAT_MARKERS:
        fmt = FORMAT_MARKERS[declared_format]
        marker_pos = find_marker(data, fmt['end_marker'])

        if marker_pos != -1:
            after_marker_pos = marker_pos + len(fmt['end_marker'])
            trailing_data = data[after_marker_pos:]
            trailing_size = len(trailing_data)

            if trailing_size > 0:
                # Some trailing data is normal (metadata, padding)
                # But significant data is suspicious
                trailing_ratio = trailing_size / filesize

                if trailing_size > 1024:  # More than 1KB after end marker
                    severity = 'HIGH' if trailing_size > 10000 else 'MEDIUM'
                    detections.append(Detection(
                        severity, 'DATA_AFTER_END_MARKER',
                        f'{trailing_size:,} bytes found after {fmt["end_name"]} '
                        f'(byte {after_marker_pos:,}). '
                        f'This is {trailing_ratio*100:.1f}% of total file size.'
                    ))

                    # Check what the trailing data contains — VALIDATE, don't just match 2 bytes
                    if trailing_data[:2] == b'MZ' and _validate_pe_at(trailing_data, 0):
                        detections.append(Detection(
                            'CRITICAL', 'HIDDEN_PE_EXE',
                            f'PE executable (MZ header) found at byte {after_marker_pos:,}! '
                            f'This file is a polyglot — valid {fmt["name"]} that also contains a Windows executable.'
                        ))
                    elif trailing_data[:4] == b'\x7fELF' and _validate_elf_at(trailing_data, 0):
                        detections.append(Detection(
                            'CRITICAL', 'HIDDEN_ELF_EXE',
                            f'ELF executable found at byte {after_marker_pos:,}!'
                        ))
                    elif trailing_data[:2] == b'#!':
                        detections.append(Detection(
                            'HIGH', 'HIDDEN_SCRIPT',
                            f'Shell script (shebang) found at byte {after_marker_pos:,}!'
                        ))
                    elif trailing_data[:3] == b'\xff\xd8\xff':
                        detections.append(Detection(
                            'MEDIUM', 'HIDDEN_JPEG',
                            f'Another JPEG image found after end marker at byte {after_marker_pos:,}.'
                        ))

                    # Check entropy of trailing data
                    entropy = calculate_entropy(trailing_data)
                    if entropy > 7.0:
                        detections.append(Detection(
                            'HIGH', 'HIGH_ENTROPY_PAYLOAD',
                            f'Trailing data has very high entropy ({entropy:.2f}/8.0) — '
                            f'likely compressed, encrypted, or packed payload.'
                        ))
                    elif entropy > 6.0:
                        detections.append(Detection(
                            'MEDIUM', 'ELEVATED_ENTROPY',
                            f'Trailing data has elevated entropy ({entropy:.2f}/8.0).'
                        ))

    # 4. Scan for embedded executable signatures (with validation)
    SAFE_EXT = {'.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.htm', '.xhtml',
                '.php', '.asp', '.aspx', '.jsp', '.vue', '.svelte', '.rb', '.pl',
                '.sh', '.bash', '.zsh', '.ps1', '.bat', '.cmd', '.vbs', '.lua',
                '.md', '.txt', '.rst', '.csv', '.json', '.xml', '.yaml', '.yml',
                '.toml', '.ini', '.cfg', '.conf', '.log', '.sql',
                '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.go', '.rs'}

    ext = os.path.splitext(filename)[1].lower()
    if ext not in SAFE_EXT:
        for sig_bytes, sig_name in EXE_SIGNATURES.items():
            positions = []
            start = 0
            while True:
                pos = data.find(sig_bytes, start)
                if pos == -1:
                    break
                # Skip the first occurrence if it's at byte 0 (that's the declared format)
                if pos == 0 and declared_format in ('exe', 'elf'):
                    start = pos + 1
                    continue
                positions.append(pos)
                start = pos + 1

            for pos in positions:
                # Skip if it's inside the cover's normal data area
                if declared_format in FORMAT_MARKERS:
                    fmt = FORMAT_MARKERS[declared_format]
                    marker_pos = find_marker(data, fmt['end_marker'])
                    if marker_pos != -1 and pos < marker_pos:
                        # Validate it's a REAL PE/ELF header, not random bytes
                        is_valid = False
                        if sig_bytes == b'MZ':
                            is_valid = _validate_pe_at(data, pos)
                        elif sig_bytes == b'\x7fELF':
                            is_valid = _validate_elf_at(data, pos)
                        else:
                            is_valid = True  # Other signatures are fine

                        if is_valid:
                            detections.append(Detection(
                                'HIGH', 'EMBEDDED_EXE_IN_BODY',
                                f'{sig_name} VALID header found at byte {pos:,} (inside {fmt["name"]} data). '
                                f'Confirmed valid PE/ELF structure.'
                            ))
                    elif marker_pos != -1 and pos > marker_pos:
                        detections.append(Detection(
                            'HIGH', 'EXE_AFTER_MARKER',
                            f'{sig_name} found at byte {pos:,} (AFTER {fmt["end_name"]}). '
                            f'Definite polyglot indicator.'
                        ))

    # 5. Scan for suspicious script patterns (ONLY in trailing data)
    if ext not in SAFE_EXT and declared_format in FORMAT_MARKERS:
        fmt = FORMAT_MARKERS[declared_format]
        marker_pos = find_marker(data, fmt['end_marker'])
        if marker_pos != -1:
            trailing = data[marker_pos + len(fmt['end_marker']):]
            for sig_bytes, sig_name in SCRIPT_SIGNATURES.items():
                pos = trailing.find(sig_bytes)
                if pos != -1:
                    detections.append(Detection(
                        'HIGH', 'SUSPICIOUS_SCRIPT',
                        f'{sig_name} found at byte {marker_pos + len(fmt["end_marker"]) + pos:,} — script in trailing data.'
                    ))

    # 6. Double extension check
    if '..' in filename:
        detections.append(Detection(
            'HIGH', 'DOUBLE_EXTENSION',
            f'Filename contains double dots: {filename}'
        ))

    suspicious_extensions = ['.jpg.exe', '.png.exe', '.pdf.exe', '.mp4.exe',
                             '.jpg.bat', '.png.vbs', '.pdf.js', '.mp4.ps1',
                             '.scr', '.pif', '.com']
    for sus_ext in suspicious_extensions:
        if filename.lower().endswith(sus_ext):
            detections.append(Detection(
                'CRITICAL', 'SUSPICIOUS_EXTENSION',
                f'File has suspicious extension: {sus_ext}'
            ))

    # 7. Check for polyglot markers (multiple format headers in one file)
    formats_found = []
    for fmt_name, fmt_info in FORMAT_MARKERS.items():
        if data[:len(fmt_info['magic'])] == fmt_info['magic']:
            formats_found.append(fmt_name)

    if len(formats_found) > 1:
        detections.append(Detection(
            'CRITICAL', 'MULTIPLE_FORMAT_HEADERS',
            f'Multiple format headers detected: {", ".join(formats_found)}'
        ))

    # 8. Check for null bytes in filename (null byte injection)
    if '\x00' in filename:
        detections.append(Detection(
            'CRITICAL', 'NULL_BYTE_FILENAME',
            'Filename contains null bytes — possible null byte injection attack.'
        ))

    if not detections:
        detections.append(Detection(
            'SAFE', 'CLEAN',
            'No polyglot indicators detected.'
        ))

    return detections


def print_report(filepath: str, detections: list, verbose: bool = False):
    """Pretty-print detection results."""
    severity_colors = {
        'CRITICAL': '\033[91m',  # Red
        'HIGH': '\033[93m',      # Yellow
        'MEDIUM': '\033[33m',    # Orange
        'LOW': '\033[96m',       # Cyan
        'SAFE': '\033[92m',      # Green
    }
    reset = '\033[0m'

    filesize = os.path.getsize(filepath)
    print(f"\n{'='*70}")
    print(f"  POLYGLOT DETECTOR — Scan Report")
    print(f"{'='*70}")
    print(f"  File: {filepath}")
    print(f"  Size: {filesize:,} bytes ({filesize/1024:.1f} KB)")
    print(f"{'='*70}")

    max_severity = 'SAFE'
    severity_order = ['SAFE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']

    for det in detections:
        color = severity_colors.get(det.severity, '')
        print(f"\n  {color}[{det.severity}]{reset} {det.indicator}")
        if verbose:
            print(f"    {det.details}")
        else:
            # Print truncated details
            print(f"    {det.details[:120]}{'...' if len(det.details) > 120 else ''}")

        if severity_order.index(det.severity) > severity_order.index(max_severity):
            max_severity = det.severity

    print(f"\n{'='*70}")
    color = severity_colors.get(max_severity, '')
    print(f"  VERDICT: {color}{max_severity}{reset}")
    print(f"{'='*70}\n")

    return max_severity


def main():
    parser = argparse.ArgumentParser(
        description='Polyglot Detector — Scan files for polyglot indicators',
        epilog='Scans files for hidden data after end markers, embedded executables, suspicious scripts, and other polyglot indicators.'
    )
    parser.add_argument('files', nargs='+', help='Files or directories to scan')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed indicators')
    parser.add_argument('-r', '--recursive', action='store_true', help='Scan directories recursively')
    parser.add_argument('-q', '--quiet', action='store_true', help='Only show CRITICAL/HIGH findings')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    all_results = []
    target_files = []

    for target in args.files:
        if os.path.isfile(target):
            target_files.append(target)
        elif os.path.isdir(target):
            if args.recursive:
                for root, dirs, files in os.walk(target):
                    for f in files:
                        target_files.append(os.path.join(root, f))
            else:
                for f in os.listdir(target):
                    fp = os.path.join(target, f)
                    if os.path.isfile(fp):
                        target_files.append(fp)

    if not target_files:
        print("[!] No files found to scan.")
        sys.exit(1)

    total_critical = 0
    total_high = 0

    for filepath in target_files:
        try:
            detections = scan_file(filepath, args.verbose)

            if args.quiet:
                detections = [d for d in detections if d.severity in ('CRITICAL', 'HIGH')]

            if detections:
                if not args.json:
                    print_report(filepath, detections, args.verbose)
                all_results.append((filepath, detections))

                for d in detections:
                    if d.severity == 'CRITICAL':
                        total_critical += 1
                    elif d.severity == 'HIGH':
                        total_high += 1
        except Exception as e:
            if args.verbose:
                print(f"[!] Error scanning {filepath}: {e}")

    # Summary
    if not args.json:
        print(f"\n{'='*70}")
        print(f"  SCAN SUMMARY")
        print(f"{'='*70}")
        print(f"  Files scanned: {len(target_files)}")
        print(f"  CRITICAL: {total_critical}")
        print(f"  HIGH:     {total_high}")
        print(f"{'='*70}\n")

    if args.json:
        import json
        output = []
        for filepath, detections in all_results:
            output.append({
                'file': filepath,
                'detections': [
                    {'severity': d.severity, 'indicator': d.indicator, 'details': d.details}
                    for d in detections
                ]
            })
        print(json.dumps(output, indent=2))

    if total_critical > 0:
        sys.exit(2)
    elif total_high > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
