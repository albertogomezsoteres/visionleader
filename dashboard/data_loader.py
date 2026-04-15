"""Cached loaders for the experiment results consumed by the dashboard."""
import streamlit as st

from utils import (
    load_csv_expanded,
    load_csv_reduced,
    load_environment_info,
)


@st.cache_data
def load_all_data():
    try:
        df_expanded = load_csv_expanded()
        df_reduced = load_csv_reduced()
        env_info = load_environment_info()
        return df_expanded, df_reduced, env_info
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None, None, None
