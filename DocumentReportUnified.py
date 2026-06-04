import streamlit as st
import pandas as pd
import paramiko
import re
import textwrap
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import io
import msal
import requests
import urllib3
import extra_streamlit_components as stx
import plotly.express as px
from openpyxl import load_workbook
from copy import copy

# --- 1. CONFIGURATION ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# SharePoint Config
TENANT_ID = st.secrets["TENANT_ID"]
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
SHAREPOINT_DOMAIN = "optimalcoth.sharepoint.com"
SITE_NAME = "InformationTechnology"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
GRAPH_URL = "https://graph.microsoft.com/v1.0"

# NAS Config
NAS_IP = st.secrets.get("NAS_IP", "")
NAS_PORT = 22        # SSH port (ปกติคือ 22 หรือ 2222 — ตรวจสอบใน DSM > Terminal & SNMP)
SSH_USER = st.secrets.get("SSH_USER", "")
SSH_PWD = st.secrets.get("SSH_PWD", "")
MAX_THREADS = 6
SYNOACL_PATH = "/usr/syno/bin/synoacltool"

# Password File Config
SHAREPOINT_FOLDER = "Update IT documents"
PASSWORD_FILE_NAME = "Password.xlsx"

# ✅ Admin List — เพิ่ม/ลด email ได้ที่นี่
ADMIN_EMAILS = [
    "itsupport@poonyaruk.co.th",
    "IT_Network@poonyaruk.co.th",
    "Teerapat.Po@optimal.co.th",

]

# Field mapping สำหรับ Computer Asset
COMPUTER_FIELDS = {
    "field_1": "บริษัท",
    "field_3": "ชื่อพนักงาน",
    "field_6": "Hostname",
    "field_7": "Model",
    "field_8": "Serial No.",
    "field_13": "RAM",
    "field_14": "Storage Type",
    "field_15": "Storage C:",
    "field_16": "Storage D:",
    "Status": "Status",
}

# Field mapping สำหรับ Monitor
MONITOR_FIELDS = {
    "field_1": "บริษัท",
    "field_3": "ชื่อพนักงาน",
    "field_2": "Brand/Model",
    "field_4": "Serial No.",
    "Status": "Status",
}

# Field mapping สำหรับ Printer
PRINTER_FIELDS = {
    "Company": "บริษัท",
    "User": "User",
    "Brand_x0020__x002f__x0020_Model": "Brand/Model",
    "S_x002f_N_x0020_No_x002e_": "Serial No.",
    "field_3": "IP Address",
}

COMPANY_OPTIONS = ["OPT", "SWI", "PRP", "PLC", "EGI", "THK"]
STATUS_OPTIONS = ["Active", "Inactive", "Spare", "Repair"]

# Field mapping สำหรับ Ink Stock
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

# --- 2. AUTH HELPERS ---
def get_manager():
    if "cookie_manager" not in st.session_state:
        st.session_state["cookie_manager"] = stx.CookieManager(key="cookie_mgr_singleton")
    return st.session_state["cookie_manager"]

def is_admin(username: str) -> bool:
    if not username:
        return False
    return any(username.lower() in email.lower() or email.lower() in username.lower()
               for email in ADMIN_EMAILS)

@st.cache_data(ttl=3600)
def get_access_token():
    app = msal.ConfidentialClientApplication(CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET)
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    return result.get("access_token")

def check_ms_login(username, password):
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
    result = app.acquire_token_by_username_password(username, password, scopes=["User.Read", "email"])
    if "access_token" in result:
        claims = result.get("id_token_claims", {})
        name = claims.get("name", username)
        email = claims.get("preferred_username", username)
        return True, name, email
    return False, result.get("error_description", "ล็อกอินไม่สำเร็จ"), ""

# --- 3. SHAREPOINT LIST CRUD ---
@st.cache_data(ttl=3600)
def get_sp_site_id():
    token = get_access_token()
    headers = {'Authorization': f'Bearer {token}'}
    res = requests.get(f"{GRAPH_URL}/sites/{SHAREPOINT_DOMAIN}:/sites/{SITE_NAME}", headers=headers).json()
    return res.get('id')

@st.cache_data(ttl=3600)
def get_sp_list_id(list_name):
    token = get_access_token()
    headers = {'Authorization': f'Bearer {token}'}
    site_id = get_sp_site_id()
    res = requests.get(f"{GRAPH_URL}/sites/{site_id}/lists", headers=headers).json()
    target = next((l for l in res.get('value', []) if l['displayName'] == list_name), None)
    return target['id'] if target else None

@st.cache_data(ttl=3600)
def load_sp_data(target_display_name):
    token = get_access_token()
    headers = {'Authorization': f'Bearer {token}'}
    try:
        site_id = get_sp_site_id()
        list_id = get_sp_list_id(target_display_name)
        if list_id:
            items_res = requests.get(
                f"{GRAPH_URL}/sites/{site_id}/lists/{list_id}/items?expand=fields&$top=999",
                headers=headers
            ).json()
            rows = []
            for item in items_res.get('value', []):
                fields = item['fields']
                fields['_item_id'] = item['id']  # เก็บ item ID สำหรับ CRUD
                rows.append(fields)
            return pd.DataFrame(rows)
    except Exception as e:
        print(f"Error fetching SP data: {e}")
    return pd.DataFrame()

def sp_create_item(list_name, fields_dict):
    token = get_access_token()
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    site_id = get_sp_site_id()
    list_id = get_sp_list_id(list_name)
    res = requests.post(
        f"{GRAPH_URL}/sites/{site_id}/lists/{list_id}/items",
        headers=headers,
        json= {"fields": fields_dict}
    )
    return res.status_code in (200, 201), res.json()

def sp_update_item(list_name, item_id, fields_dict):
    token = get_access_token()
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    site_id = get_sp_site_id()
    list_id = get_sp_list_id(list_name)
    res = requests.patch(
        f"{GRAPH_URL}/sites/{site_id}/lists/{list_id}/items/{item_id}/fields",
        headers=headers,
        json=fields_dict
    )
    return res.status_code in (200, 204), res.json() if res.content else {}

def sp_delete_item(list_name, item_id):
    token = get_access_token()
    headers = {'Authorization': f'Bearer {token}'}
    site_id = get_sp_site_id()
    list_id = get_sp_list_id(list_name)
    res = requests.delete(
        f"{GRAPH_URL}/sites/{site_id}/lists/{list_id}/items/{item_id}",
        headers=headers
    )
    return res.status_code in (200, 204, 200)

def clear_sp_cache():
    load_sp_data.clear()

# --- 3b. INK STOCK HELPERS ---
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

# --- 4. PASSWORD EXCEL CRUD ---
def parse_password_sheet(ws):
    all_rows = list(ws.iter_rows(values_only=True))
    if not all_rows:
        return pd.DataFrame()
    raw_headers = list(all_rows[0])
    valid_col_idx = [i for i, h in enumerate(raw_headers) if h is not None]
    headers = [str(raw_headers[i]).strip() for i in valid_col_idx]
    data = []
    for row in all_rows[1:]:
        vals = [row[i] if i < len(row) else None for i in valid_col_idx]
        non_null = [v for v in vals if v is not None and str(v).strip() != '']
        if non_null:
            data.append([str(v).strip() if v is not None else None for v in vals])
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data, columns=headers)

@st.cache_data(ttl=1800)
def load_password_excel():
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    try:
        site_id = get_sp_site_id()
        drive_res = requests.get(f"{GRAPH_URL}/sites/{site_id}/drive", headers=headers).json()
        drive_id = drive_res.get("id")
        file_url = f"{GRAPH_URL}/drives/{drive_id}/root:/{SHAREPOINT_FOLDER}/{PASSWORD_FILE_NAME}:/content"
        file_res = requests.get(file_url, headers=headers)
        if file_res.status_code == 200:
            wb = load_workbook(io.BytesIO(file_res.content))
            sheets = {}
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                df = parse_password_sheet(ws)
                if not df.empty:
                    sheets[sheet_name] = df
            return sheets, drive_id
        return {"_error": f"HTTP {file_res.status_code} - ไม่พบไฟล์ที่ path: {SHAREPOINT_FOLDER}/{PASSWORD_FILE_NAME}", "_url": file_url}, drive_id
    except Exception as e:
        return {"_error": str(e)}, None

def upload_password_excel(drive_id, sheets_dict):
    """
    สร้าง Excel ใหม่จาก sheets_dict แล้วอัปโหลดทับไฟล์เดิมบน SharePoint
    """
    token = get_access_token()
    headers_auth = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/octet-stream'}

    # ดาวน์โหลดไฟล์เดิมมาก่อนเพื่อรักษา format
    site_id = get_sp_site_id()
    dl_headers = {'Authorization': f'Bearer {token}'}
    file_res = requests.get(
        f"{GRAPH_URL}/drives/{drive_id}/root:/{SHAREPOINT_FOLDER}/{PASSWORD_FILE_NAME}:/content",
        headers=dl_headers
    )
    wb = load_workbook(io.BytesIO(file_res.content))

    for sheet_name, df in sheets_dict.items():
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        # ลบ data rows เดิม (เก็บ header row 1)
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.value = None

        # เขียนข้อมูลใหม่
        for r_idx, (_, row) in enumerate(df.iterrows(), start=2):
            for c_idx, val in enumerate(row, start=1):
                ws.cell(row=r_idx, column=c_idx, value=val if val not in ('None', 'nan', '') else None)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    upload_res = requests.put(
        f"{GRAPH_URL}/drives/{drive_id}/root:/{SHAREPOINT_FOLDER}/{PASSWORD_FILE_NAME}:/content",
        headers=headers_auth,
        data=output.getvalue()
    )
    return upload_res.status_code in (200, 201)

# --- 5. SSH / NAS ---
def create_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(NAS_IP, port=NAS_PORT, username=SSH_USER, password=SSH_PWD, timeout=10)
    return ssh

def run_command(ssh, cmd):
    full_cmd = f"sudo -S {cmd}"
    stdin, stdout, stderr = ssh.exec_command(full_cmd)
    stdin.write(SSH_PWD + "\n")
    stdin.flush()
    return stdout.read().decode('utf-8', errors='ignore'), stderr.read().decode('utf-8', errors='ignore')

def check_synoacl():
    try:
        ssh = create_ssh()
        output, _ = run_command(ssh, f"ls {SYNOACL_PATH}")
        ssh.close()
        return SYNOACL_PATH in output
    except Exception as e:
        st.warning(f"⚠️ ไม่สามารถเชื่อมต่อ NAS ได้: {e}")
        return False

def get_shares():
    try:
        ssh = create_ssh()
        output, _ = run_command(ssh, "ls /volume1")
        ssh.close()
        return [l.strip() for l in output.splitlines() if l.strip() and not l.startswith("@")]
    except:
        return []

def fetch_acl(share, employee_list):
    try:
        ssh = create_ssh()
        raw, _ = run_command(ssh, f"{SYNOACL_PATH} -get /volume1/{share}")
        ssh.close()
        if not raw:
            return share, [], []
        acl_entries = []
        for line in raw.splitlines():
            if "allow" in line or "deny" in line:
                parts = line.split(':')
                if len(parts) >= 4:
                    readable_perm = "Read/Write" if 'w' in parts[3] else "Read"
                    acl_entries.append(f"{parts[0]}:{parts[1]} ({readable_perm})")
        acl_tags = list(set(acl_entries))
        matched_employees = []
        for entry in acl_tags:
            match = re.search(r"^(.*?)\s*\((Read(?:/Write)?)\)", entry)
            if not match:
                continue
            clean_entity = re.sub(r'^\[\d+\]\s*(user|group):\s*', '', match.group(1).strip())
            clean_entity = clean_entity.replace('OPTIMALGROUP\\', '').strip()
            if not clean_entity:
                continue
            for emp in employee_list:
                if clean_entity.lower() in emp.lower() or emp.lower() in clean_entity.lower():
                    matched_employees.append(f"{emp} ({match.group(2).strip()})")
        return share, acl_tags, list(set(matched_employees))
    except Exception as e:
        return share, [], []

@st.cache_data(ttl=1800)
def load_nas_data():
    if not check_synoacl():
        return None
    df_emp = load_sp_data("Employees")
    employees = df_emp['field_3'].dropna().unique().tolist() if not df_emp.empty and 'field_3' in df_emp.columns else []
    shares = get_shares()
    data = []
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = [executor.submit(fetch_acl, s, employees) for s in shares]
        for future in as_completed(futures):
            share, tags, matched_emps = future.result()
            data.append({"Share": share, "ACL Tags (Raw)": ", ".join(sorted(tags)), "Matched Employees": ", ".join(sorted(matched_emps))})
    return pd.DataFrame(data).sort_values("Share")

# --- 6. CARD RENDER ---
def _hw_badge(status):
    cls = {"Active":"badge-active","Inactive":"badge-inactive","Spare":"badge-spare","Repair":"badge-repair"}.get(status,"badge-default")
    return f'<span class="badge {cls}">{status or "—"}</span>' if status else ''

def render_card_computer(row, key, admin_mode):
    status = row.get('Status', '')
    with st.container():
        st.markdown(f"""
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px;">
            <div>
                <div class="hw-card-title">👤 {row.get('field_3','N/A')}</div>
                <div class="hw-card-sub">🏢 {row.get('field_1','-')}</div>
            </div>
            {_hw_badge(status)}
        </div>
        <div class="hw-field"><strong>💻 Hostname</strong>&nbsp;&nbsp;{row.get('field_6','-')}</div>
        <div class="hw-field"><strong>🏷️ Model</strong>&nbsp;&nbsp;{row.get('field_7','-')}</div>
        <div class="hw-field"><strong>💾 RAM</strong>&nbsp;&nbsp;{row.get('field_13','-')}</div>
        """, unsafe_allow_html=True)
        if admin_mode:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔍 ดูข้อมูล", key=f"comp_view_{key}", use_container_width=True):
                    show_pop_computer(row.to_dict(), admin_mode=True)
            with c2:
                if st.button("✏️ แก้ไข", key=f"comp_edit_{key}", use_container_width=True):
                    st.session_state[f"edit_computer_{key}"] = True
                    st.rerun()
        else:
            st.caption("🔒 ข้อมูลเพิ่มเติมและการแก้ไขเฉพาะผู้ดูแลระบบ")

