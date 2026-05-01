.PHONY: dev demo prod pull-model init-db seed-demo test lint migrate tunnel

dev:
	docker compose up --build

demo:
	docker compose -f docker-compose.demo.yml up --build -d

prod:
	docker compose -f docker-compose.prod.yml up --build -d

pull-model:
	docker compose exec ollama ollama pull llama3.2:3b

init-db:
	docker compose exec backend alembic upgrade head
	docker compose exec backend python scripts/init_db.py

seed-demo:
	docker compose exec backend python scripts/seed_demo.py

migrate:
	docker compose exec backend alembic upgrade head

test:
	docker compose exec backend pytest tests/ -v

lint:
	docker compose exec backend mypy app/
	docker compose exec backend ruff check app/

logs:
	docker compose logs -f backend worker

stop:
	docker compose down

clean:
	docker compose down -v
	rm -rf data/chromadb data/documents data/arqive_dev.db 2>/dev/null || true
