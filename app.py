import streamlit as st
import base64
import json
import csv
from pathlib import Path
from datetime import datetime

# ---------------------------
# CONFIG
# ---------------------------
st.set_page_config(
    page_title="PIATTAFORMA • CORSO PL",
    page_icon="🚓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

COURSE_PASSWORD = "polizia2026"      # password corsista
TEACHER_PASSWORD = "docente2026"     # password docente (cambiala)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# ---------------------------
# HELPERS
# ---------------------------
def img_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()

def ensure_state():
    st.session_state.setdefault("is_auth", False)
    st.session_state.setdefault("is_teacher", False)
    st.session_state.setdefault("user_name", "")
    st.session_state.setdefault("page", "HOME")  # HOME | QUIZ | CASI | BANCA | DOCENTE

def logout():
    st.session_state.is_auth = False
    st.session_state.is_teacher = False
    st.session_state.user_name = ""
    st.session_state.page = "HOME"
    st.rerun()

def goto(page: str):
    st.session_state.page = page
    st.rerun()

def safe_load_items_from_upload(uploaded_file):
    """
    Accetta:
      - JSON: lista di domande (dict)
      - CSV: colonne consigliate:
          domanda, A, B, C, corretta, spiegazione (facoltativa)
    Ritorna: list[dict]
    """
    name = uploaded_file.name.lower()
    raw = uploaded_file.getvalue()

    if name.endswith(".json"):
        data = json.loads(raw.decode("utf-8"))
        if isinstance(data, dict) and "items" in data:
            data = data["items"]
        if not isinstance(data, list):
            raise ValueError("JSON non valido: deve essere una LISTA di domande (oppure {'items':[...]}).")
        return data

    if name.endswith(".csv"):
        text = raw.decode("utf-8", errors="ignore").splitlines()
        reader = csv.DictReader(text)
        items = []
        for r in reader:
            # normalizzo chiavi
            domanda = (r.get("domanda") or r.get("Domanda") or "").strip()
            A = (r.get("A") or r.get("a") or "").strip()
            B = (r.get("B") or r.get("b") or "").strip()
            C = (r.get("C") or r.get("c") or "").strip()
            corretta = (r.get("corretta") or r.get("Corretta") or r.get("risposta") or "").strip()
            spiegazione = (r.get("spiegazione") or r.get("Spiegazione") or "").strip()

            if not domanda or not A or not B or not C:
                # salto righe incomplete
                continue

            item = {
                "domanda": domanda,
                "opzioni": [A, B, C],
                "corretta": corretta,      # può essere "A"/"B"/"C" oppure testo
                "spiegazione": spiegazione
            }
            items.append(item)

        if not items:
            raise ValueError("CSV letto ma nessuna riga valida. Controlla intestazioni e colonne.")
        return items

    raise ValueError("Formato non supportato. Carica solo .json o .csv")

def save_bank(target: str, items: list, label: str = ""):
    """
    target: QUIZ | CASI | BANCA
    Salva un file JSON in data/<target>_bank.json
    """
    file_map = {
        "QUIZ": DATA_DIR / "quiz_bank.json",
        "CASI": DATA_DIR / "casi_bank.json",
        "BANCA": DATA_DIR / "bancadati_bank.json",
    }
    path = file_map[target]
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(existing, list):
            existing = []
    else:
        existing = []

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    for it in items:
        it.setdefault("tag", label.strip())
        it.setdefault("created_at", stamp)

    existing.extend(items)
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    return path, len(items), len(existing)

def load_bank(target: str):
    file_map = {
        "QUIZ": DATA_DIR / "quiz_bank.json",
        "CASI": DATA_DIR / "casi_bank.json",
        "BANCA": DATA_DIR / "bancadati_bank.json",
    }
    path = file_map[target]
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []

# ---------------------------
# INIT
# ---------------------------
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
# STYLES (i tuoi)
# ---------------------------
st.markdown(
    f"""
    <style>
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
        font-size: 46px;
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

    #card_marker {{ display:none; }}
    div[data-testid="stVerticalBlock"]:has(#card_marker) {{
        max-width: 760px;
        margin: 0 auto;
        padding: 18px;
        border-radius: 18px;
        background: linear-gradient(180deg, rgba(255,255,255,0.20) 0%, rgba(255,255,255,0.14) 100%);
        border: 1px solid rgba(255,255,255,0.22);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        box-shadow: 0 28px 90px rgba(0,0,0,0.28);
    }}

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

    @media (max-width: 640px) {{
        .block-container {{
            padding-left: 12px !important;
            padding-right: 12px !important;
        }}
        .hero h1 {{ font-size: 34px; }}
        .menu-wrap {{ grid-template-columns: 1fr; }}
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------------------
# HERO
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

# marker
st.markdown('<div id="card_marker"></div>', unsafe_allow_html=True)

# ---------------------------
# LOGIN
# ---------------------------
if not st.session_state.is_auth:
    st.markdown('<div class="login-pill">Accesso (corsista o docente)</div>', unsafe_allow_html=True)

    nome = st.text_input("", placeholder="Nome e Cognome (es. Mario Rossi)")

    colA, colB = st.columns([1, 1])
    with colA:
        password = st.text_input("Password corsista", type="password", label_visibility="collapsed",
                                 placeholder="Password corsista")
    with colB:
        docente_flag = st.checkbox("Spunta docente")

    docente_pass = ""
    if docente_flag:
        docente_pass = st.text_input("Password docente", type="password", label_visibility="collapsed",
                                     placeholder="Password docente")

    if st.button("Entra"):
        if not nome.strip():
            st.error("Inserisci Nome e Cognome.")
        elif docente_flag:
            if docente_pass.strip() != TEACHER_PASSWORD:
                st.error("Password docente errata.")
            else:
                st.session_state.is_auth = True
                st.session_state.is_teacher = True
                st.session_state.user_name = nome.strip()
                st.session_state.page = "DOCENTE"
                st.rerun()
        else:
            if password.strip() != COURSE_PASSWORD:
                st.error("Password corsista errata.")
            else:
                st.session_state.is_auth = True
                st.session_state.is_teacher = False
                st.session_state.user_name = nome.strip()
                st.session_state.page = "HOME"
                st.rerun()

    st.caption("Suggerimento: per il docente entra con la spunta e la password docente.")
    st.stop()

# ---------------------------
# TOP BAR
# ---------------------------
left, right = st.columns([3, 1])
with left:
    role = "DOCENTE" if st.session_state.is_teacher else "CORSISTA"
    st.markdown(
        f"<div class='login-pill'>Loggato: <b>{st.session_state.user_name}</b> · Ruolo: <b>{role}</b></div>",
        unsafe_allow_html=True
    )
with right:
    if st.button("Esci"):
        logout()

# ---------------------------
# PAGES RENDER
# ---------------------------
def render_home():
    st.markdown("<div class='menu-wrap'>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        <div class='menu-card'>
          <h3>⏱️ Simulazione quiz</h3>
          <p>Prova completa · timer e report finale</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Apri quiz"):
            goto("QUIZ")

    with c2:
        st.markdown("""
        <div class='menu-card'>
          <h3>🧩 Prova pratica</h3>
          <p>Caso pratico · timer e correzione del test</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Apri caso pratico"):
            goto("CASI")

    with c3:
        st.markdown("""
        <div class='menu-card'>
          <h3>📚 Banca dati</h3>
          <p>Studio libero · ricerca e consultazione</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Apri banca dati"):
            goto("BANCA")

    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.is_teacher:
        st.divider()
        if st.button("👨‍🏫 Area docente"):
            goto("DOCENTE")

def render_docente():
    st.subheader("👨‍🏫 Area docente — Carica contenuti")
    st.write("Carica un file **CSV o JSON** e scegli dove inserirlo: **Quiz / Casi pratici / Banca dati**.")

    target = st.selectbox("Dove vuoi salvarlo?", ["QUIZ", "CASI", "BANCA"])
    label = st.text_input("Etichetta / tag (facoltativo)", placeholder="es. CDS, Penale, Amministrativo...")

    up = st.file_uploader("Carica file (.csv o .json)", type=["csv", "json"])
    if up is not None:
        try:
            items = safe_load_items_from_upload(up)
            st.success(f"Letti {len(items)} elementi dal file.")
            st.json(items[0] if items else {})
            if st.button("✅ Salva in piattaforma"):
                path, added, total = save_bank(target, items, label=label)
                st.success(f"Salvati {added} elementi in {path.name}. Totale ora: {total}")
        except Exception as e:
            st.error(f"Errore nel caricamento: {e}")

    st.divider()
    st.write("📌 Contenuti attualmente presenti:")
    q = len(load_bank("QUIZ"))
    c = len(load_bank("CASI"))
    b = len(load_bank("BANCA"))
    st.info(f"QUIZ: {q} · CASI: {c} · BANCA DATI: {b}")

    st.divider()
    if st.button("⬅️ Torna alla home"):
        goto("HOME")

def render_quiz():
    st.subheader("⏱️ Simulazione quiz")
    items = load_bank("QUIZ")
    if not items:
        st.warning("Nessun quiz caricato. (Docente: carica da Area docente)")
        if st.button("⬅️ Home"):
            goto("HOME")
        return

    st.write(f"Totale quiz disponibili: **{len(items)}**")

    # demo minimale: mostra i primi 5
    n = st.slider("Quanti visualizzare (demo)", 1, min(20, len(items)), 5)
    for i, it in enumerate(items[:n], start=1):
        st.markdown(f"**{i}. {it.get('domanda','(senza testo)')}**")
        opts = it.get("opzioni", [])
        if opts:
            st.radio("Risposta", opts, key=f"q_{i}", label_visibility="collapsed")
        st.divider()

    if st.button("⬅️ Home"):
        goto("HOME")

def render_casi():
    st.subheader("🧩 Casi pratici")
    items = load_bank("CASI")
    if not items:
        st.warning("Nessun caso pratico caricato. (Docente: carica da Area docente)")
        if st.button("⬅️ Home"):
            goto("HOME")
        return

    st.write(f"Totale casi disponibili: **{len(items)}**")
    st.json(items[0])
    if st.button("⬅️ Home"):
        goto("HOME")

def render_banca():
    st.subheader("📚 Banca dati")
    items = load_bank("BANCA")
    if not items:
        st.warning("Banca dati vuota. (Docente: carica da Area docente)")
        if st.button("⬅️ Home"):
            goto("HOME")
        return

    st.write(f"Totale elementi in banca dati: **{len(items)}**")
    q = st.text_input("Cerca nel testo domanda", placeholder="Scrivi una parola chiave...")
    filtered = items
    if q.strip():
        qq = q.strip().lower()
        filtered = [x for x in items if qq in (x.get("domanda","").lower())]

    st.write(f"Risultati: **{len(filtered)}**")
    for it in filtered[:10]:
        st.markdown(f"- {it.get('domanda','(senza testo)')}")
    if len(filtered) > 10:
        st.caption("Mostro solo i primi 10 risultati (demo).")

    if st.button("⬅️ Home"):
        goto("HOME")

# ---------------------------
# ROUTING
# ---------------------------
if st.session_state.page == "HOME":
    render_home()
elif st.session_state.page == "DOCENTE":
    if not st.session_state.is_teacher:
        st.error("Accesso negato: area docente.")
        if st.button("⬅️ Home"):
            goto("HOME")
    else:
        render_docente()
elif st.session_state.page == "QUIZ":
    render_quiz()
elif st.session_state.page == "CASI":
    render_casi()
elif st.session_state.page == "BANCA":
    render_banca()
else:
    goto("HOME")
