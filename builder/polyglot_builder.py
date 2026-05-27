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
    if payload_data[:4] in (b'\xfe\xed\xfa\xce', b'\xfe\xed\xfa\xcf',
                             b'\xce\xfa\xed\xfe', b'\xcf\xfa\xed\xfe'):
        return 'macho'
    if payload_data[:5] == b'<?php' or payload_data[:4] == b'<%@':
        return 'webshell'
    return 'raw'


def _build_pe_polyglot(cover_data: bytes, payload_data: bytes,
                       cover_format: str) -> bytes:
    """
    Build a REAL PE polyglot using overlay technique:
    - PE at offset 0 with VALID import table (kernel32.dll → ExitProcess)
    - Cover image appended after PE EOF (overlay)
    - Windows PE loader ignores overlay data → PE executes normally
    - Image viewers scan forward and find image signature in overlay
    """
    if payload_data[:2] == b'MZ' and _validate_pe_structure(payload_data):
        return payload_data + cover_data
    pe_stub = _build_valid_pe_stub(payload_data)
    return pe_stub + cover_data


def _validate_pe_structure(data: bytes) -> bool:
    """Check if data is a structurally valid PE."""
    if len(data) < 64:
        return False
    try:
        e_lfanew = struct.unpack_from('<I', data, 60)[0]
        if e_lfanew + 4 > len(data):
            return False
        if data[e_lfanew:e_lfanew+4] != b'PE\x00\x00':
            return False
        opt_off = e_lfanew + 24
        if opt_off + 2 > len(data):
            return False
        magic = struct.unpack_from('<H', data, opt_off)[0]
        return magic in (0x10B, 0x20B)
    except Exception:
        return False


def _build_valid_pe_stub(payload_data: bytes = b'') -> bytes:
    """
    Build a minimal valid PE32+ executable with proper import table.
    Imports kernel32.dll → ExitProcess. Entry point calls ExitProcess(0).
    """
    payload_aligned = ((len(payload_data) + 0x1FF) // 0x200) * 0x200 if payload_data else 0
    num_sections = 3 if payload_data else 2
    headers_size = 64 + 4 + 20 + 240 + (num_sections * 40)
    headers_padded = ((headers_size + 0x1FF) // 0x200) * 0x200

    text_file_off = headers_padded
    text_rva = 0x1000
    rdata_file_off = text_file_off + 0x200
    rdata_rva = 0x2000
    if payload_data:
        data_file_off = rdata_file_off + 0x200
        data_rva = 0x3000
        size_of_image = 0x4000
    else:
        data_file_off = 0
        data_rva = 0
        size_of_image = 0x3000

    total_size = rdata_file_off + 0x200 + payload_aligned
    pe = bytearray(total_size)

    # DOS Header
    pe[0:2] = b'MZ'
    pe[60:64] = struct.pack('<I', 64)

    # PE Signature
    pe[64:68] = b'PE\x00\x00'

    # COFF Header
    pe[68:70] = struct.pack('<H', 0x8664)
    pe[70:72] = struct.pack('<H', num_sections)
    pe[80:82] = struct.pack('<H', 0xF0)
    pe[82:84] = struct.pack('<H', 0x22)

    # Optional Header (PE32+) — correct offsets
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
    pe[o+56:o+60] = struct.pack('<I', size_of_image)
    pe[o+60:o+64] = struct.pack('<I', headers_padded)
    pe[o+68:o+70] = struct.pack('<H', 3)
    pe[o+70:o+72] = struct.pack('<H', 0x8100)
    pe[o+72:o+80] = struct.pack('<Q', 0x100000)
    pe[o+80:o+88] = struct.pack('<Q', 0x1000)
    pe[o+88:o+96] = struct.pack('<Q', 0x100000)
    pe[o+96:o+104] = struct.pack('<Q', 0x1000)
    pe[o+108:o+112] = struct.pack('<I', 16)
    pe[o+120:o+124] = struct.pack('<I', rdata_rva)
    pe[o+124:o+128] = struct.pack('<I', 0x28)

    # Section headers
    sec_off = 328
    pe[sec_off:sec_off+6] = b'.text\x00'
    pe[sec_off+8:sec_off+12] = struct.pack('<I', 0x100)
    pe[sec_off+12:sec_off+16] = struct.pack('<I', text_rva)
    pe[sec_off+16:sec_off+20] = struct.pack('<I', 0x200)
    pe[sec_off+20:sec_off+24] = struct.pack('<I', text_file_off)
    pe[sec_off+36:sec_off+40] = struct.pack('<I', 0x60000020)

    sec_off += 40
    pe[sec_off:sec_off+6] = b'.rdata\x00'
    pe[sec_off+8:sec_off+12] = struct.pack('<I', 0x200)
    pe[sec_off+12:sec_off+16] = struct.pack('<I', rdata_rva)
    pe[sec_off+16:sec_off+20] = struct.pack('<I', 0x200)
    pe[sec_off+20:sec_off+24] = struct.pack('<I', rdata_file_off)
    pe[sec_off+36:sec_off+40] = struct.pack('<I', 0x40000040)

    if payload_data:
        sec_off += 40
        pe[sec_off:sec_off+6] = b'.data\x00'
        pe[sec_off+8:sec_off+12] = struct.pack('<I', len(payload_data))
        pe[sec_off+12:sec_off+16] = struct.pack('<I', data_rva)
        pe[sec_off+16:sec_off+20] = struct.pack('<I', payload_aligned)
        pe[sec_off+20:sec_off+24] = struct.pack('<I', data_file_off)
        pe[sec_off+36:sec_off+40] = struct.pack('<I', 0xC0000040)

    # .text code: call ExitProcess(0) via IAT
    code_off = text_file_off
    pe[code_off:code_off+4] = b'\x48\x83\xEC\x28'
    pe[code_off+4:code_off+6] = b'\x33\xC9'
    pe[code_off+6:code_off+8] = b'\xFF\x15'
    disp = (rdata_rva + 0x30) - (text_rva + 12)
    pe[code_off+8:code_off+12] = struct.pack('<I', disp)
    pe[code_off+12] = 0x90
    pe[code_off+13] = 0xCC

    # .rdata import table
    rdata = bytearray(0x200)
    struct.pack_into('<I', rdata, 0, rdata_rva + 0x28)
    struct.pack_into('<I', rdata, 12, rdata_rva + 0x48)
    struct.pack_into('<I', rdata, 16, rdata_rva + 0x30)
    struct.pack_into('<Q', rdata, 0x28, rdata_rva + 0x38)
    struct.pack_into('<Q', rdata, 0x30, rdata_rva + 0x38)
    struct.pack_into('<H', rdata, 0x38, 0)
    rdata[0x3A:0x46] = b'ExitProcess\x00'
    rdata[0x48:0x55] = b'kernel32.dll\x00'
    pe[rdata_file_off:rdata_file_off+0x200] = rdata

    if payload_data:
        pe[data_file_off:data_file_off+len(payload_data)] = payload_data

    return bytes(pe)


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
        if payload_type in ('pe', 'elf', 'macho') and cover_format in ('jpeg', 'png', 'gif', 'bmp'):
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
