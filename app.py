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
    page_title="Corso Polizia Locale — Simulazioni e Quiz",
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

/* buttons (base) */
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

/* RADIO / INPUTS */
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
   QUIZ CARD LOOK (solo estetica, logica invariata)
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
.quiz-question{
  font-weight: 800;
  font-size: 15px;
  color: #111827;
  margin: 0 0 8px 0;
}
.quiz-hint{
  color: rgba(0,0,0,.55);
  font-size: 12px;
  margin-top: 6px;
}

/* =========================================
   BOTTONE ROSSO SOLO PER "TERMINA"
   (usiamo classi CSS attaccate al container)
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
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# =========================================================
# COSTANTI
# =========================================================
N_QUESTIONS_DEFAULT = 30
DURATION_SECONDS_DEFAULT = 30 * 60  # 30 minuti

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
  <div class="hero-title">🚓 Corso Polizia Locale — Simulazioni e Quiz</div>
  <div class="hero-sub">
    Piattaforma didattica a cura di <b>Raffaele Sotero</b><br>
    Simulazioni random • {N_QUESTIONS_DEFAULT} domande • Timer {DURATION_SECONDS_DEFAULT//60} minuti • Correzione finale dettagliata
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
render_header(bank_count)

tab_stud, tab_doc = st.tabs(["🎓 Studente", "🧑‍🏫 Docente (upload CSV)"])

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
# STUDENTE
# =========================================================
with tab_stud:
    st.subheader("Accesso studente")

    # ---------- LOGIN ----------
    if not st.session_state["logged"]:
        class_code = st.text_input("Codice classe (es. CDS2026)")
        nickname = st.text_input("Nickname (es. Mirko)")

        if st.button("Entra"):
            if not class_code or not nickname:
                st.error("Inserisci codice classe e nickname.")
            else:
                try:
                    st.session_state["student"] = upsert_student(class_code, nickname)
                    st.session_state["logged"] = True
                    st.success("Accesso OK ✅")
                    st.rerun()
                except Exception as e:
                    st.error("Errore accesso.")
                    st.exception(e)

        st.stop()

    student = st.session_state["student"]

    st.info(f"Connesso come: {student['nickname']} (classe {student['class_code']})")

    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("Logout"):
            st.session_state["logged"] = False
            st.session_state["student"] = None
            st.session_state["session_id"] = None
            st.session_state["in_progress"] = False
            st.session_state["show_results"] = False
            st.session_state["started_ts"] = None
            st.session_state["finished_ts"] = None
            st.session_state["duration_seconds"] = DURATION_SECONDS_DEFAULT
            st.rerun()

    bank_count = fetch_bank_count()
    st.write(f"📚 Domande in banca dati: **{bank_count}**")

    if bank_count < N_QUESTIONS_DEFAULT:
        st.warning(f"Servono almeno {N_QUESTIONS_DEFAULT} domande. Ora: {bank_count}")
        st.stop()

    st.divider()

    # ---------- START ----------
    if (not st.session_state["in_progress"]) and (not st.session_state["show_results"]):
        st.markdown("### Simulazione (30 domande – 30 minuti)")
        st.caption("Le domande vengono estratte casualmente dalla banca dati. Il timer scorre in tempo reale.")

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
        render_live_timer(end_ts)

        progress = 1.0 - (remaining / int(st.session_state["duration_seconds"]))
        st.progress(min(max(progress, 0.0), 1.0))
        st.divider()

        # controllo scadenza (server-side, senza refresh forzato)
        if time.time() >= end_ts:
            st.warning("Tempo scaduto! Correzione automatica…")
            st.session_state["in_progress"] = False
            st.session_state["show_results"] = True
            st.session_state["finished_ts"] = time.time()
            finish_session(session_id)
            st.rerun()

        st.markdown("## 📝 Sessione in corso")

        # Lettere "bold" compatibili con radio (no markdown)
        BOLD_LETTER = {"A": "𝐀", "B": "𝐁", "C": "𝐂", "D": "𝐃"}

        for idx, row in enumerate(rows, start=1):
            # --- card più professionale, senza cambiare la logica ---
            st.markdown(
                f"""
                <div class="quiz-card">
                  <div class="quiz-title">Domanda n°{idx}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            # DOMANDA IN GRASSETTO
            st.markdown(f"**{row['question_text']}**")

            options_map = {
                "A": (row.get("option_a") or "").strip(),
                "B": (row.get("option_b") or "").strip(),
                "C": (row.get("option_c") or "").strip(),
                "D": (row.get("option_d") or "").strip(),
            }

            # MOSTRA SOLO OPZIONI CHE HANNO TESTO (D sparisce se vuota)
            letters = [k for k in ["A", "B", "C", "D"] if options_map[k] != ""]

            # per poter "non rispondere"
            radio_options = ["—"] + letters

            def fmt(opt: str) -> str:
                if opt == "—":
                    return "— (lascia senza risposta)"
                # A/B/C/D in "finto grassetto" per radio
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
            )

            # salva (— = None)
            new_val = None if choice == "—" else choice
            old_val = (row.get("chosen_option") or None)

            if new_val != old_val:
                try:
                    update_chosen_option(row_id=row["id"], session_id=session_id, chosen_letter=new_val)
# Stato risposta selezionata (più professionale)
                if new_val is None:
                st.caption("📝 **Stato:** Non hai risposto")
                else:
                st.caption(f"📝 **Stato:** Risposta selezionata → **{new_val}**")

                except Exception:
                    pass

            st.divider()

        # BOTTONE TERMINA ROSSO PROFESSIONALE (solo questo)
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

        if st.button("Nuova simulazione"):
            st.session_state["session_id"] = None
            st.session_state["in_progress"] = False
            st.session_state["show_results"] = False
            st.session_state["started_ts"] = None
            st.session_state["finished_ts"] = None
            st.session_state["duration_seconds"] = DURATION_SECONDS_DEFAULT
            st.rerun()
