PYTHON ?= python3

.PHONY: test pilot dev freeze experiment report demo serve reproduce
test:
	$(PYTHON) -m unittest discover -s tests -v
pilot:
	$(PYTHON) -m briefguard run --split pilot --out results/pilot-final
dev:
	$(PYTHON) -m briefguard run --split dev --out results/dev
freeze:
	$(PYTHON) -m briefguard freeze --pilot results/pilot-final
experiment:
	$(PYTHON) -m briefguard run --split test --out results/test
report:
	$(PYTHON) -m briefguard report --run results/test
demo:
	$(PYTHON) -m briefguard demo --run results/test --out demo
serve:
	$(PYTHON) -m http.server --bind 127.0.0.1 8765 --directory demo
reproduce:
	$(PYTHON) -m briefguard run --split test --out results/reproduce
	$(PYTHON) scripts/compare_runs.py results/test results/reproduce
