"""Microsoft Graph and SharePoint service helpers."""

import msal
import pandas as pd
import requests
import streamlit as st


# SharePoint Config
TENANT_ID = st.secrets["TENANT_ID"]
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
SHAREPOINT_DOMAIN = "optimalcoth.sharepoint.com"
SITE_NAME = "InformationTechnology"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
GRAPH_URL = "https://graph.microsoft.com/v1.0"


@st.cache_data(ttl=3600)
def get_access_token():
    app = msal.ConfidentialClientApplication(CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET)
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    return result.get("access_token")


def _escape_graph_filter_value(value: str) -> str:
    """Escape single quote for Microsoft Graph OData filter."""
    return str(value or "").replace("'", "''").strip()


def _graph_get(url, *, headers=None, params=None, timeout=30):
    """เรียก Microsoft Graph แบบรวม Error ให้ดูง่าย"""
    token = get_access_token()
    req_headers = {"Authorization": f"Bearer {token}"}
    if headers:
        req_headers.update(headers)
    res = requests.get(url, headers=req_headers, params=params, timeout=timeout)
    try:
        data = res.json()
    except Exception:
        data = {"error": {"message": res.text[:300]}}
    if res.status_code >= 400:
        msg = data.get("error", {}).get("message", str(data)) if isinstance(data, dict) else str(data)
        raise Exception(f"Graph HTTP {res.status_code}: {msg}")
    return data


@st.cache_data(ttl=1800, show_spinner=False)
def graph_find_user(user_identity: str):
    """หา User จาก UPN / Email / Display Name / Account name

    คืนค่า dict ที่มี id, displayName, userPrincipalName, mail
    """
    ident = str(user_identity or "").strip()
    if not ident:
        return None

    select_cols = "id,displayName,userPrincipalName,mail,mailNickname,jobTitle,department,companyName"

    # 1) ถ้าเป็น email/upn ให้เรียกตรงก่อน
    if "@" in ident:
        try:
            return _graph_get(
                f"{GRAPH_URL}/users/{ident}",
                params={"$select": select_cols},
            )
        except Exception:
            pass

    # 2) ถ้าเป็น account name เช่น Ratchaphruek.Ro ให้ลองเติม domain ที่ใช้ login อยู่
    login_email = st.session_state.get("user_email", "") if hasattr(st, "session_state") else ""
    login_domain = login_email.split("@")[-1] if "@" in login_email else ""
    if login_domain and "@" not in ident and " " not in ident:
        try:
            return _graph_get(
                f"{GRAPH_URL}/users/{ident}@{login_domain}",
                params={"$select": select_cols},
            )
        except Exception:
            pass

    # 3) ค้นหาจาก displayName / UPN / mailNickname
    safe = _escape_graph_filter_value(ident)
    filters = [
        f"startswith(displayName,'{safe}')",
        f"startswith(userPrincipalName,'{safe}')",
        f"startswith(mailNickname,'{safe}')",
    ]

    # ถ้าเป็นชื่อแบบมีจุด ให้ลองแปลงจุดเป็นเว้นวรรคด้วย
    if "." in ident:
        safe_space = _escape_graph_filter_value(ident.replace(".", " "))
        filters.append(f"startswith(displayName,'{safe_space}')")

    for flt in filters:
        try:
            data = _graph_get(
                f"{GRAPH_URL}/users",
                params={"$select": select_cols, "$top": 5, "$filter": flt},
            )
            users = data.get("value", []) if isinstance(data, dict) else []
            if users:
                return users[0]
        except Exception:
            continue

    return None


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
    """
    โหลดข้อมูลจาก SharePoint List

    Parameters
    ----------
    target_display_name : str

    Returns
    -------
    pandas.DataFrame
    """
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
