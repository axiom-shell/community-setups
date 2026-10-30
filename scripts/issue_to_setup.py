#!/usr/bin/env python3
"""Turn a "Submit a setup" issue into a setups/<id>/ folder.

    ISSUE_BODY=… ISSUE_AUTHOR=login scripts/issue_to_setup.py

Run by .github/workflows/submission.yml. The body is untrusted: it's only
parsed (JSON, images through Pillow), files are fetched only from GitHub's
own attachment hosts, sizes are capped, and nothing from it reaches a
shell. Prints the setup id; exits 2 with a message for the submitter (inert
Markdown, for the bot's comment) when the issue can't be turned into a
folder, and 3 when something failed that isn't theirs to fix
(scripts/check.sh then reports everything else).
"""

import json
import os
import re
import shutil
import sys
import urllib.request
from urllib.parse import urlparse

from setups import ID_RE, SCREENSHOT_MAX, SETUPS, WALLPAPER_MAX, inert, set_theme_name, with_header, write_json

# Issue form labels (.github/ISSUE_TEMPLATE/01-submit-setup.yml)
FIELDS = {
    "name": "Title",
    "id": "Setup id",
    "description": "Description",
    "about": "About it",
    "tags": "Tags",
    "tested": "Tested on",
    "fonts": "Fonts",
    "config": "config.json",
    "screenshot": "Screenshot",
    "theme": "theme.json",
    "wallpaper": "Wallpaper",
    "license": "Wallpaper license",
    "source": "Wallpaper source",
}
# The form's section after its last field
FORM_END = "Checklist"
NO_RESPONSE = "_No response_"
ATTACHMENT_HOSTS = ("github.com", "user-images.githubusercontent.com", "private-user-images.githubusercontent.com", "objects.githubusercontent.com")
# Where github.com/user-attachments/ redirects: GitHub's own S3 bucket
ATTACHMENT_STORAGE = ("github-production-user-asset-6210df.s3.amazonaws.com",)
DOWNLOAD_MAX = WALLPAPER_MAX + 1


class Refused(Exception):
    pass


def sections(body):
    """{label: text} from the form's `### Label` sections. The form renders
    its fields in order, so each label is looked for after the one before:
    a `### heading` in the submitter's Markdown (About it) stays part of
    its field unless it is exactly the next field's label."""
    text = body.replace("\r\n", "\n")
    heads = []
    pos = 0
    for label in [*FIELDS.values(), FORM_END]:
        match = re.compile(rf"^### {re.escape(label)}[ \t]*$", re.M).search(text, pos)
        if match:
            heads.append((label, match))
            pos = match.end()
    found = {}
    for (label, match), following in zip(heads, heads[1:] + [(None, None)]):
        value = text[match.end():following[1].start() if following[1] else len(text)].strip()
        found[label] = "" if value == NO_RESPONSE else value
    return found


def field(found, key):
    return found.get(FIELDS[key], "").strip()


def listed(text):
    """A multi-select dropdown's answer, or a comma/newline list"""
    return [w.strip() for w in re.split(r"[,\n]", text) if w.strip()]


def attachment_urls(text):
    urls = re.findall(r"""(?:\]\(|src=["'])(https://[^\s)"']+)""", text)
    urls += re.findall(r"(?<![(\"'])\bhttps://github\.com/user-attachments/\S+", text)
    seen = []
    for url in urls:
        url = url.rstrip(").,'\"")
        if url not in seen:
            seen.append(url)
    return seen


def allowed(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ATTACHMENT_HOSTS:
        return False
    return parsed.hostname != "github.com" or parsed.path.startswith("/user-attachments/")


def redirect_allowed(url):
    """GitHub serves an attachment through a redirect to its storage"""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return parsed.scheme == "https" and (host in ATTACHMENT_HOSTS or host in ATTACHMENT_STORAGE or host.endswith(".githubusercontent.com"))


class _Redirects(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only to GitHub's storage, checked before the
    request is made rather than after"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not redirect_allowed(newurl):
            raise Refused("the attachment redirected somewhere unexpected")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_Redirects)


def download(url, what):
    if not allowed(url):
        raise Refused(f"{what}: attach the file to the issue (drag it into the field); links elsewhere aren't fetched")
    request = urllib.request.Request(url, headers={"User-Agent": "axiom-community-setups"})
    try:
        with _opener.open(request, timeout=30) as response:
            data = response.read(DOWNLOAD_MAX + 1)
    except Refused as e:
        raise Refused(f"{what}: {e}")
    except (OSError, ValueError) as e:  # URLError, HTTPError and timeouts are OSErrors
        raise Refused(f"{what}: the attachment couldn't be downloaded ({e}); attach it again")
    if len(data) > DOWNLOAD_MAX:
        raise Refused(f"{what}: too large")
    return data


def json_field(text, what, required):
    """Pasted JSON (fenced or not) or an attached .json file"""
    fenced = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.S)
    # A `render: json` field left empty comes as an empty fence, not _No response_
    if fenced and not fenced.group(1).strip() and not text.replace(fenced.group(0), "").strip():
        text = ""
    if not text:
        if required:
            raise Refused(f"{what} is missing")
        return None
    candidate = fenced.group(1) if fenced else text
    if candidate.lstrip().startswith("{"):
        source = candidate
    else:
        urls = attachment_urls(text)
        if not urls:
            raise Refused(f"{what}: paste the file's contents, or attach the file")
        source = download(urls[0], what).decode("utf-8", "replace")
    try:
        value = json.loads(source)
    except json.JSONDecodeError as e:
        raise Refused(f"{what} isn't valid JSON: {e}")
    if not isinstance(value, dict):
        raise Refused(f"{what} must be a JSON object")
    return value


