#!/usr/bin/env bash
# Run in the owner's ordinary Terminal when the agent sandbox cannot use the network.
# Never invokes a paid model, merges a PR, or pushes the default branch.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ "$(git branch --show-current)" != "research/briefguard" ]]; then
  echo "Expected research/briefguard; refusing to publish another branch." >&2
  exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree has changes. Review and commit them before publishing." >&2
  exit 1
fi
if [[ "$(git remote get-url origin)" != "https://github.com/lilite572-cyber/briefguard.git" ]]; then
  echo "Unexpected origin; review it before publishing." >&2
  exit 1
fi
command -v gh >/dev/null || { echo "Install the GitHub CLI from cli.github.com first." >&2; exit 1; }
account="$(gh api user --jq .login)"
if [[ "$account" != "lilite572-cyber" ]]; then
  echo "The GitHub CLI must use lilite572-cyber for this project." >&2
  exit 1
fi

# Prefer a caller-selected Python; this fallback is the already installed runtime
# on the development Mac, not a download or a change to system Python.
if [[ -z "${PYTHON_BIN:-}" ]]; then
  if command -v python3.12 >/dev/null; then
    export PYTHON_BIN=python3.12
  elif [[ -x "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3.12" ]]; then
    export PYTHON_BIN="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3.12"
  else
    export PYTHON_BIN=python3
  fi
fi
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  bash scripts/acceptance.sh --docker
else
  bash scripts/acceptance.sh
  echo "Docker daemon unavailable: Docker acceptance remains pending."
fi

git fetch origin research/briefguard
if ! git merge-base --is-ancestor FETCH_HEAD HEAD; then
  echo "The remote contains changes absent locally. Reconcile them without force push." >&2
  exit 1
fi
git push origin HEAD:refs/heads/research/briefguard
gh pr edit 1 --repo lilite572-cyber/briefguard --body-file docs/pr_draft.md
published="$(git ls-remote origin refs/heads/research/briefguard | cut -f1)"
if [[ "$published" != "$(git rev-parse HEAD)" ]]; then
  echo "Remote head changed; inspect the PR before claiming publication." >&2
  exit 1
fi
echo "Published $published to research/briefguard; draft PR #1 updated. No merge performed."
echo "Human annotation and paid VLM inference remain pending."
echo "Follow docs/browser_checklist.md at http://127.0.0.1:8765"
echo "Press Ctrl-C to stop this local demo server."
exec "$PYTHON_BIN" -m http.server --bind 127.0.0.1 8765 --directory demo
