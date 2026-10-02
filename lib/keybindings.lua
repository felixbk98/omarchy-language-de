-- omarchy-language-de: translates keybinding descriptions.
--
-- Generated into ~/.local/state/omarchy-language-de/ and loaded from
-- ~/.config/hypr/hyprland.lua before Omarchy's defaults. It wraps
-- hl.bind (not o.bind: o.bind also uses the description as the window match
-- for web apps), so only the text shown in the keybinding list changes.
-- omarchy-menu-keybindings runs the same config in a stub and gets the same
-- translations.

if type(hl) ~= "table" or type(hl.bind) ~= "function" then
  return
end

-- Hyprland may keep the Lua state across reloads; never wrap twice.
if rawget(_G, "__omarchy_language_de_bind") == hl.bind then
  return
end

-- Filled in by `omarchy-language-de apply` from catalog/keybindings.json.
local catalog = __CATALOG__

local exact = catalog.exact or {}
local patterns = catalog.patterns or {}

local function translate(text)
  if exact[text] then
    return exact[text]
  end
  for _, rule in ipairs(patterns) do
    local result, count = text:gsub(rule[1], rule[2])
    if count > 0 then
      return result
    end
  end
  return text
end

local original = hl.bind
local function bind(keys, dispatcher, opts)
  if type(opts) == "table" and type(opts.description) == "string" then
    local ok_translate, text = pcall(translate, opts.description)
    if ok_translate then
      opts.description = text
    end
  end
  return original(keys, dispatcher, opts)
end

hl.bind = bind
_G.__omarchy_language_de_bind = bind
