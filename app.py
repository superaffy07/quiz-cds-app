import os
import time
import random
from typing import List, Dict, Optional

import streamlit as st
from supabase import create_client, Client


# =========================
# CONFIG
# =========================
st.set_page_config(page_title="ESERCITAZIONE CORSO POLIZIA LOCALE", page_icon="🚓", layout="wide")

# Durata simulazione
N_QUESTIONS_DEFAULT = 30
DURATION_SECONDS_DEFAULT = 30 * 60  # 30 minuti

# =========================
# SUPABASE INIT
# =========================
def get_supabase() -> Client:
    # prima prova da Streamlit secrets, poi da env
    url = None
    key = None

    if hasattr(st, "secrets"):
        url = st.secrets.get("SUPABASE_URL", None)
        key = st.secrets.get("SUPABASE_ANON_KEY", None)

    url = url or os.getenv("SUPABASE_URL")
    key = key or os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        st.error("Mancano SUPABASE_URL / SUPABASE_ANON_KEY (secrets o env).")
        st.stop()

    return create_client(url, key)


sb = get_supabase()


# =========================
# DB HELPERS
# =========================
def upsert_student(class_code: str, nickname: str) -> Dict:
    class_code = class_code.strip()
    nickname = nickname.strip()

    # prova a leggere se esiste
    existing = (
        sb.table("students")
        .select("*")
        .eq("class_code", class_code)
        .eq("nickname", nickname)
        .limit(1)
        .execute()
        .data
    )
    if existing:
        return existing[0]

    # altrimenti inserisci
    inserted = (
        sb.table("students")
        .insert({"class_code": class_code, "nickname": nickname})
        .execute()
        .data
    )
    return inserted[0]


def create_session(student_id: int, n_questions: int) -> Dict:
    payload = {
        "student_id": student_id,
        "mode": "sim",
        "topic_scope": "bank",
        "selected_topic_id": None,
        "n_questions": int(n_questions),
    }
    sess = sb.table("sessions").insert(payload).execute().data[0]
    return sess


def finish_session(session_id: str) -> None:
    sb.table("sessions").update({"finished_at": "now()"}).eq("id", session_id).execute()


def fetch_bank_count() -> int:
    # supabase count exact
    res = sb.table("question_bank").select("id", count="exact").execute()
    return int(res.count or 0)


def fetch_all_bank_questions() -> List[Dict]:
    # scarica tutte (per 1000+ va paginato, ma per ora ok)
    res = sb.table("question_bank").select("*").execute().data
    return res or []