def render_card_monitor(row, key, admin_mode):
    status = row.get('Status', '')
    with st.container():
        st.markdown(f"""
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px;">
            <div>
                <div class="hw-card-title">👤 {row.get('field_3','N/A')}</div>
                <div class="hw-card-sub">🏢 {row.get('field_1','-')}</div>
            </div>
            {_hw_badge(status)}
        </div>
        <div class="hw-field"><strong>🖥️ Model</strong>&nbsp;&nbsp;{row.get('field_2','-')}</div>
        {f"<div class=\"hw-field\"><strong>🔢 Serial No.</strong>&nbsp;&nbsp;{row.get('field_4','-')}</div>" if admin_mode else ""}
        """, unsafe_allow_html=True)
        if admin_mode:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔍 ดูข้อมูล", key=f"mon_view_{key}", use_container_width=True):
                    show_pop_monitor(row.to_dict(), admin_mode=True)
            with c2:
                if st.button("✏️ แก้ไข", key=f"mon_edit_{key}", use_container_width=True):
                    st.session_state[f"edit_monitor_{key}"] = True
                    st.rerun()
        else:
            st.caption("🔒 ดูข้อมูลเชิงลึกและแก้ไขเฉพาะผู้ดูแลระบบ")

def render_card_printer(row, key, admin_mode):
    with st.container():
        st.markdown(f"""
        <div style="margin-bottom:6px;">
            <div class="hw-card-title">🖨️ {row.get('Brand_x0020__x002f__x0020_Model','Printer')}</div>
            <div class="hw-card-sub">🏢 {row.get('field_1','-')}</div>
        </div>
        <div class="hw-field"><strong>👤 User</strong>&nbsp;&nbsp;{row.get('User','-')}</div>
        {f"<div class=\"hw-field\"><strong>🔢 Serial No.</strong>&nbsp;&nbsp;{row.get('S_x002f_N_x0020_No_x002e_','-')}</div>" if admin_mode else ""}
        {f"<div class=\"hw-field\"><strong>🌐 IP</strong>&nbsp;&nbsp;{row.get('field_3','-')}</div>" if admin_mode else ""}
        """, unsafe_allow_html=True)
        if admin_mode:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔍 ดูข้อมูล", key=f"prn_view_{key}", use_container_width=True):
                    show_pop_printer(row.to_dict(), admin_mode=True)
            with c2:
                if st.button("✏️ แก้ไข", key=f"prn_edit_{key}", use_container_width=True):
                    st.session_state[f"edit_printer_{key}"] = True
                    st.rerun()
        else:
            st.caption("🔒 ดูข้อมูลเชิงลึกและแก้ไขเฉพาะผู้ดูแลระบบ")

# --- 7. DIALOG: VIEW ---
@st.dialog("📋 รายละเอียด Computer")
def show_pop_computer(data, admin_mode=False):
    st.markdown(f"### 💻 {data.get('field_7', 'Computer')}")
    c1, c2 = st.columns(2)
    with c1:
        st.write(f"**👤 พนักงาน:** {data.get('field_3', '-')}")
        st.write(f"**🏢 บริษัท:** {data.get('field_1', '-')}")
        st.write(f"**💻 Hostname:** {data.get('field_6', '-')}")
    with c2:
        if admin_mode:
            st.write(f"**🔢 Serial No:** {data.get('field_8', '-')}")
        else:
            st.write("**🔢 Serial No:** 🔒 ซ่อนสำหรับผู้ใช้ทั่วไป")
        st.write(f"**✳️ สถานะ:** {data.get('Status', '-')}")
        st.write(f"**💾 RAM:** {data.get('field_13', '-')}")
        st.write(f"**💿 Storage C:** {data.get('field_15', '-')}  D: {data.get('field_16', '-')}")
    with st.expander("📊 ดูข้อมูลดิบ"):
        st.json(data)

@st.dialog("📋 รายละเอียด Monitor")
def show_pop_monitor(data, admin_mode=False):
    st.markdown(f"### 🖥️ {data.get('field_2', 'Monitor')}")
    st.write(f"**👤 พนักงาน:** {data.get('field_3', '-')}")
    st.write(f"**🏢 บริษัท:** {data.get('field_1', '-')}")
    if admin_mode:
        st.write(f"**🔢 Serial No.:** {data.get('field_4', '-')}")
    else:
        st.write("**🔢 Serial No.:** 🔒 ซ่อนสำหรับผู้ใช้ทั่วไป")
    st.write(f"**✅ สถานะ:** {data.get('Status', '-')}")
    with st.expander("📊 ดูข้อมูลดิบ"):
        st.json(data)

@st.dialog("📋 รายละเอียด Printer")
def show_pop_printer(data, admin_mode=False):
    st.markdown(f"### 🖨️ {data.get('field_2', 'Printer')}")
    st.write(f"**🏢 บริษัท:** {data.get('field_1', '-')}")
    st.write(f"**👤 User:** {data.get('User', '-')}")
    if admin_mode:
        st.write(f"**🔢 Serial No.:** {data.get('S_x002f_N_x0020_No_x002e_', '-')}")
        st.write(f"**🌐 IP Address:** {data.get('field_3', '-')}")
    else:
        st.write("**🔢 Serial No.:** 🔒 ซ่อนสำหรับผู้ใช้ทั่วไป")
        st.write("**🌐 IP Address:** 🔒 ซ่อนสำหรับผู้ใช้ทั่วไป")
    with st.expander("📊 ดูข้อมูลดิบ"):
        st.json(data)

# --- 8. DIALOG: EDIT HARDWARE ---
@st.dialog("✏️ แก้ไข Computer Asset")
def edit_computer_dialog(row, list_name):
    st.markdown(f"### ✏️ แก้ไข: {row.get('field_3', '')}")
    item_id = row.get('_item_id')
    company = st.selectbox("🏢 บริษัท", COMPANY_OPTIONS, index=COMPANY_OPTIONS.index(row.get('field_1', 'OPT')) if row.get('field_1') in COMPANY_OPTIONS else 0)
    emp_name = st.text_input("👤 ชื่อพนักงาน", value=row.get('field_3', ''))
    hostname = st.text_input("💻 Hostname", value=row.get('field_6', ''))
    model = st.text_input("🏷️ Model", value=row.get('field_7', ''))
    serial = st.text_input("🔢 Serial No.", value=row.get('field_8', ''))
    ram = st.text_input("💾 RAM", value=row.get('field_13', ''))
    storage_type = st.text_input("💿 Storage Type", value=row.get('field_14', ''))
    storage_c = st.text_input("💿 Storage C:", value=row.get('field_15', ''))
    storage_d = st.text_input("💿 Storage D:", value=row.get('field_16', ''))
    status = st.selectbox("✳️ Status", STATUS_OPTIONS, index=STATUS_OPTIONS.index(row.get('Status', 'Active')) if row.get('Status') in STATUS_OPTIONS else 0)
    col_save, col_del = st.columns(2)
    with col_save:
        if st.button("💾 บันทึก", use_container_width=True, type="primary"):
            fields = {"field_1": company, "field_3": emp_name, "field_6": hostname,
                      "field_7": model, "field_8": serial, "field_13": ram,
                      "field_14": storage_type, "field_15": storage_c,
                      "field_16": storage_d, "Status": status}
            ok, res_data = sp_update_item(list_name, item_id, fields)
            if ok:
                st.success("✅ บันทึกสำเร็จ")
                clear_sp_cache()
                st.rerun()
            else:
                err_msg = res_data.get("error", {}).get("message", str(res_data)) if isinstance(res_data, dict) else str(res_data)
            st.error(f"❌ บันทึกไม่สำเร็จ: {err_msg}")
    with col_del:
        if st.button("🗑️ ลบรายการนี้", use_container_width=True):
            st.session_state['confirm_delete'] = item_id
    if st.session_state.get('confirm_delete') == item_id:
        st.warning("⚠️ ยืนยันการลบ?")
        if st.button("✅ ยืนยันลบ", type="primary"):
            ok = sp_delete_item(list_name, item_id)
            if ok:
                st.success("✅ ลบสำเร็จ")
                st.session_state.pop('confirm_delete', None)
                clear_sp_cache()
                st.rerun()
            else:
                st.error("❌ ลบไม่สำเร็จ")

@st.dialog("✏️ แก้ไข Monitor")
def edit_monitor_dialog(row, list_name):
    st.markdown(f"### ✏️ แก้ไข: {row.get('field_2', '')}")
    item_id = row.get('_item_id')
    company = st.selectbox("🏢 บริษัท", COMPANY_OPTIONS, index=COMPANY_OPTIONS.index(row.get('field_1', 'OPT')) if row.get('field_1') in COMPANY_OPTIONS else 0)
    emp_name = st.text_input("👤 ชื่อพนักงาน", value=row.get('field_3', ''))
    model = st.text_input("🏷️ Brand/Model", value=row.get('field_2', ''))
    serial = st.text_input("🔢 Serial No.", value=row.get('field_4', ''))
    status = st.selectbox("✅ Status", STATUS_OPTIONS, index=STATUS_OPTIONS.index(row.get('Status', 'Active')) if row.get('Status') in STATUS_OPTIONS else 0)
    col_save, col_del = st.columns(2)
    with col_save:
        if st.button("💾 บันทึก", use_container_width=True, type="primary"):
            fields = {"field_1": company, "field_3": emp_name, "field_2": model, "field_4": serial, "Status": status}
            ok, res_data = sp_update_item(list_name, item_id, fields)
            if ok:
                st.success("✅ บันทึกสำเร็จ")
                clear_sp_cache()
                st.rerun()
            else:
                err_msg = res_data.get("error", {}).get("message", str(res_data)) if isinstance(res_data, dict) else str(res_data)
            st.error(f"❌ บันทึกไม่สำเร็จ: {err_msg}")
    with col_del:
        if st.button("🗑️ ลบรายการนี้", use_container_width=True):
            st.session_state['confirm_delete'] = item_id
    if st.session_state.get('confirm_delete') == item_id:
        st.warning("⚠️ ยืนยันการลบ?")
        if st.button("✅ ยืนยันลบ", type="primary"):
            ok = sp_delete_item(list_name, item_id)
            if ok:
                st.success("✅ ลบสำเร็จ")
                st.session_state.pop('confirm_delete', None)
                clear_sp_cache()
                st.rerun()
            else:
                st.error("❌ ลบไม่สำเร็จ")

@st.dialog("✏️ แก้ไข Printer")
def edit_printer_dialog(row, list_name):
    st.markdown(f"### ✏️ แก้ไข Printer")
    item_id = row.get('_item_id')
    company = st.selectbox("🏢 บริษัท", COMPANY_OPTIONS, index=COMPANY_OPTIONS.index(row.get('field_1', 'OPT')) if row.get('field_1') in COMPANY_OPTIONS else 0)
    user = st.text_input("👤 User", value=row.get('User', ''))
    model = st.text_input("🏷️ Brand/Model", value=row.get('Brand_x0020__x002f__x0020_Model', ''))
    serial = st.text_input("🔢 Serial No.", value=row.get('S_x002f_N_x0020_No_x002e_', ''))
    ip = st.text_input("🌐 IP Address", value=row.get('field_3', ''))
    col_save, col_del = st.columns(2)
    with col_save:
        if st.button("💾 บันทึก", use_container_width=True, type="primary"):
            fields = {"field_1": company, "User": user,
                      "Brand_x0020__x002f__x0020_Model": model,
                      "S_x002f_N_x0020_No_x002e_": serial, "field_3": ip}
            ok, res_data = sp_update_item(list_name, item_id, fields)
            if ok:
                st.success("✅ บันทึกสำเร็จ")
                clear_sp_cache()
                st.rerun()
            else:
                err_msg = res_data.get("error", {}).get("message", str(res_data)) if isinstance(res_data, dict) else str(res_data)
            st.error(f"❌ บันทึกไม่สำเร็จ: {err_msg}")
    with col_del:
        if st.button("🗑️ ลบรายการนี้", use_container_width=True):
            st.session_state['confirm_delete'] = item_id
    if st.session_state.get('confirm_delete') == item_id:
        st.warning("⚠️ ยืนยันการลบ?")
        if st.button("✅ ยืนยันลบ", type="primary"):
            ok = sp_delete_item(list_name, item_id)
            if ok:
                st.success("✅ ลบสำเร็จ")
                st.session_state.pop('confirm_delete', None)
                clear_sp_cache()
                st.rerun()
            else:
                st.error("❌ ลบไม่สำเร็จ")

# --- 9. DIALOG: ADD HARDWARE ---
@st.dialog("➕ เพิ่ม Computer Asset")
def add_computer_dialog(list_name):
    st.markdown("### ➕ เพิ่มอุปกรณ์ใหม่")
    company = st.selectbox("🏢 บริษัท", COMPANY_OPTIONS)
    emp_name = st.text_input("👤 ชื่อพนักงาน")
    hostname = st.text_input("💻 Hostname")
    model = st.text_input("🏷️ Model")
    serial = st.text_input("🔢 Serial No.")
    ram = st.text_input("💾 RAM")
    storage_type = st.text_input("💿 Storage Type")
    storage_c = st.text_input("💿 Storage C:")
    storage_d = st.text_input("💿 Storage D:")
    status = st.selectbox("✳️ Status", STATUS_OPTIONS)
    if st.button("💾 บันทึก", use_container_width=True, type="primary"):
        fields = {"field_1": company, "field_3": emp_name, "field_6": hostname,
                  "field_7": model, "field_8": serial, "field_13": ram,
                  "field_14": storage_type, "field_15": storage_c,
                  "field_16": storage_d, "Status": status}
        ok, res_data = sp_create_item(list_name, fields)
        if ok:
            st.success("✅ เพิ่มสำเร็จ")
            clear_sp_cache()
            st.rerun()
        else:
            err_msg = res_data.get("error", {}).get("message", str(res_data)) if isinstance(res_data, dict) else str(res_data)
            st.error(f"❌ เพิ่มไม่สำเร็จ: {err_msg}")

