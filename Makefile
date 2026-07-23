# ============================================================
# PricePulse — Makefile
# ============================================================
# Run 'make help' to see all available commands.
# ============================================================

.PHONY: help setup install db-up db-down db-reset db-test lint format test dashboard clean

help: ## Show this help message
	@echo.
	@echo   PricePulse - Available Commands
	@echo   ================================
	@echo.
	@echo   setup        Create venv and install all dependencies
	@echo   install      Install dependencies into current venv
	@echo   db-up        Start PostgreSQL via Docker Compose
	@echo   db-down      Stop PostgreSQL
	@echo   db-reset     Stop PostgreSQL and delete all data
	@echo   db-test      Test database connection
	@echo   lint         Run ruff linter
	@echo   format       Run ruff formatter
	@echo   test         Run pytest
	@echo   dashboard    Launch Streamlit dashboard
	@echo   clean        Remove caches and temp files
	@echo.

# --- Setup ---
setup: ## Create virtual environment and install dependencies
	python -m venv venv
	venv\Scripts\pip install -r requirements.txt
	venv\Scripts\playwright install chromium

install: ## Install dependencies into current venv
	pip install -r requirements.txt

# --- Database ---
db-up: ## Start PostgreSQL via Docker Compose
	docker-compose up -d db

db-down: ## Stop all Docker services
	docker-compose down

db-reset: ## Stop Docker services and delete volumes
	docker-compose down -v

db-test: ## Test database connection
	python scripts/test_db_connection.py

# --- Quality ---
lint: ## Run ruff linter
	ruff check src/ tests/ config/ scripts/

format: ## Run ruff formatter
	ruff format src/ tests/ config/ scripts/

test: ## Run pytest with coverage
	pytest tests/ -v --cov=src --cov-report=term-missing

# --- Dashboard ---
dashboard: ## Launch Streamlit dashboard
	streamlit run dashboard/app.py

# --- Cleanup ---
clean: ## Remove caches and temp files
	if exist __pycache__ rmdir /s /q __pycache__
	if exist .pytest_cache rmdir /s /q .pytest_cache
	if exist .ruff_cache rmdir /s /q .ruff_cache
	if exist htmlcov rmdir /s /q htmlcov
	for /r %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
