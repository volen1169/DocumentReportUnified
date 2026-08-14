"""Ink Stock business and data helpers."""

from services.microsoft_graph import (
    load_sp_data,
    sp_create_item,
    sp_update_item,
    sp_delete_item,
)

INK_STOCK_LIST   = "Ink Stock"        # ชื่อ SharePoint List สำหรับสต็อกหมึก
INK_HISTORY_LIST = "Ink History"      # ชื่อ SharePoint List สำหรับประวัติการเบิก
INK_LOW_THRESHOLD = 3                 # จำนวนต่ำสุดก่อนแจ้งเตือน (default)
INK_COLOR_OPTIONS = ["Black", "Cyan", "Magenta", "Yellow", "Color (Tri)", "Other"]
INK_STOCK_FIELDS = {
    "Title":         "รุ่นหมึก",
    "Color":         "สี",
    "Printer_Model": "รุ่นเครื่องพิมพ์",
    "Company":       "บริษัท",
    "Quantity":      "จำนวนคงเหลือ",
    "Min_Qty":       "จุดแจ้งเตือน",
    "Unit_Price":    "ราคา/ชิ้น (บาท)",
    "Notes":         "หมายเหตุ",
}
INK_HISTORY_FIELDS = {
    "Ink_Title":     "รุ่นหมึก",
    "Color":         "สี",
    "Qty_Change":    "จำนวน (+/-)",
    "Action":        "ประเภท",
    "Requester":     "ผู้เบิก/เพิ่ม",
    "Note":          "หมายเหตุ",
    "Timestamp":     "วันเวลา",
}

def ink_create(fields_dict):
    return sp_create_item(INK_STOCK_LIST, fields_dict)

def ink_update(item_id, fields_dict):
    return sp_update_item(INK_STOCK_LIST, item_id, fields_dict)

def ink_delete(item_id):
    return sp_delete_item(INK_STOCK_LIST, item_id)

def ink_adjust_quantity(item_id, current_qty, delta, title, color,
                        requester, note, action_label):
    """เพิ่ม/ลดสต็อกหมึกและบันทึก history ใน SharePoint"""
    new_qty = max(0, current_qty + delta)
    ok, _ = ink_update(item_id, {"Quantity": new_qty})
    if ok:
        from datetime import datetime
        history_fields = {
            "Ink_Title":  title,
            "Color":      color,
            "Qty_Change": delta,
            "Action":     action_label,
            "Requester":  requester,
            "Note":       note,
            "Timestamp":  datetime.now().strftime("%Y-%m-%d %H:%M"),
}
        sp_create_item(INK_HISTORY_LIST, history_fields)
        load_sp_data.clear()
    return ok, new_qty

