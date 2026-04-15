"""Performance section."""
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
    # Custom header for Performance section
    st.markdown("""
        <div style="padding: 0 0 1rem 0; margin: 0;">
            <h1 style="font-size: 1.75rem; font-weight: 700; color: #1565C0; margin: 0; padding: 0; line-height: 1.75rem;">
                Performance Analysis
            </h1>
            <p style="font-size: 0.9rem; color: #6B7280; margin: 0.25rem 0 0 0; padding: 0;">
                Computational efficiency and resource usage across models
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # Initialize df_filtered with df_expanded (no filters applied yet)
    df_filtered = df_expanded.copy()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        if "Throughput (images/sec)" in df_filtered.columns:
            fig = px.bar(
                df_filtered.sort_values("Throughput (images/sec)", ascending=False).head(15),
                x="Throughput (images/sec)",
                y="Model ID",
                orientation='h',
                color="Throughput (images/sec)",
                color_continuous_scale=[[0, '#FEF3C7'], [0.5, '#F59E0B'], [1, '#D97706']]
            )
            fig.update_layout(**get_plotly_layout("Throughput Ranking"))
            fig.update_layout(coloraxis_showscale=False, height=500)
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        if "VRAM Usage (GB)" in df_filtered.columns:
            fig = px.bar(
                df_filtered.sort_values("VRAM Usage (GB)", ascending=True).head(15),
                x="VRAM Usage (GB)",
                y="Model ID",
                orientation='h',
                color="VRAM Usage (GB)",
                color_continuous_scale=[[0, '#DCFCE7'], [0.5, '#22C55E'], [1, '#16A34A']]
            )
            fig.update_layout(**get_plotly_layout("VRAM Efficiency"))
            fig.update_layout(coloraxis_showscale=False, height=500)
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Efficiency scatter
    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
    if "Throughput (images/sec)" in df_filtered.columns and "Exact Match" in df_filtered.columns:
        fig = px.scatter(
            df_filtered,
            x="Throughput (images/sec)",
            y="Exact Match",
            color="Size",
            size="VRAM Usage (GB)" if "VRAM Usage (GB)" in df_filtered.columns else None,
            hover_name="Model ID",
            color_discrete_sequence=COLORS['chart_colors']
        )
        fig.update_layout(**get_plotly_layout("Efficiency vs Accuracy Trade-off"))
        fig.update_traces(marker=dict(line=dict(width=1, color='white')))
        st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

