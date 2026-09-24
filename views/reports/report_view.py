
"""Centralized Export workspace for Hardware Assets and NAS Permissions."""

from __future__ import annotations

import html
import importlib
import io
import sys
from typing import Callable, Optional

import pandas as pd
import streamlit as st
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


_ASSET_SOURCES = (
    ("Computer Asset", "Computer Asset", "💻"),
    ("Monitor Asset", "Asset Monitor", "🖥️"),
    ("Printer Asset", "Asset Printer", "🖨️"),
    ("Projector Asset", "Asset Projector", "📽️"),
    ("UPS Asset", "Asset UPS", "🔋"),
    ("CCTV Asset", "Asset CCTV", "📹"),
    ("Access Control Asset", "Asset Access Control", "🔐"),
)

_NAS_LABEL = "NAS Permission"


def _resolve_main_callable(name: str):
    main_module = sys.modules.get("__main__")
    if main_module is None:
        return None
    value = getattr(main_module, name, None)
    return value if callable(value) else None


def _load_nas_export_module():
    for module_name in ("services.nas_export", "nas_export"):
        try:
            return importlib.import_module(module_name)
        except Exception:
            continue
    return None


def _safe_frame(value) -> pd.DataFrame:
    return value.copy() if isinstance(value, pd.DataFrame) else pd.DataFrame()


def _clean_asset_export_frame(frame: pd.DataFrame) -> pd.DataFrame:
    frame = _safe_frame(frame)
    internal_columns = [
        column
        for column in frame.columns
        if str(column).startswith("@")
        or str(column) in {"_item_id", "id", "contentType", "fields@odata.context"}
    ]
    return frame.drop(columns=internal_columns, errors="ignore")


def _build_asset_csv(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8-sig")


def _style_asset_sheet(ws) -> None:
    if ws.max_column < 1:
        return

    thin = Side(style="thin", color="D7DEE8")
    header_fill = PatternFill("solid", fgColor="4F46E5")
    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    body_font = Font(name="Arial", size=10, color="1F2937")

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.font = body_font
            cell.alignment = Alignment(vertical="center")
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col_idx in range(1, ws.max_column + 1):
        values = [
            str(ws.cell(row=row_idx, column=col_idx).value or "")
            for row_idx in range(1, min(ws.max_row, 120) + 1)
        ]
        width = min(max(max((len(value) for value in values), default=8) + 2, 11), 36)
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    ws.sheet_view.showGridLines = False
    ws.row_dimensions[1].height = 24


def _build_asset_excel(frame: pd.DataFrame, sheet_name: str) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name=sheet_name[:31])
        _style_asset_sheet(writer.sheets[sheet_name[:31]])
    buffer.seek(0)
    return buffer.getvalue()


