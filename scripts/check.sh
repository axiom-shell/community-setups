#!/usr/bin/env bash
# Check setups the way CI does: each config loaded by axiom's own binary
# (migrated, validated, and with `axiom config share` picked as Export
# would), then everything else, by scripts/validate.py.
#
#   scripts/check.sh [--axiom DIR] [validate.py args…] [ID…]
#   scripts/check.sh [--axiom DIR] --upgrade ID…
#
# --upgrade rewrites each setup's config.json as that axiom exports it
# (migrated, look only, defaults left out), then checks it: how a maintainer
# brings setups up to a new config schema.
#
# Without --axiom or $AXIOM_DIR, axiom's edge build and the commit it was
# built from are fetched into .axiom/ (scripts/axiom.sh). With a checkout of
# your own, the binary is $AXIOM_BIN, else `axiom` on PATH: build it from
# that checkout so the two agree.
#
# Exits 0 when every setup passes, 1 when one doesn't, 3 when axiom couldn't
# be fetched or run.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
axiom="${AXIOM_DIR:-}"
args=()
while [ $# -gt 0 ]; do
  case "$1" in
    --axiom) axiom="$2"; shift 2 ;;
    --axiom=*) axiom="${1#--axiom=}"; shift ;;
    *) args+=("$1"); shift ;;
  esac
done

if [ -z "$axiom" ]; then
  axiom="$root/.axiom"
  "$root/scripts/axiom.sh" "$axiom" || exit 3
fi

exec python3 "$root/scripts/validate.py" --axiom "$axiom" "${args[@]}"
