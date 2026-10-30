"""Shared checks for community setups.

What a config may hold is axiom's to say: its binary loads each one
(`axiom config share`, or `config validate` on an axiom without it), which
migrates any version, validates it, and answers what Export would keep and
what it leaves out (`dropped`, by scope). So what this repo accepts is
exactly the part axiom would apply from it, and no config section, scope or
schema annotation is written down here. Only the config's header (`meta`,
or format 1's `_example`) and `Appearance.theme` are read, to match them
with setup.json and theme.json.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETUPS = ROOT / "setups"
MANIFEST_SCHEMA = ROOT / "schema" / "setup.schema.json"

ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
BASE_RE = re.compile(r"^base0[0-9A-F]$")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")

# Limits, in bytes and pixels
SCREENSHOT_MAX = 3 * 1024 * 1024
WALLPAPER_MAX = 10 * 1024 * 1024
THEME_MAX = 16 * 1024
CONFIG_MAX = 256 * 1024
SCREENSHOT_MIN_WIDTH = 1280
SCREENSHOT_MAX_WIDTH = 7680
ASPECT_MIN, ASPECT_MAX = 1.3, 3.6  # 4:3 up to 32:9
# A config's format: 2 holds `format` and `meta`; format 1 (versions up to
# 75) held `_example` and no `format`, and axiom still converts it
FORMAT = 2


class Report:
    """Errors fail a setup; warnings are shown but pass."""

    def __init__(self, setup_id):
        self.id = setup_id
        self.errors = []
        self.warnings = []

    def error(self, message, file="setup.json"):
        self.errors.append((file, message))

    def warn(self, message, file="setup.json"):
        self.warnings.append((file, message))

    @property
    def ok(self):
        return not self.errors


# ---------------------------------------------------------------- axiom ---


class AxiomFailed(Exception):
    """axiom itself failed (not the setup): no answer, or one it can't give"""


