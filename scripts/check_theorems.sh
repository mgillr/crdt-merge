#!/bin/bash
# P-112: THE LEAN GATE — machine-check every theorem file in theorem/.
set -e
cd "$(dirname "$0")/.."
if ! command -v lean >/dev/null 2>&1; then
  echo "LEAN GATE: lean not installed (install elan first)"; exit 2
fi
if grep -rn "sorry" theorem/; then
  echo "LEAN GATE: FAIL — unproven hole present"; exit 1
fi
for f in theorem/*.lean; do lean "$f"; done
echo "LEAN GATE: PASS — all theorem files machine-verified, zero holes"
