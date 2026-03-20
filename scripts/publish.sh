#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Running checks..."
uvx ruff check temple/ tests/
uvx ruff format --check temple/ tests/
uv run ty check temple/
uv run pytest

echo "Building..."
rm -rf dist/
uv build

echo "Publishing to PyPI..."
uv publish