class Axiom:
    """axiom's checkout (its themes, and the schema --tree builds) and its
    binary (scripts/axiom.sh fetches both, the binary as `.edge/axiom`)."""

    def __init__(self, path, binary=None):
        self.path = Path(path).resolve()
        themes = self.path / "config" / "themes"
        template = themes / "template" / "theme.json"
        if not template.is_file():
            raise SystemExit(f"{template} not found: point --axiom (or AXIOM_DIR) at a checkout of axiom")
        self.themes = sorted(p.stem for p in themes.glob("*.json") if not p.name.endswith(".schema.json"))
        self.theme_template = json.loads(template.read_text())
        self.binary = binary
        self.can_share = False
        self.version = None
        self.config_version = None
        if binary:
            self.can_share = "share" in self._run("config", "--help").stdout.split("commands:", 1)[-1]
            self.version = (self._run("version").stdout.strip().splitlines() or ["axiom"])[0]
            try:
                schema = json.loads(self._run("schema", "build", "--tree", str(self.path), "-o", "-").stdout)
                self.config_version = schema["properties"]["version"]["default"]
            except (ValueError, KeyError, TypeError):
                raise AxiomFailed("axiom schema build gave no schema")

    @staticmethod
    def locate(arg=None, binary=None):
        for candidate in (arg, os.environ.get("AXIOM_DIR"), ROOT / ".axiom"):
            if candidate and Path(candidate).is_dir():
                path = Path(candidate)
                for found in (binary, os.environ.get("AXIOM_BIN"), path / ".edge" / "axiom", shutil.which("axiom")):
                    if found and Path(found).is_file() and os.access(found, os.X_OK):
                        return Axiom(path, str(found))
                return Axiom(path)
        raise SystemExit(
            "No axiom checkout: run scripts/check.sh (it fetches one), pass --axiom DIR, or set AXIOM_DIR"
        )

    def _run(self, *args):
        try:
            return subprocess.run([self.binary, *args], capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise AxiomFailed(f"{self.binary} {args[0]}: {e}")

    def load(self, config_file):
        """The config as axiom loads it: {valid: true, migrated, changes,
        removed, scoped, and with `config share` config, dropped, secrets},
        or {valid: false, issues: [{path, message}]}. AxiomFailed when axiom
        gives neither."""
        command = ["config", "share", "--places"] if self.can_share else ["config", "validate"]
        run = self._run(*command, "--json", "--tree", str(self.path), str(config_file))
        try:
            answer = json.loads(run.stdout)
        except ValueError:
            answer = None
        if not isinstance(answer, dict):
            raise AxiomFailed(f"axiom {command[1]} exited {run.returncode} without an answer: {run.stderr.strip()[-500:]}")
        error = answer.get("error")
        if run.returncode == 1 and isinstance(error, dict) and error.get("kind") == "invalid_config":
            return {"valid": False, "issues": error.get("issues") or [{"path": "", "message": error.get("message", "")}]}
        if run.returncode != 0 or answer.get("valid") is not True:
            raise AxiomFailed(f"axiom {command[1]} exited {run.returncode}: {(error or {}).get('message') or run.stderr.strip()[-500:]}")
        return {**answer, "scoped": self.can_share}


# Why axiom leaves a value out of a shared file, by its scope (x-scope, or
# "takeover" for x-takeover). A scope axiom adds later gets the fallback.
SCOPE_MESSAGES = {
    "takeover": "takes something over on the PC (compositor mode, locker, idle, polkit, greeter) and is never shared",
    "personal": "personal (keybinds, apps, preferences): export again with personal settings off",
    "commands": "runs a command as you: export again with commands off",
    "machine": "belongs to the PC it was made on (monitor names, wallpapers, accounts, paths), never shared",
}


def scope_message(scope):
    return SCOPE_MESSAGES.get(scope, f"{scope!r} scope, which a shared setup never holds: export it again")


def header_key(config):
    """Where a config's title and description are: format 2's `meta`, or
    format 1's `_example`"""
    return "meta" if config.get("format") == FORMAT else "_example"


def with_header(config, title, description):
    """The config with its header set (first, as axiom writes it), the
    other's removed"""
    key = header_key(config)
    head = {k: config[k] for k in ("format", "version") if k in config}
    rest = {k: v for k, v in config.items() if k not in ("format", "version", "meta", "_example")}
    return {**head, key: {"title": title, "description": description}, **rest}


def theme_name(config):
    """Appearance.theme's name: format 2's `{name}`, format 1's string"""
    appearance = config.get("Appearance")
    theme = appearance.get("theme") if isinstance(appearance, dict) else None
    if isinstance(theme, dict):
        theme = theme.get("name")
    return theme


def set_theme_name(config, name):
    appearance = config.get("Appearance")
    if not isinstance(appearance, dict):
        appearance = config["Appearance"] = {}
    if config.get("format") == FORMAT:
        theme = appearance.get("theme")
        appearance["theme"] = {**(theme if isinstance(theme, dict) else {}), "name": name}
    else:
        appearance["theme"] = name


def inert(text):
    """Text from a submission made inert Markdown for a bot's comment: no
    @mention, no HTML, no image or link (the comment reads the same)"""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("@", "@\u200b").replace("](", "]\u200b(").replace("://", ":\u200b//"))


# ---------------------------------------------------------------- files ---


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path, report, file):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        report.error(f"not valid JSON: {e}", file)
        return None


def write_json(path, value):
    """Atomically, 2-space indented, as axiom writes its own files"""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)


def symlinks(folder):
    """The symlinks in a setup's folder (itself included), relative to it"""
    found = ["."] if folder.is_symlink() else []
    return found + sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_symlink())


def images(folder, stem):
    """The folder's `stem`.png/.jpg/.jpeg/.webp files"""
    return [p for p in folder.iterdir() if p.is_file() and p.stem == stem and p.suffix.lower() in IMAGE_EXTS]


def check_image(path, folder, report, max_bytes, screenshot=False):
    from PIL import Image

    name = path.relative_to(folder).as_posix()
    size = path.stat().st_size
    if size > max_bytes:
        report.error(f"{size // 1024} KB, over the {max_bytes // 1024} KB limit", name)
    try:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            width, height = im.size
            fmt = im.format
    except Exception as e:  # Pillow raises many kinds
        report.error(f"not a readable image: {e}", name)
        return
    if fmt not in ("PNG", "JPEG", "WEBP"):
        report.error(f"{fmt} image: use PNG, JPEG or WebP", name)
    if screenshot:
        if not SCREENSHOT_MIN_WIDTH <= width <= SCREENSHOT_MAX_WIDTH:
            report.error(f"{width}px wide: screenshots are {SCREENSHOT_MIN_WIDTH}–{SCREENSHOT_MAX_WIDTH}px", name)
        if not ASPECT_MIN <= width / height <= ASPECT_MAX:
            report.error(f"{width}×{height}: crop to a whole screen, 4:3 to 32:9", name)


