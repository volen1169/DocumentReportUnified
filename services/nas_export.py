"""Pure transformation and serialization helpers for NAS permission exports."""

import io
import re

import pandas as pd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


_COMPANY_ALIASES = {
    "optimaltechcoltd": "OPT",
    "poonyarukpattanacoltd": "PRP",
    "puritylabcoltd": "PLC",
    "evergloryinternationalcoltd": "EGI",
    "siamwinindustrycoltd": "SWI",
}

_PERMISSION_RANK = {"R": 1, "R/W": 2, "Deny": 3}

_SHARE_HEADER_COLORS = {
    "EGI_": ("166534", "FFFFFF"),
    "OPG_": ("F97316", "FFFFFF"),
    "OPT_": ("93C5FD", "0F172A"),
    "PLC_": ("67E8F9", "0F172A"),
    "SWI_": ("86EFAC", "0F172A"),
}


def _nas_company_abbreviation(value):
    """Convert the full AD company name to the agreed abbreviation."""
    raw = str(value or "").strip()
    # Ignore punctuation/spacing/case so Co.,Ltd. and Co., Ltd. both match.
    key = re.sub(r"[^a-z0-9]", "", raw.casefold())
    return _COMPANY_ALIASES.get(key, raw or "-")


def _nas_first_value(data, *keys):
    if not isinstance(data, dict):
        return ""
    folded = {str(k).casefold(): v for k, v in data.items()}
    for key in keys:
        value = data.get(key)
        if value in (None, ""):
            value = folded.get(str(key).casefold())
        if isinstance(value, list):
            value = value[0] if value else ""
        if value not in (None, ""):
            return str(value).strip()
    return ""


def resolve_nas_export_profile(
    entity,
    *,
    clean_principal,
    policy_lookup,
    policy_formatter,
) -> dict:
    """Resolve Company, Department, and Firewall Policy for an ACL entity."""
    clean_entity = clean_principal(entity)
    candidates = []
    for candidate in (
        clean_entity,
        clean_entity.split("@")[0] if "@" in clean_entity else "",
        clean_entity.replace(" ", ".") if " " in clean_entity else "",
    ):
        candidate = str(candidate or "").strip()
        if candidate and candidate.casefold() not in {x.casefold() for x in candidates}:
            candidates.append(candidate)

    last_error = ""
    for candidate in candidates:
        summary = policy_lookup(candidate)
        if not summary.get("ok"):
            last_error = summary.get("error", "")
            continue
        user = summary.get("user") or {}
        company = _nas_first_value(user, "company", "companyName", "Company", "CompanyName")
        department = _nas_first_value(user, "department", "Department", "departmentName")
        policy_names = policy_formatter(summary.get("policies", []))
        return {
            "Company": _nas_company_abbreviation(company),
            "Department": department or "-",
            "Firewall Policy": policy_names or "-",
        }
    return {"Company": "-", "Department": "-", "Firewall Policy": "-", "Error": last_error}


def build_nas_export_dataframe(
    display_df,
    *,
    clean_principal,
    profile_lookup,
):
    """Build the user-by-share NAS permission matrix in baseline order."""
    prepared_export = prepare_nas_export_permissions(
        display_df,
        clean_principal=clean_principal,
    )
    return build_nas_export_dataframe_from_permissions(
        prepared_export,
        profile_lookup=profile_lookup,
    )


def prepare_nas_export_permissions(
    display_df,
    *,
    clean_principal,
):
    """Parse the share and permission mapping before profile enrichment."""
    share_names = []
    permission_by_user = {}

    for _, export_source_row in display_df.iterrows():
        share_name = str(export_source_row.get("Share", "")).strip()
        if not share_name:
            continue
        if share_name not in share_names:
            share_names.append(share_name)
        raw_acl = str(export_source_row.get("ACL Tags (Raw)", "") or "")
        if not raw_acl or raw_acl.casefold() in ("nan", "none"):
            continue
        for item in [part.strip() for part in raw_acl.split(",")]:
            match = re.search(r"^(.*?)\s*\((Read(?:/Write)?|Deny)\)", item, flags=re.I)
            if not match:
                continue
            entity = clean_principal(match.group(1))
            if not entity:
                continue
            raw_permission = match.group(2).casefold()
            permission = "Deny" if raw_permission == "deny" else ("R/W" if "write" in raw_permission else "R")
            user_key = entity.casefold()
            user_record = permission_by_user.setdefault(user_key, {"Name": entity, "Shares": {}})
            old_permission = user_record["Shares"].get(share_name, "")
            if _PERMISSION_RANK.get(permission, 0) > _PERMISSION_RANK.get(old_permission, 0):
                user_record["Shares"][share_name] = permission

    return share_names, permission_by_user


def build_nas_export_dataframe_from_permissions(
    prepared_export,
    *,
    profile_lookup,
):
    """Enrich a prepared permission mapping and build the export DataFrame."""
    share_names, permission_by_user = prepared_export
    matrix_rows = []
    for user_record in sorted(permission_by_user.values(), key=lambda item: item["Name"].casefold()):
        profile = profile_lookup(user_record["Name"])
        export_record = {
            "Name": user_record["Name"],
            "Company": profile.get("Company", "-"),
            "Department": profile.get("Department", "-"),
        }
        export_record.update({share: user_record["Shares"].get(share, "") for share in share_names})
        export_record["Firewall Policy"] = profile.get("Firewall Policy", "-")
        matrix_rows.append(export_record)

    export_columns = ["Name", "Company", "Department"] + share_names + ["Firewall Policy"]
    return pd.DataFrame(matrix_rows, columns=export_columns)


def build_nas_csv(export_df) -> bytes:
    """Serialize a NAS export DataFrame as UTF-8 CSV with BOM."""
    return export_df.to_csv(index=False).encode("utf-8-sig")


def build_nas_excel(export_df) -> bytes:
    """Serialize a NAS export DataFrame as the formatted baseline workbook."""
    excel_buf = io.BytesIO()
    export_columns = list(export_df.columns)

    with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="NAS Permissions")
        ws = writer.sheets["NAS Permissions"]
        thin = Side(style="thin", color="D9E2F3")
        default_fill, default_font_color = "4472C4", "FFFFFF"
        for col_index, column_name in enumerate(export_columns, start=1):
            cell = ws.cell(row=1, column=col_index)
            fill_color, font_color = default_fill, default_font_color
            if col_index > 3 and column_name != "Firewall Policy":
                for prefix, colors in _SHARE_HEADER_COLORS.items():
                    if str(column_name).upper().startswith(prefix):
                        fill_color, font_color = colors
                        break
            cell.fill = PatternFill("solid", fgColor=fill_color)
            cell.font = Font(name="Kanit", size=10, bold=True, color=font_color)
            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
                text_rotation=90 if col_index > 3 and column_name != "Firewall Policy" else 0,
                wrap_text=True,
            )
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
            for row_index in range(2, ws.max_row + 1):
                body_cell = ws.cell(row=row_index, column=col_index)
                body_cell.font = Font(name="Kanit", size=10)
                body_cell.alignment = Alignment(
                    horizontal="center" if col_index > 1 else "left",
                    vertical="center",
                )
                body_cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
            ws.column_dimensions[get_column_letter(col_index)].width = (
                8
                if col_index > 3 and column_name != "Firewall Policy"
                else min(max(len(str(column_name)) + 3, 14), 34)
            )
        ws.row_dimensions[1].height = 120
        ws.freeze_panes = "D2"
        ws.auto_filter.ref = ws.dimensions

    excel_buf.seek(0)
    return excel_buf.getvalue()
