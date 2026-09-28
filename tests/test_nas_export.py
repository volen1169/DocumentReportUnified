"""Regression checks for export-only NAS permission rules and serializers."""

import io
import unittest

import pandas as pd

from services.nas_export import (
    _apply_nas_export_required_permissions,
    build_nas_csv,
    build_nas_excel,
    build_nas_export_dataframe_from_permissions,
)


OPT_ISO_RW_USERS = (
    "teerapat.po",
    "cholticha.ma",
    "sompong.po",
    "sirinapa.ru",
    "supanee.na",
    "surattana.ch",
    "sirikorn.ph",
)


def _prepared_frame(records):
    """Build the same prepared (shares, NAS identities) contract as the parser."""
    permission_by_user = {
        username.casefold(): {"Name": username, "Shares": {"OPT_ISO": acl}}
        for username, _company, _display_name, acl in records
    }
    profiles = {
        username.casefold(): {"Company": company, "Display Name": display_name}
        for username, company, display_name, _acl in records
    }
    return build_nas_export_dataframe_from_permissions(
        (["OPT_ISO"], permission_by_user),
        profile_lookup=lambda username: profiles[username.casefold()],
        exclude_names=set(),
    )


class NasExportTests(unittest.TestCase):
    def test_opt_regular_user_has_read_permission(self):
        record = _apply_nas_export_required_permissions({"OPT_ISO": "Deny"}, "OPT", "normal.user")
        self.assertEqual(record["OPT_ISO"], "R")

    def test_all_seven_approved_users_have_read_write(self):
        for username in OPT_ISO_RW_USERS:
            with self.subTest(username=username):
                record = _apply_nas_export_required_permissions({}, "OPT", username)
                self.assertEqual(record["OPT_ISO"], "R/W")

    def test_username_case_and_surrounding_whitespace(self):
        for username in ("Teerapat.Po", " teerapat.po "):
            with self.subTest(username=username):
                record = _apply_nas_export_required_permissions({}, "OPT", username)
                self.assertEqual(record["OPT_ISO"], "R/W")

    def test_approved_username_in_other_companies_remains_blank(self):
        for company in ("PRP", "SWI", "PLC", "EGI"):
            with self.subTest(company=company):
                record = _apply_nas_export_required_permissions(
                    {"OPT_ISO": "Deny"}, company, "teerapat.po"
                )
                self.assertEqual(record["OPT_ISO"], "")

    def test_source_acl_is_overridden_for_regular_and_approved_opt_users(self):
        for username, expected in (("normal.user", "R"), ("teerapat.po", "R/W")):
            for acl in ("", "R", "R/W", "Deny"):
                with self.subTest(username=username, acl=acl):
                    record = _apply_nas_export_required_permissions(
                        {"OPT_ISO": acl}, "OPT", username
                    )
                    self.assertEqual(record["OPT_ISO"], expected)

    def test_ad_display_name_does_not_replace_nas_username_for_permission(self):
        frame = _prepared_frame([("teerapat.po", "OPT", "Teerapat Full Name", "Deny")])
        self.assertEqual(frame.loc[0, "Name"], "Teerapat Full Name")
        self.assertEqual(frame.loc[0, "OPT_ISO"], "R/W")

    def test_dataframe_company_sort_name_sort_and_numbering(self):
        frame = _prepared_frame([
            ("opt.z", "OPT", "Zeta", "Deny"),
            ("swi.a", "SWI", "Alpha", "R/W"),
            ("opt.a", "OPT", "alpha", ""),
            ("prp.b", "PRP", "Beta", "Deny"),
        ])
        self.assertEqual(frame["Company"].tolist(), ["OPT", "OPT", "PRP", "SWI"])
        self.assertEqual(frame["Name"].tolist(), ["alpha", "Zeta", "Beta", "Alpha"])
        self.assertEqual(frame["No."].tolist(), [1, 2, 3, 4])
        self.assertEqual(frame["OPT_ISO"].tolist(), ["R", "R", "", ""])

    def test_csv_and_excel_permissions_match_final_dataframe(self):
        frame = _prepared_frame([
            ("normal.user", "OPT", "Regular OPT", "Deny"),
            ("teerapat.po", "OPT", "Approved OPT", ""),
            ("prp.user", "PRP", "Other company", "R/W"),
        ])
        csv_frame = pd.read_csv(io.BytesIO(build_nas_csv(frame)), keep_default_na=False)
        excel_frame = pd.read_excel(
            io.BytesIO(build_nas_excel(frame)), sheet_name="NAS Permissions", keep_default_na=False
        )
        for output in (csv_frame, excel_frame):
            self.assertEqual(output["Name"].tolist(), frame["Name"].tolist())
            self.assertEqual(output["OPT_ISO"].tolist(), frame["OPT_ISO"].tolist())
        self.assertEqual(frame["OPT_ISO"].tolist(), ["R/W", "R", ""])

    def test_other_required_shares_remain_export_only(self):
        original_acl = {"OPG_Data_Center": "Deny", "OPT_Data_Center": "R", "OPG_Information_Technology": "Deny"}
        regular = _apply_nas_export_required_permissions(original_acl.copy(), "OPT", "normal.user")
        approved = _apply_nas_export_required_permissions(original_acl.copy(), "OPT", "teerapat.po")
        non_opt = _apply_nas_export_required_permissions(original_acl.copy(), "PRP", "normal.user")
        self.assertEqual(original_acl, {"OPG_Data_Center": "Deny", "OPT_Data_Center": "R", "OPG_Information_Technology": "Deny"})
        for record in (regular, approved, non_opt):
            self.assertEqual(record["OPG_Data_Center"], "R/W")
        self.assertEqual(regular["OPT_Data_Center"], "R/W")
        self.assertEqual(approved["OPT_Data_Center"], "R/W")
        self.assertEqual(approved["OPG_Information_Technology"], "R/W")
        self.assertEqual(regular["OPG_Information_Technology"], "")
        self.assertEqual(non_opt["OPG_Information_Technology"], "")


if __name__ == "__main__":
    unittest.main()
