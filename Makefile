.PHONY: help all clean lint test build claude-code claude-desktop codex hermes

TARGETS := claude-code claude-desktop codex hermes

help:
	@echo "Available targets:"
	@echo "  make all              build all plugin targets"
	@echo "  make claude-code      build Claude Code plugin"
	@echo "  make claude-desktop   build Claude Desktop config"
	@echo "  make codex            build Codex AGENTS.md bundle"
	@echo "  make hermes           build Hermes skill bundle"
	@echo "  make lint             validate skill manifests"
	@echo "  make test             run pytest"
	@echo "  make clean            remove build/"

all: $(TARGETS)

claude-code claude-desktop codex hermes:
	python -m tools.build $@

lint:
	python -m tools.lint_skills

test:
	pytest -q

clean:
	rm -rf build/ dist/ *.egg-info
