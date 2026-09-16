from pathlib import Path
import ast
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
        self.placeholders = []
        self.column_specs = []

    def markdown(self, value, **_kwargs):
        self.markdowns.append(value)

    def metric(self, label, value):
        self.metrics.append((label, value))

    def columns(self, spec):
        self.column_specs.append(spec)
        count = spec if isinstance(spec, int) else len(spec)
        return [_Context() for _ in range(count)]

    def text_input(self, *_args, **kwargs):
        self.placeholders.append(kwargs.get("placeholder"))
        return self.search

    def button(self, label, *, key=None, **_kwargs):
        return key == self.clicked_key or (key is None and label == self.clicked_label)

    def container(self, **_kwargs):
        return _Context()

    def caption(self, value):
        self.captions.append(value)

    def info(self, value):
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
        '"Status"', '"Active"', '"Inactive"', '"Repair"',
        "Hostname", "Model", "S/N",
    ):
        assert forbidden not in source


def test_generic_metrics_and_search_placeholder_are_page_owned():
    fake = FakeStreamlit()
    generic_hardware_asset.st = fake
    frame = pd.DataFrame([{"Name": "one"}])
    generic_hardware_asset.render_generic_hardware_asset(
        df_hw=frame,
        list_name="Asset Example",
        hardware_name="Example",
        admin_mode=False,
        card_renderer=lambda *_args: None,
        add_handler=None,
        add_button_label="",
        search_fields=("Name",),
        metric_config=(("ITEMS", lambda data: len(data)),),
    )
    assert fake.metrics == [("ITEMS", 1)]
    assert fake.placeholders == ["ค้นหาข้อมูล..."]


def test_generic_omitted_metric_config_skips_metrics_and_continues():
    fake = FakeStreamlit()
    generic_hardware_asset.st = fake
    rendered = []
    generic_hardware_asset.render_generic_hardware_asset(
        df_hw=pd.DataFrame([{"Name": "one"}]),
        list_name="Asset Example",
        hardware_name="Example",
        admin_mode=False,
        card_renderer=lambda row, key, is_admin: rendered.append((row["Name"], key, is_admin)),
        add_handler=None,
        add_button_label="",
        search_fields=("Name",),
    )
    assert fake.metrics == []
    assert 0 not in fake.column_specs
    assert rendered == [("one", 0, False)]


def test_generic_empty_metric_config_skips_metrics_without_zero_columns():
    fake = FakeStreamlit()
    generic_hardware_asset.st = fake
    generic_hardware_asset.render_generic_hardware_asset(
        df_hw=pd.DataFrame(),
        list_name="Asset Example",
        hardware_name="Example",
        admin_mode=False,
        card_renderer=lambda *_args: None,
        add_handler=None,
        add_button_label="",
        search_fields=(),
        metric_config=(),
    )
    assert fake.metrics == []
    assert 0 not in fake.column_specs
    assert fake.column_specs == [[0.82, 0.18]]


def test_generic_empty_frame_calls_page_owned_empty_state_not_card_renderer():
    fake = FakeStreamlit()
    generic_hardware_asset.st = fake
    calls = []
    generic_hardware_asset.render_generic_hardware_asset(
        df_hw=pd.DataFrame(),
        list_name="Asset CCTV",
        hardware_name="CCTV",
        admin_mode=False,
        card_renderer=lambda *_args: calls.append("card"),
        add_handler=None,
        add_button_label="",
        search_fields=(),
        empty_state_renderer=lambda: calls.append("empty"),
    )
    assert calls == ["empty"]
    assert 3 not in fake.column_specs


def test_generic_empty_frame_without_custom_state_uses_neutral_fallback():
    fake = FakeStreamlit()
    generic_hardware_asset.st = fake
    generic_hardware_asset.render_generic_hardware_asset(
        df_hw=pd.DataFrame(),
        list_name="Asset Example",
        hardware_name="Example",
        admin_mode=False,
        card_renderer=lambda *_args: None,
        add_handler=None,
        add_button_label="",
        search_fields=(),
    )
    assert fake.captions == ["ยังไม่มีข้อมูล"]
    assert 3 not in fake.column_specs


