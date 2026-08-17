SHELL := /bin/bash
COMPOSE_ENV_FILE ?= $(if $(wildcard backend/.env),backend/.env,backend/.env.example)

.PHONY: help bootstrap venv-backend install-backend install-frontend ensure-backend-env \
	run-backend run-frontend format lint test test-backend eval-backend eval-foundry eval-all \
	test-e2e test-e2e-selected-thread manual-matrix run-mock-mcp up down logs ps docker-test \
	validate-quick validate-full test-skills test-scripts test-deployment-profile clean \
	azure-profile-apply azure-iac-build azure-package azure-preflight azure-bootstrap \
	azure-postgres-schema azure-postgres-credentials azure-build-images azure-app-deploy \
	azure-verify azure-smoke azure-domain-e2e azure-browser-e2e azure-model-preflight \
	azure-eval azure-telemetry azure-evidence azure-release

help:
	@echo "Local: make test eval-backend test-e2e docker-test"
	@echo "Contracts: make test-skills test-scripts test-deployment-profile azure-iac-build"
	@echo "Bootstrap (reviewed only): AZURE_BOOTSTRAP_APPROVED=true make azure-bootstrap"
	@echo "Routine app-only release: make azure-release"

bootstrap: install-backend install-frontend

venv-backend:
	cd backend && python3 -m venv .venv

install-backend: venv-backend
	cd backend && . .venv/bin/activate && pip install -r requirements-dev.txt

install-frontend:
	cd frontend && npm install
	cd scripts/playwright && npm install

ensure-backend-env:
	test -d backend/.venv || $(MAKE) venv-backend
	. backend/.venv/bin/activate && python -c "import pytest" >/dev/null 2>&1 || $(MAKE) install-backend

run-backend: ensure-backend-env
	./infra/azure-apphosted/runtime/entrypoint.sh

run-frontend:
	cd frontend && npm run dev

format: ensure-backend-env
	cd backend && . .venv/bin/activate && ruff format .

lint: ensure-backend-env
	cd backend && . .venv/bin/activate && ruff check .

test: lint test-backend

test-backend: ensure-backend-env
	./scripts/local/run_with_test_postgres.sh bash -lc 'cd backend && . .venv/bin/activate && pytest -q'

eval-backend: ensure-backend-env
	./scripts/local/run_with_test_postgres.sh bash -lc 'cd backend && . .venv/bin/activate && python -m evals.eval_runner'

eval-foundry: ensure-backend-env
	./scripts/azure/run_foundry_eval.sh

eval-all: eval-backend eval-foundry

test-e2e-selected-thread:
	@if [[ -n "$${PLAYWRIGHT_BASE_URL:-}" ]]; then \
		cd frontend && PLAYWRIGHT_BASE_URL="$${PLAYWRIGHT_BASE_URL}" npm run test:e2e -- tests/e2e/selected-thread-integrations.spec.ts; \
	else \
		cd frontend && npm run test:e2e -- tests/e2e/selected-thread-integrations.spec.ts; \
	fi

test-e2e:
	@set -euo pipefail; \
	if [[ -n "$${PLAYWRIGHT_BASE_URL:-}" ]]; then \
		cd scripts/playwright && npm run test:e2e; \
		PLAYWRIGHT_BASE_URL="$${PLAYWRIGHT_BASE_URL}" $(MAKE) -C "$(CURDIR)" test-e2e-selected-thread; \
	else \
		free_port() { python3 scripts/local/find_free_port.py; }; \
		backend_port="$${E2E_BACKEND_HOST_PORT:-$$(free_port)}"; \
		postgres_port="$${E2E_POSTGRES_HOST_PORT:-$$(free_port)}"; \
		mock_mcp_port="$${E2E_MOCK_MCP_HOST_PORT:-$$(free_port)}"; \
		compose_project="$${E2E_COMPOSE_PROJECT_NAME:-langgraph-azure-e2e-$${backend_port}}"; \
		cleanup() { \
			if [[ -n "$${frontend_pid:-}" ]]; then kill "$${frontend_pid}" 2>/dev/null || true; wait "$${frontend_pid}" 2>/dev/null || true; fi; \
			COMPOSE_PROJECT_NAME="$${compose_project}" BACKEND_HOST_PORT="$${backend_port}" POSTGRES_HOST_PORT="$${postgres_port}" MOCK_MCP_HOST_PORT="$${mock_mcp_port}" docker compose --env-file $(COMPOSE_ENV_FILE) down --remove-orphans >/dev/null 2>&1 || true; \
		}; \
		trap cleanup EXIT; \
		COMPOSE_PROJECT_NAME="$${compose_project}" BACKEND_HOST_PORT="$${backend_port}" POSTGRES_HOST_PORT="$${postgres_port}" MOCK_MCP_HOST_PORT="$${mock_mcp_port}" docker compose --env-file $(COMPOSE_ENV_FILE) up --build -d backend; \
		backend_url="http://127.0.0.1:$${backend_port}"; \
		for _ in {1..60}; do curl -fsS "$${backend_url}/health" >/dev/null && break; sleep 1; done; \
		curl -fsS "$${backend_url}/health" >/dev/null; \
		frontend_port="$$(python3 scripts/local/find_free_port.py)"; \
		frontend_url="http://127.0.0.1:$${frontend_port}"; \
		(cd frontend && VITE_PROXY_TARGET="$${backend_url}" node_modules/.bin/vite --host 127.0.0.1 --port "$${frontend_port}" --strictPort) >/dev/null 2>&1 & \
		frontend_pid="$$!"; \
		for _ in {1..30}; do curl -fsS "$${frontend_url}" >/dev/null && break; sleep 1; done; \
		PLAYWRIGHT_BASE_URL="$${frontend_url}" bash -c 'cd scripts/playwright && npm run test:e2e'; \
		PLAYWRIGHT_BASE_URL="$${frontend_url}" $(MAKE) -C "$(CURDIR)" test-e2e-selected-thread; \
	fi

