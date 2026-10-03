# omarchy-language-de

Die Oberfläche von [Omarchy](https://omarchy.org) auf Deutsch: Menü,
Tastenkürzel, Leiste, Panels, Benachrichtigungen, Bildschirmanzeigen, Uhr und
Datum. Einheitliche Begriffe, Anrede „Sie“, kein Übersetzungsdeutsch.

Omarchy selbst wird dabei **nie verändert**. Das Projekt nutzt nur die
offiziellen Erweiterungswege und übersteht jedes `omarchy update`.

## So funktioniert es

| Teil | Weg |
|---|---|
| Menü | Übersetzte Einträge in `~/.config/omarchy/extensions/omarchy-menu.jsonc` (markierter Block) |
| Tastenkürzel | Kleiner Block in `~/.config/hypr/hyprland.lua`, der nur die angezeigten Beschreibungen übersetzt |
| Tastenkürzel-Liste | `bin/omarchy-keybindings-de` zeigt Omarchys Liste mit deutschen Tastennamen (Strg, Umschalt, Enter …); das Menü „Hilfe › Tastenkürzel“ ruft sie auf |
| Leiste und Panels | Plugin-Klone (`de.*` in `~/.config/omarchy/plugins`), wie `omarchy plugin clone` sie anlegt |
| Benachrichtigungen, OSD | Klone übersetzen Omarchy-Meldungen beim Anzeigen; Meldungen anderer Programme bleiben unberührt |
| App-Namen | `Name[de]` in Omarchys Kopien unter `~/.local/share/applications` |
| Emoji-Suche | Deutsche Stichwörter aus Unicode CLDR zusätzlich zu den englischen |
| Extra: Kalender | Ein Klick auf einen Tag im Uhr-Kalender öffnet Google Kalender (Monatsansicht) bei genau diesem Tag im Browser |

Die Klone werden bei jedem Lauf **frisch aus dem installierten Omarchy**
erzeugt; danach werden nur exakt festgelegte Textstellen ersetzt. Passt eine
Stelle nach einem Update nicht mehr, bleibt nur sie englisch. Lässt sich ein
Klon nicht sauber bauen, wird er abgeschaltet und das Original übernimmt.

## Installation

```bash
git clone https://github.com/felixbk98/omarchy-language-de ~/.local/share/omarchy-language-de
~/.local/share/omarchy-language-de/bin/omarchy-language-de apply
```

Voraussetzung: Omarchy 4 mit Quickshell-Shell, `python3`. Für deutsche
Wochentage und Monate sollte die Systemsprache Deutsch sein
(`localectl set-locale LANG=de_DE.UTF-8`).

`apply` richtet zwei Hooks ein: nach jedem `omarchy update` (`post-update`)
und als Rückfallebene beim Start, falls Omarchy anders aktualisiert wurde
(`post-boot`). Kommen mit einem Update neue englische Texte dazu, meldet sich
eine Benachrichtigung; `omarchy-language-de todo` listet sie auf.

## Befehle

```
omarchy-language-de apply    # anwenden (läuft nach Updates automatisch)
omarchy-language-de status   # Stand, Fehlstellen
omarchy-language-de todo     # neue, noch nicht übersetzte Texte
omarchy-language-de remove   # alles entfernen, Originalzustand
```

Im Menü: Aktualisieren › Übersetzung prüfen.

Eigene Tastenkürzel (`~/.config/hypr/bindings.lua`) übersetzt eine lokale
Datei `~/.config/omarchy-language-de/keybindings.json` im selben Format wie
`catalog/keybindings.json`.

Eigene Änderungen an den Klonen gehören in
`~/.config/omarchy-language-de/plugins/<name>.json` (`id` und `replace` wie
in `catalog/plugins/`); ihre Ersetzungen werden an den Katalog angehängt.

## Bleibt englisch

- Sperrbildschirm und Passwortabfrage: Klone dieser Plugins verlieren die
  Berechtigung zur Anmeldung.
- Ausgaben und Rückfragen der Omarchy-Skripte im Terminal.
- Der Installer, Markennamen.
- Zwei feste Einträge in der Tastenkürzel-Übersicht (Web-App-Kürzel).

Bekannte Nebenwirkung: Die Tastenkürzel-Übersicht (Super+K) sortiert nicht
mehr nach Wichtigkeit, weil Omarchy dafür englische Texte erwartet.

## Mitmachen

Begriffe und Stil: [glossary.md](glossary.md). Katalogformat:
[docs/KATALOG.md](docs/KATALOG.md).

## Lizenz

MIT. Die deutschen Emoji-Stichwörter (`catalog/extra/emoji-de.json`) stammen
aus [Unicode CLDR](https://cldr.unicode.org) und stehen unter der
[Unicode License v3](https://www.unicode.org/license.txt).