def image_field(text, what, required, max_bytes):
    if not text:
        if required:
            raise Refused(f"{what} is missing")
        return None
    urls = attachment_urls(text)
    if not urls:
        raise Refused(f"{what}: drag the image into the field")
    data = download(urls[0], what)
    from io import BytesIO

    from PIL import Image

    try:
        with Image.open(BytesIO(data)) as im:
            fmt = im.format
    except Exception:
        raise Refused(f"{what} isn't a readable image")
    ext = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}.get(fmt)
    if not ext:
        raise Refused(f"{what} is {fmt}: use PNG, JPEG or WebP")
    if len(data) > max_bytes:
        # GitHub re-encodes an attached PNG as 32-bit, often larger than the
        # submitter's file: shrink it here, losslessly if that's enough
        try:
            data, ext = shrunk(data, max_bytes), ".webp"
        except Exception:  # too many pixels for Pillow or WebP (16383 px a side)
            raise Refused(f"{what} is too large to convert: attach a smaller one")
    return data, ext


def shrunk(data, max_bytes):
    from io import BytesIO

    from PIL import Image

    with Image.open(BytesIO(data)) as im:
        im = im.convert("RGBA" if im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info else "RGB")
    if im.mode == "RGBA" and im.getchannel("A").getextrema() == (255, 255):
        im = im.convert("RGB")
    for options in ({"lossless": True}, {"quality": 90}):
        out = BytesIO()
        im.save(out, "WEBP", method=6, **options)
        if out.tell() <= max_bytes:
            return out.getvalue()
    # Still too large: kept, and the checks report its size
    return out.getvalue()


def slug(text):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")[:40].strip("-")


def build(body, author):
    found = sections(body)
    title = field(found, "name")
    setup_id = field(found, "id") or slug(title)
    if not ID_RE.match(setup_id) or len(setup_id) > 40:
        raise Refused(f"setup id {setup_id!r}: lowercase letters, digits and dashes, at most 40")

    manifest = {
        "title": title,
        "author": author,
        "description": field(found, "description"),
        "tags": listed(field(found, "tags")),
        "tested": [t.lower() for t in listed(field(found, "tested"))],
        "fonts": listed(field(found, "fonts")),
    }
    if field(found, "about"):
        manifest["about"] = field(found, "about")

    config = json_field(field(found, "config"), "config.json", True)
    theme = json_field(field(found, "theme"), "theme.json", False)
    shot = image_field(field(found, "screenshot"), "Screenshot", True, SCREENSHOT_MAX)
    wall = image_field(field(found, "wallpaper"), "Wallpaper", False, WALLPAPER_MAX)
    if wall:
        manifest["wallpaper"] = {"license": field(found, "license"), "source": field(found, "source")}

    # A bundled theme is named after the setup, whatever the export said
    if theme is not None:
        if not isinstance(config.get("Appearance", {}), dict):
            raise Refused("config.json: `Appearance` must be an object: export it again")
        set_theme_name(config, f"community/{setup_id}")
        theme.setdefault("author", author)
    config = with_header(config, manifest["title"], manifest["description"])

    folder = SETUPS / setup_id
    if folder.exists():
        try:
            existing = json.loads((folder / "setup.json").read_text()).get("author", "")
        except (OSError, ValueError, AttributeError):
            existing = ""
        if not isinstance(existing, str) or existing.lower() != author.lower():
            raise Refused(f"{setup_id!r} is @{existing or 'someone else'}'s setup: pick another id")
        # An update replaces the whole setup
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    write_json(folder / "setup.json", manifest)
    write_json(folder / "config.json", config)
    if theme is not None:
        write_json(folder / "theme.json", theme)
    (folder / ("screenshot" + shot[1])).write_bytes(shot[0])
    if wall:
        (folder / ("wallpaper" + wall[1])).write_bytes(wall[0])
    return setup_id


def main():
    body = os.environ.get("ISSUE_BODY", "")
    author = os.environ.get("ISSUE_AUTHOR", "")
    if not body or not author:
        sys.exit("ISSUE_BODY and ISSUE_AUTHOR are required")
    try:
        print(build(body, author))
    except Refused as e:
        print(inert(e), file=sys.stderr)
        sys.exit(2)
    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(3)


if __name__ == "__main__":
    main()
