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


def build_polyglot(cover_path: str, payload_path: str, output_path: str,
                   cover_format: str = 'auto', verbose: bool = False) -> dict:
    """
    Build a polyglot file by appending a payload after the cover file's
    natural end marker.

    Args:
        cover_path: Path to the cover file (image/document/video)
        payload_path: Path to the payload file to embed
        output_path: Path for the output polyglot file
        cover_format: Force cover format ('auto' tries to detect)
        verbose: Print detailed info

    Returns:
        dict with build stats
    """
    # Read cover file
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

    # Find insertion point (after end marker)
    finder_map = {
        'jpeg': find_jpeg_eoi,
        'png': find_png_iend,
        'gif': find_gif_trailer,
        'pdf': find_pdf_eof,
        'zip': find_zip_eocd,
    }

    finder = finder_map.get(cover_format)
    if finder:
        insert_pos = finder(cover_data)
    else:
        # For formats without clear end markers, append at end
        insert_pos = len(cover_data)

    # Build polyglot: cover up to end marker + payload
    polyglot_data = cover_data[:insert_pos] + payload_data

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
        'technique': fmt['description'],
    }

    if verbose:
        print(f"\n{'='*60}")
        print(f"  POLYGLOT BUILDER — Educational Tool")
        print(f"{'='*60}")
        print(f"  Cover:     {cover_path}")
        print(f"  Format:    {fmt['name']}")
        print(f"  Cover:     {len(cover_data):,} bytes")
        print(f"  Payload:   {len(payload_data):,} bytes")
        print(f"  Output:    {len(polyglot_data):,} bytes")
        print(f"  Insert at: byte {insert_pos:,}")
        print(f"  Technique: {fmt['description']}")
        print(f"  Output:    {output_path}")
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
                           args.format, args.verbose)

    if not args.verbose:
        print(f"[+] Polyglot built: {stats['output_path']} ({stats['polyglot_size']:,} bytes)")


if __name__ == '__main__':
    main()
