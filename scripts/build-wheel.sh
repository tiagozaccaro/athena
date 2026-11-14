#!/usr/bin/env bash
# Builds the server wheel with the web UI and the built-in catalog bundled, into dist/.
# Used by the release workflow and the end-to-end workflow; run it locally to test an
# install of unreleased code (`install.sh --wheel dist/athena_server-*.whl`).
#
#   scripts/build-wheel.sh            # builds the web UI first (needs `pnpm install`)
#   scripts/build-wheel.sh --no-web   # reuses an existing apps/web/out
set -euo pipefail

cd "$(dirname "$0")/.."

BUILD_WEB=1
if [ "${1:-}" = "--no-web" ]; then BUILD_WEB=0; fi

if [ "$BUILD_WEB" -eq 1 ]; then pnpm build; fi
[ -f apps/web/out/index.html ] || { echo "error: apps/web/out is missing; run pnpm build" >&2; exit 1; }

WEB=apps/server/src/athena/web
CATALOG=apps/server/src/athena/catalog_builtin
# Both are gitignored build artifacts. Remove them afterwards so a dev server doesn't
# keep serving a stale bundled UI.
cleanup() { rm -rf "$WEB" "$CATALOG"; }
trap cleanup EXIT
cleanup
cp -R apps/web/out "$WEB"
cp -R catalog "$CATALOG"

rm -f dist/athena_server-*.whl
(cd apps/server && uv build --wheel --out-dir ../../dist)

# The installers serve the bundled UI and catalog; a wheel without them is broken.
python3 - <<'PY'
import glob, sys, zipfile
wheels = glob.glob("dist/athena_server-*.whl")
if len(wheels) != 1:
    sys.exit(f"expected one wheel in dist/, found {wheels}")
names = zipfile.ZipFile(wheels[0]).namelist()
need = ("athena/web/index.html", "athena/catalog_builtin/apps/jellyfin/compose.yaml")
missing = [p for p in need if p not in names]
sys.exit(f"missing from {wheels[0]}: {missing}" if missing else 0)
print(wheels[0])
PY
