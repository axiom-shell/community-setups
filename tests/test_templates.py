#!/usr/bin/env python3
"""The issue forms GitHub would show. A form that isn't valid YAML, or
breaks one of GitHub's form rules, is dropped from the New issue page
without a word (as 01-submit-setup.yml was from #5 to #8), so each one is
parsed here, and the submission form's labels are checked against what
scripts/issue_to_setup.py reads. A field a file is dragged into must be a
textarea without `render`: GitHub turns `render` into a code block that
takes no attachments (the config and theme fields were, until #9)."""

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / ".github" / "ISSUE_TEMPLATE"
sys.path.insert(0, str(ROOT / "scripts"))
import issue_to_setup as its  # noqa: E402

TYPES = {"markdown", "input", "textarea", "dropdown", "checkboxes", "upload"}
# Fields of the submission form a file is dropped into (issue_to_setup.FIELDS keys)
FILE_FIELDS = ("config", "screenshot", "theme", "wallpaper")
ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def form_problems(form):
    problems = []
    for key in ("name", "description", "body"):
        if key not in form:
            problems.append(f"no top-level `{key}`")
    for key in ("name", "description", "title"):
        if key in form and not isinstance(form[key], str):
            problems.append(f"`{key}` isn't a string")
    ids, labels = set(), set()
    for i, item in enumerate(form.get("body") or []):
        where = f"body[{i}]"
        kind = item.get("type")
        if kind not in TYPES:
            problems.append(f"{where}: type {kind!r}")
            continue
        attrs = item.get("attributes") or {}
        for key, value in attrs.items():
            if key in ("label", "description", "placeholder", "value", "render") and not isinstance(value, str):
                problems.append(f"{where}.{key} isn't a string")
        if kind == "markdown":
            continue
        if "id" in item:
            if not ID_RE.match(str(item["id"])) or item["id"] in ids:
                problems.append(f"{where}: id {item['id']!r} is malformed or repeated")
            ids.add(item["id"])
        label = attrs.get("label")
        if not label or label in labels:
            problems.append(f"{where}: label {label!r} is missing or repeated")
        labels.add(label)
        for key, value in (item.get("validations") or {}).items():
            if key == "required" and not isinstance(value, bool) or key == "min_length" and (type(value) is not int or value < 0):
                problems.append(f"{where}.validations.{key}: {value!r}")
        if kind == "dropdown":
            options = attrs.get("options") or []
            if not options or len(set(map(str, options))) != len(options):
                problems.append(f"{where}: options missing or repeated")
        if kind == "checkboxes":
            for option in attrs.get("options") or []:
                if not isinstance(option.get("label"), str):
                    problems.append(f"{where}: a checkbox without a label")
    return problems


def main():
    results = []
    for path in sorted(TEMPLATES.glob("*.yml")):
        try:
            data = yaml.safe_load(path.read_text())
        except yaml.YAMLError as e:
            results.append((path.name, [f"not valid YAML: {e}"]))
            continue
        results.append((path.name, [] if path.name == "config.yml" else form_problems(data)))

    try:
        submit = yaml.safe_load((TEMPLATES / "01-submit-setup.yml").read_text())
    except yaml.YAMLError:
        return report(results)
    labels = [item["attributes"]["label"] for item in submit["body"] if item["type"] != "markdown"]
    expected = [*its.FIELDS.values(), its.FORM_END]
    results.append(("01-submit-setup.yml matches issue_to_setup.FIELDS", [] if labels == expected else [f"form {labels} != script {expected}"]))
    if "title" in {item.get("id") for item in submit["body"]}:
        results[-1][1].append("a field with id `title` takes the issue title's ?title= prefill")
    by_label = {item["attributes"]["label"]: item for item in submit["body"] if item["type"] != "markdown"}
    problems = []
    for key in FILE_FIELDS:
        item = by_label.get(its.FIELDS[key], {})
        if item.get("type") != "textarea" or "render" in item.get("attributes", {}):
            problems.append(f"{its.FIELDS[key]!r} must be a textarea without `render` to take a dragged-in file")
    results.append(("01-submit-setup.yml's file fields take attachments", problems))
    report(results)


def report(results):
    for name, problems in results:
        print(f"{'ok  ' if not problems else 'FAIL'} {name}")
        for problem in problems:
            print(f"     {problem}")
    failed = sum(1 for _, p in results if p)
    print(f"\n{len(results) - failed}/{len(results)} ok")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
