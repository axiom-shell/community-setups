#!/usr/bin/env python3
"""scripts/issue_to_setup.py on issue bodies as GitHub renders the form,
with downloads stubbed (no network)."""

import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import issue_to_setup as its  # noqa: E402
from setups import SCREENSHOT_MAX  # noqa: E402


def png(size=(1920, 1080)):
    buf = io.BytesIO()
    Image.new("RGB", size).save(buf, "PNG")
    return buf.getvalue()


def body(**over):
    values = {
        "Title": "Glass Harbor",
        "Setup id": "_No response_",
        "Description": "Translucent bars over a harbour at night",
        "About it": "_No response_",
        "Tags": "dark, glass",
        "Tested on": "Hyprland, niri",
        "Fonts": "Inter",
        "Exported config": '```json\n{"format": 2, "version": 84, "meta": {"title": "x", "description": ""}, "Appearance": {"theme": {"name": "dracula"}, "font": {"family": "Inter"}}}\n```',
        "Screenshot": "![shot](https://github.com/user-attachments/assets/1111-2222)",
        "Theme": "_No response_",
        "Wallpaper": "_No response_",
        "Wallpaper license": "_No response_",
        "Wallpaper source": "_No response_",
    }
    values.update(over)
    values["Checklist"] = "- [X] I exported it with **Share → Export**, keybinds, apps and commands off."
    return "\n\n".join(f"### {k}\n\n{v}" for k, v in values.items())


def run(case, text, expect_error=None, check=None):
    try:
        setup_id = its.build(text, "someone")
    except its.Refused as e:
        ok = expect_error is not None and expect_error in str(e)
        print(f"{'ok  ' if ok else 'FAIL'} {case}" + ("" if ok else f": refused: {e}"))
        return ok
    if expect_error is not None:
        print(f"FAIL {case}: expected a refusal with {expect_error!r}")
        return False
    ok = check(its.SETUPS / setup_id) if check else True
    print(f"{'ok  ' if ok else 'FAIL'} {case}")
    return ok


