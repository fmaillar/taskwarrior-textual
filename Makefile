SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

PYTHON ?= python3
VENV ?= .venv
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff
COVERAGE := $(VENV)/bin/coverage

REPORT_DIR := reports

.PHONY: help venv install test coverage report lint check push-reports clean

help:
	@printf '%s\n' \
	  'make venv          Create the virtual environment' \
	  'make install       Install project + development dependencies' \
	  'make test          Run pytest with the configured coverage gate' \
	  'make coverage      Run tests and generate coverage reports' \
	  'make report        Generate compact reports suitable for Git' \
	  'make lint          Run Ruff' \
	  'make check         Run lint + report' \
	  'make push-reports  Generate, commit and push reports even if tests fail' \
	  'make clean         Remove generated local artifacts'

venv:
	@test -x "$(VENV)/bin/python" || $(PYTHON) -m venv "$(VENV)"

install: venv
	$(PIP) install -e '.[dev]'

test: install
	$(PYTEST)

coverage: install
	mkdir -p "$(REPORT_DIR)"
	$(PYTEST) \
	  --junitxml="$(REPORT_DIR)/junit.xml" \
	  --cov-report=term-missing \
	  --cov-report=html \
	  --cov-report=xml:"$(REPORT_DIR)/coverage.xml"
	$(COVERAGE) json -o "$(REPORT_DIR)/coverage.json"

report: install
	mkdir -p "$(REPORT_DIR)"
	@set +e; \
	$(PYTEST) \
	  --junitxml="$(REPORT_DIR)/junit.xml" \
	  --cov-report=term-missing \
	  --cov-report=xml:"$(REPORT_DIR)/coverage.xml" \
	  2>&1 | tee "$(REPORT_DIR)/pytest.txt"; \
	status=$${PIPESTATUS[0]}; \
	$(COVERAGE) json -o "$(REPORT_DIR)/coverage.json"; \
	printf '%s\n' "$$status" > "$(REPORT_DIR)/pytest-exit-status.txt"; \
	exit $$status

lint: install
	$(RUFF) check src tests

check: lint report

push-reports: install
	@set +e; \
	$(MAKE) --no-print-directory report; \
	status=$$?; \
	git add "$(REPORT_DIR)"; \
	if git diff --cached --quiet -- "$(REPORT_DIR)"; then \
		echo "No report changes to commit."; \
	else \
		git commit -m "Update test and coverage reports" && git push; \
	fi; \
	exit $$status

clean:
	rm -rf htmlcov .coverage .pytest_cache .ruff_cache "$(REPORT_DIR)"