manual-matrix:
	scripts/manual/run-manual-matrix.sh "$${API_URL:-http://localhost:8000}" $${MANUAL_MATRIX_ARGS:-}

run-mock-mcp: ensure-backend-env
	. backend/.venv/bin/activate && uvicorn scripts.mcp.mock_mcp_server:app --reload --port 8011

up:
	docker compose --env-file $(COMPOSE_ENV_FILE) up --build -d backend frontend mock-mcp

down:
	docker compose --env-file $(COMPOSE_ENV_FILE) down --remove-orphans

logs:
	docker compose --env-file $(COMPOSE_ENV_FILE) logs -f --tail=200

ps:
	docker compose --env-file $(COMPOSE_ENV_FILE) ps

docker-test:
	@set -euo pipefail; \
	free_port() { python3 scripts/local/find_free_port.py; }; \
	backend_port="$$(free_port)"; frontend_port="$$(free_port)"; postgres_port="$$(free_port)"; mock_mcp_port="$$(free_port)"; \
	compose_project="langgraph-azure-docker-$${backend_port}"; \
	trap 'COMPOSE_PROJECT_NAME="$$compose_project" BACKEND_HOST_PORT="$$backend_port" FRONTEND_HOST_PORT="$$frontend_port" POSTGRES_HOST_PORT="$$postgres_port" MOCK_MCP_HOST_PORT="$$mock_mcp_port" docker compose --env-file $(COMPOSE_ENV_FILE) down --remove-orphans >/dev/null 2>&1 || true' EXIT; \
	COMPOSE_PROJECT_NAME="$$compose_project" BACKEND_HOST_PORT="$$backend_port" FRONTEND_HOST_PORT="$$frontend_port" POSTGRES_HOST_PORT="$$postgres_port" MOCK_MCP_HOST_PORT="$$mock_mcp_port" docker compose --env-file $(COMPOSE_ENV_FILE) --profile test up --build --abort-on-container-exit --exit-code-from playwright playwright

validate-quick:
	$(MAKE) test-scripts test-deployment-profile

validate-full:
	$(MAKE) test
	$(MAKE) eval-backend
	$(MAKE) test-scripts
	$(MAKE) test-deployment-profile
	$(MAKE) test-skills
	./scripts/skills/design-review-skill.sh

test-skills:
	python3 scripts/skills/validate-skills.py

test-scripts: ensure-backend-env
	PYTHONPATH=backend:. backend/.venv/bin/pytest -q \
		scripts/azure/tests/test_postgres_runtime_credentials.py \
		scripts/azure/tests/test_azure_hosting_contract.py \
		scripts/azure/tests/test_release_evidence.py
	bash -n scripts/azure/*.sh deployment/*.sh deployment/tests/*.sh

test-deployment-profile:
	bash deployment/tests/test-profile.sh

azure-profile-apply:
	bash deployment/apply-azd-profile.sh "$${AZURE_DEPLOYMENT_PROFILE:-deployment/profiles/azure-hosted.env}"

azure-iac-build:
	az bicep build --file infra/azure-apphosted/iac/main.bicep

azure-package:
	docker build --quiet -f backend/Dockerfile backend
	docker build --quiet -f frontend/Dockerfile frontend

azure-preflight:
	scripts/azure/preflight.sh

azure-bootstrap:
	scripts/azure/bootstrap.sh

azure-postgres-schema:
	scripts/azure/bootstrap_postgres_schema.sh

azure-postgres-credentials:
	scripts/azure/provision_postgres_runtime_credentials.sh

azure-build-images:
	scripts/azure/build_images.sh

azure-app-deploy:
	scripts/azure/deploy_apps.sh

azure-verify:
	scripts/azure/verify_deployment.sh

azure-smoke:
	scripts/azure/smoke.sh

azure-domain-e2e:
	scripts/azure/domain_e2e.sh

azure-browser-e2e:
	scripts/azure/browser_e2e.sh

azure-model-preflight:
	scripts/azure/preflight_models.sh

azure-eval:
	scripts/azure/run_foundry_eval.sh

azure-telemetry:
	scripts/azure/verify_telemetry.sh

azure-evidence:
	python3 scripts/azure/release_evidence.py aggregate --release-id "$${AZURE_RELEASE_ID:?AZURE_RELEASE_ID is required}"

azure-release:
	scripts/azure/release.sh

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf backend/.pytest_cache scripts/playwright/test-results scripts/playwright/playwright-report frontend/test-results frontend/playwright-report
