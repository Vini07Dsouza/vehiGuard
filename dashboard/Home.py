import sqlite3

import pandas as pd
import streamlit as st

st.set_page_config(page_title="VehiLence - Police Console", layout="wide")
st.title("VehiLence - Police Console")

con = sqlite3.connect("data/vehilence.db")

tab_alerts, tab_search = st.tabs(["Alerts", "Search vehicle"])

with tab_alerts:
    st.subheader("Recent alerts")
    alerts = pd.read_sql(
        "SELECT created_at, type, severity, status, session_id "
        "FROM alerts ORDER BY created_at DESC LIMIT 100",
        con,
    )
    st.dataframe(alerts)
    st.button("Refresh")

with tab_search:
    plate = st.text_input("Plate number", placeholder="KA19AB1234").strip().upper()
    if plate:
        vehicle = pd.read_sql(
            "SELECT * FROM vehicles WHERE plate_no = ?", con, params=(plate,)
        )
        if vehicle.empty:
            st.error("Not found in registry (UNREGISTERED)")
        else:
            st.dataframe(vehicle)
