# Auto-discover build targets from the filesystem: every targets/<name>/build.py
# is a host (mirrors tools.build's discover_targets()), so this list never goes
# stale when a host is added or removed.
TARGETS := $(filter-out _common,$(notdir $(patsubst %/,%,$(dir $(wildcard targets/*/build.py)))))

# Use the project venv if present, otherwise fall back to python3 on PATH.
# Resolved at parse time so `make test` / `make lint` / `make <host>` work whether
# or not the venv is activated — and for headless workers that never activate it.
PYTHON := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

.PHONY: help all clean lint test $(TARGETS)

help:
	@echo "Using PYTHON=$(PYTHON)"
	@echo "Available targets:"
	@echo "  make all              build all plugin targets"
	@echo "  make <host>           build one host plugin"
	@echo "  make lint             validate skill manifests"
	@echo "  make test             run pytest"
	@echo "  make clean            remove build/"
	@echo
	@echo "Discovered hosts: $(TARGETS)"

all: $(TARGETS)

$(TARGETS):
	$(PYTHON) -m tools.build $@

lint:
	$(PYTHON) -m tools.lint_skills

test:
	$(PYTHON) -m pytest -q

clean:
	rm -rf build/ dist/ *.egg-info
