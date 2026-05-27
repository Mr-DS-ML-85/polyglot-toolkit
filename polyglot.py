#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  POLYGLOT TOOLKIT v3.0 — Single Entry Point                  ║
║  GUI + CLI + TUI + Server — One file to rule them all        ║
║  Author: Mr-DS-ML-85                                         ║
╚══════════════════════════════════════════════════════════════╝

Usage:
  python polyglot.py                          Auto-detect (GUI if display, else TUI)
  python polyglot.py gui                      PyQt6 GUI
  python polyglot.py tui                      Rich TUI (interactive menu)
  python polyglot.py server [--port 8888]     Headless API + web dashboard
  python polyglot.py build <cover> <payload>  Build polyglot (CLI)
  python polyglot.py scan <file_or_dir>       Scan for threats (CLI)
  python polyglot.py sanitize <file_or_dir>   Strip hidden data (CLI)
  python polyglot.py recover <file_or_dir>    Restore .bak backup files
  python polyglot.py train [--samples N]      Generate data + train model
  python polyglot.py monitor <dir>            Real-time monitor (CLI)
  python polyglot.py help                     Show help

Build binary:
  make build          → dist/polyglot (single executable)
"""

import sys
import os
import shutil

# Ensure we can find engines/ relative to this file
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

# ═══════════════════════════════════════════════════════════════
# SAFETY & EDUCATIONAL WARNINGS
# ═══════════════════════════════════════════════════════════════

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║  POLYGLOT TOOLKIT v3.0 — Red Team + Shield Edition           ║
║  Author: Mr-DS-ML-85                                         ║
╚══════════════════════════════════════════════════════════════╝"""

DISCLAIMER = """
  ⚠  FOR EDUCATIONAL & AUTHORIZED SECURITY TESTING ONLY
  Unauthorized use against systems you don't own is illegal.
  The author is not responsible for any misuse of this tool.
"""

SAFETY_NOTES = """
  ⚠  SAFETY NOTES:
  • Scanner may produce FALSE POSITIVES — always verify findings manually
  • Sanitizer creates .bak backups by default — keep them until you verify
  • NEVER sanitize or delete your only copy of a file
  • PDFs with XMP/Canva/Adobe trailing metadata are NOT threats — that's normal
  • Use --dry-run to preview what the sanitizer would change
  • Use 'polyglot recover' to restore .bak backup files
"""


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
    try:
        from polyglot_app import main as gui_main
        gui_main()
    except ImportError as e:
        print(f"GUI dependencies not available: {e}")
        print("Install: pip install PyQt6")
        sys.exit(1)
    except Exception as e:
        print(f"GUI error: {e}")
        sys.exit(1)


def run_tui():
    """Launch Rich TUI application."""
    try:
        from polyglot_tui import main as tui_main
        tui_main()
    except ImportError as e:
        print(f"TUI dependencies not available: {e}")
        print("Install: pip install rich")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nInterrupted. Stay stealthy. ── Mr-DS-ML-85")
        sys.exit(0)
    except Exception as e:
        print(f"TUI error: {e}")
        sys.exit(1)