# ------------------------------------------------------------- checking ---


def check_manifest(manifest, report):
    import jsonschema

    schema = json.loads(MANIFEST_SCHEMA.read_text())
    validator = jsonschema.Draft202012Validator(schema)
    for e in sorted(validator.iter_errors(manifest), key=lambda e: list(e.path)):
        where = "/".join(str(p) for p in e.path) or "(root)"
        report.error(f"{where}: {e.message}")


def check_theme(theme, setup_id, manifest, axiom, report):
    template = axiom.theme_template
    allowed = set(template)
    for key in theme:
        if key not in allowed:
            report.error(f"unknown key {key!r} (a theme has {', '.join(sorted(allowed))})", "theme.json")
    if not isinstance(theme.get("name"), str) or not theme["name"].strip():
        report.error("`name` is empty: it's what the Themes page shows", "theme.json")
    if theme.get("variant") not in ("dark", "light"):
        report.error("`variant` must be dark or light", "theme.json")
    paired = theme.get("paired", "")
    if paired and paired not in axiom.themes:
        report.error(f"`paired` {paired!r} isn't a theme axiom ships (leave it empty)", "theme.json")
    if theme.get("author") and theme["author"] != manifest.get("author"):
        report.warn("`author` differs from setup.json's", "theme.json")
    colors = theme.get("colors")
    if not isinstance(colors, dict):
        report.error("`colors` is missing", "theme.json")
        return
    for key in template["colors"]:
        if not HEX_RE.match(str(colors.get(key, ""))):
            report.error(f"colors.{key} must be #rrggbb", "theme.json")
    for key in colors:
        if key not in template["colors"]:
            report.error(f"unknown colour {key!r}", "theme.json")
    semantic = theme.get("semantic", {})
    if not isinstance(semantic, dict):
        report.error("`semantic` must be an object", "theme.json")
        return
    for key, value in semantic.items():
        if key not in template["semantic"]:
            report.error(f"unknown semantic colour {key!r}", "theme.json")
        elif not (BASE_RE.match(str(value)) or HEX_RE.match(str(value))):
            report.error(f"semantic.{key} must be a base00–base0F name or #rrggbb", "theme.json")


