import shlex
import subprocess
from typing import Dict, List, Optional


HOTSPOT_CONNECTION_NAME = "shmoobox-ap"
DEFAULT_HOTSPOT_SSID = "shmoobox-setup"
DEFAULT_HOTSPOT_PASSWORD = "12345678"


class NetworkError(Exception):
    pass


def _run_command(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    """
    Run a command and return the completed process.
    Raises NetworkError on failure if check=True.
    """
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )

    if check and result.returncode != 0:
        joined = " ".join(shlex.quote(part) for part in cmd)
        raise NetworkError(
            f"Command failed: {joined}\n"
            f"stdout: {result.stdout.strip()}\n"
            f"stderr: {result.stderr.strip()}"
        )

    return result

def _nmcli(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """
    Convenience wrapper around nmcli using sudo.
    """
    return _run_command(["sudo", "nmcli", *args], check=check)


def _iw(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """
    Convenience wrapper around iw using sudo.
    """
    return _run_command(["sudo", "iw", *args], check=check)

def get_wifi_device() -> Optional[str]:
    """
    Return the first Wi-Fi device managed by NetworkManager, or None if not found.
    """
    result = _nmcli("-t", "-f", "DEVICE,TYPE,STATE", "device", "status", check=False)

    for line in result.stdout.splitlines():
        parts = line.strip().split(":")
        if len(parts) < 3:
            continue

        device, dev_type, _state = parts[0], parts[1], parts[2]
        if dev_type == "wifi":
            return device

    return None

def is_connected() -> bool:
    """
    Return True if wlan0 has an active non-hotspot Wi-Fi connection.
    """
    wifi_device = get_wifi_device()
    if not wifi_device:
        return False

    active = _nmcli(
        "-t",
        "-f",
        "NAME,DEVICE,TYPE",
        "connection",
        "show",
        "--active",
        check=False,
    )

    for line in active.stdout.splitlines():
        parts = line.strip().split(":")
        if len(parts) < 3:
            continue

        name, device, conn_type = parts[0], parts[1], parts[2]

        if device != wifi_device:
            continue

        if conn_type not in {"802-11-wireless", "wifi"}:
            continue

        if name == HOTSPOT_CONNECTION_NAME:
            continue

        return True

    return False


def get_active_connection() -> Optional[Dict[str, str]]:
    """
    Return info about the first active non-loopback connection, or None.
    """
    result = _nmcli(
        "-t",
        "-f",
        "NAME,DEVICE,TYPE",
        "connection",
        "show",
        "--active",
        check=False,
    )

    for line in result.stdout.splitlines():
        parts = line.strip().split(":")
        if len(parts) < 3:
            continue

        name, device, conn_type = parts[0], parts[1], parts[2]
        if conn_type in {"802-11-wireless", "wifi", "ethernet"}:
            return {
                "name": name,
                "device": device,
                "type": conn_type,
            }

    return None


def start_hotspot(
    ssid: str = DEFAULT_HOTSPOT_SSID,
    password: str = DEFAULT_HOTSPOT_PASSWORD,
    connection_name: str = HOTSPOT_CONNECTION_NAME,
) -> bool:
    """
    Start a Wi-Fi hotspot using a clean NetworkManager AP profile.
    """
    wifi_device = get_wifi_device()
    if not wifi_device:
        raise NetworkError("No Wi-Fi device found for hotspot mode.")

    if len(password) < 8:
        raise ValueError("Hotspot password must be at least 8 characters.")

    # Clean out stale state.
    _nmcli("device", "disconnect", wifi_device, check=False)
    _nmcli("radio", "wifi", "off", check=False)
    _nmcli("radio", "wifi", "on", check=False)
    _iw("dev", wifi_device, "set", "power_save", "off", check=False)

    # Remove any old hotspot profile.
    _nmcli("connection", "down", connection_name, check=False)
    _nmcli("connection", "delete", connection_name, check=False)

    # Create fresh AP profile.
    _nmcli(
        "connection",
        "add",
        "type",
        "wifi",
        "ifname",
        wifi_device,
        "con-name",
        connection_name,
        "ssid",
        ssid,
    )

    _nmcli(
        "connection",
        "modify",
        connection_name,
        "802-11-wireless.mode",
        "ap",
        "802-11-wireless.band",
        "bg",
        "802-11-wireless.channel",
        "1",
        "ipv4.method",
        "shared",
        "wifi-sec.key-mgmt",
        "wpa-psk",
        "wifi-sec.psk",
        password,
    )

    result = _nmcli("connection", "up", connection_name, check=False)
    return result.returncode == 0

def stop_hotspot(connection_name: str = HOTSPOT_CONNECTION_NAME) -> bool:
    """
    Stop and remove the Shmoobox hotspot profile.
    """
    _nmcli("connection", "down", connection_name, check=False)
    _nmcli("connection", "delete", connection_name, check=False)
    return True

def connect_wifi(
    ssid: str,
    password: str,
    connection_name: Optional[str] = None,
) -> bool:
    """
    Connect to a Wi-Fi network using NetworkManager.
    """
    if not ssid:
        raise ValueError("ssid must not be empty")

    wifi_device = get_wifi_device()
    if not wifi_device:
        raise NetworkError("No Wi-Fi device found for client connection.")

    if connection_name is None:
        connection_name = ssid

    # Shut down provisioning AP first.
    stop_hotspot()

    # Remove stale client profile with same name.
    _nmcli("connection", "delete", connection_name, check=False)

    result = _nmcli(
        "device",
        "wifi",
        "connect",
        ssid,
        "password",
        password,
        "ifname",
        wifi_device,
        "name",
        connection_name,
        check=False,
    )

    if result.returncode != 0:
        raise NetworkError(
            f"Failed to connect to Wi-Fi SSID {ssid!r}: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )

    return True

def list_wifi_networks() -> List[Dict[str, str]]:
    """
    Return a simple list of visible Wi-Fi networks.
    """
    wifi_device = get_wifi_device()
    if not wifi_device:
        return []

    _nmcli("device", "wifi", "rescan", "ifname", wifi_device, check=False)

    result = _nmcli(
        "-t",
        "-f",
        "SSID,SIGNAL,SECURITY",
        "device",
        "wifi",
        "list",
        "ifname",
        wifi_device,
        check=False,
    )

    networks: List[Dict[str, str]] = []
    seen = set()

    for line in result.stdout.splitlines():
        parts = line.strip().split(":")
        if len(parts) < 3:
            continue

        ssid, signal, security = parts[0], parts[1], parts[2]
        if not ssid or ssid in seen:
            continue

        seen.add(ssid)
        networks.append(
            {
                "ssid": ssid,
                "signal": signal,
                "security": security,
            }
        )

    return networks
