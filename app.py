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
        '  python -m streamlit run "app (26).py"\n'
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
# PAGE CONFIG
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

# SOSTITUISCI TU con la tua password reale
COURSE_PASSWORD = "<COURSE_PASSWORD>"
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
    for fn in filenames:
        if os.path.exists(fn) and os.path.isfile(fn):
            ext = fn.split(".")[-1].lower()
            mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
            with open(fn, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            return f"data:{mime};base64,{b64}"
    return None


def render_live_timer(end_ts: float):
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
    for i, r in enumerate(reader, start=2):
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
        "menu_page": "home",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


ss_init()

# =========================================================
# THEME / UI (base app)
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
  --gold: #E6B25A;
  --gold2:#F2C76D;
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

header, footer {{ visibility: hidden; height: 0px; }}
div[data-testid="stSidebar"] {{ display: none; }}

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

div[data-testid="stForm"] {{ background: transparent; border: 0; padding: 0; }}

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


def render_landing_login() -> tuple[str, str, bool]:
    DEFAULT_HERO_BG_URL = (
        "https://raw.githubusercontent.com/superaffy07/quiz-cds-app/"
        "a2259150bd4cd99d07966de4c35d9fafc04fab13/"
        "ChatGPT%20Image%2027%20gen%202026%2C%2000_56_50.png"
    )
    try:
        hero_bg_url = (st.secrets.get("HERO_BG_URL", "") or "").strip()
    except Exception:
        hero_bg_url = ""
    if not hero_bg_url:
        hero_bg_url = DEFAULT_HERO_BG_URL

    car_svg = (
        "<svg width='18' height='18' viewBox='0 0 24 24' fill='none' "
        "xmlns='http://www.w3.org/2000/svg' style='opacity:.95;'>"
        "<path d='M5.6 11.2L7.1 7.6C7.4 6.9 8.1 6.5 8.9 6.5H15.1C15.9 6.5 16.6 6.9 16.9 7.6L18.4 11.2' "
        "stroke='white' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'/>"
        "<path d='M6.3 16.8H5.4C4.6 16.8 4 16.2 4 15.4V12.8C4 12 4.6 11.4 5.4 11.4H18.6C19.4 11.4 20 12 20 12.8V15.4C20 16.2 19.4 16.8 18.6 16.8H17.7' "
        "stroke='white' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'/>"
        "<path d='M7.3 16.8V18.2' stroke='white' stroke-width='1.6' stroke-linecap='round'/>"
        "<path d='M16.7 16.8V18.2' stroke='white' stroke-width='1.6' stroke-linecap='round'/>"
        "<path d='M8 14.3H9.6' stroke='white' stroke-width='1.6' stroke-linecap='round'/>"
        "<path d='M14.4 14.3H16' stroke='white' stroke-width='1.6' stroke-linecap='round'/>"
        "</svg>"
    )

    # IMPORTANTE: niente ``` qui dentro. Solo HTML puro.
    st.markdown(
        f"""
<style>
/* ===== LANDING (fix: render HTML, not code) ===== */
.landing-canvas {{
  position: relative;
  width: 100%;
  min-height: calc(100vh - 90px);
  border-radius: 26px;
  overflow: hidden;
  border: 1px solid rgba(255,255,255,.10);
  box-shadow: 0 30px 90px rgba(0,0,0,.55);
}}
.landing-bg {{
  position:absolute;
  inset:0;
  background: url("{hero_bg_url}");
  background-size: cover;
  background-position: center;
  transform: scale(1.06);
  filter: saturate(1.05) contrast(1.08);
}}
.landing-dim {{
  position:absolute;
  inset:0;
  background: radial-gradient(1100px 700px at 50% 0%, rgba(0,0,0,.35), rgba(0,0,0,.70));
  backdrop-filter: blur(10px);
}}
.landing-sirens {{
  position:absolute;
  inset:-45% -25%;
  pointer-events:none;
  mix-blend-mode: screen;
  opacity: .95;
  filter: blur(2px);
}}
.landing-sirens:before,
.landing-sirens:after {{
  content:"";
  position:absolute;
  width: 58%;
  height: 58%;
  border-radius: 999px;
}}
.landing-sirens:before {{
  left: -8%;
  top: 8%;
  background: radial-gradient(circle, rgba(45,115,255,.65), transparent 62%);
}}
.landing-sirens:after {{
  right: -8%;
  top: 8%;
  background: radial-gradient(circle, rgba(255,80,120,.60), transparent 62%);
}}
.landing-grain {{
  position:absolute;
  inset:0;
  pointer-events:none;
  opacity: .12;
  background-image:
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='180'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='180' height='180' filter='url(%23n)' opacity='.5'/%3E%3C/svg%3E");
}}
.landing-hero {{
  position: relative;
  z-index: 2;
  padding: 48px 18px 18px;
  display:flex;
  flex-direction: column;
  align-items:center;
  text-align:center;
}}
.landing-pill {{
  display:inline-flex;
  align-items:center;
  gap: 12px;
  padding: 11px 18px;
  border-radius: 999px;
  background: rgba(255,255,255,.10);
  border: 1px solid rgba(255,255,255,.16);
  backdrop-filter: blur(16px);
  box-shadow: 0 14px 34px rgba(0,0,0,.25);
  color: rgba(255,255,255,.92);
  font-weight: 900;
  letter-spacing: .3px;
}}
.landing-pill .dot {{ opacity:.55; }}
.landing-pill .car {{ display:inline-flex; align-items:center; justify-content:center; }}
.landing-title {{
  margin: 22px 0 10px;
  font-family: Oswald, Inter, sans-serif;
  font-size: 62px;
  line-height: 1.02;
  color: rgba(255,255,255,.95);
  text-shadow: 0 18px 60px rgba(0,0,0,.45);
}}
@media (max-width: 980px) {{
  .landing-title {{ font-size: 44px; }}
}}
.landing-locale {{
  margin: 0 0 14px;
  font-family: Oswald, Inter, sans-serif;
  font-size: 28px;
  letter-spacing: .2px;
  color: rgba(255,255,255,.88);
}}
.landing-subtitle {{
  margin: 0 0 10px;
  font-size: 18px;
  color: rgba(255,255,255,.78);
}}
.landing-bullet {{
  margin: 0;
  font-size: 16px;
  font-weight: 800;
  color: rgba(255,255,255,.84);
}}
.landing-shortcuts {{
  margin-top: 16px;
  display:flex;
  gap: 14px;
  flex-wrap: wrap;
  justify-content: center;
}}
.shortcut {{
  padding: 11px 18px;
  border-radius: 999px;
  background: rgba(255,255,255,.08);
  border: 1px solid rgba(255,255,255,.14);
  backdrop-filter: blur(16px);
  color: rgba(255,255,255,.90);
  font-weight: 900;
}}
.login-wrap {{
  position: relative;
  z-index: 3;
  margin-top: 26px;
}}
.login-card {{
  background: rgba(255,255,255,.14);
  border: 1px solid rgba(255,255,255,.18);
  border-radius: 26px;
  box-shadow: 0 28px 80px rgba(0,0,0,.40);
  backdrop-filter: blur(22px);
  overflow: hidden;
}}
.login-card-inner {{ padding: 22px 22px 16px; }}
.login-title {{
  margin: 0;
  font-family: Oswald, Inter, sans-serif;
  font-size: 32px;
  color: rgba(255,255,255,.92);
  text-align: center;
}}
.icon-badge {{
  width: 44px;
  height: 44px;
  border-radius: 14px;
  display:flex;
  align-items:center;
  justify-content:center;
  background: rgba(255,255,255,.12);
  border: 1px solid rgba(255,255,255,.18);
  backdrop-filter: blur(12px);
  font-size: 18px;
}}
.login-foot {{
  margin: 14px 0 6px;
  text-align: center;
  color: rgba(255,255,255,.72);
  font-size: 13px;
  line-height: 1.35;
}}
</style>

<div class="landing-canvas landing-scope">
  <div class="landing-bg"></div>
  <div class="landing-dim"></div>
  <div class="landing-sirens"></div>
  <div class="landing-grain"></div>

  <div class="landing-hero">
    <div class="landing-pill">
      <span class="car">{car_svg}</span>
      <span>PLATFORM</span>
      <span class="dot">•</span>
      <span>CORSO PL 2026</span>
    </div>

    <div class="landing-title">Banca dati, simulazioni e quiz</div>
    <div class="landing-locale">Polizia Locale</div>

    <div class="landing-subtitle">Piattaforma didattica a cura di <b>Raffaele Sotero</b></div>
    <div class="landing-bullet">• Correzione finale dettagliata</div>

    <div class="landing-shortcuts">
      <div class="shortcut">Casi pratici</div>
      <div class="shortcut">Quiz</div>
      <div class="shortcut">Banca dati</div>
    </div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

    left, mid, right = st.columns([1.2, 1.0, 1.2])
    with mid:
        st.markdown(
            """
            <div class="login-wrap">
              <div class="login-card">
                <div class="login-card-inner">
                  <div class="login-title">Accesso corsista</div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("landing_login_form", clear_on_submit=False):
            c1, c2 = st.columns([0.18, 0.82], vertical_alignment="center")
            with c1:
                st.markdown('<div class="icon-badge">👤</div>', unsafe_allow_html=True)
            with c2:
                full_name = st.text_input(
                    "Nome e Cognome",
                    placeholder="Nome e Cognome (es. Mario Rossi)",
                    label_visibility="collapsed",
                )

            c3, c4 = st.columns([0.18, 0.82], vertical_alignment="center")
            with c3:
                st.markdown('<div class="icon-badge">🔒</div>', unsafe_allow_html=True)
            with c4:
                course_pass = st.text_input(
                    "Password del corso",
                    type="password",
                    placeholder="Password del corso",
                    label_visibility="collapsed",
                )

            st.markdown('<div class="primary-gold">', unsafe_allow_html=True)
            clicked = st.form_submit_button("Entra")
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            """
            <div class="login-foot">
              Accesso riservato ai corsisti • Inserisci Nome e Cognome e la password del corso.
            </div>
            """,
            unsafe_allow_html=True,
        )

    return full_name, course_pass, clicked


# =========================================================
# APP START
# =========================================================
bank_count = fetch_bank_count()

if st.session_state.get("logged"):
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
    if not st.session_state["logged"]:
        full_name, course_pass, clicked = render_landing_login()

        if clicked:
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

        st.stop()

    # Da qui in poi: resto app invariato (menu/quiz ecc.)
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

    if (not st.session_state["in_progress"]) and (not st.session_state["show_results"]) and st.session_state["menu_page"] == "home":
        st.markdown("## Seleziona modalità")
        st.caption("Simulazione con timer, oppure studio libero e casi pratici.")
        st.markdown("*(Il resto dell’app è invariato.)*")
        st.stop()
