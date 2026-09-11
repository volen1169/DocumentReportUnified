from pathlib import Path
import sys
from types import SimpleNamespace

import pandas as pd

sys.modules.setdefault("streamlit", SimpleNamespace())

from views.assets import generic_hardware_asset, monitor_asset, printer_asset


ROOT = Path(__file__).resolve().parents[1]


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeStreamlit:
    def __init__(self, *, search="", clicked_key=None, clicked_label=None):
        self.search = search
        self.clicked_key = clicked_key
        self.clicked_label = clicked_label
        self.markdowns = []
        self.metrics = []
        self.captions = []

    def markdown(self, value, **_kwargs):
        self.markdowns.append(value)

    def metric(self, label, value):
        self.metrics.append((label, value))

    def columns(self, spec):
        count = spec if isinstance(spec, int) else len(spec)
        return [_Context() for _ in range(count)]

    def text_input(self, *_args, **_kwargs):
        return self.search

    def button(self, label, *, key=None, **_kwargs):
        return key == self.clicked_key or (key is None and label == self.clicked_label)

    def container(self, **_kwargs):
        return _Context()

    def caption(self, value):
        self.captions.append(value)


def _render(module, fake_st, frame, *, admin_mode=False, **handlers):
    generic_hardware_asset.st = fake_st
    module.st = fake_st
    module_name = "monitor" if module is monitor_asset else "printer"
    getattr(module, f"render_{module_name}_asset")(
        df_hw=frame,
        admin_mode=admin_mode,
        **handlers,
    )


def test_generic_has_no_schema_or_computer_callback_dependency():
    source = (ROOT / "views/assets/generic_hardware_asset.py").read_text(encoding="utf-8")
    for forbidden in (
        "show_pop_computer", "add_computer_dialog", "edit_computer_dialog",
        "field_1", "field_3", "field_6", "field_7", "field_8", "field_13",
    ):
        assert forbidden not in source


def test_monitor_owns_schema_search_card_and_callbacks():
    frame = pd.DataFrame([
        {"field_1": "OPT", "field_2": "Dell P2422H", "field_3": "Alice", "field_4": "MON-1", "Status": "Active"},
        {"field_1": "PRP", "field_2": "LG 24", "field_3": "Bob", "field_4": "MON-2", "Status": "Repair"},
    ], index=[7, 3])
    calls = []
    fake = FakeStreamlit(search="dell", clicked_key="mon_view_7")
    _render(
        monitor_asset, fake, frame, admin_mode=True,
        show_pop_monitor=lambda data, admin_mode=False: calls.append(("view", data["field_4"], admin_mode)),
        add_monitor_dialog=lambda name: calls.append(("add", name)),
        edit_monitor_dialog=lambda data, name: calls.append(("edit", data["field_4"], name)),
        badge_renderer=lambda status: f"badge:{status}",
    )
    rendered = "\n".join(fake.markdowns)
    assert "Dell P2422H" in rendered and "MON-1" in rendered
    assert "LG 24" not in rendered
    assert calls == [("view", "MON-1", True)]
    assert fake.metrics == [("TOTAL ASSETS", 2), ("ACTIVE", 1), ("INACTIVE", 0), ("REPAIR", 1)]
    assert tuple(monitor_asset.MONITOR_FIELDS) == ("field_1", "field_3", "field_2", "field_4", "Status")


def test_printer_owns_schema_search_card_and_callbacks():
    frame = pd.DataFrame([
        {"field_1": "OPT", "User": "Alice", "Brand_x0020__x002f__x0020_Model": "Canon A", "S_x002f_N_x0020_No_x002e_": "PRN-1", "field_3": "10.0.0.1", "Status": "Active"},
        {"field_1": "PRP", "User": "Bob", "Brand_x0020__x002f__x0020_Model": "Ricoh B", "S_x002f_N_x0020_No_x002e_": "PRN-2", "field_3": "10.0.0.2", "Status": "Inactive"},
    ], index=[4, 9])
    calls = []
    fake = FakeStreamlit(search="CANON", clicked_key="prn_edit_4")
    _render(
        printer_asset, fake, frame, admin_mode=True,
        show_pop_printer=lambda data, admin_mode=False: calls.append(("view", data["field_3"], admin_mode)),
        add_printer_dialog=lambda name: calls.append(("add", name)),
        edit_printer_dialog=lambda data, name: calls.append(("edit", data["field_3"], name)),
    )
    rendered = "\n".join(fake.markdowns)
    assert "Canon A" in rendered and "PRN-1" in rendered
    assert "Ricoh B" not in rendered
    assert calls == [("edit", "10.0.0.1", "Asset Printer")]
    assert tuple(printer_asset.PRINTER_FIELDS) == (
        "Company", "User", "Brand_x0020__x002f__x0020_Model",
        "S_x002f_N_x0020_No_x002e_", "field_3",
    )


def test_empty_and_non_admin_paths_do_not_call_mutations():
    calls = []
    fake = FakeStreamlit()
    _render(
        monitor_asset, fake, pd.DataFrame(columns=monitor_asset.MONITOR_FIELDS),
        show_pop_monitor=lambda *_args, **_kwargs: calls.append("view"),
        add_monitor_dialog=lambda *_args: calls.append("add"),
        edit_monitor_dialog=lambda *_args: calls.append("edit"),
        badge_renderer=lambda status: status,
    )
    assert calls == []
    assert fake.metrics == [("TOTAL ASSETS", 0), ("ACTIVE", 0), ("INACTIVE", 0), ("REPAIR", 0)]


def test_entrypoint_routes_specific_pages_and_marks_pending_compatibility():
    source = (ROOT / "DocumentReportUnified.py").read_text(encoding="utf-8")
    assert 'sub == "Asset Monitor"' in source and "show_pop_monitor=show_pop_monitor" in source
    assert 'sub == "Asset Printer"' in source and "show_pop_printer=show_pop_printer" in source
    assert "SCHEMA PENDING CONFIRMATION" in source
    assert "render_temporary_legacy_hardware_card" in source
