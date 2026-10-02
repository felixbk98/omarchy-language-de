import json
import os
import shutil
import subprocess
import time

from . import catalogs, extract, parts, paths, plugins, scan, shell

USAGE = """Verwendung: omarchy-language-de <Befehl>

  apply     Übersetzung anwenden (läuft nach jedem Omarchy-Update automatisch)
  remove    Übersetzung vollständig entfernen, Originalzustand herstellen
  status    Stand anzeigen: was übersetzt ist, was fehlt
  todo      Neue, noch nicht übersetzte Texte auflisten (--json für Maschinen)

Entwicklung:
  build [name …]  Klone nur im Staging bauen und prüfen
  extract         Alle Literale der Plugins nach staging/extract schreiben
"""

LINK = os.path.join(paths.HOME, ".local", "share", "omarchy-language-de")
GENERATORS = {"messages": parts.messages_js, "emoji-keywords": parts.emoji_keywords}
HOOKS = {
    "post-update": "90-omarchy-language-de.hook",
    "post-boot": "90-omarchy-language-de.hook",
}


def notify(title, body=""):
    subprocess.run(["omarchy-notification-send", "--app-name", "omarchy-language-de",
                    "-g", "󰗊", title, body], capture_output=True)


def write_report(report):
    os.makedirs(paths.STATE, exist_ok=True)
    with open(paths.REPORT, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def read_report():
    try:
        with open(paths.REPORT) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------ installation


def install_links():
    """~/.local/share/omarchy-language-de points at this project; the hooks
    call the tool through it."""
    if os.path.islink(LINK) and os.path.realpath(LINK) != paths.PROJECT:
        os.remove(LINK)
    if not os.path.lexists(LINK):
        os.makedirs(os.path.dirname(LINK), exist_ok=True)
        os.symlink(paths.PROJECT, LINK)
    for hook, name in HOOKS.items():
        directory = os.path.join(paths.CONFIG, "hooks", hook + ".d")
        os.makedirs(directory, exist_ok=True)
        target = os.path.join(directory, name)
        with open(os.path.join(paths.PROJECT, "hooks", hook)) as f:
            content = f.read()
        current = open(target).read() if os.path.exists(target) else None
        if current != content:
            with open(target, "w") as f:
                f.write(content)
            os.chmod(target, 0o755)


def remove_links():
    for hook, name in HOOKS.items():
        target = os.path.join(paths.CONFIG, "hooks", hook + ".d", name)
        if os.path.exists(target):
            os.remove(target)
    if os.path.islink(LINK):
        os.remove(LINK)


# ------------------------------------------------------------------ clones


def bar_entries(config):
    layout = ((config or {}).get("bar") or {}).get("layout") or {}
    for section in ("left", "center", "right"):
        for entry in layout.get(section) or []:
            yield entry if isinstance(entry, dict) else {"id": entry}


def in_bar(config, plugin_id):
    return any(e.get("id") == plugin_id for e in bar_entries(config))


def source_active(config, catalog, manifest):
    """Should the clone replace the original? Only where the original is in
    use, so translating never adds widgets or services of its own."""
    source = catalog["source"]
    kinds = manifest.get("kinds") or []
    # A catalog marked "skip" stays on the original (e.g. a clone that breaks
    # in Omarchy); its texts are still tracked so `todo` stays quiet.
    if catalog.get("skip"):
        return False
    # Once the clone is in place it stands for the original.
    if clone_enabled(config, catalog["id"]) or in_bar(config, source):
        return True
    non_widget = [k for k in kinds if k != "bar-widget"]
    return bool(non_widget) and source not in ((config or {}).get("disabledPlugins") or [])


def enable_clone(catalog, manifest):
    """Enables a clone the way `omarchy plugin clone` does. A widget-capable
    clone whose original is not in the bar is registered as a plugin only,
    since enablePlugin would also put it into the bar."""
    config = shell.read_config() or {}
    clone, source = catalog["id"], catalog["source"]
    kinds = manifest.get("kinds") or []
    if "bar-widget" in kinds and not in_bar(config, source):
        config.setdefault("plugins", [])
        if not any((p.get("id") if isinstance(p, dict) else p) == clone for p in config["plugins"]):
            config["plugins"].append({"id": clone})
        disabled = config.setdefault("disabledPlugins", [])
        if source not in disabled:
            disabled.append(source)
            restores = config.setdefault("cloneSourceRestores", [])
            if clone not in restores:
                restores.append(clone)
        shell.write_config(config)
        return True
    return shell.ipc("enablePlugin", clone, "{}") == "ok"


def clone_enabled(config, clone):
    if in_bar(config, clone):
        return True
    return any((p.get("id") if isinstance(p, dict) else p) == clone
               for p in (config or {}).get("plugins") or [])


def disable_clone(clone):
    config = shell.read_config() or {}
    if not clone_enabled(config, clone):
        return True
    return shell.ipc("setPluginEnabled", clone, "false") == "ok"


def apply_settings(catalog, reverse=False):
    """Bar settings the clone needs, e.g. the clock as center anchor and
    German default formats. Only values still at the known default change."""
    config = shell.read_config()
    if not config:
        return
    changed = False
    clone, source = catalog["id"], catalog["source"]
    old_id, new_id = (clone, source) if reverse else (source, clone)
    bar = config.get("bar") or {}
    if bar.get("centerAnchor") == old_id:
        bar["centerAnchor"] = new_id
        changed = True
    for entry in bar_entries(config):
        if entry.get("id") != (source if reverse else clone):
            continue
        for key, (en, de) in (catalog.get("settings") or {}).items():
            before, after = (de, en) if reverse else (en, de)
            if entry.get(key) == before:
                entry[key] = after
                changed = True
    # bar_entries yields the dicts inside config, except for plain-string
    # entries, which never carry settings.
    if changed:
        shell.write_config(config)


def wait_for_shell(seconds):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if shell.running():
            return True
        time.sleep(0.5)
    return False


def apply_plugins(report, restart):
    if not wait_for_shell(30):
        report["problems"].append("Omarchy-Shell läuft nicht; Plugins nicht angewendet")
        return False
    config = shell.read_config() or {}
    stage = os.path.join(paths.STAGE, "apply")
    shutil.rmtree(stage, ignore_errors=True)
    changed_files = False
    to_enable = []
    for catalog in catalogs.plugin_catalogs():
        found = plugins.find_source(catalog["source"])
        manifest = json.load(open(found[1])) if found else {}
        final_dir = os.path.join(paths.PLUGINS_DIR, catalog["id"])
        if not found or not source_active(config, catalog, manifest):
            if os.path.exists(final_dir):
                apply_settings(catalog, reverse=True)
                disable_clone(catalog["id"])
                shutil.rmtree(final_dir)
                changed_files = True
            report["plugins"].append({"id": catalog["id"], "status": "unused"})
            continue
        result = plugins.build(catalog, stage, GENERATORS)
        if result["status"] == "built":
            changed_files |= plugins.install(result.pop("dir"), final_dir)
            result["status"] = "active"
            to_enable.append((catalog, manifest))
        else:
            # A clone made from an older Omarchy must not outlive a failed
            # build: switch back to the original.
            apply_settings(catalog, reverse=True)
            disable_clone(catalog["id"])
            if os.path.exists(final_dir):
                shutil.rmtree(final_dir)
                changed_files = True
        report["plugins"].append(result)
    shutil.rmtree(stage, ignore_errors=True)

    if to_enable:
        shell.rescan_and_wait([c["id"] for c, _ in to_enable])
    for catalog, manifest in to_enable:
        if not clone_enabled(shell.read_config(), catalog["id"]):
            if not enable_clone(catalog, manifest):
                report["problems"].append(f"{catalog['id']}: Aktivieren fehlgeschlagen")
        apply_settings(catalog)
    if changed_files and restart:
        subprocess.run(["omarchy-restart-shell"], capture_output=True)
    return True


def remove_plugins(report):
    if not wait_for_shell(10):
        report["problems"].append("Omarchy-Shell läuft nicht; Klone nicht entfernt")
        return False
    removed = False
    for catalog in catalogs.plugin_catalogs():
        final_dir = os.path.join(paths.PLUGINS_DIR, catalog["id"])
        apply_settings(catalog, reverse=True)
        if not disable_clone(catalog["id"]):
            report["problems"].append(f"{catalog['id']}: Deaktivieren fehlgeschlagen")
            continue
        if os.path.exists(final_dir):
            shutil.rmtree(final_dir)
            removed = True
    if removed:
        shell.ipc("rescanPlugins")
    return removed


# ---------------------------------------------------------------- commands


def hypr_reload():
    subprocess.run(["hyprctl", "reload"], capture_output=True)


def cmd_apply(args):
    restart = "--no-restart" not in args
    version = paths.omarchy_version()
    if "--if-changed" in args:
        try:
            if open(paths.APPLIED_VERSION).read().strip() == version:
                return 0
        except OSError:
            pass
    report = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "omarchy": version,
              "plugins": [], "problems": []}
    install_links()

    report["menu"] = parts.apply_menu()
    before = open(parts.KEYBINDINGS_LUA).read() if os.path.exists(parts.KEYBINDINGS_LUA) else None
    report["keybindings"] = parts.apply_keybindings()
    if report["keybindings"].get("status") == "ok" and not report["keybindings"]["changed"] \
            and before != open(parts.KEYBINDINGS_LUA).read():
        hypr_reload()
    report["keybindings"].pop("changed", None)

    report["desktop"] = parts.apply_desktop()
    plugins_ok = apply_plugins(report, restart)
    report["todo"] = len(scan.todo())
    write_report(report)
    if plugins_ok:
        with open(paths.APPLIED_VERSION, "w") as f:
            f.write(version + "\n")

    failed = [p["id"] for p in report["plugins"] if p["status"] == "failed"]
    if failed or report["problems"]:
        notify("Übersetzung: Problem", "Teilweise wieder Englisch.\nDetails: Menü › Aktualisieren › Übersetzung prüfen")
    elif missed_total(report):
        n = missed_total(report)
        notify("Übersetzung: Update prüfen",
               f"{n} {'Text ist' if n == 1 else 'Texte sind'} nach dem Update wieder englisch.")
    elif report["todo"]:
        notify("Übersetzung: neue Texte", f"{report['todo']} neue englische Texte seit dem Update.")
    print_status(report)
    return 1 if failed or report["problems"] else 0


