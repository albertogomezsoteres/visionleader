"""PaliGemma Evaluation Dashboard - thin orchestrator.

Wires the styles, sidebar, data loader and individual section renderers.
Every concrete piece of UI lives in its own module under ``dashboard/``.
"""
import sys
from pathlib import Path

dashboard_dir = Path(__file__).parent
sys.path.insert(0, str(dashboard_dir))

import streamlit as st

st.set_page_config(
    page_title="PaliGemma Evaluation Dashboard",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

from styles import inject_styles
from sidebar import render_sidebar
from data_loader import load_all_data
from main_header import render_header
from footer import render_footer

import section_overview
import section_comparison
import section_visualizations
import section_confusion
import section_individual_model
import section_performance
import section_by_category
import section_downloads


SECTION_RENDERERS = {
    "Overview": section_overview.render,
    "Comparison": section_comparison.render,
    "Visualizations": section_visualizations.render,
    "Confusion Matrices": section_confusion.render,
    "Individual Model": section_individual_model.render,
    "Performance": section_performance.render,
    "By Category": section_by_category.render,
    "Downloads": section_downloads.render,
}


def main() -> None:
    inject_styles()

    if "current_section" not in st.session_state:
        st.session_state.current_section = "Overview"

    df_expanded, df_reduced, env_info = load_all_data()
    if df_expanded is None:
        st.error(
            "Could not load data. Please verify that the results folder exists."
        )
        st.stop()

    render_sidebar()
    render_header()

    section = st.session_state.current_section
    renderer = SECTION_RENDERERS.get(section)
    if renderer is not None:
        renderer(df_expanded, df_reduced, env_info)

    render_footer()


main()
