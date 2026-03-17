from flask import Flask, redirect, request, url_for
import shutil
import socket
import subprocess

from config import load_config, save_config
from network import (
    connect_wifi,
    get_active_connection,
    is_connected,
    list_wifi_networks,
    start_hotspot,
)

app = Flask(__name__)


def get_ip_addresses() -> str:
    try:
        output = subprocess.check_output(["hostname", "-I"], text=True).strip()
        return output if output else "unknown"
    except Exception:
        return "unknown"


def get_uptime() -> str:
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as f:
            seconds = int(float(f.read().split()[0]))
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)

        if days:
            return f"{days}d {hours}h {minutes}m"
        return f"{hours}h {minutes}m"
    except Exception:
        return "unknown"


@app.route("/")
def index():
    cfg = load_config()

    if not is_connected():
        return redirect(url_for("setup_network"))

    hostname = socket.gethostname()
    ips = get_ip_addresses()
    uptime = get_uptime()
    total, used, free = shutil.disk_usage("/")

    active = get_active_connection()
    active_name = active["name"] if active else "unknown"
    active_type = active["type"] if active else "unknown"

    setup = "complete" if cfg.get("setup_complete") else "incomplete"

    html = f"""
    <html>
    <head>
      <title>Shmoobox</title>
    </head>
    <body>
      <h1>Shmoobox</h1>
      <p><strong>Status:</strong> alive</p>
      <p><strong>Hostname:</strong> {hostname}</p>
      <p><strong>IP address(es):</strong> {ips}</p>
      <p><strong>Uptime:</strong> {uptime}</p>
      <p><strong>Disk free:</strong> {free // (1024**3)} GB</p>
      <p><strong>Setup:</strong> {setup}</p>
      <p><strong>Active connection:</strong> {active_name} ({active_type})</p>
      <p><a href="/setup/network">Network setup</a></p>
      <p><a href="/complete">Mark setup complete</a></p>
    </body>
    </html>
    """
    return html


@app.route("/setup/network", methods=["GET", "POST"])
def setup_network():
    cfg = load_config()
    message = ""
    error = ""

    if request.method == "POST":
        appliance_name = request.form.get("appliance_name", "").strip()
        ssid = request.form.get("ssid", "").strip()
        password = request.form.get("password", "").strip()

        if appliance_name:
            cfg["appliance_name"] = appliance_name

        if "network" not in cfg or not isinstance(cfg["network"], dict):
            cfg["network"] = {}

        cfg["network"]["last_wifi_ssid"] = ssid or None

        try:
            if ssid and password:
                ok = connect_wifi(ssid, password)
                if ok:
                    cfg["setup_complete"] = True
                    save_config(cfg)
                    return redirect(url_for("index"))
                else:
                    error = "Wi-Fi connection failed. Starting hotspot."
                    start_hotspot()
                    save_config(cfg)
            else:
                error = "SSID and password are required."
                save_config(cfg)
        except Exception as exc:
            error = f"Network error: {exc}"
            try:
                start_hotspot()
            except Exception:
                pass
            save_config(cfg)

    networks = list_wifi_networks()

    network_items = "".join(
        f"<li>{n['ssid']} (signal: {n['signal']}, security: {n['security']})</li>"
        for n in networks
    )

    if not network_items:
        network_items = "<li>No Wi-Fi networks found.</li>"

    appliance_name = cfg.get("appliance_name", "shmoobox")
    last_ssid = cfg.get("network", {}).get("last_wifi_ssid", "") or ""

    html = f"""
    <html>
    <head>
      <title>Shmoobox Network Setup</title>
    </head>
    <body>
      <h1>Shmoobox Network Setup</h1>

      <p>Shmoobox is not currently connected to a network.</p>

      {f'<p style="color: green;"><strong>{message}</strong></p>' if message else ''}
      {f'<p style="color: red;"><strong>{error}</strong></p>' if error else ''}

      <form method="post">
        <p>
          <label for="appliance_name">Appliance name:</label><br>
          <input type="text" id="appliance_name" name="appliance_name" value="{appliance_name}">
        </p>

        <p>
          <label for="ssid">Wi-Fi SSID:</label><br>
          <input type="text" id="ssid" name="ssid" value="{last_ssid}">
        </p>

        <p>
          <label for="password">Wi-Fi password:</label><br>
          <input type="password" id="password" name="password">
        </p>

        <p>
          <button type="submit">Connect</button>
        </p>
      </form>

      <h2>Visible Wi-Fi Networks</h2>
      <ul>
        {network_items}
      </ul>

      <p><a href="/">Back to status</a></p>
    </body>
    </html>
    """
    return html


@app.route("/complete")
def complete():
    cfg = load_config()
    cfg["setup_complete"] = True
    save_config(cfg)
    return "Setup marked complete"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
