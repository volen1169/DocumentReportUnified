"""Safe Microsoft license renewal data for the Overview Dashboard."""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping

import pandas as pd


BANGKOK_TZ = dt.timezone(dt.timedelta(hours=7), name="Asia/Bangkok")

_PRODUCT_NAMES = {
    "app for business": "Microsoft 365 Apps for business",
    "microsoft 365 apps for business": "Microsoft 365 Apps for business",
    "microsoft 365 business basic": "Microsoft 365 Business Basic",
}

_PLAN_COLUMNS = ("License Plan", "Plan", "Product Name", "License Type")
_EXPIRY_COLUMNS = ("Expiry Date", "Expire Date", "License Expiry", "End Date")

# Explicitly limited output contract. Source rows can contain passwords and other
# credentials, so callers must never receive a copy of the original row.
SAFE_RECORD_FIELDS = frozenset(
    {
        "product",
        "expiration_date",
        "days_remaining",
        "renewal_target",
        "urgency",
        "tone",
        "status_label",
        "source_category",
    }
)


def _clean_text(value) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "nat"} else text


def _find_column(columns, candidates):
    lookup = {str(column).strip().lower(): column for column in columns}
    return next((lookup[name.lower()] for name in candidates if name.lower() in lookup), None)


def normalize_product_name(value) -> str | None:
    """Return a supported display name without guessing unknown products."""
    source = _clean_text(value)
    return _PRODUCT_NAMES.get(source.casefold())


def parse_expiration_date(value) -> dt.date | None:
    """Parse an Excel/pandas date as a date-only value."""
    if isinstance(value, (dt.datetime, dt.date, pd.Timestamp)) and not pd.isna(value):
        return value.date() if isinstance(value, (dt.datetime, pd.Timestamp)) else value
    text = _clean_text(value)
    if not text:
        return None
    # ISO values are year-first and must not be reinterpreted by dayfirst=True.
    is_iso = bool(re.match(r"^\d{4}-\d{2}-\d{2}(?:\D|$)", text))
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=not is_iso)
    return None if pd.isna(parsed) else parsed.date()


def classify_expiry(days_remaining: int | None) -> tuple[str, str, str] | None:
    """Return urgency, color tone, and user-facing label for an expiry."""
    if days_remaining is None:
        return "unavailable", "neutral", "Expiry date unavailable"
    if days_remaining < 0:
        return "expired", "expired", "Expired"
    if days_remaining <= 30:
        return "renewal_due", "red", "Renewal Due"
    if days_remaining <= 60:
        return "plan_renewal", "yellow", "Plan Renewal"
    if days_remaining <= 90:
        return "monitoring", "green", "Monitoring"
    return None


def build_license_expiry_records(
    software_datasets: Mapping[str, pd.DataFrame] | None,
    *,
    today: dt.date | None = None,
) -> list[dict]:
    """Build safe supported-product records for the Overview Dashboard.

    A populated plan/license-type field is the identity gate. This deliberately
    excludes spreadsheet rows kept alive only by formulas in calculated fields.
    Records beyond 90 days are excluded; missing-expiry supported products remain
    visible as informational items.
    """
    current_date = today or dt.datetime.now(BANGKOK_TZ).date()
    safe_records = []

    for category, frame in (software_datasets or {}).items():
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            continue
        plan_column = _find_column(frame.columns, _PLAN_COLUMNS)
        if plan_column is None:
            continue
        expiry_column = _find_column(frame.columns, _EXPIRY_COLUMNS)

        for _, row in frame.iterrows():
            product = normalize_product_name(row.get(plan_column))
            if product is None:
                continue
            expiration_date = parse_expiration_date(row.get(expiry_column)) if expiry_column else None
            days_remaining = (expiration_date - current_date).days if expiration_date else None
            classification = classify_expiry(days_remaining)
            if classification is None:
                continue
            urgency, tone, status_label = classification
            safe_records.append(
                {
                    "product": product,
                    "expiration_date": expiration_date,
                    "days_remaining": days_remaining,
                    "renewal_target": expiration_date - dt.timedelta(days=30) if expiration_date else None,
                    "urgency": urgency,
                    "tone": tone,
                    "status_label": status_label,
                    "source_category": str(category),
                }
            )

    return safe_records


def group_license_expiry_records(records: list[dict]) -> list[dict]:
    """Group identical product/expiry/urgency records for compact rendering."""
    grouped = {}
    for record in records:
        safe = {field: record.get(field) for field in SAFE_RECORD_FIELDS}
        key = (safe["product"], safe["expiration_date"], safe["urgency"])
        if key not in grouped:
            grouped[key] = {**safe, "record_count": 0}
        grouped[key]["record_count"] += 1

    order = {"renewal_due": 0, "plan_renewal": 1, "monitoring": 2, "expired": 3, "unavailable": 4}
    return sorted(
        grouped.values(),
        key=lambda item: (
            order.get(item["urgency"], 9),
            item["days_remaining"] if item["days_remaining"] is not None else 10**9,
            item["product"],
        ),
    )


def summarize_license_expiry(records: list[dict]) -> dict[str, int]:
    """Return record counts, not purchased-seat counts."""
    return {
        "expiring_within_90": sum(
            1 for record in records if record.get("days_remaining") is not None and 0 <= record["days_remaining"] <= 90
        ),
        "renewal_due_within_30": sum(
            1 for record in records if record.get("days_remaining") is not None and 0 <= record["days_remaining"] <= 30
        ),
        "expired": sum(1 for record in records if record.get("urgency") == "expired"),
    }
