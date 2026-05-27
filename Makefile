# ═══════════════════════════════════════════════════════════════
# POLYGLOT TOOLKIT v3.0 — Makefile
# Author: Mr-DS-ML-85
# ═══════════════════════════════════════════════════════════════

PYTHON  ?= python3
VENV     = .venv
VENV_PY  = $(VENV)/bin/python
VENV_PIP = $(VENV)/bin/pip
UV      ?= uv

# Detect OS
UNAME_S := $(shell uname -s)

.PHONY: help install run run-gui run-tui build train test clean dist release lint

help: ## Show this help
	@echo ""
	@echo "  POLYGLOT TOOLKIT v3.0 — Makefile Targets"
	@echo "  Author: Mr-DS-ML-85"
	@echo ""
	@echo "  Usage: make <target>"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ── Setup ────────────────────────────────────────────────────

install: ## Install all dependencies (creates venv with UV)
	@echo "[*] Creating venv with UV..."
	$(UV) venv --python 3.14 $(VENV) 2>/dev/null || $(UV) venv $(VENV)
	@echo "[*] Installing dependencies..."
	$(UV) pip install --python $(VENV_PY) \
		PyQt6 rich catboost numpy scikit-learn watchdog pyyaml pandas
	@echo "[✓] Installed. Run: make run"

install-dev: install ## Install dev dependencies (+ pyinstaller)
	$(UV) pip install --python $(VENV_PY) pyinstaller pytest flake8

# ── Run ──────────────────────────────────────────────────────

run: ## Run the app (auto-detect: GUI if display, else TUI)
	$(VENV_PY) polyglot.py

run-gui: ## Run PyQt6 GUI
	$(VENV_PY) polyglot.py gui

run-tui: ## Run Rich TUI
	$(VENV_PY) polyglot.py tui

# ── CLI Commands ─────────────────────────────────────────────

scan: ## Scan file/dir (usage: make scan TARGET=~/Downloads)
	$(VENV_PY) polyglot.py scan $(TARGET)

sanitize: ## Sanitize file/dir (usage: make sanitize TARGET=suspicious.jpg)
	$(VENV_PY) polyglot.py sanitize $(TARGET)

build-polyglot: ## Build polyglot (usage: make build-polyglot COVER=x.jpg PAYLOAD=y.exe)
	$(VENV_PY) polyglot.py build $(COVER) $(PAYLOAD)

# ── Training ─────────────────────────────────────────────────

train: ## Generate training data + train ML model (usage: make train SAMPLES=100)
	$(VENV_PY) polyglot.py train --samples $(or $(SAMPLES),50) --gpu

train-cpu: ## Train on CPU (usage: make train-cpu SAMPLES=100)
	$(VENV_PY) polyglot.py train --samples $(or $(SAMPLES),50) --cpu

generate-data: ## Generate training data only
	$(VENV_PY) generate_training_data.py --samples $(or $(SAMPLES),50)

train-only: ## Train model only (requires training_dataset.csv)
	$(VENV_PY) train_model.py --data training_dataset.csv --gpu

# ── Build Binary ─────────────────────────────────────────────

dist: ## Build single binary with PyInstaller
	@echo "[*] Building single binary..."
	$(VENV_PY) -m PyInstaller \
		--onefile \
		--name polyglot \
		--add-data "engines:engines" \
		--add-data "config.yaml:." \
		--add-data "polyglot_app.py:." \
		--add-data "polyglot_tui.py:." \
		--add-data "generate_training_data.py:." \
		--add-data "train_model.py:." \
		--hidden-import PyQt6 \
		--hidden-import PyQt6.QtWidgets \
		--hidden-import PyQt6.QtCore \
		--hidden-import PyQt6.QtGui \
		--hidden-import rich \
		--hidden-import catboost \
		--hidden-import numpy \
		--hidden-import sklearn \
		--hidden-import yaml \
		--hidden-import pandas \
		--hidden-import watchdog \
		--collect-all catboost \
		--noconfirm \
		--clean \
		polyglot.py
	@echo "[✓] Binary built: dist/polyglot"
	@ls -lh dist/polyglot

server: ## Start server mode (headless API + web dashboard)
	@echo "[*] Starting PolyglotShield Server on :$(or $(PORT),8888)..."
	$(PYTHON) server.py --port $(or $(PORT),8888)

server-remote: ## Start server bound to 0.0.0.0 (remote access)
	@echo "[*] Starting PolyglotShield Server (remote) on :$(or $(PORT),8888)..."
	$(PYTHON) server.py --host 0.0.0.0 --port $(or $(PORT),8888)

release: dist ## Build release binary + create archive
	@echo "[*] Creating release archive..."
	@mkdir -p releases
	@cp dist/polyglot releases/
	@cp README.md LICENSE config.yaml releases/
	@tar -czf releases/polyglot-v3.0-linux-x86_64.tar.gz -C releases \
		polyglot README.md LICENSE config.yaml
	@echo "[✓] Release: releases/polyglot-v3.0-linux-x86_64.tar.gz"
	@ls -lh releases/

# ── Testing ──────────────────────────────────────────────────

test: ## Run tests
	$(VENV_PY) -m pytest tests/ -v 2>/dev/null || \
		$(VENV_PY) -c "from polyglot_tui import PolyglotBuilder, PolyglotDetector, PolyglotSanitizer; print('All engines import OK')"

lint: ## Run linter
	$(VENV_PY) -m flake8 polyglot.py polyglot_app.py polyglot_tui.py \
		generate_training_data.py train_model.py \
		--max-line-length=120 --ignore=E501,W503 2>/dev/null || \
		echo "Install flake8: make install-dev"

# ── Cleanup ──────────────────────────────────────────────────

clean: ## Clean build artifacts
	rm -rf dist/ build/ releases/ *.spec
	rm -rf __pycache__ engines/__pycache__
	rm -rf training_data/ training_dataset.csv yara_training.json
	rm -rf samples/ logs/ quarantine/
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
	@echo "[✓] Cleaned"

clean-all: clean ## Clean everything including venv
	rm -rf $(VENV) models/*.cbm models/*.meta.json
	@echo "[✓] All cleaned (including venv + models)"

# ── Info ─────────────────────────────────────────────────────

info: ## Show project info
	@echo ""
	@echo "  POLYGLOT TOOLKIT v3.0"
	@echo "  Author: Mr-DS-ML-85"
	@echo ""
	@echo "  Python:    $(shell $(VENV_PY) --version 2>/dev/null || echo 'not installed')"
	@echo "  Venv:      $(VENV)"
	@echo "  Platform:  $(UNAME_S)"
	@echo "  Files:     $(shell find . -name '*.py' ! -path './.venv/*' ! -path './__pycache__/*' | wc -l) Python files"
	@echo "  Lines:     $(shell find . -name '*.py' ! -path './.venv/*' -exec cat {} + | wc -l) total lines"
	@echo "  Modules:   $(shell ls engines/*.py 2>/dev/null | wc -l) engine modules"
	@echo ""
	@ls -la polyglot.py polyglot_app.py polyglot_tui.py generate_training_data.py train_model.py 2>/dev/null
	@echo ""
