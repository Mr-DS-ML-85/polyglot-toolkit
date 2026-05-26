#!/usr/bin/env python3
"""
Polyglot Sanitizer — Strips hidden payloads from files.

Scans files for data after format-specific end markers and removes it,
leaving a clean file that works normally as its declared format.

Author: Mr-DS-ML-85
License: MIT
"""

import argparse
import os
import sys
import shutil
from pathlib import Path

# ============================================================
# Format definitions with end marker locators
# ============================================================

FORMATS = {
    'jpeg': {
        'magic': b'\xff\xd8\xff',
        'name': 'JPEG',
        'extensions': ['.jpg', '.jpeg'],
    },
    'png': {
        'magic': b'\x89PNG\r\n\x1a\n',
        'name': 'PNG',
        'extensions': ['.png'],
    },
    'gif87a': {
        'magic': b'GIF87a',
        'name': 'GIF87a',
        'extensions': ['.gif'],
    },
    'gif89a': {
        'magic': b'GIF89a',
        'name': 'GIF89a',
        'extensions': ['.gif'],
    },
    'pdf': {
        'magic': b'%PDF',
        'name': 'PDF',
        'extensions': ['.pdf'],
    },
    'bmp': {
        'magic': b'BM',
        'name': 'BMP',
        'extensions': ['.bmp'],
    },
    'zip': {
        'magic': b'PK\x03\x04',
        'name': 'ZIP',
        'extensions': ['.zip'],
    },
    'rar': {
        'magic': b'Rar!\x1a\x07',
        'name': 'RAR',
        'extensions': ['.rar'],
    },
    '7z': {
        'magic': b'7z\xbc\xaf\x27\x1c',
        'name': '7-Zip',
        'extensions': ['.7z'],
    },
    'gzip': {
        'magic': b'\x1f\x8b',
        'name': 'GZIP',
        'extensions': ['.gz'],
    },
    'elf': {
        'magic': b'\x7fELF',
        'name': 'ELF',
        'extensions': ['.elf', ''],
    },
}


def detect_format(data: bytes) -> str:
    """Detect file format from magic bytes."""
    for fmt_name, fmt_info in FORMATS.items():
        magic = fmt_info['magic']
        if data[:len(magic)] == magic:
            return fmt_name
    if data[:2] == b'MZ':
        return 'exe'
    return 'unknown'


def find_clean_end(data: bytes, fmt_name: str) -> int:
    """
    Find the proper end position for a file format.
    Returns the byte position where the file should end.
    """
    if fmt_name == 'jpeg':
        # Find the LAST EOI marker (FF D9)
        pos = data.rfind(b'\xff\xd9')
        if pos == -1:
            return len(data)
        return pos + 2

    elif fmt_name == 'png':
        # Find the IEND chunk: length(4) + 'IEND'(4) + CRC(4) = 12 bytes
        pos = data.rfind(b'IEND')
        if pos == -1:
            return len(data)
        return pos + 8  # IEND + CRC

    elif fmt_name in ('gif87a', 'gif89a'):
        # Find the GIF trailer (0x3B)
        pos = data.rfind(b'\x3b')
        if pos == -1:
            return len(data)
        return pos + 1

    elif fmt_name == 'pdf':
        # Find the last %%EOF
        pos = data.rfind(b'%%EOF')
        if pos == -1:
            return len(data)
        # PDF spec says %%EOF should be followed by optional whitespace
        end = pos + 5
        # Skip trailing newlines/carriage returns
        while end < len(data) and data[end:end+1] in (b'\n', b'\r', b' '):
            end += 1
        return end

    elif fmt_name == 'zip':
        # Find End of Central Directory (PK\x05\x06)
        pos = data.rfind(b'PK\x05\x06')
        if pos == -1:
            return len(data)
        # EOCD: sig(4) + disk(2) + cd_disk(2) + cd_entries_disk(2) +
        #        cd_entries(2) + cd_size(4) + cd_offset(4) + comment_len(2) = 22
        if pos + 22 > len(data):
            return len(data)
        comment_len = struct.unpack('<H', data[pos+20:pos+22])[0]
        return pos + 22 + comment_len

    elif fmt_name in ('rar', '7z', 'gzip'):
        # For archives, we can't easily find the end without full parsing
        # Return full length (no trimming possible)
        return len(data)

    elif fmt_name == 'bmp':
        # BMP file size is in bytes 2-5 (little-endian)
        if len(data) >= 6:
            declared_size = struct.unpack('<I', data[2:6])[0]
            if 0 < declared_size < len(data):
                return declared_size
        return len(data)

    return len(data)


