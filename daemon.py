#!/usr/bin/env python3
"""
PolyglotShield Background Monitor Daemon
Cross-platform (Windows/macOS/Linux) real-time file monitoring service.

Usage:
    python daemon.py start --dir ~/Downloads        # Start monitoring
    python daemon.py stop                            # Stop monitoring
    python daemon.py status                          # Check if running
    python daemon.py install                         # Install as system service
    python daemon.py uninstall                       # Remove system service

On Windows: Uses pythonw.exe + scheduled task or system tray
On macOS:   Uses launchd plist
On Linux:   Uses systemd user service
"""

import os
import sys
import json
import time
import signal
import platform
import subprocess
import logging
from pathlib import Path

PLATFORM = platform.system()  # 'Windows', 'Darwin', 'Linux'
HOME = Path.home()
APP_NAME = "polyglot-shield"
PID_FILE = HOME / ".polyglot" / "monitor.pid"
CONFIG_FILE = HOME / ".polyglot" / "monitor.json"
LOG_FILE = HOME / ".polyglot" / "monitor.log"

# Ensure directory exists before logging
(HOME / ".polyglot").mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(APP_NAME)


def get_config():
    """Load or create default monitor config."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    default = {
        "watch_dirs": [str(HOME / "Downloads")],
        "scan_interval": 5,
        "notify": True,
        "auto_quarantine": False,
        "extensions": [
            ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".pdf",
            ".doc", ".docx", ".xls", ".xlsx", ".zip", ".exe",
            ".dll", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".mp4"
        ]
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(default, f, indent=2)
    return default


def save_config(config):
    """Save monitor config."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def is_running():
    """Check if the daemon is running."""
    if not PID_FILE.exists():
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
        if PLATFORM == "Windows":
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True, text=True
            )
            return str(pid) in result.stdout
        else:
            os.kill(pid, 0)
            return True
    except (ProcessLookupError, ValueError, PermissionError):
        PID_FILE.unlink(missing_ok=True)
        return False


def get_pid():
    """Get the running daemon PID."""
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except ValueError:
            return None
    return None


def start_daemon(watch_dirs=None):
    """Start the background monitoring daemon."""
    if is_running():
        print(f"Daemon already running (PID: {get_pid()})")
        return

    config = get_config()
    if watch_dirs:
        config["watch_dirs"] = watch_dirs
        save_config(config)

    # Import here to avoid loading heavy modules for simple commands
    script = Path(__file__).parent / "polyglot_tui.py"
    if not script.exists():
        script = Path(__file__).parent / "polyglot.py"

    if PLATFORM == "Windows":
        # On Windows, use pythonw.exe (no console window)
        pythonw = sys.executable.replace("python.exe", "pythonw.exe")
        if not Path(pythonw).exists():
            pythonw = sys.executable

        # Use subprocess with CREATE_NO_WINDOW flag
        proc = subprocess.Popen(
            [pythonw, str(Path(__file__).resolve()), "_run_monitor",
             json.dumps(config["watch_dirs"])],
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        # On Unix, use nohup + detach
        proc = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "_run_monitor",
             json.dumps(config["watch_dirs"])],
            stdout=open(LOG_FILE, 'a'),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(proc.pid))
    print(f"Monitor started (PID: {proc.pid})")
    print(f"Watching: {', '.join(config['watch_dirs'])}")
    logger.info(f"Monitor started, PID={proc.pid}")


def stop_daemon():
    """Stop the background monitoring daemon."""
    if not is_running():
        print("Daemon is not running")
        PID_FILE.unlink(missing_ok=True)
        return

    pid = get_pid()
    try:
        if not pid:
            print('No PID found'); return
        if PLATFORM == "Windows":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                          capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        print(f"Monitor stopped (PID: {pid})")
        logger.info(f"Monitor stopped, PID={pid}")
    except (ProcessLookupError, PermissionError) as e:
        print(f"Error stopping: {e}")
    finally:
        PID_FILE.unlink(missing_ok=True)


