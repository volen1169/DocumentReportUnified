import streamlit as st


def render_generic_hardware_asset(
    *,
    df_hw,
    list_name,
    hardware_name,
    admin_mode,
    show_pop_computer,
    add_computer_dialog,
    edit_computer_dialog,
):
    st.markdown(f"""
        <div class="asset-hero">
            <div class="asset-title">💻 {hardware_name}</div>
            <div class="asset-sub">
                ระบบจัดการ{hardware_name}และทรัพย์สิน IT ทั้งหมด
            </div>
        </div>
        """, unsafe_allow_html=True)

    total_assets = len(df_hw)
    active_assets = len(df_hw[df_hw["Status"] == "Active"]) if not df_hw.empty else 0
    inactive_assets = len(df_hw[df_hw["Status"] == "Inactive"]) if not df_hw.empty else 0
    repair_assets = len(df_hw[df_hw["Status"] == "Repair"]) if not df_hw.empty else 0

    # ใช้ Streamlit metric แทน HTML เพื่อป้องกัน HTML render เป็น text
    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.metric("TOTAL ASSETS", total_assets)

    with m2:
        st.metric("ACTIVE", active_assets)

    with m3:
        st.metric("INACTIVE", inactive_assets)

    with m4:
        st.metric("REPAIR", repair_assets)

    col_search, col_add = st.columns([0.82, 0.18])

    with col_search:
        search = st.text_input(
            "",
            placeholder="🔍 ค้นหาชื่อพนักงาน, Hostname, Model, S/N...",
            label_visibility="collapsed"
        )

    with col_add:
        if admin_mode:
            if st.button("➕ เพิ่มคอมพิวเตอร์", use_container_width=True, type="primary"):
                add_computer_dialog(list_name)

    if search and not df_hw.empty:
        df_hw = df_hw[df_hw.astype(str).apply(
            lambda x: x.str.contains(search, case=False)
        ).any(axis=1)]

    cols = st.columns(3)

    for i, (idx, row) in enumerate(df_hw.iterrows()):

        with cols[i % 3]:

            name = row.get("field_3", "Unknown")
            initials = "".join([x[0] for x in name.split()[:2]]).upper()

            status = row.get("Status", "Active")
            badge_class = "badge-active" if status == "Active" else "badge-inactive"

            with st.container(border=True):
                st.markdown(f"### 👤 {name}")
                st.caption(f"🏢 {row.get('field_1','-')}  |  Status: {status}")
                st.write(f"💻 Hostname: {row.get('field_6','-')}")
                st.write(f"🏷️ Model: {row.get('field_7','-')}")
                st.write(f"💾 RAM: {row.get('field_13','-')}")
                st.write(f"🔢 Serial: {row.get('field_8','-')}")

            if admin_mode:
                b1, b2 = st.columns(2)

                with b1:
                    if st.button("🔍 ดูข้อมูล", key=f"view_{idx}", use_container_width=True):
                        show_pop_computer(row.to_dict())

                with b2:
                    if st.button("✏️ แก้ไข", key=f"edit_{idx}", use_container_width=True):
                        edit_computer_dialog(row.to_dict(), list_name)
            else:
                st.caption("🔒 ดูรายละเอียดเพิ่มเติมได้เฉพาะผู้ดูแลระบบ")