def run_build(args):
    """CLI: Build a polyglot file."""
    from polyglot_tui import PolyglotBuilder

    if len(args) < 2:
        print("Usage: polyglot build <cover> <payload> [options]")
        print("  --type <jpeg|png|gif|pdf|zip|mp4|xlsx|docx>  Container type")
        print("  --payload-type <vbs|ps1|bash|sh|python|applescript|xlsx|docx>  Payload wrapper")
        print("  --target-os <windows|linux|macos|all>        Target platform (default: windows)")
        print("  --encrypt                                     XOR encrypt payload")
        print("  --fud                                         FUD cryptor obfuscation")
        print("  --mime                                        MIME-type confusion")
        print("  --output <path>                               Output file path")
        sys.exit(1)

    cover_path, payload_path = args[0], args[1]
    container = "jpeg"
    encrypt = fud = mime = False
    output = None
    payload_type = None
    target_os = "windows"

    i = 2
    while i < len(args):
        if args[i] == "--type" and i + 1 < len(args):
            container = args[i + 1]; i += 2
        elif args[i] == "--payload-type" and i + 1 < len(args):
            payload_type = args[i + 1]; i += 2
        elif args[i] == "--target-os" and i + 1 < len(args):
            target_os = args[i + 1].lower(); i += 2
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

    if not os.path.isfile(cover_path):
        print(f"Cover file not found: {cover_path}")
        sys.exit(1)
    if not os.path.isfile(payload_path):
        print(f"Payload file not found: {payload_path}")
        sys.exit(1)

    builder = PolyglotBuilder()
    try:
        # If target_os is "all", build for each platform
        if target_os == "all" and payload_type:
            platform_map = {
                'linux': {'ext': 'linux', 'os': 'linux'},
                'macos': {'ext': 'macos', 'os': 'macos'},
                'windows': {'ext': 'win', 'os': 'windows'},
            }
            base, ext = os.path.splitext(output)
            built = []
            for plat_name, plat_info in platform_map.items():
                plat_output = f"{base}_{plat_info['ext']}{ext}"
                try:
                    stats = builder.build(cover_path, payload_path, plat_output,
                                          container_type=container, encrypt=encrypt,
                                          fud=fud, mime_confuse=mime,
                                          payload_type=payload_type,
                                          target_os=plat_info['os'])
                    print(f"\n  [{plat_name.upper()}] Output: {plat_output}")
                    print(f"    Payload Type: {stats.get('payload_type', 'N/A')}")
                    print(f"    Total:        {stats['output_size']:,} bytes")
                    built.append(plat_name)
                except ValueError as e:
                    print(f"\n  [{plat_name.upper()}] Skipped: {e}")
            print(f"\n  ✓ Built {len(built)}/3 platform variants: {', '.join(built)}")
            return

        stats = builder.build(cover_path, payload_path, output,
                              container_type=container, encrypt=encrypt,
                              fud=fud, mime_confuse=mime, payload_type=payload_type,
                              target_os=target_os)
        print(f"\n  Output:       {stats['output']}")
        print(f"  Container:    {stats['container_type']}")
        print(f"  Target OS:    {target_os}")
        if stats.get('payload_type'):
            print(f"  Payload Type: {stats['payload_type']}")
        print(f"  Cover:        {stats['cover_size']:,} bytes")
        print(f"  Payload:      {stats['payload_size']:,} bytes")
        print(f"  Total:        {stats['output_size']:,} bytes")
        print(f"  Offset:       0x{stats['payload_offset']:X}")
        print(f"  Entropy:      {stats['entropy']}")
        print(f"  Encrypted:    {'Yes' if stats['encrypted'] else 'No'}")
        print(f"  FUD:          {'Yes' if stats['fud_protected'] else 'No'}")
        print(f"  MIME Confuse: {'Yes' if stats['mime_confused'] else 'No'}")
        print(f"\n  ✓ Polyglot built: {output}")
    except Exception as e:
        print(f"Build error: {e}")
        sys.exit(1)


def run_scan(args):
    """CLI: Scan files for polyglot threats."""
    from polyglot_tui import PolyglotDetector

    if not args:
        print("Usage: polyglot scan <file_or_dir>")
        sys.exit(1)

    target = args[0]
    detector = PolyglotDetector()

    # Try to load ML model
    model = None
    try:
        from engines.model import PolyglotModel
        from engines.features import extract_features_from_file
        from pathlib import Path
        model_path = "models/polyglot_shield.cbm"
        if Path(model_path).exists():
            model = PolyglotModel({'task_type': 'CPU'})
            model.load(model_path)
    except Exception:
        pass

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
        print(f"Not found: {target}")
        sys.exit(1)

    threats = 0
    status = "ALL CLEAN"
    for fpath in files:
        fname = os.path.basename(fpath)
        try:
            findings = detector.scan_file(fpath)
            crit = [f for f in findings if f['severity'] in ('critical', 'high')]

            # ML prediction
            ml_info = ""
            if model and model.is_loaded:
                try:
                    feats = extract_features_from_file(fpath)
                    pred = model.predict_single(feats)
                    ml_info = f"  ML: {pred['label']} ({pred['risk_score']:.1f}% risk, {pred['risk_level']})"
                except Exception:
                    pass

            if crit:
                threats += len(crit)
                status = "THREATS FOUND"
                print(f"  ⚠ {fname}")
                for f in findings:
                    print(f"    [{f['severity'].upper()}] {f['type']}: {f['detail']}")
                if ml_info:
                    print(f"   {ml_info}")
            elif findings:
                print(f"  ○ {fname} — minor warnings")
                if ml_info:
                    print(f"   {ml_info}")
            else:
                print(f"  ✓ {fname}")
                if ml_info:
                    print(f"   {ml_info}")
        except Exception as e:
            print(f"  ✗ {fname} — scan error: {e}")

    print(f"\n{status} — {len(files)} files scanned")


