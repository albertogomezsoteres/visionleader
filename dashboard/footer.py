"""Fixed footer rendered at the bottom of every dashboard page."""
import streamlit as st


def render_footer() -> None:
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
