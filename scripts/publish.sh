#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Running checks..."
uvx ruff check templum/ tests/
uvx ruff format --check templum/ tests/
uv run ty check templum/
uv run pytest

echo "Building..."
rm -rf dist/
uv build

echo "Publishing to PyPI..."
uv publish