def _render_styles() -> None:
    st.html(
        """
        <style>
        .ex-header{
            display:flex;align-items:center;gap:15px;padding:18px 20px;margin:0 0 12px;
            background:#fff;border:1px solid #e2e8f0;border-radius:20px;
            box-shadow:0 10px 26px rgba(15,23,42,.05)
        }
        .ex-icon{
            width:54px;height:54px;display:grid;place-items:center;flex:0 0 54px;
            border-radius:16px;background:#eef2ff;color:#4f46e5;font-size:26px
        }
        .ex-header h1{margin:0;color:#0f172a;font-size:24px;font-weight:850}
        .ex-header p{margin:4px 0 0;color:#64748b;font-size:12px}

        .ex-section-title{margin:10px 0 8px;color:#0f172a;font-size:13px;font-weight:850}
        .ex-section-sub{margin:-4px 0 10px;color:#64748b;font-size:10.5px}

        .stApp [class*="st-key-export_card_"] button{
            min-height:112px!important;
            padding:12px 10px!important;
            border:1px solid #e2e8f0!important;
            border-radius:17px!important;
            background:#fff!important;
            box-shadow:0 7px 18px rgba(15,23,42,.04)!important;
            font-size:13px!important;
            font-weight:800!important;
            white-space:pre-line!important;
        }
        .stApp [class*="st-key-export_card_"] button:hover{
            border-color:#a5b4fc!important;
            background:#f8faff!important;
            transform:translateY(-1px);
        }
        .stApp [class*="st-key-export_card_selected_"] button{
            min-height:112px!important;
            padding:12px 10px!important;
            border:2px solid #6366f1!important;
            border-radius:17px!important;
            background:linear-gradient(180deg,#f5f3ff,#eef2ff)!important;
            box-shadow:0 10px 24px rgba(99,102,241,.13)!important;
            color:#3730a3!important;
            font-size:13px!important;
            font-weight:850!important;
            white-space:pre-line!important;
        }

        .ex-selected{
            margin:14px 0 10px;padding:13px 15px;background:#fff;border:1px solid #dfe5ef;
            border-radius:16px;box-shadow:0 6px 16px rgba(15,23,42,.035)
        }
        .ex-selected b{color:#0f172a;font-size:13px}
        .ex-selected span{display:block;margin-top:3px;color:#64748b;font-size:10.5px}

        .ex-column-shell{
            margin-top:10px;padding:15px 16px;background:#fff;border:1px solid #e2e8f0;
            border-radius:18px;box-shadow:0 8px 20px rgba(15,23,42,.04)
        }
        .ex-column-title{color:#0f172a;font-size:13px;font-weight:850}
        .ex-column-sub{margin-top:3px;color:#64748b;font-size:10.5px}
        .ex-count{
            display:inline-flex;margin-top:8px;padding:4px 9px;border-radius:999px;
            background:#eef2ff;color:#4338ca;font-size:10px;font-weight:800
        }

        .ex-export-box{
            margin-top:12px;padding:15px 16px;background:#fff;border:1px solid #e2e8f0;
            border-radius:18px;box-shadow:0 8px 20px rgba(15,23,42,.04)
        }
        .ex-empty{
            padding:18px;text-align:center;color:#64748b;background:#fff;
            border:1px dashed #cbd5e1;border-radius:16px
        }
        </style>
        """
    )


def _card_button(label: str, icon: str, selected: bool, key: str) -> bool:
    button_key = f"export_card_selected_{key}" if selected else f"export_card_{key}"
    caption = f"{icon}\n{label}"
    return st.button(caption, key=button_key, use_container_width=True)


def _render_source_cards(selected_label: str) -> str:
    cards = list(_ASSET_SOURCES) + [(_NAS_LABEL, "", "🗂️")]
    rows = [cards[:4], cards[4:]]

    current = selected_label
    for row_index, row_cards in enumerate(rows):
        cols = st.columns(len(row_cards), gap="small")
        for idx, (label, _, icon) in enumerate(row_cards):
            with cols[idx]:
                safe_key = f"{row_index}_{idx}_{label.lower().replace(' ', '_')}"
                if _card_button(label, icon, current == label, safe_key):
                    st.session_state["export_center_selected"] = label
                    st.session_state.pop("export_center_ready_bytes", None)
                    st.session_state.pop("export_center_ready_name", None)
                    st.session_state.pop("export_center_ready_mime", None)
                    st.rerun()
    return current


def _render_column_selector(columns: list[str], prefix: str) -> list[str]:
    if not columns:
        return []

    state_key = f"{prefix}_selected_columns"
    default_selected = st.session_state.get(state_key)
    if not isinstance(default_selected, list):
        default_selected = list(columns)
        st.session_state[state_key] = list(columns)

    valid_selected = [column for column in default_selected if column in columns]
    if valid_selected != default_selected:
        st.session_state[state_key] = valid_selected

    c1, c2, c3 = st.columns([1.0, 1.0, 4.0])
    with c1:
        if st.button("✓ เลือกทั้งหมด", use_container_width=True, key=f"{prefix}_select_all"):
            st.session_state[state_key] = list(columns)
            for column in columns:
                st.session_state[f"{prefix}_col_{column}"] = True
            st.rerun()
    with c2:
        if st.button("ล้างทั้งหมด", use_container_width=True, key=f"{prefix}_clear_all"):
            st.session_state[state_key] = []
            for column in columns:
                st.session_state[f"{prefix}_col_{column}"] = False
            st.rerun()

    selected = []
    per_row = 3
    for start in range(0, len(columns), per_row):
        row_columns = columns[start:start + per_row]
        ui_cols = st.columns(per_row, gap="small")
        for idx, column in enumerate(row_columns):
            with ui_cols[idx]:
                checkbox_key = f"{prefix}_col_{column}"
                if checkbox_key not in st.session_state:
                    st.session_state[checkbox_key] = column in st.session_state[state_key]
                checked = st.checkbox(
                    str(column),
                    key=checkbox_key,
                )
                if checked:
                    selected.append(column)

    st.session_state[state_key] = selected
    return selected


