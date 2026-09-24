
import html
import math

import pandas as pd
import streamlit as st


MONITOR_FIELDS = {
    "Company": "บริษัท",
    "User": "ชื่อพนักงาน",
    "Brand_x002f_Model": "Brand/Model",
    "S_x002f_NNo_x002e_": "Serial No.",
    "Status": "Status",
}


def _display_value(value, default="-"):
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text if text else default


def _status_value(row):
    return _display_value(row.get("Status"), default="-")


def _status_class(status):
    normalized = str(status or "").strip().casefold()
    if normalized == "active":
        return "active"
    if normalized == "inactive":
        return "inactive"
    return "other"


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
    frame = df_hw.copy() if isinstance(df_hw, pd.DataFrame) else pd.DataFrame()

    st.markdown(
        """
        <div class="ma-page"></div>
        <style>
        .stApp:has(.ma-page) [data-testid="stMainBlockContainer"]{background:transparent!important;padding-top:6px!important}
        .stApp:has(.ma-page) [data-testid="stHeader"],.stApp:has(.ma-page) [data-testid="stToolbar"]{display:none!important}
        .stApp:has(.ma-page) [data-testid="stVerticalBlock"]{gap:.62rem}.ma-page{display:none}
        .ma-header{min-height:94px;box-sizing:border-box;display:flex;align-items:center;gap:15px;padding:16px 21px;margin-bottom:10px;background:#FFF;border:1px solid #E2E8F0;border-radius:20px;box-shadow:0 10px 26px rgba(15,23,42,.055)}
        .ma-header-icon{width:54px;height:54px;flex:0 0 54px;display:grid;place-items:center;color:#4F46E5;background:#F3F5FF;border:1px solid #E0E7FF;border-radius:16px;font-size:27px}
        .ma-header h1{margin:0 0 4px!important;color:#0F172A!important;font-size:24px!important;font-weight:850;letter-spacing:-.035em}
        .ma-header p{margin:0!important;color:#64748B!important;font-size:12px!important}
        .ma-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:10px}
        .ma-card{position:relative;height:94px;box-sizing:border-box;padding:13px 14px;background:#FFF;border:1px solid #E2E8F0;border-radius:17px;box-shadow:0 7px 18px rgba(15,23,42,.04);overflow:hidden}
        .ma-card:after{content:"";position:absolute;inset:auto 0 0;height:3px;background:var(--tone)}
        .ma-card-label{color:#475569;font-size:10.5px;font-weight:800}
        .ma-card-value{margin-top:7px;color:#0F172A;font-size:25px;line-height:1;font-weight:850;letter-spacing:-.04em}
        .ma-card-foot{position:absolute;left:14px;right:14px;bottom:10px;display:flex;justify-content:space-between;color:#64748B;font-size:10px}
        .ma-card-foot strong{color:var(--tone)}
        .stApp:has(.ma-page) .stTextInput input,.stApp:has(.ma-page) .stSelectbox div[data-baseweb="select"]>div{height:42px!important;min-height:42px!important;border:1px solid #DDE5EF!important;border-radius:12px!important;background:#FFF!important;font-size:12px!important}
        .stApp:has(.ma-page) .stButton>button,.stApp:has(.ma-page) .stDownloadButton>button{height:40px;min-height:40px;border-radius:11px;border-color:#E2E8F0;font-size:12px;font-weight:750}
        .stApp:has(.ma-page) button[kind="primary"]{color:#FFF!important;border:0!important;background:linear-gradient(135deg,#3B82F6,#7C3AED)!important;box-shadow:0 7px 16px rgba(99,102,241,.18)}
        .ma-table-title{height:50px;display:flex;align-items:center;justify-content:space-between;padding:0 14px;background:#FFF;border:1px solid #E2E8F0;border-bottom:0;border-radius:18px 18px 0 0;color:#334155;font-size:12px;font-weight:800}
        .ma-table-title-left{display:flex;align-items:center;gap:8px}.ma-table-title-left span{width:29px;height:29px;display:grid;place-items:center;border-radius:9px;background:#EEF2FF;color:#4F46E5}
        .ma-table-title-right{color:#64748B;font-size:10.5px;font-weight:700}
        .stApp:has(.ma-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ma-grid-marker){padding:0!important;border:1px solid #E2E8F0!important;border-radius:0 0 17px 17px!important;background:#FFF!important;box-shadow:0 8px 22px rgba(15,23,42,.045)!important;overflow:hidden}
        .stApp:has(.ma-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ma-grid-marker)>div{padding:0!important}
        .ma-grid-marker{display:none}.ma-head{height:42px;display:flex;align-items:center;padding:0 10px;color:#475569;background:#F8FAFC;font-size:10.5px;font-weight:850;white-space:nowrap}
        .ma-cell{height:42px;display:flex;align-items:center;padding:0 10px;color:#334155;font-size:11.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .ma-status-wrap{height:42px;display:flex;align-items:center;padding-left:6px}.ma-status{display:inline-flex;align-items:center;gap:5px;padding:4px 8px;border-radius:999px;font-size:10px;font-weight:850}
        .ma-status:before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}
        .ma-status-active{background:#ECFDF5;color:#059669}.ma-status-inactive{background:#FEF2F2;color:#DC2626}.ma-status-other{background:#F1F5F9;color:#64748B}
        .ma-divider{height:1px;margin:0;background:#EDF2F7}.ma-footer{height:44px;display:flex;align-items:center;justify-content:space-between;padding:0 14px;color:#64748B;font-size:10.5px;border-top:1px solid #E2E8F0}
        .stApp:has(.ma-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ma-grid-marker) [data-testid="stVerticalBlock"]{gap:0!important}
        .stApp:has(.ma-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ma-grid-marker) [data-testid="stElementContainer"]{margin:0!important}
        .stApp:has(.ma-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ma-grid-marker) [data-testid="stHorizontalBlock"]{gap:0!important}
        .stApp:has(.ma-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ma-grid-marker) [data-testid="column"]{border-right:1px solid #EDF2F7}
        .stApp:has(.ma-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ma-grid-marker) [data-testid="column"]:last-child{border-right:0}
        .stApp:has(.ma-page) [class*="st-key-ma_view_"] button,.stApp:has(.ma-page) [class*="st-key-ma_edit_"] button{width:30px!important;min-width:30px!important;max-width:30px!important;height:30px!important;min-height:30px!important;max-height:30px!important;padding:0!important;margin:0 auto!important;border-radius:9px!important;box-shadow:none!important}
        .stApp:has(.ma-page) [class*="st-key-ma_view_"] button{color:#2563EB!important;background:#EFF6FF!important;border-color:#DBEAFE!important}
        .stApp:has(.ma-page) [class*="st-key-ma_edit_"] button{color:#7C3AED!important;background:#F5F3FF!important;border-color:#EDE9FE!important}
        .ma-analytics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:12px}
        .ma-chart{min-height:220px;box-sizing:border-box;padding:15px;background:#FFF;border:1px solid #E2E8F0;border-radius:17px;box-shadow:0 7px 18px rgba(15,23,42,.04);overflow:hidden}
        .ma-chart-title{margin-bottom:12px;color:#0F172A;font-size:12.5px;font-weight:850}.ma-bars{display:grid;gap:11px}
        .ma-bar-row{display:grid;grid-template-columns:95px 1fr 30px;align-items:center;gap:8px;color:#475569;font-size:10px}.ma-bar-label{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .ma-track{height:7px;background:#EEF2FF;border-radius:99px;overflow:hidden}.ma-fill{height:100%;border-radius:99px;background:linear-gradient(90deg,#3B82F6,#8B5CF6)}
        .ma-bar-row strong{text-align:right;color:#334155}.ma-legend{display:grid;gap:12px;margin-top:8px}.ma-legend-row{display:grid;grid-template-columns:9px 1fr auto;align-items:center;gap:8px;color:#64748B;font-size:10.5px}
        .ma-dot{width:8px;height:8px;border-radius:50%}.ma-dot.active{background:#10B981}.ma-dot.inactive{background:#EF4444}.ma-dot.other{background:#94A3B8}.ma-legend-row b{color:#334155}
        @media(max-width:1100px){.ma-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.ma-analytics{grid-template-columns:1fr}}
        @media(max-width:700px){.ma-header{min-height:105px}.ma-metrics{grid-template-columns:1fr}}
        </style>
        """,
        unsafe_allow_html=True,
    )

    total = len(frame)
    statuses = frame["Status"].astype(str).str.strip() if "Status" in frame.columns else pd.Series(dtype=str)
    active = int(statuses.eq("Active").sum())
    inactive = int(statuses.eq("Inactive").sum())
    company_count = int(frame["Company"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().nunique()) if "Company" in frame.columns else 0

    def pct(value):
        return (value / total * 100.0) if total else 0.0

    st.markdown(
        '<section class="ma-header"><div class="ma-header-icon">🖥️</div><div><h1>Monitor Asset</h1><p>จัดการข้อมูล Monitor ทั้งหมดในองค์กร</p></div></section>',
        unsafe_allow_html=True,
    )

    metrics = [
        ("TOTAL MONITORS", total, "#2563EB", "เครื่อง", f"{pct(total):.2f}%"),
        ("ACTIVE", active, "#10B981", "เครื่อง", f"{pct(active):.2f}%"),
        ("INACTIVE", inactive, "#EF4444", "เครื่อง", f"{pct(inactive):.2f}%"),
        ("บริษัท", company_count, "#8B5CF6", "บริษัท", ""),
    ]
    st.markdown(
        '<div class="ma-metrics">'
        + "".join(
            f'<div class="ma-card" style="--tone:{tone}"><div class="ma-card-label">{html.escape(label)}</div><div class="ma-card-value">{value:,}</div><div class="ma-card-foot"><span>{html.escape(unit)}</span>{f"<strong>{foot}</strong>" if foot else ""}</div></div>'
            for label, value, tone, unit, foot in metrics
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    companies = sorted({_display_value(r.get("Company"), default="") for _, r in frame.iterrows() if _display_value(r.get("Company"), default="")})
    models = sorted({_display_value(r.get("Brand_x002f_Model"), default="") for _, r in frame.iterrows() if _display_value(r.get("Brand_x002f_Model"), default="")})
    status_options = sorted({_status_value(r) for _, r in frame.iterrows() if _status_value(r) != "-"})

    f1, f2, f3, f4, f5 = st.columns([3.2, 1.25, 1.25, 1.55, 1.05])
    with f1:
        search = st.text_input("ค้นหา", placeholder="ค้นหา User, บริษัท, Brand/Model, Serial No.", label_visibility="collapsed", key="ma_search")
    with f2:
        company_filter = st.selectbox("บริษัท", ["ทั้งหมด"] + companies, label_visibility="collapsed", key="ma_company")
    with f3:
        status_filter = st.selectbox("Status", ["ทั้งหมด"] + status_options, label_visibility="collapsed", key="ma_status")
    with f4:
        model_filter = st.selectbox("Brand/Model", ["ทั้งหมด"] + models, label_visibility="collapsed", key="ma_model")
    with f5:
        if st.button("↻ ล้าง", use_container_width=True, key="ma_reset"):
            for key in ("ma_search", "ma_company", "ma_status", "ma_model"):
                st.session_state.pop(key, None)
            st.rerun()

    filtered = frame.copy()
    if search:
        searchable = [c for c in ("Company", "User", "Brand_x002f_Model", "S_x002f_NNo_x002e_", "Status") if c in filtered.columns]
        if searchable:
            mask = filtered[searchable].astype(str).apply(lambda col: col.str.contains(search, case=False, na=False)).any(axis=1)
            filtered = filtered[mask]
    if company_filter != "ทั้งหมด" and "Company" in filtered.columns:
        filtered = filtered[filtered["Company"].astype(str).str.strip().eq(company_filter)]
    if status_filter != "ทั้งหมด" and "Status" in filtered.columns:
        filtered = filtered[filtered["Status"].astype(str).str.strip().eq(status_filter)]
    if model_filter != "ทั้งหมด" and "Brand_x002f_Model" in filtered.columns:
        filtered = filtered[filtered["Brand_x002f_Model"].astype(str).str.strip().eq(model_filter)]

    a1, a2, a3, _ = st.columns([1.25, 0.9, 1.8, 3.2])
    with a1:
        if admin_mode and st.button("＋ เพิ่ม Monitor", use_container_width=True, type="primary", key="ma_add"):
            add_monitor_dialog(list_name)
    with a2:
        st.download_button("Export", filtered.to_csv(index=False).encode("utf-8-sig"), "monitor_assets.csv", "text/csv", use_container_width=True, key="ma_export")
    with a3:
        sort_mode = st.selectbox("เรียงข้อมูล", ["User A–Z", "User Z–A", "Company A–Z", "Brand/Model A–Z"], label_visibility="collapsed", key="ma_sort")

    records = []
    for idx, row in filtered.iterrows():
        records.append(
            (
                idx,
                row,
                {
                    "user": _display_value(row.get("User")),
                    "company": _display_value(row.get("Company")),
                    "model": _display_value(row.get("Brand_x002f_Model")),
                    "serial": _display_value(row.get("S_x002f_NNo_x002e_")),
                    "status": _status_value(row),
                },
            )
        )

    if sort_mode == "User A–Z":
        records.sort(key=lambda x: x[2]["user"].casefold())
    elif sort_mode == "User Z–A":
        records.sort(key=lambda x: x[2]["user"].casefold(), reverse=True)
    elif sort_mode == "Company A–Z":
        records.sort(key=lambda x: (x[2]["company"].casefold(), x[2]["user"].casefold()))
    else:
        records.sort(key=lambda x: (x[2]["model"].casefold(), x[2]["user"].casefold()))

    page_size = 10
    page_count = max(1, math.ceil(len(records) / page_size))
    page = max(1, min(int(st.session_state.get("ma_page", 1)), page_count))
    st.session_state["ma_page"] = page
    start = (page - 1) * page_size
    page_records = records[start : start + page_size]

    st.markdown(
        f'<div class="ma-table-title"><div class="ma-table-title-left"><span>▦</span>Monitor Inventory</div><div class="ma-table-title-right">{len(records):,} รายการ</div></div>',
        unsafe_allow_html=True,
    )

    widths = [1.35, 0.85, 1.55, 1.35, 0.8, 0.85]
    labels = ["User", "Company", "Brand / Model", "Serial Number", "Status", "Action"]
    row_from = start + 1 if records else 0
    row_to = min(start + page_size, len(records))

    with st.container(border=True):
        st.markdown('<div class="ma-grid-marker"></div>', unsafe_allow_html=True)
        head = st.columns(widths, gap="small")
        for col, label in zip(head, labels):
            with col:
                st.markdown(f'<div class="ma-head">{html.escape(label)}</div>', unsafe_allow_html=True)

        if not page_records:
            st.info("ไม่พบข้อมูลตามเงื่อนไข")

        for idx, row, data in page_records:
            cols = st.columns(widths, gap="small", vertical_alignment="center")
            for col, value in zip(cols[:4], [data["user"], data["company"], data["model"], data["serial"]]):
                with col:
                    safe = html.escape(str(value), quote=True)
                    st.markdown(f'<div class="ma-cell" title="{safe}">{safe}</div>', unsafe_allow_html=True)

            with cols[4]:
                safe_status = html.escape(str(data["status"]), quote=True)
                css = _status_class(data["status"])
                st.markdown(f'<div class="ma-status-wrap"><span class="ma-status ma-status-{css}">{safe_status}</span></div>', unsafe_allow_html=True)

            with cols[5]:
                if admin_mode:
                    b1, b2 = st.columns(2, gap="small")
                    with b1:
                        if st.button(" ", icon=":material/visibility:", key=f"ma_view_{idx}", help="ดูรายละเอียด"):
                            show_pop_monitor(row.to_dict(), admin_mode=True)
                    with b2:
                        if st.button(" ", icon=":material/edit:", key=f"ma_edit_{idx}", help="แก้ไข"):
                            edit_monitor_dialog(row.to_dict(), list_name)
                else:
                    if st.button(" ", icon=":material/visibility:", key=f"ma_view_{idx}", help="ดูรายละเอียด"):
                        show_pop_monitor(row.to_dict(), admin_mode=False)

            st.markdown('<div class="ma-divider"></div>', unsafe_allow_html=True)

        st.markdown(f'<div class="ma-footer"><span>แสดง {row_from} ถึง {row_to} จาก {len(records)} รายการ</span><span>หน้า {page} / {page_count}</span></div>', unsafe_allow_html=True)

    nav = st.columns([7, .52, .52, .52, .52, .52])
    with nav[1]:
        if st.button("⏮️", use_container_width=True, key="ma_first", disabled=page <= 1):
            st.session_state["ma_page"] = 1
            st.rerun()
    with nav[2]:
        if st.button("◀️", use_container_width=True, key="ma_prev", disabled=page <= 1):
            st.session_state["ma_page"] = page - 1
            st.rerun()
    with nav[3]:
        st.button(str(page), use_container_width=True, type="primary", key="ma_current", disabled=True)
    with nav[4]:
        if st.button("▶️", use_container_width=True, key="ma_next", disabled=page >= page_count):
            st.session_state["ma_page"] = page + 1
            st.rerun()
    with nav[5]:
        if st.button("⏭️", use_container_width=True, key="ma_last", disabled=page >= page_count):
            st.session_state["ma_page"] = page_count
            st.rerun()

    company_counts, model_counts, status_counts = {}, {}, {}
    for _, row in frame.iterrows():
        company = _display_value(row.get("Company"), default="ไม่ระบุ")
        model = _display_value(row.get("Brand_x002f_Model"), default="ไม่ระบุ")
        status = _status_value(row)
        company_counts[company] = company_counts.get(company, 0) + 1
        model_counts[model] = model_counts.get(model, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1

    def bars(title, data, limit=6):
        top = sorted(data.items(), key=lambda item: (-item[1], item[0].casefold()))[:limit]
        max_value = max([value for _, value in top] or [1])
        rows = []
        for label, value in top:
            safe = html.escape(str(label))
            rows.append(
                f'<div class="ma-bar-row"><span class="ma-bar-label" title="{safe}">{safe}</span><div class="ma-track"><div class="ma-fill" style="width:{value / max_value * 100:.1f}%"></div></div><strong>{value}</strong></div>'
            )
        return f'<div class="ma-chart"><div class="ma-chart-title">{html.escape(title)}</div><div class="ma-bars">{"".join(rows)}</div></div>'

    status_rows = []
    for status, value in sorted(status_counts.items(), key=lambda item: (-item[1], item[0].casefold())):
        css = _status_class(status)
        status_rows.append(f'<div class="ma-legend-row"><span class="ma-dot {css}"></span><b>{html.escape(str(status))}</b><span>{value}</span></div>')

    status_card = '<div class="ma-chart"><div class="ma-chart-title">Status Distribution</div><div class="ma-legend">' + "".join(status_rows) + "</div></div>"

    st.markdown(
        '<div class="ma-analytics">' + bars("By Company", company_counts) + status_card + bars("Top Brand / Model", model_counts) + "</div>",
        unsafe_allow_html=True,
    )
