#!/usr/bin/env bash
# Render docs/BENDER_INVESTOR_PITCH.md to PDF exactly as written.
# Usage: ./scripts/build_pitch_pdf.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MD="$ROOT/docs/BENDER_INVESTOR_PITCH.md"
HTML="$ROOT/docs/BENDER_INVESTOR_PITCH.html"
PDF="$ROOT/docs/BENDER_INVESTOR_PITCH.pdf"
CSS="$ROOT/docs/BENDER_INVESTOR_PITCH.css"

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

if [[ ! -f "$MD" ]]; then
  echo "Error: $MD not found" >&2
  exit 1
fi

if ! command -v pandoc >/dev/null 2>&1; then
  echo "Error: pandoc is required but not installed" >&2
  exit 1
fi

if [[ ! -f "$CHROME" ]]; then
  echo "Error: Google Chrome not found at $CHROME" >&2
  exit 1
fi

pandoc "$MD" \
  --from markdown \
  --to html \
  --standalone \
  --css="BENDER_INVESTOR_PITCH.css" \
  --output="$HTML"

"$CHROME" \
  --headless \
  --disable-gpu \
  --print-to-pdf="$PDF" \
  --run-all-compositor-stages-before-draw \
  --no-pdf-header-footer \
  "file://$HTML"

echo "Built:"
echo "  HTML: $HTML"
echo "  PDF:  $PDF"