@st.dialog("➕ เพิ่ม Monitor")
def add_monitor_dialog(list_name):
    st.markdown("### ➕ เพิ่ม Monitor ใหม่")
    company = st.selectbox("🏢 บริษัท", COMPANY_OPTIONS)
    emp_name = st.text_input("👤 ชื่อพนักงาน")
    model = st.text_input("🏷️ Brand/Model")
    serial = st.text_input("🔢 Serial No.")
    status = st.selectbox("✅ Status", STATUS_OPTIONS)
    if st.button("💾 บันทึก", use_container_width=True, type="primary"):
        fields = {"field_1": company, "field_3": emp_name, "field_2": model, "field_4": serial, "Status": status}
        ok, res_data = sp_create_item(list_name, fields)
        if ok:
            st.success("✅ เพิ่มสำเร็จ")
            clear_sp_cache()
            st.rerun()
        else:
            err_msg = res_data.get("error", {}).get("message", str(res_data)) if isinstance(res_data, dict) else str(res_data)
            st.error(f"❌ เพิ่มไม่สำเร็จ: {err_msg}")

@st.dialog("➕ เพิ่ม Printer")
def add_printer_dialog(list_name):
    st.markdown("### ➕ เพิ่ม Printer ใหม่")
    company = st.selectbox("🏢 บริษัท", COMPANY_OPTIONS)
    user = st.text_input("👤 User")
    model = st.text_input("🏷️ Brand/Model")
    serial = st.text_input("🔢 Serial No.")
    ip = st.text_input("🌐 IP Address")
    if st.button("💾 บันทึก", use_container_width=True, type="primary"):
        fields = {"field_1": company, "User": user,
                  "Brand_x0020__x002f__x0020_Model": model,
                  "S_x002f_N_x0020_No_x002e_": serial, "field_3": ip}
        ok, res_data = sp_create_item(list_name, fields)
        if ok:
            st.success("✅ เพิ่มสำเร็จ")
            clear_sp_cache()
            st.rerun()
        else:
            err_msg = res_data.get("error", {}).get("message", str(res_data)) if isinstance(res_data, dict) else str(res_data)
            st.error(f"❌ เพิ่มไม่สำเร็จ: {err_msg}")

# --- 10. PASSWORD CARD + EDIT ---
def get_sheet_icon(sheet_name):
    icon_map = {"server": "🖥️", "network": "🌐", "sql": "🗄️",
                "software": "📦", "license": "📦", "domain": "🌍",
                "email": "📧", "mail": "📧", "internet": "📡",
                "wifi": "📶", "vpn": "🔒", "firewall": "🔥"}
    s = sheet_name.lower()
    return next((v for k, v in icon_map.items() if k in s), "🔑")

def is_secret_field(col_name):
    return any(k in str(col_name).lower() for k in ['pass', 'pwd', 'secret', 'key', 'รหัส', 'token'])

def render_password_card(row, sheet_name, card_key, admin_mode, df_pw, drive_id, pw_sheets):
    cols_list = list(row.index)
    icon = get_sheet_icon(sheet_name)
    title_col = cols_list[1] if len(cols_list) > 1 else cols_list[0]
    title_val = str(row.get(title_col, 'N/A'))
    if title_val in ('None', '', 'nan'):
        title_val = str(row.get(cols_list[0], 'N/A'))

    normal_fields = [(c, row[c]) for c in cols_list if not is_secret_field(c) and pd.notna(row[c]) and str(row[c]).strip() not in ('', 'None', 'nan')]
    secret_fields = [(c, row[c]) for c in cols_list if is_secret_field(c) and pd.notna(row[c]) and str(row[c]).strip() not in ('', 'None', 'nan')]

    with st.container():
        # header
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
            <div style="width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#ede9fe,#ddd6fe);
                        display:flex;align-items:center;justify-content:center;font-size:1.1rem;flex-shrink:0;">
                {icon}
            </div>
            <div>
                <div style="font-size:0.95rem;font-weight:700;color:#1e293b;">{title_val}</div>
                <div style="font-size:0.72rem;color:#94a3b8;">{sheet_name}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # normal fields
        if normal_fields:
            fields_html = ""
            for col_name, val in normal_fields:
                fields_html += f'<div class="pw-field-row"><span class="pw-field-label">{col_name}</span><span class="pw-field-value">{val}</span></div>'
            st.markdown(fields_html, unsafe_allow_html=True)

        # secret fields
        if secret_fields:
            
            for col_name, val in secret_fields:
                with st.expander(f"🔐 {col_name}"):
                    st.code(str(val), language=None)

        if admin_mode:
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✏️ แก้ไข", key=f"pw_edit_{sheet_name}_{card_key}", use_container_width=True):
                    st.session_state[f"pw_edit_row_{sheet_name}_{card_key}"] = True
                    st.rerun()
            with c2:
                if st.button("🗑️ ลบ", key=f"pw_del_{sheet_name}_{card_key}", use_container_width=True):
                    st.session_state[f"pw_del_confirm_{sheet_name}_{card_key}"] = True

            if st.session_state.get(f"pw_del_confirm_{sheet_name}_{card_key}"):
                st.warning("⚠️ ยืนยันการลบ?")
                if st.button("✅ ยืนยันลบ", key=f"pw_del_ok_{sheet_name}_{card_key}", type="primary"):
                    new_df = df_pw.drop(index=card_key).reset_index(drop=True)
                    pw_sheets[sheet_name] = new_df
                    ok = upload_password_excel(drive_id, pw_sheets)
                    if ok:
                        st.success("✅ ลบสำเร็จ")
                        load_password_excel.clear()
                        st.session_state.pop(f"pw_del_confirm_{sheet_name}_{card_key}", None)
                        st.rerun()
                    else:
                        st.error("❌ ลบไม่สำเร็จ")

@st.dialog("✏️ แก้ไข Password Entry")
def edit_password_dialog(row, row_idx, sheet_name, df_pw, drive_id, pw_sheets):
    st.markdown(f"### ✏️ แก้ไขรายการ")
    new_vals = {}
    for col in df_pw.columns:
        cur_val = str(row.get(col, '')) if pd.notna(row.get(col)) else ''
        if is_secret_field(col):
            new_vals[col] = st.text_input(f"🔐 {col}", value=cur_val, type="password")
        else:
            new_vals[col] = st.text_input(col, value=cur_val)
    if st.button("💾 บันทึก", use_container_width=True, type="primary"):
        for col, val in new_vals.items():
            df_pw.at[row_idx, col] = val if val.strip() != '' else None
        pw_sheets[sheet_name] = df_pw
        ok = upload_password_excel(drive_id, pw_sheets)
        if ok:
            st.success("✅ บันทึกสำเร็จ")
            load_password_excel.clear()
            st.rerun()
        else:
            err_msg = res_data.get("error", {}).get("message", str(res_data)) if isinstance(res_data, dict) else str(res_data)
            st.error(f"❌ บันทึกไม่สำเร็จ: {err_msg}")

@st.dialog("➕ เพิ่ม Password Entry")
def add_password_dialog(sheet_name, df_pw, drive_id, pw_sheets):
    st.markdown(f"### ➕ เพิ่มรายการใหม่ — {sheet_name}")
    new_vals = {}
    for col in df_pw.columns:
        if is_secret_field(col):
            new_vals[col] = st.text_input(f"🔐 {col}", type="password")
        else:
            new_vals[col] = st.text_input(col)
    if st.button("💾 บันทึก", use_container_width=True, type="primary"):
        new_row = {col: (val if val.strip() != '' else None) for col, val in new_vals.items()}
        new_df = pd.concat([df_pw, pd.DataFrame([new_row])], ignore_index=True)
        pw_sheets[sheet_name] = new_df
        ok = upload_password_excel(drive_id, pw_sheets)
        if ok:
            st.success("✅ เพิ่มสำเร็จ")
            load_password_excel.clear()
            st.rerun()
        else:
            err_msg = res_data.get("error", {}).get("message", str(res_data)) if isinstance(res_data, dict) else str(res_data)
            st.error(f"❌ เพิ่มไม่สำเร็จ: {err_msg}")

# --- 10b. INK STOCK CARD + DIALOGS ---
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
    return f"<span style='background:#198754;color:#fff;padding:3px 14px;border-radius:12px;font-weight:bold;font-size:0.95em;'>✅ {qty}</span>"

def render_ink_card(row, key, admin_mode, requester_name):
    qty     = int(row.get("Quantity", 0)) if str(row.get("Quantity", 0)).lstrip("-").isdigit() else 0
    min_qty = int(row.get("Min_Qty", INK_LOW_THRESHOLD)) if str(row.get("Min_Qty", INK_LOW_THRESHOLD)).isdigit() else INK_LOW_THRESHOLD
    title   = row.get("Title", "N/A")
    color   = row.get("Color", "Other")
    item_id = row.get("_item_id")

    with st.container():
        c_left, c_right = st.columns([0.65, 0.35])
        with c_left:
            st.markdown(f"#### 🖨️ {title}")
            st.markdown(
                ink_stock_color_badge(color) + "&nbsp;&nbsp;" + ink_qty_badge(qty, min_qty),
                unsafe_allow_html=True,
            )
            st.caption(f"🏢 {row.get('Company', '-')}  |  📠 {row.get('Printer_Model', '-')}")
            price = row.get("Unit_Price", "")
            if price and str(price) not in ("None", "nan", ""):
                st.caption(f"💰 {price} บาท/ชิ้น")
        with c_right:
            # ปุ่ม เบิก / เพิ่ม / แก้ไข
            if st.button("📤 เบิก", key=f"ink_withdraw_{key}", use_container_width=True):
                st.session_state[f"ink_withdraw_{key}"] = True
                st.rerun()
            if admin_mode:
                if st.button("📥 เพิ่ม", key=f"ink_add_qty_{key}", use_container_width=True):
                    st.session_state[f"ink_add_qty_{key}"] = True
                    st.rerun()
                if st.button("✏️ แก้ไข", key=f"ink_edit_{key}", use_container_width=True):
                    st.session_state[f"ink_edit_{key}"] = True
                    st.rerun()

    # ---- dialogs triggered by session state ----
    if st.session_state.get(f"ink_withdraw_{key}"):
        st.session_state.pop(f"ink_withdraw_{key}")
        withdraw_ink_dialog(row.to_dict(), key, requester_name)

    if admin_mode and st.session_state.get(f"ink_add_qty_{key}"):
        st.session_state.pop(f"ink_add_qty_{key}")
        add_ink_qty_dialog(row.to_dict(), key, requester_name)

    if admin_mode and st.session_state.get(f"ink_edit_{key}"):
        st.session_state.pop(f"ink_edit_{key}")
        edit_ink_dialog(row.to_dict(), key)

@st.dialog("📤 เบิกหมึกพิมพ์")
def withdraw_ink_dialog(row, key, requester_name):
    qty   = int(row.get("Quantity", 0)) if str(row.get("Quantity", 0)).lstrip("-").isdigit() else 0
    title = row.get("Title", "N/A")
    color = row.get("Color", "-")
    st.markdown(f"### 📤 เบิก: {title}")
    st.markdown(ink_stock_color_badge(color), unsafe_allow_html=True)
    if qty <= 0:
        st.error("❌ หมึกหมดสต็อก ไม่สามารถเบิกได้")
        return
    st.info(f"สต็อกปัจจุบัน: **{qty}** ชิ้น")
    withdraw_qty = st.number_input("จำนวนที่ต้องการเบิก", min_value=1, max_value=qty, value=1, step=1)
    note = st.text_input("หมายเหตุ (เช่น เครื่อง/ชั้น/ห้อง)")
    if st.button("✅ ยืนยันเบิก", use_container_width=True, type="primary"):
        ok, new_qty = ink_adjust_quantity(
            row["_item_id"], qty, -withdraw_qty,
            title, color, requester_name, note, "เบิก"
        )
        if ok:
            st.success(f"✅ เบิกสำเร็จ — สต็อกคงเหลือ: {new_qty} ชิ้น")
            st.rerun()
        else:
            st.error("❌ เบิกไม่สำเร็จ")

@st.dialog("📥 เพิ่มจำนวนสต็อกหมึก")
def add_ink_qty_dialog(row, key, requester_name):
    qty   = int(row.get("Quantity", 0)) if str(row.get("Quantity", 0)).lstrip("-").isdigit() else 0
    title = row.get("Title", "N/A")
    color = row.get("Color", "-")
    st.markdown(f"### 📥 เพิ่มสต็อก: {title}")
    st.markdown(ink_stock_color_badge(color), unsafe_allow_html=True)
    st.info(f"สต็อกปัจจุบัน: **{qty}** ชิ้น")
    add_qty = st.number_input("จำนวนที่ต้องการเพิ่ม", min_value=1, value=1, step=1)
    note = st.text_input("หมายเหตุ (เช่น เลข PO / ผู้ขาย)")
    if st.button("✅ ยืนยันเพิ่มสต็อก", use_container_width=True, type="primary"):
        ok, new_qty = ink_adjust_quantity(
            row["_item_id"], qty, add_qty,
            title, color, requester_name, note, "เพิ่มสต็อก"
        )
        if ok:
            st.success(f"✅ เพิ่มสำเร็จ — สต็อกคงเหลือ: {new_qty} ชิ้น")
            st.rerun()
        else:
            st.error("❌ เพิ่มไม่สำเร็จ")