def test_monitor_owns_schema_search_card_and_callbacks():
    frame = pd.DataFrame([
        {"Company": "OPT", "Brand_x002f_Model": "Dell P2422H", "User": "Alice", "S_x002f_NNo_x002e_": "MON-1", "Status": "Active"},
        {"Company": "PRP", "Brand_x002f_Model": "LG 24", "User": "Bob", "S_x002f_NNo_x002e_": "MON-2", "Status": "Repair"},
    ], index=[7, 3])
    calls = []
    fake = FakeStreamlit(search="dell", clicked_key="mon_view_7")
    _render(
        monitor_asset, fake, frame, admin_mode=True,
        show_pop_monitor=lambda data, admin_mode=False: calls.append(("view", data["S_x002f_NNo_x002e_"], admin_mode)),
        add_monitor_dialog=lambda name: calls.append(("add", name)),
        edit_monitor_dialog=lambda data, name: calls.append(("edit", data["S_x002f_NNo_x002e_"], name)),
        badge_renderer=lambda status: f"badge:{status}",
    )
    rendered = "\n".join(fake.markdowns)
    assert "Dell P2422H" in rendered and "MON-1" in rendered
    assert "LG 24" not in rendered
    assert calls == [("view", "MON-1", True)]
    assert fake.metrics == [("TOTAL ASSETS", 2), ("ACTIVE", 1), ("INACTIVE", 0), ("REPAIR", 1)]
    assert tuple(monitor_asset.MONITOR_FIELDS) == ("Company", "User", "Brand_x002f_Model", "S_x002f_NNo_x002e_", "Status")
    assert fake.placeholders == ["🔍 ค้นหาบริษัท, ชื่อพนักงาน, รุ่น, Serial No...."]


def test_monitor_add_and_edit_callbacks_are_monitor_owned():
    frame = pd.DataFrame([{"Company": "OPT", "Brand_x002f_Model": "Dell", "User": "Alice", "S_x002f_NNo_x002e_": "MON-1", "Status": "Active"}], index=[7])
    calls = []
    for fake in (
        FakeStreamlit(clicked_label="➕ เพิ่ม Monitor"),
        FakeStreamlit(clicked_key="mon_edit_7"),
    ):
        _render(
            monitor_asset, fake, frame, admin_mode=True,
            show_pop_monitor=lambda *_args, **_kwargs: calls.append("view"),
            add_monitor_dialog=lambda name: calls.append(("add", name)),
            edit_monitor_dialog=lambda data, name: calls.append(("edit", data["S_x002f_NNo_x002e_"], name)),
            badge_renderer=lambda status: status,
        )
    assert calls == [("add", "Asset Monitor"), ("edit", "MON-1", "Asset Monitor")]


def test_monitor_card_uses_runtime_fields_and_hides_nan_status():
    frame = pd.DataFrame([{
        "Company": "OPT",
        "User": "Alice",
        "Brand_x002f_Model": "Dell P2422H",
        "S_x002f_NNo_x002e_": "MON-1",
        "Status": float("nan"),
        "field_6": "COMPUTER-HOST",
        "field_7": "COMPUTER-MODEL",
        "field_8": "COMPUTER-SERIAL",
        "field_13": "COMPUTER-RAM",
    }], index=[7])
    fake = FakeStreamlit()
    badge_values = []
    _render(
        monitor_asset, fake, frame, admin_mode=True,
        show_pop_monitor=lambda *_args, **_kwargs: None,
        add_monitor_dialog=lambda *_args: None,
        edit_monitor_dialog=lambda *_args: None,
        badge_renderer=lambda status: badge_values.append(status) or f"badge:{status}",
    )
    rendered = "\n".join(fake.markdowns)
    assert all(value in rendered for value in ("OPT", "Alice", "Dell P2422H", "MON-1"))
    assert all(value not in rendered for value in ("COMPUTER-HOST", "COMPUTER-MODEL", "COMPUTER-SERIAL", "COMPUTER-RAM"))
    assert badge_values == [""]
    assert "nan" not in rendered.lower()