def run_sanitize(args):
    """CLI: Sanitize files (strip hidden payloads)."""
    from polyglot_tui import PolyglotSanitizer

    if not args:
        print("Usage: polyglot sanitize <file_or_dir> [--no-backup] [--dry-run]")
        sys.exit(1)

    target = args[0]
    backup = "--no-backup" not in args
    dry_run = "--dry-run" in args
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
        print(f"Not found: {target}")
        sys.exit(1)

    if dry_run:
        print("  [DRY-RUN MODE — no files will be modified]\n")

    sanitized = 0
    dangers = 0
    for fpath in files:
        fname = os.path.basename(fpath)
        prefix = "[DRY-RUN] " if dry_run else ""
        try:
            result = sanitizer.sanitize(fpath, backup and not dry_run)
            if result.get('safe_metadata'):
                print(f"{prefix}○ {fname} — {result['detail']} (safe, not modified)")
            elif result['status'] == 'sanitized':
                sanitized += 1
                print(f"{prefix}✓ {fname} — {result['detail']}")
            elif result['status'] == 'danger':
                dangers += 1
                print(f"{prefix}⚠ {fname} — {result['detail']}")
            else:
                print(f"{prefix}○ {fname} — {result['detail']}")
        except Exception as e:
            print(f"{prefix}✗ {fname} — error: {e}")

    if dry_run:
        print(f"\n  [DRY-RUN] Would sanitize {sanitized}/{len(files)} files")
    elif sanitized:
        print(f"\n  Sanitized {sanitized}/{len(files)} files")
        print("  ⚠  .bak backups created — verify before deleting them")
    elif dangers:
        print(f"\n  ⚠ {dangers}/{len(files)} files are POLYGLOTS — cannot auto-sanitize, recommend quarantine or delete")
    else:
        print(f"\n  All {len(files)} files clean")


def run_recover(args):
    """CLI: Recover files from .bak backups."""
    if not args:
        print("Usage: polyglot recover <file_or_dir>")
        print("  Finds .bak files and restores the originals")
        sys.exit(1)

    target = args[0]
    dest_dir = None
    if "--dest" in args:
        idx = args.index("--dest")
        if idx + 1 < len(args):
            dest_dir = args[idx + 1]

    bak_files = []

    if os.path.isfile(target + '.bak'):
        bak_files = [target + '.bak']
    elif os.path.isfile(target) and target.endswith('.bak'):
        bak_files = [target]
    elif os.path.isdir(target):
        for root, dirs, fnames in os.walk(target):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in fnames:
                if f.endswith('.bak'):
                    bak_files.append(os.path.join(root, f))
    else:
        print(f"Not found: {target}")
        sys.exit(1)

    if not bak_files:
        print("No .bak backup files found.")
        return

    print(f"\n  Found {len(bak_files)} backup file(s)\n")
    restored = 0
    for bak in bak_files:
        original = bak[:-4]  # Remove .bak
        fname = os.path.basename(original)
        try:
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)
                dest = os.path.join(dest_dir, fname)
            else:
                dest = original
            shutil.copy2(bak, dest)
            print(f"  ✓ Restored: {fname} → {dest}")
            restored += 1
        except Exception as e:
            print(f"  ✗ Failed: {fname} — {e}")

    print(f"\n  Restored {restored}/{len(bak_files)} files")


