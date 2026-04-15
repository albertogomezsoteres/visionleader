"""Reusable presentational helpers shared across dashboard sections."""
import streamlit as st


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
