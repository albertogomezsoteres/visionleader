"""Overview section."""
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
    # Two column layout
    col1, col2 = st.columns(2)
    
    with col1:
        # Model Names Card
        st.markdown("""
            <div class="info-card-header">
                <div class="info-card-title">Model Evaluated</div>
            </div>
        """, unsafe_allow_html=True)
        
        model_names = [extract_model_name(model_id) for model_id in df_expanded["Model ID"].tolist()]
        model_names_html = ""
        for idx, model_name in enumerate(model_names, 1):
            model_names_html += f"""
                <div class="model-item">
                    <span class="model-number">{idx}</span>
                    <span class="model-name">{model_name}</span>
                </div>
            """
        st.markdown(model_names_html, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        # Metrics Used Card
        st.markdown("""
            <div class="info-card-header">
                <div class="info-card-title">Metrics Used</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Get all metric columns (exclude non-metric columns)
        exclude_cols = [
            "Model ID", "Description", "Version", "Size", "Type", "Resolution",
            "Binary YES/NO Accuracy",
            "Binary YES/NO Precision",
            "Binary YES/NO Recall",
            "Binary YES/NO F1",
            "Binary YES/NO TP",
            "Binary YES/NO FP",
            "Binary YES/NO TN",
            "Binary YES/NO FN",
            "State OPEN/CLOSED Accuracy",
            "State UP/DOWN Accuracy",
            "Navigation Elements Accuracy"
        ]
        metric_cols = [col for col in df_expanded.columns if col not in exclude_cols]
        
        metrics_html = ""
        for metric in metric_cols:
            metrics_html += f"""
                <div class="metric-item">
                    <span class="metric-spacer"></span>
                    <span class="metric-name">{metric}</span>
                </div>
            """
        st.markdown(metrics_html, unsafe_allow_html=True)
    
    # Environment Information Card
    st.markdown("""
        <div class="info-card-header">
            <div class="info-card-title" style="margin-top: 1.5rem; margin-bottom: 0; font-weight: 700; font-size: 1.75rem;">Environment Information</div>
            <p style="color: #6B7280; font-size: 0.9rem; margin: 0.5rem 0 0 0; padding: 0;">System configuration, hardware details, and experiment setup</p>
        </div>
    """, unsafe_allow_html=True)
    
    if env_info:
        env_col1, env_col2, env_col3 = st.columns(3)
        
        with env_col1:
            st.markdown('<h3 style="color: #1565C0; margin: 0 0 1rem 0;">System</h3>', unsafe_allow_html=True)
            system_info = env_info.get("system_info", {})
            for key, value in system_info.items():
                st.markdown(f"""
                    <div class="env-item">
                        <span class="env-key">{key}:</span>
                        <span class="env-value">{value}</span>
                    </div>
                """, unsafe_allow_html=True)
        
        with env_col2:
            st.markdown('<h3 style="color: #1565C0; margin: 0 0 1rem 0;">GPU</h3>', unsafe_allow_html=True)
            gpu_info = env_info.get("gpu_info", {})
            for key, value in gpu_info.items():
                st.markdown(f"""
                    <div class="env-item">
                        <span class="env-key">{key}:</span>
                        <span class="env-value">{value}</span>
                    </div>
                """, unsafe_allow_html=True)
        
        with env_col3:
            st.markdown('<h3 style="color: #1565C0; margin: 0 0 1rem 0;">Experiment</h3>', unsafe_allow_html=True)
            exp_info = env_info.get("experiment_info", {})
            for key, value in exp_info.items():
                if key not in ["base_results_path", "data_path", "config_path"]:
                    st.markdown(f"""
                        <div class="env-item">
                            <span class="env-key">{key}:</span>
                            <span class="env-value">{value}</span>
                        </div>
                    """, unsafe_allow_html=True)
        
        st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown('<h3 style="color: #1565C0; margin: 0 0 1rem 0;">Package Versions</h3>', unsafe_allow_html=True)
        package_versions = env_info.get("package_versions", {})
        pkg_cols = st.columns(4)
        pkg_items = list(package_versions.items())
        for i, (key, value) in enumerate(pkg_items):
            col_idx = i % 4
            with pkg_cols[col_idx]:
                st.markdown(f"""
                    <div class="env-item">
                        <span class="env-key">{key}:</span>
                        <span class="env-value">{value}</span>
                    </div>
                """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