def check_setup(folder, axiom, fix=False, loaded=None):
    """All the checks for one setups/<id>/ folder. `loaded`: Axiom.load's
    answer for its config; without it the config is neither validated nor
    scope-checked."""
    folder = Path(folder)
    setup_id = folder.name
    report = Report(setup_id)

    if not ID_RE.match(setup_id) or len(setup_id) > 40:
        report.error(f"folder name {setup_id!r}: lowercase letters, digits and dashes, at most 40", ".")

    # A symlink would make the published catalog copy whatever it points
    # at, on the runner that builds it
    links = symlinks(folder)
    for name in links:
        report.error("a symlink: add the file itself", name)
    if links:
        return report

    allowed = {"setup.json", "config.json", "theme.json"}
    for entry in folder.iterdir():
        if (entry.name in allowed and entry.is_file()) or (entry.is_file() and entry.stem in ("screenshot", "wallpaper") and entry.suffix.lower() in IMAGE_EXTS):
            continue
        report.error(f"unexpected file {entry.name!r}", entry.name)

    manifest_file = folder / "setup.json"
    if not manifest_file.is_file():
        report.error("missing setup.json")
        return report
    manifest = load_json(manifest_file, report, "setup.json")
    if not isinstance(manifest, dict):
        return report
    check_manifest(manifest, report)

    # Images
    shots = images(folder, "screenshot")
    if len(shots) != 1:
        report.error("needs exactly one screenshot.png, .jpg or .webp", ".")
    else:
        check_image(shots[0], folder, report, SCREENSHOT_MAX, screenshot=True)
    walls = images(folder, "wallpaper")
    if len(walls) > 1:
        report.error("at most one wallpaper file", ".")
    for wall in walls:
        check_image(wall, folder, report, WALLPAPER_MAX)
    if walls and not manifest.get("wallpaper"):
        report.error("a wallpaper needs `wallpaper.license` and `wallpaper.source` in setup.json")
    if manifest.get("wallpaper") and not walls:
        report.error("`wallpaper` is set but there's no wallpaper file")

    # Config
    config_file = folder / "config.json"
    if not config_file.is_file():
        report.error("missing config.json (Settings → Maintenance → Share → Export)", "config.json")
        return report
    if config_file.stat().st_size > CONFIG_MAX:
        report.error(f"over {CONFIG_MAX // 1024} KB: export it again, it holds only what differs from the defaults", "config.json")
    config = load_json(config_file, report, "config.json")
    if not isinstance(config, dict):
        return report
    # bool is an int in Python, but not a version to axiom
    if type(config.get("version")) is not int:
        report.error("no `version`: export it from axiom rather than copying config.json", "config.json")

    if loaded is not None:
        if not loaded["valid"]:
            for issue in loaded["issues"]:
                report.error(f"axiom refuses it: {issue['path'] or '(file)'}: {issue['message']}", "config.json")
            return report
        for path in loaded.get("secrets") or []:
            report.error(f"{path}: a secret (an API key or password): never share one, export again", "config.json")
        for item in loaded.get("dropped") or []:
            if item["path"].split(".")[0] in ("meta", "_example"):
                continue  # the header, which Export writes itself
            report.error(f"{item['path']}: {scope_message(item['scope'])}", "config.json")
        for path in loaded["removed"] or []:
            if path not in ("_example", "meta"):
                report.warn(f"{path}: unknown to axiom (after migrating), so it's ignored", "config.json")
        if not loaded["scoped"]:
            report.warn("not scope-checked: this axiom has no `axiom config share` yet, so a maintainer checks it holds only the look (axiom applies only the look either way)", "config.json")

    # The header: setup.json is the source of truth
    key = header_key(config)
    header = {"title": manifest.get("title", ""), "description": manifest.get("description", "")}
    if config.get(key) != header or ("meta" in config and "_example" in config):
        if fix:
            config = with_header(config, header["title"], header["description"])
            write_json(config_file, config)
        else:
            report.error(f"`{key}` must be setup.json's title and description, and nothing else (run scripts/check.sh --fix)", "config.json")

    # Theme
    name = theme_name(config)
    theme_file = folder / "theme.json"
    own = f"community/{setup_id}"
    if isinstance(name, str) and name.startswith("generated/"):
        report.error(f"the theme {name!r} was generated from a wallpaper on your PC: copy it to theme.json and set the theme to {own!r}", "config.json")
    elif isinstance(name, str) and name.startswith("community/"):
        if name != own:
            report.error(f"the theme {name!r}: a bundled theme is named {own!r}", "config.json")
        if not theme_file.is_file():
            report.error(f"the theme is {own!r} but there's no theme.json", "config.json")
    elif name is not None and name not in axiom.themes:
        report.error(f"the theme {name!r} isn't one axiom ships: bundle it as theme.json and set the theme to {own!r}", "config.json")
    if theme_file.is_file():
        if name != own:
            report.error(f"theme.json is bundled but the config's theme isn't {own!r}", "theme.json")
        if theme_file.stat().st_size > THEME_MAX:
            report.error("too large for a theme", "theme.json")
        theme = load_json(theme_file, report, "theme.json")
        if isinstance(theme, dict):
            check_theme(theme, setup_id, manifest, axiom, report)
        else:
            report.error("must be a JSON object", "theme.json")

    # Fonts
    appearance = config.get("Appearance") if isinstance(config.get("Appearance"), dict) else {}
    family = appearance.get("font").get("family") if isinstance(appearance.get("font"), dict) else None
    if family and family not in manifest.get("fonts", []):
        report.error(f"the config uses the font {family!r}: list it in `fonts`")

    return report


def all_setups():
    if not SETUPS.is_dir():
        return []
    return sorted(p for p in SETUPS.iterdir() if p.is_dir())
