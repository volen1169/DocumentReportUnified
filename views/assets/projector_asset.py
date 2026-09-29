"""Projector-owned UI and payload mapping for the Asset Projector SharePoint list."""

import pandas as pd
import streamlit as st

from views.assets.generic_hardware_asset import render_generic_hardware_asset


LIST_NAME = "Asset Projector"
# Internal names verified against this list's SharePoint column settings.
PROJECTOR_FIELDS = {
    "Number_x0020_Asset": "Asset No.",
    "Company": "Company",
    "Site": "Site",
    "Location": "Location",
    "User": "User",
    "Brand_x0020__x002f__x0020_Model": "Brand / Model",
    "S_x002f_N_x0020_No_x002e_": "Serial No.",
    "Asset_x0020_Code": "Asset Code",
    "Status": "Status",
}
STATUS_CHOICES = ("", "Active", "Inactive")


def projector_display_value(value, default="-"):
    """Normalize missing presentation values without changing a source record."""
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text if text else default


def projector_view_fields(row):
    """Only expose verified business fields, never Graph or SharePoint metadata."""
    return {
        label: projector_display_value(row.get(key))
        for key, label in PROJECTOR_FIELDS.items()
    }


def projector_payload(values, *, original=None):
    """Use exact list keys. Add skips empty options; Edit sends only changed fields."""
    if original is None:
        return {
            key: projector_display_value(values.get(key), default="")
            for key in PROJECTOR_FIELDS
            if projector_display_value(values.get(key), default="")
        }
    return {
        key: projector_display_value(values.get(key), default="")
        for key in PROJECTOR_FIELDS
        if projector_display_value(values.get(key), default="")
        != projector_display_value(original.get(key), default="")
    }


def projector_metrics(frame):
    if frame.empty:
        return 0, 0, 0
    if "Status" not in frame:
        return len(frame), 0, 0
    statuses = frame["Status"].map(lambda value: projector_display_value(value, default="").casefold())
    return len(frame), int(statuses.eq("active").sum()), int(statuses.eq("inactive").sum())


def _inputs(row=None):
    """Build fields owned by Projector; no Computer mapping or guessed defaults."""
    if row is None:
        row = {}
    values = {}
    for key, label in PROJECTOR_FIELDS.items():
        current = projector_display_value(row.get(key), default="")
        if key == "Status":
            options = STATUS_CHOICES if current in STATUS_CHOICES else (*STATUS_CHOICES, current)
            values[key] = st.selectbox(label, options, index=options.index(current))
        elif key == "User":
            values[key] = st.text_area(label, value=current)
        else:
            values[key] = st.text_input(label, value=current)
    return values


@st.dialog("Projector details")
def view_projector_dialog(row, *, admin_mode=False):
    for label, value in projector_view_fields(row).items():
        if label == "Serial No." and not admin_mode:
            value = "🔒 ซ่อนสำหรับผู้ใช้ทั่วไป"
        st.write(f"**{label}:** {value}")


@st.dialog("Add Projector")
def add_projector_dialog(*, create_item, clear_cache):
    values = _inputs()
    if st.button("Save Projector", type="primary"):
        payload = projector_payload(values)
        if not payload:
            st.error("Enter at least one Projector field.")
            return
        ok, response = create_item(LIST_NAME, payload)
        if ok:
            clear_cache()
            st.success("Projector added.")
            st.rerun()
        else:
            st.error(f"Could not add Projector: {response}")


@st.dialog("Edit Projector")
def edit_projector_dialog(row, *, update_item, clear_cache):
    item_id = projector_display_value(row.get("_item_id"), default="")
    if not item_id:
        st.error("The selected Projector has no SharePoint item ID.")
        return
    values = _inputs(row)
    if st.button("Save Projector", type="primary"):
        payload = projector_payload(values, original=row)
        if not payload:
            st.info("No changes to save.")
            return
        ok, response = update_item(LIST_NAME, item_id, payload)
        if ok:
            clear_cache()
            st.success("Projector updated.")
            st.rerun()
        else:
            st.error(f"Could not update Projector: {response}")


def render_projector_asset(*, df_hw, admin_mode, create_item, update_item, clear_cache):
    """Keep SharePoint keys, metrics, and actions in the Projector page."""
    frame = df_hw.copy() if isinstance(df_hw, pd.DataFrame) else pd.DataFrame()

    def card(row, index, is_admin):
        item = row.to_dict()
        with st.container(border=True):
            st.markdown(f"### {projector_display_value(item.get('Number_x0020_Asset'))}")
            fields = projector_view_fields(item)
            for label in ("Company", "User", "Brand / Model", "Location", "Status"):
                st.write(f"**{label}:** {fields[label]}")
            if st.button("View", key=f"projector_view_{index}"):
                view_projector_dialog(item, admin_mode=is_admin)
            if is_admin and st.button("Edit", key=f"projector_edit_{index}"):
                edit_projector_dialog(item, update_item=update_item, clear_cache=clear_cache)

    total, active, inactive = projector_metrics(frame)
    render_generic_hardware_asset(
        df_hw=frame,
        list_name=LIST_NAME,
        hardware_name="Projector",
        admin_mode=admin_mode,
        card_renderer=card,
        add_handler=lambda _list_name: add_projector_dialog(
            create_item=create_item, clear_cache=clear_cache
        ),
        add_button_label="Add Projector",
        search_fields=tuple(PROJECTOR_FIELDS),
        metric_config=(
            ("Total Projectors", lambda _frame: total),
            ("Active", lambda _frame: active),
            ("Inactive", lambda _frame: inactive),
        ),
    )
