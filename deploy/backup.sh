#!/bin/bash
# Back up the database and photos. Uses SQLite's own backup so it is safe to run
# while the app is writing.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
DEST=${1:-$ROOT/backups}
STAMP=$(date +%Y%m%d-%H%M%S)
OUT="$DEST/outfits-$STAMP"

mkdir -p "$OUT"
# Uses SQLite's own backup API via Python. The sqlite3 CLI is not installed on a
# stock Raspberry Pi OS image, and this is safe to run while the app is writing.
"$ROOT/.venv/bin/python" - "$ROOT/data/outfits.db" "$OUT/outfits.db" <<'PYBACKUP'
import sqlite3, sys
src, dst = sqlite3.connect(sys.argv[1]), sqlite3.connect(sys.argv[2])
with dst:
    src.backup(dst)
dst.close(); src.close()
PYBACKUP
cp -a "$ROOT/data/photos" "$OUT/photos"
tar -czf "$OUT.tar.gz" -C "$DEST" "outfits-$STAMP"
rm -rf "$OUT"

echo "Backup written: $OUT.tar.gz  ($(du -h "$OUT.tar.gz" | cut -f1))"

# Keep the ten most recent.
ls -1t "$DEST"/outfits-*.tar.gz 2>/dev/null | tail -n +11 | xargs -r rm --
