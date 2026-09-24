"""Focused tests for the Overview Dashboard license-expiry service."""

import datetime as dt
import unittest

import pandas as pd
from services.license_expiry import (
    SAFE_RECORD_FIELDS,
    build_license_expiry_records,
    classify_expiry,
    group_license_expiry_records,
    normalize_product_name,
    parse_expiration_date,
    summarize_license_expiry,
)


TODAY = dt.date(2026, 9, 23)


class LicenseExpiryTests(unittest.TestCase):
    def test_supported_product_mapping_is_explicit(self):
        self.assertEqual(normalize_product_name("App for business"), "Microsoft 365 Apps for business")
        self.assertEqual(normalize_product_name("Microsoft 365 Business Basic"), "Microsoft 365 Business Basic")
        self.assertIsNone(normalize_product_name("Unknown Plan"))

    def test_500_loader_rows_only_count_populated_identity_rows(self):
        rows = [{"License Plan": "App for business", "Expiry Date": "2026-11-12"} for _ in range(22)]
        rows.extend({"License Plan": None, "User Count (Calculated)": 0} for _ in range(478))
        records = build_license_expiry_records({"Office 365": pd.DataFrame(rows)}, today=TODAY)
        self.assertEqual(len(records), 22)
        self.assertEqual(summarize_license_expiry(records)["expiring_within_90"], 22)

    def test_returned_records_have_only_safe_fields_and_no_source_secrets(self):
        frame = pd.DataFrame([{
            "License Plan": "App for business",
            "Expiry Date": "2026-11-12",
            "Password": "must-not-leak",
            "Client Secret": "must-not-leak-either",
        }])
        record = build_license_expiry_records({"Office 365": frame}, today=TODAY)[0]
        self.assertEqual(set(record), SAFE_RECORD_FIELDS)
        self.assertNotIn("must-not-leak", repr(record))

    def test_expiry_boundaries(self):
        cases = [
            (90, "monitoring", "green", "Monitoring"),
            (61, "monitoring", "green", "Monitoring"),
            (60, "plan_renewal", "yellow", "Plan Renewal"),
            (31, "plan_renewal", "yellow", "Plan Renewal"),
            (30, "renewal_due", "red", "Renewal Due"),
            (0, "renewal_due", "red", "Renewal Due"),
            (-1, "expired", "expired", "Expired"),
        ]
        for days, urgency, tone, label in cases:
            with self.subTest(days=days):
                self.assertEqual(classify_expiry(days), (urgency, tone, label))

    def test_expiry_parsing_and_renewal_target(self):
        expiry = TODAY + dt.timedelta(days=61)
        frame = pd.DataFrame([{"License Plan": "App for business", "Expiry Date": expiry.strftime("%d/%m/%Y")}])
        record = build_license_expiry_records({"Office 365": frame}, today=TODAY)[0]
        self.assertEqual(record["expiration_date"], expiry)
        self.assertEqual(record["days_remaining"], 61)
        self.assertEqual(record["renewal_target"], expiry - dt.timedelta(days=30))

    def test_iso_date_is_not_reinterpreted_as_day_first(self):
        frame = pd.DataFrame([{"License Plan": "App for business", "Expiry Date": "2026-11-12 00:00:00"}])
        record = build_license_expiry_records({"Office 365": frame}, today=TODAY)[0]
        self.assertEqual(record["expiration_date"], dt.date(2026, 11, 12))
        self.assertEqual(record["days_remaining"], 50)

    def test_excel_datetime_loader_and_shared_expiry_parser_agree_with_overview(self):
        # The workbook loader converts Excel cells using str(value).strip().
        frame = pd.DataFrame([{"License Type": "Microsoft 365 Business Basic",
                               "Expiry Date": str(dt.datetime(2026, 11, 12)).strip()}])
        self.assertEqual(frame.loc[0, "Expiry Date"], "2026-11-12 00:00:00")
        overview = build_license_expiry_records({"Group Email": frame}, today=TODAY)[0]
        group_email_expiry = parse_expiration_date(frame.loc[0, "Expiry Date"])
        software_dashboard_expiry = parse_expiration_date(frame.loc[0, "Expiry Date"])
        self.assertEqual(overview["expiration_date"], group_email_expiry)
        self.assertEqual(overview["expiration_date"], software_dashboard_expiry)
        self.assertEqual(overview["expiration_date"].strftime("%d %b %Y"), "12 Nov 2026")
        self.assertEqual(overview["days_remaining"], (group_email_expiry - TODAY).days)
        self.assertEqual(overview["days_remaining"], (software_dashboard_expiry - TODAY).days)

    def test_date_only_inputs_and_ambiguous_text_follow_overview_contract(self):
        expected = dt.date(2026, 11, 12)
        for value in (dt.datetime(2026, 11, 12), pd.Timestamp("2026-11-12"),
                      expected, "2026-11-12", "2026-11-12 00:00:00", "12/11/2026"):
            with self.subTest(value=value):
                self.assertEqual(parse_expiration_date(value), expected)
        self.assertIsNone(parse_expiration_date(pd.NaT))

    def test_same_product_expiry_and_urgency_are_grouped(self):
        frame = pd.DataFrame(
            [{"License Plan": "App for business", "Expiry Date": "2026-11-12"} for _ in range(22)]
        )
        grouped = group_license_expiry_records(build_license_expiry_records({"Office 365": frame}, today=TODAY))
        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0]["record_count"], 22)

    def test_business_basic_without_expiry_is_informational_only(self):
        frame = pd.DataFrame([{"License Type": "Microsoft 365 Business Basic", "Expiry Date": None} for _ in range(90)])
        records = build_license_expiry_records({"Group Email": frame}, today=TODAY)
        grouped = group_license_expiry_records(records)
        self.assertEqual(grouped, [{
            "product": "Microsoft 365 Business Basic",
            "expiration_date": None,
            "days_remaining": None,
            "renewal_target": None,
            "urgency": "unavailable",
            "tone": "neutral",
            "status_label": "Expiry date unavailable",
            "source_category": "Group Email",
            "record_count": 90,
        }])
        self.assertEqual(summarize_license_expiry(records)["expiring_within_90"], 0)

    def test_rows_beyond_90_days_are_excluded(self):
        frame = pd.DataFrame([{"License Plan": "App for business", "Expiry Date": TODAY + dt.timedelta(days=91)}])
        self.assertEqual(build_license_expiry_records({"Office 365": frame}, today=TODAY), [])


if __name__ == "__main__":
    unittest.main()
