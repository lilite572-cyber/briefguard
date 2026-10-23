#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
if [[ "$(git branch --show-current)" != "research/briefguard" ]]; then
  echo 'Refusing: switch to research/briefguard first.' >&2
  exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo 'Refusing: review and preserve uncommitted changes first.' >&2
  exit 1
fi
command -v gh >/dev/null || { echo 'GitHub CLI gh is required to update the PR.' >&2; exit 1; }
git fetch origin research/briefguard
git merge-base --is-ancestor origin/research/briefguard HEAD || {
  echo 'Refusing: remote branch has changes not in this checkout; reconcile without force push.' >&2
  exit 1
}
git push origin HEAD:research/briefguard
gh pr edit 1 --repo lilite572-cyber/briefguard --body-file docs/pr_body.md
echo 'Published working branch and updated draft PR; no merge was performed.'
