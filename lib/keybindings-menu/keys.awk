# "SUPER SHIFT + RETURN    → Terminal" becomes "Win + Umschalt + Enter → Terminal".
# Descriptions the script writes itself (not from Hyprland) are looked up in
# catalog/keybindings.json, passed in as "-v catalog=<file>" with "en<TAB>de" lines.
BEGIN {
  if (catalog != "") {
    while ((getline line < catalog) > 0) {
      tab = index(line, "\t")
      if (tab) german[substr(line, 1, tab - 1)] = substr(line, tab + 1)
    }
    close(catalog)
  }
  n = split("SUPER=Win SHIFT=Umschalt CTRL=Strg ALT=Alt RETURN=Enter ESCAPE=Esc " \
    "SPACE=Leertaste BACKSPACE=Rücktaste DELETE=Entf INSERT=Einfg HOME=Pos1 END=Ende " \
    "PRINT=Druck TAB=Tab LEFT=Pfeil_links RIGHT=Pfeil_rechts UP=Pfeil_oben DOWN=Pfeil_unten " \
    "PERIOD=Punkt COMMA=Komma MINUS=Minus PLUS=Plus EQUAL=Gleich SLASH=Schrägstrich " \
    "KP_0=Num_0 KP_INSERT=Num_Einfg KP_SEPARATOR=Num_Komma KP_DELETE=Num_Entf " \
    "LEFT_MOUSE_BUTTON=Linke_Maustaste RIGHT_MOUSE_BUTTON=Rechte_Maustaste " \
    "MIDDLE_MOUSE_BUTTON=Mittlere_Maustaste " \
    "XF86AUDIORAISEVOLUME=Lauter XF86AUDIOLOWERVOLUME=Leiser XF86AUDIOMUTE=Stumm " \
    "XF86AUDIOMICMUTE=Mikrofon_stumm XF86AUDIOPLAY=Play XF86AUDIOPAUSE=Pause " \
    "XF86AUDIONEXT=Nächster_Titel XF86AUDIOPREV=Vorheriger_Titel XF86EJECT=Auswerfen " \
    "XF86MONBRIGHTNESSUP=Heller XF86MONBRIGHTNESSDOWN=Dunkler " \
    "XF86KBDBRIGHTNESSUP=Tastaturlicht_heller XF86KBDBRIGHTNESSDOWN=Tastaturlicht_dunkler " \
    "XF86KBDLIGHTONOFF=Tastaturlicht XF86TOUCHPADTOGGLE=Touchpad-Taste " \
    "XF86TOUCHPADON=Touchpad_an XF86TOUCHPADOFF=Touchpad_aus XF86POWEROFF=Ein/Aus-Taste " \
    "XF86CALCULATOR=Rechner-Taste", pairs, " ")
  for (i = 1; i <= n; i++) {
    split(pairs[i], kv, "=")
    gsub("_", " ", kv[2])
    name[kv[1]] = kv[2]
  }
}

function key_name(key, upper) {
  upper = toupper(key)
  gsub(" ", "_", upper)
  return (upper in name) ? name[upper] : key
}

{
  arrow = index($0, "→")
  if (!arrow) { lines[NR] = $0; next }
  keys = substr($0, 1, arrow - 1)
  sub(/[ \t]+$/, "", keys)
  rest = substr($0, arrow)
  description = substr(rest, length("→ ") + 1)
  if (description in german) rest = "→ " german[description]

  split(keys, halves, " \\+ ")
  out = ""
  if (keys ~ / \+ /) {
    m = split(halves[1], mods, " ")
    for (i = 1; i <= m; i++) out = out key_name(mods[i]) " + "
    key = substr(keys, length(halves[1]) + 4)
  } else {
    key = keys
  }
  out = (key == "SUPER_L" && out == "Win + ") ? "Win (antippen)" : out key_name(key)

  left[NR] = out
  right[NR] = rest
  if (length(out) > width) width = length(out)
}

END {
  for (i = 1; i <= NR; i++) {
    if (i in left) printf "%-*s  %s\n", width, left[i], right[i]
    else print lines[i]
  }
}
