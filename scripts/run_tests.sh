#!/usr/bin/env bash
# Run the DataPulse test suite.
# Usage: ./scripts/run_tests.sh
set -e
cd "$(dirname "$0")/.."
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate
python -m pytest tests/ -v --tb=short
