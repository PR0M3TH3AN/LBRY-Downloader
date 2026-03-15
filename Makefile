.PHONY: help install test lint format clean run dry-run

help:
	@echo "LBRY Downloader - Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make test       - Run tests"
	@echo "  make lint       - Run linting (if configured)"
	@echo "  make format     - Format code (if configured)"
	@echo "  make clean      - Clean generated files"
	@echo "  make run        - Run the downloader"
	@echo "  make dry-run    - Run in dry-run mode"

install:
	pip install -r requirements.txt
	@echo "Dependencies installed"

test:
	python3 -m pytest tests/ -v

lint:
	@echo "Linting not configured. Add ruff or flake8 to requirements.txt"
	@echo "and configure this target."

format:
	@echo "Formatting not configured. Add ruff or black to requirements.txt"
	@echo "and configure this target."

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .coverage htmlcov/

run:
	python3 main.py

dry-run:
	python3 main.py --dry-run
