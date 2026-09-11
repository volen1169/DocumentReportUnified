import streamlit as st

from views.assets.generic_hardware_asset import render_generic_hardware_asset


PRINTER_FIELDS = {
    "Company": "บริษัท",
    "User": "User",
    "Brand_x0020__x002f__x0020_Model": "Brand/Model",
    "S_x002f_N_x0020_No_x002e_": "Serial No.",
    "field_3": "IP Address",
}


def render_card_printer(
    row,
    key,
    admin_mode,
    *,
    list_name,
    show_pop_printer,
    edit_printer_dialog,
):
    with st.container():
        st.markdown(f"""
        <div style="margin-bottom:6px;">
            <div class="hw-card-title">🖨️ {row.get('Brand_x0020__x002f__x0020_Model','Printer')}</div>
            <div class="hw-card-sub">🏢 {row.get('field_1','-')}</div>
        </div>
        <div class="hw-field"><strong>👤 User</strong>&nbsp;&nbsp;{row.get('User','-')}</div>
        {'<div class="hw-field"><strong>🔢 Serial No.</strong>&nbsp;&nbsp;%s</div>' % row.get('S_x002f_N_x0020_No_x002e_','-') if admin_mode else ''}
        {'<div class="hw-field"><strong>🌐 IP</strong>&nbsp;&nbsp;%s</div>' % row.get('field_3','-') if admin_mode else ''}
        """, unsafe_allow_html=True)
        if admin_mode:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔍 ดูข้อมูล", key=f"prn_view_{key}", use_container_width=True):
                    show_pop_printer(row.to_dict(), admin_mode=True)
            with c2:
                if st.button("✏️ แก้ไข", key=f"prn_edit_{key}", use_container_width=True):
                    edit_printer_dialog(row.to_dict(), list_name)
        else:
            st.caption("🔒 ดูข้อมูลเชิงลึกและแก้ไขเฉพาะผู้ดูแลระบบ")


def render_printer_asset(
    *,
    df_hw,
    admin_mode,
    show_pop_printer,
    add_printer_dialog,
    edit_printer_dialog,
):
    list_name = "Asset Printer"
    hardware_name = "Printer"

    def card_renderer(row, key, is_admin):
        render_card_printer(
            row,
            key,
            is_admin,
            list_name=list_name,
            show_pop_printer=show_pop_printer,
            edit_printer_dialog=edit_printer_dialog,
        )

    render_generic_hardware_asset(
        df_hw=df_hw,
        list_name=list_name,
        hardware_name=hardware_name,
        admin_mode=admin_mode,
        card_renderer=card_renderer,
        add_handler=add_printer_dialog,
        add_button_label="➕ เพิ่ม Printer",
        search_fields=tuple(PRINTER_FIELDS),
    )
