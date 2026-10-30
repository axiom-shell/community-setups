# Submitting a setup

Thanks for sharing! A setup takes about ten minutes to submit. Everything below is checked automatically, so you'll hear about anything that's off before a maintainer looks.

## 1. Build it in axiom

Use axiom's editors and Settings page. Before exporting:
- **Use a theme axiom ships**, or bundle your own palette (step 4).
- **Don't depend on commands.** A widget whose label or click comes from a command loses it: commands are never shared, because they'd run as the person applying your setup. Describe one in `about` if it matters.
- **Try it on another compositor** if you can (a nested session is fine). Note which ones you ran it on.

## 2. Export it

Go to **Settings → Maintenance → Community setups → Export and submit…**, or **Share → Export** with **Include preferences, keybinds and apps** and **Include commands** both **off**. That writes `~/axiom-<name>-<date>-<time>.json`, holding only the look and layout that differs from axiom's defaults. Submitting through the issue form, drag that file in as it is; in a pull request, it's your setup's `config.json`.

Don't edit it by hand, and don't copy your whole `~/.config/axiom/config.json`. The export already leaves out your monitors' names (a bar or dock keeps only its place: `#2`, `@primary`, `*`), wallpapers, accounts and paths.

Export from an up-to-date axiom: CI checks your setup with axiom's current `main` (an older export is converted, as axiom converts it when someone applies it), and a setting that has since become personal (or a command) fails the check.

## 3. Screenshot it

One screenshot of the whole screen, unedited, showing what makes the setup yours: open an edge menu or the overlay if that's the point.
- PNG, JPEG or WebP, 1280 to 7680 px wide, a whole screen (4:3 to 32:9), at most 3 MB.
- Nothing private: notifications, names, email addresses, chat contents.
- `grim screenshot.png` works on every compositor axiom supports.

## 4. Optional: your own palette

If your theme (`Appearance.theme.name` in the export) isn't one of [axiom's themes](https://github.com/axiom-shell/axiom/tree/main/config/themes), bundle it:
- A theme generated from your wallpaper is in `~/.local/state/axiom/themes/<name>.json`.
- A new one starts as a copy of axiom's [`config/themes/template/theme.json`](https://github.com/axiom-shell/axiom/blob/main/config/themes/template/theme.json).

Save it as `theme.json`, fill in its `name` and `author`, and set `Appearance.theme.name` in `config.json` to `community/<id>`. Submitting through an issue does that renaming for you.

## 5. Optional: a wallpaper

One wallpaper (`wallpaper.png`, `.jpg` or `.webp`, at most 10 MB) that you made, or whose license allows sharing. Name its license and source in `setup.json`. People applying your setup choose whether to use it.

## 6. Submit

### Through an issue (no git)

Open [Submit a setup](https://github.com/axiom-shell/community-setups/issues/new?template=01-submit-setup.yml) (**Export and submit…** opens it for you), fill in the fields, and drag in the exported file and your screenshot. Use the form: an issue opened without it isn't checked, and no pull request is made from it. A workflow checks it, opens a pull request for you and comments with the result. Edit the issue to fix anything, and the pull request follows.

### As a pull request

Fork, then add a folder:

```
setups/<id>/            lowercase letters, digits and dashes, at most 40
  setup.json            below
  config.json           your export
  screenshot.png        (or .jpg / .webp)
  theme.json            optional
  wallpaper.jpg         optional
```

`setup.json` (its schema is [`schema/setup.schema.json`](schema/setup.schema.json); editors that read `$schema` autocomplete it):

```json
{
  "$schema": "../../schema/setup.schema.json",
  "title": "Glass Harbor",
  "author": "your-github-handle",
  "description": "Translucent bars over a harbour at night",
  "about": "Optional: the idea, inspiration, tips.",
  "tags": ["dark", "glass", "floating"],
  "tested": ["hyprland", "niri"],
  "fonts": ["Inter"],
  "wallpaper": { "license": "CC-BY-4.0", "source": "https://…", "credit": "Artist" }
}
```

Leave `wallpaper` out without one. `tags` come from a fixed list (see the schema); ask in an issue for a new one.

Then check it locally (Python with Pillow and jsonschema, plus curl and git): `check.sh` fetches the same axiom CI uses (its `edge` build and that commit's checkout) into `.axiom/` the first time.

```sh
scripts/check.sh --fix <id>   # writes config.json's `meta` (its title and description) from setup.json
scripts/check.sh <id>
```

## Updating or removing your setup

Open a pull request changing `setups/<id>/` (only its `author` or a maintainer can), or submit the issue form again with the same **Setup id**. To remove it, open a pull request deleting the folder, or an issue asking for it.

## Review

A maintainer checks that the screenshot matches the config and that nothing in it is private or inappropriate. Setups are accepted for how they look, not judged on taste. Once merged, a setup is in the gallery within minutes.
