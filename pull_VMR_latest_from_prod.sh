#!/usr/bin/env bash
set -euo pipefail

CURRENT_URL='https://ictv.global/vmr/current'
OUT_DIR='./VMRs'

mkdir -p "$OUT_DIR"

echo "# Accessing $CURRENT_URL"
REAL_URL="$(curl -fsSIL -o /dev/null -w '%{url_effective}' "$CURRENT_URL")"
echo "REAL_URL=$REAL_URL"

VMR_NAME="$(basename "$REAL_URL")"
OUT_FILE="$OUT_DIR/$VMR_NAME"

echo "# Writing to $OUT_FILE"
curl -fL --output "$OUT_FILE" "$CURRENT_URL"

echo "# QC"
ls -lh "$OUT_FILE"

