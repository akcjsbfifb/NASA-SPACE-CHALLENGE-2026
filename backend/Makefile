MAKEFILE_DIR := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
VENV := $(MAKEFILE_DIR)/.venv
PYTHON := $(VENV)/bin/python

.PHONY: venv dev release clean

venv:
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install -r $(MAKEFILE_DIR)/requirements.txt

dev:
	cd $(MAKEFILE_DIR) && $(VENV)/bin/uvicorn app.main:app --reload --timeout-graceful-shutdown 2 --host 127.0.0.1 --port 8787 --log-level debug

release:
	cd $(MAKEFILE_DIR) && $(VENV)/bin/uvicorn app.main:app --reload --timeout-graceful-shutdown 2 --host 127.0.0.1 --port 8787

clean:
	rm -rf $(VENV) $(MAKEFILE_DIR)/.pytest_cache
	find $(MAKEFILE_DIR) -type d -name __pycache__ -exec rm -rf {} +