def test_printer_owns_schema_search_card_and_callbacks():
    frame = pd.DataFrame([
        {"Company": "OPT", "User": "Alice", "Brand_x0020__x002f__x0020_Model": "Canon A", "S_x002f_N_x0020_No_x002e_": "PRN-1", "Status": "Active", "_item_id": "1", "field_1": "WRONG-COMPANY", "field_3": "WRONG-IP"},
        {"Company": "PRP", "User": "Bob", "Brand_x0020__x002f__x0020_Model": "Ricoh B", "S_x002f_N_x0020_No_x002e_": "PRN-2", "Status": "Inactive", "_item_id": "2", "field_1": "WRONG-COMPANY", "field_3": "WRONG-IP"},
    ], index=[4, 9])
    calls = []
    fake = FakeStreamlit(search="CANON", clicked_key="prn_edit_4")
    _render(
        printer_asset, fake, frame, admin_mode=True,
        show_pop_printer=lambda data, admin_mode=False: calls.append(("view", data["S_x002f_N_x0020_No_x002e_"], admin_mode)),
        add_printer_dialog=lambda name: calls.append(("add", name)),
        edit_printer_dialog=lambda data, name: calls.append(("edit", data["S_x002f_N_x0020_No_x002e_"], name)),
    )
    rendered = "\n".join(fake.markdowns)
    assert "Canon A" in rendered and "PRN-1" in rendered
    assert "Ricoh B" not in rendered
    assert "OPT" in rendered and "WRONG-COMPANY" not in rendered
    assert "IP" not in rendered and "WRONG-IP" not in rendered
    assert calls == [("edit", "PRN-1", "Asset Printer")]
    assert tuple(printer_asset.PRINTER_FIELDS) == (
        "Company", "User", "Brand_x0020__x002f__x0020_Model",
        "S_x002f_N_x0020_No_x002e_", "Status",
    )
    company_search = FakeStreamlit(search="prp")
    _render(
        printer_asset, company_search, frame,
        show_pop_printer=lambda *_args, **_kwargs: None,
        add_printer_dialog=lambda *_args: None,
        edit_printer_dialog=lambda *_args: None,
    )
    company_rendered = "\n".join(company_search.markdowns)
    assert "Ricoh B" in company_rendered and "Canon A" not in company_rendered


def test_printer_view_add_edit_and_non_admin_callbacks():
    frame = pd.DataFrame([{"Company": "OPT", "User": "Alice", "Brand_x0020__x002f__x0020_Model": "Canon", "S_x002f_N_x0020_No_x002e_": "PRN-1", "Status": "Active", "_item_id": "1"}], index=[4])
    calls = []
    for fake, admin_mode in (
        (FakeStreamlit(clicked_key="prn_view_4"), True),
        (FakeStreamlit(clicked_label="➕ เพิ่ม Printer"), True),
        (FakeStreamlit(clicked_key="prn_edit_4"), True),
        (FakeStreamlit(clicked_key="prn_view_4", clicked_label="➕ เพิ่ม Printer"), False),
    ):
        _render(
            printer_asset, fake, frame, admin_mode=admin_mode,
            show_pop_printer=lambda data, admin_mode=False: calls.append(("view", data["S_x002f_N_x0020_No_x002e_"], admin_mode)),
            add_printer_dialog=lambda name: calls.append(("add", name)),
            edit_printer_dialog=lambda data, name: calls.append(("edit", data["S_x002f_N_x0020_No_x002e_"], name)),
        )
    assert calls == [
        ("view", "PRN-1", True),
        ("add", "Asset Printer"),
        ("edit", "PRN-1", "Asset Printer"),
    ]


def test_printer_runtime_fields_hide_nan_and_unverified_ip():
    frame = pd.DataFrame([{
        "Company": "EGI",
        "User": "Graphic",
        "Brand_x0020__x002f__x0020_Model": "EPSON L3150",
        "S_x002f_N_x0020_No_x002e_": float("nan"),
        "Status": "Active",
        "_item_id": "1",
        "field_1": "WRONG-COMPANY",
        "field_3": "10.0.0.1",
    }], index=[4])
    fake = FakeStreamlit()
    _render(
        printer_asset, fake, frame, admin_mode=True,
        show_pop_printer=lambda *_args, **_kwargs: None,
        add_printer_dialog=lambda *_args: None,
        edit_printer_dialog=lambda *_args: None,
    )
    rendered = "\n".join(fake.markdowns)
    assert all(value in rendered for value in ("EGI", "Graphic", "EPSON L3150"))
    assert "nan" not in rendered.lower()
    assert "WRONG-COMPANY" not in rendered and "10.0.0.1" not in rendered
    assert "IP Address" not in rendered and "🌐 IP" not in rendered


