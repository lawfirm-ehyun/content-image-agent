#!/usr/bin/env bash
# Pretendard 4 weights (Regular, Medium, SemiBold, Bold) 다운로드.
# 로컬(Windows git-bash) + GitHub Actions(ubuntu) 양쪽 호환.
set -euo pipefail

VERSION="1.3.9"
FONT_DIR="assets/fonts"
BASE_URL="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@${VERSION}/packages/pretendard/dist/public/static"
LICENSE_URL="https://raw.githubusercontent.com/orioncactus/pretendard/v${VERSION}/LICENSE"

mkdir -p "$FONT_DIR"

for weight in Regular Medium SemiBold Bold; do
    out="$FONT_DIR/Pretendard-${weight}.otf"
    if [ -f "$out" ]; then
        echo "  skip: $out (already exists)"
        continue
    fi
    echo "  downloading: Pretendard-${weight}.otf"
    curl -L --fail -sS -o "$out" "$BASE_URL/Pretendard-${weight}.otf"
done

license_out="$FONT_DIR/LICENSE"
if [ ! -f "$license_out" ]; then
    echo "  downloading: LICENSE"
    curl -L --fail -sS -o "$license_out" "$LICENSE_URL"
fi

echo
echo "✓ Pretendard fonts ready in $FONT_DIR"
ls -1 "$FONT_DIR" | grep -v '^\.gitkeep$' || true
