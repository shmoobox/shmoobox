import json
import os
import shutil
import tempfile
from typing import Any, Dict

CONFIG_DIR = "/etc/shmoobox"
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
EXAMPLE_CONFIG_PATH = "/opt/shmoobox/config/config.example.json"


def ensure_config_exists() -> None:
    """
    Ensure the live config file exists.

    If /etc/shmoobox/config.json is missing, seed it from the example config.
    The example config is treated as immutable factory defaults.
    """
    os.makedirs(CONFIG_DIR, exist_ok=True)

    if os.path.exists(CONFIG_PATH):
        return

    if not os.path.exists(EXAMPLE_CONFIG_PATH):
        raise FileNotFoundError(
            f"Example config not found: {EXAMPLE_CONFIG_PATH}"
        )

    shutil.copy2(EXAMPLE_CONFIG_PATH, CONFIG_PATH)


def load_config() -> Dict[str, Any]:
    """
    Load the live config from disk, creating it from the example if needed.
    """
    ensure_config_exists()

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a JSON object: {CONFIG_PATH}")

    return data


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
