"""Display formatting helpers."""

from services.ink_stock import INK_LOW_THRESHOLD

def _hw_badge(status):
    cls = {"Active":"badge-active","Inactive":"badge-inactive","Spare":"badge-spare","Repair":"badge-repair"}.get(status,"badge-default")
    return f'<span class="badge {cls}">{status or "โ€”"}</span>' if status else ''

def get_sheet_icon(sheet_name):
    icon_map = {"server": "🖥️", "network": "🌐", "sql": "🗄️",
                "software": "📦", "license": "📦", "domain": "🌍",
                "email": "📧", "mail": "📧", "internet": "📡",
                "wifi": "📶", "vpn": "🔒", "firewall": "🔥"}
    s = sheet_name.lower()
    return next((v for k, v in icon_map.items() if k in s), "🔑")

def is_secret_field(col_name):
    return any(k in str(col_name).lower() for k in ['pass', 'pwd', 'secret', 'key', 'รหัส', 'token'])

def ink_stock_color_badge(color):
    color_map = {
        "Black":      ("#222", "#fff"),
        "Cyan":       ("#00b4d8", "#fff"),
        "Magenta":    ("#c77dff", "#fff"),
        "Yellow":     ("#f9c74f", "#333"),
        "Color (Tri)":("#43aa8b", "#fff"),
        "Other":      ("#adb5bd", "#333"),
}
    bg, fg = color_map.get(color, ("#adb5bd", "#333"))
    return f"<span style='background:{bg};color:{fg};padding:3px 12px;border-radius:12px;font-size:0.82em;font-weight:bold;'>{color}</span>"

def ink_qty_badge(qty, min_qty):
    qty = int(qty) if str(qty).isdigit() else 0
    min_qty = int(min_qty) if str(min_qty).isdigit() else INK_LOW_THRESHOLD
    if qty == 0:
        return f"<span style='background:#dc3545;color:#fff;padding:3px 14px;border-radius:12px;font-weight:bold;font-size:0.95em;'>หมด ❌</span>"
    elif qty <= min_qty:
        return f"<span style='background:#fd7e14;color:#fff;padding:3px 14px;border-radius:12px;font-weight:bold;font-size:0.95em;'>⚠️ เหลือ {qty}</span>"
    return f"<span style='background:#198754;color:#fff;padding:3px 14px;border-radius:12px;font-weight:bold;font-size:0.95em;'>โ… {qty}</span>"
