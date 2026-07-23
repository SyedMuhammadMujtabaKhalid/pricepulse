import streamlit as st
import pandas as pd
from sqlalchemy import text
import plotly.express as px

from src.storage.database import get_engine

st.set_page_config(page_title="Price Tracker | PricePulse", layout="wide")

st.title("📈 Price Tracker")

try:
    engine = get_engine()
    
    # Fetch Products for filter
    with engine.connect() as conn:
        products = pd.read_sql("SELECT id, sku, name FROM products", conn)
        
    if products.empty:
        st.warning("No products found in the database. Run `python scripts/seed_db.py` first.")
    else:
        # Filters
        selected_sku = st.selectbox("Select Product", options=products['sku'].tolist(), 
                                    format_func=lambda x: f"{x} - {products[products['sku']==x]['name'].iloc[0]}")
        
        selected_prod_id = products[products['sku'] == selected_sku]['id'].iloc[0]
        
        # Fetch Price History
        with engine.connect() as conn:
            history_query = text("""
                SELECT pr.scraped_at, pr.price, c.name as competitor
                FROM price_records pr
                JOIN competitors c ON pr.competitor_id = c.id
                WHERE pr.product_id = :pid
                ORDER BY pr.scraped_at ASC
            """)
            df = pd.read_sql(history_query, conn, params={"pid": selected_prod_id})
            
        if df.empty:
            st.info("No price history available for this product.")
        else:
            # Plot
            fig = px.line(
                df, x="scraped_at", y="price", color="competitor", 
                markers=True, title="Price History over Time",
                labels={"scraped_at": "Date", "price": "Price (USD)", "competitor": "Competitor"}
            )
            fig.update_yaxes(tickprefix="$")
            st.plotly_chart(fig, use_container_width=True)
            
            # Raw Data
            st.subheader("Raw Data")
            st.dataframe(df.sort_values(by="scraped_at", ascending=False), use_container_width=True)

except Exception as e:
    st.error("Could not load data.")
    st.exception(e)
