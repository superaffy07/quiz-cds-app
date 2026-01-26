# app.py
import os
import time
import random
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh
from supabase import create_client


# =========================
# CONFIG / STILE
# =========================
st.set_page_config(
    page_title="Simulazioni & Quiz – Polizia Locale",
    page_icon="🚓",
    layout="wide",
)

APP_TITLE = "Simulazioni & Quiz – Polizia Locale"
APP_SUBTITLE = "Piattaforma didattica a cura di Raffaele Sotero"

THEME_CSS = """
<style>
:root{
  --bg: #0f1115;
  --card: #171a21;
  --card2: #1d212b;
  --text: #e9eef6;
  --muted: #a9b3c3;
  --accent: #2ecc71;
  --accent2: #f1c40f;
  --danger: #ff6b6b;
  --line: rgba(255,255,255,0.08);
}

html, body, [class*="css"]{
  font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
}

.block-container { padding-top: 1.2rem; }

.hero{
  background: linear-gradient(135deg, rgba(46,204,113,0.16), rgba(241,196,15,0.10));
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 18px 18px 14px 18px;
  margin-bottom: 14px;
}

.hero h1{
  margin: 0;
  font-size: 30px;
  color: #0b0f14;
}

.hero .subtitle{
  margin-top: 6px;
  color: #0b0f14;
  opacity: 0.82;
  font-weight: 600;
}

.badge{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,0.60);
  color: #0b0f14;
  font-weight: 700;
  font-size: 12px;
}

.card{
  background: #ffffff;
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 16px;
  padding: 14px;
  margin-bottom: 12px;
}

.kpi{
  display:flex;
  gap:10px;
  flex-wrap: wrap;
}
.kpi .pill{
  background: #0b0f14;
  color: white;
  border-radius: 999px;
  padding: 8px 10px;
  font-weight: 700;
  font-size: 12px;
}

.smallmuted{
  color: rgba(0,0,0,0.6);
  font-size: 13px;
}

hr.soft{
  border: none;
  height: 1px;
  background: rgba(0,0,0,0.08);
  margin: 10px 0;
}

.answer-good{ color: #0f8a3a; font-weight: 800; }
.answer-bad{ color: #c0392b; font-weight: 800; }

</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)


# =========================
# SUPABASE
# =========================
def get_supabase():
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        st.error("Mancano SUPABASE_URL e/o SUPABASE_KEY nelle Secrets/Env.")
        st.stop()
    return create_client(url, key)


sb = get_supabase()


# =========================
# UTILS
# =========================
def safe_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x).strip()

def normalize_correct_letter(x: Any) -> str:
    s = safe_str(x).upper()
    s = s.replace(")", "").replace(".", "").strip()
    if s in {"A", "B", "C", "D"}:
        return s
    return ""


def render_countdown(end_epoch: float):
    """Timer visivo FLUIDO (aggiornato in JS ogni 200ms, mostra però i secondi)."""
    components.html(
        f"""
        <div style="
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:12px;
            background:#fff;
            border:1px solid rgba(0,0,0,0.10);
            border-radius:14px;
            padding:10px 12px;
            margin:8px 0 10px 0;
        ">
          <div style="font-weight:800;">⏳ Tempo rimanente</div>
          <div id="cd" style="font-weight:900; font-size:18px; color:#c0392b;">--:--</div>
        </div>

        <script>
        const end = {end_epoch} * 1000;

        function pad(n) {{
          return String(n).padStart(2,'0');
        }}

        function draw() {{
          const now = Date.now();
          let ms = end - now;
          if (ms < 0) ms = 0;

          const total = Math.floor(ms / 1000);
          const m = Math.floor(total / 60);
          const s = total % 60;

          document.getElementById("cd").innerText = pad(m) + ":" + pad(s);
        }}

        draw();
        setInterval(draw, 200);
        </script>
        """,
        height=70,
    )


def upsert_student(class_code: str, nickname: str) -> Dict[str, Any]:
    """Inserisce o recupera studente (unique class_code + nickname)."""
    class_code = class_code.strip()
    nickname = nickname.strip()

    existing = (
        sb.table("students")
        .select("*")
        .eq("class_code", class_code)
        .eq("nickname", nickname)
        .execute()
        .data
    )
    if existing:
        return existing[0]

    inserted = (
        sb.table("students")
        .insert({"class_code": class_code, "nickname": nickname})
        .execute()
        .data
    )
    return inserted[0]


def fetch_all_questions() -> List[Dict[str, Any]]:
    """Legge tutta la question_bank (ok con 120/1000)."""
    rows = sb.table("question_bank").select("*").execute().data
    return rows or []


def create_session(student_id: int, n_questions: int = 30) -> Dict[str, Any]:
    sess = (
        sb.table("sessions")
        .insert(
            {
                "student_id": student_id,
                "mode": "simulazione",
                "topic_scope": "all",
                "selected_topic_id": None,
                "n_questions": int(n_questions),
                "started_at": None,
                "finished_at": None,
            }
        )
        .execute()
        .data
    )
    return sess[0]


def insert_session_questions(session_id: str, picked: List[Dict[str, Any]]):
    """Salva le domande 'fotografate' in quiz_answers. option_d deve SEMPRE avere un valore ('' se assente)."""
    rows = []
    for q in picked:
        opt_d = safe_str(q.get("option_d"))
        # se non c'è D -> stringa vuota (evita errori NOT NULL su quiz_answers.option_d)
        if opt_d == "":
            opt_d = ""

        rows.append(
            {
                "session_id": session_id,
                "topic_id": q.get("topic_id", None),
                "question_text": safe_str(q.get("question_text")),
                "option_a": safe_str(q.get("option_a")),
                "option_b": safe_str(q.get("option_b")),
                "option_c": safe_str(q.get("option_c")),
                "option_d": opt_d,
                "correct_option": normalize_correct_letter(q.get("correct_option")),
                "chosen_option": None,
                "explanation": safe_str(q.get("explanation")),
            }
        )
    if rows:
        sb.table("quiz_answers").insert(rows).execute()


def fetch_session_questions(session_id: str) -> List[Dict[str, Any]]:
    rows = (
        sb.table("quiz_answers")
        .select("*")
        .eq("session_id", session_id)
        .order("id", desc=False)
        .execute()
        .data
    )
    return rows or []


def save_choice(answer_row_id: int, chosen_letter: str):
    sb.table("quiz_answers").update({"chosen_option": chosen_letter}).eq("id", answer_row_id).execute()


def finish_session(session_id: str):
    sb.table("sessions").update({"finished_at": "now()"}).eq("id", session_id).execute()


def letter_to_text(q: Dict[str, Any], letter: str) -> str:
    letter = (letter or "").upper()
    m = {
        "A": safe_str(q.get("option_a")),
        "B": safe_str(q.get("option_b")),
        "C": safe_str(q.get("option_c")),
        "D": safe_str(q.get("option_d")),
    }
    return m.get(letter, "")


def csv_to_question_bank(df: pd.DataFrame) -> pd.DataFrame:
    """Normalizza CSV docente -> question_bank."""
    # attese: source_pdf, question_no, question_text, option_a, option_b, option_c, option_d, correct_option
    rename_map = {}
    for c in df.columns:
        cc = c.strip().lower()
        rename_map[c] = cc
    df = df.rename(columns=rename_map)

    required = ["question_text", "option_a", "option_b", "option_c", "correct_option"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"CSV mancante colonne: {missing}")

    if "option_d" not in df.columns:
        df["option_d"] = ""

    if "source_pdf" not in df.columns:
        df["source_pdf"] = ""

    if "question_no" not in df.columns:
        df["question_no"] = None

    # pulizia
    for c in ["question_text", "option_a", "option_b", "option_c", "option_d", "source_pdf"]:
        df[c] = df[c].astype(str).fillna("").map(lambda x: x.strip())

    df["correct_option"] = df["correct_option"].map(normalize_correct_letter)

    # se correct è D ma D vuota -> errore
    bad = df[(df["correct_option"] == "D") & (df["option_d"].fillna("").str.strip() == "")]
    if len(bad) > 0:
        raise ValueError("Hai righe con correct_option = D ma option_d vuota. Correggi il CSV.")

    # se option_d è "nan" o simili
    df["option_d"] = df["option_d"].replace({"nan": "", "None": ""})

    return df


# =========================
# SESSION STATE DEFAULTS
# =========================
if "logged" not in st.session_state:
    st.session_state.logged = False
if "student" not in st.session_state:
    st.session_state.student = None
if "sim_started" not in st.session_state:
    st.session_state.sim_started = False
if "time_up" not in st.session_state:
    st.session_state.time_up = False
if "sim_start" not in st.session_state:
    st.session_state.sim_start = None
if "sim_end" not in st.session_state:
    st.session_state.sim_end = None
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "session_questions" not in st.session_state:
    st.session_state.session_questions = []
if "current_idx" not in st.session_state:
    st.session_state.current_idx = 0


# =========================
# HEADER
# =========================
st.markdown(
    f"""
