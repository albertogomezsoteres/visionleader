"""By Category section."""
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
    # Custom header for By Category section
    st.markdown("""
        <div style="padding: 0 0 1rem 0; margin: 0;">
            <h1 style="font-size: 1.75rem; font-weight: 700; color: #1565C0; margin: 0; padding: 0; line-height: 1.75rem;">
                Metrics by Category
            </h1>
            <p style="font-size: 0.9rem; color: #6B7280; margin: 0.25rem 0 0 0; padding: 0;">
                Performance metrics grouped by object category (staircase, obstacle, elevator, door, door sign)
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    available_models = get_available_models()
    
    # Create a narrower container for the selectbox
    col_select, _ = st.columns([2, 3])
    with col_select:
        selected_model_cat = st.selectbox("Select model", available_models, key="model_cat")
    
    if selected_model_cat:
        metrics = load_model_metrics(selected_model_cat)
        
        if metrics:
            by_category = metrics.get("by_category", {})
            
            if by_category:
                cat_data = []
                for cat, cat_metrics in by_category.items():
                    row = {"Category": cat}
                    row.update(cat_metrics)
                    cat_data.append(row)
                
                cat_df = pd.DataFrame(cat_data)
                
                # Reorder columns: Category, count, exact_match, keyword_recall, then BERT metrics
                desired_order = ['Category', 'count', 'exact_match', 'keyword_recall']
                # Get remaining columns (BERT metrics and any others)
                remaining_cols = [col for col in cat_df.columns if col not in desired_order]
                # Final column order
                column_order = desired_order + remaining_cols
                # Only reorder if all desired columns exist
                available_cols = [col for col in column_order if col in cat_df.columns]
                if available_cols:
                    cat_df = cat_df[available_cols]
                
                st.dataframe(cat_df, use_container_width=True, hide_index=True)
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Create charts for all metrics
                metrics_to_chart = {
                    "exact_match": "Exact Match by Category",
                    "keyword_recall": "Keyword Recall by Category",
                    "bertscore_recall": "BERTScore Recall by Category",
                    "bertscore_f1": "BERTScore F1 by Category",
                    "bertscore_precision": "BERTScore Precision by Category"
                }
                
                for metric, title in metrics_to_chart.items():
                    if metric in cat_df.columns:
                        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                        fig = px.bar(
                            cat_df,
                            x="Category",
                            y=metric,
                            color=metric,
                            color_continuous_scale=[[0, '#E9D5FF'], [0.5, '#A855F7'], [1, '#7C3AED']]
                        )
                        fig.update_layout(**get_plotly_layout(title))
                        fig.update_layout(coloraxis_showscale=False)
                        st.plotly_chart(fig, use_container_width=True)
                        st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.info("No category data available for this model")
        else:
            st.warning(f"No metrics found for {selected_model_cat}")

