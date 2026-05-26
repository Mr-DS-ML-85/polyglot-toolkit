"""
Push notification system — desktop notifications + sound alerts.
Cross-platform: Linux (notify-send), Windows (PowerShell), macOS (osascript).
"""

import os, sys, subprocess, logging, threading
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger("polyglot_shield.notify")


@dataclass
class Alert:
    title: str
    message: str
    severity: str  # critical / high / medium / low / info
    filepath: str = ""
    risk_score: float = 0.0


def _notify_linux(title: str, body: str, urgency: str = "critical",
                  timeout: int = 8000) -> bool:
    try:
        cmd = ["notify-send", f"--urgency={urgency}",
               f"--expire-time={str(timeout)}", title, body]
        subprocess.run(cmd, capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def _notify_windows(title: str, body: str) -> bool:
    try:
        ps = (
            f'[Windows.UI.Notifications.ToastNotificationManager, '
            f'Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;'
            f'$template = [Windows.UI.Notifications.ToastNotificationManager]::'
            f'GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);'
            f'$text = $template.GetElementsByTagName("text");'
            f'$text[0].AppendChild($template.CreateTextNode("{title}"));'
            f'$text[1].AppendChild($template.CreateTextNode("{body}"));'
            f'$toast = [Windows.UI.Notifications.ToastNotification]::new($template);'
            f'[Windows.UI.Notifications.ToastNotificationManager]::'
            f'CreateToastNotifier("PolyglotShield").Show($toast);'
        )
        subprocess.run(["powershell", "-Command", ps],
                        capture_output=True, timeout=10)
        return True
    except Exception:
        return False


def _notify_macos(title: str, body: str) -> bool:
    try:
        script = f'display notification "{body}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def _play_beep(pattern: str = "critical"):
    """Play an audible alert."""
    try:
        if sys.platform == "linux":
            if pattern == "critical":
                for _ in range(3):
                    subprocess.run(["pactl", "upload-sample",
                                    "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"],
                                   capture_output=True, timeout=2)
            subprocess.run(["paplay",
                            "/usr/share/sounds/freedesktop/stereo/dialog-warning.oga"],
                           capture_output=True, timeout=3)
        elif sys.platform == "win32":
            import winsound
            freq = 1000 if pattern == "critical" else 800
            dur = 500 if pattern == "critical" else 300
            for _ in range(3 if pattern == "critical" else 1):
                winsound.Beep(freq, dur)
    except Exception:
        pass


class NotificationManager:
    """Manages desktop push notifications and sound alerts."""

    def __init__(self, enabled: bool = True, sound: bool = True,
                 critical_only: bool = False, popup_duration_sec: int = 8):
        self.enabled = enabled
        self.sound = sound
        self.critical_only = critical_only
        self.popup_duration = popup_duration_sec * 1000  # ms
        self._callback = None  # GUI callback
        self._history: list = []
        self._max_history = 500

    def set_gui_callback(self, callback):
        """Set callback for in-GUI notifications: callback(alert: Alert)"""
        self._callback = callback

    def send(self, alert: Alert):
        """Send notification (thread-safe, non-blocking)."""
        self._history.append(alert)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        if not self.enabled:
            return
        if self.critical_only and alert.severity not in ("critical", "high"):
            return

        # GUI callback (always, even if desktop notify disabled)
        if self._callback:
            try:
                self._callback(alert)
            except Exception:
                pass

        # Desktop notification (non-blocking)
        threading.Thread(target=self._send_desktop, args=(alert,),
                         daemon=True).start()

        # Sound alert
        if self.sound and alert.severity in ("critical", "high"):
            threading.Thread(target=_play_beep, args=(alert.severity,),
                             daemon=True).start()

    def _send_desktop(self, alert: Alert):
        title = f"🛡️ PolyglotShield — {alert.severity.upper()}"
        body = alert.message
        if alert.filepath:
            body += f"\n📁 {os.path.basename(alert.filepath)}"
        if alert.risk_score > 0:
            body += f"\n⚠️ Risk: {alert.risk_score:.0f}/100"

        urgency = "critical" if alert.severity in ("critical", "high") else "normal"

        if sys.platform == "linux":
            _notify_linux(title, body, urgency, self.popup_duration)
        elif sys.platform == "win32":
            _notify_windows(title, body)
        elif sys.platform == "darwin":
            _notify_macos(title, body)

    def get_history(self, limit: int = 50) -> list:
        return list(reversed(self._history[-limit:]))

    def clear_history(self):
        self._history.clear()
