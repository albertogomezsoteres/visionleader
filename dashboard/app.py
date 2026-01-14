"""
PaliGemma Evaluation Dashboard - Premium Design
Inspired by modern healthcare dashboards with clean, professional aesthetics
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from pathlib import Path
from PIL import Image
import json

import sys
from pathlib import Path

# Add dashboard directory to path
dashboard_dir = Path(__file__).parent
sys.path.insert(0, str(dashboard_dir))

import config
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
    extract_model_name,
    format_metric_value
)

# ============================================================
# PAGE CONFIGURATION
# ============================================================
st.set_page_config(
    page_title="PaliGemma Evaluation Dashboard",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Force light theme
st.markdown("""
    <script>
        var elements = window.parent.document.querySelectorAll('.stApp')
        if (elements.length > 0) {
            elements[0].classList.add('light')
        }
    </script>
""", unsafe_allow_html=True)

# ============================================================
# PREMIUM CSS - PURPLE & WHITE MODERN THEME
# ============================================================
st.markdown("""
<style>
    /* Import Google Fonts - Poppins for modern look */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap');
    
    /* ========== GLOBAL STYLES ========== */
    html, body, [class*="css"] {
        font-family: 'Poppins', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    
    .stApp {
        background: #F8F9FC !important;
    }
    
    /* Hide Streamlit default elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Remove ALL top spacing from app - AGGRESSIVE */
    .stApp {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    .stApp > div:first-child {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    /* Remove spacing from main element */
    .main {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    /* Remove spacing from main > div */
    .main > div {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    /* ========== MAIN CONTAINER ========== */
    .appview-container .main .block-container {
        padding-top: 0 !important;
        padding-bottom: 5rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        margin-top: 0 !important;
        max-width: 1600px !important;
    }
    
    /* Remove ALL spacing from first child and nested elements */
    .main .block-container > div:first-child {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    .main .block-container > *:first-child {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    .main .block-container > div:first-child > div:first-child {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    /* Remove spacing from Streamlit markdown elements */
    .main .block-container [data-testid="stMarkdownContainer"]:first-child {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    .main .block-container [data-testid="stMarkdownContainer"]:first-child > * {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    /* Remove spacing from any div at the top */
    .main .block-container > div:first-child > div {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    /* Remove spacing from Streamlit elements wrapper */
    [data-testid="stAppViewContainer"] > div:first-child {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    /* Remove spacing from element with class element-container */
    .element-container:first-child {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    /* Remove spacing from first markdown container (search bar) */
    .main .block-container > div:first-child [data-testid="stMarkdownContainer"]:first-child {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    .main .block-container > div:first-child > div:first-child {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    /* Remove spacing from search bar div */
    .main .block-container > div:first-child > div:first-child > div {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    /* ========== SIDEBAR STYLES ========== */
    [data-testid="stSidebar"] {
        background: #FFFFFF !important;
        border-right: 1px solid #E8EAF0 !important;
        box-shadow: 2px 0 20px rgba(0,0,0,0.03) !important;
    }
    
    [data-testid="stSidebar"] > div:first-child {
        background: #FFFFFF !important;
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    /* Remove top spacing from sidebar content */
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:first-child {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    [data-testid="stSidebar"] > div:first-child > div:first-child {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    /* Sidebar Logo/Title Area */
    .sidebar-header {
        padding: 0 1.25rem 1rem 1.25rem;
        border-bottom: 1px solid #F0F1F5;
        margin-bottom: 0.5rem;
        margin-top: 0 !important;
        display: flex;
        align-items: center;
        min-height: 1.75rem;
    }
    
    .sidebar-logo {
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    
    .sidebar-logo-icon {
        width: 40px;
        height: 40px;
        background: linear-gradient(135deg, #7C3AED 0%, #A855F7 100%);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.25rem;
        color: white;
    }
    
    .sidebar-logo-text {
        font-size: 1.25rem;
        font-weight: 700;
        color: #1F2937;
        letter-spacing: -0.5px;
        line-height: 1.75rem;
        margin: 0;
        padding: 0;
    }
    
    /* Sidebar Navigation Buttons */
    [data-testid="stSidebar"] .stButton > button {
        width: 100% !important;
        text-align: left !important;
        padding: 0.85rem 1.25rem !important;
        margin: 0.15rem 0.5rem !important;
        border-radius: 10px !important;
        border: none !important;
        background: transparent !important;
        color: #6B7280 !important;
        font-weight: 500 !important;
        font-size: 0.925rem !important;
        transition: all 0.2s ease !important;
        box-shadow: none !important;
    }
    
    [data-testid="stSidebar"] .stButton > button:hover {
        background: #E3F2FD !important;
        color: #1565C0 !important;
    }
    
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background: #E3F2FD !important;
        color: #1565C0 !important;
        font-weight: 600 !important;
        border-left: 3px solid #1565C0 !important;
        margin-left: 0.35rem !important;
    }
    
    /* Sidebar CTA Button */
    .sidebar-cta {
        margin: 1rem;
        padding: 0.875rem 1.25rem;
        background: linear-gradient(135deg, #7C3AED 0%, #A855F7 100%);
        color: white !important;
        border-radius: 10px;
        font-weight: 600;
        font-size: 0.925rem;
        text-align: center;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(124, 58, 237, 0.3);
    }
    
    .sidebar-cta:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(124, 58, 237, 0.4);
    }
    
    /* Sidebar App Promo */
    .sidebar-promo {
        margin: 1.5rem 1rem;
        padding: 1.25rem;
        background: linear-gradient(135deg, #F0FDF4 0%, #DCFCE7 100%);
        border-radius: 16px;
        text-align: center;
    }
    
    .sidebar-promo-icon {
        font-size: 3rem;
        margin-bottom: 0.5rem;
    }
    
    .sidebar-promo-text {
        font-size: 0.85rem;
        color: #374151;
        font-weight: 500;
    }
    
    /* ========== HEADER STYLES ========== */
    .main-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.5rem 0 1.5rem 0;
        border-bottom: 1px solid #E8EAF0;
        margin-bottom: 1.5rem;
    }
    
    .header-search {
        display: flex;
        align-items: center;
        background: #F3F4F6;
        padding: 0.625rem 1rem;
        border-radius: 10px;
        width: 300px;
    }
    
    .header-search input {
        border: none;
        background: transparent;
        outline: none;
        margin-left: 0.5rem;
        font-size: 0.875rem;
        color: #6B7280;
    }
    
    .header-user {
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    
    .header-notification {
        width: 40px;
        height: 40px;
        background: #F3F4F6;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
    }
    
    .header-avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: linear-gradient(135deg, #7C3AED 0%, #A855F7 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 600;
    }
    
    /* ========== KPI CARDS ========== */
    .kpi-card {
        background: white;
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        border: 1px solid #F0F1F5;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .kpi-card:hover {
        box-shadow: 0 8px 25px rgba(0,0,0,0.06);
        transform: translateY(-2px);
    }
    
    .kpi-card-icon {
        width: 48px;
        height: 48px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
        margin-bottom: 1rem;
    }
    
    .kpi-card-icon.purple { background: #F5F3FF; color: #7C3AED; }
    .kpi-card-icon.blue { background: #EFF6FF; color: #3B82F6; }
    .kpi-card-icon.orange { background: #FFF7ED; color: #F97316; }
    .kpi-card-icon.pink { background: #FDF2F8; color: #EC4899; }
    .kpi-card-icon.green { background: #F0FDF4; color: #22C55E; }
    
    .kpi-card-value {
        font-size: 2rem;
        font-weight: 700;
        color: #1F2937;
        line-height: 1.2;
        margin-bottom: 0.25rem;
    }
    
    .kpi-card-label {
        font-size: 0.875rem;
        color: #6B7280;
        font-weight: 500;
    }
    
    .kpi-card-menu {
        position: absolute;
        top: 1rem;
        right: 1rem;
        color: #9CA3AF;
        cursor: pointer;
    }
    
    /* ========== CHART CONTAINERS ========== */
    .chart-container {
        background: white;
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        border: 1px solid #F0F1F5;
        margin-bottom: 1.5rem;
    }
    
    /* Hide empty containers */
    .chart-container:empty {
        display: none !important;
    }
    
    /* Hide containers that only have whitespace */
    .chart-container:has(> :empty:only-child) {
        display: none !important;
    }
    
    .chart-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1.25rem;
    }
    
    .chart-title {
        font-size: 1.125rem;
        font-weight: 600;
        color: #1F2937;
    }
    
    .chart-subtitle {
        font-size: 0.8rem;
        color: #9CA3AF;
        margin-top: 0.25rem;
    }
    
    .chart-dropdown {
        padding: 0.5rem 1rem;
        background: #F9FAFB;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        font-size: 0.875rem;
        color: #374151;
        cursor: pointer;
    }
    
    /* ========== INFO CARDS ========== */
    .info-card {
        background: white;
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        border: 1px solid #F0F1F5;
        margin-bottom: 1.5rem;
    }
    
    .info-card-header {
        margin-bottom: 1.25rem;
        padding-bottom: 1rem;
        border-bottom: 2px solid #F0F1F5;
    }
    
    .info-card-title {
        font-size: 1.125rem;
        font-weight: 600;
        color: #1565C0;
    }
    
    .model-item {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.75rem 0;
        border-bottom: 1px solid #F0F1F5;
        min-height: 44px;
    }
    
    .model-item:last-child {
        border-bottom: none;
    }
    
    .model-number {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        background: #E3F2FD;
        color: #1565C0;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.875rem;
        flex-shrink: 0;
    }
    
    .model-name {
        color: #1F2937;
        font-size: 0.95rem;
        font-weight: 500;
    }
    
    .metric-item {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.75rem 0;
        border-bottom: 1px solid #F0F1F5;
        min-height: 44px;
    }
    
    .metric-item:last-child {
        border-bottom: none;
    }
    
    .metric-name {
        color: #1F2937;
        font-size: 0.95rem;
        font-weight: 500;
        margin-left: 0;
    }
    
    /* Spacer to align with model-number */
    .metric-spacer {
        width: 28px;
        flex-shrink: 0;
    }
    
    .env-item {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
        padding: 0.75rem 0;
        border-bottom: 1px solid #F0F1F5;
    }
    
    .env-item:last-child {
        border-bottom: none;
    }
    
    .env-key {
        color: #6B7280;
        font-size: 0.875rem;
        font-weight: 500;
        text-transform: capitalize;
    }
    
    .env-value {
        color: #1F2937;
        font-size: 0.95rem;
        font-weight: 600;
        word-break: break-word;
    }
    
    /* ========== DATA TABLE ========== */
    .data-table-container {
        background: white;
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        border: 1px solid #F0F1F5;
    }
    
    /* Streamlit dataframe styling - force white background, visible data */
    [data-testid="stDataFrame"] {
        border-radius: 12px !important;
        overflow: hidden !important;
        background: white !important;
        background-color: white !important;
    }
    
    [data-testid="stDataFrame"] > div {
        border-radius: 12px !important;
        background: white !important;
        background-color: white !important;
    }
    
    [data-testid="stDataFrame"] > div > div {
        background: white !important;
        background-color: white !important;
    }
    
    /* Table text colors - visible text on white background */
    [data-testid="stDataFrame"] table {
        color: #374151 !important;
        background: white !important;
        background-color: white !important;
        border-collapse: collapse !important;
    }
    
    [data-testid="stDataFrame"] table tbody {
        background: white !important;
        background-color: white !important;
    }
    
    [data-testid="stDataFrame"] table thead {
        background: #F3F4F6 !important;
        background-color: #F3F4F6 !important;
    }
    
    [data-testid="stDataFrame"] th {
        background: #F3F4F6 !important;
        background-color: #F3F4F6 !important;
        color: #1565C0 !important;
        font-weight: 600 !important;
        border: 1px solid #E5E7EB !important;
    }
    
    [data-testid="stDataFrame"] td {
        color: #374151 !important;
        background: white !important;
        background-color: white !important;
        border: 1px solid #E5E7EB !important;
    }
    
    [data-testid="stDataFrame"] tr {
        background: white !important;
        background-color: white !important;
    }
    
    [data-testid="stDataFrame"] tbody tr:nth-child(even) {
        background: #F9FAFB !important;
        background-color: #F9FAFB !important;
    }
    
    [data-testid="stDataFrame"] tbody tr:nth-child(even) td {
        background: #F9FAFB !important;
        background-color: #F9FAFB !important;
    }
    
    [data-testid="stDataFrame"] tbody tr:nth-child(odd) {
        background: white !important;
        background-color: white !important;
    }
    
    [data-testid="stDataFrame"] tbody tr:nth-child(odd) td {
        background: white !important;
        background-color: white !important;
    }
    
    /* Override any dark backgrounds in dataframe */
    [data-testid="stDataFrame"] [style*="background"] {
        background-color: white !important;
    }
    
    [data-testid="stDataFrame"] [style*="rgb(0, 0, 0)"],
    [data-testid="stDataFrame"] [style*="#000"],
    [data-testid="stDataFrame"] [style*="black"] {
        background-color: white !important;
        color: #374151 !important;
    }
    
    /* Ensure text is visible */
    [data-testid="stDataFrame"] * {
        color: #374151 !important;
    }
    
    [data-testid="stDataFrame"] th * {
        color: #1565C0 !important;
    }
    
    /* Selectbox and Radio button styling */
    [data-testid="stSelectbox"] label,
    [data-testid="stRadio"] label,
    [data-testid="stMultiSelect"] label {
        color: #374151 !important;
        font-weight: 600 !important;
        background: #F8F9FC !important;
    }
    
    [data-testid="stMultiSelect"] > label {
        background: #F8F9FC !important;
    }
    
    [data-testid="stMultiSelect"] .element-container > label {
        background: #F8F9FC !important;
    }
    
    [data-testid="stSelectbox"] > div > div,
    [data-testid="stSelectbox"] > div > div > div {
        color: #374151 !important;
        background: white !important;
    }
    
    [data-testid="stSelectbox"] select {
        color: #374151 !important;
        background: white !important;
    }
    
    [data-testid="stRadio"] > div {
        color: #374151 !important;
    }
    
    [data-testid="stRadio"] > div > label {
        color: #374151 !important;
    }
    
    [data-testid="stRadio"] > div > label > div {
        color: #374151 !important;
    }
    
    /* Radio button selected indicator - light blue */
    [data-testid="stRadio"] input[type="radio"]:checked {
        background-color: #93C5FD !important;
        border-color: #60A5FA !important;
    }
    
    [data-testid="stRadio"] input[type="radio"]:checked::before {
        background-color: #60A5FA !important;
    }
    
    [data-testid="stRadio"] input[type="radio"]:checked::after {
        background-color: #60A5FA !important;
    }
    
    /* Radio button not selected - white */
    [data-testid="stRadio"] input[type="radio"]:not(:checked) {
        background-color: white !important;
        border-color: #D1D5DB !important;
    }
    
    [data-testid="stRadio"] input[type="radio"]:not(:checked)::before {
        background-color: white !important;
    }
    
    /* Radio button circle/dot - selected */
    [data-testid="stRadio"] label input[type="radio"]:checked + span {
        background-color: #93C5FD !important;
    }
    
    [data-testid="stRadio"] label input[type="radio"]:checked + span::before {
        background-color: #60A5FA !important;
    }
    
    /* Radio button circle/dot - not selected */
    [data-testid="stRadio"] label input[type="radio"]:not(:checked) + span {
        background-color: white !important;
        border-color: #D1D5DB !important;
    }
    
    /* BaseWeb radio button styling */
    [data-testid="stRadio"] [data-baseweb="radio"] input[type="radio"]:checked {
        background-color: #93C5FD !important;
        border-color: #60A5FA !important;
    }
    
    [data-testid="stRadio"] [data-baseweb="radio"] input[type="radio"]:checked + span {
        background-color: #60A5FA !important;
    }
    
    /* Radio button not selected - white */
    [data-testid="stRadio"] [data-baseweb="radio"] input[type="radio"]:not(:checked) {
        background-color: white !important;
        border-color: #D1D5DB !important;
    }
    
    [data-testid="stRadio"] [data-baseweb="radio"] input[type="radio"]:not(:checked) + span {
        background-color: white !important;
        border-color: #D1D5DB !important;
    }
    
    /* Multiselect styling */
    [data-testid="stMultiSelect"] > div > div {
        color: #374151 !important;
        background: white !important;
    }
    
    [data-testid="stMultiSelect"] input {
        color: #374151 !important;
    }
    
    /* Multiselect container background - white */
    [data-testid="stMultiSelect"] > div {
        background: white !important;
    }
    
    [data-testid="stMultiSelect"] {
        background: white !important;
    }
    
    /* Multiselect input container */
    [data-testid="stMultiSelect"] > div > div > div {
        background: white !important;
    }
    
    /* Multiselect chips/tags - very light blue (almost white) with very subtle border */
    [data-testid="stMultiSelect"] [data-baseweb="tag"],
    [data-testid="stMultiSelect"] span[data-baseweb="tag"],
    [data-testid="stMultiSelect"] div[data-baseweb="tag"],
    [data-testid="stMultiSelect"] button[data-baseweb="tag"] {
        background: #DBEAFE !important;
        color: #1565C0 !important;
        border: 1px solid #F0F4FF !important;
        border-color: #F0F4FF !important;
        border-width: 1px !important;
    }
    
    [data-testid="stMultiSelect"] [data-baseweb="tag"] span,
    [data-testid="stMultiSelect"] span[data-baseweb="tag"] span {
        color: #1565C0 !important;
    }
    
    [data-testid="stMultiSelect"] [data-baseweb="tag"] svg,
    [data-testid="stMultiSelect"] span[data-baseweb="tag"] svg {
        color: #1565C0 !important;
        fill: #1565C0 !important;
    }
    
    /* Alternative selectors for multiselect chips */
    [data-testid="stMultiSelect"] button[data-baseweb="tag"],
    [data-testid="stMultiSelect"] div[role="button"] {
        background: #DBEAFE !important;
        color: #1565C0 !important;
    }
    
    [data-testid="stMultiSelect"] button[data-baseweb="tag"] span,
    [data-testid="stMultiSelect"] div[role="button"] span {
        color: #1565C0 !important;
    }
    
    /* General text color for all Streamlit widgets */
    .stSelectbox,
    .stRadio,
    .stMultiSelect,
    .element-container label {
        color: #374151 !important;
        background: #F8F9FC !important;
    }
    
    /* More specific selectors for multiselect label */
    [data-testid="stMultiSelect"] + label,
    .element-container [data-testid="stMultiSelect"] + label,
    div[data-testid="stMultiSelect"] ~ label,
    .element-container:has([data-testid="stMultiSelect"]) label {
        background: #F8F9FC !important;
        color: #374151 !important;
    }
    
    /* Force page background color on label container */
    .element-container:has([data-testid="stMultiSelect"]) {
        background: #F8F9FC !important;
    }
    
    .element-container:has([data-testid="stMultiSelect"]) > label {
        background: #F8F9FC !important;
        padding: 0.25rem 0 !important;
    }
    
    /* Ensure all text in widgets is visible */
    .stSelectbox *,
    .stRadio *,
    .stMultiSelect * {
        color: #374151 !important;
    }
    
    /* Multiselect chips - comprehensive styling - very light blue with very subtle border */
    [data-testid="stMultiSelect"] *[class*="tag"],
    [data-testid="stMultiSelect"] *[class*="chip"],
    [data-testid="stMultiSelect"] button[class*="tag"],
    [data-testid="stMultiSelect"] div[class*="tag"] {
        background: #DBEAFE !important;
        color: #1565C0 !important;
        border: 1px solid #F0F4FF !important;
        border-color: #F0F4FF !important;
        border-width: 1px !important;
    }
    
    [data-testid="stMultiSelect"] *[class*="tag"] *,
    [data-testid="stMultiSelect"] *[class*="chip"] *,
    [data-testid="stMultiSelect"] button[class*="tag"] *,
    [data-testid="stMultiSelect"] div[class*="tag"] * {
        color: #1565C0 !important;
    }
    
    /* Radio button - comprehensive styling for selected state */
    [data-testid="stRadio"] input[type="radio"]:checked,
    [data-testid="stRadio"] * input[type="radio"]:checked {
        accent-color: #93C5FD !important;
        background-color: #93C5FD !important;
        border-color: #60A5FA !important;
    }
    
    [data-testid="stRadio"] input[type="radio"]:checked::before,
    [data-testid="stRadio"] * input[type="radio"]:checked::before {
        background-color: #60A5FA !important;
    }
    
    /* Override any red colors in multiselect and radio */
    [data-testid="stMultiSelect"] * {
        --tag-background: #DBEAFE !important;
        --tag-color: #1565C0 !important;
    }
    
    [data-testid="stRadio"] * {
        --radio-checked: #93C5FD !important;
        --radio-dot: #60A5FA !important;
    }
    
    /* Direct styling for BaseWeb components - very light blue with very subtle border */
    [data-baseweb="tag"] {
        background-color: #DBEAFE !important;
        color: #1565C0 !important;
        border: 1px solid #F0F4FF !important;
        border-color: #F0F4FF !important;
        border-width: 1px !important;
    }
    
    [data-baseweb="tag"] span {
        color: #1565C0 !important;
    }
    
    [data-baseweb="tag"] svg {
        color: #1565C0 !important;
        fill: #1565C0 !important;
    }
    
    /* Radio button BaseWeb styling - selected */
    [data-baseweb="radio"] input[type="radio"]:checked {
        background-color: #93C5FD !important;
        border-color: #60A5FA !important;
    }
    
    [data-baseweb="radio"] input[type="radio"]:checked + span {
        background-color: #60A5FA !important;
    }
    
    /* Radio button BaseWeb styling - not selected */
    [data-baseweb="radio"] input[type="radio"]:not(:checked) {
        background-color: white !important;
        border-color: #D1D5DB !important;
    }
    
    [data-baseweb="radio"] input[type="radio"]:not(:checked) + span {
        background-color: white !important;
        border-color: #D1D5DB !important;
    }
    
    /* Override any red/black colors globally in these components */
    [data-testid="stMultiSelect"] [style*="red"],
    [data-testid="stMultiSelect"] [style*="rgb(239, 68, 68)"],
    [data-testid="stMultiSelect"] [style*="#EF4444"],
    [data-testid="stMultiSelect"] [style*="rgb(0, 0, 0)"],
    [data-testid="stMultiSelect"] [style*="#000"] {
        background-color: #DBEAFE !important;
        color: #1565C0 !important;
    }
    
    [data-testid="stRadio"] [style*="red"],
    [data-testid="stRadio"] [style*="rgb(239, 68, 68)"],
    [data-testid="stRadio"] [style*="#EF4444"] {
        background-color: #93C5FD !important;
        color: white !important;
    }
    
    /* ========== SECTION HEADER ========== */
    .section-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 0.25rem;
        padding-bottom: 1rem;
        border-bottom: 2px solid #F0F1F5;
    }
    
    .section-header-icon {
        width: 40px;
        height: 40px;
        background: linear-gradient(135deg, #7C3AED 0%, #A855F7 100%);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 1.25rem;
    }
    
    .section-header-text {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1F2937;
    }
    
    /* ========== FILTERS BAR ========== */
    .filters-bar {
        background: white;
        border-radius: 16px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        border: 1px solid #F0F1F5;
    }
    
    .filters-bar .stSelectbox label,
    .filters-bar .stTextInput label {
        font-weight: 600 !important;
        color: #374151 !important;
        font-size: 0.85rem !important;
    }
    
    .filters-bar .stSelectbox > div > div,
    .filters-bar .stTextInput > div > div > input {
        background: #F9FAFB !important;
        border: 1px solid #E5E7EB !important;
        border-radius: 8px !important;
        color: #374151 !important;
    }
    
    /* ========== METRIC CARDS ROW ========== */
    .metric-row {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1.5rem;
        margin-bottom: 1.5rem;
    }
    
    /* ========== DONUT CHART LEGEND ========== */
    .donut-legend {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-top: 0.5rem;
    }
    
    .donut-legend-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
    }
    
    .donut-legend-text {
        font-size: 0.8rem;
        color: #6B7280;
    }
    
    /* ========== STAT BOX ========== */
    .stat-box {
        background: linear-gradient(135deg, #7C3AED 0%, #6D28D9 100%);
        border-radius: 16px;
        padding: 1.5rem;
        color: white;
    }
    
    .stat-box-value {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.25rem;
    }
    
    .stat-box-label {
        font-size: 0.9rem;
        opacity: 0.9;
    }
    
    .stat-box-chart {
        margin-top: 1rem;
    }
    
    /* ========== LIST ITEM ========== */
    .list-item {
        display: flex;
        align-items: center;
        padding: 0.875rem 0;
        border-bottom: 1px solid #F3F4F6;
    }
    
    .list-item:last-child {
        border-bottom: none;
    }
    
    .list-item-icon {
        width: 36px;
        height: 36px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-right: 1rem;
        font-size: 1rem;
    }
    
    .list-item-text {
        flex: 1;
        font-size: 0.925rem;
        color: #374151;
        font-weight: 500;
    }
    
    .list-item-value {
        font-size: 0.925rem;
        font-weight: 600;
        color: #1F2937;
    }
    
    /* ========== TABS ========== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0 !important;
        background: #F3F4F6 !important;
        border-radius: 12px !important;
        padding: 4px !important;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 0.75rem 1.5rem !important;
        border-radius: 8px !important;
        color: #6B7280 !important;
        font-weight: 500 !important;
        background: transparent !important;
    }
    
    .stTabs [aria-selected="true"] {
        background: white !important;
        color: #7C3AED !important;
        font-weight: 600 !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
    }
    
    /* ========== EXPANDERS ========== */
    .streamlit-expanderHeader {
        background: #F9FAFB !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        color: #374151 !important;
        border: 1px solid #E5E7EB !important;
    }
    
    .streamlit-expanderHeader:hover {
        background: #F3F4F6 !important;
    }
    
    .streamlit-expanderContent {
        background: white !important;
        border: 1px solid #E5E7EB !important;
        border-top: none !important;
        border-radius: 0 0 10px 10px !important;
        padding: 1rem !important;
    }
    
    /* ========== BUTTONS ========== */
    .stButton > button {
        background: linear-gradient(135deg, #7C3AED 0%, #A855F7 100%) !important;
        color: white !important;
        border: none !important;
        padding: 0.75rem 1.5rem !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(124, 58, 237, 0.25) !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(124, 58, 237, 0.35) !important;
    }
    
    .stDownloadButton > button {
        background: linear-gradient(135deg, #86EFAC 0%, #4ADE80 100%) !important;
        box-shadow: 0 4px 15px rgba(134, 239, 172, 0.25) !important;
    }
    
    .stDownloadButton > button:hover {
        box-shadow: 0 6px 20px rgba(134, 239, 172, 0.35) !important;
        background: linear-gradient(135deg, #96F5BC 0%, #5AEE90 100%) !important;
    }
    
    /* ========== METRICS ========== */
    [data-testid="stMetricValue"] {
        font-size: 2rem !important;
        font-weight: 700 !important;
        color: #1F2937 !important;
    }
    
    [data-testid="stMetricLabel"] {
        font-size: 0.875rem !important;
        color: #6B7280 !important;
        font-weight: 500 !important;
    }
    
    /* ========== SCROLLBAR ========== */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #F3F4F6;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #D1D5DB;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #9CA3AF;
    }
    
    /* ========== INFO BOXES ========== */
    .stInfo {
        background: #F5F3FF !important;
        border-left: 4px solid #7C3AED !important;
        border-radius: 8px !important;
        color: #5B21B6 !important;
    }
    
    .stWarning {
        background: #FFFBEB !important;
        border-left: 4px solid #F59E0B !important;
        border-radius: 8px !important;
    }
    
    .stSuccess {
        background: #F0FDF4 !important;
        border-left: 4px solid #22C55E !important;
        border-radius: 8px !important;
    }
    
    /* ========== IMAGES ========== */
    .stImage img {
        border-radius: 12px !important;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08) !important;
    }
    
    /* Hide default Streamlit header/title margin */
    h1 {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
</style>
<script>
    // Force multiselect label background to white
    function updateMultiselectStyles() {
        // Update label background
        const multiselectLabels = document.querySelectorAll('[data-testid="stMultiSelect"]').forEach(el => {
            const label = el.closest('.element-container')?.querySelector('label');
            if (label) {
                label.style.background = '#F8F9FC';
                label.style.backgroundColor = '#F8F9FC';
            }
        });
        
        // Update chip borders to be more subtle
        const tags = document.querySelectorAll('[data-baseweb="tag"]');
        tags.forEach(tag => {
            tag.style.borderColor = '#F0F4FF';
            tag.style.borderWidth = '1px';
            tag.style.borderStyle = 'solid';
            tag.style.background = '#DBEAFE';
        });
        
        // Force label background to page background color
        document.querySelectorAll('.element-container label').forEach(label => {
            if (label.textContent.includes('Select columns')) {
                label.style.background = '#F8F9FC';
                label.style.backgroundColor = '#F8F9FC';
            }
        });
        
        // Force table to be white with visible data
        const dataframes = document.querySelectorAll('[data-testid="stDataFrame"]');
        dataframes.forEach(df => {
            // Force container background
            df.style.backgroundColor = 'white';
            
            // Force all child divs to white
            df.querySelectorAll('div').forEach(div => {
                div.style.backgroundColor = 'white';
            });
            
            // Force table background
            const tables = df.querySelectorAll('table');
            tables.forEach(table => {
                table.style.backgroundColor = 'white';
                table.style.color = '#374151';
            });
            
            // Force table body background
            const tbodies = df.querySelectorAll('tbody');
            tbodies.forEach(tbody => {
                tbody.style.backgroundColor = 'white';
            });
            
            // Force table rows - alternate colors for visibility
            const rows = df.querySelectorAll('tbody tr');
            rows.forEach((row, index) => {
                if (index % 2 === 0) {
                    row.style.backgroundColor = 'white';
                } else {
                    row.style.backgroundColor = '#F9FAFB';
                }
            });
            
            // Force table cells - ensure text is visible
            const cells = df.querySelectorAll('td');
            cells.forEach((cell) => {
                const row = cell.closest('tr');
                const tbody = row ? row.closest('tbody') : null;
                if (tbody) {
                    const rowIndex = Array.from(tbody.children).indexOf(row);
                    if (rowIndex % 2 === 0) {
                        cell.style.backgroundColor = 'white';
                    } else {
                        cell.style.backgroundColor = '#F9FAFB';
                    }
                } else {
                    cell.style.backgroundColor = 'white';
                }
                cell.style.color = '#374151';
            });
            
            // Force table headers
            const headers = df.querySelectorAll('th');
            headers.forEach(header => {
                header.style.backgroundColor = '#F3F4F6';
                header.style.color = '#1565C0';
            });
            
            // Override any black/dark backgrounds but keep text visible
            const allElements = df.querySelectorAll('*');
            allElements.forEach(el => {
                const bg = window.getComputedStyle(el).backgroundColor;
                if (bg && (bg.includes('rgb(0, 0, 0)') || bg.includes('black') || bg === 'rgb(0, 0, 0)')) {
                    const tagName = el.tagName.toLowerCase();
                    if (tagName === 'th') {
                        el.style.backgroundColor = '#F3F4F6';
                        el.style.color = '#1565C0';
                    } else if (tagName === 'td') {
                        const row = el.closest('tr');
                        const tbody = row ? row.closest('tbody') : null;
                        if (tbody) {
                            const rowIndex = Array.from(tbody.children).indexOf(row);
                            el.style.backgroundColor = rowIndex % 2 === 0 ? 'white' : '#F9FAFB';
                        } else {
                            el.style.backgroundColor = 'white';
                        }
                        el.style.color = '#374151';
                    } else {
                        el.style.backgroundColor = 'white';
                        if (el.textContent && el.textContent.trim()) {
                            el.style.color = '#374151';
                        }
                    }
                }
            });
        });
        
        // Update radio buttons - selected: light blue, not selected: white
        const radioButtons = document.querySelectorAll('[data-testid="stRadio"] input[type="radio"], [data-baseweb="radio"] input[type="radio"]');
        radioButtons.forEach(radio => {
            if (radio.checked) {
                radio.style.backgroundColor = '#93C5FD';
                radio.style.borderColor = '#60A5FA';
                // Update the visual indicator
                const span = radio.nextElementSibling;
                if (span) {
                    span.style.backgroundColor = '#93C5FD';
                    span.style.borderColor = '#60A5FA';
                }
            } else {
                radio.style.backgroundColor = 'white';
                radio.style.borderColor = '#D1D5DB';
                // Update the visual indicator
                const span = radio.nextElementSibling;
                if (span) {
                    span.style.backgroundColor = 'white';
                    span.style.borderColor = '#D1D5DB';
                }
            }
        });
        
        // Force table to be white
        const dataframes = document.querySelectorAll('[data-testid="stDataFrame"]');
        dataframes.forEach(df => {
            // Force all elements inside dataframe to have white background
            const allElements = df.querySelectorAll('*');
            allElements.forEach(el => {
                const computedStyle = window.getComputedStyle(el);
                if (computedStyle.backgroundColor && 
                    (computedStyle.backgroundColor.includes('rgb(0, 0, 0)') || 
                     computedStyle.backgroundColor.includes('black') ||
                     computedStyle.backgroundColor === 'rgb(0, 0, 0)')) {
                    el.style.backgroundColor = 'white';
                }
            });
            
            // Force table rows
            const rows = df.querySelectorAll('tr');
            rows.forEach((row, index) => {
                if (index % 2 === 0) {
                    row.style.backgroundColor = 'white';
                } else {
                    row.style.backgroundColor = '#F9FAFB';
                }
            });
            
            // Force table cells
            const cells = df.querySelectorAll('td');
            cells.forEach(cell => {
                cell.style.backgroundColor = 'white';
                cell.style.color = '#374151';
            });
            
            // Force table headers
            const headers = df.querySelectorAll('th');
            headers.forEach(header => {
                header.style.backgroundColor = '#F3F4F6';
                header.style.color = '#1565C0';
            });
        });
    }
    
    // Run on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', updateMultiselectStyles);
    } else {
        updateMultiselectStyles();
    }
    
    // Run after a delay to catch dynamically loaded elements
    setTimeout(updateMultiselectStyles, 500);
    setTimeout(updateMultiselectStyles, 1000);
    
    // Use MutationObserver to watch for new elements
    const observer = new MutationObserver(updateMultiselectStyles);
    observer.observe(document.body, { childList: true, subtree: true });
</script>
""", unsafe_allow_html=True)

# ============================================================
# NAVIGATION SYSTEM
# ============================================================
SECTIONS = {
    "Overview": "🏠",
    "Comparison": "📊",
    "Visualizations": "📈",
    "Confusion Matrices": "🎯",
    "Individual Model": "🔍",
    "Performance": "⚡",
    "By Category": "📋",
    "Downloads": "📥"
}

if 'current_section' not in st.session_state:
    st.session_state.current_section = 'Overview'

def navigate_to(section):
    st.session_state.current_section = section

# ============================================================
# DATA LOADING
# ============================================================
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

df_expanded, df_reduced, env_info = load_all_data()

if df_expanded is None:
    st.error("Could not load data. Please verify that the results folder exists.")
    st.stop()

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    # Logo and Title
    st.markdown("""
        <div class="sidebar-header">
            <div class="sidebar-logo">
                <div class="sidebar-logo-text" style="color: #1565C0;">VisionLeaderUFV</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Navigation Menu
    st.markdown("<div style='padding: 0.5rem 0;'>", unsafe_allow_html=True)
    
    for section, icon in SECTIONS.items():
        is_active = st.session_state.current_section == section
        if st.button(
            f"{icon}  {section}",
            key=f"nav_{section}",
            use_container_width=True,
            type="primary" if is_active else "secondary"
        ):
            navigate_to(section)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # User profile at bottom
    st.markdown("<div style='margin-top: 2rem;'>", unsafe_allow_html=True)
    st.markdown("""
        <div style="
            margin: 1rem 0.5rem 1rem 0;
            padding: 0.85rem 1.25rem;
            border-radius: 10px;
            color: #6B7280;
            font-weight: 500;
            font-size: 0.925rem;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        ">
            <svg style="width: 20px; height: 20px; color: #6B7280;" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24">
                <path fill-rule="evenodd" d="M12 4a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm-2 9a4 4 0 0 0-4 4v1a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-1a4 4 0 0 0-4-4h-4Z" clip-rule="evenodd"/>
            </svg>
            <span>Alberto Gomez</span>
        </div>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Promo Card
    st.markdown("""
        <div class="sidebar-promo">
            <div class="sidebar-promo-icon">🚀</div>
            <div class="sidebar-promo-text">
                <strong>TFG Project</strong><br>
                <span style="font-size: 0.8rem; color: #6B7280;">VisionLeaderUFV</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

# ============================================================
# HELPER FUNCTIONS
# ============================================================
def create_section_header(title, icon="📊"):
    st.markdown(f"""
        <div class="section-header">
            <div class="section-header-icon">{icon}</div>
            <div class="section-header-text">{title}</div>
        </div>
    """, unsafe_allow_html=True)

def create_kpi_card(icon, value, label, color_class="purple"):
    return f"""
        <div class="kpi-card">
            <div class="kpi-card-menu">•••</div>
            <div class="kpi-card-icon {color_class}">{icon}</div>
            <div class="kpi-card-value">{value}</div>
            <div class="kpi-card-label">{label}</div>
        </div>
    """

def get_plotly_layout(title=""):
    return dict(
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family='Poppins, sans-serif', color='#374151', size=12),
        title=dict(text=title, font=dict(size=16, color='#1F2937', family='Poppins, sans-serif')),
        xaxis=dict(
            gridcolor='#F3F4F6',
            linecolor='#E5E7EB',
            tickfont=dict(color='#6B7280'),
            titlefont=dict(color='#374151', size=13)
        ),
        yaxis=dict(
            gridcolor='#F3F4F6',
            linecolor='#E5E7EB',
            tickfont=dict(color='#6B7280'),
            titlefont=dict(color='#374151', size=13)
        ),
        legend=dict(
            font=dict(color='#374151', size=11),
            bgcolor='rgba(255,255,255,0.9)',
            bordercolor='#E5E7EB',
            borderwidth=1
        ),
        margin=dict(l=60, r=30, t=50, b=60),
        hoverlabel=dict(
            bgcolor='white',
            font_size=12,
            font_family='Poppins, sans-serif'
        )
    )

# Color palette
COLORS = {
    'primary': '#7C3AED',
    'secondary': '#A855F7',
    'success': '#22C55E',
    'warning': '#F59E0B',
    'danger': '#EF4444',
    'info': '#3B82F6',
    'purple_gradient': ['#7C3AED', '#A855F7', '#C084FC', '#E9D5FF'],
    'chart_colors': ['#7C3AED', '#3B82F6', '#22C55E', '#F59E0B', '#EF4444', '#EC4899', '#8B5CF6', '#06B6D4']
}

# ============================================================
# MAIN CONTENT
# ============================================================

# Header (only show if not in Comparison, Confusion Matrices, By Category, Downloads, Individual Model, Visualizations, or Performance sections)
if st.session_state.current_section not in ['Comparison', 'Confusion Matrices', 'By Category', 'Downloads', 'Individual Model', 'Visualizations', 'Performance']:
    st.markdown("""
        <div style="display: flex; justify-content: space-between; align-items: flex-start; padding: 0 0 1rem 0; margin: 0;">
            <div>
                <h1 style="font-size: 1.75rem; font-weight: 700; color: #1565C0; margin: 0; padding: 0; line-height: 1.75rem;">
                    PaliGemma Evaluation Dashboard
                </h1>
                <p style="font-size: 0.9rem; color: #6B7280; margin: 0.25rem 0 0 0; padding: 0;">
                    PaliGemma model versions performance analysis and comparison
                </p>
            </div>
        </div>
    """, unsafe_allow_html=True)
        
# ============================================================
# SECTION: OVERVIEW
# ============================================================
# SECTION: OVERVIEW
# ============================================================
if st.session_state.current_section == 'Overview':
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

# ============================================================
# SECTION: COMPARISON
# ============================================================
elif st.session_state.current_section == 'Comparison':
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

# ============================================================
# SECTION: VISUALIZATIONS
# ============================================================
elif st.session_state.current_section == 'Visualizations':
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

# ============================================================
# SECTION: CONFUSION MATRICES
# ============================================================
elif st.session_state.current_section == 'Confusion Matrices':
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

# ============================================================
# SECTION: INDIVIDUAL MODEL
# ============================================================
elif st.session_state.current_section == 'Individual Model':
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

# ============================================================
# SECTION: PERFORMANCE
# ============================================================
elif st.session_state.current_section == 'Performance':
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

# ============================================================
# SECTION: BY CATEGORY
# ============================================================
elif st.session_state.current_section == 'By Category':
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

# ============================================================
# SECTION: DOWNLOADS
# ============================================================
elif st.session_state.current_section == 'Downloads':
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

# ============================================================
# FOOTER
# ============================================================
st.markdown("""
    <div style="
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        margin-top: 3rem;
        padding: 1.5rem;
        text-align: center;
        border-top: 1px solid #E5E7EB;
        background: #F8F9FC;
        color: #9CA3AF;
        font-size: 0.85rem;
        z-index: 100;
    ">
        <p style="margin: 0;">
            <strong style="color: #7C3AED;">PaliGemma Evaluation Dashboard</strong> • 
            TFG VisionLeaderUFV • 
            Built with Streamlit & Plotly
        </p>
    </div>
""", unsafe_allow_html=True)