@st.dialog("✏️ แก้ไขข้อมูลหมึกพิมพ์")
def edit_ink_dialog(row, key):
    item_id = row.get("_item_id")
    st.markdown(f"### ✏️ แก้ไข: {row.get('Title', '')}")
    title      = st.text_input("รุ่นหมึก", value=row.get("Title", ""))
    color      = st.selectbox("สี", INK_COLOR_OPTIONS,
                              index=INK_COLOR_OPTIONS.index(row.get("Color", "Black"))
                              if row.get("Color") in INK_COLOR_OPTIONS else 0)
    printer_m  = st.text_input("รุ่นเครื่องพิมพ์", value=row.get("Printer_Model", ""))
    company    = st.selectbox("บริษัท", ["ALL"] + COMPANY_OPTIONS,
                              index=(["ALL"] + COMPANY_OPTIONS).index(row.get("Company", "ALL"))
                              if row.get("Company") in ["ALL"] + COMPANY_OPTIONS else 0)
    qty        = st.number_input("จำนวนคงเหลือ", min_value=0, value=int(row.get("Quantity", 0)) if str(row.get("Quantity", 0)).isdigit() else 0)
    min_qty    = st.number_input("จุดแจ้งเตือน (Low Stock)", min_value=1, value=int(row.get("Min_Qty", INK_LOW_THRESHOLD)) if str(row.get("Min_Qty", INK_LOW_THRESHOLD)).isdigit() else INK_LOW_THRESHOLD)
    unit_price = st.text_input("ราคา/ชิ้น (บาท)", value=str(row.get("Unit_Price", "")).replace("None","").replace("nan",""))
    notes      = st.text_input("หมายเหตุ", value=str(row.get("Notes", "")).replace("None","").replace("nan",""))
    col_save, col_del = st.columns(2)
    with col_save:
        if st.button("💾 บันทึก", use_container_width=True, type="primary"):
            fields = {"Title": title, "Color": color, "Printer_Model": printer_m,
                      "Company": company, "Quantity": qty, "Min_Qty": min_qty,
                      "Unit_Price": unit_price or None, "Notes": notes or None}
            ok, res_data = ink_update(item_id, fields)
            if ok:
                st.success("✅ บันทึกสำเร็จ")
                clear_sp_cache()
                st.rerun()
            else:
                err_msg = res_data.get("error", {}).get("message", str(res_data)) if isinstance(res_data, dict) else str(res_data)
                st.error(f"❌ บันทึกไม่สำเร็จ: {err_msg}")
    with col_del:
        if st.button("🗑️ ลบรายการนี้", use_container_width=True):
            st.session_state["ink_confirm_delete"] = item_id
    if st.session_state.get("ink_confirm_delete") == item_id:
        st.warning("⚠️ ยืนยันการลบ?")
        if st.button("✅ ยืนยันลบ", type="primary"):
            ok = ink_delete(item_id)
            if ok:
                st.success("✅ ลบสำเร็จ")
                st.session_state.pop("ink_confirm_delete", None)
                clear_sp_cache()
                st.rerun()
            else:
                st.error("❌ ลบไม่สำเร็จ")

@st.dialog("➕ เพิ่มหมึกพิมพ์ใหม่")
def add_ink_dialog():
    st.markdown("### ➕ เพิ่มหมึกพิมพ์ใหม่")
    title      = st.text_input("รุ่นหมึก *", placeholder="เช่น HP 680 Black")
    color      = st.selectbox("สี *", INK_COLOR_OPTIONS)
    printer_m  = st.text_input("รุ่นเครื่องพิมพ์", placeholder="เช่น HP DeskJet 2135")
    company    = st.selectbox("บริษัท", ["ALL"] + COMPANY_OPTIONS)
    qty        = st.number_input("จำนวนเริ่มต้น", min_value=0, value=0)
    min_qty    = st.number_input("จุดแจ้งเตือน (Low Stock)", min_value=1, value=INK_LOW_THRESHOLD)
    unit_price = st.text_input("ราคา/ชิ้น (บาท)", placeholder="เช่น 350")
    notes      = st.text_input("หมายเหตุ")
    if st.button("💾 บันทึก", use_container_width=True, type="primary"):
        if not title.strip():
            st.warning("⚠️ กรุณาระบุรุ่นหมึก")
            return
        fields = {"Title": title.strip(), "Color": color, "Printer_Model": printer_m,
                  "Company": company, "Quantity": qty, "Min_Qty": min_qty,
                  "Unit_Price": unit_price or None, "Notes": notes or None}
        ok, res_data = ink_create(fields)
        if ok:
            st.success("✅ เพิ่มสำเร็จ")
            clear_sp_cache()
            st.rerun()
        else:
            err_msg = res_data.get("error", {}).get("message", str(res_data)) if isinstance(res_data, dict) else str(res_data)
            st.error(f"❌ เพิ่มไม่สำเร็จ: {err_msg}")

# --- 11. STREAMLIT UI ---
st.set_page_config(layout="wide", page_title="Optimal IT Management", page_icon="🛡️")
cookie_manager = get_manager()

# --- AUTH ---
saved_user  = cookie_manager.get(cookie="user_name")
saved_email = cookie_manager.get(cookie="user_email")

if 'is_auth' not in st.session_state:
    st.session_state.is_auth  = False
    st.session_state.user_name  = ""
    st.session_state.user_email = ""
    st.session_state.skip_cookie_login = False

if saved_user and not st.session_state.get('is_auth') and not st.session_state.get('skip_cookie_login'):
    st.session_state.is_auth  = True
    st.session_state.user_name  = saved_user
    st.session_state.user_email = saved_email or ""

