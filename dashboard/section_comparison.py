"""Comparison section."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from PIL import Image
import json

from utils import (
    load_csv_expanded,
    load_csv_reduced,
    load_environment_info,
    load_model_metrics,
    load_model_results,
    get_available_models,
    get_confusion_matrix_path,
    extract_model_name,
    get_all_confusion_matrices,
    filter_models,
    format_metric_value,
)
from components import (
    create_section_header,
    create_kpi_card,
    get_plotly_layout,
    COLORS,
)


def render(df_expanded, df_reduced, env_info):
    # Custom header for Comparison section
    st.markdown("""
        <div style="padding: 0 0 1rem 0; margin: 0;">
            <h1 style="font-size: 1.75rem; font-weight: 700; color: #1565C0; margin: 0; padding: 0; line-height: 1.75rem;">
                Model Comparison
            </h1>
            <p style="font-size: 0.9rem; color: #6B7280; margin: 0.25rem 0 0 0; padding: 0;">
                Performance metrics across models
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # Initialize df_filtered with df_expanded (no filters applied yet)
    df_filtered = df_expanded.copy()
    
    # Column selector
    available_cols = df_filtered.columns.tolist()
    default_cols = ["Model ID", "Version", "Size", "Type", "Resolution", 
                    "Exact Match", "Keyword Recall", "BERTScore F1", 
                    "Throughput (images/sec)", "VRAM Usage (GB)"]
    default_cols = [c for c in default_cols if c in available_cols]
    
    selected_cols = st.multiselect(
        "Select columns to display",
        available_cols,
        default=default_cols
    )
    
    if selected_cols:
        # Sort options
        col_sort, _ = st.columns([2, 3])
        with col_sort:
            sort_col = st.selectbox("Sort by", selected_cols, index=selected_cols.index("Exact Match") if "Exact Match" in selected_cols else 0)
        sort_order = st.radio("Order", ["Descending", "Ascending"], horizontal=True)
        
        display_df = df_filtered[selected_cols].sort_values(
            sort_col, 
            ascending=(sort_order == "Ascending")
        )
        
        # Remove empty rows (rows where all values are NaN or empty)
        display_df = display_df.dropna(how='all')
        # Also remove rows where all values are empty strings or whitespace
        mask = display_df.astype(str).apply(lambda row: row.str.strip().eq('').all(), axis=1)
        display_df = display_df[~mask]
        
        st.dataframe(display_df, use_container_width=True, hide_index=True, height=500)
    
    st.markdown('</div>', unsafe_allow_html=True)

