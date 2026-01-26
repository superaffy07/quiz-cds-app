import os
import time
import uuid
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client


# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="Simulazioni & Quiz — Polizia Locale",
    page_icon="🚓",
    layout="wide",
)

SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL"))
SUPABASE_ANON_KEY = st.secrets.get("SUPABASE_ANON_KEY", os.getenv("SUPABASE_ANON_KEY"))
ADMIN_CODE = st.secrets.get("ADMIN_CODE", os.getenv("ADMIN_CODE", "DOCENTE1"))

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("❌ Mancano SUPABASE_URL e/o SUPABASE_ANON_KEY nelle Secrets/Env.")
    st.stop()

sb = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

SIM_QUESTIONS = 30
SIM_DURATION_SECONDS = 30 * 60  # 30 minuti


# =========================================================
# CSS (non blu, leggibile)
# =========================================================
st.markdown(
    """
<style>
:root{
  --bg:#ffffff;
  --text:#0b1220;
  --muted:#5b6473;
  --card:#ffffff;
  --border:rgba(0,0,0,.08);
  --shadow:0 8px 24px rgba(0,0,0,.06);
  --primary:#111827;
  --danger:#dc2626;
}

.block-container{padding-top: 24px; padding-bottom: 24px;}
h1,h2,h3,h4{color:var(--text);}
p,li,span,div{color:var(--text);}

.header-wrap{
  padding:18px 18px;
  border:1px solid var(--border);
  border-radius:16px;
  background: linear-gradient(180deg, rgba(0,0,0,0.03), rgba(0,0,0,0.00));
  box-shadow: var(--shadow);
  margin-bottom: 14px;
}
.header-title{
  font-size: 28px;
  font-weight: 800;
  letter-spacing: .2px;
  margin: 0;
}
.header-sub{
  margin-top: 6px;
  color: var(--muted);
  font-size: 14px;
}

.badge-row{display:flex; gap:10px; flex-wrap:wrap; margin-top:10px;}
.badge{
  display:inline-flex;
  align-items:center;
  gap:8px;
  padding:6px 10px;
  border-radius:999px;
  border:1px solid var(--border);
  background: rgba(0,0,0,0.03);
  font-size: 12.5px;
  color: var(--text);
}

.quiz-card{
  border:1px solid var(--border);
  background: var(--card);
  border-radius: 16px;
  padding: 14px 16px;
  box-shadow: var(--shadow);
  margin-bottom: 14px;
}
.quiz-title{
  font-weight: 800;
  font-size: 18px;
  margin-bottom: 8px;
}
.quiz-q{
  font-size: 16px;
  line-height: 1.35;
  margin-bottom: 8px;
}
.small-muted{color: var(--muted); font-size: 13px;}

.timer-box{
  display:flex;
  align-items:center;
  justify-content:space-between;
  border:1px solid var(--border);
  border-radius:14px;
  padding:12px 14px;
  background: rgba(0,0,0,0.02);
  margin: 8px 0 14px 0;
}
.timer-left{display:flex; gap:10px; align-items:center;}
.timer-label{font-size:13px; color:var(--muted);}
.timer-value{font-size:18px; font-weight:800;}

.end-btn-wrap{
  display:flex;
  justify-content:flex-end;
  margin-top: 10px;
}
.end-btn-wrap button{
  background: var(--danger) !important;
  color: white !important;
  border: 0 !important;
}
.end-btn-wrap button:hover{
  filter: brightness(0.95);
}

.result-card{
  border:1px solid var(--border);
  border-radius:16px;
  padding: 16px;
  box-shadow: var(--shadow);
  background: var(--card);
  margin-top: 12px;
}
.correct{color:#16a34a; font-weight:800;}
.wrong{color:#dc2626; font-weight:800;}
.neutral{color:#6b7280; font-weight:800;}

.status-pill{padding:8px 12px;border-radius:12px;margin-top:8px;margin-bottom:8px;font-size:0.95rem;border:1px solid rgba(0,0,0,0.06);}
.status-pill.ok{background:rgba(16,185,129,0.12);}
.status-pill.warn{background:rgba(245,158,11,0.14);}

.kpi-row{display:flex;gap:10px;flex-wrap:wrap;margin:8px 0 14px 0;}
.kpi-pill{background:rgba(0,0,0,0.04);border:1px solid rgba(0,0,0,0.06);padding:6px 10px;border-radius:999px;font-size:0.92rem;}
</style>
""",
    unsafe_allow_html=True,
)