<div class="hero">
  <div style="display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap;">
    <div>
      <h1>🚓 {APP_TITLE}</h1>
      <div class="subtitle">{APP_SUBTITLE}</div>
    </div>
    <div style="display:flex; gap:8px; align-items:center;">
      <span class="badge">✅ Correzione finale</span>
      <span class="badge">⏱️ Timer 30 min</span>
      <span class="badge">🎯 30 domande random</span>
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

tabs = st.tabs(["🎓 Studente", "🧑‍🏫 Docente (upload CSV)"])


# =========================
# STUDENTE
# =========================
with tabs[0]:
    st.markdown("### Accesso studente")

    if not st.session_state.logged:
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            class_code = st.text_input("Codice classe (es. CDS2026)", value="CDS2026")
        with c2:
            nickname = st.text_input("Nickname (es. Mirko)", value="")
        with c3:
            st.write("")
            st.write("")
            if st.button("Entra ✅", use_container_width=True):
                if not class_code.strip() or not nickname.strip():
                    st.error("Inserisci codice classe e nickname.")
                else:
                    st.session_state.student = upsert_student(class_code, nickname)
                    st.session_state.logged = True
                    st.rerun()

    if st.session_state.logged and st.session_state.student:
        st.success("Accesso OK ✅")
        st.info(f"Connesso come: **{st.session_state.student['nickname']}** (classe **{st.session_state.student['class_code']}**)")

        colA, colB, colC = st.columns([2, 2, 1])
        with colA:
            total = len(fetch_all_questions())
            st.markdown(f"<div class='kpi'><div class='pill'>📚 Domande in banca dati: {total}</div></div>", unsafe_allow_html=True)
        with colC:
            if st.button("Logout", use_container_width=True):
                for k in ["logged","student","sim_started","time_up","sim_start","sim_end","session_id","session_questions","current_idx"]:
                    if k in st.session_state:
                        del st.session_state[k]
                st.rerun()

        st.markdown("### Simulazione (30 domande – 30 minuti)")
        st.caption("Le domande vengono estratte casualmente dalla banca dati e salvate per la sessione. Correzione alla fine.")

        # Avvio simulazione
        if not st.session_state.sim_started and not st.session_state.session_id:
            if st.button("🚀 Inizia simulazione", use_container_width=True):
                bank = fetch_all_questions()
                if len(bank) < 30:
                    st.error("Banca dati insufficiente: servono almeno 30 domande.")
                else:
                    picked = random.sample(bank, 30)
                    sess = create_session(st.session_state.student["id"], 30)

                    st.session_state.session_id = sess["id"]
                    st.session_state.session_questions = []  # verranno lette dalla quiz_answers
                    st.session_state.current_idx = 0

                    # timer
                    st.session_state.sim_started = True
                    st.session_state.time_up = False
                    st.session_state.sim_start = time.time()
                    st.session_state.sim_end = st.session_state.sim_start + 30 * 60

                    # salva snapshot in quiz_answers
                    insert_session_questions(st.session_state.session_id, picked)

                    # ricarica domande sessione
                    st.session_state.session_questions = fetch_session_questions(st.session_state.session_id)
                    st.rerun()

        # Simulazione in corso
        if st.session_state.sim_started and st.session_state.session_id:
            # refresh backend ogni 1s (logica timer), ma UI timer è JS fluido
            st_autorefresh(interval=1000, key="sim_refresh")

            # check time up
            if time.time() >= float(st.session_state.sim_end):
                st.session_state.time_up = True
                st.session_state.sim_started = False
                finish_session(st.session_state.session_id)
                st.rerun()

            # timer (JS)
            render_countdown(float(st.session_state.sim_end))

            qs = st.session_state.session_questions
            n = len(qs)
            idx = int(st.session_state.current_idx)

            # progress domanda
            st.progress(min(1.0, (idx) / max(1, n)))

            # barra tempo (python)
            remaining = max(0, int(float(st.session_state.sim_end) - time.time()))
            elapsed = max(0, 30 * 60 - remaining)
            st.progress(min(1.0, elapsed / (30 * 60)), text=f"⏱️ Avanzamento tempo: {elapsed//60:02d}:{elapsed%60:02d} / 30:00")

            st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

            if n == 0:
                st.error("Nessuna domanda caricata nella sessione.")
                st.stop()

            q = qs[idx]
            q_text = safe_str(q.get("question_text"))

            st.markdown(f"<div class='card'><b>Q{idx+1}/{n}</b><br/>{q_text}</div>", unsafe_allow_html=True)

            options = []
            letters = []

            a = safe_str(q.get("option_a"))
            b = safe_str(q.get("option_b"))
            c = safe_str(q.get("option_c"))
            d = safe_str(q.get("option_d"))

            if a:
                letters.append("A")
                options.append(f"A) {a}")
            if b:
                letters.append("B")
                options.append(f"B) {b}")
            if c:
                letters.append("C")
                options.append(f"C) {c}")
            # D solo se c'è testo
            if d.strip():
                letters.append("D")
                options.append(f"D) {d}")

            chosen_letter = q.get("chosen_option")
            default_index = 0
            if chosen_letter in letters:
                default_index = letters.index(chosen_letter)

            picked_text = st.radio(
                "Seleziona risposta",
                options,
                index=default_index if chosen_letter else None,
                key=f"radio_{q['id']}",
            )

            # salva risposta immediatamente
            if picked_text:
                chosen = picked_text.split(")")[0].strip()
                if chosen in {"A", "B", "C", "D"} and chosen != chosen_letter:
                    save_choice(int(q["id"]), chosen)
                    # aggiorna in memoria
                    st.session_state.session_questions[idx]["chosen_option"] = chosen

            nav1, nav2, nav3 = st.columns([1, 1, 2])
            with nav1:
                if st.button("⬅️ Precedente", use_container_width=True, disabled=(idx == 0)):
                    st.session_state.current_idx = max(0, idx - 1)
                    st.rerun()
            with nav2:
                if st.button("➡️ Successiva", use_container_width=True, disabled=(idx >= n - 1)):
                    st.session_state.current_idx = min(n - 1, idx + 1)
                    st.rerun()
            with nav3:
                if st.button("✅ Termina simulazione e vedi correzione", use_container_width=True):
                    st.session_state.sim_started = False
                    finish_session(st.session_state.session_id)
                    st.rerun()

        # Correzione finale
        if (not st.session_state.sim_started) and st.session_state.session_id:
            qs = fetch_session_questions(st.session_state.session_id)
            n = len(qs)

            correct = 0
            for q in qs:
                if safe_str(q.get("chosen_option")).upper() == safe_str(q.get("correct_option")).upper():
                    correct += 1

            # tempo impiegato
            total_elapsed = 0
            if st.session_state.sim_start:
                total_elapsed = int(time.time() - float(st.session_state.sim_start))

            mm = total_elapsed // 60
            ss = total_elapsed % 60

            st.markdown("## ✅ Correzione finale")
            st.markdown(
                f"""
<div class="card">
  <div class="kpi">
    <div class="pill">🎯 Punteggio: {correct} / {n}</div>
    <div class="pill">⏱️ Tempo impiegato: {mm} min {ss} sec</div>
  </div>
  <div class="smallmuted" style="margin-top:8px;">
    Qui trovi, per ogni domanda, la tua risposta (con testo) e la risposta corretta (con testo).
  </div>
</div>
""",
                unsafe_allow_html=True,
            )

            # reset / nuova simulazione
            cR1, cR2 = st.columns([1, 3])
            with cR1:
                if st.button("🔄 Nuova simulazione", use_container_width=True):
                    for k in ["sim_started","time_up","sim_start","sim_end","session_id","session_questions","current_idx"]:
                        if k in st.session_state:
                            del st.session_state[k]
                    st.rerun()

            st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

            for i, q in enumerate(qs, start=1):
                qtext = safe_str(q.get("question_text"))
                your = safe_str(q.get("chosen_option")).upper()
                corr = safe_str(q.get("correct_option")).upper()

                your_txt = letter_to_text(q, your) if your else "—"
                corr_txt = letter_to_text(q, corr) if corr else "—"

                ok = (your == corr) and (your != "")
                status = "✅" if ok else "❌"

                st.markdown(
                    f"""
<div class="card">
  <b>{status} Q{i}</b><br/>
  {qtext}<br/><br/>
  <div><b>Tua risposta:</b> <span class="{ "answer-good" if ok else "answer-bad" }">{your if your else "—"}</span> — {your_txt}</div>
  <div><b>Corretta:</b> <span class="answer-good">{corr}</span> — {corr_txt}</div>
</div>
""",
                    unsafe_allow_html=True,
                )