def test_printer_dialogs_use_runtime_payload_without_ip_guess():
    source = (ROOT / "DocumentReportUnified.py").read_text(encoding="utf-8")
    view_start = source.index("def show_pop_printer")
    edit_start = source.index("def edit_printer_dialog")
    add_start = source.index("def add_printer_dialog")
    view = source[view_start:source.index("# SECTION 09", view_start)]
    edit = source[edit_start:source.index("# SECTION 10", edit_start)]
    add = source[add_start:source.index("# SECTION 11", add_start)]
    for section in (view, edit, add):
        assert "Brand_x0020__x002f__x0020_Model" in section
        assert "S_x002f_N_x0020_No_x002e_" in section
        assert "field_1" not in section and "field_3" not in section
        assert "IP Address" not in section
    assert '"Company": company' in edit and '"Company": company' in add


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
    assert "render_temporary_legacy_hardware_empty_state" in source
    pending = source[source.index("def render_temporary_legacy_hardware_card"):source.index("# SECTION 08")]
    for forbidden in (
        "show_pop_computer", "edit_computer_dialog", "Hostname", "Model", "RAM", "Serial",
        "field_1", "field_3", "field_6", "field_7", "field_8", "field_13",
    ):
        assert forbidden not in pending
    route = source[source.index('if sub == "Asset Monitor"'):source.index("# 🌐 AD / Firewall Policy")]
    assert "add_handler=None" in route
    assert "search_fields=()" in route
    assert "empty_state_renderer=" in route


def test_pending_page_renderer_is_schema_neutral_for_each_pending_page():
    source = (ROOT / "DocumentReportUnified.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "render_temporary_legacy_hardware_card"
    )
    namespace = {"st": FakeStreamlit()}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "pending_renderer", "exec"), namespace)
    renderer = namespace["render_temporary_legacy_hardware_card"]
    for list_name in ("Asset Projector", "Asset UPS", "Asset CCTV", "Asset Access Control"):
        fake = FakeStreamlit(clicked_key="view_1")
        namespace["st"] = fake
        renderer(
            pd.Series({"field_1": "SECRET-COMPANY", "field_6": "SECRET-HOST"}),
            1,
            True,
            list_name=list_name,
        )
        rendered = "\n".join(fake.markdowns + fake.captions)
        assert list_name.replace("Asset ", "") in rendered
        assert "Schema pending confirmation" in rendered
        assert "SECRET-COMPANY" not in rendered and "SECRET-HOST" not in rendered


def test_pending_empty_state_is_schema_neutral_for_each_pending_page():
    source = (ROOT / "DocumentReportUnified.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "render_temporary_legacy_hardware_empty_state"
    )
    namespace = {"st": FakeStreamlit()}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "pending_empty_state", "exec"), namespace)
    renderer = namespace["render_temporary_legacy_hardware_empty_state"]
    for list_name in ("Asset Projector", "Asset UPS", "Asset CCTV", "Asset Access Control"):
        fake = FakeStreamlit()
        namespace["st"] = fake
        renderer(list_name=list_name)
        rendered = "\n".join(fake.markdowns + fake.captions)
        assert list_name.replace("Asset ", "") in rendered
        assert "Schema pending confirmation" in rendered
        assert "Hostname" not in rendered and "RAM" not in rendered


