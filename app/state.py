import time
from typing import Any, Dict, Optional

from config import load_config, save_config
from network import (
    NetworkError,
    connect_wifi,
    get_active_connection,
    is_connected,
    start_hotspot,
    stop_hotspot,
)


STATE_BOOT = "BOOT"
STATE_AP_MODE = "AP_MODE"
STATE_CONNECTING_WIFI = "CONNECTING_WIFI"
STATE_ONLINE_READY = "ONLINE_READY"
STATE_OFFLINE_RECOVERING = "OFFLINE_RECOVERING"
STATE_RECOVERY_AP_MODE = "RECOVERY_AP_MODE"
STATE_ERROR = "ERROR"


def _now() -> int:
    return int(time.time())


def _ensure_sections(cfg: Dict[str, Any]) -> Dict[str, Any]:
    if "network" not in cfg or not isinstance(cfg["network"], dict):
        cfg["network"] = {}

    if "state_machine" not in cfg or not isinstance(cfg["state_machine"], dict):
        cfg["state_machine"] = {}

    sm = cfg["state_machine"]

    sm.setdefault("current_state", STATE_BOOT)
    sm.setdefault("last_error", "")
    sm.setdefault("hotspot_active", False)
    sm.setdefault("recovery_attempts", 0)
    sm.setdefault("max_recovery_attempts", 5)
    sm.setdefault("last_state_change", 0)
    sm.setdefault("last_connected_at", 0)

    return cfg


def _load_cfg() -> Dict[str, Any]:
    return _ensure_sections(load_config())


def _save_cfg(cfg: Dict[str, Any]) -> None:
    save_config(_ensure_sections(cfg))


def _network_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return cfg["network"]


