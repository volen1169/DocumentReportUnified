import streamlit as st
import pandas as pd

from views.assets.generic_hardware_asset import render_generic_hardware_asset


MONITOR_FIELDS = {
    "Company": "บริษัท",
    "User": "ชื่อพนักงาน",
    "Brand_x002f_Model": "Brand/Model",
    "S_x002f_NNo_x002e_": "Serial No.",
    "Status": "Status",
}


MONITOR_METRICS = (
    ("TOTAL ASSETS", lambda frame: len(frame)),
    ("ACTIVE", lambda frame: int(frame["Status"].eq("Active").sum()) if "Status" in frame else 0),
    ("INACTIVE", lambda frame: int(frame["Status"].eq("Inactive").sum()) if "Status" in frame else 0),
    ("REPAIR", lambda frame: int(frame["Status"].eq("Repair").sum()) if "Status" in frame else 0),
)


def _display_value(value, default="-"):
    """Return a presentation-safe value without changing the source row."""
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text if text else default


def render_card_monitor(
    row,
    key,
    admin_mode,
    *,
    list_name,
    show_pop_monitor,
    edit_monitor_dialog,
    badge_renderer,
):
    status = _display_value(row.get("Status"), default="")
    employee = _display_value(row.get("User"), default="N/A")
    company = _display_value(row.get("Company"))
    model = _display_value(row.get("Brand_x002f_Model"))
    serial = _display_value(row.get("S_x002f_NNo_x002e_"))
    with st.container():
        st.markdown(f"""
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px;">
            <div>
                <div class="hw-card-title">👤 {employee}</div>
                <div class="hw-card-sub">🏢 {company}</div>
            </div>
            {badge_renderer(status)}
        </div>
        <div class="hw-field"><strong>🖥️ Model</strong>&nbsp;&nbsp;{model}</div>
        {'<div class="hw-field"><strong>🔢 Serial No.</strong>&nbsp;&nbsp;%s</div>' % serial if admin_mode else ''}
        """, unsafe_allow_html=True)
        if admin_mode:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔍 ดูข้อมูล", key=f"mon_view_{key}", use_container_width=True):
                    show_pop_monitor(row.to_dict(), admin_mode=True)
            with c2:
                if st.button("✏️ แก้ไข", key=f"mon_edit_{key}", use_container_width=True):
                    edit_monitor_dialog(row.to_dict(), list_name)
        else:
            st.caption("🔒 ดูข้อมูลเชิงลึกและแก้ไขเฉพาะผู้ดูแลระบบ")


def render_monitor_asset(
    *,
    df_hw,
    admin_mode,
    show_pop_monitor,
    add_monitor_dialog,
    edit_monitor_dialog,
    badge_renderer,
):
    list_name = "Asset Monitor"
    hardware_name = "Monitor"

    def card_renderer(row, key, is_admin):
        render_card_monitor(
            row,
            key,
            is_admin,
            list_name=list_name,
            show_pop_monitor=show_pop_monitor,
            edit_monitor_dialog=edit_monitor_dialog,
            badge_renderer=badge_renderer,
        )

    render_generic_hardware_asset(
        df_hw=df_hw,
        list_name=list_name,
        hardware_name=hardware_name,
        admin_mode=admin_mode,
        card_renderer=card_renderer,
        add_handler=add_monitor_dialog,
        add_button_label="➕ เพิ่ม Monitor",
        search_fields=tuple(MONITOR_FIELDS),
        metric_config=MONITOR_METRICS,
        search_placeholder="🔍 ค้นหาบริษัท, ชื่อพนักงาน, รุ่น, Serial No....",
    )
