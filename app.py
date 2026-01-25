import os
import io
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
# HELPERS (DB)
# =========================
def upsert_student(class_code: str, nickname: str) -> dict:
    """
    Crea o aggiorna studente (class_code+nickname).
    Tabella attesa: students(id, class_code, nickname, created_at)
    """
    class_code = class_code.strip()
    nickname = nickname.strip()

    # prova a cercare
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

    # inserisci nuovo
    ins = (
        sb.table("students")
        .insert({"class_code": class_code, "nickname": nickname})
        .execute()
    )
    return ins.data[0]


def fetch_topics() -> list[dict]:
    """
    Tabella attesa: topics(id, materia, argomento, fonte_testo, difficolta, tags, created_at)
    """
    res = sb.table("topics").select("*").order("id").execute()
    return res.data or []


def create_session(student_id: str, topic_scope: str, selected_topic_id: int | None, n_questions: int, mode: str) -> dict:
    """
    Tabella attesa: sessions(id, student_id, mode, topic_scope, selected_topic_id, n_questions, created_at)
    id può essere UUID generato dal DB
    """
    payload = {
        "student_id": student_id,
        "mode": mode,  # "quiz" oppure "mix"
        "topic_scope": topic_scope,  # "single" / "all"
        "selected_topic_id": selected_topic_id,
        "n_questions": int(n_questions),
    }
    res = sb.table("sessions").insert(payload).execute()
    return res.data[0]


def insert_quiz_answers_batch(rows: list[dict]) -> None:
    """
    Tabella attesa: quiz_answers(
        id, session_id, topic_id, question_text,
        option_a, option_b, option_c, option_d,
        correct_option, chosen_option, explanation,
        created_at
    )
    """
    if not rows:
        return
    sb.table("quiz_answers").insert(rows).execute()


def fetch_quiz_answers(session_id: str) -> list[dict]:
    res = (
        sb.table("quiz_answers")
        .select("*")
        .eq("session_id", session_id)
        .order("id")
        .execute()
    )
    return res.data or []


def update_chosen_option(session_id: str, row_id: int, chosen: str | None) -> None:
    sb.table("quiz_answers").update({"chosen_option": chosen}).eq("id", row_id).eq("session_id", session_id).execute()


# =========================
# GENERATION (NO AI) - semplice ma stabile
# =========================
def build_mcq_from_source(argomento: str, fonte_testo: str) -> tuple[str, list[str], str, str]:
    """
    Crea una domanda MCQ "ragionata" usando argomento + fonte_testo (se c'è).
    Ritorna: question, options[4], correct_letter(A-D), explanation
    """
    base = argomento.strip()
    src = (fonte_testo or "").strip()

    question = f"In base a quanto previsto per: **{base}**, qual è l’affermazione più corretta?"
    correct = f"È corretta l’applicazione pratica coerente con {base}."
    distractors = [
        f"Si applica sempre il contrario di {base}, senza eccezioni.",
        f"{base} vale solo se non esistono ordinanze o regolamenti locali.",
        f"{base} non prevede mai conseguenze sanzionatorie.",
    ]

    options = [correct] + distractors
    random.shuffle(options)
    correct_letter = "ABCD"[options.index(correct)]

    expl = f"La risposta corretta è quella coerente con {base}."
    if src:
        expl += " (Derivata dal testo caricato.)"

    return question, options, correct_letter, expl


def build_practical_case(argomento: str) -> str:
    return (
        f"Caso pratico su **{argomento}**:\n\n"
        "Descrivi in 5-8 righe come applicheresti la norma in un caso concreto, "
        "indicando: (1) fatto, (2) valutazione, (3) azione operativa, (4) eventuale sanzione/atto."
    )


# =========================
# STATE INIT
# =========================
if "logged" not in st.session_state:
    st.session_state["logged"] = False
if "student" not in st.session_state:
    st.session_state["student"] = None
if "in_progress" not in st.session_state:
    st.session_state["in_progress"] = False
if "session_id" not in st.session_state:
    st.session_state["session_id"] = None
