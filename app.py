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
st.markdown("""
<style>
/* === CENTRA LOGIN === */
.login-wrapper {
    max-width: 420px;
    margin: 0 auto;
    margin-top: 20px;
}

/* === INPUT PIÙ COMPATTI === */
.login-wrapper input {
    height: 42px !important;
    font-size: 15px !important;
}

/* === LABEL PIÙ COMPATTE === */
.login-wrapper label {
    margin-bottom: 4px !important;
    font-size: 14px;
}

/* === BOTTONE ENTRA === */
.login-wrapper button {
    height: 46px;
    font-size: 16px;
    font-weight: 700;
}

/* === RIDUCE SPAZI STREAMLIT === */
div[data-testid="stVerticalBlock"] > div {
    gap: 0.6rem;
}
</style>
""", unsafe_allow_html=True)

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
# render_header(bank_count)
# ===============================
# HERO / LANDING PAGE
# ===============================
components.html(
    """
    <style>
        .hero-wrapper {
            background: linear-gradient(135deg, #0b2c4d, #0f4c81);
            padding: 48px 40px;
            border-radius: 18px;
            color: white;
            margin-bottom: 40px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.25);
            font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
        }
        .hero-badge {
            display: inline-block;
            background: rgba(255,255,255,0.15);
            padding: 6px 14px;
            border-radius: 999px;
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 18px;
        }
        .hero-title {
            font-size: 42px;
            font-weight: 800;
            line-height: 1.15;
            margin-bottom: 14px;
        }
        .hero-sub {
            font-size: 17px;
            opacity: 0.92;
            max-width: 900px;
            margin-bottom: 34px;
        }
        .hero-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 18px;
        }
        .hero-card {
            background: rgba(255,255,255,0.12);
            border-radius: 14px;
            padding: 18px;
            font-size: 15px;
            line-height: 1.4;
            backdrop-filter: blur(6px);
        }
        .hero-card h4 {
            margin: 0 0 6px 0;
            font-size: 16px;
            font-weight: 700;
        }
    </style>

    <div class="hero-wrapper">
        <div class="hero-badge">🚓 Platform Corso PL</div>

        <div class="hero-title">
            Banca dati, simulazioni e quiz<br>
            <span style="opacity:0.9;">Polizia Locale</span>
        </div>

        <div class="hero-sub">
            Piattaforma didattica professionale per la preparazione ai concorsi
            di Polizia Locale: simulazioni d’esame, banca dati normativa
            e casi pratici commentati.
        </div>

        <div class="hero-cards">
            <div class="hero-card">
                <h4>📚 Banca dati</h4>
                Normativa aggiornata e consultabile per lo studio.
            </div>
            <div class="hero-card">
                <h4>📝 Simulazioni quiz</h4>
                Prove d’esame realistiche con timer e correzione.
            </div>
            <div class="hero-card">
                <h4>⚖️ Casi pratici</h4>
                Applicazione concreta delle norme operative.
            </div>
        </div>
    </div>
    """,
    height=420,
)

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

    bank_count = fetch_bank_count()
    st.write(f"📚 Domande in banca dati: **{bank_count}**")
    st.divider()

    # =========================================================
    # MENU DOPO LOGIN (NUOVO)
    # =========================================================
    if (not st.session_state["in_progress"]) and (not st.session_state["show_results"]) and st.session_state["menu_page"] == "home":
        st.markdown("## Seleziona modalità")
        st.caption("Scegli cosa vuoi fare oggi. La simulazione ha il timer; banca dati e caso pratico per ora sono in modalità base.")

        # layout a 3 card
        st.markdown('<div class="menu-grid">', unsafe_allow_html=True)

        st.markdown(
            """
            <div class="menu-card">
              <div class="menu-chip">⏱️ Timer attivo</div>
              <div class="menu-title">Simulazione Quiz (30 minuti)</div>
              <div class="menu-desc">
                30 domande estratte casualmente dalla banca dati. Alla fine vedi punteggio e correzione dettagliata.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("➡️ Vai alla Simulazione"):
                st.session_state["menu_page"] = "sim"
                st.rerun()

        st.markdown(
            """
            <div class="menu-card">
              <div class="menu-chip">📚 Studio libero</div>
              <div class="menu-title">Banca dati</div>
              <div class="menu-desc">
                Modalità studio: sfoglia le domande e allenati senza timer. (In arrivo: filtri per argomento)
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with c2:
            if st.button("➡️ Vai alla Banca dati"):
                st.session_state["menu_page"] = "bank"
                st.rerun()

        st.markdown(
            """
            <div class="menu-card">
              <div class="menu-chip">🧠 Allenamento</div>
              <div class="menu-title">Caso pratico</div>
              <div class="menu-desc">
                Rispondi a uno scenario operativo. (In arrivo: correzione guidata e griglia di valutazione)
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with c3:
            if st.button("➡️ Vai al Caso pratico"):
                st.session_state["menu_page"] = "case"
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    # =========================================================
    # =========================================================
    # BANCA DATI (PDF materiali di studio) - NO TIMER
    # =========================================================
    if (not st.session_state["in_progress"]) and (not st.session_state["show_results"]) and st.session_state["menu_page"] == "bank":
        st.markdown("## 📚 Banca dati")
        st.caption("Materiali di studio consultabili (PDF).")

        # Stato selezione documento
        if "bank_doc" not in st.session_state:
            st.session_state["bank_doc"] = None

        # Documenti disponibili
        docs = [
            {
                "title": "LEGGE QUADRO (Legge 7 marzo 1986, n. 65)",
                "url": "https://sjeztkpspxzxyctfjsyg.supabase.co/storage/v1/object/public/study/legge%20quadro%20completa.pdf",
            },
            {
                "title": "CODICE DELLA STRADA (D.Lgs. 30 aprile 1992, n. 285)",
                "url": "https://sjeztkpspxzxyctfjsyg.supabase.co/storage/v1/object/public/study/cds%20completo.pdf",
            },
        ]

                # Lista argomenti (clic diretto -> apre PDF in nuova scheda)
        st.markdown("### Seleziona un argomento (si apre in una nuova scheda)")
        for d in docs:
            st.link_button(f"📄 {d['title']}", d["url"], use_container_width=True)

        st.stop()


    # =========================================================
    # CASO PRATICO (placeholder, NO timer)
    # =========================================================
    if (not st.session_state["in_progress"]) and (not st.session_state["show_results"]) and st.session_state["menu_page"] == "case":
        st.markdown("## 🧠 Caso pratico")
        st.caption("Qui inseriremo casi pratici per argomento. Per ora è una versione base senza correzione automatica.")

        st.markdown("### Scenario (demo)")
        st.write(
            "Durante un controllo, un conducente circola con documento di guida non esibito al momento del controllo e sostiene di averlo dimenticato a casa."
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
    # SIMULAZIONE (timer SOLO QUI)
    # =========================================================
    if bank_count < N_QUESTIONS_DEFAULT:
        st.warning(f"Servono almeno {N_QUESTIONS_DEFAULT} domande per la simulazione. Ora: {bank_count}")
        st.stop()

    # ---------- START SIM (solo se menu_page == sim) ----------
    if (not st.session_state["in_progress"]) and (not st.session_state["show_results"]) and st.session_state["menu_page"] == "sim":
        st.markdown("### Simulazione (30 domande – 30 minuti)")
        st.caption("Le domande vengono estratte casualmente dalla banca dati. Il timer parte SOLO in questa modalità.")

        if st.button("Inizia simulazione"):
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

        elapsed = int(time.time() - float(st.session_state["started_ts"]))
        remaining = max(0, int(st.session_state["duration_seconds"]) - elapsed)

        # TIMER SUPER FLUIDO (NO RERUN)
        end_ts = float(st.session_state["started_ts"]) + int(st.session_state["duration_seconds"])
        time_up = time.time() >= end_ts
        render_live_timer(end_ts)

        progress = 1.0 - (remaining / int(st.session_state["duration_seconds"]))
        st.progress(min(max(progress, 0.0), 1.0))
        st.divider()

        # controllo scadenza
        if time.time() >= end_ts:
            st.warning("Tempo scaduto! Correzione automatica…")
            st.session_state["in_progress"] = False
            st.session_state["show_results"] = True
            st.session_state["finished_ts"] = time.time()
            finish_session(session_id)
            st.rerun()

        st.markdown("## 📝 Sessione in corso")

        answered = sum(1 for r in rows if (r.get("chosen_option") or "").strip())
        st.markdown(
            f'<div class="badge">✅ <strong>Risposte date</strong>: {answered}/{len(rows)}</div>',
            unsafe_allow_html=True
        )

        # Lettere "bold" compatibili con radio (no markdown)
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
                return f"{BOLD_LETTER.get(opt,opt)}) {options_map[opt]}"

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
            old_val = (row.get("chosen_option") or None)

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
        if st.button("Termina simulazione e vedi correzione"):
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

        if st.button("Torna al menu"):
            st.session_state["session_id"] = None
            st.session_state["in_progress"] = False
            st.session_state["show_results"] = False
            st.session_state["started_ts"] = None
            st.session_state["finished_ts"] = None
            st.session_state["duration_seconds"] = DURATION_SECONDS_DEFAULT
            st.session_state["menu_page"] = "home"
            st.rerun()

# =========================================================
# PADDING (non rimuovere nulla)
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
