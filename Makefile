.PHONY: install test demo api worker migrate up
install:
	pip install -e ".[dev,api]"
test:
	pytest
demo:
	python scripts/demo_synthetic.py
migrate:
	alembic upgrade head
api:
	cd backend && uvicorn app.main:app --reload --port 8000
worker:
	PYTHONPATH=backend:src rq worker forestwatch
up:
	docker compose up --build
