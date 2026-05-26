#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  POLYGLOT TOOLKIT v3.0 — Single Entry Point                  ║
║  GUI + CLI + TUI — One file to rule them all                 ║
║  Author: Mr-DS-ML-85                                         ║
╚══════════════════════════════════════════════════════════════╝

Usage:
  python polyglot.py                          Auto-detect (GUI if display, else TUI)
  python polyglot.py gui                      PyQt6 GUI
  python polyglot.py tui                      Rich TUI (interactive menu)
  python polyglot.py build <cover> <payload>  Build polyglot (CLI)
  python polyglot.py scan <file_or_dir>       Scan for threats (CLI)
  python polyglot.py sanitize <file_or_dir>   Strip hidden data (CLI)
  python polyglot.py train [--samples N]      Generate data + train model
  python polyglot.py monitor <dir>            Real-time monitor (CLI)
  python polyglot.py help                     Show help

Build binary:
  make build          → dist/polyglot (single executable)
"""

import sys
import os
import argparse

# Ensure we can find engines/ relative to this file
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)


def has_display():
    """Check if a graphical display is available."""
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return True
    if sys.platform == "win32":
        return True
    if sys.platform == "darwin":
        return True
    return False


def run_gui():
    """Launch PyQt6 GUI application."""
    from polyglot_app import main as gui_main
    gui_main()


def run_tui():
    """Launch Rich TUI application."""
    from polyglot_tui import main as tui_main
    tui_main()


def run_build(args):
    """CLI: Build a polyglot file."""
    from polyglot_tui import PolyglotBuilder
    import json

    if len(args) < 2:
        print("Usage: polyglot build <cover> <payload> [options]")
        print("  --type <jpeg|png|gif|pdf|zip|mp4>  Container type")
        print("  --encrypt                           XOR encrypt payload")
        print("  --fud                               FUD cryptor obfuscation")
        print("  --mime                              MIME-type confusion")
        print("  --output <path>                     Output file path")
        sys.exit(1)

    cover, payload = args[0], args[1]
    container = "jpeg"
    encrypt = fud = mime = False
    output = None

    i = 2
    while i < len(args):
        if args[i] == "--type" and i + 1 < len(args):
            container = args[i + 1]; i += 2
        elif args[i] == "--encrypt":
            encrypt = True; i += 1
        elif args[i] == "--fud":
            fud = True; i += 1
        elif args[i] == "--mime":
            mime = True; i += 1
        elif args[i] == "--output" and i + 1 < len(args):
            output = args[i + 1]; i += 2
        else:
            i += 1

    if not output:
        output = f"polyglot.{container}"

    b = PolyglotBuilder()
    try:
        stats = b.build(cover, payload, output, container, encrypt, fud, mime)
        print(json.dumps(stats, indent=2, default=str))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


def run_scan(args):
    """CLI: Scan files for polyglot threats."""
    from polyglot_tui import PolyglotDetector

    if not args:
        print("Usage: polyglot scan <file_or_dir>")
        sys.exit(1)

    target = args[0]
    detector = PolyglotDetector()

    if os.path.isfile(target):
        files = [target]
    elif os.path.isdir(target):
        exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.pdf', '.doc', '.docx',
                '.zip', '.exe', '.dll', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.mp4'}
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
        findings = detector.scan_file(fpath)
        fname = os.path.basename(fpath)
        crit = [f for f in findings if f['severity'] in ('critical', 'high')]
        if crit:
            threats += len(crit)
            print(f"⚠ {fname}")
            for f in findings:
                print(f"  [{f['severity'].upper()}] {f['type']}: {f['detail']}")
        else:
            print(f"✓ {fname}")

    status = f"THREATS: {threats}" if threats else "ALL CLEAN"
    print(f"\n{status} — {len(files)} files")


def run_sanitize(args):
    """CLI: Sanitize files (strip hidden payloads)."""
    from polyglot_tui import PolyglotSanitizer

    if not args:
        print("Usage: polyglot sanitize <file_or_dir> [--no-backup]")
        sys.exit(1)

    target = args[0]
    backup = "--no-backup" not in args
    sanitizer = PolyglotSanitizer()

    if os.path.isfile(target):
        files = [target]
    elif os.path.isdir(target):
        exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.pdf', '.zip', '.mp4'}
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
        result = sanitizer.sanitize(fpath, backup)
        fname = os.path.basename(fpath)
        if result['status'] == 'sanitized':
            print(f"✓ {fname} — {result['detail']}")
        else:
            print(f"○ {fname} — {result['detail']}")


def run_train(args):
    """CLI: Generate training data + train model."""
    samples = 50
    task = "GPU"
    i = 0
    while i < len(args):
        if args[i] == "--samples" and i + 1 < len(args):
            samples = int(args[i + 1]); i += 2
        elif args[i] == "--cpu":
            task = "CPU"; i += 1
        elif args[i] == "--gpu":
            task = "GPU"; i += 1
        else:
            i += 1

    # Step 1: Generate training data
    print("[1/2] Generating training data...")
    from generate_training_data import ComprehensiveGenerator, extract_and_export, generate_yara_training_data
    gen = ComprehensiveGenerator("training_data")
    sample_list = gen.generate_dataset(n_per_type=samples)
    n_ok, n_fail = extract_and_export(sample_list, "training_dataset.csv")
    generate_yara_training_data(sample_list, "yara_training.json")
    print(f"  Generated {n_ok} samples ({n_fail} failed)")

    # Step 2: Train model
    print("\n[2/2] Training CatBoost model...")
    from train_model import train
    train("training_dataset.csv", task, "models/polyglot_shield.cbm")


def run_monitor(args):
    """CLI: Real-time directory monitor."""
    from polyglot_tui import PolyglotTUI
    tui = PolyglotTUI()
    tui.menu_monitor()


def show_help():
    """Show help text."""
    help_text = """
