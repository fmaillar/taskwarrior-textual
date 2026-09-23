SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

PYTHON ?= python3
VENV ?= .venv
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff
MYPY := $(VENV)/bin/mypy
BUILD := $(VENV)/bin/python -m build
COVERAGE := $(VENV)/bin/coverage
PYTEST_JOBS ?= auto
INSTALL_STAMP := $(VENV)/.taskwarrior-textual-installed
PACKAGE_TEST_VENV := .venv-package-test
PUBLISH_REMOTE ?= public

REPORT_DIR := reports

.PHONY: help venv install reinstall test test-compat test-serial coverage report lint typecheck package verify-package check publish push-reports clean

help:
	@printf '%s\n' \
	  'make venv          Create the virtual environment' \
	  'make install       Install only when pyproject.toml changed' \
	  'make reinstall     Force reinstall project + development dependencies' \
	  'make test          Run pytest in parallel with the configured coverage gate' \
	  'make test-compat   Run tests without duplicate coverage work' \
	  'make test-serial   Run pytest sequentially for debugging' \
	  'make coverage      Run parallel tests and generate coverage reports' \
	  'make report        Generate Ruff + pytest/coverage reports and statuses' \
	  'make lint          Run Ruff' \
	  'make typecheck     Run mypy over the package' \
	  'make package       Build wheel and source distribution' \
	  'make verify-package  Verify wheel installation in a clean virtualenv' \
	  'make check         Run Ruff, mypy, tests/coverage, and package verification' \
	  'make publish       Publish validated main + tags to the public remote' \
	  'make push-reports  Always commit/push reports, even when tests fail' \
	  'make clean         Remove generated local artifacts'

venv:
	@test -x "$(VENV)/bin/python" || $(PYTHON) -m venv "$(VENV)"

install: $(INSTALL_STAMP)

$(INSTALL_STAMP): pyproject.toml | venv
	$(PIP) install -e '.[dev]'
	@touch "$(INSTALL_STAMP)"

reinstall: venv
	@rm -f "$(INSTALL_STAMP)"
	$(MAKE) --no-print-directory install

test: install
	$(PYTEST) -n "$(PYTEST_JOBS)"

test-compat: install
	$(PYTEST) -n "$(PYTEST_JOBS)" --no-cov

test-serial: install
	$(PYTEST)

coverage: install
	mkdir -p "$(REPORT_DIR)"
	$(PYTEST) -n "$(PYTEST_JOBS)" \
	  --junitxml="$(REPORT_DIR)/junit.xml" \
	  --cov-report=term-missing \
	  --cov-report=html \
	  --cov-report=xml:"$(REPORT_DIR)/coverage.xml"
	$(COVERAGE) json -o "$(REPORT_DIR)/coverage.json"

report: install
	mkdir -p "$(REPORT_DIR)"
	@set +e; \
	$(RUFF) check src tests 2>&1 | tee "$(REPORT_DIR)/ruff.txt"; \
	lint_status=$${PIPESTATUS[0]}; \
	printf '%s\n' "$$lint_status" > "$(REPORT_DIR)/ruff-exit-status.txt"; \
	$(MYPY) 2>&1 | tee "$(REPORT_DIR)/mypy.txt"; \
	type_status=$${PIPESTATUS[0]}; \
	printf '%s\n' "$$type_status" > "$(REPORT_DIR)/mypy-exit-status.txt"; \
	$(PYTEST) -n "$(PYTEST_JOBS)" \
	  --junitxml="$(REPORT_DIR)/junit.xml" \
	  --cov-report=term-missing \
	  --cov-report=xml:"$(REPORT_DIR)/coverage.xml" \
	  2>&1 | tee "$(REPORT_DIR)/pytest.txt"; \
	test_status=$${PIPESTATUS[0]}; \
	$(COVERAGE) json -o "$(REPORT_DIR)/coverage.json"; \
	printf '%s\n' "$$test_status" > "$(REPORT_DIR)/pytest-exit-status.txt"; \
	if [ $$lint_status -ne 0 ]; then \
		exit $$lint_status; \
	fi; \
	if [ $$type_status -ne 0 ]; then \
		exit $$type_status; \
	fi; \
	exit $$test_status

lint: install
	$(RUFF) check src tests

typecheck: install
	$(MYPY)

package: install
	rm -rf dist
	$(BUILD)

verify-package: package
	$(VENV)/bin/python -c 'from pathlib import Path; import tarfile, zipfile; s=next(Path("dist").glob("*.tar.gz")); w=next(Path("dist").glob("*.whl")); tf=tarfile.open(s); sn=tf.getnames(); zf=zipfile.ZipFile(w); wn=zf.namelist(); assert any(n.endswith("/LICENSE") for n in sn); assert any(n.endswith("/README.md") for n in sn); assert any("/docs/" in n for n in sn); assert any(n.endswith(".dist-info/licenses/LICENSE") for n in wn); assert "taskwarrior_textual/__init__.py" in wn'
	rm -rf "$(PACKAGE_TEST_VENV)"
	$(PYTHON) -m venv "$(PACKAGE_TEST_VENV)"
	"$(PACKAGE_TEST_VENV)/bin/pip" install dist/*.whl
	$(VENV)/bin/python -c 'import subprocess, tomllib; expected=tomllib.load(open("pyproject.toml", "rb"))["project"]["version"]; actual=subprocess.check_output(["$(PACKAGE_TEST_VENV)/bin/taskwarrior-textual", "--version"], text=True).strip(); assert actual == f"taskwarrior-textual {expected}", f"expected taskwarrior-textual {expected}, got {actual}"'
	rm -rf "$(PACKAGE_TEST_VENV)"

check: report verify-package

publish:
	@test "$$(git branch --show-current)" = "main" || { echo "publish requires main"; exit 1; }
	@test -z "$$(git status --porcelain)" || { echo "publish requires a clean working tree"; exit 1; }
	@git remote get-url "$(PUBLISH_REMOTE)" >/dev/null 2>&1 || { echo "missing remote: $(PUBLISH_REMOTE)"; exit 1; }
	@git fetch origin main
	@test "$$(git rev-parse HEAD)" = "$$(git rev-parse origin/main)" || { echo "local main is not origin/main"; exit 1; }
	git push "$(PUBLISH_REMOTE)" main
	git push "$(PUBLISH_REMOTE)" --tags
push-reports: install
	@set +e; \
	$(MAKE) --no-print-directory report; \
	test_status=$$?; \
	git add "$(REPORT_DIR)"; \
	push_status=0; \
	if git diff --cached --quiet -- "$(REPORT_DIR)"; then \
		echo "No report changes to commit."; \
	else \
		git commit -m "Update test and coverage reports" || push_status=$$?; \
		if [ $$push_status -eq 0 ]; then \
			git push || push_status=$$?; \
		fi; \
	fi; \
	echo "Test/coverage exit status: $$test_status"; \
	if [ $$push_status -ne 0 ]; then \
		echo "Report push failed with status $$push_status"; \
		exit $$push_status; \
	fi; \
	echo "Reports pushed successfully."; \
	exit 0

clean:
	rm -rf htmlcov .coverage .pytest_cache .ruff_cache .mypy_cache build dist "$(REPORT_DIR)" "$(PACKAGE_TEST_VENV)"
