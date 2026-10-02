import os

HOME = os.path.expanduser("~")
OMARCHY_PATH = os.environ.get("OMARCHY_PATH") or "/usr/share/omarchy"
PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
CATALOG = os.path.join(PROJECT, "catalog")

CONFIG = os.path.join(HOME, ".config", "omarchy")
PLUGINS_DIR = os.path.join(CONFIG, "plugins")
SHELL_JSON = os.path.join(CONFIG, "shell.json")
MENU_EXTENSION = os.path.join(CONFIG, "extensions", "omarchy-menu.jsonc")
HYPRLAND_LUA = os.path.join(HOME, ".config", "hypr", "hyprland.lua")
APPLICATIONS = os.path.join(HOME, ".local", "share", "applications")

STATE = os.path.join(HOME, ".local", "state", "omarchy-language-de")
STAGE = os.path.join(STATE, "staging")
REPORT = os.path.join(STATE, "report.json")
APPLIED_VERSION = os.path.join(STATE, "omarchy-version")

MARK_BEGIN = ">>> omarchy-language-de (automatisch erzeugt, nicht von Hand ändern)"
MARK_END = "<<< omarchy-language-de"


def omarchy_version():
    try:
        with open(os.path.join(OMARCHY_PATH, "version")) as f:
            version = f.read().strip()
    except OSError:
        version = ""
    # The version file can lag behind the package; pair it with the package.
    try:
        import subprocess
        pkg = subprocess.run(["pacman", "-Q", "omarchy"], capture_output=True, text=True).stdout.strip()
    except OSError:
        pkg = ""
    return " ".join(x for x in (pkg, version) if x)
