# 🎯 PricePulse

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)
![Playwright](https://img.shields.io/badge/Playwright-Enabled-green)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-red)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

**PricePulse** is a production-grade Competitor Price Intelligence Platform designed for e-commerce businesses. It automatically extracts, validates, normalizes, and analyzes product prices across multiple competitor sources to provide actionable pricing intelligence.

---

## 🏗️ System Architecture

PricePulse uses a clean, modular pipeline architecture:

1. **Extraction Layer**: Pluggable Source Adapters (`httpx` for APIs, `playwright` for scraping, `csv` for historical data).
2. **Validation Layer**: `pydantic` schemas enforce strict data contracts and deduplication rules.
3. **Storage Layer**: Relational data warehousing in `PostgreSQL` using `SQLAlchemy 2.0` and `Alembic` for migrations.
4. **Intelligence Engine**: Post-extraction processor that identifies significant price drops and generates alerts.
5. **Analytics Dashboard**: Interactive `Streamlit` application with `plotly` visualizations.
6. **Automation**: `GitHub Actions` for CI/CD and scheduled pipeline execution.

## 🚀 Quickstart

### Prerequisites
- Python 3.11+
- Docker Desktop (for PostgreSQL)

### Installation

1. **Clone and setup environment**:
   ```bash
   git clone https://github.com/yourusername/pricepulse.git
   cd pricepulse
   make setup
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials if necessary
   ```

3. **Start the Database**:
   ```bash
   make db-up
   make db-test  # Verify connection
   ```

4. **Initialize Schema and Seed Data**:
   ```bash
   # (Once Docker is running)
   alembic upgrade head
   python scripts/seed_db.py
   ```

5. **Launch the Dashboard**:
   ```bash
   make dashboard
   ```
   The dashboard will be available at `http://localhost:8501`.

## 📁 Project Structure

Following enterprise Data Engineering standards:
- `config/`: Pydantic settings and environment management.
- `src/sources/`: Pluggable extraction adapters.
- `src/quality/`: Validation schemas and anomaly detection.
- `src/storage/`: SQLAlchemy ORM models and database connections.
- `src/engine/`: Business logic for price change detection.
- `src/pipeline/`: Main ETL orchestrator.
- `dashboard/`: Streamlit interactive front-end.
- `.github/workflows/`: CI and scheduled jobs.

## 🛠️ Engineering Trade-offs

- **Playwright vs. BeautifulSoup**: Playwright was chosen for the scraping source because modern e-commerce sites are heavily JavaScript-rendered. Headless Chrome is launched with resource blocking (images, CSS) to optimize speed.
- **Python runner vs. Airflow**: Airflow is overkill for a simple MVP pipeline running twice a day. A custom `PipelineRunner` executed via GitHub Actions cron provides maximum reliability with minimum infrastructure overhead.
- **Append-only Price History**: We never `UPDATE` price records. Instead, we `INSERT` new records and use the `price_changes` materialized view to detect drops. This provides a perfect audit trail.

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.