def missed_total(report):
    plugins_missed = sum(p.get("missed", 0) for p in report.get("plugins", []))
    return plugins_missed + len((report.get("menu") or {}).get("missed") or [])


def cmd_remove(args):
    report = {"plugins": [], "problems": []}
    remove_plugins(report)
    parts.remove_menu()
    parts.remove_keybindings()
    parts.remove_desktop()
    hypr_reload()
    remove_links()
    for path in (paths.REPORT, paths.APPLIED_VERSION):
        if os.path.exists(path):
            os.remove(path)
    shutil.rmtree(paths.STAGE, ignore_errors=True)
    if report["problems"]:
        for problem in report["problems"]:
            print("Problem:", problem)
        return 1
    print("Übersetzung entfernt, Omarchy ist wieder im Originalzustand.")
    return 0


def print_status(report):
    print(f"Omarchy {report.get('omarchy', '?')}, angewendet {report.get('time', '?')}")
    menu = report.get("menu") or {}
    print(f"Menü: {menu.get('translated', 0)} Einträge übersetzt, "
          f"{len(menu.get('missed') or [])} englisch")
    keys = report.get("keybindings") or {}
    print(f"Tastenkürzel: {keys.get('entries', 0)} Übersetzungen")
    active = [p for p in report.get("plugins", []) if p["status"] == "active"]
    print(f"Plugins: {len(active)} übersetzt")
    for p in report.get("plugins", []):
        if p["status"] == "failed":
            print(f"  {p['id']}: Fehler, Original aktiv: {'; '.join(p.get('problems') or [])}")
        elif p.get("missed"):
            if p["missed"] == 1:
                print(f"  {p['id']}: 1 Stelle nicht gefunden (bleibt englisch)")
            else:
                print(f"  {p['id']}: {p['missed']} Stellen nicht gefunden (bleiben englisch)")
    for problem in report.get("problems", []):
        print("Problem:", problem)
    if report.get("todo"):
        print(f"Neue Texte: {report['todo']} (omarchy-language-de todo)")


