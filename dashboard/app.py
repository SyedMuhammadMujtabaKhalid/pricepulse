"""
PricePulse — Streamlit Dashboard Entry Point
=============================================

Main app file for the Streamlit dashboard.
Run: `make dashboard` or `streamlit run dashboard/app.py`
"""

import sys
from pathlib import Path

# Add project root to python path so dashboard can import src/
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
from sqlalchemy import text

from config.settings import get_settings
from src.storage.database import get_engine, Base
import src.storage.models  # noqa: F401 — register models with Base.metadata


st.set_page_config(
    page_title="PricePulse | Intelligence",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

def main():
    st.title("🎯 PricePulse")
    st.subheader("Competitor Price Intelligence Platform")
    
    st.markdown("""
    Welcome to PricePulse. Use the sidebar to navigate to specific reports:
    
    * **Overview**: High-level KPIs and critical alerts.
    * **Price Tracker**: Detailed historical price charts per product.
    
    *Data refreshes automatically on load.*
    """)
    
    st.divider()
    
    # Check DB Connection silently
    try:
        engine = get_engine()
        # Ensure tables exist (idempotent)
        Base.metadata.create_all(bind=engine)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT count(*) FROM products")).scalar()
            
        st.success(f"✅ Database connected. Tracking {result} products.")
    except Exception as e:
        st.error(f"❌ Database connection failed: {e}")
        st.info("💡 Hint: Did you run `make db-up` and `python scripts/seed_db.py`?")


if __name__ == "__main__":
    main()
