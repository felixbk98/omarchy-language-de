"""Plugin clones: copy a built-in plugin, apply the catalog, check, install.

The copy follows /usr/share/omarchy/bin/omarchy-plugin-clone (copy_plugin and
update_manifest), so the shell treats the result exactly like a clone made by
`omarchy plugin clone`.
"""

import json
import os
import shutil
import subprocess
import tempfile

from . import paths


def find_source(source_id):
    """Returns (source_dir, manifest_path) of a built-in plugin, or None."""
    root = os.path.join(paths.OMARCHY_PATH, "shell", "plugins")
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath[len(root):].count(os.sep)
        if depth >= 4:
            dirnames[:] = []
        for name in sorted(filenames):
            if name != "manifest.json" and not name.endswith(".manifest.json"):
                continue
            manifest = os.path.join(dirpath, name)
            try:
                with open(manifest) as f:
                    if json.load(f).get("id") == source_id:
                        return dirpath, manifest
            except (OSError, ValueError):
                continue
    return None


def _copy(src, dst):
    if os.path.isdir(src):
        shutil.copytree(src, dst, symlinks=False, dirs_exist_ok=True)
    else:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)


def _rewrite_path(target_dir, source, target):
    for dirpath, _, filenames in os.walk(target_dir):
        for name in filenames:
            path = os.path.join(dirpath, name)
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
            except (OSError, UnicodeDecodeError):
                continue
            if source in text:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text.replace(source, target))


def copy_plugin(source_dir, manifest, target_dir):
    os.makedirs(target_dir, exist_ok=True)
    if os.path.basename(manifest) == "manifest.json":
        _copy(source_dir, target_dir)
        return

    shutil.copy2(manifest, os.path.join(target_dir, "manifest.json"))
    with open(manifest) as f:
        data = json.load(f)
    pairs = {}
    for entry in (data.get("entryPoints") or {}).values():
        pairs[entry] = entry
    for item in (data.get("omarchy") or {}).get("clonePaths") or []:
        pairs[item["target"]] = item["source"]
    for target, source in sorted(pairs.items()):
        if target.startswith("/") or ".." in target:
            raise ValueError("invalid clone target path: " + target)
        _copy(os.path.join(source_dir, source), os.path.join(target_dir, target))
        if source != target:
            _rewrite_path(target_dir, source, target)


def update_manifest(target_dir, source_id, new_id, name):
    path = os.path.join(target_dir, "manifest.json")
    with open(path) as f:
        data = json.load(f)
    data["id"] = new_id
    data["name"] = name
    if isinstance(data.get("barWidget"), dict):
        data["barWidget"]["displayName"] = name
    meta = data.get("omarchy") if isinstance(data.get("omarchy"), dict) else {}
    meta["clonedFrom"] = source_id
    meta.pop("clonePaths", None)
    data["omarchy"] = meta
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def apply_entries(target_dir, entries):
    """Replaces exact snippets. An entry whose match count differs from the
    expected count is skipped as a whole, so the text stays English."""
    results = []
    for entry in entries:
        path = os.path.join(target_dir, entry["file"])
        expected = entry.get("count", 1)
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            results.append({**entry, "status": "missing-file", "found": 0})
            continue
        found = text.count(entry["find"])
        if found != expected:
            results.append({**entry, "status": "miss", "found": found})
            continue
        with open(path, "w", encoding="utf-8") as f:
            f.write(text.replace(entry["find"], entry["replace"]))
        results.append({**entry, "status": "ok", "found": found})
    return results


# qmlformat parses QML and JS and fails on syntax errors; it is fast, unlike
# qmllint, which can spin for minutes on large files.
QMLFORMAT = next((p for p in ("/usr/lib/qt6/bin/qmlformat", shutil.which("qmlformat6") or "",
                              shutil.which("qmlformat") or "") if p and os.path.exists(p)), None)


def _parses(path):
    if not QMLFORMAT:
        return True
    try:
        proc = subprocess.run([QMLFORMAT, path], capture_output=True, timeout=30)
    except subprocess.TimeoutExpired:
        return False
    return proc.returncode == 0


