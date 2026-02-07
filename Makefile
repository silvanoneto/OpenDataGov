.PHONY: help install lint lint-python lint-go lint-tofu lint-md test test-python test-go build compose-up compose-down compose-full-up compose-full-down compose-logs kind-up kind-down kind-load tofu-init tofu-apply tofu-destroy proto clean

PYTHON_SERVICES := libs/python/odg-core services/governance-engine services/lakehouse-agent services/data-expert
GO_SERVICES := services/gateway

COMPOSE_FILE := deploy/docker-compose/docker-compose.yml
COMPOSE_FULL := deploy/docker-compose/docker-compose.full.yml
KIND_CLUSTER := opendatagov
TOFU_DIR := deploy/tofu
APP_IMAGES := opendatagov/governance-engine opendatagov/lakehouse-agent opendatagov/data-expert opendatagov/gateway

install: ## Set up local dev environment
	@./scripts/setup-dev.sh

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Lint ─────────────────────────────────────────────────

lint: lint-python lint-go lint-tofu lint-md ## Run all linters

lint-python: ## Run ruff + mypy on Python code
	@for svc in $(PYTHON_SERVICES); do \
		echo "==> Linting $$svc"; \
		(cd $$svc && uv run ruff check . && uv run mypy .) || exit 1; \
	done

lint-go: ## Run golangci-lint on Go code
	@for svc in $(GO_SERVICES); do \
		echo "==> Linting $$svc"; \
		(cd $$svc && golangci-lint run ./...) || exit 1; \
	done

lint-tofu: ## Run tofu fmt check + tflint on OpenTofu code
	@echo "==> Checking tofu format"
	cd $(TOFU_DIR) && tofu fmt -check -diff
	@if command -v tflint >/dev/null 2>&1; then \
		echo "==> Running tflint"; \
		cd $(TOFU_DIR) && tflint --init && tflint; \
	else \
		echo "==> tflint not installed, skipping"; \
	fi

lint-md: ## Run mdformat on Markdown files
	@echo "==> Checking markdown format"
	uv run mdformat --check README.md CONTRIBUTING.md SECURITY.md docs/

# ─── Test ─────────────────────────────────────────────────

test: test-python test-go ## Run all tests

test-python: ## Run pytest on Python services
	@for svc in $(PYTHON_SERVICES); do \
		echo "==> Testing $$svc"; \
		(cd $$svc && uv run pytest --cov -q) || exit 1; \
	done

test-go: ## Run go test on Go services
	@for svc in $(GO_SERVICES); do \
		echo "==> Testing $$svc"; \
		(cd $$svc && go test ./... -v) || exit 1; \
	done

# ─── Build ────────────────────────────────────────────────

build: ## Build all Docker images via docker compose
	docker compose -f $(COMPOSE_FILE) build
	@for img in $(APP_IMAGES); do \
		svc=$$(echo $$img | sed 's|opendatagov/||'); \
		docker tag docker-compose-$$svc:latest $$img:0.1.0; \
	done
	@echo "==> Tagged images: $(APP_IMAGES)"

# ─── Compose ──────────────────────────────────────────────

compose-up: ## Start quick-start stack
	docker compose -f $(COMPOSE_FILE) up -d

compose-down: ## Stop stack
	docker compose -f $(COMPOSE_FILE) down

compose-full-up: ## Start full stack (with Kafka, Grafana, VictoriaMetrics)
	docker compose -f $(COMPOSE_FILE) -f $(COMPOSE_FULL) up -d

compose-full-down: ## Stop full stack
	docker compose -f $(COMPOSE_FILE) -f $(COMPOSE_FULL) down

compose-logs: ## Tail logs from all services
	docker compose -f $(COMPOSE_FILE) logs -f

# ─── Kind + Tofu ─────────────────────────────────────────

kind-up: build ## Create kind cluster, load images, deploy via tofu
	@kind create cluster --name $(KIND_CLUSTER) --config deploy/kind/kind-config.yaml 2>/dev/null || true
	@for img in $(APP_IMAGES); do \
		echo "==> Loading $$img:0.1.0 into kind"; \
		kind load docker-image $$img:0.1.0 --name $(KIND_CLUSTER); \
	done
	cd $(TOFU_DIR) && tofu init -input=false && tofu apply -auto-approve

kind-load: build ## Rebuild, reload images, and restart pods
	@for img in $(APP_IMAGES); do \
		echo "==> Loading $$img:0.1.0 into kind"; \
		kind load docker-image $$img:0.1.0 --name $(KIND_CLUSTER); \
	done
	kubectl rollout restart deploy -n opendatagov -l app.kubernetes.io/part-of=opendatagov

kind-down: ## Delete kind cluster and clean tofu state
	kind delete cluster --name $(KIND_CLUSTER)
	rm -f $(TOFU_DIR)/terraform.tfstate $(TOFU_DIR)/terraform.tfstate.backup

tofu-init: ## Initialize tofu providers
	cd $(TOFU_DIR) && tofu init -input=false

tofu-apply: ## Apply tofu (deploy/update helm release)
	cd $(TOFU_DIR) && tofu apply -auto-approve

tofu-destroy: ## Destroy tofu-managed resources
	cd $(TOFU_DIR) && tofu destroy -auto-approve

# ─── Proto ────────────────────────────────────────────────

proto: ## Generate protobuf code (Go + Python)
	./scripts/generate-proto.sh

# ─── Clean ────────────────────────────────────────────────

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
