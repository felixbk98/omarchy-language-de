"""Non-plugin parts: menu, keybindings, runtime message table."""

import json
import os
import re
import tempfile

from . import catalogs, paths

# ------------------------------------------------------------------ helpers


def strip_jsonc(raw):
    """Same rules as MenuModel.js stripJsonc: whole-line comments and
    trailing commas only. Anything else would make the menu drop the file."""
    text = re.sub(r"^\s*//[^\n]*(\n|$)", "", raw, flags=re.M)
    return re.sub(r",(\s*[}\]])", r"\1", text)


def write_atomic(path, text):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + os.path.basename(path) + ".", dir=directory)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    if os.path.exists(path):
        os.chmod(tmp, os.stat(path).st_mode & 0o7777)
    os.replace(tmp, path)


def replace_block(text, block_lines, comment, anchor, indent=""):
    """Puts block_lines between the markers. Without markers the block goes
    right before/after the anchor line (anchor(lines) returns an index)."""
    begin, end = f"{comment} {paths.MARK_BEGIN}", f"{comment} {paths.MARK_END}"
    lines = text.split("\n")
    starts = [i for i, l in enumerate(lines) if l.strip() == begin]
    ends = [i for i, l in enumerate(lines) if l.strip() == end]
    if starts and ends and starts[0] < ends[0]:
        lines[starts[0]: ends[0] + 1] = [] if block_lines is None else \
            [indent + begin, *block_lines, indent + end]
        return "\n".join(lines)
    if block_lines is None:
        return text
    index = anchor(lines)
    if index is None:
        return None
    lines[index:index] = [indent + begin, *block_lines, indent + end]
    return "\n".join(lines)


# ---------------------------------------------------------------------- menu

MENU_SOURCE = os.path.join(paths.OMARCHY_PATH, "default", "omarchy", "omarchy-menu.jsonc")

OWN_MENU_ITEMS = {
    "update.language-de": {
        "icon": "󰗊",
        "label": "Übersetzung prüfen",
        "description": "omarchy-language-de deutsch übersetzung translation",
        "action": "omarchy-launch-floating-terminal-with-presentation "
                  "\"$HOME/.local/share/omarchy-language-de/bin/omarchy-language-de status\"",
    },
}


def menu_rows():
    """Returns ({id: row}, misses) for the translated menu block."""
    with open(MENU_SOURCE, encoding="utf-8") as f:
        source = json.loads(strip_jsonc(f.read()))
    catalog = catalogs.load_json("menu.json", {})
    rows, misses = {}, []
    for item_id, row in source.items():
        if not isinstance(row, dict) or "label" not in row:
            continue
        entry = catalog.get(item_id)
        if not entry or entry.get("en") != row["label"]:
            misses.append({"id": item_id, "label": row["label"]})
            continue
        new = dict(row)
        new["label"] = entry["label"]
        if "title" in row:
            if entry.get("title_en") == row["title"] and entry.get("title"):
                new["title"] = entry["title"]
            else:
                misses.append({"id": item_id, "title": row["title"]})
        # Keep the English words searchable; the menu never shows this field
        # for its own rows (only while searching dmenu-style pickers).
        if not row.get("description"):
            new["description"] = row["label"]
        rows[item_id] = new
    rows.update(OWN_MENU_ITEMS)
    return rows, misses


def menu_text(current, rows):
    block = [f"  {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)},"
             for k, v in rows.items()] if rows is not None else None

    def after_open_brace(lines):
        for i, line in enumerate(lines):
            if line.strip() == "{":
                return i + 1
        return None

    text = replace_block(current, block, "//", after_open_brace, indent="  ")
    if text is None:
        return None
    try:
        json.loads(strip_jsonc(text))
    except ValueError:
        return None
    return text


def apply_menu():
    rows, misses = menu_rows()
    try:
        with open(paths.MENU_EXTENSION, encoding="utf-8") as f:
            current = f.read()
    except FileNotFoundError:
        current = "{\n}\n"
    text = menu_text(current, rows)
    if text is None:
        return {"status": "failed", "problems": ["Menü-Erweiterung nicht lesbar, nichts geändert"]}
    if text != current:
        write_atomic(paths.MENU_EXTENSION, text)
    return {"status": "ok", "translated": len(rows) - len(OWN_MENU_ITEMS), "missed": misses}


def remove_menu():
    try:
        with open(paths.MENU_EXTENSION, encoding="utf-8") as f:
            current = f.read()
    except FileNotFoundError:
        return
    text = menu_text(current, None)
    if text is not None and text != current:
        write_atomic(paths.MENU_EXTENSION, text)


# --------------------------------------------------------------- keybindings

KEYBINDINGS_LUA = os.path.join(paths.STATE, "keybindings.lua")


