#!/usr/bin/env bash
# Fetch the axiom the checks run against: the binary of axiom's `edge`
# prerelease (rebuilt on every merge to its main), checked against its
# SHA256SUMS, and a checkout of the commit it was built from (its themes,
# and the schema `--tree` builds), so the two always agree.
#
#   scripts/axiom.sh [DIR]   (default .axiom/; the binary is DIR/.edge/axiom)
#
# Nothing is fetched again while DIR already holds edge's commit.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dir="${1:-$root/.axiom}"
release="https://github.com/axiom-shell/axiom/releases/download/edge"
repo="https://github.com/axiom-shell/axiom"
case "$(uname -m)" in
  x86_64) asset=axiom-linux-amd64 ;;
  aarch64 | arm64) asset=axiom-linux-arm64 ;;
  *) echo "error: no axiom binary for $(uname -m)" >&2; exit 3 ;;
esac

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
fetch() { curl -fsSL --retry 3 -o "$tmp/$1" "$release/$1"; }
fetch COMMIT
fetch SHA256SUMS
commit="$(tr -d '[:space:]' < "$tmp/COMMIT")"
if [[ ! "$commit" =~ ^[0-9a-f]{40}$ ]]; then
  echo "error: edge's COMMIT isn't a commit: $commit" >&2
  exit 3
fi
(cd "$tmp" && grep -E " (COMMIT)$" SHA256SUMS | sha256sum -c --quiet -) || { echo "error: edge's COMMIT doesn't match its SHA256SUMS" >&2; exit 3; }

if [ -x "$dir/.edge/axiom" ] && [ "$(cat "$dir/.edge/COMMIT" 2>/dev/null)" = "$commit" ]; then
  echo "axiom edge ${commit:0:12} (already fetched)"
  exit 0
fi

fetch "$asset"
(cd "$tmp" && grep -E " ($asset)$" SHA256SUMS | sha256sum -c --quiet -) || { echo "error: $asset doesn't match edge's SHA256SUMS" >&2; exit 3; }

rm -rf "$dir"
mkdir -p "$dir"
git -C "$dir" init -q
git -C "$dir" fetch -q --depth=1 "$repo" "$commit"
git -C "$dir" checkout -q FETCH_HEAD
mkdir -p "$dir/.edge"
install -m 755 "$tmp/$asset" "$dir/.edge/axiom"
echo "$commit" > "$dir/.edge/COMMIT"
echo "axiom edge ${commit:0:12}"
