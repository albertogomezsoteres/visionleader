"""Downloads section."""
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
    # Custom header for Downloads section
    st.markdown("""
        <div style="padding: 0 0 1rem 0; margin: 0;">
            <h1 style="font-size: 1.75rem; font-weight: 700; color: #1565C0; margin: 0; padding: 0; line-height: 1.75rem;">
                Data Downloads
            </h1>
            <p style="font-size: 0.9rem; color: #6B7280; margin: 0.25rem 0 0 0; padding: 0;">
                Download model data, metrics, and experiment metadata
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.markdown("""
            <div class="chart-header">
                <div>
                    <div class="chart-title">📊 Comparative Data</div>
                    <div class="chart-subtitle">Download aggregated comparison tables across models</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        csv_expanded = df_expanded.to_csv(index=False)
        st.download_button(
            label="📥 Download Full CSV (28 columns)",
            data=csv_expanded,
            file_name="all_models_comparison_expanded.csv",
            mime="text/csv"
        )
        
        st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
        
        csv_reduced = df_reduced.to_csv(index=False)
        st.download_button(
            label="📥 Download Reduced CSV (11 columns)",
            data=csv_reduced,
            file_name="all_models_comparison_reduced.csv",
            mime="text/csv"
        )
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.markdown("""
            <div class="chart-header">
                <div>
                    <div class="chart-title">🔬 Individual Metrics</div>
                    <div class="chart-subtitle">Download detailed metrics for a selected model</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Create a narrower container for the selectbox
        col_select, _ = st.columns([2, 3])
        with col_select:
            selected_model_dl = st.selectbox("Select model", get_available_models(), key="model_dl")
        
        if selected_model_dl:
            metrics = load_model_metrics(selected_model_dl)
            if metrics:
                metrics_json = json.dumps(metrics, indent=2)
                st.download_button(
                    label=f"📥 Download {selected_model_dl} metrics",
                    data=metrics_json,
                    file_name=f"{selected_model_dl}_metrics.json",
                    mime="application/json"
                )
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Environment info
    if env_info:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.markdown("""
            <div class="chart-header">
                <div>
                    <div class="chart-title">⚙️ Environment Information</div>
                    <div class="chart-subtitle">Download experiment configuration and system setup</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        env_json = json.dumps(env_info, indent=2)
        st.download_button(
            label="📥 Download Environment Info",
            data=env_json,
            file_name="experiment_environment.json",
            mime="application/json"
        )
        st.markdown('</div>', unsafe_allow_html=True)

