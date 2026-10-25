#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Сборка закреплённой версии без установки пакетов и без запуска OSD.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
REV=9b14ee017fb8fdb7d03d73da597cf17b89d890f7
SOURCE="$ROOT/build/source"
for tool in git cargo python3; do
    command -v "$tool" >/dev/null || { printf 'Required tool not found: %s\n' "$tool" >&2; exit 1; }
done
if [[ -e "$ROOT/build" ]]; then
    printf 'build/ already exists. Move it aside before rebuilding.\n' >&2
    exit 1
fi
mkdir "$ROOT/build"
git clone --no-checkout https://github.com/pop-os/cosmic-osd.git "$SOURCE"
git -C "$SOURCE" checkout --detach "$REV"
git -C "$SOURCE" apply --check "$ROOT/patches/0001-hide-keyboard-layout-osd.patch"
git -C "$SOURCE" apply "$ROOT/patches/0001-hide-keyboard-layout-osd.patch"
export CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-1}"
export CARGO_PROFILE_DEV_DEBUG=0 CARGO_INCREMENTAL=0
(
    cd "$SOURCE"
    cargo +1.95.0 check --locked -j "$CARGO_BUILD_JOBS"
    cargo +1.95.0 build --locked -j "$CARGO_BUILD_JOBS" --features rust-embed/debug-embed
)
install -m 0755 "$SOURCE/target/debug/cosmic-osd" "$ROOT/build/cosmic-osd"
python3 - "$ROOT/build" "$REV" <<'PY'
import hashlib
import json
import pathlib
import platform
import sys
root = pathlib.Path(sys.argv[1])
info = {
    'upstream_revision': sys.argv[2],
    'sha256': hashlib.sha256((root / 'cosmic-osd').read_bytes()).hexdigest(),
    'architecture': platform.machine(),
}
(root / 'build-info.json').write_text(json.dumps(info, indent=2) + '\n')
print('Build completed. Nothing installed. Run: python3 scripts/manage.py install')
PY
