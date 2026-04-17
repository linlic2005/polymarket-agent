.PHONY: dev test lint db-upgrade init clear

init:
	cp .env.example .env || true
	pip install -e .[dev]

dev:
	uvicorn apps.server:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v

lint:
	ruff check .
	mypy .

db-upgrade:
	alembic upgrade head

clear:
	find . -type d -name "__pycache__" -exec rm -r {} +
