"""AD/LDAP, AD Agent, and firewall policy service helpers."""

import re

import pandas as pd
import requests
import streamlit as st

try:
    from ldap3 import ALL, SUBTREE, Connection, Server
except Exception:
    ALL = SUBTREE = Connection = Server = None

from services.microsoft_graph import GRAPH_URL, _graph_get, graph_find_user, load_sp_data


def _secret_bool(name: str, default=False) -> bool:
    value = st.secrets.get(name, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")

# AD / Firewall Policy Source
# ---------------------------------------------------------------------------
# AD_POLICY_SOURCE:
# - "ldap"  = query Domain Controller / AD Server directly via LDAP/LDAPS
# - "agent" = call internal AD Agent API
# - "graph" = Microsoft Graph / Entra ID
# - "auto"  = try ldap, then agent, then graph
AD_POLICY_SOURCE = st.secrets.get("AD_POLICY_SOURCE", "auto").lower().strip()

# LDAP / LDAPS direct AD settings
# Example:
# AD_LDAP_SERVER = "192.168.2.3"
# AD_LDAP_PORT = 389          # 636 for LDAPS
# AD_LDAP_USE_SSL = false     # true for LDAPS
# AD_DOMAIN = "optimalgroup.com"
# AD_BASE_DN = "DC=optimalgroup,DC=com"
# AD_BIND_USER = "OPTIMALGROUP\\svc_ad_reader" or "svc_ad_reader@optimalgroup.com"
# AD_BIND_PASSWORD = "..."
AD_LDAP_SERVER = st.secrets.get("AD_LDAP_SERVER", st.secrets.get("AD_SERVER", "")).strip()
AD_LDAP_USE_SSL = _secret_bool("AD_LDAP_USE_SSL", False)
AD_LDAP_PORT = int(st.secrets.get("AD_LDAP_PORT", 636 if AD_LDAP_USE_SSL else 389))
AD_DOMAIN = st.secrets.get("AD_DOMAIN", "").strip()
AD_BASE_DN = st.secrets.get("AD_BASE_DN", "").strip()
AD_BIND_USER = st.secrets.get("AD_BIND_USER", "").strip()
AD_BIND_PASSWORD = st.secrets.get("AD_BIND_PASSWORD", "")
AD_LDAP_TIMEOUT = int(st.secrets.get("AD_LDAP_TIMEOUT", 15))

# Optional internal AD Agent API settings
# Expected endpoints:
# GET {AD_AGENT_URL}/user-policy?user=<identity>
# Response: {"ok": true, "user": {...}, "groups": ["FW_Officer_D"], "policies": [...]}
AD_AGENT_URL = st.secrets.get("AD_AGENT_URL", "").rstrip("/")
AD_AGENT_TOKEN = st.secrets.get("AD_AGENT_TOKEN", "")


# Internet Policy Mapping
# -----------------------------------------------------------------------------
# ใช้สำหรับแสดงสิทธิ์ออก Internet จาก AD / Firewall Group
# แนวคิด: ให้ AD Group เป็น Source of Truth แล้ว Firewall และระบบนี้อ่านจาก Group เดียวกัน
# ถ้าบริษัทมี Policy เพิ่ม ให้เพิ่มชื่อ Group และคำอธิบายที่นี่ได้เลย
# -----------------------------------------------------------------------------
FW_POLICY_PREFIXES = ("FW_", "Firewall_", "Internet_")
FIREWALL_POLICY_MAPPING_LIST = st.secrets.get("FIREWALL_POLICY_MAPPING_LIST", "Firewall Policy Mapping")
FW_POLICY_MAP = {
    "FW_Officer_A": "Allow All Website",
    "FW_Officer_B": "Block Social Media",
    "FW_Officer_C": "Allow YouTube",
    "FW_Officer_D": "Allow Facebook",
    "FW_Officer_E": "Allow YouTube, Facebook",
    "FW_Manager": "Net True",
    "FW_IT": "IT Internet Policy",
    "FW_MD": "Management Internet Policy",
    "FW_Supervisor_B": "Supervisor Internet Policy",
    "FW_Conference": "Conference Room Internet Policy",
}
FW_POLICY_DEFAULT_DETAILS = {
    "FW_Officer_A": {
        "Policy Name": "Allow All Website",
        "Internet Level": "Full Access",
        "Allowed": "Web, Email, Business apps, YouTube, Facebook, Social media",
        "Blocked": "-",
        "Firewall Rule": "FW_Officer_A",
        "Description": "ใช้งาน Internet ได้เต็มตาม policy พนักงานกลุ่ม A",
        "Owner": "IT",
        "Last Updated": "",
    },
    "FW_Officer_B": {
        "Policy Name": "Block Social Media",
        "Internet Level": "Standard Access",
        "Allowed": "Web, Email, Business apps",
        "Blocked": "Facebook, TikTok, Instagram, Social media",
        "Firewall Rule": "FW_Officer_B",
        "Description": "ใช้งาน Internet ทั่วไปได้ แต่บล็อก Social Media",
        "Owner": "IT",
        "Last Updated": "",
    },
    "FW_Officer_C": {
        "Policy Name": "Allow YouTube",
        "Internet Level": "Standard + YouTube",
        "Allowed": "Web, Email, Business apps, YouTube",
        "Blocked": "Facebook, TikTok, Instagram",
        "Firewall Rule": "FW_Officer_C",
        "Description": "ใช้งานทั่วไปและ YouTube ได้ แต่ยังบล็อก Social Media อื่น",
        "Owner": "IT",
        "Last Updated": "",
    },
    "FW_Officer_D": {
        "Policy Name": "Allow Facebook",
        "Internet Level": "Standard + Facebook",
        "Allowed": "Web, Email, Business apps, Facebook",
        "Blocked": "YouTube, TikTok, Instagram",
        "Firewall Rule": "FW_Officer_D",
        "Description": "ใช้งานทั่วไปและ Facebook ได้",
        "Owner": "IT",
        "Last Updated": "",
    },
    "FW_Officer_E": {
        "Policy Name": "Allow YouTube, Facebook",
        "Internet Level": "Standard + Media",
        "Allowed": "Web, Email, Business apps, YouTube, Facebook",
        "Blocked": "TikTok, Instagram",
        "Firewall Rule": "FW_Officer_E",
        "Description": "ใช้งานทั่วไปพร้อม YouTube และ Facebook ได้",
        "Owner": "IT",
        "Last Updated": "",
    },
    "FW_Manager": {
        "Policy Name": "Net True",
        "Internet Level": "Manager Access",
        "Allowed": "Web, Email, Business apps, approved management access",
        "Blocked": "ตาม policy firewall",
        "Firewall Rule": "FW_Manager",
        "Description": "Policy สำหรับระดับ Manager",
        "Owner": "IT",
        "Last Updated": "",
    },
    "FW_IT": {
        "Policy Name": "IT Internet Policy",
        "Internet Level": "IT Admin Access",
        "Allowed": "All standard access, admin tools, remote support, vendor sites",
        "Blocked": "ตาม security baseline",
        "Firewall Rule": "FW_IT",
        "Description": "สิทธิ์ Internet สำหรับทีม IT",
        "Owner": "IT",
        "Last Updated": "",
    },
    "FW_MD": {
        "Policy Name": "Management Internet Policy",
        "Internet Level": "Management Access",
        "Allowed": "Business apps, web, email, executive-approved services",
        "Blocked": "ตาม policy firewall",
        "Firewall Rule": "FW_MD",
        "Description": "สิทธิ์ Internet สำหรับผู้บริหาร",
        "Owner": "IT",
        "Last Updated": "",
    },
    "FW_Supervisor_B": {
        "Policy Name": "Supervisor Internet Policy",
        "Internet Level": "Supervisor Access",
        "Allowed": "Web, Email, Business apps, approved team resources",
        "Blocked": "Social media ตามข้อกำหนด",
        "Firewall Rule": "FW_Supervisor_B",
        "Description": "สิทธิ์ Internet สำหรับ Supervisor",
        "Owner": "IT",
        "Last Updated": "",
    },
    "FW_Conference": {
        "Policy Name": "Conference Room Internet Policy",
        "Internet Level": "Meeting Room Access",
        "Allowed": "Meeting apps, web, presentation services",
        "Blocked": "High-risk categories ตาม policy firewall",
        "Firewall Rule": "FW_Conference",
        "Description": "สิทธิ์ Internet สำหรับอุปกรณ์ห้องประชุม",
        "Owner": "IT",
        "Last Updated": "",
    },
}


# =============================================================================
# SECTION 02.1 : AD / FIREWALL INTERNET POLICY
# ดึง Group Membership จาก Microsoft Entra ID / Active Directory ผ่าน Microsoft Graph
# แล้วแปลง Group ที่ขึ้นต้นด้วย FW_ เป็น Internet Policy
# =============================================================================
def _escape_ldap_filter_value(value: str) -> str:
    """Escape special characters for LDAP filter values."""
    text = str(value or "")
    return (
        text.replace("\\", r"\5c")
            .replace("*", r"\2a")
            .replace("(", r"\28")
            .replace(")", r"\29")
            .replace("\x00", r"\00")
    )


def _extract_cn_from_dn(dn: str) -> str:
    """Extract CN from a distinguishedName like CN=FW_Officer_D,OU=Groups,..."""
    text = str(dn or "").strip()
    if not text:
        return ""
    match = re.match(r"CN=((?:\\.|[^,])+)", text, flags=re.IGNORECASE)
    if not match:
        return text
    return match.group(1).replace(r"\,", ",").replace(r"\\", "\\").strip()


def _normalize_ad_identity(user_identity: str):
    ident = str(user_identity or "").strip()
    if "\\" in ident:
        ident = ident.split("\\")[-1].strip()
    return ident


def _ldap_enabled():
    return bool(AD_LDAP_SERVER and AD_BASE_DN and AD_BIND_USER and AD_BIND_PASSWORD)


def _ad_agent_enabled():
    return bool(AD_AGENT_URL)


def _source_order():
    if AD_POLICY_SOURCE in ("ldap", "agent", "graph"):
        return [AD_POLICY_SOURCE]
    return ["ldap", "agent", "graph"]


def _make_ldap_connection():
    if Server is None or Connection is None:
        raise Exception("ยังไม่ได้ติดตั้ง Python package 'ldap3' ใน environment ที่รันแอป")
    if not _ldap_enabled():
        raise Exception("ยังไม่ได้ตั้งค่า AD_LDAP_SERVER / AD_BASE_DN / AD_BIND_USER / AD_BIND_PASSWORD")

    server = Server(
        AD_LDAP_SERVER,
        port=AD_LDAP_PORT,
        use_ssl=AD_LDAP_USE_SSL,
        get_info=ALL,
        connect_timeout=AD_LDAP_TIMEOUT,
    )
    conn = Connection(
        server,
        user=AD_BIND_USER,
        password=AD_BIND_PASSWORD,
        auto_bind=True,
        receive_timeout=AD_LDAP_TIMEOUT,
    )
    return conn


@st.cache_data(ttl=1800, show_spinner=False)
def ldap_find_user(user_identity: str):
    """Find a user directly from AD LDAP and return core attributes."""
    ident = _normalize_ad_identity(user_identity)
    if not ident:
        return None

    local_part = ident.split("@")[0] if "@" in ident else ident
    safe_ident = _escape_ldap_filter_value(ident)
    safe_local = _escape_ldap_filter_value(local_part)

    filters = [
        f"(userPrincipalName={safe_ident})",
        f"(mail={safe_ident})",
        f"(sAMAccountName={safe_local})",
        f"(cn={safe_ident})",
        f"(displayName={safe_ident})",
        f"(displayName={_escape_ldap_filter_value(ident.replace('.', ' '))})",
    ]
    search_filter = "(&(objectCategory=person)(objectClass=user)(|" + "".join(filters) + "))"
    attributes = [
        "displayName",
        "userPrincipalName",
        "mail",
        "sAMAccountName",
        "distinguishedName",
        "memberOf",
        "department",
        "title",
        "company",
        "enabled",
    ]

    conn = _make_ldap_connection()
    try:
        ok = conn.search(
            search_base=AD_BASE_DN,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=attributes,
            size_limit=1,
        )
        if not ok or not conn.entries:
            return None

        entry = conn.entries[0]
        data = entry.entry_attributes_as_dict
        return {
            "id": str(data.get("distinguishedName", [""])[0] if isinstance(data.get("distinguishedName"), list) else data.get("distinguishedName", "")),
            "displayName": str(data.get("displayName", [""])[0] if isinstance(data.get("displayName"), list) and data.get("displayName") else data.get("displayName", "")),
            "userPrincipalName": str(data.get("userPrincipalName", [""])[0] if isinstance(data.get("userPrincipalName"), list) and data.get("userPrincipalName") else data.get("userPrincipalName", "")),
            "mail": str(data.get("mail", [""])[0] if isinstance(data.get("mail"), list) and data.get("mail") else data.get("mail", "")),
            "sAMAccountName": str(data.get("sAMAccountName", [""])[0] if isinstance(data.get("sAMAccountName"), list) and data.get("sAMAccountName") else data.get("sAMAccountName", "")),
            "department": str(data.get("department", [""])[0] if isinstance(data.get("department"), list) and data.get("department") else data.get("department", "")),
            "title": str(data.get("title", [""])[0] if isinstance(data.get("title"), list) and data.get("title") else data.get("title", "")),
            "company": str(data.get("company", [""])[0] if isinstance(data.get("company"), list) and data.get("company") else data.get("company", "")),
            "memberOf": data.get("memberOf", []) or [],
        }
    finally:
        conn.unbind()


@st.cache_data(ttl=1800, show_spinner=False)
def get_ldap_group_names_for_user(user_identity: str):
    """Return direct AD memberOf group names from Domain Controller."""
    user_obj = ldap_find_user(user_identity)
    if not user_obj:
        return []
    groups = [_extract_cn_from_dn(dn) for dn in user_obj.get("memberOf", [])]
    return sorted({g for g in groups if g}, key=lambda x: x.lower())


@st.cache_data(ttl=900, show_spinner=False)
def get_ad_agent_policy_summary(user_identity: str):
    """Read user/group/policy data from an internal AD Agent API if configured."""
    if not _ad_agent_enabled():
        raise Exception("ยังไม่ได้ตั้งค่า AD_AGENT_URL")

    headers = {}
    if AD_AGENT_TOKEN:
        headers["X-API-Token"] = AD_AGENT_TOKEN
        headers["Authorization"] = f"Bearer {AD_AGENT_TOKEN}"

    resp = requests.get(
        f"{AD_AGENT_URL}/user-policy",
        headers=headers,
        params={"user": user_identity},
        timeout=AD_LDAP_TIMEOUT,
    )
    try:
        data = resp.json()
    except Exception:
        data = {"error": resp.text[:300]}
    if resp.status_code >= 400:
        raise Exception(f"AD Agent HTTP {resp.status_code}: {data}")
    if not isinstance(data, dict):
        raise Exception("AD Agent response format ไม่ถูกต้อง")

    groups = data.get("groups", []) or []

    # รองรับ AD Agent ทั้ง 2 รูปแบบ:
    # 1) {"user": {...}, "groups": [...], "policies": [...]}
    # 2) {"displayName": "...", "mail": "...", "groups": [...], "internet_policy": [...]}
    user_obj = data.get("user") if isinstance(data.get("user"), dict) else {}
    if not user_obj and isinstance(data.get("User"), dict):
        user_obj = data.get("User")
    if not user_obj:
        # AD Agent deployments do not always use the same casing/field names.
        folded_data = {str(key).casefold(): value for key, value in data.items()}
        def _agent_value(*names):
            for name in names:
                value = data.get(name)
                if value in (None, ""):
                    value = folded_data.get(str(name).casefold())
                if isinstance(value, list):
                    value = value[0] if value else ""
                if value not in (None, ""):
                    return value
            return ""
        user_obj = {
            "displayName": _agent_value("displayName", "display_name"),
            "userPrincipalName": _agent_value("userPrincipalName", "upn"),
            "mail": _agent_value("mail", "email"),
            "sAMAccountName": _agent_value("sAMAccountName", "samAccountName", "account"),
            "department": _agent_value("department", "departmentName"),
            "title": _agent_value("title", "jobTitle"),
            "company": _agent_value("company", "companyName"),
        }

    policies = data.get("policies") or get_internet_policies_from_groups(groups)

    return {
        "ok": bool(data.get("ok", True)),
        "source": "AD Agent",
        "user": user_obj,
        "groups": groups,
        "policies": policies,
        "error": data.get("error", ""),
    }



@st.cache_data(ttl=900, show_spinner=False)
def get_ad_agent_policy_users(policy_name: str):
    """Read all users who are members of a firewall policy group from AD Agent.

    Expected AD Agent endpoint:
    GET {AD_AGENT_URL}/policy-users?policy=FW_Officer_A
    Response:
    {
      "ok": true,
      "policy": "FW_Officer_A",
      "description": "Allow All Website",
      "users": [{"displayName": "...", "mail": "...", "sAMAccountName": "..."}]
    }
    """
    if not _ad_agent_enabled():
        raise Exception("ยังไม่ได้ตั้งค่า AD_AGENT_URL")

    policy = str(policy_name or "").strip()
    if not policy:
        raise Exception("กรุณาระบุชื่อ Policy เช่น FW_Officer_A")

    headers = {}
    if AD_AGENT_TOKEN:
        headers["X-API-Token"] = AD_AGENT_TOKEN
        headers["Authorization"] = f"Bearer {AD_AGENT_TOKEN}"

    resp = requests.get(
        f"{AD_AGENT_URL}/policy-users",
        headers=headers,
        params={"policy": policy},
        timeout=AD_LDAP_TIMEOUT,
    )
    try:
        data = resp.json()
    except Exception:
        data = {"error": resp.text[:300]}

    if resp.status_code == 404:
        raise Exception("AD Agent ยังไม่มี endpoint /policy-users — กรุณาอัปเดต ad_agent.py บน NAS เป็นเวอร์ชันที่รองรับค้นหา Policy")
    if resp.status_code >= 400:
        raise Exception(f"AD Agent HTTP {resp.status_code}: {data}")
    if not isinstance(data, dict):
        raise Exception("AD Agent response format ไม่ถูกต้อง")

    users = data.get("users", []) or []
    if not isinstance(users, list):
        users = []

    return {
        "ok": bool(data.get("ok", True)),
        "source": "AD Agent",
        "policy": data.get("policy", policy),
        "description": data.get("description", FW_POLICY_MAP.get(policy, "")),
        "users": users,
        "count": data.get("count", len(users)),
        "error": data.get("error", ""),
    }


def get_policy_users_summary(policy_name: str):
    """คืนรายชื่อ User ทั้งหมดที่ได้ Policy นี้."""
    errors = []
    policy = str(policy_name or "").strip()

    if not policy:
        return {
            "ok": False,
            "source": "",
            "policy": "",
            "description": "",
            "users": [],
            "count": 0,
            "error": "กรุณาระบุชื่อ Policy",
        }

    # Streamlit Cloud ควรใช้ AD Agent เป็นหลัก เพราะเข้า IP ภายใน/LDAP ตรงไม่ได้
    try:
        if _ad_agent_enabled():
            result = get_ad_agent_policy_users(policy)
            if result.get("ok"):
                return result
            errors.append(f"AD Agent: {result.get('error', '')}")
        else:
            errors.append("AD Agent skipped: ยังไม่ได้ตั้งค่า AD_AGENT_URL")
    except Exception as e:
        errors.append(f"AD Agent: {e}")

    return {
        "ok": False,
        "source": "",
        "policy": policy,
        "description": FW_POLICY_MAP.get(policy, ""),
        "users": [],
        "count": 0,
        "error": " | ".join(errors) if errors else "ไม่พบข้อมูล Policy",
    }


@st.cache_data(ttl=1800, show_spinner=False)
def get_ad_group_names_for_user(user_identity: str):
    """คืนรายชื่อ AD / Entra ID Groups ที่ User เป็นสมาชิกอยู่

    ต้องให้ App Registration มีสิทธิ์ Microsoft Graph อย่างน้อย:
    - User.Read.All
    - GroupMember.Read.All หรือ Directory.Read.All
    และกด Admin consent แล้ว
    """
    user_obj = graph_find_user(user_identity)
    if not user_obj or not user_obj.get("id"):
        return []

    groups = []
    url = f"{GRAPH_URL}/users/{user_obj['id']}/transitiveMemberOf/microsoft.graph.group"
    params = {"$select": "displayName", "$top": 999}

    while url:
        data = _graph_get(url, params=params)
        for item in data.get("value", []):
            name = str(item.get("displayName", "")).strip()
            if name:
                groups.append(name)
        url = data.get("@odata.nextLink")
        params = None

    return sorted(set(groups), key=lambda x: x.lower())


def _first_policy_value(row, aliases, default=""):
    """Return the first non-empty value from possible SharePoint column names."""
    for key in aliases:
        value = row.get(key, "") if hasattr(row, "get") else ""
        value = str(value or "").strip()
        if value and value.lower() not in ("nan", "none", "-"):
            return value
    return default


def _default_firewall_policy_rows():
    rows = []
    for group_name, description in FW_POLICY_MAP.items():
        detail = dict(FW_POLICY_DEFAULT_DETAILS.get(group_name, {}))
        rows.append({
            "AD Group": group_name,
            "Policy Name": detail.get("Policy Name", description),
            "Internet Level": detail.get("Internet Level", ""),
            "Allowed": detail.get("Allowed", ""),
            "Blocked": detail.get("Blocked", ""),
            "Firewall Rule": detail.get("Firewall Rule", group_name),
            "Description": detail.get("Description", description),
            "Owner": detail.get("Owner", "IT"),
            "Last Updated": detail.get("Last Updated", ""),
            "Source": "Default Mapping",
        })
    return rows


@st.cache_data(ttl=1800, show_spinner=False)
def load_firewall_policy_mapping():
    """Load detailed firewall policy mapping from SharePoint, fallback to defaults."""
    default_rows = _default_firewall_policy_rows()

    try:
        df_map = load_sp_data(FIREWALL_POLICY_MAPPING_LIST)
    except Exception:
        df_map = pd.DataFrame()

    if df_map is None or df_map.empty:
        return default_rows

    rows = []
    for _, row in df_map.iterrows():
        ad_group = _first_policy_value(row, ["AD Group", "ADGroup", "Group", "Group Name", "Title", "field_1"])
        if not ad_group:
            continue

        fallback_description = FW_POLICY_MAP.get(ad_group, "Firewall / Internet policy group")
        rows.append({
            "AD Group": ad_group,
            "Policy Name": _first_policy_value(row, ["Policy Name", "PolicyName", "Policy", "Title"], ad_group),
            "Internet Level": _first_policy_value(row, ["Internet Level", "InternetLevel", "Level", "Access Level", "field_2"]),
            "Allowed": _first_policy_value(row, ["Allowed", "Allow", "Allow List", "AllowList", "Can Access", "field_3"]),
            "Blocked": _first_policy_value(row, ["Blocked", "Block", "Block List", "BlockList", "Deny", "field_4"]),
            "Firewall Rule": _first_policy_value(row, ["Firewall Rule", "FirewallRule", "Rule", "Rule Name", "field_5"], ad_group),
            "Description": _first_policy_value(row, ["Description", "Policy Description", "PolicyDescription", "Detail", "field_6"], fallback_description),
            "Owner": _first_policy_value(row, ["Owner", "Responsible", "Managed By", "ManagedBy", "field_7"], "IT"),
            "Last Updated": _first_policy_value(row, ["Last Updated", "LastUpdated", "Modified", "Updated", "field_8"]),
            "Source": "SharePoint Mapping",
        })

    return rows or default_rows


def get_firewall_policy_mapping_dict():
    return {
        str(row.get("AD Group", "")).strip().lower(): row
        for row in load_firewall_policy_mapping()
        if str(row.get("AD Group", "")).strip()
    }


def get_internet_policies_from_groups(group_names):
    """แปลง AD Groups เป็น Internet Policy rows พร้อมรายละเอียดว่า Policy ทำอะไรได้บ้าง"""
    mapping = get_firewall_policy_mapping_dict()
    policies = []

    for group_name in group_names or []:
        g = str(group_name).strip()
        if not g:
            continue

        is_policy_group = g.lower() in mapping or any(g.upper().startswith(p.upper()) for p in FW_POLICY_PREFIXES)
        if not is_policy_group:
            continue

        detail = dict(mapping.get(g.lower(), {}))
        if not detail:
            detail = {
                "AD Group": g,
                "Policy Name": FW_POLICY_MAP.get(g, g),
                "Internet Level": "",
                "Allowed": "",
                "Blocked": "",
                "Firewall Rule": g,
                "Description": FW_POLICY_MAP.get(g, "Firewall / Internet policy group"),
                "Owner": "IT",
                "Last Updated": "",
                "Source": "AD Group (unmapped)",
            }

        policies.append({
            "Policy Internet": g,
            "AD Group": detail.get("AD Group", g),
            "Policy Name": detail.get("Policy Name", FW_POLICY_MAP.get(g, g)),
            "Internet Level": detail.get("Internet Level", ""),
            "Allowed": detail.get("Allowed", ""),
            "Blocked": detail.get("Blocked", ""),
            "Firewall Rule": detail.get("Firewall Rule", g),
            "Description": detail.get("Description", FW_POLICY_MAP.get(g, "Firewall / Internet policy group")),
            "Owner": detail.get("Owner", ""),
            "Last Updated": detail.get("Last Updated", ""),
            "Source": detail.get("Source", "AD Group"),
        })

    return policies


def get_user_internet_policy_summary(user_identity: str):
    """คืนสรุป Internet Policy ของ User จาก AD / Agent / Graph ตาม source ที่ตั้งค่าไว้"""
    errors = []

    for source in _source_order():
        try:
            if source == "ldap":
                if not _ldap_enabled():
                    errors.append("LDAP skipped: ยังไม่ได้ตั้งค่า LDAP secrets")
                    continue
                user_obj = ldap_find_user(user_identity)
                if not user_obj:
                    errors.append("LDAP: ไม่พบ User ใน AD Server")
                    continue
                groups = get_ldap_group_names_for_user(user_identity)
                policies = get_internet_policies_from_groups(groups)
                return {
                    "ok": True,
                    "source": "AD LDAP",
                    "user": user_obj,
                    "groups": groups,
                    "policies": policies,
                    "error": "",
                }

            if source == "agent":
                if not _ad_agent_enabled():
                    errors.append("AD Agent skipped: ยังไม่ได้ตั้งค่า AD_AGENT_URL")
                    continue
                result = get_ad_agent_policy_summary(user_identity)
                if result.get("ok"):
                    return result
                errors.append(f"AD Agent: {result.get('error', '')}")
                continue

            if source == "graph":
                user_obj = graph_find_user(user_identity)
                if not user_obj or not user_obj.get("id"):
                    errors.append("Graph: ไม่พบ User ใน Entra ID")
                    continue
                groups = get_ad_group_names_for_user(user_identity)
                policies = get_internet_policies_from_groups(groups)
                return {
                    "ok": True,
                    "source": "Microsoft Graph",
                    "user": user_obj,
                    "groups": groups,
                    "policies": policies,
                    "error": "",
                }
        except Exception as e:
            errors.append(f"{source.upper()}: {e}")

    return {
        "ok": False,
        "source": "",
        "user": {},
        "groups": [],
        "policies": [],
        "error": " | ".join(errors) if errors else "ไม่พบข้อมูลจากทุก source",
    }


def format_policy_names(policies):
    if not policies:
        return "-"
    return ", ".join(sorted({p.get("Policy Internet", "") for p in policies if p.get("Policy Internet")}))


# VPN access groups are operational groups, not employee Internet policies.
# Keep them visible in AD / Firewall Policy, but omit them from NAS exports.
NAS_EXPORT_EXCLUDED_FIREWALL_POLICIES = {
    "FW_SSLVPN_Limitime",
    "FW_SSLVPN_Limitime2",
    "FW_SSLVPN_Limitime3",
    "FW_SSLVPN_Limitime4",
    "FW_SSLVPN_Limitime5",
    "FW_SSLVPN_ERPLife",
    "FW_SSLVPN_Alltime",
    "FW_IPSecVPN_Alltime",
    "FW_SSLVPN_Alltime-BP",
}
_NAS_EXPORT_EXCLUDED_FIREWALL_POLICIES_CASEFOLD = {
    policy.casefold() for policy in NAS_EXPORT_EXCLUDED_FIREWALL_POLICIES
}


def format_nas_export_policy_names(policies):
    """Format Firewall Policy for NAS CSV/Excel, excluding VPN access groups."""
    if not policies:
        return "-"

    policy_names = set()
    for policy in policies:
        if not isinstance(policy, dict):
            continue
        name = str(
            policy.get("Policy Internet")
            or policy.get("Policy Name")
            or policy.get("AD Group")
            or ""
        ).strip()
        if name and name.casefold() not in _NAS_EXPORT_EXCLUDED_FIREWALL_POLICIES_CASEFOLD:
            policy_names.add(name)

    return ", ".join(sorted(policy_names, key=str.casefold)) or "-"


def format_policy_descriptions(policies):
    if not policies:
        return "-"
    return ", ".join(sorted({p.get("Description", "") for p in policies if p.get("Description")}))


def format_policy_allowed(policies):
    if not policies:
        return "-"
    return ", ".join(sorted({p.get("Allowed", "") for p in policies if p.get("Allowed")}))


def format_policy_blocked(policies):
    if not policies:
        return "-"
    return ", ".join(sorted({p.get("Blocked", "") for p in policies if p.get("Blocked")}))
