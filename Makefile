.PHONY: all install test clean build help lint lint-fix format type-check check docs benchmark

# Default target
all: help

help:
	@echo "Available commands:"
	@echo "  make install     - Install the package in editable mode with dev and docs dependencies"
	@echo "  make test        - Run tests using pytest with coverage"
	@echo "  make lint        - Run linting using ruff"
	@echo "  make lint-fix    - Fix linting issues using ruff"
	@echo "  make format      - Format code using ruff"
	@echo "  make type-check  - Run type checking using mypy"
	@echo "  make check       - Run all verifications (lint, type-check, test)"
	@echo "  make docs        - Build HTML documentation using Sphinx"
	@echo "  make benchmark   - Run performance benchmarks"
	@echo "  make clean       - Remove build artifacts and cache files"
	@echo "  make build       - Build the package (source distribution and wheel)"

install:
	pip install -e .[dev,docs,otel,llm]
	pre-commit install

test:
	PYTHONPATH=. pytest --cov=pypss tests/
	@echo "\nRunning Benchmarks..."
	$(MAKE) benchmark

lint:
	ruff check .

lint-fix:
	ruff check --fix .

format:
	ruff format .

type-check:
	mypy --check-untyped-defs pypss tests

check: lint type-check test

docs:
	$(MAKE) -C docs html

benchmark:
	python tests/benchmarks/test_benchmark.py

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	find . -name '__pycache__' -exec rm -rf {} +
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	rm -f .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf .pytest_cache/

build: clean
	python -m build
