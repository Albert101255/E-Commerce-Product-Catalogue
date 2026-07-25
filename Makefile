.PHONY: setup run test lint format clean

setup:
	@echo "Setting up development environment..."
	poetry install
	cp -n .env.example .env || true
	poetry run pre-commit install

run:
	docker-compose up --build

test:
	poetry run pytest

lint:
	poetry run ruff check app tests
	poetry run mypy app tests

format:
	poetry run black app tests
	poetry run ruff check --fix app tests

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
