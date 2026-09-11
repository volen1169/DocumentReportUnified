import streamlit as st


def render_generic_hardware_asset(
    *,
    df_hw,
    list_name,
    hardware_name,
    admin_mode,
    card_renderer,
    add_handler,
    add_button_label,
    search_fields,
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
            if st.button(add_button_label, use_container_width=True, type="primary"):
                add_handler(list_name)

    if search and not df_hw.empty:
        searchable_columns = [field for field in search_fields if field in df_hw.columns]
        searchable_df = df_hw[searchable_columns] if searchable_columns else df_hw.iloc[:, 0:0]
        df_hw = df_hw[searchable_df.astype(str).apply(
            lambda x: x.str.contains(search, case=False)
        ).any(axis=1)]

    cols = st.columns(3)

    for i, (idx, row) in enumerate(df_hw.iterrows()):

        with cols[i % 3]:
            card_renderer(row, idx, admin_mode)
