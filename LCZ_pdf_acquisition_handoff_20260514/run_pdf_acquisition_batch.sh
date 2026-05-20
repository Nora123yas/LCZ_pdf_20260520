#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

PYTHON="${PYTHON:-python3}"

START="${1:-0}"
LIMIT="${2:-100}"
PRIORITY="${3:-high,medium}"
SLEEP_SECONDS="${4:-1}"

"${PYTHON}" acquire_fulltext_pdfs.py \
  --priority "${PRIORITY}" \
  --start "${START}" \
  --limit "${LIMIT}" \
  --sleep "${SLEEP_SECONDS}"

echo
echo "Done. Review:"
echo "${SCRIPT_DIR}/fulltext_acquisition_log.xlsx"
echo
echo "Put manually downloaded PDFs in:"
echo "${SCRIPT_DIR}/fulltext_pdfs"