def _nas_group_columns(export_df: pd.DataFrame):
    metadata = ["No.", "Name", "Position", "Division", "Company", "Firewall Policy"]
    metadata = [column for column in metadata if column in export_df.columns]
    share_columns = [column for column in export_df.columns if column not in metadata]
    return metadata, share_columns


def render_report_view(
    *,
    load_sp_data: Optional[Callable] = None,
    load_nas_data: Optional[Callable] = None,
    clean_nas_principal: Optional[Callable] = None,
    nas_profile_lookup: Optional[Callable] = None,
) -> None:
    """
    Render a card-driven Export Center.

    Flow:
    1) Click an Asset/NAS card.
    2) Tick the columns to include.
    3) Choose Excel or CSV.
    4) Export.
    """
    load_sp_data = load_sp_data or _resolve_main_callable("load_sp_data")
    load_nas_data = load_nas_data or _resolve_main_callable("load_nas_data")
    clean_nas_principal = clean_nas_principal or _resolve_main_callable("_clean_nas_principal")

    nas_module = _load_nas_export_module()

    if nas_profile_lookup is None:
        policy_lookup = _resolve_main_callable("get_user_internet_policy_summary")
        policy_formatter = _resolve_main_callable("format_policy_names")
        if (
            nas_module is not None
            and clean_nas_principal is not None
            and policy_lookup is not None
            and policy_formatter is not None
            and hasattr(nas_module, "resolve_nas_export_profile")
        ):
            nas_profile_lookup = lambda entity: nas_module.resolve_nas_export_profile(
                entity,
                clean_principal=clean_nas_principal,
                policy_lookup=policy_lookup,
                policy_formatter=policy_formatter,
            )

    _render_styles()

    st.markdown(
        """
        <section class="ex-header">
            <div class="ex-icon">⇩</div>
            <div>
                <h1>Export Center</h1>
                <p>เลือกประเภทข้อมูล กำหนดคอลัมน์ แล้ว Export เป็น Excel หรือ CSV</p>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="ex-section-title">เลือกประเภทข้อมูล</div>', unsafe_allow_html=True)
    st.markdown('<div class="ex-section-sub">กดที่การ์ดเพื่อเลือกข้อมูลที่ต้องการ Export</div>', unsafe_allow_html=True)

    if "export_center_selected" not in st.session_state:
        st.session_state["export_center_selected"] = "Computer Asset"

    selected = _render_source_cards(st.session_state["export_center_selected"])
    selected = st.session_state["export_center_selected"]

    st.markdown(
        f'<div class="ex-selected"><b>✓ {html.escape(selected)}</b>'
        f'<span>เลือกคอลัมน์ที่ต้องการในไฟล์ Export ด้านล่าง</span></div>',
        unsafe_allow_html=True,
    )

    if selected == _NAS_LABEL:
        if load_nas_data is None:
            st.error("ไม่พบ load_nas_data จากแอปหลัก")
            return
        if nas_module is None:
            st.error("ไม่พบโมดูล NAS export (services.nas_export หรือ nas_export)")
            return
        if clean_nas_principal is None or nas_profile_lookup is None:
            st.error("ยังไม่พร้อม Export NAS: ไม่พบ clean principal / AD profile lookup")
            return

        with st.spinner("กำลังเตรียม NAS Permission..."):
            nas_source = _safe_frame(load_nas_data())

        if nas_source.empty:
            st.info("ไม่พบข้อมูล NAS Permission")
            return

        export_df = nas_module.build_nas_export_dataframe(
            nas_source,
            clean_principal=clean_nas_principal,
            profile_lookup=nas_profile_lookup,
        )

        metadata_cols, share_cols = _nas_group_columns(export_df)

        st.markdown(
            f'<div class="ex-column-shell"><div class="ex-column-title">ข้อมูลพนักงาน</div>'
            f'<div class="ex-column-sub">เลือก Metadata ที่ต้องการใส่ในรายงาน</div>'
            f'<span class="ex-count">{len(metadata_cols)} คอลัมน์</span></div>',
            unsafe_allow_html=True,
        )
        selected_metadata = _render_column_selector(metadata_cols, "nas_meta")

        st.markdown(
            f'<div class="ex-column-shell"><div class="ex-column-title">Shared Folder Permissions</div>'
            f'<div class="ex-column-sub">เลือก Share ที่ต้องการใส่ในรายงาน</div>'
            f'<span class="ex-count">{len(share_cols)} คอลัมน์</span></div>',
            unsafe_allow_html=True,
        )
        selected_shares = _render_column_selector(share_cols, "nas_share")
        selected_columns = selected_metadata + selected_shares

        export_format = st.radio(
            "รูปแบบไฟล์",
            ["Excel (.xlsx)", "CSV (.csv)"],
            horizontal=True,
            key="nas_export_format",
        )

        if not selected_columns:
            st.warning("กรุณาเลือกอย่างน้อย 1 คอลัมน์")
            return

        final_df = export_df[selected_columns].copy()

        st.markdown('<div class="ex-export-box">', unsafe_allow_html=True)
        if export_format.startswith("Excel"):
            # Keep the existing NAS Excel formatter, but only with selected columns.
            file_bytes = nas_module.build_nas_excel(final_df)
            file_name = "NAS_Permission.xlsx"
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            file_bytes = nas_module.build_nas_csv(final_df)
            file_name = "NAS_Permission.csv"
            mime = "text/csv"

        st.download_button(
            f"⬇️ Export {selected}",
            data=file_bytes,
            file_name=file_name,
            mime=mime,
            use_container_width=True,
            type="primary",
            key="nas_final_download",
        )
        st.markdown('</div>', unsafe_allow_html=True)
        return

    source_lookup = {label: list_name for label, list_name, _ in _ASSET_SOURCES}
    if load_sp_data is None:
        st.error("ไม่พบ load_sp_data จากแอปหลัก")
        return

    list_name = source_lookup[selected]

    with st.spinner(f"กำลังโหลด {selected}..."):
        source_df = _clean_asset_export_frame(_safe_frame(load_sp_data(list_name)))

    if source_df.empty:
        st.info(f"ไม่พบข้อมูล {selected}")
        return

    columns = [str(column) for column in source_df.columns]

    st.markdown(
        f'<div class="ex-column-shell"><div class="ex-column-title">เลือกคอลัมน์ที่ต้องการ Export</div>'
        f'<div class="ex-column-sub">เลือกเฉพาะข้อมูลที่ต้องการ ไม่แสดงตาราง Preview</div>'
        f'<span class="ex-count">{len(columns)} คอลัมน์ · {len(source_df):,} รายการ</span></div>',
        unsafe_allow_html=True,
    )

    prefix = "asset_" + selected.lower().replace(" ", "_")
    selected_columns = _render_column_selector(columns, prefix)

    export_format = st.radio(
        "รูปแบบไฟล์",
        ["Excel (.xlsx)", "CSV (.csv)"],
        horizontal=True,
        key=f"{prefix}_format",
    )

    if not selected_columns:
        st.warning("กรุณาเลือกอย่างน้อย 1 คอลัมน์")
        return

    final_df = source_df[selected_columns].copy()

    st.markdown('<div class="ex-export-box">', unsafe_allow_html=True)
    if export_format.startswith("Excel"):
        file_bytes = _build_asset_excel(final_df, selected)
        file_name = f"{selected.replace(' ', '_')}.xlsx"
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        file_bytes = _build_asset_csv(final_df)
        file_name = f"{selected.replace(' ', '_')}.csv"
        mime = "text/csv"

    st.download_button(
        f"⬇️ Export {selected}",
        data=file_bytes,
        file_name=file_name,
        mime=mime,
        use_container_width=True,
        type="primary",
        key=f"{prefix}_download",
    )
    st.markdown('</div>', unsafe_allow_html=True)