def cmd_status(args):
    report = read_report()
    if not report:
        print("Noch nicht angewendet: omarchy-language-de apply")
        return 1
    print_status(report)
    return 0


def cmd_todo(args):
    items = scan.todo()
    if "--json" in args:
        print(json.dumps(items, indent=1, ensure_ascii=False))
        return 0
    if not items:
        print("Nichts Neues: alle Texte sind übersetzt oder geprüft.")
        return 0
    for item in items:
        print(f"{item['part']}: {item['where']}: {item['text']!r}")
    return 0


def cmd_extract(args):
    for catalog in catalogs.plugin_catalogs():
        found = plugins.find_source(catalog["source"])
        if not found:
            print("nicht gefunden:", catalog["source"])
            continue
        stage = os.path.join(paths.STAGE, "extract", catalog["id"])
        shutil.rmtree(stage, ignore_errors=True)
        plugins.copy_plugin(found[0], found[1], stage)
        found_literals = extract.plugin_literals(stage)
        with open(os.path.join(paths.STAGE, "extract", catalog["id"] + ".json"), "w") as f:
            json.dump(found_literals, f, indent=1, ensure_ascii=False)
        print(f"{catalog['id']}: {len(found_literals)} Texte")
    return 0


def cmd_build(args):
    """Builds clones into staging only and reports, without installing."""
    wanted = set(args)
    failed = 0
    for catalog in catalogs.plugin_catalogs():
        short = catalog["id"].split(".", 1)[1]
        if wanted and short not in wanted and catalog["id"] not in wanted:
            continue
        report = plugins.build(catalog, os.path.join(paths.STAGE, "build"), GENERATORS)
        print(f"{catalog['id']}: {report['status']}, {report.get('ok', 0)} ersetzt, "
              f"{report.get('missed', 0)} nicht gefunden")
        for entry in report["entries"]:
            print(f"  FEHLT {entry['file']}: {entry['find']!r} (gefunden {entry['found']}, "
                  f"erwartet {entry.get('count', 1)})")
        for problem in report["problems"]:
            print("  PROBLEM", problem)
        failed += report["status"] != "built" or bool(report["entries"])
    return 1 if failed else 0


COMMANDS = {
    "apply": cmd_apply,
    "remove": cmd_remove,
    "status": cmd_status,
    "todo": cmd_todo,
    "extract": cmd_extract,
    "build": cmd_build,
}


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help") or argv[0] not in COMMANDS:
        print(USAGE)
        return 0 if argv and argv[0] in ("-h", "--help", "help") else 1
    os.makedirs(paths.STATE, exist_ok=True)
    return COMMANDS[argv[0]](argv[1:])
