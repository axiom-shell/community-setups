<div align="center">

# axiom community setups

**Desktops people built with [axiom](https://github.com/axiom-shell/axiom), ready to apply in one click.**

[Browse](#gallery) · [Apply one](#apply-one) · [Submit yours](#submit-yours) · [What a setup can hold](#what-a-setup-can-hold)

</div>

A setup is the look and layout of an axiom desktop: its bars and their style, overlay pages, edge menus, docks, OSDs, popouts, the lock screen's layout, the theme, font, shape and motion. Each one here was built inside axiom with its own editors and exported with **Share → Export**, so none of them was written by hand.

## Gallery

**[Browse the gallery →](../../tree/catalog#readme)** (rebuilt after every merge, newest first).

## Apply one

- **In axiom**: Settings → Maintenance → **Community setups** lets you search, preview and apply one, or type `/config community <search>` in the launcher. Every file is checked against the catalog's sha256 before it's used.
- **By hand**: download a setup's `config.json`, then go to Settings → Maintenance → Share → **Import…**. If it has a `theme.json`, copy that first to `~/.local/share/axiom/themes/<id>.json`.

Applying a setup first saves your current one as `before-<id>`, so going back is one click under **Saved configs**.

## What a setup can hold

Only the look. Every setting in axiom has a scope (`look`, `personal`, `commands` or `machine`), and a setup holds only `look` settings: CI rejects anything else, and axiom drops anything else when it applies one. CI asks axiom's own binary which is which, so the rules are always axiom's current ones.

| Never in a setup | Why |
|---|---|
| Preferences, keybinds, apps, pinned apps, per-app OSD bars, interface scale and card size | Personal: they stay yours. |
| Widget and button commands, exec binds, the terminal | A command would run as you. |
| Monitor names, wallpapers (apart from the optional one below), accounts, paths | They only mean something on the PC they were set on. A bar, dock, OSD or edge menu keeps its monitor's *place* (`#1` leftmost, `#2`, `@primary`, `*`) and lands on yours in that place. |
| Compositor config mode, lock screen, idle, polkit, greeter | They take something over on your PC, so only their own cards switch them. |
| API keys and passwords | Never shared. A config holding one is refused. |

On top of the look, a setup may bundle:
- **its own palette** (`theme.json`), when it doesn't use one of axiom's themes. It's installed as `community/<id>` and shows up on the Themes page.
- **one wallpaper**, which you only get if you choose to.

**Compositors.** A setup made on Hyprland applies on niri and sway too: what a compositor can't do (blur, some window looks) is skipped there. Its `tested` list says which ones its author actually ran it on.

**Fonts.** A setup lists the fonts it uses. Without one installed, text falls back to another font.

## Submit yours

The [contributing guide](CONTRIBUTING.md) has the details. In short:

1. Build your setup in axiom.
2. Go to **Settings → Maintenance → Community setups → Export and submit…** (or **Share → Export** with both *Include* switches off).
3. Take a screenshot of the whole screen.
4. Submit it either way:
   - **No git needed**: open a [Submit a setup](../../issues/new?template=01-submit-setup.yml) issue (the button opens it), and drag the export and the screenshot in. A pull request is made for you.
   - **As a pull request**: add `setups/<id>/` with `setup.json`, `config.json` and `screenshot.png`.

Every submission is checked with axiom's current `main` (its own binary: schema, themes and config migrations), then reviewed by a maintainer.

## For maintainers

| | |
|---|---|
| `scripts/check.sh [ID…]` | Everything CI checks: each config is loaded by axiom's own binary (`axiom config share`, which migrates, validates and picks what Export would keep, naming what it leaves out; on an axiom without it, `axiom config validate` and a warning that the scope check didn't run), then `scripts/validate.py`'s checks of the folder |
| `scripts/check.sh --upgrade ID…` | Rewrites each setup's `config.json` as that axiom exports it: migrated to its config format and version, without what it no longer shares, defaults left out. Run it after a config schema change |
| `scripts/check.sh --fix ID` | Writes `config.json`'s header (`meta`, or a format-1 file's `_example`) from `setup.json` |
| `scripts/axiom.sh [DIR]` | Fetches the axiom the checks use into `.axiom/`: the `edge` prerelease's binary (checked against its `SHA256SUMS`) and a checkout of the commit it was built from |
| `scripts/build_index.py OUT` | The catalog axiom reads and its gallery page (published as the [`catalog`](../../tree/catalog) branch) |
| `tests/test_templates.py`, `tests/test_validate.py`, `tests/test_issue.py` | The checks' own tests (the issue forms parse and match the parser; the checks on fixture setups; issue bodies to folders) |
| `.github/workflows/` | `validate` (the setups a pull request, merge or submission touches), `publish` (catalog + gallery after a merge), `submission` (issue → pull request, then `validate` on its branch; a `Setup:` issue opened without the form gets a comment pointing at it) |

Without `--axiom DIR` or `$AXIOM_DIR`, `check.sh` runs `scripts/axiom.sh`, so CI and a local run use the same axiom: `main` as of its last `edge` build. With a checkout of your own, the binary is `$AXIOM_BIN`, else `axiom` on `PATH` (build it from that checkout). A setup is checked when it's posted or changed, and never again: axiom converts an older setup's config when someone applies it, as it does any import. After a big schema change, `scripts/check.sh --upgrade` brings the setups up to date in one pull request.

Nothing here knows axiom's config: what a setup may hold, its migrations and validity all come from axiom's binary, and the themes from its checkout. Only the config's header (`format`, `version`, `meta`), `Appearance.theme`'s name and font family, the theme file's shape (`config/themes/template/theme.json`) and the catalog's `format` (axiom's `CommunityCatalog.format`, `scripts/build_index.py`'s `FORMAT`) are read here. A run checks only the setups it touches (`workflow_dispatch` with `all` checks every one).

`main` is protected: changes land through a squashed pull request with the `validate` check passing and a code owner's approval (admins may merge their own). The `catalog` branch can't be deleted. CI force-pushes it.

The catalog is `https://raw.githubusercontent.com/axiom-shell/community-setups/catalog/index.json`. Each setup's files are listed with their `path` (relative to the index), `sha256` and `size`.

## License

The scripts are [MIT](LICENSE), and so are the setups, their palettes and screenshots, unless they say otherwise. A wallpaper carries the license named in its setup's `setup.json`.
