# Katalogformat

## Plugins: `catalog/plugins/<name>.json`

```json
{
  "source": "omarchy.clock",
  "id": "de.clock",
  "name": "Uhr",
  "copy": { "SpeedTestOverlayDe.qml": "Ui/SpeedTestOverlay.qml" },
  "replace": [
    { "file": "Panel.qml", "find": "text: \"Back to today\"", "replace": "text: \"Zurück zu heute\"", "count": 1 }
  ],
  "ignore": ["transparent", "birthYear"]
}
```

- `source`: Omarchy-Plugin, aus dem der Klon bei jedem `apply` frisch erzeugt
  wird. `id`: ID des Klons. `name`: deutscher Anzeigename (Manifest).
- `replace`: exakte Textstellen im Klon. `file` ist relativ zum Klon-Ordner
  (wie `omarchy-language-de extract` ihn anlegt). `find` muss genau `count`
  mal vorkommen (Standard 1), sonst wird der Eintrag übersprungen und als
  Fehlstelle gemeldet. Einträge werden der Reihe nach angewendet.
- `find` immer mit genug Kontext, damit nur Anzeige-Text getroffen wird:
  `text: "Off"` statt nur `"Off"`. Daten-Strings (IDs, Befehle, Schlüssel,
  Vergleichswerte, Regex, IPC-Werte) nie ändern.
- `copy`: gemeinsame Shell-Dateien (relativ zu `/usr/share/omarchy/shell`),
  die frisch in den Klon kopiert werden, damit ihre Texte übersetzt werden
  können. Der Klon muss dann auf die Kopie verweisen (eigener `replace`).
- `ignore`: geprüfte Literale, die kein Anzeige-Text sind. `todo` meldet nur
  Literale, die weder übersetzt noch hier eingetragen sind.

## Menü: `catalog/menu.json`

`{ "<menu-id>": { "en": "<englisches Label>", "label": "…", "title": "…" } }`

`en` ist das Original-Label; weicht es nach einem Update ab, bleibt der
Eintrag englisch und erscheint in `todo`.

## Tastenkürzel: `catalog/keybindings.json`

`{ "exact": { "<englische Beschreibung>": "<deutsch>" }, "patterns": [["^Lua%-Muster (%d+)$", "Deutsch %1"]] }`

## Meldungen: `catalog/messages.json`

Für Benachrichtigungen von Omarchy-Skripten und OSD-Texte, zur Laufzeit
übersetzt: `{ "exact": { "en": "de" }, "patterns": [["^JS-Regex (.+)$", "Deutsch $1"]] }`

## Prüfen

```
omarchy-language-de build <name>   # Klon nur im Staging bauen, Fehlstellen zeigen
omarchy-language-de todo           # neue, unübersetzte Texte
```