def show_status():
    """Show daemon status."""
    if is_running():
        pid = get_pid()
        config = get_config()
        print(f"Status: RUNNING (PID: {pid})")
        print(f"Watching: {', '.join(config['watch_dirs'])}")
        print(f"Log: {LOG_FILE}")
    else:
        print("Status: STOPPED")


def install_service():
    """Install as a system service for auto-start on boot."""
    config = get_config()

    if PLATFORM == "Linux":
        service_dir = HOME / ".config" / "systemd" / "user"
        service_dir.mkdir(parents=True, exist_ok=True)
        service_file = service_dir / f"{APP_NAME}.service"

        service_content = f"""[Unit]
Description=PolyglotShield Real-Time Monitor
After=network.target

[Service]
Type=simple
ExecStart={sys.executable} {Path(__file__).resolve()} _run_monitor '{json.dumps(config["watch_dirs"])}'
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
"""
        service_file.write_text(service_content)
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        subprocess.run(["systemctl", "--user", "enable", APP_NAME], capture_output=True)
        print(f"Installed systemd service: {service_file}")
        print(f"Start with: systemctl --user start {APP_NAME}")

    elif PLATFORM == "Darwin":
        plist_dir = HOME / "Library" / "LaunchAgents"
        plist_dir.mkdir(parents=True, exist_ok=True)
        plist_file = plist_dir / f"com.{APP_NAME}.monitor.plist"

        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.{APP_NAME}.monitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>{Path(__file__).resolve()}</string>
        <string>_run_monitor</string>
        <string>{json.dumps(config["watch_dirs"])}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{LOG_FILE}</string>
    <key>StandardErrorPath</key>
    <string>{LOG_FILE}</string>
