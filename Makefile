# Makefile for the data-simulator

.PHONY: help install test up down restart logs status tick clean

# Pull SIM_PORT (and seed/data paths used by docker compose) from .env if present.
-include .env
export
SIM_PORT ?= 6030

VENV := .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Create the venv and install dev dependencies
	python3 -m venv $(VENV)
	$(PIP) install -r requirements-dev.txt

test: ## Run the test suite with coverage (same command as CI)
	$(PY) -m pytest -m "not skip" --color=yes --junitxml=reports/junit_report.xml --cov=src --cov-report term --cov-report html:reports/coverage -W ignore::DeprecationWarning

up: ## Build and start the simulator (detached)
	docker compose up --build -d

down: ## Stop and remove the simulator container
	docker compose down

restart: ## Restart the simulator (picks up settings.json changes)
	docker compose restart

logs: ## Follow the simulator logs
	docker compose logs -f

status: ## Print the live status of every source
	@curl -s localhost:$(SIM_PORT)/status | python3 -m json.tool

tick: ## Force a tick now: make tick SRC=radar|glm|wrf
	@curl -s -X POST localhost:$(SIM_PORT)/tick/$(SRC); echo

clean: ## Stop the container and remove orphans
	docker compose down --remove-orphans