def lua_string(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def keybindings_lua():
    catalog = catalogs.load_json("keybindings.json", {})
    exact = catalog.get("exact") or {}
    patterns = catalog.get("patterns") or []
    table = ["{", "  exact = {"]
    table += [f"    [{lua_string(k)}] = {lua_string(v)}," for k, v in sorted(exact.items())]
    table += ["  },", "  patterns = {"]
    table += [f"    {{ {lua_string(p)}, {lua_string(r)} }}," for p, r in patterns]
    table += ["  },", "}"]
    with open(os.path.join(paths.PROJECT, "lib", "keybindings.lua"), encoding="utf-8") as f:
        template = f.read()
    return template.replace("__CATALOG__", "\n".join(table)), len(exact) + len(patterns)


HYPR_BLOCK = [
    "-- Omarchy auf Deutsch: übersetzt die Beschreibungen der Tastenkürzel.",
    'pcall(dofile, (os.getenv("HOME") or "") .. "/.local/state/omarchy-language-de/keybindings.lua")',
]


def _before_omarchy_require(lines):
    for i, line in enumerate(lines):
        if line.strip().startswith('require("default.hypr.omarchy")'):
            return i
    return None


def apply_keybindings():
    lua, count = keybindings_lua()
    write_atomic(KEYBINDINGS_LUA, lua)
    with open(paths.HYPRLAND_LUA, encoding="utf-8") as f:
        current = f.read()
    text = replace_block(current, HYPR_BLOCK, "--", _before_omarchy_require)
    if text is None:
        return {"status": "failed", "problems": ['require("default.hypr.omarchy") nicht gefunden']}
    changed = text != current
    if changed:
        write_atomic(paths.HYPRLAND_LUA, text)
    return {"status": "ok", "entries": count, "changed": changed}


def remove_keybindings():
    try:
        with open(paths.HYPRLAND_LUA, encoding="utf-8") as f:
            current = f.read()
    except FileNotFoundError:
        current = None
    if current is not None:
        text = replace_block(current, None, "--", _before_omarchy_require)
        if text != current:
            write_atomic(paths.HYPRLAND_LUA, text)
    if os.path.exists(KEYBINDINGS_LUA):
        os.remove(KEYBINDINGS_LUA)


# ------------------------------------------------------------------ messages


def messages_js():
    """Runtime table for notifications and OSD, copied into those clones."""
    catalog = catalogs.load_json("messages.json", {})
    exact = catalog.get("exact") or {}
    patterns = []
    for pattern, replacement in catalog.get("patterns") or []:
        try:
            re.compile(pattern)
        except re.error:
            continue
        patterns.append([pattern, replacement])
    return (
        ".pragma library\n\n"
        "// Generated by omarchy-language-de from catalog/messages.json.\n"
        f"var exact = {json.dumps(exact, ensure_ascii=False, indent=1)}\n\n"
        f"var patterns = {json.dumps(patterns, ensure_ascii=False, indent=1)}\n\n"
        "var compiled = null\n\n"
        "function tr(text) {\n"
        "  if (typeof text !== \"string\" || text === \"\") return text\n"
        "  try {\n"
        "    if (Object.prototype.hasOwnProperty.call(exact, text)) return exact[text]\n"
        "    if (compiled === null) {\n"
        "      compiled = []\n"
        "      for (var p = 0; p < patterns.length; p++) {\n"
        "        try { compiled.push([new RegExp(patterns[p][0]), patterns[p][1]]) } catch (e) { }\n"
        "      }\n"
        "    }\n"
        "    for (var i = 0; i < compiled.length; i++) {\n"
        "      if (compiled[i][0].test(text)) return text.replace(compiled[i][0], compiled[i][1])\n"
        "    }\n"
        "  } catch (e) { }\n"
        "  return text\n"
        "}\n\n"
        "// Multi-line bodies: whole text first, then line by line.\n"
        "function trLines(text) {\n"
        "  if (typeof text !== \"string\" || text.indexOf(\"\\n\") < 0) return tr(text)\n"
        "  var whole = tr(text)\n"
        "  if (whole !== text) return whole\n"
        "  return text.split(\"\\n\").map(tr).join(\"\\n\")\n"
        "}\n"
    )


# -------------------------------------------------------------------- emojis


def emoji_keywords(path):
    """Appends German CLDR keywords (catalog/extra/emoji-de.json, Unicode
    CLDR annotations) to Omarchy's English ones, so both languages find."""
    german = catalogs.load_json(os.path.join("extra", "emoji-de.json"), {})
    with open(path, encoding="utf-8") as f:
        emojis = json.load(f)
    for item in emojis:
        words = german.get(item.get("e")) if isinstance(item, dict) else None
        if words:
            item["k"] = f"{item.get('k', '')} {words}".strip()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(emojis, f, ensure_ascii=False, separators=(",", ":"))


# ------------------------------------------------------------ desktop files

DESKTOP_STATE = os.path.join(paths.STATE, "desktop-added.json")


def _desktop_state():
    try:
        with open(DESKTOP_STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _desktop_add(path, fields):
    """Adds Key[de]= lines to the [Desktop Entry] group where the English
    value is still the known one and no German value exists. Returns the
    lines added, so remove can take back exactly those."""
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    present = {l.split("=", 1)[0] for l in lines if "[de]=" in l}
    out, group, added = [], None, []
    for line in lines:
        if line.startswith("["):
            group = line.strip()
        out.append(line)
        key, _, value = line.partition("=")
        if group == "[Desktop Entry]" and key in fields and value == fields[key][0] \
                and key + "[de]" not in present:
            out.append(f"{key}[de]={fields[key][1]}")
            added.append(out[-1])
    if added:
        write_atomic(path, "\n".join(out))
    return added


def _desktop_remove(path, added):
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    out = [l for l in lines if l not in added]
    if len(out) != len(lines):
        write_atomic(path, "\n".join(out))


def apply_desktop():
    catalog = catalogs.load_json("desktop.json", {})
    state = _desktop_state()
    for name, fields in catalog.items():
        path = os.path.join(paths.APPLICATIONS, name)
        if not os.path.exists(path):
            continue
        added = _desktop_add(path, fields)
        if added:
            state[name] = sorted(set(state.get(name, []) + added))
    with open(DESKTOP_STATE, "w") as f:
        json.dump(state, f, indent=1, ensure_ascii=False)
    return {"status": "ok", "files": len(state)}


def remove_desktop():
    for name, added in _desktop_state().items():
        path = os.path.join(paths.APPLICATIONS, name)
        if os.path.exists(path):
            _desktop_remove(path, added)
    if os.path.exists(DESKTOP_STATE):
        os.remove(DESKTOP_STATE)
