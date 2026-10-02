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
    return out


def load_json(name, default=None):
    path = os.path.join(paths.CATALOG, name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)
