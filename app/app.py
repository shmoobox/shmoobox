from flask import Flask, redirect, request, url_for
import shutil
import socket
import subprocess

from network import list_wifi_networks
from state import (
    STATE_OFFLINE_RECOVERING,
    STATE_ONLINE_READY,
    attempt_wifi_connection,
    get_status,
    handle_network_loss,
    page_for_state,
    reconcile_state,
    submit_wifi_credentials,
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
    reconcile_state()
    status = get_status()

    if status["state"] != STATE_ONLINE_READY:
        return redirect(url_for(page_for_state(status["state"])))

    hostname = socket.gethostname()
    ips = get_ip_addresses()
    uptime = get_uptime()
    total, used, free = shutil.disk_usage("/")
    active = status["active_connection"]
    active_name = active["name"] if active else "unknown"
    active_type = active["type"] if active else "unknown"
    setup = "complete" if status["setup_complete"] else "incomplete"

    html = f"""
<h1>Shmoobox</h1>

<p>Status: alive</p>
<p>State: {status["state"]}</p>
<p>Hostname: {hostname}</p>
<p>IP address(es): {ips}</p>
<p>Uptime: {uptime}</p>
<p>Disk free: {free // (1024**3)} GB</p>
<p>Setup: {setup}</p>
<p>Active connection: {active_name} ({active_type})</p>

<p><a href="/setup/network">Network setup</a></p>
<p><a href="/network/recover">Force recovery attempt</a></p>
"""
    return html


@app.route("/setup/network", methods=["GET", "POST"])
def setup_network():
    reconcile_state()
    status = get_status()

    message = ""
    error = status["last_error"]

    if request.method == "POST":
        appliance_name = request.form.get("appliance_name", "").strip()
        ssid = request.form.get("ssid", "").strip()
        password = request.form.get("password", "").strip()
        hidden = request.form.get("hidden") == "on"
    
        if not ssid or not password:
            error = "SSID and password are required."
        else:
            submit_wifi_credentials(appliance_name, ssid, password, hidden=hidden)            
    status = get_status()

    if status["state"] == STATE_ONLINE_READY:
        return redirect(url_for("index"))

    error = status["last_error"]

    status = get_status()
    networks = list_wifi_networks()
    network_items = "".join(
        f"<li>{n['ssid']} (signal: {n['signal']}, security: {n['security']})</li>"
        for n in networks
    )
    if not network_items:
        network_items = "<li>No Wi-Fi networks found.</li>"

    appliance_name = "shmoobox"
    saved_ssid = status.get("saved_ssid", "") or ""

    html = f"""
<h1>Shmoobox Network Setup</h1>

<p>Current state: {status["state"]}</p>
<p>Connected: {"yes" if status["is_connected"] else "no"}</p>
<p>Hotspot active: {"yes" if status["hotspot_active"] else "no"}</p>

{"<p><strong>" + message + "</strong></p>" if message else ""}
{"<p style='color:red;'><strong>" + error + "</strong></p>" if error else ""}

<p>Shmoobox is not currently ready for normal operation.</p>

<form method="post">
  <p>
    <label>Appliance name:<br>
      <input type="text" name="appliance_name" value="{appliance_name}">
    </label>
  </p>

  <p>
    <label>Wi-Fi SSID:<br>
      <input type="text" name="ssid" value="{saved_ssid}">
    </label>
  </p>

  <p>
    <label>Wi-Fi password:<br>
      <input type="password" name="password" value="">
    </label>
  </p>
  <p>
    <label>Hidden network:
      <input type="checkbox" name="hidden">
    </label>
  </p>
  <p><button type="submit">Connect</button></p>
</form>

<h2>Visible Wi-Fi Networks</h2>
<ul>
  {network_items}
</ul>

<p><a href="/">Back to status</a></p>
<p><a href="/network/recover">Retry saved Wi-Fi now</a></p>
"""
    return html


@app.route("/network/recover")
def network_recover():
    handle_network_loss()
    status = get_status()

    if status["state"] == STATE_ONLINE_READY:
        return redirect(url_for("index"))

    return redirect(url_for("setup_network"))


@app.route("/network/retry")
def network_retry():
    attempt_wifi_connection()
    status = get_status()

    if status["state"] == STATE_ONLINE_READY:
        return redirect(url_for("index"))

    return redirect(url_for("setup_network"))


if __name__ == "__main__":
    reconcile_state()
    app.run(host="0.0.0.0", port=8080)
