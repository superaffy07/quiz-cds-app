import os
import time
import random
from datetime import datetime, timezone
from typing import List, Dict

import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client, Client


# =========================================================
# PAGE CONFIG (UNA SOLA VOLTA, IN TESTA AL FILE)
# =========================================================
st.set_page_config(
    page_title="Banca dati, simulazioni e quiz — Polizia Locale",
    page_icon="🚓",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =========================================================
# STILI (NO BLU, MODERNO, LEGGIBILE)
# =========================================================
CUSTOM_CSS = """
<style>
/* layout */
.block-container { max-width: 1100px; padding-top: 1.2rem; padding-bottom: 3rem; }

/* background chiaro pulito */
.stApp { background: #f6f7fb; }

/* card header */
.hero {
  background: white;
  border: 1px solid rgba(0,0,0,.06);
  border-radius: 18px;
  padding: 18px 18px;
  box-shadow: 0 10px 30px rgba(0,0,0,.06);
  margin-bottom: 18px;
}
.hero-title {
  font-size: 30px;
  font-weight: 800;
  margin: 0;
  letter-spacing: .2px;
  color: #111827;
}
.hero-sub {
  margin: 6px 0 0 0;
  color: #4b5563;
  font-size: 14px;
  line-height: 1.4;
}
.badges { display:flex; gap:10px; flex-wrap:wrap; margin-top: 12px; }
.badge {
  font-size: 12px;
  padding: 8px 10px;
  border-radius: 999px;
  border: 1px solid rgba(0,0,0,.08);
  background: #fbfbfd;
  color: #111827;
  display:inline-flex;
  align-items:center;
  gap:8px;
}

/* tabs */
.stTabs [data-baseweb="tab-list"] {
  gap: 10px;
  padding: 8px 6px;
  border-radius: 14px;
  background: white;
  border: 1px solid rgba(0,0,0,.06);
}
.stTabs [data-baseweb="tab"] {
  border-radius: 12px;
  padding: 10px 14px;
  color: #374151;
  font-weight: 600;
}
.stTabs [aria-selected="true"] {
  background: #f3f4f6 !important;
  border: 1px solid rgba(0,0,0,.08) !important;
}

/* buttons */
.stButton > button {
  border-radius: 12px;
  padding: 10px 14px;
  border: 1px solid rgba(0,0,0,.10);
  background: white;
  color: #111827;
  transition: all .12s ease-in-out;
  font-weight: 700;
}
.stButton > button:hover {
  transform: translateY(-1px);
  background: #f9fafb;
}

/* radio / inputs */
div[data-baseweb="input"] > div { border-radius: 12px !important; }
.stRadio label { color: #111827; }

/* alert */
div[data-testid="stAlert"] {
  border-radius: 14px;
  border: 1px solid rgba(0,0,0,.08);
}

/* divider */
hr { border-top: 1px solid rgba(0,0,0,.08); }

/* =========================================
   QUIZ CARD LOOK
   ========================================= */
.quiz-card{
  background: white;
  border: 1px solid rgba(0,0,0,.06);
  border-radius: 16px;
  box-shadow: 0 8px 22px rgba(0,0,0,.05);
  padding: 14px 14px 10px 14px;
  margin: 10px 0 12px 0;
}
.quiz-title{
  font-weight: 850;
  font-size: 16px;
  color: #111827;
  margin: 0 0 6px 0;
}

/* =========================================
   MENU CARDS (NUOVO)
   ========================================= */
.menu-grid{
  display:grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 10px;
}
@media (max-width: 980px){
  .menu-grid{ grid-template-columns: 1fr; }
}
.menu-card{
  background: white;
  border: 1px solid rgba(0,0,0,.06);
  border-radius: 16px;
  box-shadow: 0 8px 22px rgba(0,0,0,.05);
  padding: 14px 14px;
}
.menu-title{
  font-size: 16px;
  font-weight: 850;
  color: #111827;
  margin: 0 0 6px 0;
}
.menu-desc{
  color: #4b5563;
  font-size: 13px;
  margin: 0 0 12px 0;
  line-height: 1.35;
}
.menu-chip{
  display:inline-flex;
  align-items:center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(0,0,0,.08);
  background:#fbfbfd;
  color:#111827;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 10px;
}

/* =========================================
   BOTTONE ROSSO SOLO PER "TERMINA"
   ========================================= */
.end-btn-wrap .stButton > button{
  background: #b42318 !important;
  color: #ffffff !important;
  border: 1px solid rgba(0,0,0,.12) !important;
  box-shadow: 0 10px 22px rgba(180,35,24,.22) !important;
}
.end-btn-wrap .stButton > button:hover{
  background: #9b1c14 !important;
  transform: translateY(-1px);
}

/* === Stato risposta (pill verde/gialla) === */
.status-pill{
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(0,0,0,.08);
  margin: 8px 0 10px 0;
  font-size: 13px;
}
.status-pill.ok{
  background: rgba(34,197,94,0.12);
}
.status-pill.warn{
  background: rgba(245,158,11,0.14);
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# =========================================================
# COSTANTI
# =========================================================
N_QUESTIONS_DEFAULT = 30
DURATION_SECONDS_DEFAULT = 30 * 60  # 30 minuti

# =========================================================
# ACCESSO CORSO
# =========================================================
COURSE_PASSWORD = "polizia2026"
COURSE_CLASS_CODE = "CORSO_PL_2026"

# =========================================================
# TIMER FLUIDO (NO RERUN, NO SCURIMENTO)
# =========================================================
def render_live_timer(end_ts: float):
    """
    Mostra un countdown fluido aggiornato ogni 1s lato browser.
    NON provoca rerun Streamlit -> niente schermo che scurisce.
    """
    end_ms = int(end_ts * 1000)
    components.html(
        f"""
        <div style="margin: 0 0 10px 0;">
          <div style="font-size: 20px; font-weight: 800; color:#111827;">
            ⏱️ Tempo residuo: <span id="tval">--:--</span>
          </div>
        </div>
        <script>
          const end = {end_ms};
          function pad(n) {{ return String(n).padStart(2,'0'); }}
          function tick(){{
            const now = Date.now();
            let remaining = Math.max(0, Math.floor((end - now)/1000));
            const m = Math.floor(remaining/60);
            const s = remaining % 60;
            document.getElementById("tval").textContent = pad(m) + ":" + pad(s);
          }}
          tick();
          setInterval(tick, 1000);
        </script>
        """,
        height=40,
    )

# =========================================================
# SUPABASE
# =========================================================
def get_secret(name: str, default: str = "") -> str:
    try:
        v = st.secrets.get(name, default)
        if v:
            return v
    except Exception:
        pass
    return os.getenv(name, default)

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

def update_chosen_option(row_id: int, session_id: str, chosen_letter: str | None) -> None:
    sb.table("quiz_answers").update({"chosen_option": chosen_letter}).eq("id", row_id).eq("session_id", session_id).execute()

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
        # NUOVO: pagina menu dopo login
        "menu_page": "home",   # home | sim | bank | case
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

ss_init()

# =========================================================
# HEADER
# =========================================================
def render_header(total_questions: int):
    st.markdown(
        f"""
<div class="hero">
  <div class="hero-title">🚓 Banca dati, simulazioni e quiz — Polizia Locale</div>
  <div class="hero-sub">
    Piattaforma didattica a cura di <b>Raffaele Sotero</b><br>
    Casi pratici • Quiz • Banca dati • Correzione finale dettagliata
  </div>
  <div class="badges">
    <div class="badge">📚 <strong>Banca dati</strong>: {total_questions} domande</div>
    <div class="badge">⏱️ <strong>Tempo</strong>: {DURATION_SECONDS_DEFAULT//60} minuti</div>
    <div class="badge">✅ <strong>Valutazione</strong>: 1 punto per risposta esatta</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

# =========================================================
# APP
# =========================================================

bank_count = fetch_bank_count()

# ---------------------------------------------------------
# LANDING WOW (MOSTRA SOLO SE NON LOGGATO)
# ---------------------------------------------------------
LANDING_CSS = """
<style>
/* Nascondo header Streamlit e padding extra */
header {visibility: hidden;}
.block-container { padding-top: 1.2rem; }

/* Sfondo WOW */
.landing-bg{
  position: relative;
  border-radius: 22px;
  overflow: hidden;
  padding: 34px 34px 28px 34px;
  margin-bottom: 18px;
  border: 1px solid rgba(255,255,255,.14);
  box-shadow: 0 22px 60px rgba(0,0,0,.30);
  background:
    radial-gradient(1200px 500px at 20% 0%, rgba(59,130,246,.28), transparent 60%),
    radial-gradient(900px 500px at 85% 10%, rgba(244,63,94,.22), transparent 55%),
    linear-gradient(135deg, #071a33 0%, #0b2b52 48%, #1a0830 100%);
}

/* Linea luci (blu/rosso) */
.landing-bg:before{
  content:"";
  position:absolute;
  left:-10%;
  top:22px;
  width:120%;
  height:2px;
  background: linear-gradient(90deg, rgba(59,130,246,0) 0%, rgba(59,130,246,.9) 35%, rgba(244,63,94,.9) 65%, rgba(244,63,94,0) 100%);
  filter: blur(.2px);
  opacity:.95;
}

/* Titoli */
.landing-badge{
  display:inline-flex;
  align-items:center;
  gap:10px;
  padding: 7px 14px;
  border-radius: 999px;
  background: rgba(255,255,255,.12);
  border: 1px solid rgba(255,255,255,.14);
  color: rgba(255,255,255,.92);
  font-weight: 800;
  font-size: 13px;
  margin-bottom: 16px;
}
.landing-title{
  color: #ffffff;
  font-weight: 900;
  letter-spacing: .2px;
  font-size: 44px;
  line-height: 1.08;
  margin: 0 0 10px 0;
}
.landing-sub{
  color: rgba(255,255,255,.86);
  font-size: 15px;
  line-height: 1.5;
  max-width: 820px;
  margin-bottom: 16px;
}
.landing-chips{
  display:flex;
  gap:10px;
  flex-wrap:wrap;
  margin-bottom: 18px;
}
.landing-chip{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,.16);
  background: rgba(0,0,0,.18);
  color: rgba(255,255,255,.90);
  font-weight: 800;
  font-size: 13px;
}

/* Card login */
.login-card{
  margin-top: 16px;
  background: rgba(255,255,255,.10);
  border: 1px solid rgba(255,255,255,.16);
  border-radius: 20px;
  padding: 18px 18px 16px 18px;
  backdrop-filter: blur(10px);
}
.login-title{
  color:#fff;
  font-size: 20px;
  font-weight: 900;
  margin: 0 0 10px 0;
}
.login-hint{
  color: rgba(255,255,255,.78);
  font-size: 13px;
  margin-top: 10px;
}

/* Input Streamlit dentro landing: li rendo “glass” */
.landing-input [data-baseweb="input"] > div{
  border-radius: 14px !important;
  background: rgba(255,255,255,.92) !important;
}
.landing-input input{
  font-weight: 700 !important;
}

/* Bottone “Entra” gold */
.landing-btn .stButton > button{
  width: 100%;
  border-radius: 14px !important;
  padding: 12px 14px !important;
  border: 1px solid rgba(0,0,0,.12) !important;
  background: linear-gradient(180deg, #f7c777 0%, #e7a93d 100%) !important;
  color: #1b1b1b !important;
  font-weight: 900 !important;
  box-shadow: 0 14px 30px rgba(231,169,61,.25) !important;
}
.landing-btn .stButton > button:hover{
  transform: translateY(-1px);
}
</style>
"""

def render_landing_login(total_questions: int):
    st.markdown(LANDING_CSS, unsafe_allow_html=True)

    st.markdown('<div class="landing-bg">', unsafe_allow_html=True)

    st.markdown(
        """
        <div class="landing-badge">🚓 Platform • Corso PL</div>
        <div class="landing-title">Banca dati, simulazioni e quiz<br><span style="opacity:.92;">Polizia Locale</span></div>
        <div class="landing-sub">
          Piattaforma didattica a cura di <b>Raffaele Sotero</b> • Correzione finale dettagliata.<br>
          Simulazioni d’esame, banca dati normativa e casi pratici commentati.
        </div>
        <div class="landing-chips">
          <div class="landing-chip">📚 Banca dati: %d domande</div>
          <div class="landing-chip">⏱️ 30 minuti</div>
          <div class="landing-chip">✅ 1 punto per risposta esatta</div>
        </div>
        """ % (total_questions,),
        unsafe_allow_html=True,
    )

    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.markdown('<div class="login-title">Accesso corsista</div>', unsafe_allow_html=True)

    # Input (veri Streamlit) dentro la card
    st.markdown('<div class="landing-input">', unsafe_allow_html=True)
    full_name = st.text_input("Nome e Cognome (es. Mario Rossi)")
    course_pass = st.text_input("Password del corso", type="password")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="landing-btn">', unsafe_allow_html=True)
    go = st.button("Entra")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        '<div class="login-hint">Accesso riservato ai corsisti • Inserisci Nome e Cognome e la password del corso.</div>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)  # chiude login-card
    st.markdown("</div>", unsafe_allow_html=True)  # chiude landing-bg

    # Logica login (UGUALE alla tua, ma qui sopra)
    if go:
        if not full_name or not course_pass:
            st.error("Inserisci Nome e Cognome + Password.")
            st.stop()
        if course_pass != COURSE_PASSWORD:
            st.error("Password errata. Riprova.")
            st.stop()

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


# Se NON loggato: mostro SOLO la landing WOW e STOP.
# Sei già loggato perché la landing fa st.stop() se non loggato
# quindi qui dentro arrivano SOLO utenti autenticati.
st.subheader("Area corsista")


# Se loggato: tutto come prima (header + tabs)
render_header(bank_count)

tab_stud, tab_doc = st.tabs(["🎓 Corsista", "🧑‍🏫 Docente (upload CSV)"])

    st.subheader("Carica banca dati (CSV)")
    st.write("CSV richiesto: `question_text, option_a, option_b, option_c, option_d, correct_option` (+ opzionale `explanation`).")
    st.write("Nota: `option_d` può essere vuota. Se è vuota, la D non comparirà nel quiz.")

    admin = st.text_input("Codice docente", type="password")
    up = st.file_uploader("Carica CSV", type=["csv"])

    st.divider()
    st.write("Domande in banca dati:", fetch_bank_count())

    if up and admin == ADMIN_CODE:
        import pandas as pd
        import io

        raw = up.getvalue()
        df = None
        for enc in ("utf-8-sig", "utf-8", "latin1"):
            try:
                df = pd.read_csv(io.BytesIO(raw), encoding=enc)
                break
            except Exception:
                df = None

        if df is None:
            st.error("Impossibile leggere il CSV. Salvalo come UTF-8.")
            st.stop()

        required = ["question_text", "option_a", "option_b", "option_c", "option_d", "correct_option"]
        miss = [c for c in required if c not in df.columns]
        if miss:
            st.error(f"Mancano colonne: {miss}")
            st.stop()

        if "explanation" not in df.columns:
            df["explanation"] = ""

        df = df.fillna("")
        df["correct_option"] = df["correct_option"].astype(str).str.strip().str.upper()
        df["option_d"] = df["option_d"].astype(str).fillna("").str.strip()

        bad = ~df["correct_option"].isin(["A", "B", "C", "D"])
        if bad.any():
            st.error("Trovate righe con correct_option non valido (deve essere A/B/C/D).")
            st.dataframe(df.loc[bad, ["question_text", "correct_option"]].head(10))
            st.stop()

        bad_d = (df["option_d"] == "") & (df["correct_option"] == "D")
        if bad_d.any():
            st.error("Righe con correct_option = D ma option_d vuota. Correggi il CSV.")
            st.dataframe(df.loc[bad_d, ["question_text", "option_d", "correct_option"]].head(20))
            st.stop()

        rows = df[required + ["explanation"]].to_dict(orient="records")

        try:
            sb.table("question_bank").insert(rows).execute()
            st.success(f"Caricate {len(rows)} domande ✅")
            st.rerun()
        except Exception as e:
            st.error("Errore inserimento in question_bank.")
            st.exception(e)

    elif up and admin != ADMIN_CODE:
        st.warning("Codice docente errato.")

# =========================================================
# CORSISTA
# =========================================================
with tab_stud:
    # =========================================================
    # LANDING / LOGIN WOW (SOLO PRIMA DEL LOGIN)
    # =========================================================
    LANDING_CSS = """
    <style>
      /* Rende la sezione landing più "cinematografica" */
      .pl-landing {
        position: relative;
        border-radius: 22px;
        overflow: hidden;
        padding: 42px 34px;
        margin: 10px 0 18px 0;
        box-shadow: 0 18px 45px rgba(0,0,0,.22);
        border: 1px solid rgba(255,255,255,.10);
        color: #fff;
        background:
          radial-gradient(1200px 480px at 20% 10%, rgba(60,130,255,.35), transparent 60%),
          radial-gradient(900px 420px at 90% 20%, rgba(255,60,90,.28), transparent 55%),
          radial-gradient(900px 560px at 50% 90%, rgba(10,20,40,.95), rgba(10,20,40,.92)),
          linear-gradient(135deg, #071a2f, #0b2b4c);
      }

      /* “barra lampeggiante” in alto */
      .pl-landing::before{
        content:"";
        position:absolute;
        left:-5%;
        right:-5%;
        top:18px;
        height:2px;
        background: linear-gradient(90deg, rgba(50,140,255,0), rgba(50,140,255,.9), rgba(255,70,100,.9), rgba(255,70,100,0));
        filter: drop-shadow(0 0 8px rgba(50,140,255,.55));
        opacity:.9;
      }

      .pl-pill {
        display:inline-flex;
        align-items:center;
        gap:10px;
        padding: 8px 14px;
        border-radius: 999px;
        background: rgba(255,255,255,.10);
        border: 1px solid rgba(255,255,255,.16);
        font-weight: 800;
        font-size: 13px;
        letter-spacing: .4px;
      }

      .pl-title {
        margin: 14px 0 6px 0;
        font-size: 44px;
        line-height: 1.08;
        font-weight: 900;
        letter-spacing: .2px;
      }

      .pl-sub {
        margin: 8px 0 0 0;
        font-size: 15px;
        opacity: .92;
        max-width: 950px;
      }

      .pl-chiprow{
        margin-top: 12px;
        display:flex;
        gap:10px;
        flex-wrap: wrap;
        opacity:.95;
      }
      .pl-chip{
        padding: 8px 12px;
        border-radius: 999px;
        background: rgba(0,0,0,.18);
        border: 1px solid rgba(255,255,255,.12);
        font-weight: 700;
        font-size: 12px;
      }

      /* layout: testo sopra, card login sotto */
      .pl-login-wrap{
        margin-top: 18px;
        display:flex;
        justify-content:center;
      }

      .pl-login-card{
        width: min(720px, 96%);
        background: rgba(255,255,255,.10);
        border: 1px solid rgba(255,255,255,.16);
        border-radius: 20px;
        padding: 18px 18px 14px 18px;
        backdrop-filter: blur(10px);
        box-shadow: 0 16px 35px rgba(0,0,0,.20);
      }

      .pl-login-title{
        text-align:center;
        font-size: 22px;
        font-weight: 900;
        margin: 2px 0 12px 0;
      }

      /* Styling input Streamlit */
      .pl-login-card div[data-baseweb="input"] > div{
        background: rgba(255,255,255,.92) !important;
        border-radius: 14px !important;
        border: 1px solid rgba(0,0,0,.10) !important;
      }
      .pl-login-card input{
        color: #0b1220 !important;
        font-weight: 700 !important;
      }

      /* Bottone "Entra" stile oro */
      .pl-login-card .stButton > button{
        width: 100%;
        background: linear-gradient(180deg, #f2c36b, #d59a3a) !important;
        color: #1b1206 !important;
        border: 1px solid rgba(0,0,0,.18) !important;
        border-radius: 14px !important;
        padding: 12px 16px !important;
        font-weight: 900 !important;
        box-shadow: 0 14px 28px rgba(213,154,58,.22) !important;
      }
      .pl-login-card .stButton > button:hover{
        transform: translateY(-1px);
        filter: brightness(1.02);
      }

      .pl-login-foot{
        text-align:center;
        opacity:.9;
        font-size: 12px;
        margin-top: 10px;
      }

      @media (max-width: 820px){
        .pl-title{ font-size: 34px; }
        .pl-landing{ padding: 34px 20px; }
      }
    </style>
    """

    st.markdown(LANDING_CSS, unsafe_allow_html=True)

    # ---------- LOGIN ----------
    if not st.session_state["logged"]:
        st.markdown(
            """
            <div class="pl-landing">
              <div class="pl-pill">🚓 Platform Corso PL</div>

              <div class="pl-title">
                Banca dati, simulazioni e quiz<br>
                <span style="opacity:.9;">Polizia Locale</span>
              </div>

              <div class="pl-sub">
                Piattaforma didattica a cura di <b>Raffaele Sotero</b> • Correzione finale dettagliata.<br>
                Simulazioni d’esame, banca dati normativa e casi pratici commentati.
              </div>

              <div class="pl-chiprow">
                <div class="pl-chip">Casi pratici</div>
                <div class="pl-chip">Quiz</div>
                <div class="pl-chip">Banca dati</div>
              </div>

              <div class="pl-login-wrap">
                <div class="pl-login-card">
                  <div class="pl-login-title">Accesso corsista</div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Card “reale” (widget Streamlit) – la CSS sopra la rende uguale al mockup
        with st.container():
            # Questo container finisce dentro la card perché Streamlit lo renderizza subito sotto:
            # (visivamente risulta come nell’immagine)
            full_name = st.text_input("Nome e Cognome (es. Mario Rossi)")
            course_pass = st.text_input(
                "Password del corso",
                type="password",
                help="Inserisci la password fornita per accedere.",
            )

            if st.button("Entra"):
                if not full_name or not course_pass:
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

            st.markdown(
                '<div class="pl-login-foot">Accesso riservato ai corsisti • Inserisci Nome e Cognome e la password del corso.</div>',
                unsafe_allow_html=True,
            )

        st.stop()

    # Se sei loggato, da qui in poi resta TUTTO come già hai (non tocchiamo nulla)
    st.subheader("Accesso corsista")

    st.subheader("Accesso corsista")

    # ---------- LOGIN ----------
    if not st.session_state["logged"]:
        full_name = st.text_input("Nome e Cognome (es. Mario Rossi)")
        course_pass = st.text_input("Password corso", type="password", help="Inserisci la password per accedere (es. polizia2026)")

        if st.button("Entra"):
            if not full_name or not course_pass:
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

    # ---------- PROFILO ----------
    student = st.session_state["student"]
    st.info(f"Connesso come: {student['nickname']} (corso {student['class_code']})")

    col1, col2, col3 = st.columns([1, 1, 5])
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

    # =========================================================
# APP
# =========================================================
bank_count = fetch_bank_count()

# ---------------------------------------------------------
# LANDING WOW (MOSTRA SOLO SE NON LOGGATO)
# ---------------------------------------------------------
LANDING_CSS = """
<style>
/* Nascondo header Streamlit */
header {visibility: hidden;}

.block-container { max-width: 1100px; padding-top: 1.2rem; padding-bottom: 3rem; }

/* Sfondo WOW (blu/rosso stile lampeggianti) */
.landing-bg{
  position: relative;
  border-radius: 22px;
  overflow: hidden;
  padding: 34px 34px 28px 34px;
  margin-bottom: 18px;
  border: 1px solid rgba(255,255,255,.14);
  box-shadow: 0 22px 60px rgba(0,0,0,.30);
  background:
    radial-gradient(1200px 500px at 20% 0%, rgba(59,130,246,.28), transparent 60%),
    radial-gradient(900px 500px at 85% 10%, rgba(244,63,94,.22), transparent 55%),
    linear-gradient(135deg, #071a33 0%, #0b2b52 48%, #1a0830 100%);
}

/* Linea luci (blu/rosso) */
.landing-bg:before{
  content:"";
  position:absolute;
  left:-10%;
  top:22px;
  width:120%;
  height:2px;
  background: linear-gradient(90deg, rgba(59,130,246,0) 0%, rgba(59,130,246,.9) 35%, rgba(244,63,94,.9) 65%, rgba(244,63,94,0) 100%);
  opacity:.95;
}

/* Badge */
.landing-badge{
  display:inline-flex;
  align-items:center;
  gap:10px;
  padding: 7px 14px;
  border-radius: 999px;
  background: rgba(255,255,255,.12);
  border: 1px solid rgba(255,255,255,.14);
  color: rgba(255,255,255,.92);
  font-weight: 800;
  font-size: 13px;
  margin-bottom: 16px;
}

/* Titoli */
.landing-title{
  color: #ffffff;
  font-weight: 900;
  letter-spacing: .2px;
  font-size: 44px;
  line-height: 1.08;
  margin: 0 0 10px 0;
}
.landing-sub{
  color: rgba(255,255,255,.86);
  font-size: 15px;
  line-height: 1.5;
  max-width: 820px;
  margin-bottom: 16px;
}
.landing-chips{
  display:flex;
  gap:10px;
  flex-wrap:wrap;
  margin-bottom: 18px;
}
.landing-chip{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,.16);
  background: rgba(0,0,0,.18);
  color: rgba(255,255,255,.90);
  font-weight: 800;
  font-size: 13px;
}

/* Card login */
.login-card{
  margin-top: 16px;
  background: rgba(255,255,255,.10);
  border: 1px solid rgba(255,255,255,.16);
  border-radius: 20px;
  padding: 18px 18px 16px 18px;
  backdrop-filter: blur(10px);
}
.login-title{
  color:#fff;
  font-size: 20px;
  font-weight: 900;
  margin: 0 0 10px 0;
  text-align:center;
}
.login-hint{
  color: rgba(255,255,255,.78);
  font-size: 13px;
  margin-top: 10px;
  text-align:center;
}

/* Input Streamlit “glass” */
.landing-input [data-baseweb="input"] > div{
  border-radius: 14px !important;
  background: rgba(255,255,255,.92) !important;
}
.landing-input input{
  font-weight: 700 !important;
}

/* Bottone “Entra” gold */
.landing-btn .stButton > button{
  width: 100%;
  border-radius: 14px !important;
  padding: 12px 14px !important;
  border: 1px solid rgba(0,0,0,.12) !important;
  background: linear-gradient(180deg, #f7c777 0%, #e7a93d 100%) !important;
  color: #1b1b1b !important;
  font-weight: 900 !important;
  box-shadow: 0 14px 30px rgba(231,169,61,.25) !important;
}
.landing-btn .stButton > button:hover{
  transform: translateY(-1px);
}
</style>
"""

def render_landing_login(total_questions: int):
    st.markdown(LANDING_CSS, unsafe_allow_html=True)

    st.markdown('<div class="landing-bg">', unsafe_allow_html=True)

    # NB: qui metto "Corso PL 2026" come vuoi tu
    st.markdown(
        f"""
        <div class="landing-badge">🚓 Corso PL 2026</div>
        <div class="landing-title">Banca dati, simulazioni e quiz<br><span style="opacity:.92;">Polizia Locale</span></div>
        <div class="landing-sub">
          Piattaforma didattica a cura di <b>Raffaele Sotero</b> • Correzione finale dettagliata.<br>
          Simulazioni d’esame, banca dati normativa e casi pratici commentati.
        </div>
        <div class="landing-chips">
          <div class="landing-chip">📚 Banca dati: {total_questions} domande</div>
          <div class="landing-chip">⏱️ 30 minuti</div>
          <div class="landing-chip">✅ 1 punto per risposta esatta</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.markdown('<div class="login-title">Accesso corsista</div>', unsafe_allow_html=True)

    st.markdown('<div class="landing-input">', unsafe_allow_html=True)
    full_name = st.text_input("Nome e Cognome (es. Mario Rossi)", key="landing_full_name")
    course_pass = st.text_input("Password del corso", type="password", key="landing_course_pass")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="landing-btn">', unsafe_allow_html=True)
    go = st.button("Entra", key="landing_enter")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        '<div class="login-hint">Accesso riservato ai corsisti • Inserisci Nome e Cognome e la password del corso.</div>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)  # login-card
    st.markdown("</div>", unsafe_allow_html=True)  # landing-bg

    # Login logic (uguale alla tua)
    if go:
        if not full_name or not course_pass:
            st.error("Inserisci Nome e Cognome + Password.")
            st.stop()
        if course_pass != COURSE_PASSWORD:
            st.error("Password errata. Riprova.")
            st.stop()

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


# 1) Se NON loggato: mostra SOLO landing WOW e STOP
if not st.session_state["logged"]:
    render_landing_login(bank_count)
    st.stop()

# 2) Se loggato: da qui in poi il tuo flusso normale (NIENTE doppioni)
render_header(bank_count)

tab_stud, tab_doc = st.tabs(["🎓 Corsista", "🧑‍🏫 Docente (upload CSV)"])


# =========================================================
# DOCENTE
# =========================================================
with tab_doc:
    st.subheader("Carica banca dati (CSV)")
    st.write("CSV richiesto: `question_text, option_a, option_b, option_c, option_d, correct_option` (+ opzionale `explanation`).")
    st.write("Nota: `option_d` può essere vuota. Se è vuota, la D non comparirà nel quiz.")

    admin = st.text_input("Codice docente", type="password")
    up = st.file_uploader("Carica CSV", type=["csv"])

    st.divider()
    st.write("Domande in banca dati:", fetch_bank_count())

    if up and admin == ADMIN_CODE:
        import pandas as pd
        import io

        raw = up.getvalue()
        df = None
        for enc in ("utf-8-sig", "utf-8", "latin1"):
            try:
                df = pd.read_csv(io.BytesIO(raw), encoding=enc)
                break
            except Exception:
                df = None

        if df is None:
            st.error("Impossibile leggere il CSV. Salvalo come UTF-8.")
            st.stop()

        required = ["question_text", "option_a", "option_b", "option_c", "option_d", "correct_option"]
        miss = [c for c in required if c not in df.columns]
        if miss:
            st.error(f"Mancano colonne: {miss}")
            st.stop()

        if "explanation" not in df.columns:
            df["explanation"] = ""

        df = df.fillna("")
        df["correct_option"] = df["correct_option"].astype(str).str.strip().str.upper()
        df["option_d"] = df["option_d"].astype(str).fillna("").str.strip()

        bad = ~df["correct_option"].isin(["A", "B", "C", "D"])
        if bad.any():
            st.error("Trovate righe con correct_option non valido (deve essere A/B/C/D).")
            st.dataframe(df.loc[bad, ["question_text", "correct_option"]].head(10))
            st.stop()

        bad_d = (df["option_d"] == "") & (df["correct_option"] == "D")
        if bad_d.any():
            st.error("Righe con correct_option = D ma option_d vuota. Correggi il CSV.")
            st.dataframe(df.loc[bad_d, ["question_text", "option_d", "correct_option"]].head(20))
            st.stop()

        rows = df[required + ["explanation"]].to_dict(orient="records")

        try:
            sb.table("question_bank").insert(rows).execute()
            st.success(f"Caricate {len(rows)} domande ✅")
            st.rerun()
        except Exception as e:
            st.error("Errore inserimento in question_bank.")
            st.exception(e)

    elif up and admin != ADMIN_CODE:
        st.warning("Codice docente errato.")


# =========================================================
# CORSISTA
# =========================================================
with tab_stud:
    # DA QUI IN POI NON CAMBIO NULLA: è il tuo blocco già funzionante.
    # (Il login vecchio NON serve più perché lo fa la landing sopra)

    student = st.session_state["student"]
    st.info(f"Connesso come: {student['nickname']} (corso {student['class_code']})")

    col1, col2, col3 = st.columns([1, 1, 5])
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
    # QUI SOTTO CI INCOLLI IL TUO BLOCCO CORSISTA ESISTENTE
    # (menu_page, bank, case, sim, risultati)
    # =========================================================

# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
# padding
