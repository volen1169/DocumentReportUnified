"""Lightweight Report workspace page."""

import streamlit as st


def render_report_view() -> None:
    """Render the Report landing page without loading report data."""
    st.title("Report")
    st.write("ศูนย์รวมรายงานและการวิเคราะห์ข้อมูล")
    st.info("ยังไม่มีรายงานที่เปิดใช้งาน")
