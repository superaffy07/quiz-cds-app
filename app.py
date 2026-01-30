import streamlit as st
import base64
from pathlib import Path

# ---------------------------
# CONFIG
# ---------------------------
st.set_page_config(
    page_title="PIATTAFORMA • CORSO PL",
    page_icon="🚓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

COURSE_PASSWORD = "polizia2026"  # password unica per ora


# ---------------------------
# HELPERS
# ---------------------------
def img_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def ensure_state():
    if "is_auth" not in st.session_state:
        st.session_state.is_auth = False
    if "user_name" not in st.session_state:
        st.session_state.user_name = ""


def logout():
    st.session_state.is_auth = False
    st.session_state.user_name = ""
    st.rerun()


ensure_state()

# ---------------------------
# BACKGROUND
# ---------------------------
bg_path = Path("assets/bg.png")
if not bg_path.exists():
    st.error("❌ Non trovo assets/bg.png")
    st.stop()

bg_b64 = img_to_base64(bg_path)

# ---------------------------
# STYLES (parto dal tuo stile e aggiungo dashboard + fix)
# ---------------------------
st.markdown(
    f"""
    <style>
    /* ---------------------------
       GLOBAL / BACKGROUND
    --------------------------- */
    .stApp {{
        background: url("data:image/png;base64,{bg_b64}") no-repeat center center fixed;
        background-size: cover;
    }}
    #MainMenu {{visibility:hidden;}}
    footer {{visibility:hidden;}}
    header {{visibility:hidden;}}
    section[data-testid="stSidebar"] {{display:none;}}

    .stApp::before {{
        content: "";
        position: fixed;
        inset: 0;
        background: radial-gradient(ellipse at top, rgba(0,0,0,0.32), rgba(0,0,0,0.12) 45%, rgba(0,0,0,0.34));
        pointer-events: none;
        z-index: 0;
    }}

    .block-container {{
        position: relative;
        z-index: 1;
        padding-top: 14px !important;
        padding-bottom: 14px !important;
        max-width: 1100px !important;
    }}

    /* ---------------------------
       HERO
    --------------------------- */
    .hero {{
        text-align: center;
        color: rgba(255,255,255,0.96);
        text-shadow: 0 10px 30px rgba(0,0,0,0.45);
        margin-top: 4px;
        margin-bottom: 8px;
    }}

    .pill {{
        display:inline-flex;
        align-items:center;
        gap:10px;
        padding: 9px 16px;
        border-radius: 999px;
        background: rgba(255,255,255,0.14);
        border: 1px solid rgba(255,255,255,0.20);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        font-weight: 850;
        letter-spacing: 0.35px;
        margin-bottom: 12px;
        font-size: 13px;
    }}

    .hero h1 {{
        font-size: 46px;      /* un filo più “piccolo” */
        line-height: 1.04;
        margin: 0 0 8px 0;
        font-weight: 950;
        letter-spacing: 0.2px;
    }}

    .hero .sub {{
        font-size: 18px;
        font-weight: 900;
        opacity: 0.98;
        margin-top: 4px;
    }}

    /* ---------------------------
       ACCESS BADGE
    --------------------------- */
    .login-pill {{
        width: fit-content;
        margin: 12px auto 10px auto;
        padding: 10px 16px;
        border-radius: 999px;
        background: rgba(20, 23, 35, 0.35);
        border: 1px solid rgba(255,255,255,0.20);
        color: rgba(255,255,255,0.96);
        font-weight: 900;
        letter-spacing: 0.25px;
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        text-shadow: 0 6px 18px rgba(0,0,0,0.55);
        font-size: 14px;
    }}

    /* ---------------------------
       REAL CARD BLOCK (LOGIN/DASH)
    --------------------------- */
    #card_marker {{ display:none; }}

    div[data-testid="stVerticalBlock"]:has(#card_marker) {{
        max-width: 660px;
        margin: 0 auto;
        padding: 18px;
        border-radius: 18px;
        background: linear-gradient(180deg, rgba(255,255,255,0.20) 0%, rgba(255,255,255,0.14) 100%);
        border: 1px solid rgba(255,255,255,0.22);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        box-shadow: 0 28px 90px rgba(0,0,0,0.28);
    }}

    /* ---------------------------
       INPUTS / FOCUS
    --------------------------- */
    div[data-baseweb="base-input"] > div {{
        border-radius: 12px !important;
        background: rgba(255,255,255,0.82) !important;
        border: 1px solid rgba(0,0,0,0.10) !important;
    }}

    div[data-baseweb="base-input"] > div:focus-within {{
        border: 1px solid rgba(255,203,102,0.95) !important;
        box-shadow: 0 0 0 4px rgba(255,203,102,0.22) !important;
    }}

    input {{
        padding: 12px 12px !important;
        font-size: 16px !important;
        font-weight: 900 !important;
        color: rgba(0,0,0,0.88) !important;
    }}

    input::placeholder {{
        color: rgba(0,0,0,0.45) !important;
        font-weight: 750 !important;
    }}

    /* ---------------------------
       BUTTONS
    --------------------------- */
    .stButton {{
        display: flex !important;
        justify-content: center !important;
        width: 100% !important;
        margin-top: 10px !important;
    }}

    .stButton > button {{
        width: auto !important;
        margin-left: auto !important;
        margin-right: auto !important;
        padding: 11px 26px !important;
        font-size: 16px !important;
        font-weight: 950 !important;
        border-radius: 14px !important;
        border: 1px solid rgba(0,0,0,0.18) !important;
        background: linear-gradient(180deg, rgba(255,203,102,1) 0%, rgba(226,155,56,1) 100%) !important;
        color: rgba(0,0,0,0.86) !important;
        box-shadow: 0 10px 28px rgba(0,0,0,0.25) !important;
        display: block !important;
        transition: transform .08s ease, filter .12s ease;
    }}

    .stButton > button:hover {{
        filter: brightness(1.04);
    }}

    .stButton > button:active {{
        transform: translateY(1px);
    }}

    /* ---------------------------
       FOOTER TEXT
    --------------------------- */
    .foot {{
        text-align: center;
        margin-top: 10px;
        font-size: 13px;
        font-style: italic;
        color: rgba(255,255,255,0.92);
        text-shadow: 0 6px 18px rgba(0,0,0,0.55);
    }}

    /* ---------------------------
       DASHBOARD CARDS
    --------------------------- */
    .dash-title {{
        text-align:center;
        color: rgba(255,255,255,0.95);
        font-weight: 950;
        font-size: 18px;
        margin: 2px 0 12px;
        text-shadow: 0 10px 28px rgba(0,0,0,0.45);
    }}

    .menu-wrap {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
        margin-top: 12px;
    }}

    .menu-card {{
        background: rgba(255,255,255,0.10);
        border: 1px solid rgba(255,255,255,0.16);
        border-radius: 14px;
        padding: 12px;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        box-shadow: 0 18px 50px rgba(0,0,0,0.20);
        text-align: left;
    }}

    .menu-card h3 {{
        margin: 0 0 4px 0;
        color: rgba(255,255,255,0.95);
        font-size: 16px;
        font-weight: 950;
    }}

    .menu-card p {{
        margin: 0;
        color: rgba(255,255,255,0.82);
        font-size: 13px;
        font-weight: 650;
    }}

    /* ---------------------------
       RESPONSIVE (MOBILE)
    --------------------------- */
    @media (max-width: 640px) {{
        .block-container {{
            padding-top: 10px !important;
            padding-left: 12px !important;
            padding-right: 12px !important;
        }}

        .hero h1 {{
            font-size: 34px;
            line-height: 1.08;
        }}

        .hero .sub {{
            font-size: 15px;
        }}

        div[data-testid="stVerticalBlock"]:has(#card_marker) {{
            max-width: 92vw;
            padding: 14px;
            border-radius: 16px;
        }}

        .stButton > button {{
            width: 100% !important;
            padding: 13px 16px !important;
            border-radius: 16px !important;
            font-size: 16px !important;
        }}

        .menu-wrap {{
            grid-template-columns: 1fr;
        }}
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------------------
# UI - HERO
# ---------------------------
st.markdown(
    """
    <div class="hero">
      <div class="pill">🚓 <span>PIATTAFORMA • CORSO PL</span></div>
      <h1>Banca dati, simulazioni e quiz</h1>
      <div class="sub">Piattaforma didattica a cura di Raffaele Sotero</div>
    </div>
    """,
    unsafe_allow_html=True
)

# badge
st.markdown('<div class="login-pill">Accesso corsista</div>', unsafe_allow_html=True)

# marker: stessa “card” sia per login che per dashboard
st.markdown('<div id="card_marker"></div>', unsafe_allow_html=True)

# ---------------------------
# ROUTER: se autenticato -> dashboard, altrimenti login
# ---------------------------
if not st.session_state.is_auth:
    nome = st.text_input("", placeholder="Nome e Cognome (es. Mario Rossi)")
    password = st.text_input("", type="password", placeholder="Password del corso")

    if st.button("Entra"):
        if not nome.strip() or not password.strip():
            st.error("Inserisci Nome e Cognome e la password del corso.")
        elif password.strip() != COURSE_PASSWORD:
            st.error("Password errata.")
        else:
            st.session_state.is_auth = True
            st.session_state.user_name = nome.strip()
            st.rerun()

    st.markdown(
        "<div class='foot'>Accesso riservato ai corsisti · Inserisci Nome e Cognome e la password del corso.</div>",
        unsafe_allow_html=True
    )
else:
    st.markdown(
        f"<div class='dash-title'>Benvenuto, {st.session_state.user_name} 👋 — Seleziona una modalità</div>",
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class='menu-card'>
              <h3>⏱️ Simulazione quiz</h3>
              <p>Prova completa · timer e report finale</p>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("Apri quiz"):
            st.switch_page("pages/3_Simulazioni.py")

    with col2:
        st.markdown(
            """
            <div class='menu-card'>
              <h3>🧩 Prova pratica</h3>
              <p>Caso pratico · timer e correzione del test</p>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("Apri caso pratico"):
            st.switch_page("pages/4_Casi_Pratici.py")

    with col3:
        st.markdown(
            """
            <div class='menu-card'>
              <h3>📚 Banca dati</h3>
              <p>Studio libero · ricerca e consultazione</p>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("Apri banca dati"):
            st.switch_page("pages/2_Banca_Dati.py")

    st.divider()
    if st.button("Esci"):
        logout()

    st.markdown(
        "<div class='foot'>Accesso effettuato · Seleziona una sezione oppure premi Esci.</div>",
        unsafe_allow_html=True
    )
