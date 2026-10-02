"""Finds string literals in a plugin, as raw material for the catalog and to
spot new texts after an Omarchy update."""

import json
import os
import re

STRING = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
SKIP_LINE = re.compile(r"^\s*(import |//|\*|/\*|\.pragma|\.import)|console\.(log|warn|error|info|debug)")
HAS_WORD = re.compile(r"[A-Za-z]{2,}")
# Things that are clearly not prose: ids, paths, colors, commands-only flags.
NOT_PROSE = re.compile(r"^(#[0-9a-fA-F]{3,8}|[a-z][a-zA-Z0-9]*(\.[a-zA-Z0-9_-]+)+|/[^ ]*|[a-z0-9_-]+\.(qml|js|json|svg|png|sh))$")


def literals(path):
    """Yields (line_number, literal, line) for every candidate literal."""
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    for number, line in enumerate(lines, 1):
        if SKIP_LINE.search(line):
            continue
        code = line.split(" //")[0] if '"' not in line.split(" //", 1)[-1] else line
        for match in STRING.finditer(code):
            value = match.group(1)
            if not HAS_WORD.search(value) or NOT_PROSE.match(value):
                continue
            yield number, value, line.strip()


def manifest_literals(path):
    """Display texts of a manifest: names, descriptions, labels."""
    with open(path) as f:
        data = json.load(f)
    keys = {"name", "description", "displayName", "label", "placeholderText",
            "emptyText", "noSelectionText", "category"}
    out = []

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in keys and isinstance(value, str):
                    out.append((key, value))
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(data)
    return out


def plugin_literals(plugin_dir):
    """Returns [{file, line, text, context}] for one cloned plugin dir."""
    found = []
    for dirpath, _, filenames in os.walk(plugin_dir):
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, plugin_dir)
            if name.endswith((".qml", ".js")):
                for number, value, line in literals(path):
                    found.append({"file": rel, "line": number, "text": value, "context": line})
            elif name == "manifest.json":
                for key, value in manifest_literals(path):
                    found.append({"file": rel, "line": 0, "text": value, "context": key})
    found.sort(key=lambda x: (x["file"], x["line"]))
    return found
