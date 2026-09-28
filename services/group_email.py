"""Group E-mail account identity and optional device count rules."""

import math
import re


REQUIRED_HEADERS = ("Email", "Assigned Users", "Login Devices")


def email_key(value):
    if value is None:
        return ""
    text = str(value).strip()
    if text.casefold() in ("", "nan", "none", "nat", "<na>", "-"):
        return ""
    return text.casefold()


def account_counts(frame):
    """Raw rows, populated e-mail rows and distinct mailbox identities."""
    if frame is None or "Email" not in frame.columns:
        return (0 if frame is None else len(frame), 0, 0)
    keys = [email_key(value) for value in frame["Email"]]
    populated = [key for key in keys if key]
    return len(frame), len(populated), len(set(populated))


def login_devices(value):
    """Return an optional non-negative integer; reject fractional/text counts."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise ValueError("Login Devices ต้องเป็นจำนวนเต็มตั้งแต่ 0 ขึ้นไป หรือเว้นว่าง")
    if isinstance(value, int):
        result = value
    elif isinstance(value, float) and math.isfinite(value) and value.is_integer():
        result = int(value)
    elif isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip()):
        result = int(value.strip())
    else:
        raise ValueError("Login Devices ต้องเป็นจำนวนเต็มตั้งแต่ 0 ขึ้นไป หรือเว้นว่าง")
    if result < 0:
        raise ValueError("Login Devices ต้องเป็นจำนวนเต็มตั้งแต่ 0 ขึ้นไป หรือเว้นว่าง")
    return result


def group_email_payload(headers, values, existing_emails=(), original_email=None):
    """Validate exact worksheet keys without changing unrelated field values."""
    missing = [header for header in REQUIRED_HEADERS if header not in headers]
    if missing:
        raise ValueError("Group E-mail schema missing: " + ", ".join(missing))
    key = email_key(values.get("Email"))
    if not key:
        raise ValueError("กรุณากรอก Email ของ account")
    old_key = email_key(original_email)
    if key != old_key and key in {email_key(value) for value in existing_emails}:
        raise ValueError("Email นี้มีรายการอยู่แล้ว: 1 Email ต้องมี 1 record")
    payload = {header: values.get(header) for header in headers}
    payload["Login Devices"] = login_devices(values.get("Login Devices"))
    return payload
