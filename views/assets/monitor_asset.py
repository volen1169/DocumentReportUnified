import streamlit as st

from views.assets.generic_hardware_asset import render_generic_hardware_asset


MONITOR_FIELDS = {
    "field_1": "บริษัท",
    "field_3": "ชื่อพนักงาน",
    "field_2": "Brand/Model",
    "field_4": "Serial No.",
    "Status": "Status",
}


MONITOR_METRICS = (
    ("TOTAL ASSETS", lambda frame: len(frame)),
    ("ACTIVE", lambda frame: int(frame["Status"].eq("Active").sum()) if "Status" in frame else 0),
    ("INACTIVE", lambda frame: int(frame["Status"].eq("Inactive").sum()) if "Status" in frame else 0),
    ("REPAIR", lambda frame: int(frame["Status"].eq("Repair").sum()) if "Status" in frame else 0),
)


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
    status = row.get("Status", "")
    with st.container():
        st.markdown(f"""
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px;">
            <div>
                <div class="hw-card-title">👤 {row.get('field_3','N/A')}</div>
                <div class="hw-card-sub">🏢 {row.get('field_1','-')}</div>
            </div>
            {badge_renderer(status)}
        </div>
        <div class="hw-field"><strong>🖥️ Model</strong>&nbsp;&nbsp;{row.get('field_2','-')}</div>
        {'<div class="hw-field"><strong>🔢 Serial No.</strong>&nbsp;&nbsp;%s</div>' % row.get('field_4','-') if admin_mode else ''}
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
