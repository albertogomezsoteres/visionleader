"""Inject the dashboard premium CSS+JS theme into the Streamlit page."""
import streamlit as st


def inject_styles() -> None:
    st.markdown(_CSS_AND_JS, unsafe_allow_html=True)


_CSS_AND_JS = r"""
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
"""
