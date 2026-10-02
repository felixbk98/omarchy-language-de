"""Talks to the running Omarchy shell and edits shell.json."""

import json
import os
import subprocess
import tempfile
import time

from . import paths


def ipc(*args, timeout=5):
    try:
        proc = subprocess.run(["omarchy-shell", "shell", *args], capture_output=True,
                              text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def running():
    return ipc("ping") == "ok"


def list_plugins():
    out = ipc("listPlugins")
    try:
        return {p["id"]: p for p in json.loads(out)} if out else {}
    except ValueError:
        return {}


def rescan_and_wait(ids, attempts=60):
    ipc("rescanPlugins")
    for _ in range(attempts):
        known = list_plugins()
        if all(i in known for i in ids):
            return True
        time.sleep(0.1)
    return False


def read_config():
    try:
        with open(paths.SHELL_JSON) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_config(config):
    """Atomic write; the shell watches shell.json and reloads it."""
    directory = os.path.dirname(paths.SHELL_JSON)
    fd, tmp = tempfile.mkstemp(prefix=".shell.json.", dir=directory)
    with os.fdopen(fd, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, paths.SHELL_JSON)


def config_mentions(config, plugin_id):
    """True when shell.json references the id (bar layout or plugins[])."""
    text = json.dumps(config or {})
    return json.dumps(plugin_id) in text
