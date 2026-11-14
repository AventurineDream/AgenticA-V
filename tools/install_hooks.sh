#!/usr/bin/env bash
# Install the repository's staged-file pre-commit hook for this clone.
# Usage: bash tools/install_hooks.sh
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath tools/hooks
chmod +x tools/hooks/*
echo "core.hooksPath -> tools/hooks"
