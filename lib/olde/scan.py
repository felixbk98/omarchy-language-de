"""Finds texts in the current Omarchy that the catalogs do not cover yet."""

import glob
import os
import re
import shutil
import tempfile

from . import catalogs, extract, parts, paths, plugins

MANIFEST_SELF = {"name", "displayName"}  # set from the catalog's "name"


def plugin_todo():
    out = []
    tmp = tempfile.mkdtemp(prefix="olde-scan-")
    try:
        for catalog in catalogs.plugin_catalogs():
            found = plugins.find_source(catalog["source"])
            if not found:
                continue
            target = os.path.join(tmp, catalog["id"])
            plugins.copy_plugin(found[0], found[1], target)
            finds = "\n".join(e["find"] for e in catalog.get("replace") or [])
            ignore = set(catalog.get("ignore") or [])
            seen = set()
            for item in extract.plugin_literals(target):
                text = item["text"]
                if item["file"] == "manifest.json" and item["context"] in MANIFEST_SELF:
                    continue
                if text in ignore or text in seen or text in finds:
                    continue
                seen.add(text)
                out.append({"part": catalog["id"], "where": f"{item['file']}:{item['line']}",
                            "text": text})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


def menu_todo():
    _, misses = parts.menu_rows()
    return [{"part": "menu", "where": m["id"], "text": m.get("label") or m.get("title")}
            for m in misses]


BIND_DESCRIPTION = re.compile(
    r'o\.bind\(\s*"[^"]*"\s*,\s*"((?:[^"\\]|\\.)*)"|description\s*=\s*"((?:[^"\\]|\\.)*)"')


def lua_pattern_to_regex(pattern):
    classes = {"d": r"\d", "s": r"\s", "a": "[A-Za-z]", "w": r"[A-Za-z0-9]", "l": "[a-z]", "u": "[A-Z]"}
    out, i = [], 0
    while i < len(pattern):
        c = pattern[i]
        if c == "%" and i + 1 < len(pattern):
            n = pattern[i + 1]
            out.append(classes.get(n, re.escape(n)))
            i += 2
            continue
        out.append("*?" if c == "-" else c)
        i += 1
    return "".join(out)


def keybindings_todo():
    catalog = catalogs.load_json("keybindings.json", {})
    exact = catalog.get("exact") or {}
    regexes = []
    for pattern, _ in catalog.get("patterns") or []:
        try:
            regexes.append(re.compile(lua_pattern_to_regex(pattern)))
        except re.error:
            pass
    out, seen = [], set()
    for path in sorted(glob.glob(os.path.join(paths.OMARCHY_PATH, "default", "hypr", "**", "*.lua"),
                                 recursive=True)):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for match in BIND_DESCRIPTION.finditer(text):
            desc = match.group(1) or match.group(2)
            if not desc or desc in seen or desc in exact or any(r.search(desc) for r in regexes):
                continue
            seen.add(desc)
            line = text.count("\n", 0, match.start()) + 1
            out.append({"part": "keybindings", "where": f"{os.path.relpath(path, paths.OMARCHY_PATH)}:{line}",
                        "text": desc})
    return out


NOTIFY_LINE = re.compile(r"omarchy-notification-send\b(.*)")
QUOTED = re.compile(r'"((?:[^"\\]|\\.)*)"')
SHELL_VAR = re.compile(r"\$\{[^}]*\}|\$\([^)]*\)|\$[A-Za-z_][A-Za-z0-9_]*")


def messages_todo():
    catalog = catalogs.load_json("messages.json", {})
    exact = catalog.get("exact") or {}
    ignore = set(catalog.get("ignore") or [])
    regexes = []
    for pattern, _ in catalog.get("patterns") or []:
        try:
            regexes.append(re.compile(pattern))
        except re.error:
            pass
    out, seen = [], set()
    for path in sorted(glob.glob(os.path.join(paths.OMARCHY_PATH, "bin", "*"))):
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.read().split("\n")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(lines, 1):
            match = NOTIFY_LINE.search(line)
            if not match or line.lstrip().startswith("#"):
                continue
            for literal in QUOTED.findall(match.group(1)):
                if not re.search(r"[A-Za-z]{3,}", SHELL_VAR.sub("", literal)) or literal.startswith("-"):
                    continue
                sample = SHELL_VAR.sub("X", literal)
                if literal in exact or literal in ignore or literal in seen \
                        or any(r.search(sample) for r in regexes):
                    continue
                seen.add(literal)
                out.append({"part": "messages", "where": f"bin/{os.path.basename(path)}:{number}",
                            "text": literal})
    return out


def todo():
    return plugin_todo() + menu_todo() + keybindings_todo() + messages_todo()
