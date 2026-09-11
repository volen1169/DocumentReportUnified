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
    metric_config,
    search_placeholder="ค้นหาข้อมูล...",
):
    st.markdown(f"""
        <div class="asset-hero">
            <div class="asset-title">💻 {hardware_name}</div>
            <div class="asset-sub">
                ระบบจัดการ{hardware_name}และทรัพย์สิน IT ทั้งหมด
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ใช้ Streamlit metric แทน HTML เพื่อป้องกัน HTML render เป็น text
    metric_columns = st.columns(len(metric_config))
    for column, (label, resolver) in zip(metric_columns, metric_config):
        with column:
            st.metric(label, resolver(df_hw))

    col_search, col_add = st.columns([0.82, 0.18])

    with col_search:
        search = st.text_input(
            "",
            placeholder=search_placeholder,
            label_visibility="collapsed"
        )

    with col_add:
        if admin_mode and add_handler is not None:
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
