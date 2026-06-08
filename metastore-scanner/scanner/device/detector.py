"""Cross-platform device fingerprinting for scanner registration."""

from __future__ import annotations

import hashlib
import platform
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from scanner.models.dto import DeviceInfo


def _read_text_safe(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _linux_machine_id() -> str | None:
    for p in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
        text = _read_text_safe(p)
        if text:
            return text
    return None


def _windows_machine_guid() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0),
        )
        try:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            if isinstance(value, str) and value.strip():
                return value.strip()
        finally:
            winreg.CloseKey(key)
    except OSError:
        return None
    return None


def _macos_platform_uuid() -> str | None:
    if sys.platform != "darwin":
        return None
    try:
        import plistlib
        import subprocess
    except ImportError:
        return None
    try:
        out = subprocess.run(
            ["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if out.returncode != 0 or not out.stdout:
            return None
        for line in out.stdout.splitlines():
            line = line.strip()
            if "IOPlatformUUID" in line:
                parts = line.split("=", 1)
                if len(parts) == 2:
                    raw = parts[1].strip().strip('"')
                    return raw or None
        plist_path = Path("/var/root/Library/Preferences/SystemConfiguration/com.apple.platform.plist")
        if plist_path.is_file():
            data = plistlib.loads(plist_path.read_bytes())
            if isinstance(data, dict) and "UUID" in data:
                return str(data["UUID"])
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return None
    return None


def _fallback_uid() -> str:
    node = uuid.getnode()
    hn = platform.node() or "unknown-host"
    plat = platform.platform()
    raw = f"{node}:{hn}:{plat}".encode("utf-8", errors="replace")
    return hashlib.sha256(raw).hexdigest()


@dataclass(slots=True)
class DeviceDetector:
    """Resolves stable machine_uid and platform metadata."""

    def detect(self) -> DeviceInfo:
        machine_uid = (
            _linux_machine_id()
            or _windows_machine_guid()
            or _macos_platform_uuid()
            or _fallback_uid()
        )
        hostname = platform.node() or "unknown"
        os_name = platform.system() or "unknown"
        platform_name = platform.platform()
        return DeviceInfo(
            machine_uid=machine_uid,
            hostname=hostname,
            os_name=os_name,
            platform_name=platform_name,
        )


def detect_device() -> DeviceInfo:
    return DeviceDetector().detect()