# =========================
# DOCENTE – UPLOAD CSV
# =========================
with tabs[1]:
    st.markdown("### Docente – Upload CSV")
    st.caption("Carica un CSV nella tabella `question_bank`. Le colonne minime richieste: question_text, option_a, option_b, option_c, correct_option. option_d è opzionale.")

    uploaded = st.file_uploader("Seleziona CSV", type=["csv"])
    if uploaded:
        try:
            df = pd.read_csv(uploaded)
            df = csv_to_question_bank(df)

            st.success(f"CSV valido ✅ Righe pronte: {len(df)}")
            st.dataframe(df.head(20), use_container_width=True)

            if st.button("📥 Importa in question_bank", use_container_width=True):
                rows = []
                for _, r in df.iterrows():
                    rows.append(
                        {
                            "source_pdf": safe_str(r.get("source_pdf")),
                            "question_no": int(r["question_no"]) if str(r.get("question_no")).strip().isdigit() else None,
                            "question_text": safe_str(r.get("question_text")),
                            "option_a": safe_str(r.get("option_a")),
                            "option_b": safe_str(r.get("option_b")),
                            "option_c": safe_str(r.get("option_c")),
                            "option_d": safe_str(r.get("option_d")),
                            "correct_option": normalize_correct_letter(r.get("correct_option")),
                        }
                    )
                sb.table("question_bank").insert(rows).execute()
                st.success("Import completato ✅")
        except Exception as e:
            st.error(f"Errore CSV: {e}")
