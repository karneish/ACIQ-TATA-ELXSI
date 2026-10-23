# TATA-ELXSI ACIQ — one-command entry points.
# Privileged targets shell out to testbed scripts that need root; every offline
# target runs as your normal user. `make` prints the target list.

PY ?= python3
VENV ?= $(if $(wildcard /home/*/aciq-venv/bin/python),/home/*/aciq-venv/bin/python,$(PY))
SUDO ?= sudo env ACIQ_VENV=$(firstword $(wildcard /home/*/aciq-venv) $(PWD))

.PHONY: help test lint corpus report demo-light setup teardown safe-reset \
        demo phase5 phase6 s5 corpus-collect dashboard live

help:
	@grep -E '^[a-z-]+:' Makefile | sed 's/:.*/   /' | head -20

# ---- offline (no root) ----------------------------------------------------
test:            ## full offline suite (~60 s)
	$(PY) -m unittest discover -q

lint:            ## citation audit: every leaf claim resolves
	$(PY) tools/audit_claims.py scan_path_citations

secret-scan:     ## no key/token-looking strings in tracked sources
	$(PY) tools/secret_scan.py

corpus:          ## offline: evaluate classifier corpus, thresholds fixed pre-heldout
	$(PY) tools/eval_corpus.py $(if $(CORPUS),--corpus $(CORPUS),)

report:          ## build RESULTS.md/.html from raw run artefacts only
	$(PY) tools/build_report.py

demo-light:      ## offline dry-run smoke via the real CLI (no kernel)
	$(PY) run_experiments.py --scenario s2_wan_drop --system b1_cake95 \
	  --mode static --seed 7 --seeds 1 --dry-run --no-setup \
	  --results-dir data/demo_offline

# ---- root (needs sudo) ----------------------------------------------------
setup:           ## build the three-namespace testbed
	$(SUDO) ./testbed/setup.sh

teardown:        ## destroy namespaces/links (same as safe-reset, explicit)
	$(SUDO) ./testbed/cleanup.sh

safe-reset:      ## teardown then setup: a clean testbed without stale qdiscs
	$(SUDO) bash -c './testbed/cleanup.sh; ./testbed/setup.sh'

demo:            ## live demo: one scenario, all four arms, 3 seeds (~12 min)
	$(SUDO) SCENARIO=$${SCENARIO:-s2_wan_drop} SEEDS=3 ./testbed/demo.sh

phase5:          ## live: S2/S4 matrix x 10 seeds + paired table (~3 h)
	$(SUDO) ./testbed/phase5.sh

phase6:          ## live phase-6 wrapper as shipped
	$(SUDO) ./testbed/phase6.sh

s5:              ## live: safe-state + failure-injection cases (~25 min)
	$(SUDO) ./testbed/s5_live.sh

corpus-collect:  ## live: router-vantage classifier corpus (~150 s)
	$(SUDO) ./testbed/corpus_live.sh

dashboard:       ## live: capture the dashboard rendering as evidence
	$(SUDO) ./testbed/dashboard_evidence.sh

live:            ## THE one command: every privileged step with resume/log
	$(SUDO) ./testbed/run_all_live.sh
