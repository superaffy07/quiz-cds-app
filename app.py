import os
import io
import time
import random
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from supabase import create_client

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Allenamento Quiz CDS", page_icon="🚓", layout="centered")

SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL", ""))
SUPABASE_ANON_KEY = st.secrets.get("SUPABASE_ANON_KEY", os.getenv("SUPABASE_ANON_KEY", ""))
ADMIN_CODE = st.secrets.get("ADMIN_CODE", os.getenv("ADMIN_CODE", "ADMIN123"))

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("Mancano SUPABASE_URL / SUPABASE_ANON_KEY nelle Secrets di Streamlit.")
    st.stop()

sb = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# =========================
# DB HELPERS
# =========================
def upsert_student(class_code: str, nickname: str) -> dict:
    class_code = class_code.strip()
    nickname = nickname.strip()

    res = (
        sb.table("students")
        .select("*")
        .eq("class_code", class_code)
        .eq("nickname", nickname)
        .limit(1)
        .execute()
    )
    if res.data:
        return res.data[0]

    ins = sb.table("students").insert({"class_code": class_code, "nickname": nickname}).execute()
    return ins.data[0]


def create_session(student_id: int, n_questions: int, duration_seconds: int) -> dict:
    payload = {
        "student_id": student_id,
        "mode": "simulazione",
        "topic_scope": "bank",
        "selected_topic_id": None,
        "n_questions": int(n_questions),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    # NB: la tua tabella sessions accetta questi campi (come nel tuo schema)
    res = sb.table("sessions").insert(payload).execute()
    sess = res.data[0]

    # memorizza durata in session_state (non DB)
    st.session_state["duration_seconds"] = int(duration_seconds)
    return sess


def fetch_bank_count() -> int:
    # count via select head
    res = sb.table("question_bank").select("id", count="exact").limit(1).execute()
    return int(res.count or 0)


def fetch_all_bank_questions() -> list[dict]:
    # per 1000-2000 domande va bene. Se cresci tanto, poi ottimizziamo.
    res = sb.table("question_bank").select("*").order("id").execute()
    return res.data or []


def insert_session_questions(session_id: str, questions: list[dict]) -> None:
    # Salviamo le domande estratte nella tabella quiz_answers (snapshot della sessione)
    rows = []
    for q in questions:
        rows.append(
            {
                "session_id": session_id,
                "topic_id": None,
                "question_text": (q.get("question_text") or "").strip(),
                "option_a": (q.get("option_a") or "").strip(),
                "option_b": (q.get("option_b") or "").strip(),
                "option_c": (q.get("option_c") or "").strip(),
                "option_d": (q.get("option_d") or "").strip(),   # <-- mai NULL
                "correct_option": (q.get("correct_option") or "").strip().upper(),
                "chosen_option": None,
                "explanation": (q.get("explanation") or "").strip(),
            }
        )
    if rows:
        sb.table("quiz_answers").insert(rows).execute()




def fetch_session_questions(session_id: str) -> list[dict]:
    res = sb.table("quiz_answers").select("*").eq("session_id", session_id).order("id").execute()
    return res.data or []


def update_chosen_option(row_id: int, session_id: str, chosen_letter: str | None) -> None:
    sb.table("quiz_answers").update({"chosen_option": chosen_letter}).eq("id", row_id).eq("session_id", session_id).execute()


def finish_session(session_id: str) -> None:
    sb.table("sessions").update({"finished_at": datetime.now(timezone.utc).isoformat()}).eq("id", session_id).execute()


# =========================
# STATE INIT
# =========================
defaults = {
    "logged": False,
    "student": None,
    "session_id": None,
    "in_progress": False,
    "started_ts": None,          # timer start (epoch)
    "duration_seconds": 30 * 60, # 30 minuti
    "answers": {},               # {row_id: "A"/"B"/"C"/"D"}
    "show_results": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# =========================
# UI
# =========================
st.title("🚓 Allenamento Quiz CDS")
st.caption("Simulazione: 30 domande random dalla banca dati. Timer 30 minuti. Correzione finale.")

tab_stud, tab_doc = st.tabs(["🎓 Studente", "🧑‍🏫 Docente (carica banca dati)"])


# =========================
# DOCENTE TAB
# =========================
with tab_doc:
    st.subheader("Carica banca dati quiz (CSV)")
    st.write(
        "Formato CSV richiesto (colonne obbligatorie): "
        "`question_text, option_a, option_b, option_c, option_d, correct_option` "
        "(correct_option deve essere A/B/C/D). Colonna facoltativa: `explanation`."
    )

    admin = st.text_input("Codice docente", type="password")
    up = st.file_uploader("Carica CSV domande", type=["csv"])

    st.divider()
    st.write("✅ Domande attualmente in banca dati:", fetch_bank_count())

    if up and admin == ADMIN_CODE:
        data_bytes = up.getvalue()

        df = None
        for enc in ("utf-8-sig", "utf-8", "latin1"):
            try:
                df = pd.read_csv(io.BytesIO(data_bytes), encoding=enc)
                break
            except Exception:
                df = None

        if df is None:
            st.error("Impossibile leggere il CSV (encoding). Prova a salvarlo come UTF-8.")
            st.stop()

        required = ["question_text", "option_a", "option_b", "option_c", "option_d", "correct_option"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            st.error(f"Mancano colonne: {missing}")
            st.stop()

        # normalizza
        if "explanation" not in df.columns:
            df["explanation"] = ""

        df = df.fillna("")
        df["correct_option"] = df["correct_option"].astype(str).str.strip().str.upper()

        # valida correct_option
        ok_mask = df["correct_option"].isin(["A", "B", "C", "D"])
        if not ok_mask.all():
            bad = df.loc[~ok_mask, ["correct_option"]].head(10)
            st.error("Trovate righe con correct_option non valido (deve essere A/B/C/D). Esempi:")
            st.dataframe(bad)
            st.stop()

        rows = df[required + ["explanation"]].to_dict(orient="records")

        try:
            sb.table("question_bank").insert(rows).execute()
            st.success(f"Caricate {len(rows)} domande ✅")
            st.rerun()
        except Exception as e:
            st.error("Errore inserimento in DB (question_bank).")
            st.exception(e)

    elif up and admin != ADMIN_CODE:
        st.warning("Codice docente errato.")


# =========================
# STUDENTE TAB
# =========================
with tab_stud:
    st.subheader("Accesso studente")

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
            except Exception as e:
                st.error("Errore accesso/DB (students).")
                st.exception(e)

    if not st.session_state.get("logged"):
        st.stop()

    student = st.session_state["student"]
    st.info(f"Connesso come: {student['nickname']} (classe {student['class_code']})")

    bank_count = fetch_bank_count()
    if bank_count < 30:
        st.warning(f"Banca dati troppo piccola: servono almeno 30 domande. Ora: {bank_count}")
        st.stop()

    st.divider()

    # impostazioni simulazione
    n_questions = 30
    duration_seconds = 30 * 60

    # =========================
    # START SIMULATION
    # =========================
    if not st.session_state["in_progress"] and not st.session_state["show_results"]:
        st.markdown("### Simulazione (30 domande – 30 minuti)")
        if st.button("Inizia simulazione"):
            try:
                # 1) crea sessione
                sess = create_session(student_id=student["id"], n_questions=n_questions, duration_seconds=duration_seconds)
                st.session_state["session_id"] = sess["id"]
                st.session_state["in_progress"] = True
                st.session_state["show_results"] = False
                st.session_state["answers"] = {}
                st.session_state["started_ts"] = time.time()

                # 2) estrai 30 random dalla banca
                all_q = fetch_all_bank_questions()
                picked = random.sample(all_q, n_questions)

                # 3) salva snapshot in quiz_answers per la sessione
                insert_session_questions(sess["id"], picked)

                st.success("Simulazione avviata ✅")
                st.rerun()
            except Exception as e:
                st.error("Errore avvio simulazione.")
                st.exception(e)
                st.session_state["in_progress"] = False
                st.stop()

    # =========================
    # IN PROGRESS
    # =========================
    if st.session_state["in_progress"]:
        session_id = st.session_state["session_id"]
        rows = fetch_session_questions(session_id)

        if not rows:
            st.error("Sessione senza domande in DB (quiz_answers vuota).")
            st.stop()

        # TIMER
        elapsed = int(time.time() - st.session_state["started_ts"])
        remaining = max(0, st.session_state["duration_seconds"] - elapsed)

        mm = remaining // 60
        ss = remaining % 60
        st.markdown(f"## ⏱️ Tempo residuo: **{mm:02d}:{ss:02d}**")

        progress = 1.0 - (remaining / st.session_state["duration_seconds"])
        st.progress(min(max(progress, 0.0), 1.0))

        if remaining <= 0:
            st.warning("Tempo scaduto! Correzione automatica in corso…")
            st.session_state["in_progress"] = False
            st.session_state["show_results"] = True
            finish_session(session_id)
            st.rerun()

        st.divider()
        st.markdown("## 📝 Sessione in corso")

        # render domande
        for idx, row in enumerate(rows, start=1):
            st.markdown(f"### Q{idx}")
            st.write(row["question_text"])

            options_map = {
                "A": row["option_a"],
                "B": row["option_b"],
                "C": row["option_c"],
                "D": row["option_d"],
            }

            # radio: opzioni = lettere A/B/C/D, così non sbaglia mai
            def fmt(letter: str) -> str:
                return f"{letter}) {options_map[letter]}"

            current = st.session_state["answers"].get(row["id"])  # lettera
            chosen = st.radio(
                "Seleziona risposta",
                options=["A", "B", "C", "D"],
                format_func=fmt,
                index=(["A", "B", "C", "D"].index(current) if current in ["A", "B", "C", "D"] else 0),
                key=f"row_{row['id']}",
                horizontal=False,
            )

            # salva in memoria + DB subito (così se refreshi non perdi)
            st.session_state["answers"][row["id"]] = chosen
            try:
                update_chosen_option(row_id=row["id"], session_id=session_id, chosen_letter=chosen)
            except Exception:
                pass

            st.divider()

        # termina manualmente
        if st.button("Termina simulazione e vedi correzione"):
            st.session_state["in_progress"] = False
            st.session_state["show_results"] = True
            finish_session(session_id)
            st.rerun()

    # =========================
    # RESULTS
    # =========================
    if st.session_state["show_results"]:
        session_id = st.session_state["session_id"]
        rows = fetch_session_questions(session_id)

        st.markdown("## ✅ Correzione finale")

        score = 0
        for idx, row in enumerate(rows, start=1):
            chosen = row.get("chosen_option")
            correct = row.get("correct_option")
            ok = (chosen == correct)

            if ok:
                score += 1

            st.markdown(f"### Q{idx} {'✅' if ok else '❌'}")
            st.write(row["question_text"])
            st.write(f"**Tua risposta:** {chosen or '-'}")
            st.write(f"**Corretta:** {correct}")
            if row.get("explanation"):
                st.caption(row["explanation"])
            st.divider()

        st.success(f"📌 Punteggio: **{score} / {len(rows)}**")
        st.success("Sessione salvata nel database ✅")

        if st.button("Nuova simulazione"):
            st.session_state["session_id"] = None
            st.session_state["in_progress"] = False
            st.session_state["show_results"] = False
            st.session_state["answers"] = {}
            st.session_state["started_ts"] = None
            st.rerun()