# =========================================================
# Helpers
# =========================================================
BOLD_LETTER = {"A": "**A)**", "B": "**B)**", "C": "**C)**", "D": "**D)**"}

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def format_mmss(seconds: int) -> str:
    seconds = max(0, int(seconds))
    m = seconds // 60
    s = seconds % 60
    return f"{m:02d}:{s:02d}"

def safe_str(x) -> str:
    return "" if x is None else str(x).strip()

def get_secret(name: str, default=None):
    return st.secrets.get(name, os.getenv(name, default))

def upsert_student(class_code: str, nickname: str) -> dict:
    payload = {"class_code": class_code, "nickname": nickname}
    res = sb.table("students").upsert(payload, on_conflict="class_code,nickname").select("*").execute()
    if not res.data:
        raise RuntimeError("Impossibile creare/recuperare studente.")
    return res.data[0]

def count_question_bank() -> int:
    res = sb.table("question_bank").select("id", count="exact").execute()
    return int(res.count or 0)

def fetch_random_questions(n: int) -> list[dict]:
    # semplice: prende più righe e poi campiona lato python
    res = sb.table("question_bank").select("*").execute()
    data = res.data or []
    if len(data) < n:
        raise RuntimeError(f"Banca dati insufficiente: trovate {len(data)} domande, servono {n}.")
    import random
    return random.sample(data, n)

def create_session(student_id: int) -> dict:
    payload = {
        "student_id": student_id,
        "mode": "quiz",
        "topic_scope": "all",
        "selected_topic_id": None,
        "n_questions": SIM_QUESTIONS,
        "started_at": now_utc().isoformat(),
    }
    res = sb.table("sessions").insert(payload).select("*").execute()
    return res.data[0]

def insert_session_questions(session_id: str, questions: list[dict]) -> None:
    rows = []
    for q in questions:
        # option_d può essere vuota -> salviamo stringa vuota (NON NULL)
        rows.append(
            {
                "session_id": session_id,
                "topic_id": None,
                "question_text": safe_str(q.get("question_text")),
                "option_a": safe_str(q.get("option_a")),
                "option_b": safe_str(q.get("option_b")),
                "option_c": safe_str(q.get("option_c")),
                "option_d": safe_str(q.get("option_d")),  # ok anche ""
                "correct_option": safe_str(q.get("correct_option")).upper(),
                "chosen_option": None,
                "explanation": safe_str(q.get("explanation")),
            }
        )
    if rows:
        sb.table("quiz_answers").insert(rows).execute()

def fetch_session_questions(session_id: str) -> list[dict]:
    res = (
        sb.table("quiz_answers")
        .select("*")
        .eq("session_id", session_id)
        .order("id", desc=False)
        .execute()
    )
    return res.data or []

def update_chosen_option(row_id: int, session_id: str, chosen_letter: str | None):
    payload = {"chosen_option": chosen_letter}
    sb.table("quiz_answers").update(payload).eq("id", row_id).eq("session_id", session_id).execute()

def finish_session(session_id: str):
    sb.table("sessions").update({"finished_at": now_utc().isoformat()}).eq("id", session_id).execute()

def compute_score(rows: list[dict]) -> tuple[int, int]:
    total = len(rows)
    correct = 0
    for r in rows:
        if safe_str(r.get("chosen_option")).upper() == safe_str(r.get("correct_option")).upper():
            correct += 1
    return correct, total


# =========================================================
# JS Timer (fluido senza scurire / rerun aggressivo)
# =========================================================
def timer_component(end_ts: float, key: str = "timer"):
    """
    Timer fluido lato client.
    - mostra il countdown aggiornato ogni secondo
    - quando scade, setta window.streamlitSetComponentValue("DONE")
    """
    html = f"""
    <div class="timer-box">
      <div class="timer-left">
        <div style="font-size:20px;">⏱️</div>
        <div>
          <div class="timer-label">Tempo residuo</div>
          <div class="timer-value" id="timer_val">--:--</div>
        </div>
      </div>
      <div class="timer-label">Simulazione: {SIM_QUESTIONS} domande — {SIM_DURATION_SECONDS//60} minuti</div>
    </div>

    <script>
      const endTs = {end_ts};
      const el = document.getElementById("timer_val");

      function pad(n){{ return (n<10? "0":"") + n; }}
      function render() {{
        const now = Date.now()/1000;
        let diff = Math.max(0, Math.floor(endTs - now));
        const m = Math.floor(diff/60);
        const s = diff % 60;
        el.textContent = pad(m) + ":" + pad(s);
        if(diff <= 0) {{
          // segnala a Streamlit che è finito
          const msg = {{isStreamlitMessage: true, type: "streamlit:setComponentValue", value: "DONE"}};
          window.parent.postMessage(msg, "*");
        }}
      }}
      render();
      setInterval(render, 1000);
    </script>
    """
    return components.html(html, height=90, key=key)


