"""Synology NAS, NAS Agent, and ACL service helpers."""

import datetime
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import paramiko
import requests
import streamlit as st

from services.microsoft_graph import load_sp_data


NAS_IP = st.secrets.get("NAS_IP", "")
NAS_PORT = int(st.secrets.get("NAS_PORT", 22))        # รองรับ SSH port custom เช่น 2222
SSH_USER = st.secrets.get("SSH_USER", "")
SSH_PWD = st.secrets.get("SSH_PWD", "")

NAS_BASE_URL = st.secrets.get("NAS_BASE_URL", st.secrets.get("NAS_URL", "")).rstrip("/")
NAS_USER = st.secrets.get("NAS_USER", SSH_USER)
NAS_PASSWORD = st.secrets.get("NAS_PASSWORD", SSH_PWD)
NAS_MODE = st.secrets.get("NAS_MODE", "api" if NAS_BASE_URL else "ssh").lower().strip()

# NAS Local API Agent Config
# ใช้สำหรับอ่าน ACL จริงจาก synoacltool ผ่าน Agent ที่รันอยู่บน NAS
# Streamlit Secrets ตัวอย่าง:
# NAS_AGENT_URL   = "https://nas-agent.poonyaruk.co.th"
# NAS_AGENT_TOKEN = "รหัสเดียวกับ NAS_AGENT_TOKEN ใน Docker"
NAS_AGENT_URL = st.secrets.get("NAS_AGENT_URL", "").rstrip("/")
NAS_AGENT_TOKEN = st.secrets.get("NAS_AGENT_TOKEN", "")
NAS_AGENT_MODE = st.secrets.get("NAS_AGENT_MODE", "agent" if NAS_AGENT_URL else "").lower().strip()

# Force Agent-first mode: ป้องกัน Streamlit ไปเรียก DSM domain เดิม (nas-api) ตอนใช้ NAS Agent
AGENT_ONLY_MODE = NAS_MODE in ("agent", "nas_agent", "nas-agent") or NAS_AGENT_MODE == "agent"
NAS_SHARES_SECRET = st.secrets.get("NAS_SHARES", "")

MAX_THREADS = 6
NAS_TIMEOUT = int(st.secrets.get("NAS_TIMEOUT", 30))
SYNOACL_PATH = ""  # Deprecated: Streamlit ไม่เรียก synoacltool เองแล้ว ใช้ NAS Agent แทน


def _nas_api_enabled():
    """คืนค่า True เฉพาะเมื่อเลือกใช้ DSM API จริง ๆ

    หมายเหตุ: ถ้า NAS_MODE=agent ให้ปิด DSM API fallback เพื่อไม่ให้ไปเรียก
    nas-api.poonyaruk.co.th ซึ่งเป็น DSM route และทำให้ timeout บน Streamlit Cloud
    """
    if AGENT_ONLY_MODE:
        return False
    return NAS_MODE == "api" and bool(NAS_BASE_URL)


def _nas_agent_enabled():
    """คืนค่า True เมื่อกำหนด NAS_AGENT_URL เพื่ออ่าน ACL จริงผ่าน NAS Local API Agent"""
    return AGENT_ONLY_MODE or bool(NAS_AGENT_URL)


def _safe_json_response(resp, context="NAS API"):
    """แปลง Response เป็น JSON พร้อม Error ที่อ่านง่าย"""
    try:
        return resp.json()
    except Exception:
        preview = resp.text[:300] if getattr(resp, "text", None) else ""
        raise Exception(f"{context} ไม่ได้ตอบกลับเป็น JSON | HTTP {resp.status_code} | {preview}")


def synology_api_info():
    """ทดสอบว่า Synology WebAPI ผ่าน Cloudflare Tunnel ใช้งานได้หรือไม่"""
    if not NAS_BASE_URL:
        raise Exception("ยังไม่ได้ตั้งค่า NAS_BASE_URL ใน Streamlit secrets")

    resp = requests.get(
        f"{NAS_BASE_URL}/webapi/query.cgi",
        params={
            "api": "SYNO.API.Info",
            "version": "1",
            "method": "query",
            "query": "all",
        },
        timeout=NAS_TIMEOUT,
    )
    data = _safe_json_response(resp, "SYNO.API.Info")
    if not data.get("success"):
        raise Exception(f"SYNO.API.Info failed: {data}")
    return data


