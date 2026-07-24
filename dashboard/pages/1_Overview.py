import streamlit as st
import pandas as pd
from sqlalchemy import text

from src.storage.database import get_engine

st.set_page_config(page_title="Overview | PricePulse", layout="wide")

st.title("Executive Overview")

try:
    engine = get_engine()

    # KPIs
    with engine.connect() as conn:
        kpi_query = text("""
            SELECT 
                (SELECT count(*) FROM products) as prod_count,
                (SELECT count(*) FROM competitors WHERE is_active=true) as comp_count,
                (SELECT count(*) FROM alerts WHERE is_acknowledged=false) as active_alerts
        """)
        kpis = conn.execute(kpi_query).fetchone()

    col1, col2, col3 = st.columns(3)
    col1.metric("Products Tracked", kpis.prod_count if kpis else 0)
    col2.metric("Active Competitors", kpis.comp_count if kpis else 0)
    col3.metric(
        "Unacknowledged Alerts",
        kpis.active_alerts if kpis else 0,
        delta_color="inverse",
        delta="Needs Attention" if kpis and kpis.active_alerts > 0 else "All Good",
    )

    st.divider()

    # Recent Alerts
    st.subheader("🚨 Critical Alerts")
    with engine.connect() as conn:
        alerts_df = pd.read_sql(
            "SELECT severity, message, created_at FROM alerts WHERE is_acknowledged=false ORDER BY created_at DESC LIMIT 5",
            conn,
        )

    if not alerts_df.empty:
        for _, row in alerts_df.iterrows():
            if row["severity"] == "critical":
                st.error(
                    f"[{row['created_at'].strftime('%Y-%m-%d %H:%M')}] **{row['message']}**"
                )
            elif row["severity"] == "high":
                st.warning(
                    f"[{row['created_at'].strftime('%Y-%m-%d %H:%M')}] **{row['message']}**"
                )
            else:
                st.info(
                    f"[{row['created_at'].strftime('%Y-%m-%d %H:%M')}] {row['message']}"
                )
    else:
        st.success("No active alerts.")

except Exception as e:
    st.error("Could not load data. Ensure database is running.")
    st.exception(e)