╔══════════════════════════════════════════════════════════════╗
║  POLYGLOT TOOLKIT v3.0 — Red Team + Shield Edition           ║
║  Author: Mr-DS-ML-85                                         ║
╚══════════════════════════════════════════════════════════════╝

MODES:
  (no args)                         Auto-detect: GUI if display, else TUI
  gui                               PyQt6 GUI (9 panels)
  tui                               Rich TUI (interactive terminal menu)

CLI COMMANDS:
  build <cover> <payload> [opts]    Build polyglot file
  scan <file_or_dir>                Scan for hidden threats
  sanitize <file_or_dir>            Strip hidden payloads
  train [--samples N] [--gpu]       Generate data + train ML model
  monitor <dir>                     Real-time directory monitor

BUILD OPTIONS:
  --type <jpeg|png|gif|pdf|zip|mp4> Container type (default: jpeg)
  --encrypt                         XOR encrypt payload
  --fud                             FUD cryptor (multi-layer obfuscation)
  --mime                            MIME-type confusion headers
  --output <path>                   Output file path

TRAIN OPTIONS:
  --samples N                       Samples per type (default: 50)
  --gpu                             GPU training (default)
  --cpu                             CPU training

EXAMPLES:
  polyglot gui
  polyglot build cover.jpg payload.exe --type jpeg --encrypt --fud
  polyglot scan ~/Downloads
  polyglot sanitize suspicious.jpg
  polyglot train --samples 100 --gpu
  polyglot monitor ~/Downloads

ATTACK VECTORS (Builder):
  Standard Polyglot, FUD Cryptor, MIME Confusion, Covert Embedding

ML FEATURES (Scanner):
  338-feature extraction, CatBoost GPU classifier, 26 YARA rules
  Targets: PE-in-PDF, ELF-in-ZIP, Cobalt Strike, Metasploit, UPX, shellcode

FIRST TIME:
  polyglot train --samples 100     Train the ML model
  polyglot gui                     Launch GUI → Scanner → Use ML Model
"""
    print(help_text)


def main():
    """Single entry point — dispatches to GUI, TUI, or CLI."""
    # If no args, auto-detect mode
    if len(sys.argv) == 1:
        if has_display():
            run_gui()
        else:
            run_tui()
        return

    command = sys.argv[1].lower()
    args = sys.argv[2:]

    dispatch = {
        'gui': lambda: run_gui(),
        'tui': lambda: run_tui(),
        'build': lambda: run_build(args),
        'scan': lambda: run_scan(args),
        'sanitize': lambda: run_sanitize(args),
        'train': lambda: run_train(args),
        'monitor': lambda: run_monitor(args),
        'help': lambda: show_help(),
        '--help': lambda: show_help(),
        '-h': lambda: show_help(),
    }

    handler = dispatch.get(command)
    if handler:
        handler()
    else:
        print(f"Unknown command: {command}")
        print("Run: polyglot help")
        sys.exit(1)


if __name__ == '__main__':
    main()