def test_computer_asset_source_is_unchanged_from_base():
    import subprocess

    current = (ROOT / "views/assets/computer_asset.py").read_bytes()
    baseline = subprocess.run(
        ["git", "show", "041d1994d5de49914865bba2942e366c2fab0c5c:views/assets/computer_asset.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    assert current == baseline


class MonitorDialogStreamlit:
    def __init__(self, *, clicked_label=None):
        self.clicked_label = clicked_label
        self.markdowns = []
        self.writes = []
        self.input_values = {}
        self.session_state = {}

    def markdown(self, value, **_kwargs):
        self.markdowns.append(value)

    def write(self, value):
        self.writes.append(value)

    def expander(self, *_args, **_kwargs):
        return _Context()

    def json(self, _value):
        return None

    def selectbox(self, label, options, *, index=0, **_kwargs):
        value = options[index]
        self.input_values[label] = value
        return value

    def text_input(self, label, *, value="", **_kwargs):
        self.input_values[label] = value
        return value

    def columns(self, spec):
        count = spec if isinstance(spec, int) else len(spec)
        return [_Context() for _ in range(count)]

    def button(self, label, **_kwargs):
        return label == self.clicked_label

    def success(self, _value):
        return None

    def error(self, _value):
        return None

    def warning(self, _value):
        return None

    def rerun(self):
        return None


def _load_monitor_dialog_functions(fake_st, *, update=None, create=None):
    source = (ROOT / "DocumentReportUnified.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {
        "_monitor_display_value", "show_pop_monitor",
        "edit_monitor_dialog", "add_monitor_dialog",
    }
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    for function in functions:
        function.decorator_list = []
    namespace = {
        "pd": pd,
        "st": fake_st,
        "COMPANY_OPTIONS": ["OPT", "SWI", "PRP", "PLC", "EGI", "THK"],
        "STATUS_OPTIONS": ["Active", "Inactive", "Spare", "Repair"],
        "sp_update_item": update or (lambda *_args: (True, {})),
        "sp_create_item": create or (lambda *_args: (True, {})),
        "sp_delete_item": lambda *_args: True,
        "clear_sp_cache": lambda: None,
    }
    exec(compile(ast.Module(body=functions, type_ignores=[]), "monitor_dialogs", "exec"), namespace)
    return namespace


def test_monitor_view_dialog_uses_runtime_schema_and_hides_nan():
    fake = MonitorDialogStreamlit()
    functions = _load_monitor_dialog_functions(fake)
    functions["show_pop_monitor"]({
        "Company": "OPT",
        "User": "Alice",
        "Brand_x002f_Model": "Dell P2422H",
        "S_x002f_NNo_x002e_": "MON-1",
        "Status": float("nan"),
        "field_1": "LEGACY-COMPANY",
        "field_2": "LEGACY-MODEL",
        "field_3": "LEGACY-USER",
        "field_4": "LEGACY-SERIAL",
    }, admin_mode=True)
    rendered = "\n".join(fake.markdowns + fake.writes)
    assert all(value in rendered for value in ("OPT", "Alice", "Dell P2422H", "MON-1"))
    assert all(value not in rendered for value in (
        "LEGACY-COMPANY", "LEGACY-MODEL", "LEGACY-USER", "LEGACY-SERIAL", "nan",
    ))
    assert "**✅ สถานะ:** -" in rendered


def test_monitor_edit_dialog_uses_runtime_initial_values_and_payload():
    fake = MonitorDialogStreamlit(clicked_label="💾 บันทึก")
    updates = []
    functions = _load_monitor_dialog_functions(
        fake,
        update=lambda list_name, item_id, fields: updates.append((list_name, item_id, fields)) or (True, {}),
    )
    functions["edit_monitor_dialog"]({
        "_item_id": "42",
        "Company": "OPT",
        "User": "Alice",
        "Brand_x002f_Model": "Dell P2422H",
        "S_x002f_NNo_x002e_": "MON-1",
        "Status": "Active",
        "field_1": "LEGACY-COMPANY",
        "field_2": "LEGACY-MODEL",
        "field_3": "LEGACY-USER",
        "field_4": "LEGACY-SERIAL",
    }, "Asset Monitor")
    assert fake.input_values == {
        "🏢 บริษัท": "OPT",
        "👤 ชื่อพนักงาน": "Alice",
        "🏷️ Brand/Model": "Dell P2422H",
        "🔢 Serial No.": "MON-1",
        "โ… Status": "Active",
    }
    assert updates == [("Asset Monitor", "42", {
        "Company": "OPT",
        "User": "Alice",
        "Brand_x002f_Model": "Dell P2422H",
        "S_x002f_NNo_x002e_": "MON-1",
        "Status": "Active",
    })]
    assert not any(key.startswith("field_") for key in updates[0][2])


def test_monitor_add_dialog_uses_runtime_payload_only():
    fake = MonitorDialogStreamlit(clicked_label="💾 บันทึก")
    creates = []
    functions = _load_monitor_dialog_functions(
        fake,
        create=lambda list_name, fields: creates.append((list_name, fields)) or (True, {}),
    )
    functions["add_monitor_dialog"]("Asset Monitor")
    assert creates == [("Asset Monitor", {
        "Company": "OPT",
        "User": "",
        "Brand_x002f_Model": "",
        "S_x002f_NNo_x002e_": "",
        "Status": "Active",
    })]
    assert not any(key.startswith("field_") for key in creates[0][1])