def synology_login(session="FileStation"):
    """Login DSM API แล้วคืนค่า SID"""
    if not NAS_BASE_URL:
        raise Exception("ยังไม่ได้ตั้งค่า NAS_BASE_URL ใน Streamlit secrets")
    if not NAS_USER or not NAS_PASSWORD:
        raise Exception("ยังไม่ได้ตั้งค่า NAS_USER / NAS_PASSWORD ใน Streamlit secrets")

    resp = requests.get(
        f"{NAS_BASE_URL}/webapi/auth.cgi",
        params={
            "api": "SYNO.API.Auth",
            "version": "7",
            "method": "login",
            "account": NAS_USER,
            "passwd": NAS_PASSWORD,
            "session": session,
            "format": "sid",
        },
        timeout=NAS_TIMEOUT,
    )
    data = _safe_json_response(resp, "SYNO.API.Auth")
    if not data.get("success"):
        raise Exception(f"NAS API Login failed: {data}")
    return data.get("data", {}).get("sid", "")


def synology_logout(sid, session="FileStation"):
    """Logout DSM API แบบ best-effort"""
    if not sid or not NAS_BASE_URL:
        return
    try:
        requests.get(
            f"{NAS_BASE_URL}/webapi/auth.cgi",
            params={
                "api": "SYNO.API.Auth",
                "version": "7",
                "method": "logout",
                "session": session,
                "_sid": sid,
            },
            timeout=10,
        )
    except Exception:
        pass


def synology_get_shares_api():
    """ดึงรายชื่อ Shared Folder ผ่าน Synology FileStation API"""
    sid = synology_login("FileStation")
    try:
        resp = requests.get(
            f"{NAS_BASE_URL}/webapi/entry.cgi",
            params={
                "api": "SYNO.FileStation.List",
                "version": "2",
                "method": "list_share",
                "_sid": sid,
            },
            timeout=NAS_TIMEOUT,
        )
        data = _safe_json_response(resp, "SYNO.FileStation.List")
        if not data.get("success"):
            raise Exception(f"list_share failed: {data}")

        shares = []
        for item in data.get("data", {}).get("shares", []):
            name = item.get("name") or item.get("path", "").strip("/")
            if name and not name.startswith("@"):
                shares.append(name)
        return sorted(set(shares))
    finally:
        synology_logout(sid, "FileStation")


def load_nas_data_api():
    """
    โหลดรายชื่อ Share ผ่าน DSM API เท่านั้น
    ใช้เป็น fallback เมื่อยังไม่ได้ตั้งค่า NAS Agent
    """
    synology_api_info()
    shares = synology_get_shares_api()

    rows = []
    for share in shares:
        rows.append({
            "Share": share,
            "ACL Tags (Raw)": "เชื่อมต่อผ่าน DSM API สำเร็จ — อ่าน Raw ACL ต้องใช้ NAS Agent หรือ SSH/synoacltool",
            "Matched Employees": "",
        })

    return pd.DataFrame(rows, columns=["Share", "ACL Tags (Raw)", "Matched Employees"]).sort_values("Share")


def nas_agent_health():
    """ตรวจสอบ NAS Local API Agent และยืนยันว่าเป็นเวอร์ชัน SSH"""
    if not NAS_AGENT_URL:
        raise Exception("ยังไม่ได้ตั้งค่า NAS_AGENT_URL ใน Streamlit secrets")

    resp = requests.get(
        f"{NAS_AGENT_URL}/health",
        timeout=NAS_TIMEOUT,
        headers={"Cache-Control": "no-cache"},
        params={"_": datetime.datetime.now().timestamp()},
    )
    data = _safe_json_response(resp, "NAS Agent /health")

    if data.get("status") != "ok":
        raise Exception(f"NAS Agent health failed: {data}")

    service_name = str(data.get("service", ""))
    if service_name and service_name != "nas-agent-ssh":
        raise Exception(
            "NAS Agent ยังเป็นเวอร์ชันเก่า "
            f"(service={service_name}) — กรุณา restart/recreate container ให้เป็น nas-agent-ssh"
        )

    return data


