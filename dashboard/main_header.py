"""Top-of-page header rendered only on Overview-style sections."""
import streamlit as st


def render_header() -> None:
    if st.session_state.current_section in [
        'Comparison', 'Confusion Matrices', 'By Category',
        'Downloads', 'Individual Model', 'Visualizations', 'Performance',
    ]:
        return
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
