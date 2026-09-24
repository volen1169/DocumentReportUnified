"""Focused Group E-mail schema and mailbox ownership rules."""

import datetime as dt
import unittest

import pandas as pd

from services.group_email import account_counts, group_email_payload, login_devices
from services.license_expiry import parse_expiration_date


HEADERS = ("Record ID", "Display Name", "Email", "Assigned Users", "Login Devices", "Company", "Expiry Date")


class GroupEmailTests(unittest.TestCase):
    def test_loaded_exact_fields_and_multiple_users_stay_on_one_row(self):
        frame = pd.DataFrame([{
            "Display Name": "PD", "Email": "PD@siamwin.co.th",
            "Assigned Users": "Parinda Putson / Suphakan Chotirak",
            "Login Devices": "2",
        }])
        self.assertEqual(account_counts(frame), (1, 1, 1))
        self.assertEqual(frame.iloc[0]["Assigned Users"], "Parinda Putson / Suphakan Chotirak")
        self.assertEqual(login_devices(frame.iloc[0]["Login Devices"]), 2)

    def test_blank_and_zero_device_counts(self):
        self.assertIsNone(login_devices(""))
        self.assertIsNone(login_devices(None))
        self.assertEqual(login_devices("0"), 0)

    def test_positive_integer_device_count(self):
        self.assertEqual(login_devices("12"), 12)
        self.assertEqual(login_devices(2), 2)

    def test_invalid_device_counts(self):
        for value in ("-1", -1, "1.5", 1.5, "many", True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                login_devices(value)

    def test_add_payload_uses_exact_keys_and_preserves_names(self):
        values = dict.fromkeys(HEADERS, "")
        values.update({"Display Name": "PD", "Email": "PD@siamwin.co.th",
                       "Assigned Users": "Parinda Putson / Suphakan Chotirak", "Login Devices": "2"})
        payload = group_email_payload(HEADERS, values)
        self.assertEqual(set(payload), set(HEADERS))
        self.assertEqual(payload["Login Devices"], 2)
        self.assertEqual(payload["Display Name"], "PD")
        self.assertEqual(payload["Assigned Users"], values["Assigned Users"])

    def test_edit_payload_allows_blank_devices_and_retains_unrelated_fields(self):
        values = {"Record ID": 17, "Display Name": "PD", "Email": "PD@siamwin.co.th",
                  "Assigned Users": "Parinda / Suphakan", "Login Devices": "", "Company": "SWI",
                  "Expiry Date": "2026-11-12 00:00:00"}
        payload = group_email_payload(HEADERS, values, ["other@siamwin.co.th"], original_email=values["Email"])
        self.assertIsNone(payload["Login Devices"])
        self.assertEqual(payload["Record ID"], 17)
        self.assertEqual(payload["Expiry Date"], values["Expiry Date"])

    def test_add_rejects_duplicate_email_regardless_of_case_or_outer_space(self):
        values = {"Email": " PD@siamwin.co.th ", "Login Devices": "0"}
        with self.assertRaisesRegex(ValueError, "1 Email"):
            group_email_payload(HEADERS, values, ["pd@SIAMWIN.co.th"])

    def test_missing_schema_and_blank_email_rejected(self):
        with self.assertRaisesRegex(ValueError, "Login Devices"):
            group_email_payload(("Email", "Assigned Users"), {"Email": "a@b.com"})
        with self.assertRaisesRegex(ValueError, "กรุณากรอก Email"):
            group_email_payload(HEADERS, {"Email": "  "})

    def test_blank_email_and_duplicates_excluded_from_account_total(self):
        frame = pd.DataFrame({"Email": ["  ", None, "PD@siamwin.co.th", " pd@SIAMWIN.co.th ", "other@example.com"]})
        self.assertEqual(account_counts(frame), (5, 3, 2))

    def test_expiry_parser_regression_for_loader_datetime_text(self):
        self.assertEqual(parse_expiration_date("2026-11-12 00:00:00"), dt.date(2026, 11, 12))
        self.assertEqual((dt.date(2026, 11, 12) - dt.date(2026, 9, 24)).days, 49)


if __name__ == "__main__":
    unittest.main()
