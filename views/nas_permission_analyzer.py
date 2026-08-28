import html
import re

import pandas as pd
import streamlit as st

from services.ad_directory import (
    format_nas_export_policy_names,
    format_policy_descriptions,
    format_policy_names,
    get_ad_agent_policy_summary,
    get_ad_group_names_for_user,
    get_ldap_group_names_for_user,
    get_user_internet_policy_summary,
    ldap_find_user,
)
from services.microsoft_graph import graph_find_user
from services.nas_export import (
    build_nas_csv,
    build_nas_excel,
    build_nas_export_dataframe_from_permissions,
    prepare_nas_export_permissions,
    resolve_nas_export_profile,
)
from services.nas_service import load_nas_data


def render_nas_permission_analyzer(
    *,
    admin_mode: bool,
    page_header,
    clean_nas_principal,
) -> None:
    page_header("📂", "NAS Permission Analyzer", "ตรวจสอบสิทธิ์การเข้าถึง Share บน Synology NAS")
    st.info("🔒 ข้อมูลสิทธิ์ NAS เป็น Read-only — กรุณาแก้ไขผ่าน Synology DSM โดยตรง")
    st.markdown("---")

    if 'nas_df' not in st.session_state or st.session_state.nas_df is None:
        with st.spinner("กำลังดึงข้อมูลจาก NAS..."):
            df_result = load_nas_data()
            st.session_state.nas_df = df_result if df_result is not None else None
            if df_result is None:
                st.error("ไม่สามารถเชื่อมต่อ NAS ได้")

    if st.session_state.nas_df is not None:
        display_df = st.session_state.nas_df.copy()

        st.markdown("""
            <style>
            .nas-hero-search{
                background:linear-gradient(135deg,#ffffff,#f8faff);
                border:1px solid #e2e8f0;
                border-radius:22px;
                padding:22px;
                margin-bottom:20px;
                box-shadow:0 10px 30px rgba(99,102,241,.08);
}

            .nas-modern-card{
                background:linear-gradient(180deg,#ffffff 0%, #fafbff 100%);
                border:1px solid #e2e8f0;
                border-radius:24px;
                padding:22px;
                margin-bottom:18px;
                box-shadow:0 8px 30px rgba(15,23,42,.05);
                transition:all .2s ease;
}

            .nas-modern-card:hover{
                transform:translateY(-2px);
                box-shadow:0 18px 40px rgba(99,102,241,.12);
}

            /* ป้องกัน block ว่างจาก markdown div */
            .nas-modern-card:empty{
                display:none !important;
                padding:0 !important;
                margin:0 !important;
                border:none !important;
}

            .nas-card-title{
                font-size:1.15rem;
                font-weight:800;
                color:#312e81;
                margin-top:8px;
}

            .nas-mini-stat{
                display:inline-flex;
                align-items:center;
                gap:6px;
                padding:7px 12px;
                border-radius:999px;
                background:#eef2ff;
                color:#4f46e5;
                font-size:.76rem;
                font-weight:700;
                margin-right:8px;
                margin-top:10px;
}

            .nas-section-title{
                font-size:.72rem;
                font-weight:800;
                letter-spacing:1px;
                text-transform:uppercase;
                color:#94a3b8;
                margin-bottom:10px;
}

            .nas-user-pill{
                display:inline-flex;
                align-items:center;
                padding:6px 12px;
                border-radius:999px;
                font-size:.76rem;
                font-weight:700;
                margin:4px;
}

            .nas-user-rw{
                background:rgba(99,102,241,.14);
                color:#4338ca;
                border:1px solid rgba(99,102,241,.20);
}

            .nas-user-ro{
                background:#dcfce7;
                color:#166534;
                border:1px solid #86efac;
}
            </style>
            """, unsafe_allow_html=True)

        total_shares = len(display_df)

        total_rw = 0
        total_ro = 0

        for _, row in display_df.iterrows():
            if row["Matched Employees"]:
                for staff in row["Matched Employees"].split(", "):
                    if "Read/Write" in staff:
                        total_rw += 1
                    else:
                        total_ro += 1

        s1, s2, s3 = st.columns(3)
        with s1:
            st.metric("📁 Shares", total_shares)
        with s2:
            st.metric("🔐 Read / Write", total_rw)
        with s3:
            st.metric("👁 Read Only", total_ro)



        col_s, col_r = st.columns([0.82, 0.18])

        with col_s:
            search_term = st.text_input(
                "🔎 Search User / Share Drive",
                "",
                placeholder="ค้นหา Share Drive หรือ Username..."
            )

        with col_r:


            if st.button("🔄 Refresh", use_container_width=True):
                load_nas_data.clear()
                ldap_find_user.clear()
                get_ldap_group_names_for_user.clear()
                get_ad_agent_policy_summary.clear()
                graph_find_user.clear()
                get_ad_group_names_for_user.clear()
                st.session_state.nas_df = load_nas_data()
                st.rerun()



        if search_term:
            # แสดง Internet Policy ของ User ที่ค้นหา จาก AD / Firewall Group
            # ถ้าค้นหาเป็นชื่อ Share Drive อย่างเดียว อาจไม่พบ User ใน AD ซึ่งระบบจะแจ้งแบบไม่ทำให้หน้าล่ม
            policy_summary = get_user_internet_policy_summary(search_term)
            if policy_summary.get("ok") and policy_summary.get("policies"):
                _policy_rows = policy_summary.get("policies", [])
                _policy_names = [
                    str(policy.get("Policy Name") or policy.get("Policy Internet") or "-")
                    for policy in _policy_rows
                ]
                st.markdown(
                    f"""
                        <div style="margin:8px 0 14px;padding:14px 18px;border:1px solid #BFDBFE;
                        border-radius:16px;background:linear-gradient(135deg,#EFF6FF,#F8FAFF);
                        color:#1E3A8A;font-size:0.92rem;">
                            <b>Internet Policy</b>
                            <span style="margin-left:8px;color:#475569;">
                                พบ {len(_policy_rows)} policy: {html.escape(", ".join(_policy_names[:3]))}
                            </span>
                        </div>
                        """,
                    unsafe_allow_html=True,
                )
                with st.expander("ดูรายละเอียด Internet Policy / AD Groups"):
                    st.dataframe(
                        pd.DataFrame(_policy_rows),
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.caption("AD Groups: " + (", ".join(policy_summary.get("groups", [])) or "-"))
            elif policy_summary.get("ok"):
                st.info("🌐 ไม่พบ AD Group ที่ตรงกับ Internet Policy เช่น FW_Officer_B / FW_IT สำหรับคำค้นหานี้")
            else:
                st.warning(f"🌐 ยังดึง Internet Policy จาก AD ไม่ได้: {policy_summary.get('error', '')}")

            display_df = display_df[
                display_df["Share"].str.contains(search_term, case=False, na=False) |
                display_df["Matched Employees"].str.contains(search_term, case=False, na=False) |
                display_df["ACL Tags (Raw)"].str.contains(search_term, case=False, na=False)
            ]

        # --------------------------------------------------
        # Export CSV / Excel (matrix: one Share Drive per column)
        # --------------------------------------------------
        @st.cache_data(ttl=900, show_spinner=False)
        def _nas_export_ad_profile(entity):
            """Use exactly the same AD lookup path as AD / Firewall Policy."""
            return resolve_nas_export_profile(
                entity,
                clean_principal=clean_nas_principal,
                policy_lookup=get_user_internet_policy_summary,
                policy_formatter=format_nas_export_policy_names,
            )

        prepared_export = prepare_nas_export_permissions(
            display_df,
            clean_principal=clean_nas_principal,
        )
        _, permission_by_user = prepared_export
        if permission_by_user:
            with st.spinner("กำลังจับคู่ Company, Department และ Firewall Policy จาก AD..."):
                export_df = build_nas_export_dataframe_from_permissions(
                    prepared_export,
                    profile_lookup=_nas_export_ad_profile,
                )
        else:
            export_df = build_nas_export_dataframe_from_permissions(
                prepared_export,
                profile_lookup=_nas_export_ad_profile,
            )

        csv_data = build_nas_csv(export_df)
        excel_data = build_nas_excel(export_df)

        if admin_mode:
            export_col1, export_col2, _ = st.columns([0.18, 0.18, 0.64])
            with export_col1:
                st.download_button("📥 Export CSV", csv_data, "User_permission_listt.csv", "text/csv", use_container_width=True)
            with export_col2:
                st.download_button("📊 Export Excel", excel_data, "User_permission_listt.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        else:
            st.info("🔒 Export ข้อมูล NAS ได้เฉพาะผู้ดูแลระบบ")

        for idx, row in display_df.iterrows():

            rw_users = []
            ro_users = []

            raw_acl = str(row['ACL Tags (Raw)'])

            if raw_acl and raw_acl != "nan":

                for item in [x.strip() for x in raw_acl.split(',')]:

                    m = re.search(r"^(.*?)\s*\((Read(?:/Write)?)\)", item)

                    if m:

                        entity = clean_nas_principal(m.group(1))

                        permission = m.group(2)

                        if permission == "Read/Write":
                            rw_users.append(entity)
                        else:
                            ro_users.append(entity)

            st.markdown('<div class="nas-modern-card">', unsafe_allow_html=True)

            top1, top2 = st.columns([0.75, 0.25])

            with top1:
                card_html = f"<div style='display:flex;align-items:center;gap:16px;'>" \
                    f"<div style='width:74px;height:74px;border-radius:20px;background:linear-gradient(135deg,#ede9fe,#c4b5fd);display:flex;align-items:center;justify-content:center;font-size:2rem;border:1px solid #c4b5fd;'>📁</div>" \
                    f"<div>" \
                    f"<div class='nas-card-title'>{row['Share']}</div>" \
                    f"<div class='nas-mini-stat'>👥 {len(rw_users)+len(ro_users)} Users</div>" \
                    f"<div class='nas-mini-stat'>🔐 {len(rw_users)} RW</div>" \
                    f"<div class='nas-mini-stat'>👁 {len(ro_users)} Read</div>" \
                    f"</div></div>"

                st.markdown(card_html, unsafe_allow_html=True)

            with top2:

                if st.button("🔎 รายละเอียด", key=f"acl_{idx}", use_container_width=True):

                    @st.dialog("📜 Authorized Users/Groups")
                    def show_acl_pop(raw):
                        if raw:
                            parsed = []
                            for item in [t.strip() for t in raw.split(',')]:
                                m = re.search(r"^(.*?)\s*\((Read(?:/Write)?)\)", item)
                                if m:
                                    e = clean_nas_principal(m.group(1))
                                    if e:
                                        policy_summary = get_user_internet_policy_summary(e)
                                        policies = policy_summary.get("policies", [])
                                        parsed.append({
                                            "Entity": e,
                                            "Permission": m.group(2),
                                            "Policy Internet": format_policy_names(policies),
                                            "Policy Description": format_policy_descriptions(policies),
                                            "AD Groups": ", ".join(policy_summary.get("groups", [])) if policy_summary.get("ok") else f"Error: {policy_summary.get('error', '')}",
                                        })

                            if parsed:
                                parsed_df = pd.DataFrame(parsed)

                                tab_perm, tab_policy, tab_raw = st.tabs([
                                    "NAS Permission",
                                    "Internet Policy",
                                    "Raw ACL",
                                ])

                                with tab_perm:
                                    st.dataframe(
                                        parsed_df[["Entity", "Permission"]],
                                        use_container_width=True,
                                        hide_index=True
                                    )

                                with tab_policy:
                                    policy_df = parsed_df[[
                                        "Entity",
                                        "Policy Internet",
                                        "Policy Description",
                                        "AD Groups",
                                    ]]
                                    st.dataframe(
                                        policy_df,
                                        use_container_width=True,
                                        hide_index=True
                                    )
                                    st.caption("ดึงจาก AD / Entra ID Group ที่ขึ้นต้นด้วย FW_ แล้วเทียบกับ FW_POLICY_MAP ในโค้ด")

                                with tab_raw:
                                    st.code(raw)
                            else:
                                st.info("ไม่พบรายการ ACL ที่อ่านได้")
                                with st.expander("Raw ACL"):
                                    st.code(raw)

                    show_acl_pop(row['ACL Tags (Raw)'])


            if not rw_users and not ro_users:
                st.info("ไม่พบผู้ใช้งาน")
            else:
                st.markdown(
                    f"""
                        <div style='margin-top:10px;padding:14px 18px;border-radius:16px;
                        background:linear-gradient(135deg,#eef2ff,#f8faff);
                        border:1px solid #dbeafe;
                        color:#475569;
                        font-size:0.92rem;
                        font-weight:600;'>
                        🔐 พบผู้ใช้งานที่มีสิทธิ์ทั้งหมด <b>{len(rw_users)+len(ro_users)}</b> รายการ
                        </div>
                        """,
                    unsafe_allow_html=True
                )

            # ปิด div ของ nas-modern-card เพื่อป้องกัน layout เพี้ยน/เกิดช่องว่างสีขาว
            st.markdown('</div>', unsafe_allow_html=True)




    # -------------------------------------------------------
    # 🔑 Password Information
    # -------------------------------------------------------
