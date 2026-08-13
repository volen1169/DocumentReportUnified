"""CSS theme constants for DocumentReportUnified.

Values are moved verbatim from the Streamlit entrypoint.
"""

COLORS = {
    "primary": "#6366F1",     # Indigo
    "secondary": "#8B5CF6",   # Purple
    "accent": "#38BDF8",      # Sky
    "success": "#10B981",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "bg": "#F8FAFC",
    "card": "#FFFFFF",
}



SIDEBAR_V32_THEME = """
<style>
/* LOGIN STYLE SIDEBAR */
section[data-testid="stSidebar"],
[data-testid="stSidebar"]{
    background:
        radial-gradient(circle at top left, rgba(56,189,248,.18), transparent 28%),
        radial-gradient(circle at bottom right, rgba(139,92,246,.15), transparent 30%),
        linear-gradient(135deg,#e0f2fe 0%,#dbeafe 35%,#ede9fe 100%) !important;
}

/* Sidebar inner container */
[data-testid="stSidebar"] > div:first-child{
    background:transparent !important;
}

/* Default text */
[data-testid="stSidebar"] *{
    color:#334155 !important;
}

/* Navigation buttons */
[data-testid="stSidebar"] .stButton > button{
    border-radius:16px !important;
}

/* Active menu */
[data-testid="stSidebar"] .stButton > button[kind="primary"]{
    background:transparent !important;
    color:#2563EB !important;
    border:none !important;
    border-left:4px solid #2563EB !important;
    box-shadow:none !important;
}

/* Badge */
.sidebar-badge{
    background:rgba(255,255,255,.65);
    backdrop-filter:blur(8px);
    border-radius:999px;
}

/* Profile card glass */
.profile-card{
    background:rgba(255,255,255,.30);
    backdrop-filter:blur(20px);
    border:1px solid rgba(255,255,255,.45);
    border-radius:20px;
}

/* ==========================================================
   FIX STREAMLIT SIDEBAR WHITE BOX
   ========================================================== */

[data-testid="stSidebar"]
[data-testid="stVerticalBlockBorderWrapper"]{
    background:transparent !important;
    border:none !important;
    box-shadow:none !important;
}

[data-testid="stSidebar"]
[data-testid="stVerticalBlockBorderWrapper"] > div{
    background:transparent !important;
    border:none !important;
    box-shadow:none !important;
    backdrop-filter:none !important;
}

[data-testid="stSidebar"]
[data-testid="stHorizontalBlock"]{
    background:transparent !important;
}

[data-testid="stSidebar"]
[data-testid="stHorizontalBlock"] > div{
    background:transparent !important;
    border:none !important;
    box-shadow:none !important;
}

[data-testid="stSidebar"]
div[data-testid="stVerticalBlock"]{
    background:transparent !important;
    border:none !important;
    box-shadow:none !important;
}

[data-testid="stSidebar"] .stButton{
    background:transparent !important;
    border:none !important;
    box-shadow:none !important;
}

/* ========================================================================= */
/* DEBUG REMOVE NAVIGATION WHITE BOX                                         */
/* ใช้ตรวจว่ากล่องขาวมาจากปุ่ม Secondary หรือไม่                          */
/* ========================================================================= */

[data-testid="stSidebar"] .stButton > button[kind="secondary"]{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    backdrop-filter: none !important;
}

[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover{
    background: rgba(255,255,255,0.12) !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    box-shadow: none !important;
}

/* ล้าง wrapper รอบปุ่ม */
[data-testid="stSidebar"] .stButton{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

/* ล้าง element-container ที่ Streamlit สร้าง */
[data-testid="stSidebar"] div[data-testid="stElementContainer"]{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

/* FORCE KILL ALL SIDEBAR BUTTON BACKGROUND */

[data-testid="stSidebar"] .stButton > button{
    background: transparent !important;
    box-shadow: none !important;
}

[data-testid="stSidebar"] .stButton > button:hover{
    box-shadow: none !important;
}


[data-testid="stSidebar"] button p,
[data-testid="stSidebar"] button span{
    background: transparent !important;
    border-radius: 0 !important;
    box-shadow: none !important;
}



</style>
"""


MODERN_THEME = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=IBM+Plex+Sans+Thai:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"]{font-family:'Inter','IBM Plex Sans Thai',sans-serif !important;}
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at top right, rgba(99,102,241,.10), transparent 22%),radial-gradient(circle at bottom left, rgba(14,165,233,.08), transparent 18%),#eef2ff !important;}
[data-testid="stMetric"]{background:rgba(255,255,255,.84) !important;border:none !important;border-radius:24px !important;padding:1.3rem !important;box-shadow:0 10px 30px rgba(15,23,42,.06) !important;}
[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"] > div{border:none !important;border-radius:24px !important;background:rgba(255,255,255,.86) !important;box-shadow:0 10px 30px rgba(15,23,42,.05) !important;transition:all .2s ease !important;}
[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"] > div:hover{transform:translateY(-2px);box-shadow:0 18px 40px rgba(99,102,241,.12) !important;}
[data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] > div{background:transparent !important;border:none !important;box-shadow:none !important;}
.stButton button{border-radius:14px !important;font-weight:700 !important;}
.stTextInput input,.stSelectbox div[data-baseweb="select"] > div{border-radius:14px !important;}
[data-testid="stDataFrame"]{border-radius:22px !important;overflow:hidden !important;}
</style>
"""
