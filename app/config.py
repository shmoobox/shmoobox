import json
import os
import shutil
import tempfile
from typing import Any, Dict

CONFIG_DIR = "/etc/shmoobox"
CONFIG_FILE = f"{CONFIG_DIR}/config.json"
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
EXAMPLE_CONFIG_PATH = "/opt/shmoobox/config/config.example.json"


def ensure_config_exists():
    os.makedirs(CONFIG_DIR, exist_ok=True)

    if not os.path.exists(CONFIG_FILE):
        cfg = default_config()
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)


def load_config() -> dict:
    ensure_config_exists()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Corrupt or unreadable config → reset
        cfg = default_config()
        save_config(cfg)
        return cfg

def save_config(cfg: Dict[str, Any]) -> None:
    """
    Save config atomically to avoid partial writes.

    Writes to a temp file in the same directory, fsyncs it, then renames it
    into place.
    """
    if not isinstance(cfg, dict):
        raise TypeError("cfg must be a dictionary")

    os.makedirs(CONFIG_DIR, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        prefix="config.",
        suffix=".json.tmp",
        dir=CONFIG_DIR,
        text=True,
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, CONFIG_PATH)

    except Exception:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
        raise

def default_config() -> dict:
    return {
        "setup_complete": False,
        "appliance_name": "shmoobox",
        "network": {
            "last_wifi_ssid": None,
            "wifi_password": None,
        },
        "state_machine": {
            "current_state": "BOOT",
            "last_error": "",
            "hotspot_active": False,
            "recovery_attempts": 0,
            "max_recovery_attempts": 5,
            "last_state_change": 0,
            "last_connected_at": 0,
        },
    }
