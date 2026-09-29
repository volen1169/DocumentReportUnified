"""Projector field ownership against verified Asset Projector list internal names."""

import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd

# Import a separate copy with inert dialogs so these tests never require a
# running Streamlit session, even when the real package is installed in CI.
_streamlit = SimpleNamespace(dialog=lambda _title: lambda fn: fn)
_path = Path(__file__).resolve().parents[1] / "views/assets/projector_asset.py"
_spec = importlib.util.spec_from_file_location("projector_asset_under_test", _path)
projector_asset = importlib.util.module_from_spec(_spec)
with patch.dict("sys.modules", {"streamlit": _streamlit}):
    from views.assets import generic_hardware_asset
    _spec.loader.exec_module(projector_asset)


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeStreamlit:
    def __init__(self, clicked=None):
        self.clicked = clicked
        self.text = []
        self.metrics = []
        self.info_messages = []
        self.errors = []
        self.reruns = 0

    def markdown(self, text, **_kwargs):
        self.text.append(text)

    def write(self, text):
        self.text.append(text)

    def container(self, **_kwargs):
        return _Context()

    def columns(self, spec):
        return [_Context() for _ in range(spec if isinstance(spec, int) else len(spec))]

    def metric(self, label, value):
        self.metrics.append((label, value))

    def text_input(self, label, value="", **_kwargs):
        return value

    def text_area(self, label, value=""):
        return value

    def selectbox(self, label, options, index=0):
        return options[index]

    def button(self, label, **_kwargs):
        return label == self.clicked

    def info(self, text):
        self.info_messages.append(text)

    def error(self, text):
        self.errors.append(text)

    def success(self, text):
        self.text.append(text)

    def rerun(self):
        self.reruns += 1


ROW = {
    "_item_id": "test-item-13",
    "Number_x0020_Asset": "PJ-013",
    "Company": "OPT",
    "Site": "BR",
    "Location": "Meeting PLC",
    "User": "Meeting room",
    "Brand_x0020__x002f__x0020_Model": "Acer P1200",
    "S_x002f_N_x0020_No_x002e_": "SER-013",
    "Asset_x0020_Code": "OPT/2553/EQ/0582",
    "Status": "Active",
    "Title": None,
    "Created": "internal value",
}


class ProjectorTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeStreamlit()
        projector_asset.st = self.fake
        generic_hardware_asset.st = self.fake

    def test_exact_projector_runtime_keys_and_no_computer_fields(self):
        self.assertEqual(set(projector_asset.PROJECTOR_FIELDS), set(ROW) - {"_item_id", "Title", "Created"})
        self.assertFalse(any(key.startswith("field_") for key in projector_asset.PROJECTOR_FIELDS))
        self.assertEqual(projector_asset.STATUS_CHOICES, ("", "Active", "Inactive"))

    def test_view_excludes_internal_fields_and_normalizes_missing_values(self):
        row = {**ROW, "Location": float("nan"), "User": "   "}
        fields = projector_asset.projector_view_fields(row)
        self.assertEqual(fields["Location"], "-")
        self.assertEqual(fields["User"], "-")
        self.assertEqual(fields["Brand / Model"], "Acer P1200")
        self.assertNotIn("_item_id", fields)
        self.assertNotIn("Title", fields)
        projector_asset.view_projector_dialog(row, admin_mode=True)
        self.assertFalse(any("nan" in str(text).lower() or "internal value" in str(text)
                             for text in self.fake.text))

    def test_non_admin_view_hides_serial(self):
        projector_asset.view_projector_dialog(ROW)
        self.assertFalse(any("SER-013" in str(text) for text in self.fake.text))
        self.assertTrue(any("ซ่อนสำหรับผู้ใช้ทั่วไป" in str(text) for text in self.fake.text))

    def test_edit_preloads_verified_values_from_selected_row(self):
        seen = []
        self.fake.text_input = lambda label, value="", **_kwargs: (seen.append((label, value)) or value)
        self.fake.text_area = lambda label, value="": (seen.append((label, value)) or value)
        values = projector_asset._inputs(pd.Series(ROW))
        self.assertEqual(values["Number_x0020_Asset"], ROW["Number_x0020_Asset"])
        self.assertEqual(values["User"], ROW["User"])
        self.assertIn(("Serial No.", "SER-013"), seen)
        self.assertEqual(values["Status"], "Active")

    def test_display_value_missing_and_real_values(self):
        for missing in (None, float("nan"), "", " "):
            with self.subTest(missing=missing):
                self.assertEqual(projector_asset.projector_display_value(missing), "-")
        self.assertEqual(projector_asset.projector_display_value(" Acer "), "Acer")

    def test_add_payload_uses_only_verified_nonblank_keys(self):
        values = {**ROW, "User": "", "Location": float("nan")}
        payload = projector_asset.projector_payload(values)
        self.assertEqual(set(payload), set(projector_asset.PROJECTOR_FIELDS) - {"User", "Location"})
        self.assertNotIn("_item_id", payload)
        self.assertNotIn("Title", payload)
        self.assertEqual(payload["Number_x0020_Asset"], "PJ-013")
        self.assertEqual(payload["S_x002f_N_x0020_No_x002e_"], "SER-013")

    def test_edit_payload_preserves_untouched_fields_and_original_record(self):
        original = ROW.copy()
        values = {**ROW, "User": "Other room", "Location": ""}
        payload = projector_asset.projector_payload(values, original=original)
        self.assertEqual(payload, {"Location": "", "User": "Other room"})
        self.assertEqual(original, ROW)
        self.assertEqual(projector_asset.projector_payload(original, original=original), {})

    def test_edit_save_targets_original_item_id_with_delta_only(self):
        update = Mock(return_value=(True, {}))
        clear = Mock()
        self.fake.clicked = "Save Projector"
        original_inputs = projector_asset._inputs
        projector_asset._inputs = lambda _row: {**ROW, "User": "Other room"}
        try:
            projector_asset.edit_projector_dialog(ROW.copy(), update_item=update, clear_cache=clear)
        finally:
            projector_asset._inputs = original_inputs
        update.assert_called_once_with(
            "Asset Projector", ROW["_item_id"], {"User": "Other room"}
        )
        clear.assert_called_once()
        self.assertEqual(self.fake.reruns, 1)

    def test_add_save_with_mock_never_calls_sharepoint(self):
        create = Mock(return_value=(True, {}))
        clear = Mock()
        self.fake.clicked = "Save Projector"
        original_inputs = projector_asset._inputs
        projector_asset._inputs = lambda: {"Company": "OPT", "Status": "", "User": ""}
        try:
            projector_asset.add_projector_dialog(create_item=create, clear_cache=clear)
        finally:
            projector_asset._inputs = original_inputs
        create.assert_called_once_with("Asset Projector", {"Company": "OPT"})
        clear.assert_called_once()

    def test_missing_item_id_blocks_edit_and_empty_page_remains_safe(self):
        update = Mock()
        projector_asset.edit_projector_dialog(
            {"Company": "OPT"}, update_item=update, clear_cache=Mock()
        )
        update.assert_not_called()
        self.assertTrue(self.fake.errors)
        projector_asset.render_projector_asset(
            df_hw=pd.DataFrame(), admin_mode=True,
            create_item=Mock(), update_item=update, clear_cache=Mock(),
        )
        self.assertIn("ยังไม่มีข้อมูล", self.fake.info_messages)
        self.assertEqual(self.fake.metrics, [
            ("Total Projectors", 0), ("Active", 0), ("Inactive", 0)
        ])

    def test_cards_and_metrics_use_projector_values(self):
        projector_asset.render_projector_asset(
            df_hw=pd.DataFrame([ROW, {**ROW, "_item_id": "other", "Status": "Inactive"}]),
            admin_mode=False, create_item=Mock(), update_item=Mock(), clear_cache=Mock(),
        )
        self.assertEqual(self.fake.metrics, [
            ("Total Projectors", 2), ("Active", 1), ("Inactive", 1)
        ])
        self.assertTrue(any("PJ-013" in str(text) for text in self.fake.text))


if __name__ == "__main__":
    unittest.main()
