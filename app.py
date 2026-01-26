import os
import time
import random
import csv
import io
import base64
from datetime import datetime, timezone
from typing import List, Dict, Optional

# =========================================================
# Dipendenze esterne (Streamlit + Supabase)
# =========================================================
try:
    import streamlit as st
    import streamlit.components.v1 as components
except ModuleNotFoundError:
    raise SystemExit(
        "Errore: manca la libreria 'streamlit'.\n"
        "Questa app è una UI web e richiede Streamlit per funzionare.\n"
        "Esegui (nel tuo venv):\n"
        "  python -m pip install streamlit\n"
        "Poi avvia con:\n"
        '  python -m streamlit run "app (23).py"\n'
    )

try:
    from supabase import create_client, Client
except ModuleNotFoundError:
    raise SystemExit(
        "Errore: manca la libreria 'supabase'.\n"
        "Questa app usa Supabase come database.\n"
        "Installa nel venv:\n"
        "  python -m pip install supabase\n"
    )

# =========================================================
# PAGE CONFIG (UNA SOLA VOLTA, IN TESTA AL FILE)
# =========================================================
st.set_page_config(
    page_title="Banca dati, simulazioni e quiz — Corso PL 2026",
    page_icon="🚓",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =========================================================
# COSTANTI
# =========================================================
N_QUESTIONS_DEFAULT = 30
DURATION_SECONDS_DEFAULT = 30 * 60  # 30 minuti

COURSE_PASSWORD = "polizia2026"
COURSE_CLASS_CODE = "CORSO_PL_2026"

# =========================================================
# Helpers
# =========================================================
def get_secret(name: str, default: str = "") -> str:
    try:
        v = st.secrets.get(name, default)
        if v:
            return v
    except Exception:
        pass
    return os.getenv(name, default)


def load_local_background_base64(
    filenames: tuple[str, ...] = ("background.jpg", "background.jpeg", "background.png", "bg.jpg", "bg.png")
) -> Optional[str]:
    """
    Carica un file immagine locale (se presente) e lo converte in data URL base64
    per usarlo come background in CSS.
    """
    for fn in filenames:
        if os.path.exists(fn) and os.path.isfile(fn):
            ext = fn.split(".")[-1].lower()
            mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
            with open(fn, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            return f"data:{mime};base64,{b64}"
    return None


def render_live_timer(end_ts: float):
    """
    Countdown fluido aggiornato lato browser (no rerun Streamlit).
    """
    end_ms = int(end_ts * 1000)
    components.html(
        f"""
        <div class="timer-wrap">
          <div class="timer-label">⏱️ Tempo residuo: <span id="tval">--:--</span></div>
        </div>
        <script>
          const end = {end_ms};
          function pad(n) {{ return String(n).padStart(2,'0'); }}
          function tick(){{
            const now = Date.now();
            let remaining = Math.max(0, Math.floor((end - now)/1000));
            const m = Math.floor(remaining/60);
            const s = remaining % 60;
            const el = document.getElementById("tval");
            if (el) el.textContent = pad(m) + ":" + pad(s);
          }}
          tick();
          setInterval(tick, 1000);
        </script>
        """,
        height=44,
    )


# =========================================================
# SUPABASE INIT
# =========================================================
SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_ANON_KEY = get_secret("SUPABASE_ANON_KEY")
ADMIN_CODE = get_secret("ADMIN_CODE", "DOCENTE123")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("Mancano SUPABASE_URL / SUPABASE_ANON_KEY nelle Secrets (o env).")
    st.stop()

sb: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# =========================================================
# DB HELPERS
# =========================================================
def upsert_student(class_code: str, nickname: str) -> Dict:
    class_code = class_code.strip()
    nickname = nickname.strip()

    res = (
        sb.table("students")
        .select("*")
        .eq("class_code", class_code)
        .eq("nickname", nickname)
        .limit(1)
        .execute()
        .data
    )
    if res:
        return res[0]

    ins = sb.table("students").insert({"class_code": class_code, "nickname": nickname}).execute().data
    return ins[0]


def create_session(student_id: int, n_questions: int) -> Dict:
    payload = {
        "student_id": student_id,
        "mode": "sim",
        "topic_scope": "bank",
        "selected_topic_id": None,
        "n_questions": int(n_questions),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    return sb.table("sessions").insert(payload).execute().data[0]


def finish_session(session_id: str) -> None:
    sb.table("sessions").update({"finished_at": datetime.now(timezone.utc).isoformat()}).eq("id", session_id).execute()


def fetch_bank_count() -> int:
    res = sb.table("question_bank").select("id", count="exact").limit(1).execute()
    return int(res.count or 0)


def fetch_all_bank_questions() -> List[Dict]:
    return sb.table("question_bank").select("*").order("id").execute().data or []


def insert_session_questions(session_id: str, questions: List[Dict]) -> None:
    rows = []
    for q in questions:
        qa = (q.get("question_text") or "").strip()
        oa = (q.get("option_a") or "").strip()
        ob = (q.get("option_b") or "").strip()
        oc = (q.get("option_c") or "").strip()
        od = (q.get("option_d") or "").strip()

        co = (q.get("correct_option") or "").strip().upper()
        if co not in ["A", "B", "C", "D"]:
            co = "A"

        if od == "" and co == "D":
            if oc:
                co = "C"
            elif ob:
                co = "B"
            else:
                co = "A"

        rows.append(
            {
                "session_id": session_id,
                "topic_id": None,
                "question_text": qa,
                "option_a": oa,
                "option_b": ob,
                "option_c": oc,
                "option_d": od if od else "",
                "correct_option": co,
                "chosen_option": None,
                "explanation": (q.get("explanation") or "").strip(),
            }
        )

    if rows:
        sb.table("quiz_answers").insert(rows).execute()


def fetch_session_questions(session_id: str) -> List[Dict]:
    return (
        sb.table("quiz_answers")
        .select("*")
        .eq("session_id", session_id)
        .order("id")
        .execute()
        .data
        or []
    )


def update_chosen_option(row_id: int, session_id: str, chosen_letter: Optional[str]) -> None:
    sb.table("quiz_answers").update({"chosen_option": chosen_letter}).eq("id", row_id).eq("session_id", session_id).execute()


# =========================================================
# CSV upload (no pandas)
# =========================================================
REQUIRED_COLUMNS = ["question_text", "option_a", "option_b", "option_c", "option_d", "correct_option"]

def parse_csv_questions(raw_bytes: bytes) -> List[Dict]:
    """
    Legge CSV da bytes con encoding robusto. Non richiede pandas.
    Supporta colonna opzionale: explanation
    """
    text = None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            text = None

    if text is None:
        raise ValueError("Impossibile decodificare il CSV. Salvalo come UTF-8 (consigliato).")

    reader = csv.DictReader(io.StringIO(text))
    cols = reader.fieldnames or []
    missing = [c for c in REQUIRED_COLUMNS if c not in cols]
    if missing:
        raise ValueError(f"Mancano colonne richieste: {missing}")

    rows: List[Dict] = []
    for i, r in enumerate(reader, start=2):  # 1 = header, quindi dati da riga 2
        rr = {k: (r.get(k, "") or "").strip() for k in cols}
        rr.setdefault("explanation", "")
        rr["correct_option"] = rr["correct_option"].upper()

        if rr["correct_option"] not in ("A", "B", "C", "D"):
            raise ValueError(f"Riga {i}: correct_option non valido ({rr['correct_option']}). Deve essere A/B/C/D.")

        if rr["correct_option"] == "D" and rr.get("option_d", "") == "":
            raise ValueError(f"Riga {i}: correct_option = D ma option_d è vuota.")

        rows.append(
            {
                "question_text": rr["question_text"],
                "option_a": rr["option_a"],
                "option_b": rr["option_b"],
                "option_c": rr["option_c"],
                "option_d": rr["option_d"],
                "correct_option": rr["correct_option"],
                "explanation": rr.get("explanation", ""),
            }
        )

    if not rows:
        raise ValueError("CSV vuoto: nessuna domanda trovata.")
    return rows


# =========================================================
# SESSION STATE
# =========================================================
def ss_init():
    defaults = {
        "logged": False,
        "student": None,
        "session_id": None,
        "in_progress": False,
        "show_results": False,
        "started_ts": None,
        "finished_ts": None,
        "duration_seconds": DURATION_SECONDS_DEFAULT,
        "n_questions": N_QUESTIONS_DEFAULT,
        "menu_page": "home",  # home | sim | bank | case
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

ss_init()

# =========================================================
# THEME / UI — Stile "super professionale" (come immagine)
# =========================================================
BG_DATA_URL = load_local_background_base64()
BG_CSS = f'url("{BG_DATA_URL}")' if BG_DATA_URL else "none"

CUSTOM_CSS = f"""
<style>
@import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=Oswald:wght@400;600&display=swap");

:root {{
  --bg0: #070A12;
  --bg1: #0B1220;
  --text: rgba(255,255,255,.92);
  --muted: rgba(255,255,255,.72);

  --glass: rgba(255,255,255,.10);
  --glass2: rgba(255,255,255,.14);
  --stroke: rgba(255,255,255,.16);

  --gold: #E6B25A;
  --gold2:#F2C76D;
  --navy: #0B1D2B;
  --blue: #1A5CFF;
  --red: #FF2D55;

  --shadow: 0 22px 60px rgba(0,0,0,.40);
}}

html, body, [class*="css"] {{
  font-family: Inter, "Segoe UI", sans-serif;
}}

.stApp {{
  background:
    radial-gradient(1000px 500px at 18% 15%, rgba(26,92,255,.35), transparent 58%),
    radial-gradient(900px 500px at 82% 18%, rgba(255,45,85,.35), transparent 60%),
    radial-gradient(1200px 900px at 55% 110%, rgba(255,255,255,.07), transparent 55%),
    linear-gradient(180deg, var(--bg0) 0%, var(--bg1) 100%);
  color: var(--text);
  {f"background-image: {BG_CSS}; background-size: cover; background-position: center; background-repeat: no-repeat;" if BG_DATA_URL else ""}
}}

.block-container {{
  max-width: 1200px;
  padding-top: 1.2rem;
  padding-bottom: 2.4rem;
}}

header, footer {{
  visibility: hidden;
  height: 0px;
}}

div[data-testid="stSidebar"] {{
  display: none;
}}

a {{
  color: var(--gold2);
}}

.top-pill {{
  display:inline-flex;
  align-items:center;
  gap:10px;
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(255,255,255,.10);
  border: 1px solid rgba(255,255,255,.14);
  backdrop-filter: blur(10px);
  box-shadow: 0 10px 24px rgba(0,0,0,.22);
  font-weight: 700;
  letter-spacing: .3px;
}}

.hero-title {{
  font-family: Oswald, Inter, sans-serif;
  font-size: 54px;
  line-height: 1.02;
  margin: 18px 0 10px 0;
  text-shadow: 0 10px 30px rgba(0,0,0,.35);
}}

.hero-sub {{
  color: var(--muted);
  font-size: 16px;
  line-height: 1.55;
  max-width: 760px;
}}

.hero-actions {{
  margin-top: 14px;
  display:flex;
  gap:10px;
  flex-wrap: wrap;
  align-items: center;
}}

.chip {{
  display:inline-flex;
  align-items:center;
  gap:10px;
  padding: 9px 12px;
  border-radius: 999px;
  background: rgba(255,255,255,.08);
  border: 1px solid rgba(255,255,255,.14);
  backdrop-filter: blur(10px);
  color: var(--text);
  font-weight: 700;
  font-size: 12px;
}}

.login-shell {{
  margin-top: 22px;
  display: grid;
  grid-template-columns: 1.1fr .9fr;
  gap: 18px;
  align-items: stretch;
}}
@media (max-width: 980px){{
  .login-shell {{ grid-template-columns: 1fr; }}
}}

.glass-card {{
  background: rgba(255,255,255,.10);
  border: 1px solid rgba(255,255,255,.16);
  border-radius: 22px;
  box-shadow: var(--shadow);
  backdrop-filter: blur(14px);
  overflow: hidden;
  position: relative;
}}

.glass-card:before {{
  content:"";
  position:absolute;
  inset: 0;
  background:
    radial-gradient(500px 200px at 18% 10%, rgba(26,92,255,.18), transparent 60%),
    radial-gradient(500px 200px at 82% 10%, rgba(255,45,85,.18), transparent 62%);
  pointer-events: none;
}}

.card-pad {{
  padding: 22px 22px;
  position: relative;
  z-index: 1;
}}

.card-title {{
  font-family: Oswald, Inter, sans-serif;
  font-size: 30px;
  margin: 0 0 6px 0;
}}

.card-sub {{
  margin: 0 0 14px 0;
  color: var(--muted);
  line-height: 1.45;
}}

.divider-soft {{
  height: 1px;
  background: rgba(255,255,255,.14);
  margin: 14px 0;
}}

.small-note {{
  color: rgba(255,255,255,.68);
  font-size: 12px;
}}

.timer-wrap {{
  background: rgba(255,255,255,.10);
  border: 1px solid rgba(255,255,255,.14);
  border-radius: 16px;
  padding: 10px 12px;
  backdrop-filter: blur(10px);
  box-shadow: 0 10px 22px rgba(0,0,0,.22);
}}
.timer-label {{
  font-weight: 900;
  letter-spacing: .2px;
}}

.stTabs [data-baseweb="tab-list"] {{
  gap: 10px;
  padding: 8px;
  border-radius: 16px;
  background: rgba(255,255,255,.08);
  border: 1px solid rgba(255,255,255,.14);
  backdrop-filter: blur(10px);
}}
.stTabs [data-baseweb="tab"] {{
  border-radius: 14px;
  padding: 10px 14px;
  color: rgba(255,255,255,.78);
  font-weight: 800;
}}
.stTabs [aria-selected="true"] {{
  background: rgba(255,255,255,.12) !important;
  border: 1px solid rgba(255,255,255,.16) !important;
  color: rgba(255,255,255,.92) !important;
}}

div[data-testid="stForm"] {{
  background: transparent;
  border: 0;
  padding: 0;
}}

label, .stRadio label {{
  color: rgba(255,255,255,.86) !important;
}}

div[data-baseweb="input"] > div {{
  border-radius: 14px !important;
  background: rgba(255,255,255,.10) !important;
  border: 1px solid rgba(255,255,255,.16) !important;
}}
div[data-baseweb="base-input"] input {{
  color: rgba(255,255,255,.92) !important;
}}
div[data-baseweb="base-input"] input::placeholder {{
  color: rgba(255,255,255,.55) !important;
}}

.stButton > button {{
  border-radius: 14px;
  padding: 12px 14px;
  font-weight: 900;
  border: 1px solid rgba(255,255,255,.16);
  background: rgba(255,255,255,.10);
  color: rgba(255,255,255,.92);
  transition: transform .12s ease, background .12s ease;
}}
.stButton > button:hover {{
  transform: translateY(-1px);
  background: rgba(255,255,255,.14);
}}

.primary-gold .stButton > button {{
  width: 100%;
  background: linear-gradient(180deg, var(--gold2), var(--gold));
  color: #1b1b1b;
  border: 1px solid rgba(0,0,0,.12);
  box-shadow: 0 14px 30px rgba(230,178,90,.28);
}}
.primary-gold .stButton > button:hover {{
  background: linear-gradient(180deg, #FFD98B, var(--gold2));
}}

.menu-grid {{
  display:grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}}
@media (max-width: 980px){{
  .menu-grid {{ grid-template-columns: 1fr; }}
}}
.menu-card {{
  background: rgba(255,255,255,.10);
  border: 1px solid rgba(255,255,255,.16);
  border-radius: 18px;
  box-shadow: var(--shadow);
  backdrop-filter: blur(14px);
  padding: 16px 16px;
}}
.menu-card h3 {{
  margin: 0 0 6px 0;
  font-size: 18px;
  letter-spacing: .2px;
}}
.menu-card p {{
  margin: 0 0 10px 0;
  color: rgba(255,255,255,.72);
  line-height: 1.45;
}}
.menu-pill {{
  display:inline-flex;
  align-items:center;
  gap:8px;
  padding: 7px 10px;
  border-radius: 999px;
  background: rgba(255,255,255,.08);
  border: 1px solid rgba(255,255,255,.14);
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 10px;
}}

.quiz-card {{
  background: rgba(255,255,255,.08);
  border: 1px solid rgba(255,255,255,.12);
  border-radius: 16px;
  box-shadow: 0 14px 34px rgba(0,0,0,.28);
  padding: 14px 14px 10px 14px;
  margin: 10px 0 12px 0;
  backdrop-filter: blur(10px);
}}
.quiz-title {{
  font-weight: 900;
  font-size: 15px;
  color: rgba(255,255,255,.92);
  margin: 0 0 6px 0;
}}

.status-pill {{
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,.16);
  margin: 8px 0 10px 0;
  font-size: 13px;
  background: rgba(255,255,255,.08);
  backdrop-filter: blur(10px);
}}
.status-pill.ok {{
  border-color: rgba(34,197,94,.35);
}}
.status-pill.warn {{
  border-color: rgba(245,158,11,.35);
}}

.end-btn-wrap .stButton > button {{
  background: linear-gradient(180deg, #FF4D4D, #D61F2A) !important;
  color: #fff !important;
  border: 1px solid rgba(0,0,0,.12) !important;
  box-shadow: 0 14px 30px rgba(214,31,42,.26) !important;
}}
.end-btn-wrap .stButton > button:hover {{
  background: linear-gradient(180deg, #FF6B6B, #E02B36) !important;
}}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# =========================================================
# UI Blocks
# =========================================================
def render_top_hero(bank_count: int):
    st.markdown(
        f"""
        <div class="top-pill">🚓 <span>PLATFORM</span> <span style="opacity:.55;">•</span> <span>CORSO PL 2026</span></div>
        <div class="hero-title">Banca dati, simulazioni e quiz</div>
        <div class="hero-sub">
          Piattaforma didattica a cura di <b>Raffaele Sotero</b><br/>
          Correzione finale dettagliata • Casi pratici • Quiz • Banca dati
        </div>
        <div class="hero-actions">
          <div class="chip">📚 Banca dati: <b>{bank_count}</b> domande</div>
          <div class="chip">⏱️ Simulazione: <b>{DURATION_SECONDS_DEFAULT//60}</b> minuti</div>
          <div class="chip">✅ Valutazione: <b>1 punto</b> per risposta esatta</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# APP START
# =========================================================
bank_count = fetch_bank_count()
render_top_hero(bank_count)

tab_stud, tab_doc = st.tabs(["🎓 Corsista", "🧑‍🏫 Docente (upload CSV)"])

# =========================================================
# DOCENTE
# =========================================================
with tab_doc:
    st.markdown(
        """
        <div class="glass-card">
          <div class="card-pad">
            <div class="card-title">Area Docente</div>
            <div class="card-sub">Carica la banca dati (CSV) in modo sicuro e controllato.</div>
            <div class="divider-soft"></div>
            <div class="small-note">
              CSV richiesto: <b>question_text, option_a, option_b, option_c, option_d, correct_option</b>
              (+ opzionale <b>explanation</b>).<br/>
              Nota: <b>option_d</b> può essere vuota, ma allora <b>correct_option</b> non può essere D.
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    admin = st.text_input("Codice docente", type="password", placeholder="Inserisci codice docente…")
    up = st.file_uploader("Carica CSV", type=["csv"])

    st.write(f"Domande attuali in banca dati: **{fetch_bank_count()}**")

    if up and admin == ADMIN_CODE:
        try:
            raw = up.getvalue()
            rows = parse_csv_questions(raw)
            sb.table("question_bank").insert(rows).execute()
            st.success(f"Caricate {len(rows)} domande ✅")
            st.rerun()
        except Exception as e:
            st.error("Errore durante la lettura o l'inserimento del CSV.")
            st.exception(e)

    elif up and admin != ADMIN_CODE:
        st.warning("Codice docente errato.")


# =========================================================
# CORSISTA
# =========================================================
with tab_stud:
    # ---------- LOGIN ----------
    if not st.session_state["logged"]:
        st.markdown('<div class="login-shell">', unsafe_allow_html=True)

        # Left: info panel
        st.markdown(
            """
            <div class="glass-card">
              <div class="card-pad">
                <div class="card-title">Area Formazione — Polizia Locale</div>
                <div class="card-sub">
                  Accedi per iniziare le simulazioni con timer, consultare i materiali e svolgere casi pratici.
                </div>
                <div class="divider-soft"></div>
                <div class="menu-pill">🚨 Accesso riservato ai corsisti</div>
                <div class="small-note">
                  Suggerimento: se vuoi lo sfondo identico al tuo esempio, metti un file <b>background.jpg</b> nella stessa cartella del programma.
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Right: login card (Streamlit form)
        with st.container():
            st.markdown(
                """
                <div class="glass-card">
                  <div class="card-pad">
                    <div class="card-title">Accesso corsista</div>
                    <div class="card-sub">Inserisci <b>Nome e Cognome</b> e la <b>password del corso</b>.</div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.form("login_form", clear_on_submit=False):
                full_name = st.text_input(
                    "Nome e Cognome",
                    placeholder="es. Mario Rossi",
                )
                course_pass = st.text_input(
                    "Password del corso",
                    type="password",
                    placeholder="Inserisci password…",
                )
                st.markdown('<div class="primary-gold">', unsafe_allow_html=True)
                submitted = st.form_submit_button("Entra")
                st.markdown("</div>", unsafe_allow_html=True)

            if submitted:
                if not full_name.strip() or not course_pass.strip():
                    st.error("Inserisci Nome e Cognome + Password.")
                elif course_pass != COURSE_PASSWORD:
                    st.error("Password errata. Riprova.")
                else:
                    try:
                        st.session_state["student"] = upsert_student(COURSE_CLASS_CODE, full_name)
                        st.session_state["logged"] = True
                        st.session_state["menu_page"] = "home"
                        st.success("Accesso OK ✅")
                        st.rerun()
                    except Exception as e:
                        st.error("Errore accesso.")
                        st.exception(e)

        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    # ---------- PROFILO ----------
    student = st.session_state["student"]
    st.info(f"Connesso come: {student['nickname']} (corso {student['class_code']})")

    col1, col2, col3 = st.columns([1, 1, 6])
    with col1:
        if st.button("🏠 Menu"):
            st.session_state["menu_page"] = "home"
            st.rerun()

    with col2:
        if st.button("Logout"):
            st.session_state["logged"] = False
            st.session_state["student"] = None
            st.session_state["session_id"] = None
            st.session_state["in_progress"] = False
            st.session_state["show_results"] = False
            st.session_state["started_ts"] = None
            st.session_state["finished_ts"] = None
            st.session_state["duration_seconds"] = DURATION_SECONDS_DEFAULT
            st.session_state["menu_page"] = "home"
            st.rerun()

    bank_count = fetch_bank_count()
    st.write(f"📚 Domande in banca dati: **{bank_count}**")
    st.divider()

    # =========================================================
    # MENU DOPO LOGIN
    # =========================================================
    if (not st.session_state["in_progress"]) and (not st.session_state["show_results"]) and st.session_state["menu_page"] == "home":
        st.markdown("## Seleziona modalità")
        st.caption("Simulazione con timer, oppure studio libero e casi pratici.")

        st.markdown('<div class="menu-grid">', unsafe_allow_html=True)

        st.markdown(
            """
            <div class="menu-card">
              <div class="menu-pill">⏱️ Timer attivo</div>
              <h3>Simulazione Quiz (30 minuti)</h3>
              <p>30 domande estratte casualmente. Correzione finale con spiegazioni (se presenti).</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="menu-card">
              <div class="menu-pill">📚 Studio libero</div>
              <h3>Banca dati</h3>
              <p>Materiali PDF e consultazione senza timer. (Espandibile con filtri per argomento)</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="menu-card">
              <div class="menu-pill">🧠 Allenamento</div>
              <h3>Caso pratico</h3>
              <p>Scenario operativo + risposta. (Espandibile con griglia e feedback)</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("</div>", unsafe_allow_html=True)

        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("➡️ Vai alla Simulazione", use_container_width=True):
                st.session_state["menu_page"] = "sim"
                st.rerun()
        with b2:
            if st.button("➡️ Vai alla Banca dati", use_container_width=True):
                st.session_state["menu_page"] = "bank"
                st.rerun()
        with b3:
            if st.button("➡️ Vai al Caso pratico", use_container_width=True):
                st.session_state["menu_page"] = "case"
                st.rerun()

        st.stop()

    # =========================================================
    # BANCA DATI (PDF)
    # =========================================================
    if (not st.session_state["in_progress"]) and (not st.session_state["show_results"]) and st.session_state["menu_page"] == "bank":
        st.markdown("## 📚 Banca dati")
        st.caption("Materiali di studio consultabili (PDF).")

        docs = [
            {
                "title": "LEGGE QUADRO (Legge 7 marzo 1986, n. 65)",
                "url": "https://example.invalid/storage/study/legge-quadro.pdf",
            },
            {
                "title": "CODICE DELLA STRADA (D.Lgs. 30 aprile 1992, n. 285)",
                "url": "https://example.invalid/storage/study/cds.pdf",
            },
        ]

        st.markdown("### Seleziona un argomento (si apre in una nuova scheda)")
        for d in docs:
            st.link_button(f"📄 {d['title']}", d["url"], use_container_width=True)

        st.stop()

    # =========================================================
    # CASO PRATICO
    # =========================================================
    if (not st.session_state["in_progress"]) and (not st.session_state["show_results"]) and st.session_state["menu_page"] == "case":
        st.markdown("## 🧠 Caso pratico")
        st.caption("Versione base senza correzione automatica (espandibile).")

        st.markdown("### Scenario (demo)")
        st.write(
            "Durante un controllo, un conducente circola con documento di guida non esibito al momento "
            "del controllo e sostiene di averlo dimenticato a casa."
        )
        ans = st.text_area("Scrivi la tua risposta (sintetica ma completa):", height=140)

        colA, colB = st.columns([1, 3])
        with colA:
            if st.button("Salva risposta (demo)"):
                st.success("Risposta salvata (demo). In arrivo: correzione automatica e griglia di valutazione.")

        with colB:
            st.info("Prossimo step: casi pratici reali + criteri di idoneità + feedback automatico.")

        st.stop()

    # =========================================================
    # SIMULAZIONE
    # =========================================================
    if bank_count < N_QUESTIONS_DEFAULT:
        st.warning(f"Servono almeno {N_QUESTIONS_DEFAULT} domande per la simulazione. Ora: {bank_count}")
        st.stop()

    if (not st.session_state["in_progress"]) and (not st.session_state["show_results"]) and st.session_state["menu_page"] == "sim":
        st.markdown("## Simulazione")
        st.caption("30 domande – 30 minuti. Il timer parte solo qui.")

        if st.button("Inizia simulazione", use_container_width=True):
            try:
                sess = create_session(student_id=student["id"], n_questions=N_QUESTIONS_DEFAULT)
                st.session_state["session_id"] = sess["id"]
                st.session_state["in_progress"] = True
                st.session_state["show_results"] = False
                st.session_state["started_ts"] = time.time()
                st.session_state["finished_ts"] = None
                st.session_state["duration_seconds"] = DURATION_SECONDS_DEFAULT

                all_q = fetch_all_bank_questions()
                picked = random.sample(all_q, N_QUESTIONS_DEFAULT)
                insert_session_questions(sess["id"], picked)

                st.success("Simulazione avviata ✅")
                st.rerun()
            except Exception as e:
                st.error("Errore avvio simulazione.")
                st.exception(e)

        st.stop()

    # ---------- IN PROGRESS ----------
    if st.session_state["in_progress"]:
        session_id = st.session_state["session_id"]
        rows = fetch_session_questions(session_id)

        if not rows:
            st.error("Sessione senza domande (quiz_answers vuota).")
            st.stop()

        end_ts = float(st.session_state["started_ts"]) + int(st.session_state["duration_seconds"])
        time_up = time.time() >= end_ts

        render_live_timer(end_ts)

        elapsed = int(time.time() - float(st.session_state["started_ts"]))
        remaining = max(0, int(st.session_state["duration_seconds"]) - elapsed)
        progress = 1.0 - (remaining / int(st.session_state["duration_seconds"]))
        st.progress(min(max(progress, 0.0), 1.0))
        st.divider()

        if time_up:
            st.warning("Tempo scaduto! Correzione automatica…")
            st.session_state["in_progress"] = False
            st.session_state["show_results"] = True
            st.session_state["finished_ts"] = time.time()
            finish_session(session_id)
            st.rerun()

        st.markdown("## 📝 Sessione in corso")

        answered = sum(1 for r in rows if (r.get("chosen_option") or "").strip())
        st.markdown(
            f'<div class="chip">✅ Risposte date: <b>{answered}/{len(rows)}</b></div>',
            unsafe_allow_html=True
        )

        BOLD_LETTER = {"A": "𝐀", "B": "𝐁", "C": "𝐂", "D": "𝐃"}

        for idx, row in enumerate(rows, start=1):
            st.markdown(
                f"""
                <div class="quiz-card">
                  <div class="quiz-title">Domanda n°{idx} di {len(rows)}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.markdown(f"**{row['question_text']}**")

            options_map = {
                "A": (row.get("option_a") or "").strip(),
                "B": (row.get("option_b") or "").strip(),
                "C": (row.get("option_c") or "").strip(),
                "D": (row.get("option_d") or "").strip(),
            }

            letters = [k for k in ["A", "B", "C", "D"] if options_map[k] != ""]
            radio_options = ["—"] + letters

            def fmt(opt: str) -> str:
                if opt == "—":
                    return "— (lascia senza risposta)"
                return f"{BOLD_LETTER.get(opt, opt)}) {options_map[opt]}"

            current = (row.get("chosen_option") or "").strip().upper()
            if current not in letters:
                current = "—"

            choice = st.radio(
                "Seleziona risposta",
                options=radio_options,
                index=radio_options.index(current),
                format_func=fmt,
                key=f"q_{row['id']}",
                disabled=time_up,
            )

            new_val = None if choice == "—" else choice
            old_val = row.get("chosen_option") or None

            if (not time_up) and (new_val != old_val):
                try:
                    update_chosen_option(row_id=row["id"], session_id=session_id, chosen_letter=new_val)
                except Exception:
                    pass

            if new_val is None:
                st.markdown(
                    '<div class="status-pill warn">📝 <b>Stato risposta:</b> ⚠️ Non hai ancora risposto</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="status-pill ok">📝 <b>Stato risposta:</b> ✅ Risposta selezionata: <b>{new_val}</b></div>',
                    unsafe_allow_html=True,
                )

            st.divider()

        st.markdown('<div class="end-btn-wrap">', unsafe_allow_html=True)
        if st.button("Termina simulazione e vedi correzione", use_container_width=True):
            st.session_state["in_progress"] = False
            st.session_state["show_results"] = True
            st.session_state["finished_ts"] = time.time()
            finish_session(session_id)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # ---------- RESULTS ----------
    if st.session_state["show_results"]:
        session_id = st.session_state["session_id"]
        rows = fetch_session_questions(session_id)

        score = 0
        for row in rows:
            chosen = (row.get("chosen_option") or "").strip().upper()
            correct = (row.get("correct_option") or "").strip().upper()
            if chosen and chosen == correct:
                score += 1

        start_ts = st.session_state.get("started_ts")
        end_ts2 = st.session_state.get("finished_ts") or time.time()
        elapsed_sec = int(max(0, float(end_ts2) - float(start_ts))) if start_ts else 0
        em = elapsed_sec // 60
        es = elapsed_sec % 60

        st.markdown("## ✅ Correzione finale")
        st.success(f"📌 Punteggio: **{score} / {len(rows)}**  •  ⏱️ Completata in **{em} min {es:02d} sec**")
        st.divider()

        def letter_to_text(row: dict, letter: str) -> str:
            letter = (letter or "").strip().upper()
            if letter == "A":
                return (row.get("option_a") or "").strip()
            if letter == "B":
                return (row.get("option_b") or "").strip()
            if letter == "C":
                return (row.get("option_c") or "").strip()
            if letter == "D":
                return (row.get("option_d") or "").strip()
            return ""

        for idx, row in enumerate(rows, start=1):
            chosen = (row.get("chosen_option") or "").strip().upper()
            correct = (row.get("correct_option") or "").strip().upper()

            chosen_text = letter_to_text(row, chosen) if chosen else ""
            correct_text = letter_to_text(row, correct)

            ok = (chosen != "" and chosen == correct)

            st.markdown(f"### Domanda n°{idx} {'✅' if ok else '❌'}")
            st.markdown(f"**{row['question_text']}**")

            if chosen:
                st.write(f"**Tua risposta:** {chosen}) {chosen_text}")
            else:
                st.write("**Tua risposta:** — (non risposta)")

            st.write(f"**Corretta:** {correct}) {correct_text}")

            if row.get("explanation"):
                st.caption(row["explanation"])

            st.divider()

        st.success(f"📌 Punteggio: **{score} / {len(rows)}**  •  ⏱️ Completata in **{em} min {es:02d} sec**")

        if st.button("Torna al menu", use_container_width=True):
            st.session_state["session_id"] = None
            st.session_state["in_progress"] = False
            st.session_state["show_results"] = False
            st.session_state["started_ts"] = None
            st.session_state["finished_ts"] = None
            st.session_state["duration_seconds"] = DURATION_SECONDS_DEFAULT
            st.session_state["menu_page"] = "home"
            st.rerun()
```