def nas_agent_get_shares():
    """ดึงรายชื่อ Shared Folder จาก NAS Agent (/shares)

    ถ้า Agent ยังไม่มี endpoint /shares สามารถใส่ Secrets เพิ่มได้:
    NAS_SHARES = "Share1,Share2,Share3"
    """
    if not NAS_AGENT_URL:
        raise Exception("ยังไม่ได้ตั้งค่า NAS_AGENT_URL ใน Streamlit secrets")
    if not NAS_AGENT_TOKEN:
        raise Exception("ยังไม่ได้ตั้งค่า NAS_AGENT_TOKEN ใน Streamlit secrets")

    headers = {"X-API-Token": NAS_AGENT_TOKEN}
    resp = requests.get(
        f"{NAS_AGENT_URL}/shares",
        headers=headers,
        timeout=NAS_TIMEOUT,
    )

    if resp.status_code == 404:
        if NAS_SHARES_SECRET:
            return sorted([x.strip() for x in NAS_SHARES_SECRET.split(",") if x.strip()])
        raise Exception(
            "NAS Agent ยังไม่มี endpoint /shares — กรุณาอัปเดต nas_agent.py หรือเพิ่ม NAS_SHARES ใน Secrets"
        )

    data = _safe_json_response(resp, "NAS Agent /shares")
    if resp.status_code != 200:
        raise Exception(f"NAS Agent /shares HTTP {resp.status_code}: {data}")

    shares = data.get("shares") or data.get("data") or []
    if not isinstance(shares, list):
        raise Exception(f"NAS Agent /shares รูปแบบข้อมูลไม่ถูกต้อง: {data}")

    return sorted(set(str(x).strip() for x in shares if str(x).strip() and not str(x).strip().startswith("@")))


def nas_agent_get_acl_payload(share):
    """ดึง Permission จาก NAS Agent

    รองรับ Agent เวอร์ชันใหม่ที่มี /share-permissions ก่อน
    ถ้า Agent ยังไม่มี endpoint นี้ จะ fallback เป็น /acl แบบเดิม
    """
    if not NAS_AGENT_URL:
        raise Exception("ยังไม่ได้ตั้งค่า NAS_AGENT_URL ใน Streamlit secrets")
    if not NAS_AGENT_TOKEN:
        raise Exception("ยังไม่ได้ตั้งค่า NAS_AGENT_TOKEN ใน Streamlit secrets")

    headers = {"X-API-Token": NAS_AGENT_TOKEN}

    # Agent ใหม่: คืน permissions ที่แยก Read/Write จาก Synology share privilege แล้ว
    for endpoint in ("share-permissions", "permissions"):
        try:
            resp = requests.get(
                f"{NAS_AGENT_URL}/{endpoint}",
                params={"share": share},
                headers=headers,
                timeout=NAS_TIMEOUT,
            )
            if resp.status_code == 404:
                continue
            data = _safe_json_response(resp, f"NAS Agent /{endpoint} share={share}")
            if resp.status_code != 200:
                raise Exception(f"NAS Agent /{endpoint} HTTP {resp.status_code}: {data}")
            return data
        except requests.exceptions.HTTPError:
            continue
        except Exception:
            # ถ้า endpoint ใหม่ยังไม่พร้อม ให้ลอง /acl ต่อ
            pass

    # Agent เดิม: คืน raw synoacltool
    resp = requests.get(
        f"{NAS_AGENT_URL}/acl",
        params={"share": share},
        headers=headers,
        timeout=NAS_TIMEOUT,
    )
    data = _safe_json_response(resp, f"NAS Agent /acl share={share}")

    if resp.status_code != 200:
        raise Exception(f"NAS Agent /acl HTTP {resp.status_code}: {data}")

    if data.get("returncode", 0) not in (0, None):
        raise Exception(f"synoacltool failed for {share}: {data.get('stderr', '')}")

    return data


def nas_agent_get_acl_raw(share):
    """ดึง Raw ACL จาก NAS Agent ซึ่งรัน synoacltool บน NAS"""
    data = nas_agent_get_acl_payload(share)
    return data.get("stdout") or data.get("acl") or ""


def _clean_nas_principal(name: str) -> str:
    """Normalize Synology ACL principal names.

    Examples:
    - OPTIMALGROUP\\Sasithorn.Su -> Sasithorn.Su
    - user:OPTIMALGROUP\\IT_Network -> IT_Network
    - group:administrators -> administrators
    """
    if name is None:
        return ""

    cleaned = str(name).strip()
    if not cleaned or cleaned.lower() in ("nan", "none", "null"):
        return ""

    # Remove optional prefix that may already be included in parsed text.
    cleaned = re.sub(r"^(user|group)\s*:\s*", "", cleaned, flags=re.I).strip()

    # Synology / AD principals are often DOMAIN\\name.
    if "\\" in cleaned:
        cleaned = cleaned.split("\\")[-1].strip()

    # Remove accidental surrounding quotes/spaces.
    cleaned = cleaned.strip().strip('"').strip("'").strip()

    return cleaned