def _sm(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return cfg["state_machine"]


def get_saved_ssid(cfg: Optional[Dict[str, Any]] = None) -> Optional[str]:
    if cfg is None:
        cfg = _load_cfg()
    return _network_cfg(cfg).get("last_wifi_ssid") or None


def get_saved_password(cfg: Optional[Dict[str, Any]] = None) -> Optional[str]:
    if cfg is None:
        cfg = _load_cfg()
    return _network_cfg(cfg).get("wifi_password") or None


def has_saved_wifi(cfg: Optional[Dict[str, Any]] = None) -> bool:
    if cfg is None:
        cfg = _load_cfg()
    return bool(get_saved_ssid(cfg) and get_saved_password(cfg))


def get_current_state(cfg: Optional[Dict[str, Any]] = None) -> str:
    if cfg is None:
        cfg = _load_cfg()
    return _sm(cfg).get("current_state", STATE_BOOT)


def set_state(
    new_state: str,
    *,
    error: str = "",
    cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if cfg is None:
        cfg = _load_cfg()

    sm = _sm(cfg)
    sm["current_state"] = new_state
    sm["last_error"] = error
    sm["last_state_change"] = _now()

    if new_state == STATE_ONLINE_READY:
        sm["last_connected_at"] = sm["last_state_change"]
        sm["recovery_attempts"] = 0
        cfg["setup_complete"] = True

    _save_cfg(cfg)
    return cfg


def get_status() -> Dict[str, Any]:
    cfg = _load_cfg()
    sm = _sm(cfg)
    active = get_active_connection()

    return {
        "state": sm.get("current_state", STATE_BOOT),
        "last_error": sm.get("last_error", ""),
        "hotspot_active": bool(sm.get("hotspot_active", False)),
        "recovery_attempts": int(sm.get("recovery_attempts", 0)),
        "max_recovery_attempts": int(sm.get("max_recovery_attempts", 5)),
        "setup_complete": bool(cfg.get("setup_complete")),
        "saved_ssid": get_saved_ssid(cfg) or "",
        "is_connected": is_connected(),
        "active_connection": active,
    }


def page_for_state(state: str) -> str:
    if state == STATE_ONLINE_READY:
        return "index"
    return "setup_network"


def reconcile_state() -> Dict[str, Any]:
    """
    Cheap state reconciliation.
    Safe to call from request handlers.
    """

    cfg = _load_cfg()
    sm = _sm(cfg)

    connected = is_connected()
    managed = is_managed_config_complete(cfg)
    current = sm.get("current_state", STATE_BOOT)

    # Rule 1:
    # If Shmoobox does not have a valid managed config, the device is not provisioned.
    # Even if it happens to be connected right now, we should still go to setup.
    if not managed:
        if current != STATE_AP_MODE:
            cfg = set_state(STATE_AP_MODE, cfg=cfg)
            sm = _sm(cfg)

        if not sm.get("hotspot_active"):
            try:
                start_hotspot()
                sm["hotspot_active"] = True
                _save_cfg(cfg)
            except Exception as exc:
                cfg = set_state(
                    STATE_ERROR,
                    error=f"Failed to start hotspot: {exc}",
                    cfg=cfg,
                )

        return cfg

    # Rule 2:
    # Managed config exists and network is up -> ready.
    if connected:
        if current != STATE_ONLINE_READY:
            cfg = set_state(STATE_ONLINE_READY, cfg=cfg)
            sm = _sm(cfg)

        if sm.get("hotspot_active"):
            try:
                stop_hotspot()
            except Exception:
                pass
            sm["hotspot_active"] = False
            _save_cfg(cfg)

        return cfg

    # Rule 3:
    # Managed config exists but network is down -> recovery.
    if current not in {
        STATE_CONNECTING_WIFI,
        STATE_OFFLINE_RECOVERING,
        STATE_RECOVERY_AP_MODE,
    }:
        cfg = set_state(STATE_OFFLINE_RECOVERING, cfg=cfg)

    return cfg


def submit_wifi_credentials(appliance_name: str, ssid: str, password: str) -> Dict[str, Any]:
    """
    Save user-supplied provisioning values, then attempt client connection.
    """
    cfg = _load_cfg()

    if appliance_name:
        cfg["appliance_name"] = appliance_name.strip()

    cfg["network"]["last_wifi_ssid"] = ssid.strip() or None
    cfg["network"]["wifi_password"] = password

    _save_cfg(cfg)
    return attempt_wifi_connection()


def attempt_wifi_connection() -> Dict[str, Any]:
    cfg = _load_cfg()
    sm = _sm(cfg)

    ssid = get_saved_ssid(cfg)
    password = get_saved_password(cfg)

    if not ssid or not password:
        return set_state(STATE_AP_MODE, error="SSID and password are required.", cfg=cfg)

    if sm.get("hotspot_active"):
        try:
            stop_hotspot()
        except Exception:
            pass
        sm["hotspot_active"] = False
        _save_cfg(cfg)

    cfg = set_state(STATE_CONNECTING_WIFI, cfg=cfg)
    sm = _sm(cfg)

    try:
        connect_wifi(ssid, password)

        if is_connected():
            return set_state(STATE_ONLINE_READY, cfg=cfg)

        # Defensive fallback: if connect_wifi succeeded but connectivity test says no
        raise NetworkError("Wi-Fi connect command completed, but no active client connection was detected.")

    except Exception as exc:
        had_been_online_before = bool(sm.get("last_connected_at"))
        sm["recovery_attempts"] = int(sm.get("recovery_attempts", 0)) + 1
        _save_cfg(cfg)

        max_attempts = int(sm.get("max_recovery_attempts", 5))
        error = f"Unable to connect to Wi-Fi network {ssid!r}: {exc}"

        if not had_been_online_before:
            try:
                start_hotspot()
                sm["hotspot_active"] = True
                _save_cfg(cfg)
            except Exception as ap_exc:
                error = f"{error} Also failed to restart hotspot: {ap_exc}"
                return set_state(STATE_ERROR, error=error, cfg=cfg)

            return set_state(STATE_AP_MODE, error=error, cfg=cfg)

        if sm["recovery_attempts"] >= max_attempts:
            try:
                start_hotspot()
                sm["hotspot_active"] = True
                _save_cfg(cfg)
            except Exception as ap_exc:
                error = f"{error} Also failed to restart hotspot: {ap_exc}"
                return set_state(STATE_ERROR, error=error, cfg=cfg)

            return set_state(STATE_RECOVERY_AP_MODE, error=error, cfg=cfg)

        return set_state(STATE_OFFLINE_RECOVERING, error=error, cfg=cfg)


def handle_network_loss() -> Dict[str, Any]:
    """
    Entry point for later callback/event use.
    For now, app.py can call this when it notices the device is no longer connected.
    """
    cfg = _load_cfg()

    if is_connected():
        return set_state(STATE_ONLINE_READY, cfg=cfg)

    if not has_saved_wifi(cfg):
        try:
            start_hotspot()
            _sm(cfg)["hotspot_active"] = True
            _save_cfg(cfg)
        except Exception as exc:
            return set_state(STATE_ERROR, error=f"Failed to start hotspot: {exc}", cfg=cfg)

        return set_state(
            STATE_AP_MODE,
            error="Network lost and no saved Wi-Fi configuration exists.",
            cfg=cfg,
        )

    cfg = set_state(STATE_OFFLINE_RECOVERING, cfg=cfg)
    return attempt_wifi_connection()

def is_managed_config_complete(cfg: Optional[Dict[str, Any]] = None) -> bool:
    if cfg is None:
        cfg = _load_cfg()

    network = _network_cfg(cfg)
    ssid = network.get("last_wifi_ssid")
    password = network.get("wifi_password")

    return bool(ssid and password)
