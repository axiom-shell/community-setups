#!/usr/bin/env python3
"""The validator's own tests: a good setup passes, and each way of breaking
one fails with its message. Builds the setups in a temp folder and runs
scripts/check.sh on them, so through axiom's binary (fetched into .axiom/
when no --axiom is given).

    tests/test_validate.py [--axiom DIR]

The scope cases need `axiom config share`; on an axiom without it they're
skipped, and the warning that the scope check didn't run is checked
instead.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from setups import Axiom, set_theme_name  # noqa: E402

THEME = {
    "name": "Fixture",
    "author": "someone",
    "variant": "dark",
    "paired": "",
    "colors": {f"base0{c}": "#123456" for c in "0123456789ABCDEF"},
    "semantic": {"accent": "base0D", "background": "#000000"},
}


class Symlink(str):
    """A file written as a symlink to this target"""


def good(axiom):
    return {
        "setup.json": {
            "title": "Fixture",
            "author": "someone",
            "description": "A setup the validator must accept",
            "tags": ["dark", "minimal"],
            "tested": ["hyprland"],
            "fonts": ["Inter"],
        },
        "config.json": {
            "format": 2,
            "version": axiom.config_version,
            "meta": {"title": "Fixture", "description": "A setup the validator must accept"},
            "Appearance": {"theme": {"name": "dracula"}, "font": {"family": "Inter", "size": 14}, "shape": {"radius": 12}},
        },
        "screenshot.png": (1920, 1080),
    }


def format1(files):
    """An export from before format 2, which axiom still converts"""
    files["config.json"] = {
        "_example": files["config.json"]["meta"],
        "version": 75,
        "Appearance": {"theme": "dracula", "font": {"family": "Inter", "size": 14}},
    }


def with_config(change):
    def mutate(files):
        change(files["config.json"])
    return mutate


def with_manifest(change):
    def mutate(files):
        change(files["setup.json"])
    return mutate


def bundled_theme(files, theme=None):
    set_theme_name(files["config.json"], "community/{id}")
    files["theme.json"] = theme or dict(THEME)


def bars(*names):
    return with_config(lambda c: c.__setitem__("Bars", {"items": [{"id": f"b{i}", "screen": {"names": [n]}} for i, n in enumerate(names)]}))


# name: (mutation, expected substring in the output, or None for a pass)
CASES = {
    "good": (lambda f: None, None),
    "good-format-1": (format1, None),
    "good-bundled-theme": (bundled_theme, None),
    "good-bundled-theme-format-1": (lambda f: (format1(f), bundled_theme(f)), None),
    "good-wallpaper": (lambda f: (f.__setitem__("wallpaper.jpg", (2560, 1440)), f["setup.json"].__setitem__("wallpaper", {"license": "CC0-1.0", "source": "own"})), None),
    "invalid-value": (with_config(lambda c: c["Appearance"]["font"].__setitem__("size", "big")), "Appearance.font.size"),
    "newer-version": (with_config(lambda c: c.__setitem__("version", 9999)), "newer than"),
    "no-version": (with_config(lambda c: c.pop("version")), "no `version`"),
    "bool-version": (with_config(lambda c: c.__setitem__("version", True)), "no `version`"),
    "header-mismatch": (with_config(lambda c: c.__setitem__("meta", {"title": "x", "description": "y"})), "`meta` must be"),
    "header-format-1-mismatch": (lambda f: (format1(f), f["config.json"].__setitem__("_example", {"title": "x"})), "`_example` must be"),
    "two-headers": (with_config(lambda c: c.__setitem__("_example", c["meta"])), "`meta` must be"),
    "generated-theme": (with_config(lambda c: set_theme_name(c, "generated/wall")), "generated from a wallpaper"),
    "unknown-theme": (with_config(lambda c: set_theme_name(c, "my-own")), "isn't one axiom ships"),
    "schema-isnt-a-theme": (with_config(lambda c: set_theme_name(c, "theme.schema")), "isn't one axiom ships"),
    "theme-wrong-name": (lambda f: (bundled_theme(f), set_theme_name(f["config.json"], "community/other")), "a bundled theme is named"),
    "theme-unused": (lambda f: f.__setitem__("theme.json", dict(THEME)), "the config's theme isn't"),
    "theme-bad-colour": (lambda f: bundled_theme(f, {**THEME, "colors": {**THEME["colors"], "base08": "red"}}), "colors.base08"),
    "theme-extra-key": (lambda f: bundled_theme(f, {**THEME, "script": "x"}), "unknown key 'script'"),
    "font-unlisted": (with_manifest(lambda m: m.__setitem__("fonts", [])), "list it in `fonts`"),
    "bad-tag": (with_manifest(lambda m: m.__setitem__("tags", ["cool"])), "tags/0"),
    "bad-author": (with_manifest(lambda m: m.__setitem__("author", "not a handle")), "author"),
    "no-screenshot": (lambda f: f.pop("screenshot.png"), "exactly one screenshot"),
    "small-screenshot": (lambda f: f.__setitem__("screenshot.png", (800, 450)), "px wide"),
    "tall-screenshot": (lambda f: f.__setitem__("screenshot.png", (1920, 1920)), "crop to a whole screen"),
    "wallpaper-no-license": (lambda f: f.__setitem__("wallpaper.jpg", (1920, 1080)), "needs `wallpaper.license`"),
    "license-no-wallpaper": (with_manifest(lambda m: m.__setitem__("wallpaper", {"license": "CC0-1.0", "source": "own"})), "no wallpaper file"),
    "stray-file": (lambda f: f.__setitem__("run.sh", "echo hi"), "unexpected file 'run.sh'"),
    "extra-folder": (lambda f: f.__setitem__("extra", "x"), "unexpected file 'extra'"),
    "symlink": (lambda f: f.__setitem__("theme.json", Symlink("/etc/hostname")), "a symlink"),
    "Bad_Id": (lambda f: None, "folder name"),
}

# What axiom's pick decides (`axiom config share`)
SCOPE_CASES = {
    "good-monitor-places": (bars("@primary", "#2", "*"), None),
    "good-default-personal": (with_config(lambda c: c.__setitem__("Apps", {"pinned": []})), None),
    "personal-apps": (with_config(lambda c: c.__setitem__("Apps", {"pinned": ["firefox"]})), "personal"),
    "personal-osd-app-bar": (with_config(lambda c: c.__setitem__("OSD", {"items": [{"id": "o", "bars": [{"type": "master"}, {"type": "app", "icon": "web"}]}]})), "personal"),
    "commands-terminal": (with_config(lambda c: c.__setitem__("Apps", {"terminal": "foot"})), "runs a command"),
    "machine-monitor": (bars("DP-1"), "belongs to the PC"),
    "takeover": (with_config(lambda c: c.__setitem__("Compositor", {"mode": "managed"})), "takes something over"),
}


def write_setup(folder, files):
    folder.mkdir(parents=True)
    for name, value in files.items():
        path = folder / name
        if isinstance(value, Symlink):
            path.symlink_to(value)
        elif isinstance(value, tuple):
            Image.new("RGB", value, (40, 44, 52)).save(path)
        elif isinstance(value, dict):
            text = json.dumps(value).replace("{id}", folder.name)
            path.write_text(text)
        else:
            path.write_text(value)


def check(args, env):
    run = subprocess.run([str(ROOT / "scripts" / "check.sh"), *args], capture_output=True, text=True, env=env)
    return run.returncode, run.stdout + run.stderr


def main():
    axiom_arg = sys.argv[sys.argv.index("--axiom") + 1] if "--axiom" in sys.argv else None
    if not axiom_arg and not os.environ.get("AXIOM_DIR"):
        subprocess.run([str(ROOT / "scripts" / "axiom.sh")], check=True)
    axiom = Axiom.locate(axiom_arg)
    if not axiom.binary:
        sys.exit("No axiom binary: run scripts/axiom.sh, or set AXIOM_BIN")
    cases = dict(CASES)
    if axiom.can_share:
        cases.update(SCOPE_CASES)
    else:
        print(f"skipping {len(SCOPE_CASES)} scope cases: {axiom.version} has no `axiom config share`")
        cases["scope-check-not-run"] = (lambda f: None, "not scope-checked")
    tmp = Path(tempfile.mkdtemp())
    env = {**os.environ, "GITHUB_ACTIONS": "", "GITHUB_STEP_SUMMARY": ""}
    base = ["--axiom", str(axiom.path), "--bin", axiom.binary, "--root", str(tmp)]
    try:
        for name, (mutate, _) in cases.items():
            files = good(axiom)
            mutate(files)
            write_setup(tmp / name, files)
        failures = 0
        for name, (_, expected) in cases.items():
            code, output = check([*base, name], env)
            ok = code == 0 if expected is None else (code == 1 and expected in output)
            if name == "scope-check-not-run":
                ok = code == 0 and expected in output
            failures += not ok
            print(f"{'ok  ' if ok else 'FAIL'} {name}")
            if not ok:
                print("     expected " + ("a pass" if expected is None else f"a failure with {expected!r}"))
                print("     " + output.strip().replace("\n", "\n     "))

        # --fix writes the header from setup.json, in the config's format
        extra = []
        for name, mutate in (("fix", lambda f: None), ("fix-format-1", format1)):
            files = good(axiom)
            mutate(files)
            files["setup.json"]["title"] = "Renamed"
            write_setup(tmp / name, files)
            code, output = check([*base, "--fix", name], env)
            config = json.loads((tmp / name / "config.json").read_text())
            key = "meta" if name == "fix" else "_example"
            ok = code == 0 and config[key]["title"] == "Renamed" and ({"meta", "_example"} - {key}).isdisjoint(config)
            extra.append((name, ok, output))

        # --upgrade rewrites a setup as this axiom exports it: what it can't
        # share is left out, and the setup passes
        if axiom.can_share:
            files = good(axiom)
            format1(files)
            files["config.json"]["Apps"] = {"terminal": "foot"}
            write_setup(tmp / "upgrade", files)
            code, output = check([*base, "--upgrade", "upgrade"], env)
            config = json.loads((tmp / "upgrade" / "config.json").read_text())
            ok = code == 0 and config.get("format") == 2 and "Apps" not in config and config["meta"]["title"] == "Fixture"
            extra.append(("upgrade", ok, output))
        for name, ok, output in extra:
            failures += not ok
            print(f"{'ok  ' if ok else 'FAIL'} {name}")
            if not ok:
                print("     " + output.strip().replace("\n", "\n     "))
        total = len(cases) + len(extra)
        print(f"\n{total - failures}/{total} cases ok")
        sys.exit(1 if failures else 0)
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
