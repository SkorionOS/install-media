"""Keyboard-driven WiFi for Textual TUI — same intent as GUI NetworkManager page.

Call chain for 「连接」:
  NetworkScreen → WifiService.connect(ssid, password)
    → NetworkManager.connect_to_wifi (Live / NM available)
    → or nmcli (fallback)
    → or sim success (INSTALLER_SIMULATION / INSTALLER_SIM_WIFI)

No touch / mouse required; OptionList + password Screen are fully keyboardable.
"""

from __future__ import annotations

import os
import subprocess
import threading
from dataclasses import dataclass
from typing import Callable, List, Optional


ConnectCallback = Callable[[bool, Optional[str], str], None]
DisconnectCallback = Callable[[bool, str], None]


@dataclass
class WifiNetwork:
    ssid: str
    strength: int
    secured: bool
    connected: bool
    band: str = "?"
    # Opaque NM AccessPoint when using GI NetworkManager
    ap: object = None


def _sim_mode() -> bool:
    return os.environ.get("INSTALLER_SIMULATION", "") in ("1", "true", "yes") or os.environ.get(
        "INSTALLER_SIM_WIFI", ""
    ) in ("1", "true", "yes")


class WifiService:
    """Scan / connect / disconnect with NM → nmcli → sim fallbacks."""

    def __init__(self) -> None:
        self._nm = None
        if not _sim_mode():
            try:
                from installer.network.manager import NetworkManager

                self._nm = NetworkManager()
                if not self._nm.is_available():
                    self._nm = None
            except Exception:
                self._nm = None

    def is_online(self) -> bool:
        if self._nm is not None:
            try:
                return bool(self._nm.is_online())
            except Exception:
                pass
        if _sim_mode():
            return os.environ.get("INSTALLER_SIM_ONLINE", "1") in ("1", "true", "yes")
        try:
            r = subprocess.run(
                ["ping", "-c", "1", "-W", "1", "1.1.1.1"],
                capture_output=True,
                check=False,
            )
            return r.returncode == 0
        except Exception:
            return False

    def connected_ssid(self) -> Optional[str]:
        if self._nm is not None:
            try:
                return self._nm.get_connected_wifi_ssid()
            except Exception:
                pass
        if _sim_mode():
            return os.environ.get("INSTALLER_SIM_WIFI_SSID") or None
        try:
            r = subprocess.run(
                ["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if r.returncode != 0:
                return None
            for ln in r.stdout.splitlines():
                parts = ln.split(":")
                if len(parts) >= 2 and parts[0] == "yes":
                    return parts[1] or None
        except Exception:
            pass
        return None

    def scan(self) -> List[WifiNetwork]:
        if self._nm is not None:
            try:
                out: List[WifiNetwork] = []
                for ap, ssid in self._nm.scan_networks():
                    strength = int(ap.get_strength())
                    freq = int(ap.get_frequency())
                    out.append(
                        WifiNetwork(
                            ssid=ssid,
                            strength=strength,
                            secured=bool(self._nm.is_secured(ap)),
                            connected=bool(self._nm.is_wifi_connected(ssid)),
                            band="5G" if freq > 5000 else "2.4G",
                            ap=ap,
                        )
                    )
                for _dev in self._nm.get_ethernet_devices():
                    out.insert(
                        0,
                        WifiNetwork(
                            ssid="有线网络（已连接）",
                            strength=100,
                            secured=False,
                            connected=True,
                            band="ETH",
                            ap=None,
                        ),
                    )
                if out:
                    return out
            except Exception:
                pass

        if _sim_mode():
            cur = os.environ.get("INSTALLER_SIM_WIFI_SSID", "")
            return [
                WifiNetwork("Skorion-Guest", 88, False, cur == "Skorion-Guest", "2.4G"),
                WifiNetwork("Skorion-Lab", 72, True, cur == "Skorion-Lab", "5G"),
                WifiNetwork("Office-WiFi", 55, True, cur == "Office-WiFi", "5G"),
            ]

        # nmcli fallback
        try:
            r = subprocess.run(
                [
                    "nmcli",
                    "-t",
                    "-f",
                    "ACTIVE,SSID,SIGNAL,SECURITY,FREQ",
                    "dev",
                    "wifi",
                    "list",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
            if r.returncode != 0:
                return []
            seen = set()
            out = []
            for ln in r.stdout.splitlines():
                parts = ln.split(":")
                if len(parts) < 4:
                    continue
                active, ssid, signal, security = parts[0], parts[1], parts[2], parts[3]
                freq = parts[4] if len(parts) > 4 else "0"
                if not ssid or ssid in seen:
                    continue
                seen.add(ssid)
                try:
                    strength = int(signal)
                except Exception:
                    strength = 0
                try:
                    fnum = int("".join(c for c in freq if c.isdigit()) or "0")
                except Exception:
                    fnum = 0
                out.append(
                    WifiNetwork(
                        ssid=ssid,
                        strength=strength,
                        secured=bool(security and security not in ("", "--")),
                        connected=active == "yes",
                        band="5G" if fnum > 5000 else "2.4G",
                    )
                )
            out.sort(key=lambda n: n.strength, reverse=True)
            return out
        except Exception:
            return []

    def connect(self, net: WifiNetwork, password: str, callback: ConnectCallback) -> None:
        if net.band == "ETH" or net.ssid.startswith("有线"):
            callback(False, "有线网络无需手动连接", net.ssid)
            return

        if self._nm is not None and net.ap is not None:
            def _cb(ok: bool, err: Optional[str], ssid: str) -> None:
                callback(ok, err, ssid)

            try:
                self._nm.connect_to_wifi(net.ap, net.ssid, password or "", _cb)
                return
            except Exception as exc:
                callback(False, str(exc), net.ssid)
                return

        if _sim_mode():

            def _sim() -> None:
                import time

                time.sleep(0.15)
                os.environ["INSTALLER_SIM_ONLINE"] = "1"
                os.environ["INSTALLER_SIM_WIFI_SSID"] = net.ssid
                if net.secured and password == "bad":
                    callback(False, "密码错误", net.ssid)
                else:
                    callback(True, None, net.ssid)

            threading.Thread(target=_sim, daemon=True).start()
            return

        def _nmcli() -> None:
            cmd = ["nmcli", "dev", "wifi", "connect", net.ssid]
            if net.secured and password:
                cmd.extend(["password", password])
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)
                if r.returncode == 0:
                    callback(True, None, net.ssid)
                else:
                    err = (r.stderr or r.stdout or "连接失败").strip()
                    callback(False, err, net.ssid)
            except Exception as exc:
                callback(False, str(exc), net.ssid)

        threading.Thread(target=_nmcli, daemon=True).start()

    def disconnect(self, ssid: str, callback: DisconnectCallback) -> None:
        if self._nm is not None:
            try:
                self._nm.disconnect_wifi(ssid, callback)
                return
            except Exception:
                pass
        if _sim_mode():
            os.environ.pop("INSTALLER_SIM_WIFI_SSID", None)
            os.environ["INSTALLER_SIM_ONLINE"] = "0"
            callback(True, ssid)
            return

        def _nmcli() -> None:
            try:
                r = subprocess.run(
                    ["nmcli", "connection", "down", "id", ssid],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                )
                callback(r.returncode == 0, ssid)
            except Exception:
                callback(False, ssid)

        threading.Thread(target=_nmcli, daemon=True).start()