def parse_nas_agent_permissions_payload(payload, employee_list=None):
    """แปลง payload จาก Agent เวอร์ชันใหม่เป็น ACL Tags และ Matched Employees

    payload ที่รองรับ:
    {
      "permissions": [
        {"entity": "User", "type": "user", "permission": "Read"},
        {"entity": "Group", "type": "group", "permission": "Read/Write"}
      ]
    }
    """
    employee_list = employee_list or []
    rows = payload.get("permissions") or payload.get("data") or []
    if not isinstance(rows, list) or not rows:
        return [], []

    acl_entries = []
    matched_employees = []

    for item in rows:
        if not isinstance(item, dict):
            continue
        entity = _clean_nas_principal(item.get("entity") or item.get("name") or item.get("principal") or "")
        if not entity:
            continue
        ptype = str(item.get("type") or item.get("kind") or "user").lower()
        perm_raw = str(item.get("permission") or item.get("access") or item.get("perm") or "").strip().lower()
        raw_blob = str(item.get("raw_permission") or item.get("permission_blob") or "").strip()

        # ถ้า Agent ส่ง raw_permission มาด้วย ให้แยก Read/Write จาก permission blob จริง
        # Read-only ของ Synology มักเป็น r-x---a-R-c-- ซึ่งมี c แต่ไม่ควรนับเป็น Write
        if raw_blob:
            if any(ch in raw_blob for ch in set("wpdDWo")):
                permission = "Read/Write"
            else:
                permission = "Read"
        elif perm_raw in ("rw", "readwrite", "read/write", "write", "read-write", "read_write"):
            permission = "Read/Write"
        elif perm_raw in ("ro", "read", "readonly", "read-only", "read_only"):
            permission = "Read"
        elif perm_raw in ("deny", "no", "na", "noaccess", "no access"):
            permission = "Deny"
        else:
            permission = "Read/Write" if "write" in perm_raw or perm_raw == "rw" else "Read"

        acl_entries.append(f"{ptype}:{entity} ({permission})")

        for emp in employee_list:
            emp_text = str(emp).strip()
            if emp_text and (entity.lower() in emp_text.lower() or emp_text.lower() in entity.lower()):
                matched_employees.append(f"{emp_text} ({permission})")

    return sorted(set(acl_entries), key=lambda x: x.lower()), sorted(set(matched_employees))


def parse_synoacl_output(raw, employee_list=None):
    """แปลงผลลัพธ์ synoacltool เป็น ACL Tags และ Matched Employees"""
    employee_list = employee_list or []

    if not raw:
        return [], []

    acl_entries = []

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue

        # ตัวอย่าง:
        # [0] user:ActiveBackup:allow:rwxpdDaARWc--:fd-- (level:0)
        # [4] group:OPTIMALGROUP\Domain Admins:allow:rwxpdDaARWc--:fd-- (level:0)
        m = re.search(
            r'(?:\[\d+\]\s*)?(user|group):(.+?):(allow|deny):([^:\s]+)',
            line,
            flags=re.I,
        )
        if not m:
            continue

        kind = m.group(1).lower()
        principal_name = _clean_nas_principal(m.group(2))
        action = m.group(3).lower()
        # ห้าม lower() permission blob เพราะตัวพิมพ์เล็ก/ใหญ่ของ synoacltool มีความหมายต่างกัน
        # ตัวอย่าง Read-only มักมี r/x/a/R/c ซึ่งเดิมโดนจับเป็น RW เพราะมีตัว a
        # จึงนับเป็น Read/Write เฉพาะสิทธิ์ที่เกี่ยวกับการเขียนจริง ๆ เท่านั้น
        perm_blob = m.group(4).strip()

        if not principal_name:
            continue

        writable_flags = set("wpdDWo")

        if action == "deny":
            permission = "Deny"
        elif any(ch in perm_blob for ch in writable_flags):
            permission = "Read/Write"
        else:
            permission = "Read"

        acl_entries.append(f"{kind}:{principal_name} ({permission})")

    acl_tags = sorted(set(acl_entries), key=lambda x: x.lower())

    matched_employees = []
    for entry in acl_tags:
        match = re.search(r"^(.*?)\s*\((Read(?:/Write)?|Deny)\)", entry)
        if not match:
            continue

        clean_entity = _clean_nas_principal(match.group(1))
        if not clean_entity:
            continue

        for emp in employee_list:
            emp_text = str(emp).strip()
            if not emp_text:
                continue
            if clean_entity.lower() in emp_text.lower() or emp_text.lower() in clean_entity.lower():
                matched_employees.append(f"{emp_text} ({match.group(2).strip()})")

    return acl_tags, sorted(set(matched_employees), key=lambda x: x.lower())