if "quiz_items" not in st.session_state:
    st.session_state["quiz_items"] = []
if "answers" not in st.session_state:
    st.session_state["answers"] = {}
if "case_prompt" not in st.session_state:
    st.session_state["case_prompt"] = None
if "case_answer" not in st.session_state:
    st.session_state["case_answer"] = ""


# =========================
# UI
# =========================
st.title("🚓 Allenamento Quiz CDS")
st.caption("Correzione solo a fine sessione. Sessione e domande salvate in database.")

tab_stud, tab_doc = st.tabs(["🎓 Studente", "🧰 Docente (carica argomenti)"])


# =========================
# DOCENTE
# =========================
with tab_doc:
    st.subheader("Carica un CSV con colonne: materia, argomento, fonte_testo, difficolta, tags")

    admin = st.text_input("Codice docente", type="password")
    up = st.file_uploader("Carica CSV argomenti", type=["csv"])

    if up and admin == ADMIN_CODE:
        data_bytes = up.getvalue()

        # robust read: utf-8-sig -> utf-8 -> latin1
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

        required = ["materia", "argomento", "fonte_testo", "difficolta", "tags"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            st.error(f"Mancano colonne: {missing}")
            st.stop()

        df = df[required].fillna("")
        rows = df.to_dict(orient="records")

        try:
            sb.table("topics").insert(rows).execute()
            st.success("Argomenti caricati nel database ✅")
        except Exception as e:
            st.error("Errore inserimento in DB (topics).")
            st.exception(e)

    elif up and admin != ADMIN_CODE:
        st.warning("Codice docente errato.")


# =========================
# STUDENTE
# =========================
with tab_stud:
    st.subheader("Accesso studente")

    class_code = st.text_input("Codice classe (decidi tu, es. CDS2026)")
    nickname = st.text_input("Nickname (es. Mirko)")

    colA, colB = st.columns([1, 2])
    with colA:
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

    if st.session_state.get("logged"):
        student = st.session_state["student"]
        st.info(f"Connesso come: {student['nickname']} (classe {student['class_code']})")

        topics = fetch_topics()
        if not topics:
            st.warning("Nessun argomento in database. Vai in 'Docente' e carica il CSV.")
            st.stop()

        scope = st.radio("Allenamento su:", ["Tutti gli argomenti", "Un solo argomento"], horizontal=True)

        if scope == "Un solo argomento":
            labels = [f"{t['id']} - {t['argomento']}" for t in topics]
            chosen = st.selectbox("Seleziona argomento", labels)
            chosen_id = int(chosen.split(" - ")[0])
            selected_topics = [t for t in topics if int(t["id"]) == chosen_id]
            topic_scope = "single"
            selected_topic_id = chosen_id
        else:
            selected_topics = topics
            topic_scope = "all"
            selected_topic_id = None

        n_questions = st.slider("Numero quiz (multiple choice)", 5, 30, 10)
        include_case = st.checkbox("Includi anche 1 caso praticico (a fine sessione)", value=True)

        # =========================
        # START SESSION
        # =========================
        if st.button("Inizia sessione", disabled=st.session_state.get("in_progress", False)):
            try:
                # 1) crea sessione
                mode = "mix" if include_case else "quiz"
                sess = create_session(
                    student_id=student["id"],
                    topic_scope=topic_scope,
                    selected_topic_id=selected_topic_id,
                    n_questions=int(n_questions),
                    mode=mode,
                )

                st.session_state["session_id"] = sess["id"]
                st.session_state["quiz_items"] = []
                st.session_state["answers"] = {}
                st.session_state["case_prompt"] = None
                st.session_state["case_answer"] = ""
                st.session_state["in_progress"] = True

                # 2) genera domande in memoria + prepara batch insert DB
                batch_rows = []
                for _ in range(int(n_questions)):
                    t = random.choice(selected_topics)
                    q, opts, correct, expl = build_mcq_from_source(t["argomento"], t.get("fonte_testo", ""))

                    item = {
                        "session_id": sess["id"],
                        "topic_id": t["id"],
                        "question_text": q,
                        "option_a": opts[0],
                        "option_b": opts[1],
                        "option_c": opts[2],
                        "option_d": opts[3],
                        "correct_option": correct,
                        "chosen_option": None,
                        "explanation": expl,
                    }
                    batch_rows.append(item)

                    # per UI immediata
                    st.session_state["quiz_items"].append(item.copy())

                # 3) caso pratico (solo in UI)
                if include_case:
                    tcase = random.choice(selected_topics)
                    st.session_state["case_prompt"] = build_practical_case(tcase["argomento"])

                # 4) salva in DB in batch
                insert_quiz_answers_batch(batch_rows)

                st.success("Sessione avviata ✅ Domande generate e salvate.")
                st.rerun()

            except Exception as e:
                st.error("Errore avvio sessione (sessions/quiz_answers).")
                st.exception(e)
                st.session_state["in_progress"] = False

        st.divider()

        # =========================
        # SESSION IN PROGRESS (UI from memory)
        # =========================
        if st.session_state.get("in_progress"):
            st.markdown("## Sessione in corso (correzione alla fine)")

            quiz_items = st.session_state.get("quiz_items", [])
            if not quiz_items:
                st.warning("Quiz vuoto: non risultano domande generate in memoria.")
            else:
                for idx, item in enumerate(quiz_items, start=1):
                    st.markdown(f"### Q{idx}")
                    st.markdown(item["question_text"])

                    options_map = {
                        "A": item["option_a"],
                        "B": item["option_b"],
                        "C": item["option_c"],
                        "D": item["option_d"],
                    }

                    # label leggibili
                    labels = [f"{k}) {v}" for k, v in options_map.items()]
                    default_choice = st.session_state["answers"].get(idx)

                    selected_label = st.radio(
                        "Seleziona risposta",
                        labels,
                        index=(labels.index(default_choice) if default_choice in labels else 0),
                        key=f"q_{idx}",
                    )

                    st.session_state["answers"][idx] = selected_label
                    st.divider()

            if st.session_state.get("case_prompt"):
                st.markdown("## Caso pratico (rispondi in modo sintetico ma completo)")
                st.write(st.session_state["case_prompt"])
                st.session_state["case_answer"] = st.text_area(
                    "Risposta:",
                    value=st.session_state.get("case_answer", ""),
                    height=140,
                )

            # =========================
            # END SESSION
            # =========================
            if st.button("Termina sessione e vedi correzione"):
                session_id = st.session_state["session_id"]

                try:
                    db_rows = fetch_quiz_answers(session_id)

                    if not db_rows:
                        st.error("In DB non risultano domande per questa sessione (quiz_answers vuoto).")
                        st.stop()

                    score = 0
                    st.markdown("## ✅ Correzione (fine sessione)")

                    # salva chosen_option in DB + calcola score
                    for i, row in enumerate(db_rows, start=1):
                        chosen_label = st.session_state["answers"].get(i)
                        chosen_letter = None
                        if chosen_label and isinstance(chosen_label, str) and ")" in chosen_label:
                            chosen_letter = chosen_label.split(")")[0].strip()

                        update_chosen_option(session_id, row["id"], chosen_letter)

                        correct = row["correct_option"]
                        ok = (chosen_letter == correct)
                        if ok:
                            score += 1

                        st.markdown(f"### Q{i} {'✅' if ok else '❌'}")
                        st.write(row["question_text"])
                        st.write(f"**Tua risposta:** {chosen_letter or '-'}")
                        st.write(f"**Corretta:** {correct}")
                        st.write(row.get("explanation", ""))

                    st.success(f"Punteggio quiz: **{score} / {len(db_rows)}**")
                    st.success("Sessione salvata nel database ✅")

                    # reset stato
                    st.session_state["in_progress"] = False
                    st.session_state["quiz_items"] = []
                    st.session_state["answers"] = {}
                    st.session_state["case_prompt"] = None
                    st.session_state["case_answer"] = ""

                except Exception as e:
                    st.error("Errore in correzione/fetch DB.")
                    st.exception(e)