def main():
    tmp = Path(tempfile.mkdtemp())
    its.SETUPS = tmp
    image = png()
    exported = json.dumps({"format": 2, "version": 84, "meta": {"title": "x", "description": ""}, "Appearance": {"theme": {"name": "nord"}, "font": {"family": "Iosevka"}}}).encode()

    def download(url, what):
        if not its.allowed(url):
            raise its.Refused(f"{what}: links elsewhere aren't fetched")
        return exported if url.endswith(".json") else image
    its.download = download
    try:
        results = [
            run("pasted config", body(), check=lambda f: (
                json.loads((f / "setup.json").read_text())["tested"] == ["hyprland", "niri"]
                and list(json.loads((f / "config.json").read_text()))[:3] == ["format", "version", "meta"]
                and json.loads((f / "config.json").read_text())["meta"] == {"title": "Glass Harbor", "description": "Translucent bars over a harbour at night"}
                and (f / "screenshot.png").is_file() and f.name == "glass-harbor")),
            run("bundled theme renames it", body(**{"Setup id": "harbor", "Theme": '{"name": "Harbor", "colors": {}}'}), check=lambda f: (
                json.loads((f / "config.json").read_text())["Appearance"]["theme"] == {"name": "community/harbor"})),
            run("format 1 keeps its header and theme string", body(**{"Setup id": "old", "Theme": '{"name": "Old", "colors": {}}', "Exported config": '{"_example": {"title": "x"}, "version": 74, "Appearance": {"theme": "nord"}}'}), check=lambda f: (
                json.loads((f / "config.json").read_text()) == {"version": 74, "_example": {"title": "Glass Harbor", "description": "Translucent bars over a harbour at night"}, "Appearance": {"theme": "community/old"}})),
            run("a bad Appearance is refused, not a traceback", body(**{"Setup id": "bad-shape", "Theme": '{"name": "X"}', "Exported config": '{"format": 2, "version": 84, "Appearance": []}'}), expect_error="`Appearance` must be an object"),
            run("headings in about", body(**{"About it": "Intro\n\n### Tips\n\nUse the overlay"}), check=lambda f: (
                json.loads((f / "setup.json").read_text())["about"] == "Intro\n\n### Tips\n\nUse the overlay"
                and json.loads((f / "setup.json").read_text())["tags"] == ["dark", "glass"])),
            run("empty theme field", body(**{"Theme": "```json\n\n```"}), check=lambda f: (
                not (f / "theme.json").exists()
                and json.loads((f / "config.json").read_text())["Appearance"]["theme"] == {"name": "dracula"})),
            run("empty config field", body(**{"Exported config": "```json\n\n```"}), expect_error="Exported config is missing"),
            run("checklist isn't a field", body(), check=lambda f: "Checklist" not in (f / "setup.json").read_text()),
            # A file dragged into a textarea, as GitHub writes it in the body
            run("attached config", body(**{"Setup id": "attached", "Exported config": "[axiom-harbor-2026-10-30-101500.json](https://github.com/user-attachments/files/33891945/axiom-harbor-2026-10-30-101500.json)"}), check=lambda f: (
                json.loads((f / "config.json").read_text())["Appearance"]["theme"] == {"name": "nord"}
                and json.loads((f / "setup.json").read_text())["fonts"] == ["Iosevka", "Inter"])),
            run("attached theme", body(**{"Setup id": "attached-theme", "Theme": "[wallpaper-dark.json](https://github.com/user-attachments/files/1/wallpaper-dark.json)"}), check=lambda f: (
                (f / "theme.json").is_file()
                and json.loads((f / "config.json").read_text())["Appearance"]["theme"] == {"name": "community/attached-theme"})),
            run("submitted while still uploading", body(**{"Exported config": "[Uploading axiom-harbor.json…]()"}), expect_error="paste the file's contents, or attach the file"),
            run("an attached image isn't a config", body(**{"Exported config": '<img width="1920" alt="x" src="https://github.com/user-attachments/assets/1111" />'}), expect_error="isn't valid JSON"),
            run("fonts optional, the export's added", body(**{"Setup id": "fonts", "Fonts": "_No response_"}), check=lambda f: (
                json.loads((f / "setup.json").read_text())["fonts"] == ["Inter"])),
            run("an export's font already listed isn't repeated", body(**{"Setup id": "fonts-listed", "Fonts": "Inter, Iosevka"}), check=lambda f: (
                json.loads((f / "setup.json").read_text())["fonts"] == ["Inter", "Iosevka"])),
            run("no screenshot", body(Screenshot="_No response_"), expect_error="Screenshot is missing"),
            run("foreign link", body(Screenshot="![x](https://evil.example/x.png)"), expect_error="links elsewhere"),
            run("bad id", body(**{"Setup id": "Not OK"}), expect_error="setup id"),
            run("bad json", body(**{"Exported config": "{nope"}), expect_error="isn't valid JSON"),
        ]
        its.SCREENSHOT_MAX = len(image) - 1
        results.append(run("an oversized screenshot becomes lossless WebP", body(**{"Setup id": "large"}), check=lambda f: (
            not (f / "screenshot.png").exists()
            and (f / "screenshot.webp").stat().st_size <= its.SCREENSHOT_MAX
            and Image.open(f / "screenshot.webp").convert("RGB").tobytes() == Image.open(io.BytesIO(image)).convert("RGB").tobytes())))
        its.SCREENSHOT_MAX = SCREENSHOT_MAX
        (tmp / "taken").mkdir()
        (tmp / "taken" / "setup.json").write_text('{"author": "other"}')
        results.append(run("someone else's id", body(**{"Setup id": "taken"}), expect_error="@other's setup"))
        (tmp / "mine").mkdir()
        (tmp / "mine" / "setup.json").write_text('{"author": "someone"}')
        (tmp / "mine" / "wallpaper.png").write_bytes(image)
        results.append(run("an update replaces the folder", body(**{"Setup id": "mine"}), check=lambda f: not (f / "wallpaper.png").exists() and (f / "screenshot.png").is_file()))
        redirects = [its.redirect_allowed(u) for u in ("https://objects.githubusercontent.com/x", "https://github-production-user-asset-6210df.s3.amazonaws.com/x", "https://evil.s3.amazonaws.com/x", "http://objects.githubusercontent.com/x", "http://github-production-user-asset-6210df.s3.amazonaws.com/x")]
        ok = redirects == [True, True, False, False, False]
        print(f"{'ok  ' if ok else 'FAIL'} redirects only to GitHub's storage, over https")
        results.append(ok)
    finally:
        shutil.rmtree(tmp)
    print(f"\n{sum(results)}/{len(results)} cases ok")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
