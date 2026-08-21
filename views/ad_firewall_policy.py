"""AD and Firewall Policy Streamlit view."""

import datetime
import html

import pandas as pd
import streamlit as st


def render_ad_firewall_policy(
    *,
    firewall_policy_mapping_list,
    fw_policy_map,
    fw_policy_prefixes,
    get_user_internet_policy_summary,
    get_policy_users_summary,
    load_firewall_policy_mapping,
    ldap_find_user,
    get_ldap_group_names_for_user,
    get_ad_agent_policy_summary,
    get_ad_agent_policy_users,
    graph_find_user,
    get_ad_group_names_for_user,
):
    st.markdown("""
        <div class="adp-page-marker"></div>
        <style>
        .stApp:has(.adp-page-marker) [data-testid="stMainBlockContainer"] {
            background:#F7F9FD;
            padding-top:0!important;
        }
        .stApp:has(.adp-page-marker) [data-testid="stHeader"],
        .stApp:has(.adp-page-marker) [data-testid="stToolbar"] {
            display:none!important;
        }
        .adp-hero {
            height:132px; min-height:132px; box-sizing:border-box; padding:22px 26px;
            margin:0 0 14px; border-radius:18px; color:#fff;
            display:flex; align-items:center; gap:20px; overflow:hidden; position:relative;
            background:
              radial-gradient(circle at 88% 18%,rgba(56,189,248,.38),transparent 21%),
              radial-gradient(circle at 78% 120%,rgba(139,92,246,.72),transparent 36%),
              linear-gradient(128deg,#1E40AF 0%,#3949C6 50%,#6D3DEB 100%);
            border:1px solid rgba(255,255,255,.24);
            box-shadow:0 16px 36px rgba(49,46,129,.18);
        }
        .adp-hero:after {
            content:""; position:absolute; width:210px; height:210px; right:35px; top:-84px;
            border:1px solid rgba(255,255,255,.14); border-radius:50%;
            box-shadow:0 0 0 26px rgba(255,255,255,.035),0 0 0 58px rgba(255,255,255,.025);
        }
        .adp-hero-icon {
            width:64px; height:64px; flex:0 0 64px; border-radius:16px;
            display:grid; place-items:center; font-size:30px;
            background:linear-gradient(145deg,rgba(255,255,255,.26),rgba(255,255,255,.12));
            border:1px solid rgba(255,255,255,.18); box-shadow:inset 0 1px 0 rgba(255,255,255,.22);
        }
        .adp-hero-icon svg{width:38px;height:38px;display:block;filter:drop-shadow(0 4px 8px rgba(15,23,42,.18))}
        .adp-hero-copy {position:relative; z-index:1; min-width:0}
        .adp-hero h1 {font-size:28px!important; line-height:1.15; margin:0 0 9px!important; color:#fff!important; letter-spacing:-.025em}
        .adp-hero h1 a,.adp-hero h1 svg{display:none!important}
        .adp-hero p,.stMarkdown .adp-hero p {font-size:13px!important; line-height:1.5; margin:0!important; color:rgba(255,255,255,.88)!important}
        .adp-hero-art {position:absolute;z-index:1;right:34px;top:7px;width:230px;height:118px;color:#BAE6FD;opacity:.94}
        .adp-hero-art svg{display:block;width:100%;height:100%;overflow:visible;filter:drop-shadow(0 10px 18px rgba(30,64,175,.20))}
        .adp-globe {position:absolute;right:76px;top:0;width:80px;height:80px;border:3px solid rgba(125,211,252,.58);border-radius:50%;background:linear-gradient(90deg,transparent 46%,rgba(125,211,252,.42) 47%,rgba(125,211,252,.42) 53%,transparent 54%)}
        .adp-globe:before,.adp-globe:after {content:"";position:absolute;left:8px;right:8px;border-top:3px solid rgba(125,211,252,.55)}
        .adp-globe:before{top:27px}.adp-globe:after{top:55px}
        .adp-wall {position:absolute;right:0;bottom:4px;display:grid;grid-template-columns:repeat(3,30px);gap:4px;transform:skewY(-2deg)}
        .adp-wall i{height:22px;border-radius:4px;background:linear-gradient(145deg,#7DD3FC,#60A5FA);box-shadow:0 4px 10px rgba(30,64,175,.24)}
        .adp-lock {position:absolute;right:18px;bottom:0;font-size:35px;filter:drop-shadow(0 5px 8px rgba(30,64,175,.24))}
        .adp-info-banner {
            min-height:46px; box-sizing:border-box; display:flex; align-items:center; gap:10px;
            margin:0 0 10px; padding:8px 14px; border-radius:13px;
            color:#405174; font-size:12.5px; line-height:1.45;
            background:linear-gradient(90deg,#F1F5FF 0%,#F8FAFF 100%); border:1px solid #D8E1F5;
            box-shadow:0 2px 8px rgba(79,70,229,.025);
        }
        .adp-info-icon {width:18px;height:18px;color:#4F46E5;flex:0 0 18px;display:grid;place-items:center}
        .adp-info-icon svg{width:17px;height:17px;display:block;stroke:currentColor}
        .adp-info-banner code {font-size:11px; color:#4338CA; background:#E0E7FF; padding:2px 6px; border-radius:6px}
        .adp-stat-grid {display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:12px; margin:14px 0 8px}
        .adp-stat-card {
            height:94px; box-sizing:border-box; display:flex; align-items:center; gap:12px;
            padding:14px 16px; min-width:0; background:#FFFFFF; border:1px solid #E2E8F0;
            border-radius:14px; box-shadow:0 7px 18px rgba(30,41,59,.055);
        }
        .adp-stat-icon {width:38px;height:38px;flex:0 0 38px;border-radius:12px;display:grid;place-items:center;font-size:18px;background:linear-gradient(145deg,#EEF2FF,#E8EDFF);color:#5B5FF0;border:1px solid #E1E7FF}
        .adp-stat-icon svg{width:21px;height:21px;display:block;stroke:currentColor}
        .adp-stat-grid .adp-stat-card:nth-child(1) .adp-stat-icon{background:linear-gradient(145deg,#F3F0FF,#ECE8FF);color:#6D5DF8;border-color:#E5DEFF}
        .adp-stat-grid .adp-stat-card:nth-child(2) .adp-stat-icon{background:linear-gradient(145deg,#EFF6FF,#E7F0FF);color:#2563EB;border-color:#D9E8FF}
        .adp-stat-grid .adp-stat-card:nth-child(3) .adp-stat-icon{background:linear-gradient(145deg,#F5F1FF,#EEE9FF);color:#7C3AED;border-color:#E7DEFF}
        .adp-stat-grid .adp-stat-card:nth-child(4) .adp-stat-icon{background:linear-gradient(145deg,#ECFDF5,#E5F8EF);color:#059669;border-color:#D4F1E3}
        .adp-stat-copy {min-width:0;overflow:hidden}
        .adp-stat-label {font-size:10.5px;line-height:1.2;font-weight:750;letter-spacing:.06em;text-transform:uppercase;color:#64748B;margin-bottom:6px}
        .adp-stat-value {font-size:18px;line-height:1.25;font-weight:720;color:#16213A;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .adp-summary-grid {display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:10px 0 12px}
        .adp-summary-card {height:90px;box-sizing:border-box;padding:14px 18px;background:#fff;border:1px solid #E2E8F0;border-radius:14px;box-shadow:0 6px 16px rgba(30,41,59,.04)}
        .adp-summary-card:first-child {background:linear-gradient(135deg,#FFFFFF 0%,#F7F5FF 100%);border-color:#DCD7FE}
        .adp-summary-card:last-child {background:linear-gradient(135deg,#FFFFFF 0%,#F0F9FF 100%);border-color:#D4EAF7}
        .adp-summary-card{position:relative;overflow:hidden}
        .adp-summary-icon{position:absolute;right:17px;top:17px;width:40px;height:40px;display:grid;place-items:center;border-radius:13px;background:#F0EDFF;color:#6366F1}
        .adp-summary-card:last-child .adp-summary-icon{background:#EAF7FF;color:#0284C7}
        .adp-summary-icon svg{width:23px;height:23px;stroke:currentColor}
        .adp-summary-label {font-size:10.5px;font-weight:750;letter-spacing:.06em;color:#4F46E5;text-transform:uppercase}
        .adp-summary-value {font-size:22px;line-height:1.15;font-weight:800;color:#1E3A8A;margin-top:6px}
        .adp-summary-note {font-size:10.5px;color:#64748B;margin-top:1px}
        .adp-table-title {display:flex;align-items:center;gap:8px;font-size:13px;font-weight:750;color:#1E293B;margin:0 0 9px}
        .adp-table-title .adp-stat-icon svg{width:14px;height:14px}
        .adp-field-label {font-size:11px;font-weight:700;color:#334155;margin:0 0 5px}
        .adp-table-wrap {background:#fff;border:1px solid #DEE5EF;border-radius:15px;padding:13px 14px 14px;box-shadow:0 8px 22px rgba(30,41,59,.05);margin-top:2px;overflow:hidden}
        .adp-policy-table {width:100%;border-collapse:separate;border-spacing:0;table-layout:fixed;border:1px solid #E2E8F0;border-radius:10px;overflow:hidden;font-size:10.5px;color:#334155}
        .adp-policy-table th {height:34px;box-sizing:border-box;padding:6px 8px;text-align:left;background:#F5F7FB;color:#52617A;font-size:10px;font-weight:800;border-right:1px solid #E2E8F0;border-bottom:1px solid #DCE3ED;white-space:nowrap}
        .adp-policy-table td {height:36px;box-sizing:border-box;padding:6px 8px;border-right:1px solid #EDF1F5;border-bottom:1px solid #E8EDF3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;vertical-align:middle}
        .adp-policy-table tr:last-child td{border-bottom:0}.adp-policy-table th:last-child,.adp-policy-table td:last-child{border-right:0}
        .adp-source-pill {display:inline-flex;align-items:center;justify-content:center;min-width:26px;height:18px;padding:0 6px;border-radius:999px;background:#EDE9FE;color:#4F46E5;font-size:9.5px;font-weight:800}
        .stApp:has(.adp-page-marker) .stTabs [data-baseweb="tab-list"] {gap:8px;padding:0;background:transparent;border-radius:13px;width:min(600px,100%);max-width:100%;margin-bottom:10px}
        .stApp:has(.adp-page-marker) .stTabs [data-baseweb="tab"] {height:58px;flex:1;position:relative;justify-content:flex-start;padding:0 12px 0 46px;border:1px solid #DDE4EE;border-radius:12px;background:#FFFFFF;color:#64748B;font-size:12px;font-weight:750;box-shadow:0 4px 12px rgba(30,41,59,.035)}
        .stApp:has(.adp-page-marker) .stTabs [data-baseweb="tab"] p {font-size:12px!important;font-weight:750!important;color:inherit!important;margin:0 0 15px!important}
        .stApp:has(.adp-page-marker) .stTabs [data-baseweb="tab"]:before {content:"";position:absolute;left:15px;top:18px;width:20px;height:20px;background:currentColor;opacity:.9;mask-repeat:no-repeat;mask-position:center;mask-size:contain;-webkit-mask-repeat:no-repeat;-webkit-mask-position:center;-webkit-mask-size:contain}
        .stApp:has(.adp-page-marker) .stTabs [data-baseweb="tab"]:nth-child(1):before{mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Ccircle cx='9' cy='8' r='3' fill='black'/%3E%3Cpath d='M3 19c0-3.3 2.7-6 6-6s6 2.7 6 6v1H3zM16 8h5v2h-5zM17.5 5.5h2v7h-2z' fill='black'/%3E%3C/svg%3E");-webkit-mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Ccircle cx='9' cy='8' r='3' fill='black'/%3E%3Cpath d='M3 19c0-3.3 2.7-6 6-6s6 2.7 6 6v1H3zM16 8h5v2h-5zM17.5 5.5h2v7h-2z' fill='black'/%3E%3C/svg%3E")}
        .stApp:has(.adp-page-marker) .stTabs [data-baseweb="tab"]:nth-child(2):before{mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M10.5 3a7.5 7.5 0 1 0 4.7 13.3L20 21l1-1-4.7-4.8A7.5 7.5 0 0 0 10.5 3zm0 2a5.5 5.5 0 1 1 0 11 5.5 5.5 0 0 1 0-11z' fill='black'/%3E%3C/svg%3E");-webkit-mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M10.5 3a7.5 7.5 0 1 0 4.7 13.3L20 21l1-1-4.7-4.8A7.5 7.5 0 0 0 10.5 3zm0 2a5.5 5.5 0 1 1 0 11 5.5 5.5 0 0 1 0-11z' fill='black'/%3E%3C/svg%3E")}
        .stApp:has(.adp-page-marker) .stTabs [data-baseweb="tab"]:nth-child(3):before{mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M4 3h6v6H4V3zm10 0h6v6h-6V3zM4 15h6v6H4v-6zm10 0h6v6h-6v-6zM10 5h4v2h-4V5zm-3 4h2v6H7V9zm8 0h2v6h-2V9zm-5 9h4v2h-4v-2z' fill='black'/%3E%3C/svg%3E");-webkit-mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M4 3h6v6H4V3zm10 0h6v6h-6V3zM4 15h6v6H4v-6zm10 0h6v6h-6v-6zM10 5h4v2h-4V5zm-3 4h2v6H7V9zm8 0h2v6h-2V9zm-5 9h4v2h-4v-2z' fill='black'/%3E%3C/svg%3E")}
        .stApp:has(.adp-page-marker) .stTabs [data-baseweb="tab"]:after {position:absolute;left:46px;top:34px;color:#94A3B8;font-size:9.5px;font-weight:550;white-space:nowrap}
        .stApp:has(.adp-page-marker) .stTabs [data-baseweb="tab"]:nth-child(1):after{content:"ค้นหานโยบายของผู้ใช้"}.stApp:has(.adp-page-marker) .stTabs [data-baseweb="tab"]:nth-child(2):after{content:"ค้นหาผู้ใช้ตาม Policy"}.stApp:has(.adp-page-marker) .stTabs [data-baseweb="tab"]:nth-child(3):after{content:"ตรวจสอบการแม็ป Policy"}
        .stApp:has(.adp-page-marker) .stTabs [aria-selected="true"] {background:linear-gradient(180deg,#FFFFFF 0%,#F6F5FF 100%)!important;color:#4F46E5!important;border-color:transparent!important;border-radius:12px!important;box-shadow:0 7px 16px rgba(79,70,229,.11)!important;z-index:2}
        .stApp:has(.adp-page-marker) .stTabs [data-baseweb="tab-panel"] {padding-top:0!important}
        .stApp:has(.adp-page-marker) .stTabs [data-baseweb="tab-highlight"],
        .stApp:has(.adp-page-marker) .stTabs [data-baseweb="tab-border"] {display:none!important}
        .stApp:has(.adp-page-marker) .stTextInput input,
        .stApp:has(.adp-page-marker) .stSelectbox div[data-baseweb="select"]>div {height:42px!important;min-height:42px!important;border-radius:10px!important;border-color:#DCE3ED!important;font-size:12px!important}
        .stApp:has(.adp-page-marker) .stButton>button {height:42px!important;min-height:42px!important;border-radius:10px!important;font-size:12px!important}
        .stApp:has(.adp-page-marker) .stButton>button p {color:inherit!important;font-size:inherit!important}
        .stApp:has(.adp-page-marker) div[data-testid="stVerticalBlockBorderWrapper"] {border:1px solid #DCE3ED!important;border-radius:14px!important;background:#FFFFFF!important;box-shadow:0 7px 18px rgba(30,41,59,.045)!important}
        .stApp:has(.adp-page-marker) div[data-testid="stVerticalBlockBorderWrapper"]>div {padding:12px 14px!important}
        .adp-search-panel-marker{display:none}
        .stApp:has(.adp-page-marker) .stTabs [data-baseweb="tab-panel"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.adp-search-panel-marker){position:relative;z-index:1;margin-top:0;border:0!important;border-radius:14px!important;background:#FFFFFF!important;box-shadow:0 8px 22px rgba(30,41,59,.06)!important}
        .adp-table-footer-marker{display:flex;align-items:center;gap:7px;height:30px;margin:5px 2px 0;padding:0 4px;color:#64748B;font-size:10.5px}
        .adp-table-footer-marker svg{width:15px;height:15px;stroke:#7EA5DF}
        .stApp:has(.adp-page-marker) [data-testid="stDataFrame"] {border:1px solid #E2E8F0!important;border-radius:12px!important;box-shadow:none!important}
        .stApp:has(.adp-page-marker) [data-testid="stExpander"] {background:#FFFFFF!important;border:1px solid #DEE5EF!important;border-radius:12px!important;box-shadow:0 4px 12px rgba(30,41,59,.035);overflow:hidden;margin-top:3px}
        .stApp:has(.adp-page-marker) [data-testid="stExpander"] summary {min-height:40px;padding-top:2px;padding-bottom:2px;font-size:12px;font-weight:700;color:#334155;background:#FFFFFF!important}
        .stApp:has(.adp-page-marker) [data-testid="stExpander"] summary:hover{background:#F8FAFF!important}
        .stApp:has(.adp-page-marker) [data-testid="stExpander"] summary p {font-size:12px!important;color:#334155!important}
        .stApp:has(.adp-page-marker) [data-testid="stVerticalBlock"] {gap:.58rem}
        @media(max-width:900px){.adp-stat-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.adp-hero{height:132px;min-height:132px}.adp-hero:after,.adp-hero-art{display:none}.adp-policy-table th:nth-child(5),.adp-policy-table td:nth-child(5),.adp-policy-table th:nth-child(6),.adp-policy-table td:nth-child(6){display:none}}
        @media(max-width:640px){.adp-hero{padding:22px 18px;gap:14px}.adp-hero-icon{width:54px;height:54px;flex-basis:54px;font-size:27px}.adp-hero h1{font-size:28px!important}.adp-hero p{font-size:14px}.adp-stat-grid,.adp-summary-grid{grid-template-columns:1fr}.adp-stat-card{height:108px}.stApp:has(.adp-page-marker) .stTabs [data-baseweb="tab"]{height:50px;padding:0 9px;font-size:12px}}
        </style>
        <section class="adp-hero">
          <div class="adp-hero-icon">
            <svg viewBox="0 0 48 48" aria-hidden="true"><defs><linearGradient id="adpShield" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#E0F2FE"/><stop offset="1" stop-color="#93C5FD"/></linearGradient></defs><path d="M24 4 40 11v11c0 10.2-6.5 18.3-16 22C14.5 40.3 8 32.2 8 22V11L24 4Z" fill="url(#adpShield)" stroke="#BFDBFE" stroke-width="2"/><path d="m17.2 24.2 4.4 4.4 9.6-10" fill="none" stroke="#1D4ED8" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </div>
          <div class="adp-hero-copy">
            <h1>AD / Firewall Policy</h1>
            <p>ตรวจสอบ Internet Policy ที่ผู้ใช้หรือ Policy Group ได้รับจาก AD / Entra ID Group</p>
          </div>
          <div class="adp-hero-art" aria-hidden="true">
            <svg viewBox="0 0 260 130"><defs><linearGradient id="adpBrick" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#7DD3FC"/><stop offset="1" stop-color="#60A5FA"/></linearGradient><linearGradient id="adpMiniShield" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#BAE6FD"/><stop offset="1" stop-color="#818CF8"/></linearGradient></defs><g fill="none" stroke="#7DD3FC" stroke-width="3" opacity=".62"><circle cx="69" cy="57" r="43"/><path d="M27 57h84M69 14c-14 13-20 27-20 43s6 30 20 43M69 14c14 13 20 27 20 43s-6 30-20 43M34 35h70M34 79h70"/></g><g fill="url(#adpBrick)" stroke="#93C5FD" stroke-width="1"><rect x="102" y="48" width="43" height="24" rx="5"/><rect x="149" y="48" width="43" height="24" rx="5"/><rect x="196" y="48" width="43" height="24" rx="5"/><rect x="114" y="76" width="43" height="24" rx="5"/><rect x="161" y="76" width="43" height="24" rx="5"/><rect x="208" y="76" width="31" height="24" rx="5"/></g><g transform="translate(174 16)"><path d="M24 1 45 10v14c0 13-8.5 23.5-21 28C11.5 47.5 3 37 3 24V10L24 1Z" fill="url(#adpMiniShield)" stroke="#BAE6FD" stroke-width="2"/><path d="m15 25 6 6 13-14" fill="none" stroke="#E0F2FE" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></g><g transform="translate(184 73)"><path d="M8 14V9a12 12 0 0 1 24 0v5" fill="none" stroke="#BFDBFE" stroke-width="4"/><rect x="3" y="13" width="34" height="29" rx="6" fill="#4F46E5" stroke="#93C5FD" stroke-width="2"/><circle cx="20" cy="25" r="4" fill="#BAE6FD"/><path d="M20 29v6" stroke="#BAE6FD" stroke-width="3" stroke-linecap="round"/></g></svg>
          </div>
        </section>
        <div class="adp-info-banner"><span class="adp-info-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg></span><span>ระบบอ่าน Group Membership จาก AD Agent / LDAP / Microsoft Graph แล้วแปลงกลุ่มที่ขึ้นต้นด้วย <code>FW_</code>, <code>Firewall_</code> หรือ <code>Internet_</code> เป็น Internet Policy</span></div>
        """, unsafe_allow_html=True)

    ADP_ICONS = {
        "user": '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="3.5"/><path d="M5 20c0-4 3.1-7 7-7s7 3 7 7"/></svg>',
        "account": '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="3"/><circle cx="9" cy="11" r="2.2"/><path d="M5.8 16c.7-1.8 1.8-2.7 3.2-2.7s2.5.9 3.2 2.7M15 10h3M15 14h3"/></svg>',
        "mail": '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="m4 7 8 6 8-6"/></svg>',
        "server": '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="7" rx="2"/><rect x="3" y="14" width="18" height="7" rx="2"/><path d="M7 6.5h.01M7 17.5h.01M11 6.5h7M11 17.5h7"/></svg>',
        "shield": '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2 20 5.5V11c0 5.1-3.2 9.1-8 11-4.8-1.9-8-5.9-8-11V5.5L12 2Z"/><path d="m8.5 12 2.2 2.2 4.8-5"/></svg>',
        "groups": '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3"/><circle cx="17" cy="9" r="2.3"/><path d="M3 20c0-4 2.7-7 6-7s6 3 6 7M15 14c3.2 0 5 2.2 5 5"/></svg>',
        "link": '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m9.5 14.5 5-5M7.5 17.5l-1 1a3.5 3.5 0 0 1-5-5l4-4a3.5 3.5 0 0 1 5 0M16.5 6.5l1-1a3.5 3.5 0 0 1 5 5l-4 4a3.5 3.5 0 0 1-5 0"/></svg>',
    }

    def adp_stat_card(label, value, icon="shield"):
        safe_label = html.escape(str(label))
        safe_value = html.escape(str(value if value not in (None, "") else "-"))
        icon_svg = ADP_ICONS.get(icon, ADP_ICONS["shield"])
        return f'''<div class="adp-stat-card"><div class="adp-stat-icon">{icon_svg}</div><div class="adp-stat-copy"><div class="adp-stat-label">{safe_label}</div><div class="adp-stat-value" title="{safe_value}">{safe_value}</div></div></div>'''

    def adp_stat_grid(items):
        st.markdown('<div class="adp-stat-grid">' + ''.join(adp_stat_card(*item) for item in items) + '</div>', unsafe_allow_html=True)

    def adp_summary_grid(policy_count, group_count):
        st.markdown(f'''<div class="adp-summary-grid">
              <div class="adp-summary-card"><div class="adp-summary-icon">{ADP_ICONS['shield']}</div><div class="adp-summary-label">Internet Policies</div><div class="adp-summary-value">{int(policy_count)}</div><div class="adp-summary-note">นโยบายที่ได้รับ</div></div>
              <div class="adp-summary-card"><div class="adp-summary-icon">{ADP_ICONS['groups']}</div><div class="adp-summary-label">AD Groups</div><div class="adp-summary-value">{int(group_count)}</div><div class="adp-summary-note">กลุ่มที่เป็นสมาชิก</div></div>
            </div>''', unsafe_allow_html=True)

    def adp_policy_table(rows):
        columns = [
            ("Policy Internet", "Policy Internet", "14%"),
            ("AD Group", "AD Group", "14%"),
            ("Policy Name", "Policy Name", "14%"),
            ("Internet Level", "Internet Level", "10%"),
            ("Allowed", "Allowed", "18%"),
            ("Blocked", "Blocked", "11%"),
            ("Firewall Rule", "Firewall", "11%"),
            ("Source", "แหล่งที่มา", "8%"),
        ]
        colgroup = ''.join(f'<col style="width:{width}">' for _, _, width in columns)
        header = ''.join(f'<th>{html.escape(title)}</th>' for _, title, _ in columns)
        body_rows = []
        for row in rows:
            cells = []
            for key, _, _ in columns:
                value = str(row.get(key, "-") or "-")
                safe_value = html.escape(value)
                if key == "Source":
                    # Policies in this view originate from the user's AD group
                    # membership; keep the full mapping source in the tooltip.
                    cells.append(f'<td title="{safe_value}"><span class="adp-source-pill">AD</span></td>')
                else:
                    cells.append(f'<td title="{safe_value}">{safe_value}</td>')
            body_rows.append('<tr>' + ''.join(cells) + '</tr>')
        table = f'''<div class="adp-table-wrap"><div class="adp-table-title"><span class="adp-stat-icon" style="width:24px;height:24px;flex-basis:24px;border-radius:8px">{ADP_ICONS['link']}</span><span>Internet Policy ที่ได้รับ</span></div><table class="adp-policy-table"><colgroup>{colgroup}</colgroup><thead><tr>{header}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></div>'''
        st.markdown(table, unsafe_allow_html=True)

    tab_user, tab_policy, tab_map = st.tabs([
        "ค้นหา User",
        "ค้นหา Policy",
        "Policy Mapping",
    ])

    with tab_user:
        default_identity = st.session_state.get("user_email", "")
        with st.container(border=True):
            st.markdown('<div class="adp-search-panel-marker"></div>', unsafe_allow_html=True)
            st.markdown('<div class="adp-field-label">User / Email / UPN</div>', unsafe_allow_html=True)
            col_identity, col_lookup, col_clear = st.columns([0.66, 0.17, 0.17])
            with col_identity:
                user_identity = st.text_input(
                    "User / Email / UPN",
                    value=default_identity,
                    placeholder="เช่น supranee.ch หรือ user@company.com",
                    key="ad_policy_user_identity",
                    label_visibility="collapsed",
                )
            with col_lookup:
                lookup_clicked = st.button("ตรวจสอบ Policy", type="primary", use_container_width=True, key="ad_policy_lookup")
            with col_clear:
                if st.button("ล้าง Cache AD", use_container_width=True, key="ad_policy_clear_cache"):
                    ldap_find_user.clear()
                    get_ldap_group_names_for_user.clear()
                    get_ad_agent_policy_summary.clear()
                    get_ad_agent_policy_users.clear()
                    graph_find_user.clear()
                    get_ad_group_names_for_user.clear()
                    load_firewall_policy_mapping.clear()
                    st.rerun()

        if lookup_clicked or user_identity:
            if not user_identity.strip():
                st.warning("กรุณาระบุ User / Email / UPN")
            else:
                with st.spinner("กำลังดึงข้อมูลจาก AD / Entra ID..."):
                    policy_summary = get_user_internet_policy_summary(user_identity)
                    user_obj = policy_summary.get("user", {}) if policy_summary.get("ok") else {}

                if user_obj:
                    adp_stat_grid([
                        ("Display Name", user_obj.get("displayName", "-") or "-", "user"),
                        ("Account", user_obj.get("sAMAccountName") or user_obj.get("userPrincipalName") or "-", "account"),
                        ("Mail", user_obj.get("mail") or "-", "mail"),
                        ("Source", policy_summary.get("source", "-"), "server"),
                    ])
                else:
                    st.warning("ไม่พบ User นี้จาก AD LDAP / AD Agent / Microsoft Graph หรือตั้งค่า source ยังไม่ครบ")

                if policy_summary.get("ok"):
                    policies = policy_summary.get("policies", [])
                    groups = policy_summary.get("groups", [])

                    adp_summary_grid(len(policies), len(groups))

                    if policies:
                        adp_policy_table(policies)
                        adp_now = datetime.datetime.now(
                            datetime.timezone(datetime.timedelta(hours=7))
                        )
                        adp_thai_months = [
                            "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
                            "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
                        ]
                        adp_updated_text = (
                            f"{adp_now.day} {adp_thai_months[adp_now.month - 1]} "
                            f"{adp_now.year} {adp_now:%H:%M}"
                        )
                        st.markdown(
                            f'''<div class="adp-table-footer-marker">
                                <svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>
                                <span>อัปเดตล่าสุด: {adp_updated_text}</span></div>''',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.info("ไม่พบ Internet Policy Group สำหรับ User นี้")
                else:
                    st.error(f"ยังดึงข้อมูล AD / Entra ID ไม่ได้: {policy_summary.get('error', '')}")

    with tab_policy:
        map_rows = load_firewall_policy_mapping()
        available_policies = sorted({
            str(row.get("AD Group", "")).strip()
            for row in map_rows
            if str(row.get("AD Group", "")).strip()
        })

        c_policy, c_manual = st.columns([0.42, 0.58])
        with c_policy:
            selected_policy = st.selectbox(
                "เลือก Policy",
                available_policies if available_policies else sorted(fw_policy_map.keys()),
                key="ad_policy_selected_policy",
            )
        with c_manual:
            manual_policy = st.text_input(
                "หรือพิมพ์ชื่อ Policy เอง",
                placeholder="เช่น FW_Officer_A",
                key="ad_policy_manual_policy",
            )

        policy_query = manual_policy.strip() or selected_policy

        col_search, col_cache = st.columns([0.52, 0.48])
        with col_search:
            policy_lookup_clicked = st.button("ค้นหา User", type="primary", use_container_width=True, key="ad_policy_policy_lookup")
        with col_cache:
            if st.button("ล้าง Cache Policy", use_container_width=True, key="ad_policy_policy_clear"):
                get_ad_agent_policy_users.clear()
                load_firewall_policy_mapping.clear()
                st.rerun()

        if policy_lookup_clicked or manual_policy.strip():
            with st.spinner(f"กำลังค้นหา User ที่ใช้ {policy_query}..."):
                policy_users = get_policy_users_summary(policy_query)

            if policy_users.get("ok"):
                users = policy_users.get("users", []) or []
                adp_stat_grid([
                    ("Policy", policy_users.get("policy", policy_query), "shield"),
                    ("Users", len(users), "user"),
                    ("Source", policy_users.get("source", "-"), "server"),
                ])

                desc = policy_users.get("description") or fw_policy_map.get(policy_query, "")
                if desc:
                    st.success(f"{policy_query}: {desc}")

                if users:
                    users_df = pd.DataFrame(users)
                    preferred_cols = [
                        "displayName",
                        "sAMAccountName",
                        "mail",
                        "department",
                        "title",
                        "company",
                    ]
                    show_cols = [c for c in preferred_cols if c in users_df.columns]
                    if show_cols:
                        users_df = users_df[show_cols]
                    users_df = users_df.rename(columns={
                        "displayName": "Display Name",
                        "sAMAccountName": "Account",
                        "userPrincipalName": "UPN",
                        "mail": "Mail",
                        "department": "Department",
                        "title": "Title",
                        "company": "Company",
                    })

                    st.dataframe(users_df, use_container_width=True, hide_index=True)
                    st.download_button(
                        "Export Users CSV",
                        data=users_df.to_csv(index=False).encode("utf-8-sig"),
                        file_name=f"{policy_query}_users.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
                else:
                    st.info("ไม่พบ User ที่อยู่ใน Policy นี้")
            else:
                st.error(f"ยังดึงรายชื่อ User ของ Policy นี้ไม่ได้: {policy_users.get('error', '')}")

        st.caption("หมายเหตุ: การค้นหา Policy ต้องใช้ AD Agent endpoint `/policy-users` เช่น `https://ad-agent.poonyaruk.co.th/policy-users?policy=FW_Officer_A`")

    with tab_map:
        st.caption(f"อ่าน mapping จาก SharePoint List: {firewall_policy_mapping_list} ถ้าไม่มีหรือว่าง ระบบจะใช้ Default Mapping ในโค้ด")
        map_rows = [
            row for row in load_firewall_policy_mapping()
            if str(row.get("AD Group", "")).strip().casefold() != "fw_supervisor_b"
        ]
        map_df = pd.DataFrame(map_rows)
        if not map_df.empty:
            st.dataframe(map_df, use_container_width=True, hide_index=True)
            st.download_button(
                "Export Policy Mapping CSV",
                data=map_df.to_csv(index=False).encode("utf-8-sig"),
                file_name="firewall_policy_mapping.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.info("ยังไม่มี Policy Mapping")
        st.caption(f"Policy prefixes: {', '.join(fw_policy_prefixes)}")