def run_train(args):
    """CLI: Generate training data + train model."""
    samples = 50
    task = "GPU"
    i = 0
    while i < len(args):
        if args[i] == "--samples" and i + 1 < len(args):
            try:
                samples = int(args[i + 1])
            except ValueError:
                print(f"Invalid --samples value: {args[i + 1]}")
                sys.exit(1)
            i += 2
        elif args[i] == "--cpu":
            task = "CPU"; i += 1
        elif args[i] == "--gpu":
            task = "GPU"; i += 1
        else:
            i += 1

    print(DISCLAIMER)
    print(f"  Generating {samples} samples per type, training on {task}...\n")

    # Step 1: Generate training data
    print("[1/2] Generating training data...")
    try:
        from generate_training_data import ComprehensiveGenerator, extract_and_export, generate_yara_training_data
        gen = ComprehensiveGenerator("training_data")
        sample_list = gen.generate_dataset(n_per_type=samples)
        n_ok, n_fail = extract_and_export(sample_list, "training_dataset.csv")
        generate_yara_training_data(sample_list, "yara_training.json")
        print(f"  Generated {n_ok} samples ({n_fail} failed)")
    except Exception as e:
        print(f"  Training data generation error: {e}")
        sys.exit(1)

    # Step 2: Train model
    print("\n[2/2] Training CatBoost model...")
    try:
        from train_model import train
        train("training_dataset.csv", task, "models/polyglot_shield.cbm")
    except Exception as e:
        print(f"  Training error: {e}")
        sys.exit(1)


def run_monitor(args):
    """CLI: Real-time directory monitor."""
    if not args:
        print("Usage: polyglot monitor <directory>")
        sys.exit(1)

    directory = args[0]
    if not os.path.isdir(directory):
        print(f"Not a directory: {directory}")
        sys.exit(1)

    try:
        from polyglot_tui import PolyglotTUI
        tui = PolyglotTUI()
        tui.menu_monitor()
    except KeyboardInterrupt:
        print("\n\nMonitor stopped.")
        sys.exit(0)


def run_server(args):
    """Launch server mode (headless API + web dashboard)."""
    try:
        from server import main as server_main
        sys.argv = ['server.py'] + args
        server_main()
    except ImportError as e:
        print(f"Server dependencies not available: {e}")
        print("Install: pip install flask")
    except KeyboardInterrupt:
        print("\n\nServer stopped.")
        sys.exit(0)


def run_service(args):
    """Manage background monitoring service."""
    from daemon import start_daemon, stop_daemon, show_status, install_service, uninstall_service
    if not args:
        print("Usage: polyglot service <command>")
        print("  start [--dir path]    Start background monitor")
        print("  stop                  Stop background monitor")
        print("  status                Show monitor status")
        print("  install               Install as system service (auto-start)")
        print("  uninstall             Remove system service")
        sys.exit(1)

    cmd = args[0]
    if cmd == "start":
        watch_dirs = None
        if "--dir" in args:
            idx = args.index("--dir")
            watch_dirs = args[idx + 1:]
        start_daemon(watch_dirs)
    elif cmd == "stop":
        stop_daemon()
    elif cmd == "status":
        show_status()
    elif cmd == "install":
        install_service()
    elif cmd == "uninstall":
        uninstall_service()
    else:
        print(f"Unknown service command: {cmd}")
        sys.exit(1)