def check(orig_dir, new_dir, files):
    """Returns a list of problems the translation introduced."""
    problems = []
    for rel in sorted(set(files)):
        new = os.path.join(new_dir, rel)
        old = os.path.join(orig_dir, rel)
        if rel.endswith(".json"):
            try:
                with open(new) as f:
                    json.load(f)
            except ValueError as e:
                problems.append(f"{rel}: kein gültiges JSON ({e})")
        elif rel.endswith((".qml", ".js")):
            if not _parses(new) and (not os.path.exists(old) or _parses(old)):
                problems.append(f"{rel}: Syntaxfehler")
    return problems


def _same_tree(a, b):
    if not os.path.isdir(a) or not os.path.isdir(b):
        return False
    proc = subprocess.run(["diff", "-rq", a, b], capture_output=True)
    return proc.returncode == 0


def install(new_dir, final_dir):
    """Swaps the checked clone into place. Returns True when files changed."""
    if _same_tree(new_dir, final_dir):
        return False
    parent = os.path.dirname(final_dir)
    os.makedirs(parent, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix=".olde-", dir=parent)
    shutil.rmtree(tmp)
    shutil.copytree(new_dir, tmp)
    old = None
    if os.path.exists(final_dir):
        old = tempfile.mkdtemp(prefix=".olde-old-", dir=parent)
        os.rmdir(old)
        os.rename(final_dir, old)
    os.rename(tmp, final_dir)
    if old:
        shutil.rmtree(old)
    return True


def build(catalog, stage_root, generators=None):
    """Clones one plugin into the stage, translates and checks it.

    Returns a report dict; report["dir"] is the checked clone on success."""
    source_id = catalog["source"]
    new_id = catalog["id"]
    report = {"id": new_id, "source": source_id, "status": "failed", "problems": [], "entries": []}
    found = find_source(source_id)
    if not found:
        report["problems"].append("Quelle nicht gefunden (Plugin in Omarchy entfernt?)")
        return report
    source_dir, manifest = found

    stage = os.path.join(stage_root, new_id)
    shutil.rmtree(stage, ignore_errors=True)
    orig, new = os.path.join(stage, "orig"), os.path.join(stage, "new")
    for target in (orig, new):
        copy_plugin(source_dir, manifest, target)
        update_manifest(target, source_id, new_id, catalog.get("name") or source_id)

    # Shared shell files with hardcoded texts are copied fresh from Omarchy
    # into the clone, so the catalog can translate the copy.
    for rel, shell_rel in (catalog.get("copy") or {}).items():
        _copy(os.path.join(paths.OMARCHY_PATH, "shell", shell_rel), os.path.join(new, rel))
    for extra, rel in (catalog.get("files") or {}).items():
        _copy(os.path.join(paths.CATALOG, "extra", extra), os.path.join(new, rel))
    # Generated files, e.g. the runtime message table from messages.json.
    for rel, name in (catalog.get("generate") or {}).items():
        with open(os.path.join(new, rel), "w", encoding="utf-8") as f:
            f.write((generators or {})[name]())

    # Transforms rewrite a data file of the clone, e.g. German emoji keywords.
    for rel, name in (catalog.get("transform") or {}).items():
        (generators or {})[name](os.path.join(new, rel))

    results = apply_entries(new, catalog.get("replace") or [])
    report["entries"] = [
        {k: r[k] for k in ("file", "find", "status", "found", "count") if k in r}
        for r in results if r["status"] != "ok"
    ]
    report["ok"] = sum(r["status"] == "ok" for r in results)
    report["missed"] = len(results) - report["ok"]

    changed = {r["file"] for r in results if r["status"] == "ok"}
    changed |= set((catalog.get("files") or {}).values())
    changed |= set(catalog.get("copy") or {})
    changed |= set(catalog.get("generate") or {})
    changed |= set(catalog.get("transform") or {})
    changed.add("manifest.json")
    report["problems"] = check(orig, new, changed)
    if report["problems"]:
        return report
    report["status"] = "built"
    report["dir"] = new
    return report