def fetch_acl_agent(share, employee_list):
    """อ่าน Permission ของ Share ผ่าน NAS Agent"""
    try:
        payload = nas_agent_get_acl_payload(share)

        # ถ้า Agent ใหม่ส่ง permissions มา ให้ใช้ผลนี้ก่อน เพราะแยก Read/Write จาก Synology share privilege ได้ตรงกว่า ACL ดิบ
        if isinstance(payload, dict) and (payload.get("permissions") or payload.get("data")):
            tags, matched = parse_nas_agent_permissions_payload(payload, employee_list)
        else:
            raw = payload.get("stdout") or payload.get("acl") or ""
            tags, matched = parse_synoacl_output(raw, employee_list)

        return share, tags, matched
    except Exception as e:
        # เก็บ error ลง raw เพื่อให้ดูรายละเอียดใน Popup ได้ ไม่ทำให้ทั้งหน้าล่ม
        return share, [f"NAS Agent Error: {e}"], []


def load_nas_data_agent():
    """โหลด NAS Data แบบสมบูรณ์: Shares จาก DSM API + ACL จาก NAS Agent"""
    nas_agent_health()

    # ใช้ NAS Agent ดึงรายชื่อ Share ก่อน เพื่อไม่ต้องพึ่ง DSM route (nas-api)
    try:
        shares = nas_agent_get_shares()
    except Exception as agent_share_e:
        if _nas_api_enabled():
            shares = synology_get_shares_api()
        else:
            raise Exception(str(agent_share_e))

    df_emp = load_sp_data("Employees")
    employees = df_emp['field_3'].dropna().unique().tolist() if not df_emp.empty and 'field_3' in df_emp.columns else []

    data = []
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = [executor.submit(fetch_acl_agent, s, employees) for s in shares]
        for future in as_completed(futures):
            share, tags, matched_emps = future.result()
            data.append({
                "Share": share,
                "ACL Tags (Raw)": ", ".join(sorted(tags, key=lambda x: x.lower())),
                "Matched Employees": ", ".join(sorted(matched_emps, key=lambda x: x.lower())),
            })

    return pd.DataFrame(data).sort_values("Share")


def create_ssh():
    """
    สร้าง SSH Connection ไปยัง Synology NAS

    ใช้เฉพาะกรณี:
    - NAS เปิด SSH ผ่าน VPN/Port Forward/Cloudflare Access TCP แล้ว
    - ต้องการอ่าน ACL ผ่าน synoacltool แบบละเอียด
    """

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            hostname=NAS_IP,
            port=NAS_PORT,
            username=SSH_USER,
            password=SSH_PWD,
            timeout=NAS_TIMEOUT,
            banner_timeout=NAS_TIMEOUT,
            auth_timeout=NAS_TIMEOUT
        )

        return ssh

    except Exception as e:
        raise Exception(
            f"NAS SSH Connection Failed | "
            f"Host={NAS_IP} Port={NAS_PORT} | {str(e)}"
        )


def run_command(ssh, cmd):
    full_cmd = f"sudo -S {cmd}"
    stdin, stdout, stderr = ssh.exec_command(full_cmd)
    stdin.write(SSH_PWD + "\n")
    stdin.flush()
    return stdout.read().decode('utf-8', errors='ignore'), stderr.read().decode('utf-8', errors='ignore')


def get_shares():
    try:
        ssh = create_ssh()
        output, _ = run_command(ssh, "ls /volume1")
        ssh.close()
        return [l.strip() for l in output.splitlines() if l.strip() and not l.startswith("@")]
    except Exception:
        return []


def fetch_acl(share, employee_list):
    try:
        ssh = create_ssh()
        raw, _ = run_command(ssh, f"/usr/syno/bin/synoacltool -get /volume1/{share}")
        ssh.close()
        if not raw:
            return share, [], []
        tags, matched = parse_synoacl_output(raw, employee_list)
        return share, tags, matched
    except Exception:
        return share, [], []


def get_nas_connection_status():
    """ใช้แสดงสถานะ NAS แบบสั้น ๆ ใน Dashboard/หน้า NAS"""
    if _nas_agent_enabled():
        try:
            health = nas_agent_health()
            return True, f"NAS Agent Connected: {NAS_AGENT_URL} ({health.get('service', '-')})"
        except Exception as e:
            return False, f"NAS Agent Failed: {e}"

    if _nas_api_enabled():
        try:
            synology_api_info()
            return True, f"DSM API Connected: {NAS_BASE_URL}"
        except Exception as e:
            return False, f"DSM API Failed: {e}"
    try:
        ssh = create_ssh()
        ssh.close()
        return True, f"SSH Connected: {NAS_IP}:{NAS_PORT}"
    except Exception as e:
        return False, str(e)