# ===== MODERN UI THEME =====
MODERN_THEME = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=IBM+Plex+Sans+Thai:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"]{font-family:'Inter','IBM Plex Sans Thai',sans-serif !important;}
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at top right, rgba(99,102,241,.10), transparent 22%),radial-gradient(circle at bottom left, rgba(14,165,233,.08), transparent 18%),#eef2ff !important;}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0f172a 0%, #111827 100%) !important;border-right:1px solid rgba(255,255,255,.06);}
[data-testid="stSidebar"] *{color:#e2e8f0 !important;}
[data-testid="stMetric"]{background:rgba(255,255,255,.84) !important;border:none !important;border-radius:24px !important;padding:1.3rem !important;box-shadow:0 10px 30px rgba(15,23,42,.06) !important;}
div[data-testid="stVerticalBlockBorderWrapper"] > div{border:none !important;border-radius:24px !important;background:rgba(255,255,255,.86) !important;box-shadow:0 10px 30px rgba(15,23,42,.05) !important;transition:all .2s ease !important;}
div[data-testid="stVerticalBlockBorderWrapper"] > div:hover{transform:translateY(-2px);box-shadow:0 18px 40px rgba(99,102,241,.12) !important;}
.stButton button{border-radius:14px !important;font-weight:700 !important;}
.stTextInput input,.stSelectbox div[data-baseweb="select"] > div{border-radius:14px !important;}
[data-testid="stDataFrame"]{border-radius:22px !important;overflow:hidden !important;}
</style>
"""

# ── BASE CSS (always) ──────────────────────────────────────────────────────────
st.markdown(MODERN_THEME, unsafe_allow_html=True)

st.markdown("""
<style>
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stHeader"] { background: transparent !important; box-shadow: none !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# LOGIN PAGE
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.is_auth:
    st.markdown("""
    <style>
    /* ===== AURORA GLASS LOGIN ===== */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    html, body, [class*="css"]{
        font-family:'Inter',sans-serif !important;
}

    [data-testid="stAppViewContainer"]{
        background:
            radial-gradient(circle at top left, rgba(56,189,248,.35), transparent 28%),
            radial-gradient(circle at bottom right, rgba(139,92,246,.30), transparent 30%),
            linear-gradient(135deg,#e0f2fe 0%,#dbeafe 35%,#ede9fe 100%) !important;
        overflow:hidden;
}

    section[data-testid="stMain"],
    [data-testid="stMainBlockContainer"]{
        background:transparent !important;
}

    [data-testid="stMainBlockContainer"]{
        padding-top:6vh !important;
}

    /* floating blur orbs */
    [data-testid="stAppViewContainer"]::before{
        content:'';
        position:fixed;
        width:420px;
        height:420px;
        top:-120px;
        left:-100px;
        border-radius:50%;
        background:radial-gradient(circle,#67e8f9 0%, rgba(103,232,249,0) 70%);
        filter:blur(40px);
        animation:float1 12s ease-in-out infinite;
        z-index:0;
}

    [data-testid="stAppViewContainer"]::after{
        content:'';
        position:fixed;
        width:520px;
        height:520px;
        bottom:-180px;
        right:-120px;
        border-radius:50%;
        background:radial-gradient(circle,#a78bfa 0%, rgba(167,139,250,0) 70%);
        filter:blur(60px);
        animation:float2 14s ease-in-out infinite;
        z-index:0;
}

    @keyframes float1{
        0%,100%{transform:translateY(0px) translateX(0px);}
        50%{transform:translateY(25px) translateX(20px);}
}

    @keyframes float2{
        0%,100%{transform:translateY(0px);}
        50%{transform:translateY(-20px);}
}

    div[data-testid="column"] > div[data-testid="stVerticalBlock"]{
        position:relative;
        z-index:2;
        background:rgba(255,255,255,0.18) !important;
        backdrop-filter:blur(24px) saturate(180%) !important;
        -webkit-backdrop-filter:blur(24px) saturate(180%) !important;
        border:1px solid rgba(255,255,255,0.35) !important;
        border-radius:34px !important;
        padding:3rem 2.6rem 2.2rem !important;
        box-shadow:
            0 20px 60px rgba(99,102,241,.18),
            inset 0 1px 0 rgba(255,255,255,.45) !important;
}

    div[data-testid="column"] label{
        color:#475569 !important;
        font-weight:600 !important;
}

    div[data-testid="column"] .stTextInput > div > div > input{
        background:rgba(255,255,255,0.40) !important;
        border:1px solid rgba(255,255,255,0.50) !important;
        border-radius:18px !important;
        color:#0f172a !important;
        padding:14px 18px !important;
        font-size:.95rem !important;
        transition:all .2s ease !important;
}

    div[data-testid="column"] .stTextInput > div > div > input:focus{
        border-color:#60a5fa !important;
        box-shadow:0 0 0 4px rgba(96,165,250,.20) !important;
        background:rgba(255,255,255,0.58) !important;
}

    div[data-testid="column"] [data-testid="stFormSubmitButton"] > button{
        background:linear-gradient(135deg,#38bdf8 0%, #6366f1 55%, #8b5cf6 100%) !important;
        color:white !important;
        border:none !important;
        border-radius:18px !important;
        font-weight:700 !important;
        font-size:1rem !important;
        padding:14px !important;
        box-shadow:0 12px 30px rgba(99,102,241,.28) !important;
        transition:all .25s ease !important;
}

    div[data-testid="column"] [data-testid="stFormSubmitButton"] > button:hover{
        transform:translateY(-2px) scale(1.01) !important;
        box-shadow:0 18px 40px rgba(99,102,241,.35) !important;
}

    div[data-testid="column"] [data-testid="stAlert"]{
        border-radius:14px !important;
}
</style>
    """, unsafe_allow_html=True)

    _, center_col, _ = st.columns([1, 1.4, 1])
    with center_col:
        st.markdown("""
        <div style="text-align:center; margin-bottom:28px;">
            <div style="width:72px;height:72px;background:linear-gradient(135deg,#6366f1,#8b5cf6);
                        border-radius:20px;display:inline-flex;align-items:center;justify-content:center;
                        font-size:2rem;box-shadow:0 8px 28px rgba(99,102,241,.55);margin-bottom:16px;">🛡️</div>
            <h1 style="color:#0f172a;font-size:2rem;font-weight:800;margin:0 0 8px;letter-spacing:-1px;">
                DocumentReportUnified</h1>
            <p style="color:#475569;font-size:.92rem;margin:0;font-weight:500;">
                Enterprise IT Management Platform</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            u = st.text_input("📧 Microsoft 365 Email", placeholder="yourname@optimal.co.th")
            p = st.text_input("🔒 Password", type="password", placeholder="••••••••••••")
            submitted = st.form_submit_button("Sign In →", use_container_width=True)
            if submitted:
                if not u.strip() or not p.strip():
                    st.warning("⚠️ กรุณากรอก Email และ Password")
                else:
                    with st.spinner("กำลังตรวจสอบ..."):
                        success, name, email = check_ms_login(u, p)
                    if success:
                        st.session_state.is_auth  = True
                        st.session_state.skip_cookie_login = False
                        st.session_state.user_name  = name
                        st.session_state.user_email = email
                        cookie_manager.set("user_name",  name,  key="auth_token")
                        cookie_manager.set("user_email", email, key="auth_email")
                        st.rerun()
                    else:
                        st.error(f"❌ {name}")

        st.markdown("""
        <p style="color:rgba(255,255,255,.25);font-size:.75rem;text-align:center;margin-top:20px;">
            ☁️ Secure Microsoft 365 Access &nbsp;·&nbsp; Optimal Group © 2025</p>
        """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════════
else:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Thai:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans Thai', sans-serif;
}

    /* ── APP BG ── */
    [data-testid="stAppViewContainer"] { background: #f0f2f8 !important; }
    section[data-testid="stMain"]      { background: #f0f2f8 !important; }
    [data-testid="stMainBlockContainer"] {
        padding: 1.8rem 2rem 3rem !important;
        max-width: 1400px !important;
}
    [data-testid="stHeader"] { background: transparent !important; box-shadow: none !important; }

    /* ── SIDEBAR ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #e0f2fe 0%, #f0e7fe 50%, #ede9fe 100%) !important;
        border-right: 1px solid rgba(148,163,184,0.15) !important;
        box-shadow: 4px 0 24px rgba(56,189,248,0.08) !important;
}
    [data-testid="stSidebarContent"] { padding: 12px 8px 12px 8px !important; }
    [data-testid="stSidebar"] * { color: #1e293b !important; font-family: 'IBM Plex Sans Thai', sans-serif !important; }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 { color: #0f172a !important; }
    [data-testid="stSidebar"] label { color: #64748b !important; font-size: 0.72rem !important; font-weight: 600 !important; letter-spacing: 0.8px !important; text-transform: uppercase !important; }
    [data-testid="stSidebar"] hr { border-color: rgba(100,116,139,0.2) !important; margin: 12px 0 !important; }
    [data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div {
        background: rgba(255,255,255,0.7) !important;
        border: 1px solid rgba(100,116,139,0.2) !important;
        border-radius: 12px !important; color: #0f172a !important;
}
    [data-testid="stSidebar"] [data-baseweb="select"] svg { fill: #64748b !important; }
    [data-testid="stSidebar"] .sidebar-card {
        background: rgba(255,255,255,0.6) !important;
        border: 1px solid rgba(100,116,139,0.15) !important;
        border-radius: 18px !important;
        padding: 16px 12px !important;
        margin: 0 -8px 16px -8px !important;
        box-shadow: 0 4px 12px rgba(56,189,248,0.08) !important;
    }
    [data-testid="stSidebar"] .sidebar-section-title {
        display: block !important;
        margin: 16px -8px 12px -8px !important;
        font-size: 0.78rem !important;
        color: #475569 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        font-weight: 700 !important;
        padding: 0 8px !important;
        text-align: left !important;
    }
    [data-testid="stSidebar"] .sidebar-submenu {
        padding-left: 0 !important;
        margin-left: 0 !important;
        margin-top: 6px !important;
        text-align: left !important;
    }
    [data-testid="stSidebar"] .sidebar-label {
        font-size: 0.82rem !important;
        color: #64748b !important;
        margin: 14px -8px 10px -8px !important;
        padding: 0 8px !important;
        font-weight: 600 !important;
        text-align: left !important;
    }
    /* sidebar buttons */
    [data-testid="stSidebar"] .stButton {
        padding-left: 0 !important;
        padding-right: 0 !important;
        margin-left: 0 !important;
        margin-right: 0 !important;
    }
    [data-testid="stSidebar"] .stButton > button {
        background: rgba(255,255,255,0.7) !important;
        border: 1px solid rgba(100,116,139,0.15) !important;
        border-radius: 14px !important; color: #475569 !important;
        font-size: 0.9rem !important; font-weight: 500 !important;
        transition: all .2s !important; width: calc(100% + 16px) !important;
        padding: 10px 10px 10px 12px !important;
        text-align: left !important;
        margin-bottom: 6px !important;
        margin-left: -8px !important;
    }
}
    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(99,102,241,0.15) !important;
        border-color: rgba(99,102,241,0.3) !important;
        color: #0f172a !important;
}
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background: linear-gradient(135deg,#6366f1,#8b5cf6) !important;
        color: #fff !important;
        border-color: transparent !important;
        box-shadow: 0 8px 20px rgba(99,102,241,0.22) !important;
}
    [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg,#4f46e5,#7c3aed) !important;
        box-shadow: 0 12px 28px rgba(99,102,241,0.28) !important;
}
    [data-testid="stSidebar"] .sidebar-footer {
        margin: 18px -8px 0 -8px !important;
        padding: 14px 8px 0 8px !important;
        border-top: 1px solid rgba(100,116,139,0.15) !important;
    }
    /* admin alert in sidebar */
    [data-testid="stSidebar"] [data-testid="stAlert"] {
        background: rgba(16,185,129,0.12) !important;
        border: 1px solid rgba(16,185,129,0.25) !important;
        border-radius: 10px !important;
}
    [data-testid="stSidebar"] [data-testid="stAlert"] p,
    [data-testid="stSidebar"] [data-testid="stAlert"] * { color: #6ee7b7 !important; font-size: 0.83rem !important; }

    /* ── METRIC CARDS ── */
    [data-testid="stMetric"] {
        background: #ffffff !important;
        border-radius: 14px !important;
        padding: 1.1rem 1.4rem 1rem !important;
        border: 1px solid #e2e8f0 !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.04) !important;
        position: relative; overflow: hidden;
}
    [data-testid="stMetric"]::before {
        content: ''; position: absolute; top: 0; left: 0;
        width: 4px; height: 100%;
        background: linear-gradient(180deg, #6366f1, #8b5cf6);
}
    [data-testid="stMetricLabel"] { font-size: 0.76rem !important; color: #94a3b8 !important; font-weight: 600 !important; letter-spacing: 0.5px !important; text-transform: uppercase !important; }
    [data-testid="stMetricValue"] { font-size: 2.1rem !important; font-weight: 700 !important; color: #0f172a !important; letter-spacing: -1px !important; font-family: 'IBM Plex Mono', monospace !important; }

    /* ── CONTENT CARDS ── */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(div[data-testid="stElementContainer"]) > div {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 14px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.03) !important;
        transition: box-shadow .2s, transform .2s !important;
}
    div[data-testid="stVerticalBlockBorderWrapper"]:has(div[data-testid="stElementContainer"]) > div:hover {
        box-shadow: 0 4px 20px rgba(99,102,241,0.12), 0 1px 3px rgba(0,0,0,0.06) !important;
        transform: translateY(-1px) !important;
}

    /* ── TYPOGRAPHY ── */
    h1 { color: #0f172a !important; font-weight: 700 !important; letter-spacing: -0.5px !important; font-size: 1.6rem !important; }
    h2 { color: #1e293b !important; font-weight: 600 !important; }
    h3 { color: #334155 !important; font-weight: 600 !important; font-size: 1rem !important; }
    p, .stMarkdown p { color: #475569 !important; }

    /* ── PRIMARY BUTTON — main content only ── */
    [data-testid="stMain"] [data-testid="stButton"] > button[kind="primary"],
    [data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
        border: none !important; border-radius: 10px !important;
        color: #fff !important; font-weight: 600 !important;
        box-shadow: 0 2px 8px rgba(99,102,241,0.35) !important;
        transition: all .15s !important;
        font-family: 'IBM Plex Sans Thai', sans-serif !important;
}
    [data-testid="stMain"] [data-testid="stButton"] > button[kind="primary"]:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 16px rgba(99,102,241,0.45) !important;
}

    /* ── SECONDARY BUTTON — main content only (NOT sidebar) ── */
    [data-testid="stMain"] [data-testid="stButton"] > button:not([kind="primary"]) {
        background: #fff !important; border: 1px solid #e2e8f0 !important;
        border-radius: 10px !important; color: #475569 !important;
        font-family: 'IBM Plex Sans Thai', sans-serif !important;
        transition: all .15s !important;
}
    [data-testid="stMain"] [data-testid="stButton"] > button:not([kind="primary"]):hover {
        border-color: #6366f1 !important; color: #6366f1 !important;
        background: #f5f3ff !important;
}

    /* ── INPUTS ── */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {
        border-radius: 10px !important; border: 1.5px solid #e2e8f0 !important;
        font-family: 'IBM Plex Sans Thai', sans-serif !important;
        background: #fff !important; color: #1e293b !important;
        padding: 10px 14px !important; font-size: 0.88rem !important;
        transition: border .15s, box-shadow .15s !important;
}
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 3px rgba(99,102,241,0.12) !important;
}

    /* ── SELECTBOX ── */
    [data-baseweb="select"] > div {
        border-radius: 10px !important; border-color: #e2e8f0 !important;
        font-family: 'IBM Plex Sans Thai', sans-serif !important;
        background: #fff !important;
}
    [data-baseweb="select"] > div:hover { border-color: #a5b4fc !important; }

    /* ── DATAFRAME ── */
    [data-testid="stDataFrame"] {
        border-radius: 12px !important; overflow: hidden !important;
        border: 1px solid #e2e8f0 !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
}

    /* ── DIVIDER ── */
    hr { border-color: #e2e8f0 !important; }

    /* ── EXPANDER ── */
    details > summary {
        border-radius: 10px !important; background: #f8fafc !important;
        border: 1px solid #e2e8f0 !important; padding: 10px 14px !important;
        font-size: 0.85rem !important; font-weight: 500 !important; color: #475569 !important;
}
    details[open] > summary { border-bottom-left-radius: 0 !important; border-bottom-right-radius: 0 !important; }

    /* ── ALERTS ── */
    [data-testid="stAlert"][data-baseweb="notification"] {
        border-radius: 12px !important; border-left: 4px solid !important;
        font-size: 0.88rem !important;
}

    /* ── SPINNER ── */
    [data-testid="stSpinner"] { opacity: 0.7; }

    /* ── GAP — main content only ── */
    [data-testid="stMain"] [data-testid="stVerticalBlock"] { gap: 0.6rem !important; }

    

    /* ── SIDEBAR: logout button only ── */
    [data-testid="stSidebar"] .stButton > button {
        background: transparent !important; border: none !important;
        box-shadow: none !important; color: #f87171 !important;
        font-size: 0.84rem !important; text-align: left !important;
        justify-content: flex-start !important; border-radius: 8px !important;
        padding: 6px 10px !important; width: 100% !important;
        transition: background .12s !important;
}
    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(239,68,68,0.12) !important;
}

    
    /* REMOVE EMPTY STREAMLIT CONTAINERS */
    div[data-testid="stHorizontalBlock"]:empty,
    div[data-testid="stVerticalBlock"]:empty,
    div[data-testid="stVerticalBlockBorderWrapper"]:empty{
        display:none !important;
        margin:0 !important;
        padding:0 !important;
        height:0 !important;
        min-height:0 !important;
}

    /* FIX EMPTY COLUMN GAPS */
    div[data-testid="column"]:empty{
        display:none !important;
}

    /* REMOVE AUTO EMPTY PLACEHOLDERS */
    .element-container:empty{
        display:none !important;
}


    /* ── CHECKBOX ── */
    [data-testid="stCheckbox"] label { color: #475569 !important; font-size: 0.85rem !important; }

    /* ── CAPTION ── */
    [data-testid="stCaptionContainer"] p { color: #94a3b8 !important; font-size: 0.78rem !important; }

    /* ── SIDEBAR NAV BUTTONS ── */
    [data-testid="stSidebar"] .stButton {
        padding-left: 0 !important;
        padding-right: 0 !important;
        margin-left: 0 !important;
        margin-right: 0 !important;
    }
    [data-testid="stSidebar"] .stButton > button {
        text-align: left !important;
        justify-content: flex-start !important;
        background: transparent !important;
        border: none !important;
        border-radius: 0 !important;
        color: #0f172a !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        padding: 6px 0 6px 8px !important;
        transition: background .15s, color .15s !important;
        box-shadow: none !important;
        width: 100% !important;
        margin: 0 !important;
        display: flex !important;
        align-items: center !important;
    }
    [data-testid="stSidebar"] .stButton > button > * {
        margin-left: 0 !important;
        margin-right: 0 !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255,255,255,0.15) !important;
        color: #0f172a !important;
        border: none !important;
        box-shadow: none !important;
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background: transparent !important;
        color: #0f172a !important;
        border: none !important;
        box-shadow: none !important;
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
        background: rgba(255,255,255,0.15) !important;
        box-shadow: none !important;
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background: linear-gradient(135deg,#6366f1,#8b5cf6) !important;
        color: #fff !important;
        border-color: transparent !important;
        box-shadow: 0 8px 20px rgba(99,102,241,0.22) !important;
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg,#4f46e5,#7c3aed) !important;
        box-shadow: 0 12px 28px rgba(99,102,241,0.28) !important;
    }

    /* ── SIDEBAR STAT CARDS ── */
    .ov-card {
        background: #fff;
        border-radius: 14px;
        padding: 16px 18px 12px;
        border: 1px solid #e8eaf0;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        transition: box-shadow .2s, transform .2s;
        height: 100%;
}
    .ov-card:hover { box-shadow: 0 4px 18px rgba(99,102,241,0.13); transform: translateY(-2px); }
    .ov-card-top { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
    .ov-card-icon { width: 38px; height: 38px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.15rem; flex-shrink: 0; }
    .ov-card-label { font-size: 0.72rem; font-weight: 700; letter-spacing: 0.6px; text-transform: uppercase; color: #94a3b8; }
    .ov-card-value { font-size: 2.1rem; font-weight: 800; line-height: 1.1; letter-spacing: -1px; margin-bottom: 10px; }
    .ov-card-link { display: flex; align-items: center; gap: 4px; font-size: 0.78rem; font-weight: 500; padding-top: 8px; border-top: 1px solid #f1f5f9; cursor: pointer; }
    

    /* ── STATUS BADGE (custom html) ── */
    .badge {
        display: inline-block; padding: 3px 11px; border-radius: 20px;
        font-size: 0.73rem; font-weight: 700; letter-spacing: 0.4px;
}
    .badge-active   { background: #dcfce7; color: #15803d; }
    .badge-inactive { background: #fee2e2; color: #b91c1c; }
    .badge-spare    { background: #dbeafe; color: #1d4ed8; }
    .badge-repair   { background: #fef3c7; color: #b45309; }
    .badge-default  { background: #f1f5f9; color: #64748b; }

    /* ── PAGE HEADER (custom html) ── */
    .page-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 60%, #312e81 100%);
        border-radius: 16px; padding: 24px 28px; margin-bottom: 1.5rem;
        display: flex; align-items: center; gap: 16px;
        box-shadow: 0 4px 20px rgba(99,102,241,0.20);
        position: relative; overflow: hidden;
}
    .page-header::before {
        content: ''; position: absolute; right: -40px; top: -40px;
        width: 200px; height: 200px; border-radius: 50%;
        background: rgba(99,102,241,0.18); filter: blur(40px);
}
    .page-header-icon {
        font-size: 2.2rem; line-height: 1;
        background: rgba(255,255,255,0.10); border-radius: 14px;
        padding: 12px; border: 1px solid rgba(255,255,255,0.14);
}
    .page-header-text h1 {
        color: #fff !important; font-size: 1.4rem !important;
        font-weight: 700 !important; margin: 0 0 4px !important;
        letter-spacing: -0.3px !important;
}
    .page-header-text p { color: rgba(255,255,255,0.5) !important; font-size: 0.82rem !important; margin: 0 !important; }

    /* ── SECTION HEADER ── */
    .section-title {
        font-size: 0.72rem; font-weight: 700; letter-spacing: 1px;
        text-transform: uppercase; color: #94a3b8;
        margin: 1.2rem 0 0.5rem; padding-bottom: 6px;
        border-bottom: 1px solid #e2e8f0;
}

    /* ── HARDWARE CARD ── */
    .hw-card-title { font-size: 0.98rem; font-weight: 600; color: #1e293b; margin: 0; }
    .hw-card-sub   { font-size: 0.76rem; color: #94a3b8; margin: 3px 0 8px; }
    .hw-field      { font-size: 0.82rem; color: #475569; padding: 5px 0; border-bottom: 1px solid #f1f5f9; }
    .hw-field:last-of-type { border-bottom: none; }
    .hw-field strong { color: #334155; font-weight: 600; }

    /* ── NAS CARD ── */
    .nas-folder-badge {
        background: linear-gradient(135deg, #ede9fe, #ddd6fe);
        border: 1px solid #c4b5fd; border-radius: 10px;
        padding: 10px 14px; display: inline-block;
}
    .nas-folder-name { font-size: 1.05rem; font-weight: 700; color: #4c1d95; }
    .nas-user-tag {
        display: inline-block; margin: 2px 3px; padding: 3px 10px;
        border-radius: 16px; font-size: 0.75rem; font-weight: 600;
}
    .nas-rw  { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }
    .nas-ro  { background: #dcfce7; color: #166534; border: 1px solid #86efac; }

    /* ── PASSWORD CARD ── */
    .pw-field-row {
        display: flex; gap: 8px; align-items: baseline;
        padding: 6px 0; border-bottom: 1px solid #f8fafc; font-size: 0.83rem;
}
    .pw-field-row:last-of-type { border-bottom: none; }
    .pw-field-label { color: #94a3b8; font-size: 0.72rem; font-weight: 600; min-width: 90px; flex-shrink: 0; }
    .pw-field-value { color: #334155; font-weight: 500; word-break: break-all; }

    </style>
    """, unsafe_allow_html=True)

    # ── helpers ──────────────────────────────────────────────
    def status_badge(status: str) -> str:
        cls = {"Active": "badge-active", "Inactive": "badge-inactive",
               "Spare": "badge-spare", "Repair": "badge-repair"}.get(status, "badge-default")
        return f'<span class="badge {cls}">{status or "—"}</span>'

    def page_header(icon: str, title: str, subtitle: str = ""):
        st.markdown(f"""
        <div class="page-header">
            <div class="page-header-icon">{icon}</div>
            <div class="page-header-text">
                <h1>{title}</h1>
                {'<p>' + subtitle + '</p>' if subtitle else ''}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── SIDEBAR ──────────────────────────────────────────────
    admin_mode = is_admin(st.session_state.user_email)
    name = st.session_state.user_name or "User"
    initials = "".join([w[0].upper() for w in name.split()[:2]])

    st.sidebar.markdown(f"""
    <div class="sidebar-card">
        <div style="display:flex; align-items:center; gap: 12px; margin-bottom: 14px;">
            <div style="width:42px; height:42px; border-radius:12px; flex-shrink:0;
                        background: linear-gradient(135deg,#6366f1,#8b5cf6);
                        display:flex; align-items:center; justify-content:center;
                        font-size:1rem; font-weight:700; color:#fff; letter-spacing:-0.5px;">
                {initials}
            </div>
            <div>
                <div style="font-size:0.88rem; font-weight:700; color:#f1f5f9; line-height:1.2;">{name}</div>
                <div style="font-size:0.74rem; color:#94a3b8; margin-top:2px;">
                    {'🔑 Administrator' if admin_mode else '👤 User'}
                </div>
            </div>
        </div>
        {'<div style="background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.25);border-radius:10px;padding:8px 12px;font-size:0.78rem;font-weight:700;color:#6ee7b7;text-align:center;">Admin Mode</div>' if admin_mode else ''}
    </div>
    """, unsafe_allow_html=True)

    # ── Brand / Logo ──────────────────────────────────────────
    st.sidebar.markdown("""
    <div class="sidebar-card">
        <div style="display:flex; align-items:center; gap:10px;">
            <div style="width:38px;height:38px;border-radius:12px;flex-shrink:0;
                        background:linear-gradient(135deg,#6366f1,#8b5cf6);
                        display:flex;align-items:center;justify-content:center;font-size:1.2rem;">📊</div>
            <div>
                <div style="font-size:0.88rem;font-weight:700;color:#f1f5f9;line-height:1.2;">IT Asset Overview</div>
                <div style="font-size:0.72rem;color:#94a3b8;margin-top:2px;">Optimal IT Management</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    
    # ── NAVIGATION ─────────────────────────────────────────────
    if "active_nav" not in st.session_state:
        st.session_state.active_nav = "overview"

    if "open_hw" not in st.session_state:
        st.session_state.open_hw = True

    if "open_sw" not in st.session_state:
        st.session_state.open_sw = False

    if "open_ink" not in st.session_state:
        st.session_state.open_ink = False

    def set_nav(nav_key):
        st.session_state.active_nav = nav_key

    allowed_hw_navs = {"computers", "monitors", "projector", "printers", "ups", "misc"}
    if not admin_mode and st.session_state.active_nav not in allowed_hw_navs:
        st.session_state.active_nav = "computers"

    # ── SIDEBAR NAVIGATION ─────────────────────────────────────
    st.sidebar.markdown("<div class=\"sidebar-section-title\">🏠 เมนูหลัก</div>", unsafe_allow_html=True)

    if admin_mode:
        if st.sidebar.button(
            "📊 Overview Dashboard",
            use_container_width=True,
            type="primary" if st.session_state.active_nav == "overview" else "secondary",
            key="nav_overview"
        ):
            set_nav("overview")
            st.rerun()

    # ===== HARDWARE =====
    st.sidebar.markdown("<div class='sidebar-label'>Hardware</div>", unsafe_allow_html=True)
    if st.sidebar.button(
        f"{'▾' if st.session_state.open_hw else '▸'} 🖥️ Hardware",
        use_container_width=True,
        key="toggle_hw_btn"
    ):
        st.session_state.open_hw = not st.session_state.open_hw
        st.rerun()

    if st.session_state.open_hw:
        st.sidebar.markdown("<div class='sidebar-submenu'>", unsafe_allow_html=True)

        if st.sidebar.button(
            "💻 Computers",
            use_container_width=True,
            type="primary" if st.session_state.active_nav == "computers" else "secondary",
            key="nav_computers"
        ):
            set_nav("computers")
            st.rerun()

        if st.sidebar.button(
            "🖥️ Monitors",
            use_container_width=True,
            type="primary" if st.session_state.active_nav == "monitors" else "secondary",
            key="nav_monitors"
        ):
            set_nav("monitors")
            st.rerun()

        if st.sidebar.button(
            "📽️ Projector",
            use_container_width=True,
            type="primary" if st.session_state.active_nav == "projector" else "secondary",
            key="nav_projector"
        ):
            set_nav("projector")
            st.rerun()

        if st.sidebar.button(
            "🖨️ Printers",
            use_container_width=True,
            type="primary" if st.session_state.active_nav == "printers" else "secondary",
            key="nav_printers"
        ):
            set_nav("printers")
            st.rerun()

        if st.sidebar.button(
            "🔋 UPS",
            use_container_width=True,
            type="primary" if st.session_state.active_nav == "ups" else "secondary",
            key="nav_ups"
        ):
            set_nav("ups")
            st.rerun()

        if st.sidebar.button(
            "📦 Miscellaneous",
            use_container_width=True,
            type="primary" if st.session_state.active_nav == "misc" else "secondary",
            key="nav_misc"
        ):
            set_nav("misc")
            st.rerun()

        st.sidebar.markdown("</div>", unsafe_allow_html=True)

    if admin_mode:
        st.sidebar.markdown("<div class='sidebar-label'>Software</div>", unsafe_allow_html=True)
        if st.sidebar.button(
            f"{'▾' if st.session_state.open_sw else '▸'} 💿 Software",
            use_container_width=True,
            key="toggle_sw_btn"
        ):
            st.session_state.open_sw = not st.session_state.open_sw
            st.rerun()

        if st.session_state.open_sw:
            st.sidebar.markdown("<div class='sidebar-submenu'>", unsafe_allow_html=True)

            if st.sidebar.button(
                "📧 Email",
                use_container_width=True,
                type="primary" if st.session_state.active_nav == "email" else "secondary",
                key="nav_email"
            ):
                set_nav("email")
                st.rerun()

            if st.sidebar.button(
                "🌐 Domain",
                use_container_width=True,
                type="primary" if st.session_state.active_nav == "domain" else "secondary",
                key="nav_domain"
            ):
                set_nav("domain")
                st.rerun()

            if st.sidebar.button(
                "📋 Vendor",
                use_container_width=True,
                type="primary" if st.session_state.active_nav == "vendor" else "secondary",
                key="nav_vendor"
            ):
                set_nav("vendor")
                st.rerun()

        st.sidebar.markdown("### ⚙️ ระบบอื่นๆ")

        if st.sidebar.button(
            "🔐 User Permission",
            use_container_width=True,
            type="primary" if st.session_state.active_nav == "user_perm" else "secondary",
            key="nav_user_perm"
        ):
            set_nav("user_perm")
            st.rerun()

        if st.sidebar.button(
            "🔑 Password",
            use_container_width=True,
            type="primary" if st.session_state.active_nav == "password" else "secondary",
            key="nav_password"
        ):
            set_nav("password")
            st.rerun()

        # ===== INK =====
        if st.sidebar.button(
            f"{'▾' if st.session_state.open_ink else '▸'} 🖊️ Ink",
            use_container_width=True,
            key="toggle_ink_btn"
        ):
            st.session_state.open_ink = not st.session_state.open_ink
            st.rerun()

        if st.session_state.open_ink:

            if st.sidebar.button(
                "📦 Ink Stock",
                use_container_width=True,
                type="primary" if st.session_state.active_nav == "ink_stock" else "secondary",
                key="nav_ink_stock"
            ):
                set_nav("ink_stock")
                st.rerun()

            if st.sidebar.button(
                "📜 Ink History",
                use_container_width=True,
                type="primary" if st.session_state.active_nav == "ink_history" else "secondary",
                key="nav_ink_history"
            ):
                set_nav("ink_history")
                st.rerun()

            st.sidebar.markdown("</div>", unsafe_allow_html=True)

    st.sidebar.markdown("---")

    if st.sidebar.button("⬅ ออกจากระบบ", use_container_width=True, key="logout_btn"):
        expire_time = datetime.datetime.now() - datetime.timedelta(days=1)
        for cookie_key in ("user_name", "user_email"):
            try:
                cookie_manager.delete(cookie_key, key=f"logout_delete_{cookie_key}")
            except Exception:
                pass
            cookie_manager.set(cookie_key, "", expires_at=expire_time, max_age=0, key=f"logout_set_{cookie_key}")

        cookie_manager.get_all(key="logout_get_all")

        if "cookie_manager" in st.session_state:
            del st.session_state["cookie_manager"]

        st.session_state.is_auth = False
        st.session_state.skip_cookie_login = True
        st.session_state.user_name = ""
        st.session_state.user_email = ""

        st.rerun()

    _nav = st.session_state.active_nav

    # ── ROUTE ────────────────────────────────────────────────────────────────
    _ROUTE = {
        "overview":   ("📊 Overview Dashboard",  None),
        "computers":  ("💻 Hardware Asset",       "Computer Asset"),
        "monitors":   ("💻 Hardware Asset",       "Asset Monitor"),
        "projector":  ("💻 Hardware Asset",       "Asset Projector"),
        "printers":   ("💻 Hardware Asset",       "Asset Printer"),
        "ups":        ("💻 Hardware Asset",       "Asset UPS"),
        "misc":       ("💻 Hardware Asset",       "Asset Misc"),
        "email":      ("🔑 Password Information", None),
        "domain":     ("🔑 Password Information", None),
        "vendor":     ("🔑 Password Information", None),
        "user_perm":  ("📂 NAS Drive Check",      None),
        "password":   ("🔑 Password Information", None),
        "ink_stock":  ("🖨️ Stock หมึกพิมพ์",       None),
        "ink_history":("🖨️ Stock หมึกพิมพ์",       None),
}
    main_menu, _hw_sub_override = _ROUTE.get(_nav, ("📊 Overview Dashboard", None))
    show_ink_history_only = (_nav == "ink_history")

    if not admin_mode and main_menu != "💻 Hardware Asset":
        st.session_state.active_nav = "computers"
        _nav = "computers"
        main_menu, _hw_sub_override = _ROUTE["computers"]
        show_ink_history_only = False
        st.warning("🔒 สิทธิ์การใช้งานถูกจำกัด: ผู้ใช้ทั่วไปสามารถเข้าถึงได้เฉพาะ Hardware Asset เท่านั้น")

    # -------------------------------------------------------
    # 📊 Overview Dashboard
    # -------------------------------------------------------
    if main_menu == "📊 Overview Dashboard":
        page_header("📊", "IT Asset Overview", "ภาพรวมสินทรัพย์ IT ทั้งหมด")

        with st.spinner("กำลังโหลดข้อมูล..."):
            df_comp = load_sp_data("Computer Asset")
            df_mon  = load_sp_data("Asset Monitor")
            df_prn  = load_sp_data("Asset Printer")
            df_ink  = load_sp_data(INK_STOCK_LIST)
            df_nas  = load_nas_data()

        # ── Stat Cards ──
        _comp_count = len(df_comp)
        _mon_count  = len(df_mon)
        _prn_count  = len(df_prn)
        _nas_count  = len(df_nas) if df_nas is not None else 0
        if not df_comp.empty and 'field_1' in df_comp.columns:
            _uc = df_comp['field_1'].dropna().str.strip()
            _co_count = len(_uc[_uc != "ALL"].unique())
        else:
            _co_count = 0

        c1, c2, c3, c4, c5 = st.columns(5)
        _cards = [
            (c1, "COMPUTERS",  _comp_count, "#4f8ef7", "#eff4ff", "💻"),
            (c2, "MONITORS",   _mon_count,  "#22c55e", "#f0fdf4", "🖥️"),
            (c3, "PRINTERS",   _prn_count,  "#a855f7", "#faf5ff", "🖨️"),
            (c4, "NAS SHARES", _nas_count,  "#f59e0b", "#fffbeb", "📁"),
            (c5, "COMPANIES",  _co_count,   "#06b6d4", "#ecfeff", "🏢"),
        ]
        for _col, _label, _val, _color, _bg, _icon in _cards:
            with _col:
                st.markdown(f"""
                <div class="ov-card">
                    <div class="ov-card-top">
                        <div class="ov-card-icon" style="background:{_bg};">{_icon}</div>
                        <span class="ov-card-label">{_label}</span>
                    </div>
                    <div class="ov-card-value" style="color:{_color};">{_val}</div>
                    <div class="ov-card-link" style="color:{_color};">
                        {_icon} <span>รายการทั้งหมด</span>
                        <span style="font-size:1rem;">›</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # ── Ink low-stock alert ──
        if not df_ink.empty and "Quantity" in df_ink.columns and "Min_Qty" in df_ink.columns:
            def _toi2(v):
                try: return int(v)
                except: return 0
            low_ink = df_ink[df_ink.apply(
                lambda r: _toi2(r.get("Quantity", 0)) <= _toi2(r.get("Min_Qty", INK_LOW_THRESHOLD)), axis=1
            )]
            if not low_ink.empty:
                low_str = "  ·  ".join(f"{r.get('Title','?')} ({r.get('Color','-')})" for _, r in low_ink.iterrows())
                st.warning(f"⚠️ **หมึกพิมพ์ใกล้หมด/หมด:** {low_str}")

        st.markdown('<div style="font-size:0.8rem;font-weight:700;color:#64748b;letter-spacing:0.5px;text-transform:uppercase;padding:16px 0 8px;border-bottom:1px solid #e8eaf0;margin-bottom:8px;">📈 สถิติการใช้งาน</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            with st.container():
                st.markdown("**🏢 สัดส่วนอุปกรณ์ตามบริษัท**")
                if not df_comp.empty and 'field_1' in df_comp.columns:
                    cc = df_comp['field_1'].value_counts().reset_index()
                    cc.columns = ['Company', 'Count']
                    _total_co = cc['Company'].nunique()
                    fig = px.pie(cc, values='Count', names='Company', hole=0.50,
                        color_discrete_sequence=['#5b7ff5','#8b6cf7','#a78bfa','#c4b5fd','#ddd6fe','#ede9fe'])
                    fig.update_traces(
                        textposition='inside',
                        textinfo='percent+label',
                        insidetextfont=dict(size=11, color='white'),
                        marker=dict(line=dict(color='white', width=2))
                    )
                    fig.add_annotation(
                        text=f"รวมทั้งหมด<br><b>{_total_co} บริษัท</b>",
                        x=0.5, y=0.5, xref="paper", yref="paper",
                        showarrow=False,
                        font=dict(size=12, family='IBM Plex Sans Thai', color='#374151'),
                        align="center"
                    )
                    fig.update_layout(
                        margin=dict(t=10,b=10,l=10,r=10), height=300,
                        showlegend=True,
                        legend=dict(
                            orientation="v", x=1.02, y=0.5, xanchor="left",
                            font=dict(size=12, family='IBM Plex Sans Thai'),
                            bgcolor='rgba(0,0,0,0)',
                            itemsizing='constant',
                            traceorder='normal',
                        ),
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(family='IBM Plex Sans Thai')
                    )
                    st.plotly_chart(fig, use_container_width=True, config= {'displayModeBar': False})
                    st.markdown('<div style="background:#f8f9fc;border-radius:8px;padding:8px 12px;font-size:0.75rem;color:#94a3b8;">ℹ️ แสดงสัดส่วนจำนวนอุปกรณ์ทั้งหมด จำแนกตามบริษัท</div>', unsafe_allow_html=True)
        with col2:
            with st.container():
                st.markdown("**🏆 10 อันดับรุ่นคอมพิวเตอร์**")
                if not df_comp.empty and 'field_7' in df_comp.columns:
                    mc = df_comp['field_7'].value_counts().head(10).reset_index()
                    mc.columns = ['Model', 'Count']
                    fig2 = px.bar(mc, x='Count', y='Model', orientation='h',
                                  color='Count', color_continuous_scale=[[0,'#c4b5fd'],[0.5,'#8b6cf7'],[1,'#5b7ff5']])
                    fig2.update_layout(
                        margin=dict(t=10,b=40,l=10,r=40), height=300,
                        yaxis= {'categoryorder': 'total ascending', 'title': 'Model',
                               'title_font': dict(size=11, color='#9ca3af'),
                               'tickfont': dict(size=11, color='#6b7280')},
                        xaxis=dict(
                            title='จำนวน (เครื่อง)',
                            title_font=dict(size=11, color='#9ca3af'),
                            tickfont=dict(size=11, color='#9ca3af'),
                            showgrid=True, gridcolor='#f1f5f9',
                        ),
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                        coloraxis_showscale=False,
                        font=dict(family='IBM Plex Sans Thai'),
                        bargap=0.28,
                    )
                    fig2.update_traces(
                        marker_line_width=0,
                        text=mc['Count'],
                        textposition='outside',
                        textfont=dict(size=11, color='#374151'),
                    )
                    st.plotly_chart(fig2, use_container_width=True, config= {'displayModeBar': False})
                    st.markdown('<div style="background:#f8f9fc;border-radius:8px;padding:8px 12px;font-size:0.75rem;color:#94a3b8;">ℹ️ จัดอันดับตามจำนวนเครื่องมากที่สุด</div>', unsafe_allow_html=True)

    
    # -------------------------------------------------------
    # 💻 Hardware Asset
    # -------------------------------------------------------
    elif main_menu == "💻 Hardware Asset":

        st.markdown("""
        <style>

        .asset-hero{
            background:linear-gradient(135deg,#111827 0%, #312e81 100%);
            border-radius:28px;
            padding:32px;
            margin-bottom:24px;
            color:white;
            position:relative;
            overflow:hidden;
            box-shadow:0 20px 50px rgba(99,102,241,.18);
}

        .asset-hero::before{
            content:'';
            position:absolute;
            right:-80px;
            top:-80px;
            width:260px;
            height:260px;
            border-radius:50%;
            background:rgba(255,255,255,.08);
}

        .asset-title{
            font-size:2rem;
            font-weight:800;
            letter-spacing:-1px;
            margin-bottom:6px;
}

        .asset-sub{
            color:rgba(255,255,255,.72);
            font-size:.95rem;
}

        .asset-stat-wrap{
            display:grid;
            grid-template-columns:repeat(4,1fr);
            gap:16px;
            margin-bottom:24px;
}

        .asset-stat{
            background:white;
            border-radius:20px;
            padding:18px;
            border:1px solid #e2e8f0;
            box-shadow:0 10px 30px rgba(15,23,42,.05);
}

        .asset-stat-label{
            font-size:.75rem;
            font-weight:700;
            text-transform:uppercase;
            color:#94a3b8;
            margin-bottom:8px;
}

        .asset-stat-value{
            font-size:2rem;
            font-weight:800;
            color:#0f172a;
            letter-spacing:-1px;
}

        .asset-card{
            background:white;
            border-radius:24px;
            padding:22px;
            border:1px solid #e2e8f0;
            transition:all .22s ease;
            box-shadow:0 8px 24px rgba(15,23,42,.04);
            margin-bottom:20px;
}

        .asset-card:hover{
            transform:translateY(-4px);
            box-shadow:0 20px 40px rgba(99,102,241,.14);
            border-color:#c7d2fe;
}

        .asset-top{
            display:flex;
            justify-content:space-between;
            align-items:flex-start;
            margin-bottom:18px;
}

        .asset-user{
            display:flex;
            gap:14px;
            align-items:center;
}

        .asset-avatar{
            width:54px;
            height:54px;
            border-radius:18px;
            background:linear-gradient(135deg,#6366f1,#8b5cf6);
            display:flex;
            align-items:center;
            justify-content:center;
            color:white;
            font-weight:800;
            font-size:1.1rem;
            flex-shrink:0;
}

        .asset-name{
            font-size:1rem;
            font-weight:700;
            color:#0f172a;
}

        .asset-company{
            font-size:.78rem;
            color:#94a3b8;
            margin-top:2px;
}

        .asset-badge{
            padding:7px 14px;
            border-radius:999px;
            font-size:.76rem;
            font-weight:700;
}

        .badge-active{
            background:#dcfce7;
            color:#15803d;
}

        .badge-inactive{
            background:#fee2e2;
            color:#b91c1c;
}

        .asset-info{
            display:flex;
            flex-direction:column;
            gap:12px;
            margin-bottom:18px;
}

        .asset-row{
            display:flex;
            align-items:center;
            gap:10px;
            color:#475569;
            font-size:.88rem;
}

        .asset-row strong{
            color:#0f172a;
            min-width:90px;
}

        @media(max-width:900px){
            .asset-stat-wrap{
                grid-template-columns:1fr 1fr;
}
}

        </style>
        """, unsafe_allow_html=True)

        sub = _hw_sub_override or "Computer Asset"
        hardware_name = sub.replace("Asset ", "")
        df_hw = load_sp_data(sub)

        st.markdown(f"""
        <div class="asset-hero">
            <div class="asset-title">💻 {hardware_name}</div>
            <div class="asset-sub">
                ระบบจัดการ{hardware_name}และทรัพย์สิน IT ทั้งหมด
            </div>
        </div>
        """, unsafe_allow_html=True)

        total_assets = len(df_hw)
        active_assets = len(df_hw[df_hw["Status"] == "Active"]) if not df_hw.empty else 0
        inactive_assets = len(df_hw[df_hw["Status"] == "Inactive"]) if not df_hw.empty else 0
        repair_assets = len(df_hw[df_hw["Status"] == "Repair"]) if not df_hw.empty else 0

        # ใช้ Streamlit metric แทน HTML เพื่อป้องกัน HTML render เป็น text
        m1, m2, m3, m4 = st.columns(4)

        with m1:
            st.metric("TOTAL ASSETS", total_assets)

        with m2:
            st.metric("ACTIVE", active_assets)

        with m3:
            st.metric("INACTIVE", inactive_assets)

        with m4:
            st.metric("REPAIR", repair_assets)

        col_search, col_add = st.columns([0.82, 0.18])

        with col_search:
            search = st.text_input(
                "",
                placeholder="🔍 ค้นหาชื่อพนักงาน, Hostname, Model, S/N...",
                label_visibility="collapsed"
            )

        with col_add:
            if admin_mode:
                if st.button("➕ เพิ่มคอมพิวเตอร์", use_container_width=True, type="primary"):
                    add_computer_dialog(sub)

        if search and not df_hw.empty:
            df_hw = df_hw[df_hw.astype(str).apply(
                lambda x: x.str.contains(search, case=False)
            ).any(axis=1)]

        cols = st.columns(3)

        for i, (idx, row) in enumerate(df_hw.iterrows()):

            with cols[i % 3]:

                name = row.get("field_3", "Unknown")
                initials = "".join([x[0] for x in name.split()[:2]]).upper()

                status = row.get("Status", "Active")
                badge_class = "badge-active" if status == "Active" else "badge-inactive"

                with st.container(border=True):
                    st.markdown(f"### 👤 {name}")
                    st.caption(f"🏢 {row.get('field_1','-')}  |  Status: {status}")
                    st.write(f"💻 Hostname: {row.get('field_6','-')}")
                    st.write(f"🏷️ Model: {row.get('field_7','-')}")
                    st.write(f"💾 RAM: {row.get('field_13','-')}")
                    st.write(f"🔢 Serial: {row.get('field_8','-')}")

                if admin_mode:
                    b1, b2 = st.columns(2)

                    with b1:
                        if st.button("🔍 ดูข้อมูล", key=f"view_{idx}", use_container_width=True):
                            show_pop_computer(row.to_dict())

                    with b2:
                        if st.button("✏️ แก้ไข", key=f"edit_{idx}", use_container_width=True):
                            edit_computer_dialog(row.to_dict(), sub)
                else:
                    st.caption("🔒 ดูรายละเอียดเพิ่มเติมได้เฉพาะผู้ดูแลระบบ")



    # -------------------------------------------------------
    # 🖨️ Stock หมึกพิมพ์
    # -------------------------------------------------------
    elif main_menu == "🖨️ Stock หมึกพิมพ์":
        page_header("🖨️", "Stock หมึกพิมพ์", "ระบบติดตามและเบิกจ่ายหมึกพิมพ์")

        df_ink = load_sp_data(INK_STOCK_LIST)

        # ---- Low Stock Alert Banner ----
        if not df_ink.empty and "Quantity" in df_ink.columns and "Min_Qty" in df_ink.columns:
            def _to_int(v, default=0):
                try: return int(v)
                except: return default
            low_mask = df_ink.apply(
                lambda r: _to_int(r.get("Quantity", 0)) <= _to_int(r.get("Min_Qty", INK_LOW_THRESHOLD)), axis=1
            )
            low_items = df_ink[low_mask]
            if not low_items.empty:
                low_names = ", ".join(
                    f"{r.get('Title','?')} ({r.get('Color','-')})"
                    for _, r in low_items.iterrows()
                )
                st.warning(f"⚠️ **สต็อกต่ำ / หมด:** {low_names}")

        st.markdown("---")

        # ---- Sidebar filters ----
        comp_filter  = st.sidebar.selectbox("🏢 บริษัท:", ["ALL"] + COMPANY_OPTIONS, key="ink_company_filter")
        color_filter = st.sidebar.selectbox("🎨 สี:", ["ALL"] + INK_COLOR_OPTIONS, key="ink_color_filter")
        show_history = st.sidebar.checkbox("📜 แสดงประวัติการเบิก", value=show_ink_history_only, key="ink_show_history")

        # ---- Admin: add button ----
        if admin_mode:
            col_title2, col_add2 = st.columns([0.8, 0.2])
            with col_add2:
                if st.button("➕ เพิ่มหมึกใหม่", use_container_width=True, type="primary"):
                    add_ink_dialog()

        # ---- Summary Metrics ----
        if not df_ink.empty:
            def _toi(v):
                try: return int(v)
                except: return 0
            total_items = len(df_ink)
            total_qty   = sum(_toi(r) for r in df_ink.get("Quantity", pd.Series([])))
            low_count   = int(low_mask.sum()) if not df_ink.empty and "Quantity" in df_ink.columns else 0
            out_count   = int((df_ink["Quantity"].apply(_toi) == 0).sum()) if "Quantity" in df_ink.columns else 0
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("📦 รายการทั้งหมด", total_items)
            m2.metric("🔢 จำนวนรวม", total_qty, help="รวมทุกสี/รุ่น")
            m3.metric("⚠️ ใกล้หมด", low_count)
            m4.metric("❌ หมดสต็อก", out_count)
            st.markdown("---")

        # ---- Filter + Search ----
        if not df_ink.empty:
            df_show = df_ink.copy()
            if comp_filter != "ALL" and "Company" in df_show.columns:
                df_show = df_show[(df_show["Company"] == comp_filter) | (df_show["Company"] == "ALL")]
            if color_filter != "ALL" and "Color" in df_show.columns:
                df_show = df_show[df_show["Color"] == color_filter]
            search_ink = st.text_input("🔍 ค้นหารุ่นหมึก หรือ รุ่นเครื่องพิมพ์...")
            if search_ink:
                df_show = df_show[df_show.astype(str).apply(
                    lambda x: x.str.contains(search_ink, case=False)
                ).any(axis=1)]

            if df_show.empty:
                st.info("ไม่พบรายการที่ตรงกัน")
            else:
                ink_cols = st.columns(2)
                requester = st.session_state.get("user_name", "Unknown")
                for i, (idx, row) in enumerate(df_show.iterrows()):
                    with ink_cols[i % 2]:
                        render_ink_card(row, idx, admin_mode, requester)
        else:
            st.info("ยังไม่มีข้อมูลสต็อกหมึก — กด ➕ เพิ่มหมึกใหม่ เพื่อเริ่มต้น")
            if not admin_mode:
                st.caption("(ต้องใช้สิทธิ์ Admin ในการเพิ่มข้อมูล)")

        # ---- History Section ----
        if show_history:
            st.markdown("---")
            st.subheader("📜 ประวัติการเบิก/เพิ่มสต็อก")
            df_hist = load_sp_data(INK_HISTORY_LIST)
            if not df_hist.empty:
                display_cols = [c for c in ["Timestamp", "Ink_Title", "Color", "Action", "Qty_Change", "Requester", "Note"] if c in df_hist.columns]
                rename_map   = {k: v for k, v in INK_HISTORY_FIELDS.items() if k in display_cols}
                df_hist_show = df_hist[display_cols].rename(columns=rename_map)
                if "วันเวลา" in df_hist_show.columns:
                    df_hist_show = df_hist_show.sort_values("วันเวลา", ascending=False)

                # Export history
                col_hist_title, col_hist_export = st.columns([0.8, 0.2])
                with col_hist_export:
                    buf_hist = io.StringIO()
                    df_hist_show.to_csv(buf_hist, index=False, encoding="utf-8-sig")
                    st.download_button(
                        "📥 Export CSV", buf_hist.getvalue(),
                        "ink_history.csv", "text/csv", use_container_width=True
                    )
                st.dataframe(df_hist_show, use_container_width=True, hide_index=True)
            else:
                st.info("ยังไม่มีประวัติการเบิก/เพิ่มสต็อก")

    # -------------------------------------------------------
    # 📂 NAS Drive Check
    # -------------------------------------------------------
    elif main_menu == "📂 NAS Drive Check":
        page_header("📂", "NAS Permission Analyzer", "ตรวจสอบสิทธิ์การเข้าถึงโฟลเดอร์บน NAS")
        st.info("🔒 ข้อมูลสิทธิ์ NAS เป็น Read-only — กรุณาแก้ไขผ่าน Synology DSM โดยตรง")
        st.markdown("---")

        if 'nas_df' not in st.session_state or st.session_state.nas_df is None:
            with st.spinner("กำลังดึงข้อมูลจาก NAS..."):
                df_result = load_nas_data()
                st.session_state.nas_df = df_result if df_result is not None else None
                if df_result is None:
                    st.error("ไม่สามารถเชื่อมต่อ NAS ได้")

        if st.session_state.nas_df is not None:
            display_df = st.session_state.nas_df.copy()

            st.markdown("""
            <style>
            .nas-hero-search{
                background:linear-gradient(135deg,#ffffff,#f8faff);
                border:1px solid #e2e8f0;
                border-radius:22px;
                padding:22px;
                margin-bottom:20px;
                box-shadow:0 10px 30px rgba(99,102,241,.08);
}

            .nas-modern-card{
                background:linear-gradient(180deg,#ffffff 0%, #fafbff 100%);
                border:1px solid #e2e8f0;
                border-radius:24px;
                padding:22px;
                margin-bottom:18px;
                box-shadow:0 8px 30px rgba(15,23,42,.05);
                transition:all .2s ease;
}

            .nas-modern-card:hover{
                transform:translateY(-2px);
                box-shadow:0 18px 40px rgba(99,102,241,.12);
}

            /* ป้องกัน block ว่างจาก markdown div */
            .nas-modern-card:empty{
                display:none !important;
                padding:0 !important;
                margin:0 !important;
                border:none !important;
}

            .nas-card-title{
                font-size:1.15rem;
                font-weight:800;
                color:#312e81;
                margin-top:8px;
}

            .nas-mini-stat{
                display:inline-flex;
                align-items:center;
                gap:6px;
                padding:7px 12px;
                border-radius:999px;
                background:#eef2ff;
                color:#4f46e5;
                font-size:.76rem;
                font-weight:700;
                margin-right:8px;
                margin-top:10px;
}

            .nas-section-title{
                font-size:.72rem;
                font-weight:800;
                letter-spacing:1px;
                text-transform:uppercase;
                color:#94a3b8;
                margin-bottom:10px;
}

            .nas-user-pill{
                display:inline-flex;
                align-items:center;
                padding:6px 12px;
                border-radius:999px;
                font-size:.76rem;
                font-weight:700;
                margin:4px;
}

            .nas-user-rw{
                background:rgba(99,102,241,.14);
                color:#4338ca;
                border:1px solid rgba(99,102,241,.20);
}

            .nas-user-ro{
                background:#dcfce7;
                color:#166534;
                border:1px solid #86efac;
}
            </style>
            """, unsafe_allow_html=True)

            total_shares = len(display_df)

            total_rw = 0
            total_ro = 0

            for _, row in display_df.iterrows():
                if row["Matched Employees"]:
                    for staff in row["Matched Employees"].split(", "):
                        if "Read/Write" in staff:
                            total_rw += 1
                        else:
                            total_ro += 1

            s1, s2, s3 = st.columns(3)
            with s1:
                st.metric("📁 Shares", total_shares)
            with s2:
                st.metric("🔐 Read / Write", total_rw)
            with s3:
                st.metric("👁 Read Only", total_ro)

            

            col_s, col_r = st.columns([0.82, 0.18])

            with col_s:
                search_term = st.text_input(
                    "🔎 Search User / Share Drive",
                    "",
                    placeholder="ค้นหา Share Drive หรือ Username..."
                )

            with col_r:


                if st.button("🔄 Refresh", use_container_width=True):
                    load_nas_data.clear()
                    st.session_state.nas_df = load_nas_data()
                    st.rerun()

            

            if search_term:
                display_df = display_df[
                    display_df["Share"].str.contains(search_term, case=False, na=False) |
                    display_df["Matched Employees"].str.contains(search_term, case=False, na=False) |
                    display_df["ACL Tags (Raw)"].str.contains(search_term, case=False, na=False)
                ]

            for idx, row in display_df.iterrows():

                rw_users = []
                ro_users = []

                raw_acl = str(row['ACL Tags (Raw)'])

                if raw_acl and raw_acl != "nan":

                    for item in [x.strip() for x in raw_acl.split(',')]:

                        m = re.search(r"^(.*?)\s*\((Read(?:/Write)?)\)", item)

                        if m:

                            entity = re.sub(
                                r'^\[\d+\]\s*(user|group):',
                                '',
                                m.group(1).strip()
                            )

                            entity = entity.replace('OPTIMALGROUP\\\\', '').strip()

                            permission = m.group(2)

                            if permission == "Read/Write":
                                rw_users.append(entity)
                            else:
                                ro_users.append(entity)

                st.markdown('<div class="nas-modern-card">', unsafe_allow_html=True)

                top1, top2 = st.columns([0.75, 0.25])

                with top1:
                    card_html = f"<div style='display:flex;align-items:center;gap:16px;'>" \
                        f"<div style='width:74px;height:74px;border-radius:20px;background:linear-gradient(135deg,#ede9fe,#c4b5fd);display:flex;align-items:center;justify-content:center;font-size:2rem;border:1px solid #c4b5fd;'>📁</div>" \
                        f"<div>" \
                        f"<div class='nas-card-title'>{row['Share']}</div>" \
                        f"<div class='nas-mini-stat'>👥 {len(rw_users)+len(ro_users)} Users</div>" \
                        f"<div class='nas-mini-stat'>🔐 {len(rw_users)} RW</div>" \
                        f"<div class='nas-mini-stat'>👁 {len(ro_users)} Read</div>" \
                        f"</div></div>"

                    st.markdown(card_html, unsafe_allow_html=True)

                with top2:

                    if st.button("🔎 รายละเอียด", key=f"acl_{idx}", use_container_width=True):

                        @st.dialog("📜 Authorized Users/Groups")
                        def show_acl_pop(raw):
                            if raw:
                                parsed = []
                                for item in [t.strip() for t in raw.split(',')]:
                                    m = re.search(r"^(.*?)\s*\((Read(?:/Write)?)\)", item)
                                    if m:
                                        e = re.sub(r'^\[\d+\]\s*(user|group):\s*', '', m.group(1).strip()).replace('OPTIMALGROUP\\', '').strip()
                                        if e:
                                            parsed.append({
                                                "Entity": e,
                                                "Permission": m.group(2)
})

                                if parsed:
                                    parsed_df = pd.DataFrame(parsed)

                                    st.dataframe(
                                        parsed_df,
                                        use_container_width=True,
                                        hide_index=True
                                    )

                                with st.expander("Raw ACL"):
                                    st.code(raw)

                        show_acl_pop(row['ACL Tags (Raw)'])

                
                if not rw_users and not ro_users:
                    st.info("ไม่พบผู้ใช้งาน")
                else:
                    st.markdown(
                        f"""
                        <div style='margin-top:10px;padding:14px 18px;border-radius:16px;
                        background:linear-gradient(135deg,#eef2ff,#f8faff);
                        border:1px solid #dbeafe;
                        color:#475569;
                        font-size:0.92rem;
                        font-weight:600;'>
                        🔐 พบผู้ใช้งานที่มีสิทธิ์ทั้งหมด <b>{len(rw_users)+len(ro_users)}</b> รายการ
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                # ปิด div ของ nas-modern-card เพื่อป้องกัน layout เพี้ยน/เกิดช่องว่างสีขาว
                st.markdown('</div>', unsafe_allow_html=True)



            
            # --------------------------------------------------
            # Export CSV / Excel
            # --------------------------------------------------
            export_rows = []

            for _, row in display_df.iterrows():

                raw_acl = str(row.get('ACL Tags (Raw)', ''))

                if not raw_acl or raw_acl == 'nan':
                    continue

                for item in [x.strip() for x in raw_acl.split(',')]:

                    m = re.search(r"^(.*?)\s*\((Read(?:/Write)?)\)", item)

                    if not m:
                        continue

                    entity = re.sub(
                        r'^\[\d+\]\s*(user|group):\s*',
                        '',
                        m.group(1).strip()
                    )

                    entity = entity.replace('OPTIMALGROUP\\\\', '').strip()
                    permission = m.group(2)

                    if search_term:
                        keyword = search_term.lower().strip()

                        if (
                            keyword not in row['Share'].lower() and
                            keyword not in entity.lower()
                        ):
                            continue

                    export_rows.append({
                        "Share Drive": row['Share'],
                        "Name": entity,
                        "Permission": permission
})

            export_df = pd.DataFrame(export_rows)

            if not export_df.empty:
                export_df = export_df.drop_duplicates()
                export_df = export_df.sort_values(
                    by=["Share Drive", "Name"]
                )

            csv_buf = io.StringIO()

            export_df.to_csv(
                csv_buf,
                index=False,
                encoding='utf-8-sig'
            )

            excel_buf = io.BytesIO()

            with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:

                export_df.to_excel(
                    writer,
                    index=False,
                    sheet_name='NAS Permissions'
                )

                ws = writer.sheets['NAS Permissions']

                for col in ws.columns:

                    max_length = 0
                    column = col[0].column_letter

                    for cell in col:
                        try:
                            max_length = max(max_length, len(str(cell.value)))
                        except:
                            pass

                    ws.column_dimensions[column].width = min(max_length + 5, 50)

                ws.freeze_panes = 'A2'
                ws.auto_filter.ref = ws.dimensions

            if admin_mode:
                st.divider()

                ex1, ex2 = st.columns(2)

                with ex1:
                    st.download_button(
                        "📥 Export CSV",
                        csv_buf.getvalue(),
                        "nas_acl_report.csv",
                        "text/csv",
                        use_container_width=True
                    )

                with ex2:
                    st.download_button(
                        "📊 Export Excel",
                        excel_buf.getvalue(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
            else:
                st.info("🔒 Export ข้อมูล NAS ได้เฉพาะผู้ดูแลระบบ")


    # -------------------------------------------------------
    # 🔑 Password Information
    # -------------------------------------------------------
    elif main_menu == "🔑 Password Information":
        page_header("🔑", "Password Information", "ข้อมูล Credentials และรหัสผ่านระบบ")

        with st.spinner("กำลังโหลด..."):
            pw_result = load_password_excel()
            pw_sheets, drive_id = pw_result if isinstance(pw_result, tuple) else ({}, None)

        if not pw_sheets or "_error" in pw_sheets:
            err = pw_sheets.get("_error", "ไม่ทราบสาเหตุ") if pw_sheets else "ไม่ได้รับข้อมูลจาก SharePoint"
            st.error(f"❌ ไม่สามารถโหลดไฟล์ได้")
            st.code(err, language="text")
            st.info(f"💡 ตรวจสอบ: ชื่อโฟลเดอร์ = '{SHAREPOINT_FOLDER}' / ชื่อไฟล์ = '{PASSWORD_FILE_NAME}'")
        else:
            sheet_names = list(pw_sheets.keys())
            selected_sheet = st.sidebar.selectbox("📋 หมวดหมู่:", sheet_names, key="pw_sheet_select")
            df_pw = pw_sheets[selected_sheet].copy()
            sheet_icon = get_sheet_icon(selected_sheet)

            col_title, col_add = st.columns([0.8, 0.2])
            with col_title:
                st.subheader(f"{sheet_icon} {selected_sheet}")
                st.caption(f"พบข้อมูลทั้งหมด {len(df_pw)} รายการ")
            with col_add:
                if admin_mode:
                    st.write("##")
                    if st.button("➕ เพิ่มรายการ", use_container_width=True, type="primary"):
                        add_password_dialog(selected_sheet, df_pw, drive_id, pw_sheets)

            st.markdown("---")

            if df_pw.empty:
                st.warning("ไม่มีข้อมูลในชีทนี้")
            else:
                card_cols = st.columns(2)
                for idx, row in df_pw.iterrows():
                    with card_cols[idx % 2]:
                        render_password_card(row, selected_sheet, idx, admin_mode, df_pw, drive_id, pw_sheets)
                        # แสดง edit dialog
                        if admin_mode and st.session_state.get(f"pw_edit_row_{selected_sheet}_{idx}"):
                            st.session_state.pop(f"pw_edit_row_{selected_sheet}_{idx}")
                            edit_password_dialog(row, idx, selected_sheet, df_pw, drive_id, pw_sheets)
