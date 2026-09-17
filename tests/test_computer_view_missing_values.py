"""Focused display tests for the Computer View dialog."""

import ast
from pathlib import Path
import subprocess

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "DocumentReportUnified.py"
BASE = "a4a532be4c9987e2f59af8175528005cafc0e4ad"


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _ViewStreamlit:
    def __init__(self):
        self.output = []
        self.raw = None

    def dialog(self, _title):
        return lambda function: function

    def markdown(self, value):
        self.output.append(value)

    def write(self, value):
        self.output.append(value)

    def columns(self, count):
        return [_Context() for _ in range(count)]

    def expander(self, _title):
        return _Context()

    def json(self, value):
        self.raw = value


def _load_view():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    names = {"_computer_view_value", "show_pop_computer"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in nodes} == names
    fake = _ViewStreamlit()
    namespace = {"pd": pd, "st": fake}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace, fake


def test_missing_values_render_as_dash_without_mutating_row():
    namespace, fake = _load_view()
    row = pd.Series({
        "field_7": float("nan"), "field_3": None, "field_1": "",
        "field_6": "  ", "field_8": float("nan"), "Status": float("nan"),
        "field_13": None, "field_15": "", "field_16": " \t ",
    }).to_dict()
    original = row.copy()
    namespace["show_pop_computer"](row, admin_mode=True)
    output = "\n".join(fake.output)
    for label in ("พนักงาน", "บริษัท", "Hostname", "Serial No", "สถานะ", "RAM"):
        assert f"{label}:** -" in output
    assert "### 💻 -" in output
    assert "Storage C:** -  D: -" in output
    assert "nan" not in output.lower() and "none" not in output.lower()
    assert fake.raw is row
    for key, value in original.items():
        assert (pd.isna(value) and pd.isna(row[key])) or row[key] == value


def test_real_values_and_non_admin_serial_visibility():
    namespace, fake = _load_view()
    row = {
        "field_7": "ThinkPad T14", "field_3": "Employee A", "field_1": "OPT",
        "field_6": "HOST-A", "field_8": "SER-001", "Status": "Active",
        "field_13": 16, "field_15": "512 GB", "field_16": False,
    }
    namespace["show_pop_computer"](row, admin_mode=True)
    output = "\n".join(fake.output)
    for value in ("ThinkPad T14", "Employee A", "OPT", "HOST-A", "SER-001", "Active", "16", "512 GB", "False"):
        assert value in output
    other = _ViewStreamlit()
    namespace["st"] = other
    namespace["show_pop_computer"](row, admin_mode=False)
    assert "SER-001" not in "\n".join(other.output)
    assert any("ซ่อนสำหรับผู้ใช้ทั่วไป" in line for line in other.output)


def test_computer_mutation_dialogs_unchanged_from_main():
    current = ast.parse(SOURCE.read_text(encoding="utf-8"))
    baseline = subprocess.run(
        ["git", "show", f"{BASE}:DocumentReportUnified.py"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout
    old = ast.parse(baseline)
    for name in ("edit_computer_dialog", "add_computer_dialog"):
        get = lambda tree: next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
        assert ast.dump(get(current)) == ast.dump(get(old))