# =========================================================
# HEADER
# =========================================================
st.markdown(
    """
<div class="header-wrap">
  <div class="header-title">🚓 Simulazioni & Quiz — Polizia Locale</div>
  <div class="header-sub">Piattaforma didattica a cura di <b>Raffaele Sotero</b> • banca dati in crescita • correzione finale</div>
  <div class="badge-row">
    <div class="badge">📚 30 domande random</div>
    <div class="badge">⏱️ Timer 30 minuti</div>
    <div class="badge">✅ Correzione finale</div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)


# =========================================================
# STATE INIT
# =========================================================
if "logged" not in st.session_state:
    st.session_state["logged"] = False
if "student" not in st.session_state:
    st.session_state["student"] = None
if "active_session_id" not in st.session_state:
    st.session_state["active_session_id"] = None
if "sim_end_ts" not in st.session_state:
    st.session_state["sim_end_ts"] = None
if "show_correction" not in st.session_state:
    st.session_state["show_correction"] = False


# =========================================================
# STUDENT LOGIN
# =========================================================
with st.container():
    st.subheader("Accesso studente")
    class_code = st.text_input("Codice classe", value="CDS2026")
    nickname = st.text_input("Nickname (es. Mirko)")

    colA, colB = st.columns([1, 2])
    with colA:
        if st.button("Entra ✅"):
            if not class_code or not nickname:
                st.error("Inserisci codice classe e nickname.")
            else:
                st.session_state["student"] = upsert_student(class_code.strip(), nickname.strip())
                st.session_state["logged"] = True
                st.success("Accesso OK ✅")

    if st.session_state.get("logged"):
        student = st.session_state["student"]
        st.info(f"Connesso come: **{student['nickname']}** (classe **{student['class_code']}**)")

        if st.button("Logout"):
            st.session_state["logged"] = False
            st.session_state["student"] = None
            st.session_state["active_session_id"] = None
            st.session_state["sim_end_ts"] = None
            st.session_state["show_correction"] = False
            st.rerun()

        st.caption(f"📦 Domande in banca dati: **{count_question_bank()}**")


# =========================================================
# SIMULAZIONE
# =========================================================
if st.session_state.get("logged"):
    st.markdown("---")
    st.header("Simulazione (30 domande — 30 minuti)")

    # Avvio simulazione
    if st.session_state["active_session_id"] is None and not st.session_state["show_correction"]:
        if st.button("Inizia simulazione"):
            try:
                sess = create_session(st.session_state["student"]["id"])
                picked = fetch_random_questions(SIM_QUESTIONS)
                insert_session_questions(sess["id"], picked)

                st.session_state["active_session_id"] = sess["id"]
                st.session_state["sim_end_ts"] = time.time() + SIM_DURATION_SECONDS
                st.session_state["show_correction"] = False

                st.success("Simulazione avviata ✅")
                st.rerun()
            except Exception as e:
                st.error("Errore avvio simulazione.")
                st.exception(e)

    # Sessione in corso / Correzione
    session_id = st.session_state.get("active_session_id")
    end_ts = st.session_state.get("sim_end_ts")

    if session_id and end_ts and not st.session_state["show_correction"]:
        remaining = int(end_ts - time.time())

        # Timer fluido (client)
        timer_status = timer_component(end_ts=end_ts, key=f"timer_{session_id}")

        # Se scaduto -> correzione
        if remaining <= 0 or timer_status == "DONE":
            finish_session(session_id)
            st.session_state["show_correction"] = True
            st.rerun()

        # Carico domande
        rows = fetch_session_questions(session_id)

        # KPI in alto: risposte date / totali
        answered = sum(1 for r in rows if (r.get("chosen_option") or "").strip())
        st.markdown(
            f'''
            <div class="kpi-row">
              <span class="kpi-pill">✅ Risposte date: <b>{answered}/{len(rows)}</b></span>
              <span class="kpi-pill">⏱️ Tempo residuo: <b>{format_mmss(max(0, int(end_ts - time.time())))}</b></span>
            </div>
            ''',
            unsafe_allow_html=True,
        )

        # progress
        progress = answered / max(1, len(rows))
        st.progress(progress)
        st.divider()

        time_up = time.time() >= end_ts

        for idx, row in enumerate(rows, start=1):
            q_text = safe_str(row.get("question_text"))

            opt_a = safe_str(row.get("option_a"))
            opt_b = safe_str(row.get("option_b"))
            opt_c = safe_str(row.get("option_c"))
            opt_d = safe_str(row.get("option_d"))

            options = []
            if opt_a:
                options.append(("A", opt_a))
            if opt_b:
                options.append(("B", opt_b))
            if opt_c:
                options.append(("C", opt_c))
            if opt_d:
                options.append(("D", opt_d))

            # current selection
            current = safe_str(row.get("chosen_option")).upper()
            if current not in [x[0] for x in options]:
                current = "—"

            radio_options = ["—"] + [x[0] for x in options]

            def fmt(letter: str) -> str:
                if letter == "—":
                    return "— (non risposto)"
                for k, v in options:
                    if k == letter:
                        return f"{BOLD_LETTER.get(k, k)} {v}"
                return letter

            st.markdown(
                f'<div class="quiz-card"><div class="quiz-title">Domanda n°{idx} di {len(rows)}</div>'
                f'<div class="quiz-q"><b>{q_text}</b></div>',
                unsafe_allow_html=True,
            )

            choice = st.radio(
                "Seleziona risposta",
                options=radio_options,
                index=radio_options.index(current),
                format_func=fmt,
                key=f"q_{row['id']}",
                disabled=time_up,
            )

            # salva (— = None)
            new_val = None if choice == "—" else choice
            old_val = (row.get("chosen_option") or None)

            if (not time_up) and (new_val != old_val):
                try:
                    update_chosen_option(
                        row_id=row["id"],
                        session_id=session_id,
                        chosen_letter=new_val,
                    )
                except Exception:
                    pass

            # Stato risposta selezionata (feedback professionale)
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
            st.markdown("</div>", unsafe_allow_html=True)

        # Bottone termina (rosso)
        st.markdown('<div class="end-btn-wrap">', unsafe_allow_html=True)
        if st.button("Termina simulazione e vedi correzione"):
            finish_session(session_id)
            st.session_state["show_correction"] = True
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # Correzione finale
    if session_id and st.session_state.get("show_correction"):
        st.markdown("---")
        st.header("✅ Correzione finale")

        rows = fetch_session_questions(session_id)
        score, total = compute_score(rows)

        st.markdown(
            f"""
<div class="result-card">
  <div style="font-size:18px; font-weight:800;">Punteggio finale</div>
  <div style="font-size:28px; font-weight:900; margin-top:6px;">{score} / {total}</div>
  <div class="small-muted" style="margin-top:6px;">Risultato calcolato confrontando risposte selezionate e corrette.</div>
</div>
""",
            unsafe_allow_html=True,
        )

        for i, r in enumerate(rows, start=1):
            q = safe_str(r.get("question_text"))
            correct = safe_str(r.get("correct_option")).upper()
            chosen = safe_str(r.get("chosen_option")).upper() or "—"

            # testo opzioni
            opts = {
                "A": safe_str(r.get("option_a")),
                "B": safe_str(r.get("option_b")),
                "C": safe_str(r.get("option_c")),
                "D": safe_str(r.get("option_d")),
            }

            def opt_text(letter):
                t = safe_str(opts.get(letter))
                return t if t else "(non presente)"

            ok = (chosen == correct)

            st.markdown(
                f"""
<div class="result-card">
  <div style="font-weight:900; font-size:16px;">Domanda n°{i}</div>
  <div style="margin-top:6px;"><b>{q}</b></div>
  <div style="margin-top:10px;">
    <div><b>Risposta selezionata:</b> <span class="{ 'correct' if ok else ('neutral' if chosen=='—' else 'wrong') }">{chosen}</span> — {opt_text(chosen) if chosen!='—' else '(non risposto)'}</div>
    <div><b>Risposta corretta:</b> <span class="correct">{correct}</span> — {opt_text(correct)}</div>
  </div>
</div>
""",
                unsafe_allow_html=True,
            )

        st.success("Sessione completata ✅")

        if st.button("Nuova simulazione"):
            st.session_state["active_session_id"] = None
            st.session_state["sim_end_ts"] = None
            st.session_state["show_correction"] = False
            st.rerun()