def insert_session_questions(session_id: str, questions: List[Dict]) -> None:
    rows = []
    for q in questions:
        # normalizza opzioni
        oa = (q.get("option_a") or "").replace("\xa0", " ").strip()
        ob = (q.get("option_b") or "").replace("\xa0", " ").strip()
        oc = (q.get("option_c") or "").replace("\xa0", " ").strip()
        od = (q.get("option_d") or "").replace("\xa0", " ").strip()  # può essere vuota

        correct = (q.get("correct_option") or "").strip().upper()
        if correct not in ["A", "B", "C", "D"]:
            # se il CSV è sporco, prova a recuperare
            correct = "A"

        # IMPORTANTISSIMO: quiz_answers.option_d è NOT NULL nel tuo schema
        # quindi se non c'è D, metti stringa vuota "" (non None)
        rows.append(
            {
                "session_id": session_id,
                "topic_id": None,
                "question_text": (q.get("question_text") or q.get("testo_della_domanda") or "").strip(),
                "option_a": oa,
                "option_b": ob,
                "option_c": oc,
                "option_d": od if od else "",  # mai NULL
                "correct_option": correct,     # A/B/C/D
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


def update_chosen_option(row_id: int, chosen: str) -> None:
    sb.table("quiz_answers").update({"chosen_option": chosen}).eq("id", row_id).execute()


# =========================
# SESSION STATE DEFAULTS
# =========================
if "logged" not in st.session_state:
    st.session_state["logged"] = False

if "student" not in st.session_state:
    st.session_state["student"] = None

if "in_progress" not in st.session_state:
    st.session_state["in_progress"] = False

if "show_results" not in st.session_state:
    st.session_state["show_results"] = False

if "session_id" not in st.session_state:
    st.session_state["session_id"] = None

if "started_ts" not in st.session_state:
    st.session_state["started_ts"] = None

if "duration_seconds" not in st.session_state:
    st.session_state["duration_seconds"] = DURATION_SECONDS_DEFAULT


# =========================
# UI
# =========================
st.title("🚓 ESERCITAZIONE CORSO POLIZIA LOCALE")
st.caption("Simulazione 30 domande / 30 minuti. Correzione alla fine. Tutto salvato su Supabase.")

tab_stud, tab_doc = st.tabs(["🎓 Studente", "🛠️ Docente (info)"])


with tab_doc:
    st.subheader("Docente")
    st.write(
        "Per ora il caricamento banca dati lo fai da Supabase (Table Editor → Import CSV). "
        "Se vuoi, dopo automatizziamo un upload direttamente da app."
    )
    st.info("Suggerimento: usa la tabella `question_bank` come banca dati unica.")


with tab_stud:
    st.subheader("Accesso studente")

    if not st.session_state["logged"]:
        class_code = st.text_input("Codice classe (es. CDS2026)")
        nickname = st.text_input("Nickname (es. Mirko)")

        col1, col2 = st.columns([1, 3])
        with col1:
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
                        st.error("Errore accesso/DB (students).")
                        st.exception(e)
        st.stop()

    # LOGGATO
    student = st.session_state["student"]
    st.success("Accesso OK ✅")
    st.info(f"Connesso come: {student['nickname']} (classe {student['class_code']})")

    col_logout, col_space = st.columns([1, 6])
    with col_logout:
        if st.button("Logout"):
            # reset pulito
            st.session_state["logged"] = False
            st.session_state["student"] = None
            st.session_state["in_progress"] = False
            st.session_state["show_results"] = False
            st.session_state["session_id"] = None
            st.session_state["started_ts"] = None
            st.rerun()

    # controlla banca dati
    bank_count = fetch_bank_count()
    st.write(f"📚 Domande in banca dati: **{bank_count}**")

    if bank_count < N_QUESTIONS_DEFAULT:
        st.warning(f"Servono almeno {N_QUESTIONS_DEFAULT} domande in `question_bank`. Ora: {bank_count}")
        st.stop()

    st.divider()

    # =========================
    # STATO 1: NON AVVIATA
    # =========================
    if not st.session_state["in_progress"] and not st.session_state["show_results"]:
        st.markdown("### Simulazione (30 domande – 30 minuti)")

        if st.button("Inizia simulazione"):
            try:
                n_questions = N_QUESTIONS_DEFAULT
                duration_seconds = DURATION_SECONDS_DEFAULT

                sess = create_session(student_id=student["id"], n_questions=n_questions)
                st.session_state["session_id"] = sess["id"]
                st.session_state["in_progress"] = True
                st.session_state["show_results"] = False
                st.session_state["started_ts"] = time.time()
                st.session_state["duration_seconds"] = duration_seconds

                all_q = fetch_all_bank_questions()
                picked = random.sample(all_q, n_questions)

                insert_session_questions(sess["id"], picked)

                st.success("Simulazione avviata ✅")
                st.rerun()

            except Exception as e:
                st.error("Errore avvio simulazione.")
                st.exception(e)
                st.session_state["in_progress"] = False
                st.stop()

        st.stop()

    # =========================
    # STATO 2: IN CORSO
    # =========================
    if st.session_state["in_progress"]:
        session_id = st.session_state["session_id"]
        rows = fetch_session_questions(session_id)

        if not rows:
            st.error("Sessione senza domande in DB (quiz_answers vuota).")
            st.stop()

        elapsed = int(time.time() - float(st.session_state["started_ts"]))
        remaining = max(0, int(st.session_state["duration_seconds"]) - elapsed)

        mm = remaining // 60
        ss = remaining % 60

        st.markdown(f"## ⏱️ Tempo residuo: **{mm:02d}:{ss:02d}**")
        progress = 1.0 - (remaining / int(st.session_state["duration_seconds"]))
        st.progress(min(max(progress, 0.0), 1.0))

        if remaining <= 0:
            st.warning("Tempo scaduto! Correzione automatica in corso…")
            st.session_state["in_progress"] = False
            st.session_state["show_results"] = True
            finish_session(session_id)
            st.rerun()

        st.divider()
        st.markdown("## 📝 Sessione in corso")

        for idx, row in enumerate(rows, start=1):
            st.markdown(f"### Q{idx}")
            st.write(row["question_text"])

            # normalizza: se D vuota/non esiste → non mostrarla
            options_map = {
                "A": (row.get("option_a") or "").replace("\xa0", " ").strip(),
                "B": (row.get("option_b") or "").replace("\xa0", " ").strip(),
                "C": (row.get("option_c") or "").replace("\xa0", " ").strip(),
                "D": (row.get("option_d") or "").replace("\xa0", " ").strip(),
            }

            letters = []
            for k in ["A", "B", "C", "D"]:
                if options_map.get(k, "").strip() != "":
                    letters.append(k)

            def fmt(letter: str) -> str:
                return f"{letter}) {options_map[letter]}"

            current = row.get("chosen_option")
            if current not in letters:
                current = None

            choice = st.radio(
                "Seleziona risposta",
                options=letters,
                index=letters.index(current) if current in letters else 0,
                format_func=fmt,
                key=f"q_{row['id']}",
            )

            # salva risposta subito (così non perdi nulla se aggiorna il timer)
            if choice and choice != row.get("chosen_option"):
                try:
                    update_chosen_option(row["id"], choice)
                except Exception:
                    pass

            st.divider()

        if st.button("Termina simulazione e vedi correzione"):
            st.session_state["in_progress"] = False
            st.session_state["show_results"] = True
            finish_session(session_id)
            st.rerun()

        # ✅ TIMER “LIVE” SENZA RELOAD (questa parte risolve il tuo problema login)
        time.sleep(1)
        st.rerun()

    # =========================
    # STATO 3: RISULTATI
    # =========================
    if st.session_state["show_results"]:
        session_id = st.session_state["session_id"]
        rows = fetch_session_questions(session_id)

        st.markdown("## ✅ Correzione (fine simulazione)")

        score = 0
        total = 0

        for idx, row in enumerate(rows, start=1):
            correct = (row.get("correct_option") or "").strip().upper()
            chosen = (row.get("chosen_option") or "").strip().upper()

            total += 1
            ok = (chosen == correct)
            if ok:
                score += 1

            st.markdown(f"### Q{idx}")
            st.write(row["question_text"])
            st.write(f"**Risposta data:** {chosen or '—'}")
            st.write(f"**Corretta:** {correct}")
            st.write("✅ Esatta" if ok else "❌ Sbagliata")
            st.divider()

        st.success(f"📌 Punteggio finale: **{score} / {total}**")

        if st.button("Nuova simulazione"):
            st.session_state["in_progress"] = False
            st.session_state["show_results"] = False
            st.session_state["session_id"] = None
            st.session_state["started_ts"] = None
            st.rerun()
