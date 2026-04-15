"""Sidebar navigation: logo, section buttons and footer profile chip."""
import streamlit as st


SECTIONS = {
    "Overview": "Home",
    "Comparison": "Comparison",
    "Visualizations": "Visualizations",
    "Confusion Matrices": "Confusion",
    "Individual Model": "Per Model",
    "Performance": "Performance",
    "By Category": "By Category",
    "Downloads": "Downloads",
}


def navigate_to(section: str) -> None:
    st.session_state.current_section = section


def render_sidebar() -> None:
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