</dict>
</plist>
"""
        plist_file.write_text(plist_content)
        subprocess.run(["launchctl", "load", str(plist_file)], capture_output=True)
        print(f"Installed launchd service: {plist_file}")
        print(f"Start with: launchctl start com.{APP_NAME}.monitor")

    elif PLATFORM == "Windows":
        # Create a scheduled task that runs at login
        task_name = "PolyglotShield Monitor"
        python_path = sys.executable.replace("python.exe", "pythonw.exe")
        if not Path(python_path).exists():
            python_path = sys.executable

        cmd = (
            f'schtasks /create /tn "{task_name}" '
            f'/tr "{python_path} {Path(__file__).resolve()} _run_monitor \\"{json.dumps(config["watch_dirs"])}\\"" '
            f'/sc onlogon /rl highest /f'
        )
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Installed Windows scheduled task: {task_name}")
        else:
            print(f"Error: {result.stderr}")
            print("Try running as Administrator")


def uninstall_service():
    """Remove system service."""
    if PLATFORM == "Linux":
        subprocess.run(["systemctl", "--user", "stop", APP_NAME], capture_output=True)
        subprocess.run(["systemctl", "--user", "disable", APP_NAME], capture_output=True)
        service_file = HOME / ".config" / "systemd" / "user" / f"{APP_NAME}.service"
        service_file.unlink(missing_ok=True)
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        print("Removed systemd service")

    elif PLATFORM == "Darwin":
        plist_file = HOME / "Library" / "LaunchAgents" / f"com.{APP_NAME}.monitor.plist"
        if plist_file.exists():
            subprocess.run(["launchctl", "unload", str(plist_file)], capture_output=True)
            plist_file.unlink()
            print("Removed launchd service")

    elif PLATFORM == "Windows":
        task_name = "PolyglotShield Monitor"
        result = subprocess.run(
            f'schtasks /delete /tn "{task_name}" /f',
            shell=True, capture_output=True, text=True
        )
        if result.returncode == 0:
            print("Removed Windows scheduled task")
        else:
            print(f"Error: {result.stderr}")


def _run_monitor(watch_dirs_json):
    """Internal: Run the actual monitoring loop."""
    import hashlib

    watch_dirs = json.loads(watch_dirs_json)
    config = get_config()
    extensions = set(config.get("extensions", []))

    # Import the detector
    sys.path.insert(0, str(Path(__file__).parent))
    from polyglot_tui import PolyglotDetector

    detector = PolyglotDetector()
    file_hashes = {}
    logger.info(f"Monitor started, watching: {watch_dirs}")

    try:
        while True:
            for watch_dir in watch_dirs:
                watch_path = Path(watch_dir)
                if not watch_path.exists():
                    continue

                for root, dirs, files in os.walk(watch_path):
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    for fname in files:
                        ext = Path(fname).suffix.lower()
                        if ext not in extensions:
                            continue

                        fpath = Path(root) / fname
                        try:
                            mtime = fpath.stat().st_mtime
                            key = str(fpath)

                            if key in file_hashes and file_hashes[key] == mtime:
                                continue

                            file_hashes[key] = mtime

                            # Scan the file
                            findings = detector.scan_file(str(fpath))
                            crit = [f for f in findings
                                    if f['severity'] in ('critical', 'high')]

                            if crit:
                                msg = f"THREAT in {fname}: {len(crit)} critical findings"
                                logger.warning(msg)
                                for f in crit:
                                    logger.warning(f"  [{f['severity']}] {f['type']}: {f['detail']}")

                                # Desktop notification
                                if config.get("notify", True):
                                    _notify("PolyglotShield Alert", msg)

                                # Auto-quarantine if enabled
                                if config.get("auto_quarantine", False):
                                    _quarantine_file(fpath)

                        except (PermissionError, OSError):
                            pass

            time.sleep(config.get("scan_interval", 5))

    except KeyboardInterrupt:
        logger.info("Monitor stopped by user")
    except Exception as e:
        logger.error(f"Monitor error: {e}")
    finally:
        PID_FILE.unlink(missing_ok=True)


def _notify(title, message):
    """Send desktop notification."""
    try:
        if PLATFORM == "Linux":
            subprocess.run(["notify-send", title, message], capture_output=True)
        elif PLATFORM == "Darwin":
            subprocess.run([
                "osascript", "-e",
                f'display notification "{message}" with title "{title}"'
            ], capture_output=True)
        elif PLATFORM == "Windows":
            # Use PowerShell toast notification
            ps_script = f'''
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$textNodes = $template.GetElementsByTagName("text")
$textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) | Out-Null
$textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::new($template)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("PolyglotShield").Show($toast)
'''
            subprocess.run(["powershell", "-Command", ps_script], capture_output=True)
    except Exception:
        pass


def _quarantine_file(fpath):
    """Move a detected file to quarantine."""
    try:
        quarantine_dir = HOME / ".polyglot" / "quarantine"
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        import hashlib

        # Hash-based filename to avoid collisions
        h = hashlib.sha256(fpath.read_bytes()).hexdigest()[:12]
        dest = quarantine_dir / f"{h}_{fpath.name}"
        shutil.move(str(fpath), str(dest))
        logger.info(f"Quarantined: {fpath} -> {dest}")
    except Exception as e:
        logger.error(f"Quarantine failed: {e}")


def main():
    """CLI entry point for the daemon."""
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <command> [args]")
        print("Commands:")
        print("  start [--dir path]    Start monitoring")
        print("  stop                  Stop monitoring")
        print("  status                Show status")
        print("  install               Install as system service")
        print("  uninstall             Remove system service")
        print("  config                Show current config")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "start":
        watch_dirs = None
        if "--dir" in sys.argv:
            idx = sys.argv.index("--dir")
            watch_dirs = sys.argv[idx + 1:]
        start_daemon(watch_dirs)

    elif cmd == "stop":
        stop_daemon()

    elif cmd == "status":
        show_status()

    elif cmd == "install":
        install_service()

    elif cmd == "uninstall":
        uninstall_service()

    elif cmd == "config":
        config = get_config()
        print(json.dumps(config, indent=2))

    elif cmd == "_run_monitor":
        # Internal: called by the daemon itself
        if len(sys.argv) < 3:
            print("Error: _run_monitor requires watch_dirs_json")
            sys.exit(1)
        _run_monitor(sys.argv[2])

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
