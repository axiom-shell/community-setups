#!/usr/bin/env python3
"""Build the catalog axiom reads, with its gallery page.

    scripts/build_index.py OUT

OUT gets index.json plus each setup's files under setups/<id>/ (and a
640px thumb.webp), so the catalog is one consistent snapshot: CI
force-pushes it as the `catalog` branch, and axiom fetches
<catalog>/index.json, then files by their `path` relative to it, checking
each one's sha256. Its README.md is the gallery GitHub shows on that
branch (main is protected, so nothing is committed there).
Run it after scripts/check.sh passes: it doesn't check.
"""

import argparse
import html
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from setups import ROOT, all_setups, images, sha256, symlinks, theme_name

REPO = "axiom-shell/community-setups"
CATALOG_URL = f"https://raw.githubusercontent.com/{REPO}/catalog/"
FORMAT = 1
THUMB_WIDTH = 640
GALLERY_COLUMNS = 3


def updated(folder):
    """When the setup last changed, from git (now, outside a clone)"""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", str(folder)],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        out = ""
    return out or datetime.now(timezone.utc).isoformat(timespec="seconds")


def entry(out, rel):
    path = out / rel
    return {"path": rel, "sha256": sha256(path), "size": path.stat().st_size}


def image(folder, stem):
    found = images(folder, stem)
    return found[0] if found else None


def thumbnail(source, dest):
    from PIL import Image

    with Image.open(source) as im:
        im = im.convert("RGB")
        height = round(im.height * THUMB_WIDTH / im.width)
        im.resize((THUMB_WIDTH, height), Image.LANCZOS).save(dest, "WEBP", quality=82, method=6)


def build(out):
    out.mkdir(parents=True, exist_ok=True)
    setups = []
    for folder in all_setups():
        setup_id = folder.name
        # check.sh refuses them; this runs with write access, so never follow one
        if symlinks(folder):
            sys.exit(f"{folder} holds a symlink: run scripts/check.sh")
        manifest = json.loads((folder / "setup.json").read_text())
        config = json.loads((folder / "config.json").read_text())
        dest = out / "setups" / setup_id
        dest.mkdir(parents=True, exist_ok=True)
        base = f"setups/{setup_id}/"

        files = {}
        shutil.copy2(folder / "config.json", dest / "config.json")
        files["config"] = entry(out, base + "config.json")
        if (folder / "theme.json").is_file():
            shutil.copy2(folder / "theme.json", dest / "theme.json")
            files["theme"] = entry(out, base + "theme.json")
        shot = image(folder, "screenshot")
        shutil.copy2(shot, dest / shot.name)
        files["screenshot"] = entry(out, base + shot.name)
        thumbnail(shot, dest / "thumb.webp")
        files["thumb"] = entry(out, base + "thumb.webp")
        wall = image(folder, "wallpaper")
        if wall:
            shutil.copy2(wall, dest / wall.name)
            files["wallpaper"] = entry(out, base + wall.name)

        theme = theme_name(config)
        setups.append({
            "id": setup_id,
            "title": manifest["title"],
            "author": manifest["author"],
            "description": manifest["description"],
            "about": manifest.get("about", ""),
            "tags": manifest["tags"],
            "tested": manifest["tested"],
            "fonts": manifest["fonts"],
            "theme": theme if isinstance(theme, str) else "",
            "configVersion": config["version"],
            "wallpaper": manifest.get("wallpaper"),
            "updated": updated(folder),
            "page": f"https://github.com/{REPO}/tree/main/setups/{setup_id}",
            "files": files,
        })

    setups.sort(key=lambda s: s["updated"], reverse=True)
    index = {
        "format": FORMAT,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "setups": setups,
    }
    (out / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    return index


def cell_text(text):
    """A submitter's text as it may go in a table cell's HTML: escaped, on
    one line, with no `|` to end the cell"""
    return html.escape(" ".join(text.split())).replace("|", "&#124;")


def gallery(index):
    """The README table: newest first, linking each thumbnail to its folder"""
    setups = index["setups"]
    if not setups:
        return f"_No setups yet. [Be the first](https://github.com/{REPO}/blob/main/CONTRIBUTING.md)._"
    rows = []
    for i in range(0, len(setups), GALLERY_COLUMNS):
        chunk = setups[i:i + GALLERY_COLUMNS]
        cells = []
        for s in chunk:
            thumb = CATALOG_URL + s["files"]["thumb"]["path"]
            title, description = cell_text(s["title"]), cell_text(s["description"])
            page = f"https://github.com/{REPO}/tree/main/setups/{s['id']}"
            cells.append(
                f'<a href="{page}"><img src="{thumb}" alt="{title}"></a><br>'
                f'<b>{title}</b> · <a href="https://github.com/{s["author"]}">@{s["author"]}</a><br>'
                f'<sub>{description}</sub>'
            )
        cells += [""] * (GALLERY_COLUMNS - len(cells))
        rows.append("| " + " | ".join(cells) + " |")
    # The first row is the table's header, so there's no empty one
    separator = "|" + "|".join([" :---: "] * GALLERY_COLUMNS) + "|"
    return "\n".join([rows[0], separator] + rows[1:])


def gallery_page(index):
    """The catalog branch's README: the gallery, newest first"""
    return f"""# axiom community setups: gallery

Every setup in [{REPO}](https://github.com/{REPO}), newest first. Apply one from axiom (Settings → Maintenance → Community setups), or see [how to submit yours](https://github.com/{REPO}/blob/main/CONTRIBUTING.md).

This branch is the catalog axiom reads, rebuilt by CI after every merge: don't edit it.

{gallery(index)}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out")
    args = parser.parse_args()
    index = build(Path(args.out))
    (Path(args.out) / "README.md").write_text(gallery_page(index))
    print(f"{len(index['setups'])} setups in {args.out}/index.json")


if __name__ == "__main__":
    main()
