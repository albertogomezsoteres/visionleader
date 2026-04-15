"""Individual Model section."""
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
    # Custom header for Individual Model section
    st.markdown("""
        <div style="padding: 0 0 1rem 0; margin: 0;">
            <h1 style="font-size: 1.75rem; font-weight: 700; color: #1565C0; margin: 0; padding: 0; line-height: 1.75rem;">
                Individual Model Analysis
            </h1>
            <p style="font-size: 0.9rem; color: #6B7280; margin: 0.25rem 0 0 0; padding: 0;">
                Detailed performance metrics and configuration for a selected model
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    available_models = get_available_models()
    
    # Create a narrower container for the selectbox
    col_select, _ = st.columns([1.5, 3.5])
    with col_select:
        selected_model = st.selectbox("Select model for detailed analysis", available_models)
    
    if selected_model:
        metrics = load_model_metrics(selected_model)
        model_row = df_expanded[df_expanded["Model ID"].str.contains(selected_model)]
        
        if not model_row.empty:
            row = model_row.iloc[0]
            
            # Model Info Cards
            info_cols = st.columns(4)
            with info_cols[0]:
                st.markdown(create_kpi_card("📋", row.get("Version", "N/A"), "Version", "purple"), unsafe_allow_html=True)
            with info_cols[1]:
                st.markdown(create_kpi_card("📐", row.get("Size", "N/A"), "Size", "blue"), unsafe_allow_html=True)
            with info_cols[2]:
                st.markdown(create_kpi_card("🔧", row.get("Type", "N/A"), "Type", "green"), unsafe_allow_html=True)
            with info_cols[3]:
                st.markdown(create_kpi_card("🖼️", f"{row.get('Resolution', 'N/A')}", "Resolution", "orange"), unsafe_allow_html=True)
            
            st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
            
            # Performance Metrics
            perf_cols = st.columns(4)
            metrics_list = [
                ("Exact Match", "🎯", "purple"),
                ("Keyword Recall", "🔑", "blue"),
                ("BERTScore F1", "📊", "green"),
                ("Throughput (images/sec)", "⚡", "orange")
            ]
            
            for col, (metric, icon, color) in zip(perf_cols, metrics_list):
                with col:
                    value = row.get(metric, 0)
                    if pd.notna(value):
                        display_val = f"{value:.4f}" if value < 10 else f"{value:.2f}"
                        st.markdown(create_kpi_card(icon, display_val, metric, color), unsafe_allow_html=True)

