#!/usr/bin/env bash
# Validate the committed source in a fresh environment. Never invokes paid APIs.
set -euo pipefail

with_docker=0
case "${1:-}" in
  --docker) with_docker=1 ;;
  --help) printf '%s\n' 'Usage: PYTHON_BIN=python3.12 bash scripts/acceptance.sh [--docker]' 'Checks committed HEAD in a clean archive. Logs go to results/clean-acceptance-*/.'; exit 0 ;;
  '') ;;
  *) printf '%s\n' 'Unknown option. Use --help.' >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then printf '%s\n' 'Only --docker is accepted.' >&2; exit 2; fi
cd "$(dirname "$0")/.."
repo_root=$(pwd)
if [ -z "${PYTHON_BIN:-}" ]; then
  for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3,11))' 2>/dev/null; then
      PYTHON_BIN=$(command -v "$candidate")
      break
    fi
  done
fi
if [ -z "${PYTHON_BIN:-}" ]; then printf '%s\n' 'Python 3.11+ is required. Set PYTHON_BIN to its executable.' >&2; exit 2; fi
PYTHON_BIN=$(command -v "$PYTHON_BIN")
"$PYTHON_BIN" -c 'import sys; sys.exit("Python 3.11+ required") if sys.version_info < (3,11) else None'
PYTHON_BIN=$("$PYTHON_BIN" -c 'import sys; print(sys.executable)')
mkdir -p results
out=$(mktemp -d "$repo_root/results/clean-acceptance-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
head=$(git rev-parse HEAD)
step=archive
printf 'Evidence directory: %s\nCommitted source: %s\n' "$out" "$head"
printf 'step\tstatus\n' > "$out/status.tsv"
finish() {
  code=$?
  trap - EXIT
  "$PYTHON_BIN" - "$out" "$head" "$code" "$step" "$with_docker" <<'PY'
import datetime, json, pathlib, sys
out, head, code, step, docker = sys.argv[1:]
record = {"checked_commit": head, "finished_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "exit_code": int(code), "status": "passed" if code == "0" else "failed",
          "last_step": step, "docker_requested": docker == "1",
          "browser_visual_qa": "pending_manual_check", "human_annotation": "pending",
          "paid_api_calls": 0}
pathlib.Path(out, "acceptance.json").write_text(json.dumps(record, indent=2) + "\n")
PY
  printf 'Acceptance exit %s; evidence: %s\n' "$code" "$out"
  exit "$code"
}
trap finish EXIT
run_step() {
  step=$1
  shift
  printf '\nRunning %s\n' "$step"
  "$@" 2>&1 | tee "$out/$step.log"
  printf '%s\tpassed\n' "$step" >> "$out/status.tsv"
}
mkdir "$out/source"
git archive "$head" | tar -xf - -C "$out/source"
run_step venv "$PYTHON_BIN" -m venv "$out/venv"
py="$out/venv/bin/python"
cd "$out/source"
run_step install "$py" -m pip install --disable-pip-version-check --no-cache-dir -r requirements.txt
run_step dependencies "$py" -m pip check
run_step environment "$py" -c 'import sys,numpy,PIL; print(sys.version); print("NumPy",numpy.__version__,"Pillow",PIL.__version__)'
run_step tests "$py" -m unittest discover -s tests -v
run_step reproduce "$py" -m briefguard run --split test --out "$out/reproduction"
run_step compare "$py" scripts/compare_runs.py results/test "$out/reproduction"
run_step demo "$py" scripts/check_demo.py
if [ "$with_docker" -eq 1 ]; then
  run_step docker-info docker info
  image_tag="briefguard-acceptance:${head:0:12}"
  run_step docker-build docker build --tag "$image_tag" .
  run_step docker-tests docker run --rm --network none "$image_tag"
fi
printf '%s\n' 'Automated checks passed. Browser and human checks remain separate; use docs/browser_checklist.md.'
