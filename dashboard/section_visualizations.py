"""Visualizations section."""
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
    # Custom header for Visualizations section
    st.markdown("""
        <div style="padding: 0 0 1rem 0; margin: 0;">
            <h1 style="font-size: 1.75rem; font-weight: 700; color: #1565C0; margin: 0; padding: 0; line-height: 1.75rem;">
                Visualizations
            </h1>
            <p style="font-size: 0.9rem; color: #6B7280; margin: 0.25rem 0 0 0; padding: 0;">
                Interactive charts to explore and compare model performance
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # Initialize df_filtered with df_expanded (no filters applied yet)
    df_filtered = df_expanded.copy()
    
    viz_tabs = st.tabs(["Bar Charts", "Scatter Plots", "Radar Chart"])
    
    with viz_tabs[0]:
        # Metric selection outside columns to align charts
        metric_options = ["Exact Match", "Keyword Recall", "BERTScore F1", "BERTScore Recall"]
        metric_options = [m for m in metric_options if m in df_filtered.columns]
        
        # Create a narrower container for the selectbox
        col_select, _ = st.columns([2, 3])
        with col_select:
            selected_metric = st.selectbox("Select metric", metric_options, key="viz_metric_select")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            fig = px.bar(
                df_filtered.nlargest(10, selected_metric),
                x="Model ID",
                y=selected_metric,
                color=selected_metric,
                color_continuous_scale=[[0, '#E9D5FF'], [0.5, '#A855F7'], [1, '#7C3AED']]
            )
            fig.update_layout(**get_plotly_layout(f"Top 10 Models - {selected_metric}"))
            fig.update_layout(coloraxis_showscale=False)
            fig.update_xaxes(tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            if "Size" in df_filtered.columns:
                size_metrics = df_filtered.groupby("Size")[metric_options].mean().reset_index()
                fig = px.bar(
                    size_metrics,
                    x="Size",
                    y=metric_options,
                    barmode="group",
                    color_discrete_sequence=COLORS['chart_colors']
                )
                fig.update_layout(**get_plotly_layout("Average Metrics by Model Size"))
                st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
    
    with viz_tabs[1]:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            x_metric = st.selectbox("X axis", metric_options, key="scatter_x")
            y_metric = st.selectbox("Y axis", metric_options, index=1 if len(metric_options) > 1 else 0, key="scatter_y")
            
            fig = px.scatter(
                df_filtered,
                x=x_metric,
                y=y_metric,
                color="Type" if "Type" in df_filtered.columns else None,
                hover_name="Model ID",
                color_discrete_sequence=COLORS['chart_colors']
            )
            fig.update_layout(**get_plotly_layout(f"{x_metric} vs {y_metric}"))
            fig.update_traces(marker=dict(size=12, line=dict(width=1, color='white')))
            st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            if "Throughput (images/sec)" in df_filtered.columns and "VRAM Usage (GB)" in df_filtered.columns:
                fig = px.scatter(
                    df_filtered,
                    x="VRAM Usage (GB)",
                    y="Throughput (images/sec)",
                    color="Size" if "Size" in df_filtered.columns else None,
                    size="Exact Match",
                    hover_name="Model ID",
                    color_discrete_sequence=COLORS['chart_colors']
                )
                fig.update_layout(**get_plotly_layout("VRAM vs Throughput"))
                st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
    
    with viz_tabs[2]:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        radar_models = st.multiselect(
            "Select models for radar chart (max 5)",
            df_filtered["Model ID"].tolist(),
            default=df_filtered["Model ID"].tolist()[:3],
            max_selections=5
        )
        
        if radar_models:
            radar_metrics = ["Exact Match", "Keyword Recall", "BERTScore F1", "BERTScore Recall", "BERTScore Precision"]
            radar_metrics = [m for m in radar_metrics if m in df_filtered.columns]
            
            fig = go.Figure()
            for i, model in enumerate(radar_models):
                model_data = df_filtered[df_filtered["Model ID"] == model]
                if not model_data.empty:
                    values = model_data[radar_metrics].values[0].tolist()
                    values.append(values[0])
                    fig.add_trace(go.Scatterpolar(
                        r=values,
                        theta=radar_metrics + [radar_metrics[0]],
                        fill='toself',
                        name=extract_model_name(model),
                        line=dict(color=COLORS['chart_colors'][i % len(COLORS['chart_colors'])])
                    ))
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 1], tickfont=dict(size=10)),
                    angularaxis=dict(tickfont=dict(size=11))
                ),
                showlegend=True,
                paper_bgcolor='white',
                font=dict(family='Poppins, sans-serif')
            )
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

