from flask import Flask
import os
import socket
import shutil
import subprocess
import json

app = Flask(__name__)

def get_ip_addresses() -> str:
    try:
        output = subprocess.check_output(["hostname", "-I"], text=True).strip()
        return output if output else "unknown"
    except Exception:
        return "unknown"

def get_uptime() -> str:
    try:
        with open("/proc/uptime", "r") as f:
            seconds = int(float(f.read().split()[0]))
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        if days:
            return f"{days}d {hours}h {minutes}m"
        return f"{hours}h {minutes}m"
    except Exception:
        return "unknown"

CONFIG_PATH = "/etc/shmoobox/config.json"

def load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except:
        return {"setup_complete": False}

def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)

@app.route("/")
def index():
    hostname = socket.gethostname()
    ips = get_ip_addresses()
    uptime = get_uptime()
    total, used, free = shutil.disk_usage("/")
    config = load_config()
    setup = "complete" if config["setup_complete"] else "incomplete"


    html = f"""
    <!doctype html>
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Shmoobox</title>
      <style>
        body {{
          font-family: sans-serif;
          margin: 2rem;
          line-height: 1.5;
          max-width: 40rem;
        }}
        .card {{
          border: 1px solid #ccc;
          border-radius: 10px;
          padding: 1rem;
        }}
        h1 {{
          margin-top: 0;
        }}
        .label {{
          font-weight: bold;
        }}
      </style>
    </head>
    <body>
      <div class="card">
        <h1>Shmoobox</h1>
        <p><span class="label">Status:</span> alive</p>
        <p><span class="label">Hostname:</span> {hostname}</p>
        <p><span class="label">IP address(es):</span> {ips}</p>
        <p><span class="label">Uptime:</span> {uptime}</p>
        <p><span class="label">Disk free:</span> {free // (1024**3)} GB</p>
        <p><span class="label">Setup:</span> {setup}</p>
      </div>
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
