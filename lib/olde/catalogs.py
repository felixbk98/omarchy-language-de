import glob
import json
import os

from . import paths


def plugin_catalogs():
    out = []
    for path in sorted(glob.glob(os.path.join(paths.CATALOG, "plugins", "*.json"))):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["_path"] = path
        out.append(data)
    # Local additions (~/.config/omarchy-language-de/plugins/<name>.json) append
    # their "replace" entries to the catalog with the same id.
    by_id = {c["id"]: c for c in out}
    for path in sorted(glob.glob(os.path.join(paths.LOCAL_PLUGINS, "*.json"))):
        with open(path, encoding="utf-8") as f:
            local = json.load(f)
        if local.get("id") in by_id:
            target = by_id[local["id"]]
            target["replace"] = (target.get("replace") or []) + (local.get("replace") or [])
    return out


def load_json(name, default=None):
    path = os.path.join(paths.CATALOG, name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)
