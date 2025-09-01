# Makefile for AutoScorer - convenience targets

PROJECT_NAME=autoscorer
COMPOSE=docker compose

.PHONY: help build up down restart logs ps api worker flower sh-api sh-worker tail-api tail-worker fmt test

help:
	@echo "Available targets:"
	@echo "  make build      - Build docker image"
	@echo "  make up         - Start all services (api, worker, redis, flower)"
	@echo "  make down       - Stop and remove services"
	@echo "  make restart    - Restart services"
	@echo "  make logs       - Follow all logs"
	@echo "  make ps         - Show container status"
	@echo "  make api        - Show API logs"
	@echo "  make worker     - Show worker logs"
	@echo "  make flower     - Open Flower in browser (http://localhost:5555)"
	@echo "  make sh-api     - Shell into API container"
	@echo "  make sh-worker  - Shell into Worker container"
	@echo "  make tail-api   - Tail API container log"
	@echo "  make tail-worker- Tail Worker container log"

build:
	DOCKER_BUILDKIT=0 $(COMPOSE) build

up:
	DOCKER_BUILDKIT=0 $(COMPOSE) up -d --build

down:
	$(COMPOSE) down -v

restart:
	$(COMPOSE) down
	DOCKER_BUILDKIT=0 $(COMPOSE) up -d --build

logs:
	$(COMPOSE) logs -f --tail=200

ps:
	$(COMPOSE) ps

api:
	$(COMPOSE) logs -f api

worker:
	$(COMPOSE) logs -f worker

flower:
	@open http://localhost:5555 || true
	$(COMPOSE) logs -f flower

sh-api:
	$(COMPOSE) exec api bash || $(COMPOSE) exec api sh

sh-worker:
	$(COMPOSE) exec worker bash || $(COMPOSE) exec worker sh

# Tail container log files produced by tasks inside example workspaces
tail-api:
	@echo "Tailing API app log (if any)"
	$(COMPOSE) exec api sh -lc 'tail -n 200 -f logs/autoscorer.log || true'

tail-worker:
	@echo "Tailing Worker app log (if any)"
	$(COMPOSE) exec worker sh -lc 'tail -n 200 -f logs/autoscorer.log || true'

fmt:
	@echo "Use ruff/black locally if desired"

test:
	@echo "Run tests locally: pytest -q"