def sanitize_file(filepath: str, output_path: str = None,
                  backup: bool = True, verbose: bool = False,
                  force: bool = False) -> dict:
    """
    Sanitize a file by removing data after its format's end marker.

    Args:
        filepath: Input file path
        output_path: Output path (None = overwrite original with backup)
        backup: Create .bak backup before overwriting
        verbose: Print detailed info
        force: Force sanitization even on 'unknown' formats

    Returns:
        dict with sanitization stats
    """
    data = Path(filepath).read_bytes()
    original_size = len(data)

    fmt_name = detect_format(data)

    if fmt_name == 'unknown':
        if not force:
            return {
                'status': 'skipped',
                'reason': 'Unknown format — use --force to sanitize anyway',
                'file': filepath,
            }
        else:
            # Force mode: just trim null bytes from end
            clean_end = len(data.rstrip(b'\x00'))
            fmt_name = 'unknown (forced)'

    if fmt_name not in ('unknown (forced)',):
        clean_end = find_clean_end(data, fmt_name)

    trimmed = original_size - clean_end

    if trimmed <= 0:
        return {
            'status': 'clean',
            'reason': 'No trailing data found — file is already clean',
            'file': filepath,
            'original_size': original_size,
            'clean_size': original_size,
            'trimmed': 0,
        }

    clean_data = data[:clean_end]

    # Determine output path
    if output_path is None:
        if backup:
            backup_path = filepath + '.bak'
            shutil.copy2(filepath, backup_path)
            if verbose:
                print(f"  [+] Backup created: {backup_path}")
        output_path = filepath

    Path(output_path).write_bytes(clean_data)

    return {
        'status': 'sanitized',
        'file': filepath,
        'output': output_path,
        'format': fmt_name,
        'original_size': original_size,
        'clean_size': len(clean_data),
        'trimmed': trimmed,
        'trimmed_pct': (trimmed / original_size) * 100 if original_size > 0 else 0,
    }


def main():
    parser = argparse.ArgumentParser(
        description='Polyglot Sanitizer — Remove hidden payloads from files',
        epilog='Strips data after format end markers, leaving clean files.'
    )
    parser.add_argument('files', nargs='+', help='Files to sanitize')
    parser.add_argument('-o', '--output', help='Output directory (default: overwrite with backup)')
    parser.add_argument('--no-backup', action='store_true', help='Do not create .bak backups')
    parser.add_argument('-f', '--force', action='store_true', help='Force sanitization on unknown formats')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-r', '--recursive', action='store_true', help='Scan directories recursively')
    parser.add_argument('-n', '--dry-run', action='store_true', help='Show what would be done without doing it')

    args = parser.parse_args()

    # Collect files
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
        print("[!] No files found.")
        sys.exit(1)

    total_trimmed = 0
    total_sanitized = 0
    total_clean = 0
    total_skipped = 0

    print(f"\n{'='*60}")
    print(f"  POLYGLOT SANITIZER")
    print(f"{'='*60}")
    print(f"  Files to process: {len(target_files)}")
    if args.dry_run:
        print(f"  Mode: DRY RUN (no changes)")
    print(f"{'='*60}\n")

    for filepath in target_files:
        try:
            # Determine output path
            if args.output:
                os.makedirs(args.output, exist_ok=True)
                out = os.path.join(args.output, os.path.basename(filepath))
            else:
                out = None

            if args.dry_run:
                # Just scan, don't modify
                data = Path(filepath).read_bytes()
                fmt_name = detect_format(data)
                if fmt_name in FORMATS:
                    clean_end = find_clean_end(data, fmt_name)
                    trimmed = len(data) - clean_end
                    if trimmed > 0:
                        print(f"  [!] WOULD SANITIZE: {filepath}")
                        print(f"      Format: {fmt_name}")
                        print(f"      Trim: {trimmed:,} bytes ({(trimmed/len(data))*100:.1f}%)")
                        total_trimmed += trimmed
                        total_sanitized += 1
                    else:
                        print(f"  [OK] Clean: {filepath}")
                        total_clean += 1
                else:
                    print(f"  [?] Unknown: {filepath}")
                    total_skipped += 1
                continue

            result = sanitize_file(
                filepath, out,
                backup=not args.no_backup,
                verbose=args.verbose,
                force=args.force,
            )

            if result['status'] == 'sanitized':
                print(f"  [!] SANITIZED: {result['file']}")
                print(f"      Format: {result['format']}")
                print(f"      {result['original_size']:,} → {result['clean_size']:,} bytes "
                      f"(removed {result['trimmed']:,} bytes, {result['trimmed_pct']:.1f}%)")
                total_trimmed += result['trimmed']
                total_sanitized += 1
            elif result['status'] == 'clean':
                print(f"  [OK] Clean: {result['file']}")
                total_clean += 1
            elif result['status'] == 'skipped':
                print(f"  [?] Skipped: {result['file']} — {result['reason']}")
                total_skipped += 1

        except Exception as e:
            print(f"  [!] Error: {filepath}: {e}")

    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Sanitized: {total_sanitized}")
    print(f"  Already clean: {total_clean}")
    print(f"  Skipped: {total_skipped}")
    print(f"  Total data removed: {total_trimmed:,} bytes ({total_trimmed/1024:.1f} KB)")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    import struct  # needed for BMP/ZIP parsing
    main()
