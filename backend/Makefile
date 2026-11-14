VENV := .venv
PYTHON := $(VENV)/bin/python

.PHONY: venv dev release clean

venv:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -r requirements.txt

dev:
	$(VENV)/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --log-level debug

release:
	$(VENV)/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

clean:
	rm -rf $(VENV) .pytest_cache
	$(MAKE) -C $(C_DIR) clean
	find . -type d -name __pycache__ -exec rm -rf {} +
