
import html
import math
import textwrap

import pandas as pd
import streamlit as st


PRINTER_FIELDS = {
    "Company": "บริษัท",
    "User": "User",
    "Brand_x0020__x002f__x0020_Model": "Brand/Model",
    "S_x002f_N_x0020_No_x002e_": "Serial No.",
    "Status": "Status",
}


def printer_display_value(value, default="-"):
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


def _is_assigned(row):
    user = printer_display_value(row.get("User"), default="")
    return bool(user and user != "-")


def render_printer_asset(
    *,
    df_hw,
    admin_mode,
    show_pop_printer,
    add_printer_dialog,
    edit_printer_dialog,
):
    """
    Printer-specific inventory view.

    Keeps existing dialogs/CRUD handlers unchanged while replacing the
    generic card grid with a compact table and lightweight analytics.
    """
    list_name = "Asset Printer"
    frame = df_hw.copy() if isinstance(df_hw, pd.DataFrame) else pd.DataFrame()

    # Inject CSS as raw HTML so Streamlit Markdown cannot render it as a code block.
    st.html(textwrap.dedent("""
<style>
        .stApp:has(.pa-page) [data-testid="stMainBlockContainer"]{
            background:transparent!important;
            padding-top:6px!important;
        }
        .stApp:has(.pa-page) [data-testid="stHeader"],
        .stApp:has(.pa-page) [data-testid="stToolbar"]{display:none!important}
        .stApp:has(.pa-page) [data-testid="stVerticalBlock"]{gap:.62rem}
        .pa-page{display:none}

        .pa-header{
            min-height:94px;box-sizing:border-box;display:flex;align-items:center;gap:15px;
            padding:16px 21px;margin-bottom:10px;background:#FFF;border:1px solid #E2E8F0;
            border-radius:20px;box-shadow:0 10px 26px rgba(15,23,42,.055)
        }
        .pa-header-icon{
            width:54px;height:54px;flex:0 0 54px;display:grid;place-items:center;
            color:#4F46E5;background:#F3F5FF;border:1px solid #E0E7FF;border-radius:16px;
            font-size:27px
        }
        .pa-header h1{
            margin:0 0 4px!important;color:#0F172A!important;font-size:24px!important;
            font-weight:850;letter-spacing:-.035em
        }
        .pa-header p{margin:0!important;color:#64748B!important;font-size:12px!important}

        .pa-metrics{
            display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:10px
        }
        .pa-card{
            position:relative;height:94px;box-sizing:border-box;padding:13px 14px;background:#FFF;
            border:1px solid #E2E8F0;border-radius:17px;box-shadow:0 7px 18px rgba(15,23,42,.04);
            overflow:hidden
        }
        .pa-card:after{
            content:"";position:absolute;inset:auto 0 0;height:3px;background:var(--tone)
        }
        .pa-card-label{color:#475569;font-size:10.5px;font-weight:800}
        .pa-card-value{
            margin-top:7px;color:#0F172A;font-size:25px;line-height:1;font-weight:850;
            letter-spacing:-.04em
        }
        .pa-card-foot{
            position:absolute;left:14px;right:14px;bottom:10px;display:flex;
            justify-content:space-between;color:#64748B;font-size:10px
        }
        .pa-card-foot strong{color:var(--tone)}

        .stApp:has(.pa-page) .stTextInput input,
        .stApp:has(.pa-page) .stSelectbox div[data-baseweb="select"]>div{
            height:42px!important;min-height:42px!important;border:1px solid #DDE5EF!important;
            border-radius:12px!important;background:#FFF!important;font-size:12px!important
        }
        .stApp:has(.pa-page) .stButton>button,
        .stApp:has(.pa-page) .stDownloadButton>button{
            height:40px;min-height:40px;border-radius:11px;border-color:#E2E8F0;
            font-size:12px;font-weight:750
        }
        .stApp:has(.pa-page) button[kind="primary"]{
            color:#FFF!important;border:0!important;
            background:linear-gradient(135deg,#3B82F6,#7C3AED)!important;
            box-shadow:0 7px 16px rgba(99,102,241,.18)
        }

        .pa-table-title{
            height:50px;display:flex;align-items:center;justify-content:space-between;
            padding:0 14px;background:#FFF;border:1px solid #E2E8F0;border-bottom:0;
            border-radius:18px 18px 0 0;color:#334155;font-size:12px;font-weight:800
        }
        .pa-table-title-left{display:flex;align-items:center;gap:8px}
        .pa-table-title-left span{
            width:29px;height:29px;display:grid;place-items:center;border-radius:9px;
            background:#EEF2FF;color:#4F46E5
        }
        .pa-table-title-right{color:#64748B;font-size:10.5px;font-weight:700}

        .stApp:has(.pa-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.pa-grid-marker){
            padding:0!important;border:1px solid #E2E8F0!important;border-radius:0 0 17px 17px!important;
            background:#FFF!important;box-shadow:0 8px 22px rgba(15,23,42,.045)!important;
            overflow:hidden
        }
        .stApp:has(.pa-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.pa-grid-marker)>div{
            padding:0!important
        }
        .pa-grid-marker{display:none}
        .pa-head{
            height:42px;display:flex;align-items:center;padding:0 10px;color:#475569;
            background:#F8FAFC;font-size:10.5px;font-weight:850;white-space:nowrap
        }
        .pa-cell{
            height:42px;display:flex;align-items:center;padding:0 10px;color:#334155;
            font-size:11.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis
        }
        .pa-badge{
            display:inline-flex;align-items:center;gap:5px;padding:4px 8px;border-radius:999px;
            font-size:10px;font-weight:850
        }
        .pa-badge:before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}
        .pa-badge-assigned{background:#ECFDF5;color:#059669}
        .pa-badge-unassigned{background:#FFF7ED;color:#D97706}
        .pa-badge-wrap{height:42px;display:flex;align-items:center;padding-left:6px}
        .pa-divider{height:1px;margin:0;background:#EDF2F7}
        .pa-footer{
            height:44px;display:flex;align-items:center;justify-content:space-between;
            padding:0 14px;color:#64748B;font-size:10.5px;border-top:1px solid #E2E8F0
        }

        .stApp:has(.pa-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.pa-grid-marker)
        [data-testid="stVerticalBlock"]{gap:0!important}
        .stApp:has(.pa-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.pa-grid-marker)
        [data-testid="stElementContainer"]{margin:0!important}
        .stApp:has(.pa-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.pa-grid-marker)
        [data-testid="stHorizontalBlock"]{gap:0!important}
        .stApp:has(.pa-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.pa-grid-marker)
        [data-testid="column"]{border-right:1px solid #EDF2F7}
        .stApp:has(.pa-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.pa-grid-marker)
        [data-testid="column"]:last-child{border-right:0}

        .stApp:has(.pa-page) [class*="st-key-pa_view_"] button,
        .stApp:has(.pa-page) [class*="st-key-pa_edit_"] button{
            width:30px!important;min-width:30px!important;max-width:30px!important;
            height:30px!important;min-height:30px!important;max-height:30px!important;
            padding:0!important;margin:0 auto!important;border-radius:9px!important;box-shadow:none!important
        }
        .stApp:has(.pa-page) [class*="st-key-pa_view_"] button{
            color:#2563EB!important;background:#EFF6FF!important;border-color:#DBEAFE!important
        }
        .stApp:has(.pa-page) [class*="st-key-pa_edit_"] button{
            color:#7C3AED!important;background:#F5F3FF!important;border-color:#EDE9FE!important
        }

        .pa-analytics{
            display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:12px
        }
        .pa-chart{
            min-height:220px;box-sizing:border-box;padding:15px;background:#FFF;border:1px solid #E2E8F0;
            border-radius:17px;box-shadow:0 7px 18px rgba(15,23,42,.04);overflow:hidden
        }
        .pa-chart-title{margin-bottom:12px;color:#0F172A;font-size:12.5px;font-weight:850}
        .pa-bars{display:grid;gap:11px}
        .pa-bar-row{
            display:grid;grid-template-columns:95px 1fr 30px;align-items:center;gap:8px;
            color:#475569;font-size:10px
        }
        .pa-bar-label{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .pa-track{height:7px;background:#EEF2FF;border-radius:99px;overflow:hidden}
        .pa-fill{height:100%;border-radius:99px;background:linear-gradient(90deg,#3B82F6,#8B5CF6)}
        .pa-bar-row strong{text-align:right;color:#334155}
        .pa-legend{display:grid;gap:12px;margin-top:8px}
        .pa-legend-row{
            display:grid;grid-template-columns:9px 1fr auto;align-items:center;gap:8px;
            color:#64748B;font-size:10.5px
        }
        .pa-dot{width:8px;height:8px;border-radius:50%}
        .pa-dot.assigned{background:#10B981}.pa-dot.unassigned{background:#F59E0B}
        .pa-legend-row b{color:#334155}

        @media(max-width:1100px){
            .pa-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}
            .pa-analytics{grid-template-columns:1fr}
        }
        @media(max-width:700px){
            .pa-header{min-height:105px}
            .pa-metrics{grid-template-columns:1fr}
        }
        </style>
    """))
    st.markdown('<div class="pa-page"></div>', unsafe_allow_html=True)

    total = len(frame)
    company_count = (
        int(frame["Company"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().nunique())
        if "Company" in frame.columns else 0
    )
    assigned = sum(_is_assigned(row) for _, row in frame.iterrows())
    unassigned = total - assigned

    def pct(value):
        return (value / total * 100.0) if total else 0.0

    st.markdown(
        '<section class="pa-header"><div class="pa-header-icon">🖨️</div><div><h1>Printer Asset</h1><p>จัดการข้อมูล Printer ทั้งหมดในองค์กร</p></div></section>',
        unsafe_allow_html=True,
    )

    metrics = [
        ("TOTAL PRINTERS", total, "#2563EB", "เครื่อง", f"{pct(total):.2f}%"),
        ("ASSIGNED", assigned, "#10B981", "เครื่อง", f"{pct(assigned):.2f}%"),
        ("UNASSIGNED", unassigned, "#F59E0B", "เครื่อง", f"{pct(unassigned):.2f}%"),
        ("บริษัท", company_count, "#8B5CF6", "บริษัท", ""),
    ]
    st.markdown(
        '<div class="pa-metrics">'
        + "".join(
            f'<div class="pa-card" style="--tone:{tone}"><div class="pa-card-label">{html.escape(label)}</div><div class="pa-card-value">{value:,}</div><div class="pa-card-foot"><span>{html.escape(unit)}</span>{f"<strong>{foot}</strong>" if foot else ""}</div></div>'
            for label, value, tone, unit, foot in metrics
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    companies = sorted({
        printer_display_value(row.get("Company"), default="")
        for _, row in frame.iterrows()
        if printer_display_value(row.get("Company"), default="")
    })
    users = sorted({
        printer_display_value(row.get("User"), default="")
        for _, row in frame.iterrows()
        if printer_display_value(row.get("User"), default="")
    })
    models = sorted({
        printer_display_value(row.get("Brand_x0020__x002f__x0020_Model"), default="")
        for _, row in frame.iterrows()
        if printer_display_value(row.get("Brand_x0020__x002f__x0020_Model"), default="")
    })

    f1, f2, f3, f4, f5 = st.columns([3.2, 1.15, 1.35, 1.55, 1.0])
    with f1:
        search = st.text_input(
            "ค้นหา",
            placeholder="ค้นหา Printer, บริษัท, User, Serial No.",
            label_visibility="collapsed",
            key="pa_search",
        )
    with f2:
        company_filter = st.selectbox(
            "บริษัท",
            ["ทั้งหมด"] + companies,
            label_visibility="collapsed",
            key="pa_company",
        )
    with f3:
        user_filter = st.selectbox(
            "User",
            ["ทั้งหมด"] + users,
            label_visibility="collapsed",
            key="pa_user",
        )
    with f4:
        model_filter = st.selectbox(
            "Brand/Model",
            ["ทั้งหมด"] + models,
            label_visibility="collapsed",
            key="pa_model",
        )
    with f5:
        if st.button("↻ ล้าง", use_container_width=True, key="pa_reset"):
            for key in ("pa_search", "pa_company", "pa_user", "pa_model"):
                st.session_state.pop(key, None)
            st.rerun()

    filtered = frame.copy()

    if search:
        searchable = [
            col for col in (
                "Company",
                "User",
                "Brand_x0020__x002f__x0020_Model",
                "S_x002f_N_x0020_No_x002e_",
            )
            if col in filtered.columns
        ]
        if searchable:
            mask = filtered[searchable].astype(str).apply(
                lambda col: col.str.contains(search, case=False, na=False)
            ).any(axis=1)
            filtered = filtered[mask]

    if company_filter != "ทั้งหมด" and "Company" in filtered.columns:
        filtered = filtered[filtered["Company"].astype(str).str.strip().eq(company_filter)]

    if user_filter != "ทั้งหมด" and "User" in filtered.columns:
        filtered = filtered[filtered["User"].astype(str).str.strip().eq(user_filter)]

    if model_filter != "ทั้งหมด" and "Brand_x0020__x002f__x0020_Model" in filtered.columns:
        filtered = filtered[
            filtered["Brand_x0020__x002f__x0020_Model"].astype(str).str.strip().eq(model_filter)
        ]

    a1, a2, a3, _ = st.columns([1.25, .9, 1.8, 3.2])
    with a1:
        if admin_mode and st.button(
            "＋ เพิ่ม Printer",
            use_container_width=True,
            type="primary",
            key="pa_add",
        ):
            add_printer_dialog(list_name)
    with a2:
        st.download_button(
            "Export",
            filtered.to_csv(index=False).encode("utf-8-sig"),
            "printer_assets.csv",
            "text/csv",
            use_container_width=True,
            key="pa_export",
        )
    with a3:
        sort_mode = st.selectbox(
            "เรียงข้อมูล",
            ["Brand/Model A–Z", "Brand/Model Z–A", "Company A–Z", "User A–Z"],
            label_visibility="collapsed",
            key="pa_sort",
        )

    records = []
    for idx, row in filtered.iterrows():
        records.append(
            (
                idx,
                row,
                {
                    "model": printer_display_value(row.get("Brand_x0020__x002f__x0020_Model")),
                    "company": printer_display_value(row.get("Company")),
                    "user": printer_display_value(row.get("User")),
                    "serial": printer_display_value(row.get("S_x002f_N_x0020_No_x002e_")),
                    "assigned": _is_assigned(row),
                },
            )
        )

    if sort_mode == "Brand/Model A–Z":
        records.sort(key=lambda x: x[2]["model"].casefold())
    elif sort_mode == "Brand/Model Z–A":
        records.sort(key=lambda x: x[2]["model"].casefold(), reverse=True)
    elif sort_mode == "Company A–Z":
        records.sort(key=lambda x: (x[2]["company"].casefold(), x[2]["model"].casefold()))
    else:
        records.sort(key=lambda x: (x[2]["user"].casefold(), x[2]["model"].casefold()))

    page_size = 10
    page_count = max(1, math.ceil(len(records) / page_size))
    page = max(1, min(int(st.session_state.get("pa_page", 1)), page_count))
    st.session_state["pa_page"] = page
    start = (page - 1) * page_size
    page_records = records[start:start + page_size]

    st.markdown(
        f'<div class="pa-table-title"><div class="pa-table-title-left"><span>▦</span>Printer Inventory</div><div class="pa-table-title-right">{len(records):,} รายการ</div></div>',
        unsafe_allow_html=True,
    )

    widths = [1.55, .82, 1.25, 1.25, .82, .85]
    labels = ["Brand / Model", "Company", "User", "Serial Number", "Assignment", "Action"]

    row_from = start + 1 if records else 0
    row_to = min(start + page_size, len(records))

    with st.container(border=True):
        st.markdown('<div class="pa-grid-marker"></div>', unsafe_allow_html=True)

        head = st.columns(widths, gap="small")
        for col, label in zip(head, labels):
            with col:
                st.markdown(f'<div class="pa-head">{html.escape(label)}</div>', unsafe_allow_html=True)

        if not page_records:
            st.info("ไม่พบข้อมูลตามเงื่อนไข")

        for idx, row, data in page_records:
            cols = st.columns(widths, gap="small", vertical_alignment="center")

            for col, value in zip(
                cols[:4],
                [data["model"], data["company"], data["user"], data["serial"]],
            ):
                with col:
                    safe = html.escape(str(value), quote=True)
                    st.markdown(
                        f'<div class="pa-cell" title="{safe}">{safe}</div>',
                        unsafe_allow_html=True,
                    )

            with cols[4]:
                label = "Assigned" if data["assigned"] else "Unassigned"
                css = "assigned" if data["assigned"] else "unassigned"
                st.markdown(
                    f'<div class="pa-badge-wrap"><span class="pa-badge pa-badge-{css}">{label}</span></div>',
                    unsafe_allow_html=True,
                )

            with cols[5]:
                if admin_mode:
                    b1, b2 = st.columns(2, gap="small")
                    with b1:
                        if st.button(
                            " ",
                            icon=":material/visibility:",
                            key=f"pa_view_{idx}",
                            help="ดูรายละเอียด",
                        ):
                            show_pop_printer(row.to_dict(), admin_mode=True)
                    with b2:
                        if st.button(
                            " ",
                            icon=":material/edit:",
                            key=f"pa_edit_{idx}",
                            help="แก้ไข",
                        ):
                            edit_printer_dialog(row.to_dict(), list_name)
                else:
                    if st.button(
                        " ",
                        icon=":material/visibility:",
                        key=f"pa_view_{idx}",
                        help="ดูรายละเอียด",
                    ):
                        show_pop_printer(row.to_dict(), admin_mode=False)

            st.markdown('<div class="pa-divider"></div>', unsafe_allow_html=True)

        st.markdown(
            f'<div class="pa-footer"><span>แสดง {row_from} ถึง {row_to} จาก {len(records)} รายการ</span><span>หน้า {page} / {page_count}</span></div>',
            unsafe_allow_html=True,
        )

    nav = st.columns([7, .52, .52, .52, .52, .52])
    with nav[1]:
        if st.button("⏮️", use_container_width=True, key="pa_first", disabled=page <= 1):
            st.session_state["pa_page"] = 1
            st.rerun()
    with nav[2]:
        if st.button("◀️", use_container_width=True, key="pa_prev", disabled=page <= 1):
            st.session_state["pa_page"] = page - 1
            st.rerun()
    with nav[3]:
        st.button(str(page), use_container_width=True, type="primary", key="pa_current", disabled=True)
    with nav[4]:
        if st.button("▶️", use_container_width=True, key="pa_next", disabled=page >= page_count):
            st.session_state["pa_page"] = page + 1
            st.rerun()
    with nav[5]:
        if st.button("⏭️", use_container_width=True, key="pa_last", disabled=page >= page_count):
            st.session_state["pa_page"] = page_count
            st.rerun()

    company_counts = {}
    model_counts = {}
    assignment_counts = {"Assigned": 0, "Unassigned": 0}

    for _, row in frame.iterrows():
        company = printer_display_value(row.get("Company"), default="ไม่ระบุ")
        model = printer_display_value(
            row.get("Brand_x0020__x002f__x0020_Model"),
            default="ไม่ระบุ",
        )

        company_counts[company] = company_counts.get(company, 0) + 1
        model_counts[model] = model_counts.get(model, 0) + 1
        assignment_counts["Assigned" if _is_assigned(row) else "Unassigned"] += 1

    def bars(title, data, limit=6):
        top = sorted(
            data.items(),
            key=lambda item: (-item[1], item[0].casefold()),
        )[:limit]

        max_value = max([value for _, value in top] or [1])

        rows = []
        for label, value in top:
            safe = html.escape(str(label))
            rows.append(
                f'<div class="pa-bar-row"><span class="pa-bar-label" title="{safe}">{safe}</span><div class="pa-track"><div class="pa-fill" style="width:{value / max_value * 100:.1f}%"></div></div><strong>{value}</strong></div>'
            )

        return (
            f'<div class="pa-chart"><div class="pa-chart-title">{html.escape(title)}</div>'
            f'<div class="pa-bars">{"".join(rows)}</div></div>'
        )

    assignment_card = (
        '<div class="pa-chart"><div class="pa-chart-title">Assignment Distribution</div>'
        '<div class="pa-legend">'
        f'<div class="pa-legend-row"><span class="pa-dot assigned"></span><b>Assigned</b><span>{assignment_counts["Assigned"]}</span></div>'
        f'<div class="pa-legend-row"><span class="pa-dot unassigned"></span><b>Unassigned</b><span>{assignment_counts["Unassigned"]}</span></div>'
        '</div></div>'
    )

    st.markdown(
        '<div class="pa-analytics">'
        + bars("By Company", company_counts)
        + assignment_card
        + bars("Top Brand / Model", model_counts)
        + "</div>",
        unsafe_allow_html=True,
    )
