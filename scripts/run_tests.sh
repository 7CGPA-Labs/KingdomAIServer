#!/usr/bin/env bash
# Kingdom AI Server V2 4-Gate Automated Test Suite (Bash)
set -e

echo "======================================================================"
echo " 👑 KINGDOM AI SERVER V2 4-GATE TEST SUITE"
echo "======================================================================"

PYTHON="./venv/bin/python"
if [ ! -f "$PYTHON" ]; then
    PYTHON="python3"
fi

$PYTHON -m pytest --verbose
echo "======================================================================"
echo " All Diagnostic Verification Gates Passed Successfully!"
echo "======================================================================"
