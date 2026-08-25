import html
import re

import streamlit as st


def render_computer_asset(
    *,
    df_hw,
    list_name,
    admin_mode,
    show_pop_computer,
    add_computer_dialog,
    edit_computer_dialog,
    delete_computer_dialog,
):
    # UI REVISION: CA-ENTERPRISE-2026-06-22-R3
    # Compact single-row filters, fixed right-aligned pagination, and no column manager.
    # UI OWNER: Computer Asset only. SharePoint and CRUD functions remain unchanged.
    st.markdown("""
            <div class="ca-page"></div>
            <style>
            .stApp:has(.ca-page) [data-testid="stMainBlockContainer"]{background:transparent!important;padding-top:6px!important}
            .stApp:has(.ca-page) [data-testid="stHeader"],.stApp:has(.ca-page) [data-testid="stToolbar"]{display:none!important}
            .stApp:has(.ca-page) [data-testid="stVerticalBlock"]{gap:.58rem}.ca-page{display:none}
            .ca-header{height:102px;box-sizing:border-box;display:flex;align-items:center;gap:16px;padding:17px 22px;margin-bottom:12px;background:#FFF;border:1px solid #E2E8F0;border-radius:20px;box-shadow:0 10px 26px rgba(15,23,42,.055)}
            .ca-header-icon{width:58px;height:58px;flex:0 0 58px;display:grid;place-items:center;color:#4F46E5;background:#F3F5FF;border:1px solid #E0E7FF;border-radius:17px}.ca-header-icon svg{width:33px;height:33px;stroke:currentColor}
            .ca-header h1{margin:0 0 4px!important;color:#0F172A!important;font-size:25px!important;font-weight:800;letter-spacing:-.035em}.ca-header p{margin:0!important;color:#64748B!important;font-size:12.5px!important}
            .ca-metric-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;margin-bottom:12px}.ca-card{height:106px;box-sizing:border-box;position:relative;padding:14px;background:#FFF;border:1px solid #E2E8F0;border-radius:17px;box-shadow:0 7px 18px rgba(15,23,42,.04);overflow:hidden}.ca-card:after{content:"";position:absolute;inset:auto 0 0;height:3px;background:var(--tone)}
            .ca-card-icon{position:absolute;right:12px;top:12px;width:42px;height:42px;display:grid;place-items:center;border-radius:50%;color:var(--tone);background:var(--soft)}.ca-card-icon svg{width:22px;height:22px;stroke:currentColor}.ca-card-icon .ca-windows-logo{width:24px;height:24px;stroke:none}.ca-card-label{max-width:calc(100% - 44px);min-height:27px;color:#475569;font-size:11px;line-height:1.25;font-weight:700;overflow:hidden}.ca-card-value{margin-top:1px;color:#0F172A;font-size:25px;line-height:1;font-weight:850;letter-spacing:-.04em}.ca-card-foot{position:absolute;left:14px;right:14px;bottom:11px;display:flex;justify-content:space-between;color:#64748B;font-size:10.5px}.ca-card-foot strong{color:var(--tone)}
            .ca-search-panel{display:none}.ca-search-panel-title{margin:2px 0 7px;padding:0 2px;color:#334155;font-size:12px;font-weight:800}.ca-filter-row{display:none}
            .stApp:has(.ca-page) .stTextInput input,.stApp:has(.ca-page) .stSelectbox div[data-baseweb="select"]>div{height:44px!important;min-height:44px!important;border:1px solid #DDE5EF!important;border-radius:12px!important;background:#FFF!important;font-size:12px!important}.stApp:has(.ca-page) .stButton>button,.stApp:has(.ca-page) .stDownloadButton>button{height:40px;min-height:40px;border-radius:11px;border-color:#E2E8F0;font-size:12px;font-weight:700}.stApp:has(.ca-page) button[kind="primary"]{color:#FFF!important;border:0!important;background:linear-gradient(135deg,#3B82F6,#7C3AED)!important;box-shadow:0 7px 16px rgba(99,102,241,.20)}
            .ca-action-bar{height:52px;display:flex;align-items:center;justify-content:space-between;padding:0 14px;background:#FFF;border:1px solid #E2E8F0;border-bottom:0;border-radius:18px 18px 0 0;color:#334155;font-size:12px;font-weight:750}.ca-action-title{display:flex;align-items:center;gap:8px}.ca-action-title span{width:30px;height:30px;display:grid;place-items:center;border-radius:9px;background:#EEF2FF;color:#4F46E5}
            .ca-table{background:#FFF;border:1px solid #E2E8F0;border-radius:0 0 17px 17px;box-shadow:0 8px 22px rgba(15,23,42,.045);overflow:hidden}.ca-table-scroll{overflow:auto;max-height:560px}.ca-table table{width:100%;min-width:1120px;border-collapse:separate;border-spacing:0;table-layout:fixed;font-size:11px;color:#334155}.ca-table th{position:sticky;top:0;z-index:2;height:44px;padding:0 11px;text-align:left;background:#F8FAFC;color:#475569;font-size:10.5px;font-weight:800;border-bottom:1px solid #E2E8F0;white-space:nowrap}.ca-table td{height:44px;box-sizing:border-box;padding:0 11px;border-bottom:1px solid #EDF2F7;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ca-table tbody tr:hover td{background:#F8FAFF}
            .ca-status{display:inline-flex;align-items:center;gap:5px;padding:4px 8px;border-radius:999px;font-size:10px;font-weight:800}.ca-status:before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}.ca-status-online{background:#ECFDF5;color:#059669}.ca-status-offline{background:#FEF2F2;color:#DC2626}.ca-status-nouser{background:#FFF7ED;color:#D97706}.ca-row-actions{display:flex;gap:5px}.ca-row-action{width:25px;height:25px;display:grid;place-items:center;border:1px solid #E2E8F0;border-radius:8px;font-size:12px}.ca-view{color:#2563EB;background:#EFF6FF}.ca-edit{color:#7C3AED;background:#F5F3FF}.ca-delete{color:#EF4444;background:#FEF2F2}
            .ca-table-footer{height:52px;display:flex;align-items:center;justify-content:space-between;padding:0 13px;border-top:1px solid #E2E8F0;color:#64748B;font-size:11px}.ca-pages{display:flex;gap:5px}.ca-pages span{min-width:28px;height:28px;display:grid;place-items:center;border:1px solid #E2E8F0;border-radius:8px}.ca-pages .active{color:#FFF;border-color:#6366F1;background:linear-gradient(135deg,#6366F1,#7C3AED)}
            .stApp:has(.ca-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ca-native-grid){padding:0!important;border:1px solid #E2E8F0!important;border-radius:0 0 17px 17px!important;background:#FFF!important;box-shadow:0 8px 22px rgba(15,23,42,.045)!important;overflow:hidden}
            .stApp:has(.ca-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ca-native-grid)>div{padding:0!important}.ca-native-grid{display:none}.ca-native-head{height:42px;display:flex;align-items:center;padding:0 10px;color:#475569;background:#F8FAFC;font-size:11px;font-weight:800;white-space:nowrap}.ca-native-cell{height:42px;display:flex;align-items:center;padding:0 10px;color:#334155;font-size:11.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ca-native-status{height:42px;display:flex;align-items:center;padding-left:5px}.ca-native-divider{height:1px;margin:0;background:#EDF2F7}.ca-native-footer{height:44px;display:flex;align-items:center;justify-content:space-between;padding:0 14px;color:#64748B;font-size:10.5px;border-top:1px solid #E2E8F0}.stApp:has(.ca-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ca-native-grid) [data-testid="stVerticalBlock"]{gap:0!important}.stApp:has(.ca-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ca-native-grid) [data-testid="stElementContainer"]{margin:0!important}.stApp:has(.ca-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ca-native-grid) .stButton{display:flex!important;align-items:center!important;justify-content:center!important}.stApp:has(.ca-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ca-native-grid) .stButton>button{width:28px!important;min-width:28px!important;max-width:28px!important;height:28px!important;min-height:28px!important;max-height:28px!important;padding:0!important;margin:0 auto!important;border-radius:8px!important;box-shadow:none!important;overflow:hidden!important}.stApp:has(.ca-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ca-native-grid) .stButton>button p{font-size:0!important;line-height:0!important;margin:0!important;color:transparent!important}.stApp:has(.ca-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ca-native-grid) .stButton>button span[data-testid="stIconMaterial"]{display:block!important;font-size:16px!important;line-height:1!important;color:currentColor!important}.stApp:has(.ca-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ca-native-grid) [data-testid="stHorizontalBlock"]{gap:0!important}.stApp:has(.ca-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ca-native-grid) [data-testid="column"]{border-right:1px solid #EDF2F7}.stApp:has(.ca-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ca-native-grid) [data-testid="column"]:last-child{border-right:0}.stApp:has(.ca-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ca-native-grid) [data-testid="column"]:last-child [data-testid="stHorizontalBlock"] [data-testid="column"]{border-right:0!important}.stApp:has(.ca-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ca-native-grid) [data-testid="column"]:last-child [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(1) button{color:#2563EB!important;background:#EFF6FF!important}.stApp:has(.ca-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ca-native-grid) [data-testid="column"]:last-child [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(2) button{color:#7C3AED!important;background:#F5F3FF!important}.stApp:has(.ca-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ca-native-grid) [data-testid="column"]:last-child [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(3) button{color:#DC2626!important;background:#FEF2F2!important}
            .ca-action-marker{display:none}.stApp:has(.ca-page) [data-testid="stVerticalBlock"]:has(.ca-action-marker) .stButton{display:flex!important;align-items:center!important;justify-content:center!important}.stApp:has(.ca-page) [data-testid="stVerticalBlock"]:has(.ca-action-marker) .stButton>button{width:32px!important;min-width:32px!important;max-width:32px!important;height:32px!important;min-height:32px!important;max-height:32px!important;padding:0!important;margin:0 auto!important;border:1px solid transparent!important;border-radius:10px!important;box-shadow:none!important;overflow:hidden!important}.stApp:has(.ca-page) [data-testid="stVerticalBlock"]:has(.ca-action-marker) .stButton>button p{font-size:0!important;line-height:0!important;margin:0!important;color:transparent!important}.stApp:has(.ca-page) [data-testid="stVerticalBlock"]:has(.ca-action-marker) .stButton>button span[data-testid="stIconMaterial"]{display:block!important;font-size:17px!important;line-height:1!important;color:currentColor!important}.stApp:has(.ca-page) [data-testid="stVerticalBlock"]:has(.ca-action-view) button{color:#2563EB!important;background:#EFF6FF!important;border-color:#DBEAFE!important}.stApp:has(.ca-page) [data-testid="stVerticalBlock"]:has(.ca-action-edit) button{color:#7C3AED!important;background:#F5F3FF!important;border-color:#EDE9FE!important}.stApp:has(.ca-page) [data-testid="stVerticalBlock"]:has(.ca-action-delete) button{color:#DC2626!important;background:#FEF2F2!important;border-color:#FEE2E2!important}.stApp:has(.ca-page) [data-testid="stVerticalBlock"]:has(.ca-action-marker) button:hover{transform:translateY(-1px)!important;filter:saturate(1.15);box-shadow:0 4px 10px rgba(15,23,42,.08)!important}
            .ca-row-action-marker{display:none}.stApp:has(.ca-page) [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .ca-row-action-marker) .stButton{display:flex!important;align-items:center!important;justify-content:center!important}.stApp:has(.ca-page) [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .ca-row-action-marker) .stButton>button{width:32px!important;min-width:32px!important;max-width:32px!important;height:32px!important;min-height:32px!important;max-height:32px!important;padding:0!important;margin:0 auto!important;border:1px solid transparent!important;border-radius:10px!important;box-shadow:none!important;overflow:hidden!important}.stApp:has(.ca-page) [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .ca-row-action-marker) .stButton>button p{font-size:0!important;line-height:0!important;margin:0!important;color:transparent!important}.stApp:has(.ca-page) [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .ca-row-action-marker) .stButton>button span[data-testid="stIconMaterial"]{display:block!important;font-size:17px!important;line-height:1!important;color:currentColor!important}.stApp:has(.ca-page) [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .ca-row-action-view) button{color:#2563EB!important;background:#EFF6FF!important;border-color:#DBEAFE!important}.stApp:has(.ca-page) [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .ca-row-action-edit) button{color:#7C3AED!important;background:#F5F3FF!important;border-color:#EDE9FE!important}.stApp:has(.ca-page) [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .ca-row-action-delete) button{color:#DC2626!important;background:#FEF2F2!important;border-color:#FEE2E2!important}.stApp:has(.ca-page) [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .ca-row-action-marker) button:hover{transform:translateY(-1px)!important;filter:saturate(1.15);box-shadow:0 4px 10px rgba(15,23,42,.08)!important}
            .stApp:has(.ca-page) [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .ca-row-action-marker) .stButton button{width:32px!important;min-width:32px!important;max-width:32px!important;height:32px!important;min-height:32px!important;max-height:32px!important;padding:0!important;margin:0 auto!important;border-radius:10px!important;box-shadow:none!important;overflow:hidden!important}.stApp:has(.ca-page) [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .ca-row-action-marker) .stButton button p{font-size:0!important;line-height:0!important;margin:0!important;color:transparent!important}.stApp:has(.ca-page) [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .ca-row-action-marker) .stButton button span[data-testid="stIconMaterial"]{font-size:16px!important;line-height:1!important;color:currentColor!important}
            .stApp:has(.ca-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ca-native-grid) [data-testid="stButton"]>button{width:30px!important;min-width:30px!important;max-width:30px!important;height:30px!important;min-height:30px!important;max-height:30px!important;padding:0!important;margin:0 auto!important;border-radius:9px!important;box-shadow:none!important;overflow:hidden!important}.stApp:has(.ca-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ca-native-grid) [data-testid="stButton"]>button p{font-size:0!important;line-height:0!important;margin:0!important}.stApp:has(.ca-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ca-native-grid) [data-testid="stButton"]>button span[data-testid="stIconMaterial"]{font-size:16px!important;line-height:1!important}.stApp:has(.ca-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ca-native-grid) [data-testid="column"]:last-child [data-testid="stHorizontalBlock"]{gap:5px!important;justify-content:center!important}.stApp:has(.ca-page) div[data-testid="stVerticalBlockBorderWrapper"]:has(.ca-native-grid) [data-testid="column"]:last-child [data-testid="stHorizontalBlock"]>[data-testid="column"]{width:30px!important;min-width:30px!important;flex:0 0 30px!important}
            .stApp:has(.ca-page) [class*="st-key-ca_view_"] .stButton>button{color:#2563EB!important;background:#EFF6FF!important;border-color:#DBEAFE!important}.stApp:has(.ca-page) [class*="st-key-ca_edit_"] .stButton>button{color:#7C3AED!important;background:#F5F3FF!important;border-color:#EDE9FE!important}.stApp:has(.ca-page) [class*="st-key-ca_delete_"] .stButton>button{color:#DC2626!important;background:#FEF2F2!important;border-color:#FEE2E2!important}
            .stApp:has(.ca-page) [class*="st-key-ca_first"] .stButton>button,.stApp:has(.ca-page) [class*="st-key-ca_prev"] .stButton>button,.stApp:has(.ca-page) [class*="st-key-ca_current"] .stButton>button,.stApp:has(.ca-page) [class*="st-key-ca_next"] .stButton>button,.stApp:has(.ca-page) [class*="st-key-ca_last"] .stButton>button{height:36px!important;min-height:36px!important;border-radius:10px!important}
            .ca-analytics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:12px}.ca-chart-card,.ca-recent-card{height:235px;box-sizing:border-box;padding:15px;background:#FFF;border:1px solid #E2E8F0;border-radius:17px;box-shadow:0 7px 18px rgba(15,23,42,.04);overflow:hidden}.ca-chart-title{margin-bottom:11px;color:#0F172A;font-size:12.5px;font-weight:800}.ca-donut-layout{display:flex;align-items:center;gap:12px;height:164px}.ca-donut{width:112px;height:112px;flex:0 0 112px;border-radius:50%;position:relative;background:conic-gradient(var(--d1) 0 var(--p1),var(--d2) var(--p1) var(--p2),var(--d3) var(--p2) 100%)}.ca-donut:after{content:"";position:absolute;inset:22px;border-radius:50%;background:#FFF}.ca-legend{display:grid;gap:9px;min-width:0}.ca-legend-row{display:grid;grid-template-columns:8px 1fr auto;align-items:center;gap:7px;color:#64748B;font-size:10px}.ca-legend-row i{width:8px;height:8px;border-radius:50%}.ca-legend-row b{color:#334155;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
            .ca-bars{display:grid;gap:12px}.ca-bar-row{display:grid;grid-template-columns:78px 1fr 24px;align-items:center;gap:8px;color:#475569;font-size:10px}.ca-bar-track{height:7px;background:#EEF2FF;border-radius:99px;overflow:hidden}.ca-bar-fill{height:100%;border-radius:99px;background:linear-gradient(90deg,#3B82F6,#8B5CF6)}.ca-bar-row strong{text-align:right}.ca-recent-list{display:grid;gap:11px}.ca-recent-item{display:grid;grid-template-columns:1fr auto;gap:8px;padding-bottom:9px;border-bottom:1px solid #F1F5F9;font-size:10px}.ca-recent-name{color:#334155;font-weight:750}.ca-recent-state,.ca-recent-time{color:#94A3B8}
            @media(max-width:1180px){.ca-metric-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.ca-analytics{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:700px){.ca-header{height:auto;min-height:110px;padding:18px}.ca-header-icon{width:56px;height:56px;flex-basis:56px}.ca-header h1{font-size:23px!important}.ca-metric-grid,.ca-analytics{grid-template-columns:1fr}.ca-chart-card,.ca-recent-card{height:auto;min-height:245px}.ca-table-footer{height:auto;padding:11px;gap:8px;align-items:flex-start;flex-direction:column}}
            </style>""", unsafe_allow_html=True)

    def _ca_value(row, *names, default="-"):
        for name in names:
            value = row.get(name, None)
            if value is not None and str(value).strip() not in ("", "nan", "None", "NaT"):
                return str(value).strip()
        return default

    def _ca_status(row):
        user = _ca_value(row, "field_3", "User", "Employee", default="")
        raw = _ca_value(row, "Status", "ComputerStatus", default="Active").lower()
        if not user or user == "-": return "No User", "nouser"
        if raw in ("inactive", "offline", "repair", "เสีย", "ซ่อม"): return "Offline", "offline"
        return "Online", "online"

    _ca_esc = lambda value: html.escape(str(value), quote=True)
    _ca_pct = lambda value,total: (float(value)/float(total)*100) if total else 0
    def _ca_os_key(row):
        raw_os = _ca_value(row,"field_10",default="")
        normalized_os = re.sub(r"[^a-z0-9]+","",str(raw_os).casefold())
        if "windows11" in normalized_os or normalized_os.startswith("win11"): return "Windows 11"
        if "windows10" in normalized_os or normalized_os.startswith("win10"): return "Windows 10"
        if "windows7" in normalized_os or normalized_os.startswith("win7"): return "Windows 7"
        return "Other"
    _ca_total = len(df_hw)
    _ca_online = sum(_ca_status(r)[1] == "online" for _,r in df_hw.iterrows())
    _ca_offline = sum(_ca_status(r)[1] == "offline" for _,r in df_hw.iterrows())
    _ca_nouser = sum(_ca_status(r)[1] == "nouser" for _,r in df_hw.iterrows())
    _ca_win11 = sum(_ca_os_key(r)=="Windows 11" for _,r in df_hw.iterrows())
    _ca_win10 = sum(_ca_os_key(r)=="Windows 10" for _,r in df_hw.iterrows())
    _ca_attention = _ca_offline + _ca_nouser
    _ca_monitor = '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4"/></svg>'
    _ca_icons = [
        _ca_monitor,
        '<svg viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="m8 12 2.5 2.5L16 9"/></svg>',
        '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.9"><path d="M4 9c4.7-4 11.3-4 16 0M7 12c3-2.5 7-2.5 10 0M10 15c1.2-1 2.8-1 4 0"/><circle cx="12" cy="19" r="1"/></svg>',
        '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.9"><circle cx="12" cy="8" r="3.5"/><path d="M5 20c0-4 3-7 7-7s7 3 7 7"/></svg>',
        '<svg class="ca-windows-logo" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M3 5.1 10.4 4v7.1H3V5.1Zm8.5-1.3L21 2.4v8.7h-9.5V3.8ZM3 12.7h7.4V20L3 18.9v-6.2Zm8.5 0H21v8.9l-9.5-1.4v-7.5Z"/></svg>',
        '<svg class="ca-windows-logo" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M3 5.1 10.4 4v7.1H3V5.1Zm8.5-1.3L21 2.4v8.7h-9.5V3.8ZM3 12.7h7.4V20L3 18.9v-6.2Zm8.5 0H21v8.9l-9.5-1.4v-7.5Z"/></svg>',
        '<svg viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 17h.01"/></svg>'
    ]
    st.markdown(f'<section class="ca-header"><div class="ca-header-icon">{_ca_monitor}</div><div><h1>Computer Asset</h1><p>จัดการข้อมูลคอมพิวเตอร์ทั้งหมดในองค์กร</p></div></section>',unsafe_allow_html=True)
    _ca_metrics=[("คอมพิวเตอร์ทั้งหมด",_ca_total,"#2563EB","#EFF6FF"),("ใช้งานปกติ",_ca_online,"#10B981","#ECFDF5"),("Offline",_ca_offline,"#F59E0B","#FFF7ED"),("ไม่มีผู้ใช้งาน",_ca_nouser,"#8B5CF6","#F5F3FF"),("Windows 11",_ca_win11,"#38BDF8","#F0F9FF"),("Windows 10",_ca_win10,"#3B82F6","#EFF6FF")]
    st.markdown('<div class="ca-metric-grid">'+''.join(f'<div class="ca-card" style="--tone:{tone};--soft:{soft}"><div class="ca-card-label">{label}</div><div class="ca-card-value">{value:,}</div><div class="ca-card-icon">{_ca_icons[i]}</div><div class="ca-card-foot"><span>เครื่อง</span><strong>{_ca_pct(value,_ca_total):.2f}%</strong></div></div>' for i,(label,value,tone,soft) in enumerate(_ca_metrics))+'</div>',unsafe_allow_html=True)

    _ca_departments=sorted({_ca_value(r,"field_4") for _,r in df_hw.iterrows()})
    st.markdown('<div class="ca-search-panel-title">ค้นหาและกรองข้อมูล</div>',unsafe_allow_html=True)
    f1,f2,f3,f4,f5=st.columns([3.1,1.25,1.35,1,1.2])
    with f1: _ca_search=st.text_input("ค้นหา",placeholder="ค้นหา Computer, User, LoginAccount, Serial",label_visibility="collapsed",key="ca_search")
    with f2: _ca_sf=st.selectbox("Status",["ทั้งหมด","Online","Offline","No User"],label_visibility="collapsed",key="ca_status")
    with f3: _ca_df=st.selectbox("Department",["ทั้งหมด"]+_ca_departments,label_visibility="collapsed",key="ca_department")
    with f4: st.button("⌕ ค้นหา",use_container_width=True,type="primary",key="ca_search_button")
    with f5:
        if st.button("↻ ล้างตัวกรอง",use_container_width=True,key="ca_reset"):
            for _ca_key in ("ca_search","ca_status","ca_department"):
                st.session_state.pop(_ca_key,None)
            st.rerun()
    _ca_filtered=df_hw.copy()
    if _ca_search: _ca_filtered=_ca_filtered[_ca_filtered.astype(str).apply(lambda c:c.str.contains(_ca_search,case=False,na=False)).any(axis=1)]
    if _ca_sf!="ทั้งหมด": _ca_filtered=_ca_filtered[_ca_filtered.apply(lambda r:_ca_status(r)[0]==_ca_sf,axis=1)]
    if _ca_df!="ทั้งหมด": _ca_filtered=_ca_filtered[_ca_filtered.apply(lambda r:_ca_value(r,"field_4")==_ca_df,axis=1)]
    a1,a2,a3,_ca_action_space=st.columns([1.25,.9,1.8,3.2])
    with a1:
        if admin_mode and st.button("＋ เพิ่มคอมพิวเตอร์",use_container_width=True,type="primary",key="ca_add"): add_computer_dialog(list_name)
    with a2: st.download_button("Export",_ca_filtered.to_csv(index=False).encode("utf-8-sig"),"computer_assets.csv","text/csv",use_container_width=True,key="ca_export")
    _ca_column_defs={"computer":"Computer Name","user":"User","login":"LoginAccount","department":"Department","os":"OS","model":"Model","serial":"Serial Number","status":"Status"}
    _ca_visible_columns=list(_ca_column_defs)
    with a3: _ca_sort=st.selectbox("เรียงข้อมูล",["Computer Name A–Z","Computer Name Z–A"],label_visibility="collapsed",key="ca_sort")

    _ca_records=[]
    for idx,row in _ca_filtered.iterrows():
        status,status_class=_ca_status(row)
        _ca_records.append((idx,row,{"computer":_ca_value(row,"field_6"),"user":_ca_value(row,"field_3"),"login":_ca_value(row,"LoginAccount"),"department":_ca_value(row,"field_4"),"os":_ca_value(row,"field_10"),"model":_ca_value(row,"field_7"),"serial":_ca_value(row,"field_8"),"status":status,"status_class":status_class,"seen":_ca_value(row,"LastSeen","Last Seen","Modified")}))
    _ca_records.sort(key=lambda x:x[2]["computer"].lower(),reverse=_ca_sort=="Computer Name Zโ€“A")
    _ca_page_size=10
    _ca_page_count=max(1,(len(_ca_records)+_ca_page_size-1)//_ca_page_size)
    _ca_page=max(1,min(st.session_state.get("ca_page",1),_ca_page_count))
    st.session_state["ca_page"]=_ca_page
    _ca_start=(_ca_page-1)*_ca_page_size
    _ca_slice=_ca_records[_ca_start:_ca_start+_ca_page_size]
    st.markdown('<div class="ca-action-bar"><div class="ca-action-title"><span>▦</span>รายการคอมพิวเตอร์</div><div>Enterprise Data Grid</div></div>',unsafe_allow_html=True)
    _ca_from=(_ca_page-1)*_ca_page_size+1 if _ca_records else 0; _ca_to=min(_ca_page*_ca_page_size,len(_ca_records))
    with st.container(border=True):
        st.markdown('<div class="ca-native-grid"></div>',unsafe_allow_html=True)
        _ca_widths=[1.06,1.0,1.05,.96,.9,1.1,1.0,.78,1.05]
        _ca_head=st.columns(_ca_widths,gap="small")
        for _ca_col,_ca_label in zip(_ca_head,["Computer Name","User","LoginAccount","Department","OS","Model","Serial Number","Status","Action"]):
            with _ca_col: st.markdown(f'<div class="ca-native-head">{_ca_label}</div>',unsafe_allow_html=True)
        if not _ca_slice:
            st.info("ไม่พบข้อมูลตามเงื่อนไข")
        for _ca_idx,_ca_row,_ca_data in _ca_slice:
            _ca_cols=st.columns(_ca_widths,gap="small",vertical_alignment="center")
            _ca_values=[_ca_data["computer"],_ca_data["user"],_ca_data["login"],_ca_data["department"],_ca_data["os"],_ca_data["model"],_ca_data["serial"]]
            for _ca_col,_ca_value_text in zip(_ca_cols[:7],_ca_values):
                with _ca_col: st.markdown(f'<div class="ca-native-cell" title="{_ca_esc(_ca_value_text)}">{_ca_esc(_ca_value_text)}</div>',unsafe_allow_html=True)
            with _ca_cols[7]:
                st.markdown(f'<div class="ca-native-status"><span class="ca-status ca-status-{_ca_data["status_class"]}">{_ca_esc(_ca_data["status"])}</span></div>',unsafe_allow_html=True)
            with _ca_cols[8]:
                _ca_b1,_ca_b2,_ca_b3=st.columns(3,gap="small")
                with _ca_b1:
                    st.markdown('<span class="ca-row-action-marker ca-row-action-view"></span>',unsafe_allow_html=True)
                    if st.button(" ",icon=":material/visibility:",key=f"ca_view_{_ca_idx}",help="ดูรายละเอียด"): show_pop_computer(_ca_row.to_dict())
                with _ca_b2:
                    st.markdown('<span class="ca-row-action-marker ca-row-action-edit"></span>',unsafe_allow_html=True)
                    if admin_mode and st.button(" ",icon=":material/edit:",key=f"ca_edit_{_ca_idx}",help="แก้ไข"): edit_computer_dialog(_ca_row.to_dict(),list_name)
                with _ca_b3:
                    st.markdown('<span class="ca-row-action-marker ca-row-action-delete"></span>',unsafe_allow_html=True)
                    if admin_mode and st.button(" ",icon=":material/delete:",key=f"ca_delete_{_ca_idx}",help="ลบ"): delete_computer_dialog(_ca_row.to_dict(),list_name)
            st.markdown('<div class="ca-native-divider"></div>',unsafe_allow_html=True)
        st.markdown(f'<div class="ca-native-footer"><span>แสดง {_ca_from} ถึง {_ca_to} จาก {len(_ca_records)} รายการ</span><span>หน้า {_ca_page} / {_ca_page_count}</span></div>',unsafe_allow_html=True)

    _ca_nav=st.columns([7,.52,.52,.52,.52,.52])
    with _ca_nav[1]:
        if st.button("ยซ",use_container_width=True,key="ca_first",disabled=_ca_page<=1): st.session_state["ca_page"]=1; st.rerun()
    with _ca_nav[2]:
        if st.button("โ€น",use_container_width=True,key="ca_prev",disabled=_ca_page<=1): st.session_state["ca_page"]=_ca_page-1; st.rerun()
    with _ca_nav[3]:
        st.button(str(_ca_page),use_container_width=True,type="primary",key="ca_current",disabled=True)
    with _ca_nav[4]:
        if st.button("โ€บ",use_container_width=True,key="ca_next",disabled=_ca_page>=_ca_page_count): st.session_state["ca_page"]=_ca_page+1; st.rerun()
    with _ca_nav[5]:
        if st.button("ยป",use_container_width=True,key="ca_last",disabled=_ca_page>=_ca_page_count): st.session_state["ca_page"]=_ca_page_count; st.rerun()

    _ca_types={"Desktop":0,"All-in-One":0,"Notebook":0}; _ca_windows={"Windows 11":0,"Windows 10":0,"Windows 7":0}; _ca_depts={}
    for _,r in df_hw.iterrows():
        model=_ca_value(r,"field_7","Model",default="").lower(); kind="Notebook" if any(x in model for x in ("notebook","laptop","thinkpad","latitude")) else ("All-in-One" if any(x in model for x in ("all-in-one","aio")) else "Desktop"); _ca_types[kind]+=1
        os_key=_ca_os_key(r)
        if os_key in _ca_windows: _ca_windows[os_key]+=1
        dept=_ca_value(r,"field_4",default="ไม่ระบุ"); _ca_depts[dept]=_ca_depts.get(dept,0)+1
    def _ca_donut(title,data,colors):
        total=max(sum(data.values()),1); values=list(data.values()); p1=values[0]/total*100; p2=(values[0]+values[1])/total*100; legend=''.join(f'<div class="ca-legend-row"><i style="background:{colors[i]}"></i><b>{_ca_esc(k)}</b><span>{v}</span></div>' for i,(k,v) in enumerate(data.items())); return f'<div class="ca-chart-card"><div class="ca-chart-title">{title}</div><div class="ca-donut-layout"><div class="ca-donut" style="--d1:{colors[0]};--d2:{colors[1]};--d3:{colors[2]};--p1:{p1:.2f}%;--p2:{p2:.2f}%"></div><div class="ca-legend">{legend}</div></div></div>'
    _ca_top=sorted(_ca_depts.items(),key=lambda x:x[1],reverse=True)[:5]; _ca_max=max([v for _,v in _ca_top] or [1]); _ca_bars=''.join(f'<div class="ca-bar-row"><span>{_ca_esc(k)}</span><div class="ca-bar-track"><div class="ca-bar-fill" style="width:{v/_ca_max*100:.1f}%"></div></div><strong>{v}</strong></div>' for k,v in _ca_top); _ca_recent=''.join(f'<div class="ca-recent-item"><div><div class="ca-recent-name">{_ca_esc(d["computer"])}</div><div class="ca-recent-state">{_ca_esc(d["status"])}</div></div><div class="ca-recent-time">{_ca_esc(d["seen"])}</div></div>' for _,_,d in sorted(_ca_records,key=lambda x:x[2]["seen"],reverse=True)[:5])
    st.markdown('<div class="ca-analytics">'+_ca_donut("ประเภทเครื่อง",_ca_types,["#4F46E5","#38BDF8","#A855F7"])+_ca_donut("Windows Version",_ca_windows,["#2563EB","#3B82F6","#22C1C3"])+f'<div class="ca-chart-card"><div class="ca-chart-title">Top 5 Department</div><div class="ca-bars">{_ca_bars}</div></div><div class="ca-recent-card"><div class="ca-chart-title">◷ อัปเดตล่าสุด</div><div class="ca-recent-list">{_ca_recent}</div></div></div>',unsafe_allow_html=True)
