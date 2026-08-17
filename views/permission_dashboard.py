import streamlit as st


def _render_module_hub(title, subtitle, icon, modules):
    """Render a flat module dashboard without adding sidebar submenus."""
    st.markdown("""
        <style>
        .hub-hero{position:relative;overflow:hidden;padding:25px 28px;margin-bottom:16px;border-radius:24px;color:#FFF;background:linear-gradient(125deg,#2563EB,#6366F1 56%,#8B5CF6);box-shadow:0 16px 38px rgba(79,70,229,.20)}
        .hub-hero:after{content:'';position:absolute;width:260px;height:260px;right:-75px;top:-135px;border-radius:50%;background:rgba(255,255,255,.10)}.hub-title{font-size:28px;font-weight:850;letter-spacing:-.035em}.hub-sub{margin-top:5px;font-size:13px;color:rgba(255,255,255,.82)}
        [class*="st-key-hub_card_"] .stButton>button{position:relative!important;align-items:flex-start!important;justify-content:flex-start!important;width:100%!important;min-height:132px!important;padding:18px 48px 18px 18px!important;border:1px solid #E2E8F0!important;border-radius:18px!important;background:#FFF!important;color:#172554!important;text-align:left!important;white-space:pre-line!important;box-shadow:0 7px 20px rgba(15,23,42,.045)!important}
        [class*="st-key-hub_card_"] .stButton>button:after{content:'';position:absolute;right:14px;bottom:14px;width:27px;height:27px;border:1px solid #C7D2FE;border-radius:50%;background:#FFF}
        [class*="st-key-hub_card_"] .stButton>button:before{content:'';position:absolute;right:25px;bottom:24px;width:6px;height:6px;border-top:2px solid #4F46E5;border-right:2px solid #4F46E5;transform:rotate(45deg);z-index:1}
        [class*="st-key-hub_card_"] .stButton>button:hover{transform:translateY(-3px)!important;border-color:#A5B4FC!important;box-shadow:0 14px 30px rgba(79,70,229,.11)!important}.hub-note{margin:14px 0 8px;color:#64748B;font-size:12px}
        [class*="st-key-hub_card_"] .stButton>button p{width:100%;white-space:pre-line!important;text-align:left!important;color:#64748B!important;font-size:12px!important;line-height:1.55!important;font-weight:500!important}[class*="st-key-hub_card_"] .stButton>button p:first-line{color:#172554!important;font-size:15px!important;font-weight:850!important}
        </style>
        """, unsafe_allow_html=True)
    st.markdown(f'<div class="hub-hero"><div class="hub-title">{icon} {title}</div><div class="hub-sub">{subtitle}</div></div>', unsafe_allow_html=True)
    _hub_cols = st.columns(3, gap="medium")
    for _hub_index, (_target, _item_icon, _item_title, _item_desc) in enumerate(modules):
        with _hub_cols[_hub_index % 3]:
            if st.button(f"{_item_icon}  {_item_title}\n{_item_desc}", key=f"hub_card_{title}_{_hub_index}_{_target}", use_container_width=True):
                st.session_state.active_nav = _target
                st.rerun()


def render_permission_dashboard():
    _render_module_hub(
        "Permission Dashboard",
        "ตรวจสอบสิทธิ์การเข้าถึงระบบและนโยบายเครือข่าย",
        "🔐",
        [
            ("user_perm", "📁", "NAS Permission", "ตรวจสอบสิทธิ์การเข้าถึง NAS Shares"),
            ("ad_policy", "🛡️", "AD / Firewall", "ตรวจสอบ Internet Policy จาก AD / Entra ID"),
        ],
    )