def show_help():
    """Show help text."""
    help_text = f"""
╔══════════════════════════════════════════════════════════════╗
║  POLYGLOT TOOLKIT v3.0 — Red Team + Shield Edition           ║
║  Author: Mr-DS-ML-85                                         ║
╚══════════════════════════════════════════════════════════════╝
{DISCLAIMER}
MODES:
  (no args)                         Auto-detect: GUI if display, else TUI
  gui                               PyQt6 GUI (9 panels)
  tui                               Rich TUI (interactive terminal menu)
  server [--port 8888]              Server mode (headless API + web dashboard)

CLI COMMANDS:
  build <cover> <payload> [opts]    Build polyglot file
  scan <file_or_dir>                Scan for hidden threats
  sanitize <file_or_dir>            Strip hidden payloads
  recover <file_or_dir>             Restore .bak backup files
  train [--samples N] [--gpu]       Generate data + train ML model
  monitor <dir>                     Real-time directory monitor (foreground)
  service <cmd>                     Background monitor service (persists)

SERVICE COMMANDS:
  service start [--dir path]        Start background monitor
  service stop                      Stop background monitor
  service status                    Show monitor status
  service install                   Install as system service (auto-start on boot)
  service uninstall                 Remove system service

BUILD OPTIONS:
  --type <jpeg|png|gif|pdf|zip|mp4|xlsx|docx>  Container type (default: jpeg)
  --payload-type <TYPE>                         Payload wrapper (default: exe)
  --target-os <windows|linux|macos|all>         Target platform (default: windows)
  --encrypt                                     XOR encrypt payload
  --fud                                         FUD cryptor (multi-layer obfuscation)
  --mime                                        MIME-type confusion headers
  --output <path>                               Output file path

PAYLOAD TYPES:
  Windows:   vbs, ps1 (PowerShell)
  Linux:     bash, sh (POSIX)
  macOS:     applescript (osascript)
  All OS:    python (cross-platform Python dropper)
  Office:    xlsx, docx (VBA macro — auto-adapts to macOS)

SANITIZE OPTIONS:
  --no-backup                       Don't create .bak backups
  --dry-run                         Preview changes without modifying files

RECOVER OPTIONS:
  --dest <dir>                      Restore to a different directory

TRAIN OPTIONS:
  --samples N                       Samples per type (default: 50)
  --gpu                             GPU training (default)
  --cpu                             CPU training

SERVER OPTIONS:
  --host 127.0.0.1                  Bind address (use 0.0.0.0 for remote)
  --port 8888                       Port number

EXAMPLES:
  polyglot gui
  polyglot server --port 9999 --host 0.0.0.0
  polyglot build cover.jpg payload.exe --type jpeg --encrypt --fud
  polyglot build cover.jpg payload.exe --type jpeg --payload-type vbs --mime
  polyglot build cover.jpg payload.exe --type jpeg --payload-type ps1 --encrypt
  polyglot build cover.jpg payload.bin --type jpeg --payload-type bash --target-os linux
  polyglot build cover.jpg payload.bin --type jpeg --payload-type python --target-os all
  polyglot build cover.jpg payload.bin --type jpeg --payload-type applescript --target-os macos
  polyglot build cover.xlsx payload.exe --type xlsx
  polyglot scan ~/Downloads
  polyglot sanitize suspicious.jpg --dry-run
  polyglot recover ~/Downloads
  polyglot train --samples 100 --gpu
  polyglot monitor ~/Downloads
  polyglot service start --dir ~/Downloads
  polyglot service install
  polyglot service status
{SAFETY_NOTES}
FIRST TIME:
  polyglot train --samples 100     Train the ML model
  polyglot gui                     Launch GUI → Scanner → Use ML Model
  polyglot service install         Auto-start background monitor
"""
    print(help_text)


# ═══════════════════════════════════════════════════════════════
# MAIN DISPATCH
# ═══════════════════════════════════════════════════════════════

def main():
    """Single entry point — dispatches to GUI, TUI, Server, or CLI."""
    # If no args, auto-detect mode
    if len(sys.argv) == 1:
        print(BANNER)
        print(DISCLAIMER)
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
        'server': lambda: run_server(args),
        'build': lambda: run_build(args),
        'scan': lambda: run_scan(args),
        'sanitize': lambda: run_sanitize(args),
        'recover': lambda: run_recover(args),
        'train': lambda: run_train(args),
        'monitor': lambda: run_monitor(args),
        'service': lambda: run_service(args),
        'help': lambda: show_help(),
        '--help': lambda: show_help(),
        '-h': lambda: show_help(),
    }

    handler = dispatch.get(command)
    if handler:
        try:
            handler()
        except KeyboardInterrupt:
            print("\n\nInterrupted. ── Mr-DS-ML-85")
            sys.exit(0)
        except Exception as e:
            print(f"\nError: {e}")
            sys.exit(1)
    else:
        print(f"Unknown command: {command}")
        print("Run: polyglot help")
        sys.exit(1)


if __name__ == '__main__':
    main()
