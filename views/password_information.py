import streamlit as st

from services.display_helpers import get_sheet_icon
from services.excel_storage import (
    PASSWORD_FILE_NAME,
    SHAREPOINT_FOLDER,
    load_password_excel,
)


def render_password_information(
    *,
    admin_mode: bool,
    page_header,
    render_password_card,
    add_password_dialog,
    edit_password_dialog,
) -> None:
    page_header("🔑", "Password Manager", "ข้อมูล Credentials และรหัสผ่านระบบ")

    with st.spinner("กำลังโหลด..."):
        pw_result = load_password_excel()
        pw_sheets, drive_id = pw_result if isinstance(pw_result, tuple) else ({}, None)

    if not pw_sheets or "_error" in pw_sheets:
        err = pw_sheets.get("_error", "ไม่ทราบสาเหตุ") if pw_sheets else "ไม่ได้รับข้อมูลจาก SharePoint"
        st.error(f"❌ ไม่สามารถโหลดไฟล์ได้")
        st.code(err, language="text")
        st.info(f"💡 ตรวจสอบ: ชื่อโฟลเดอร์ = '{SHAREPOINT_FOLDER}' / ชื่อไฟล์ = '{PASSWORD_FILE_NAME}'")
    else:
        sheet_names = list(pw_sheets.keys())
        selected_sheet = st.selectbox("📋 หมวดหมู่:", sheet_names, key="pw_sheet_select")
        df_pw = pw_sheets[selected_sheet].copy()
        sheet_icon = get_sheet_icon(selected_sheet)

        col_title, col_add = st.columns([0.8, 0.2])
        with col_title:
            st.subheader(f"{sheet_icon} {selected_sheet}")
            st.caption(f"พบข้อมูลทั้งหมด {len(df_pw)} รายการ")
        with col_add:
            if admin_mode:
                st.write("##")
                if st.button("➕ เพิ่มรายการ", use_container_width=True, type="primary"):
                    add_password_dialog(selected_sheet, df_pw, drive_id, pw_sheets)

        st.markdown("---")

        if df_pw.empty: st.warning("ไม่มีข้อมูลในชีทนี้")
        else:
            card_cols = st.columns(2)
            def _render_password_sheet_row(row_index, row_data):
                render_password_card(row_data, selected_sheet, row_index, admin_mode, df_pw, drive_id, pw_sheets)
                if admin_mode and st.session_state.get(f"pw_edit_row_{selected_sheet}_{row_index}"):
                    st.session_state.pop(f"pw_edit_row_{selected_sheet}_{row_index}")
                    edit_password_dialog(row_data, row_index, selected_sheet, df_pw, drive_id, pw_sheets)
            for idx, row in df_pw.iterrows():
                with card_cols[idx % 2]: _render_password_sheet_row(idx, row)
