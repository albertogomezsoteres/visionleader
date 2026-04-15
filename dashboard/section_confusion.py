"""Confusion Matrices section."""
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
    # Custom header for Confusion Matrices section
    st.markdown("""
        <div style="padding: 0 0 1rem 0; margin: 0;">
            <h1 style="font-size: 1.75rem; font-weight: 700; color: #1565C0; margin: 0; padding: 0; line-height: 1.75rem;">
                Confusion Matrices Visualization
            </h1>
            <p style="font-size: 0.9rem; color: #6B7280; margin: 0.25rem 0 0 0; padding: 0;">
                Inspect confusion matrices and compare two models side by side
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    available_models = get_available_models()
    
    # Toggle for comparison mode
    compare_mode = st.toggle("Compare two models", value=False, key="cm_compare_toggle")
    
    if compare_mode:
        # Comparison mode: two models side by side
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Model 1**")
            col_select1_1, _ = st.columns([2, 1])
            with col_select1_1:
                selected_model_cm_1 = st.selectbox("Select first model", available_models, key="cm_model_1")
            if selected_model_cm_1:
                available_cms_1 = get_all_confusion_matrices(selected_model_cm_1)
                if available_cms_1:
                    col_select1_2, _ = st.columns([2, 1])
                    with col_select1_2:
                        selected_cm_type_1 = st.selectbox("Select matrix type", available_cms_1, key="cm_type_1")
                else:
                    st.warning("No confusion matrices available for this model")
                    selected_cm_type_1 = None
            else:
                selected_cm_type_1 = None
        
        with col2:
            st.markdown("**Model 2**")
            # Filter out the first selected model from the second dropdown
            available_models_2 = [m for m in available_models if m != selected_model_cm_1] if selected_model_cm_1 else available_models
            col_select2_1, _ = st.columns([2, 1])
            with col_select2_1:
                selected_model_cm_2 = st.selectbox("Select second model", available_models_2, key="cm_model_2")
            if selected_model_cm_2:
                available_cms_2 = get_all_confusion_matrices(selected_model_cm_2)
                if available_cms_2:
                    col_select2_2, _ = st.columns([2, 1])
                    with col_select2_2:
                        selected_cm_type_2 = st.selectbox("Select matrix type", available_cms_2, key="cm_type_2")
                else:
                    st.warning("No confusion matrices available for this model")
                    selected_cm_type_2 = None
            else:
                selected_cm_type_2 = None
        
        # Display both matrices side by side
        if selected_model_cm_1 and selected_cm_type_1 and selected_model_cm_2 and selected_cm_type_2:
            col_img1, col_img2 = st.columns(2)
            
            with col_img1:
                cm_path_1 = get_confusion_matrix_path(selected_model_cm_1, selected_cm_type_1)
                if cm_path_1 and cm_path_1.exists():
                    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                    st.image(str(cm_path_1), caption=f"{extract_model_name(selected_model_cm_1)} - {selected_cm_type_1}")
                    st.markdown('</div>', unsafe_allow_html=True)
            
            with col_img2:
                cm_path_2 = get_confusion_matrix_path(selected_model_cm_2, selected_cm_type_2)
                if cm_path_2 and cm_path_2.exists():
                    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                    st.image(str(cm_path_2), caption=f"{extract_model_name(selected_model_cm_2)} - {selected_cm_type_2}")
                    st.markdown('</div>', unsafe_allow_html=True)
    else:
        # Single model mode
        col_select1, col_select2, _ = st.columns([2, 2, 1])
        
        with col_select1:
            selected_model_cm = st.selectbox("Select model", available_models, key="cm_model")
        
        with col_select2:
            if selected_model_cm:
                available_cms = get_all_confusion_matrices(selected_model_cm)
                if available_cms:
                    selected_cm_type = st.selectbox("Select matrix type", available_cms)
                else:
                    st.warning("No confusion matrices available for this model")
                    selected_cm_type = None
            else:
                selected_cm_type = None
        
        if selected_model_cm and selected_cm_type:
            cm_path = get_confusion_matrix_path(selected_model_cm, selected_cm_type)
            if cm_path and cm_path.exists():
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                st.image(str(cm_path), caption=f"{extract_model_name(selected_model_cm)} - {selected_cm_type}")
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.info("Matrix not found for the selected model")

