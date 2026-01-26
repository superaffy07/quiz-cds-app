import os
import time
import random
from datetime import datetime, timezone
from typing import List, Dict, Optional

import streamlit as st
from supabase import create_client, Client

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Allenamento Quiz CDS", page_icon="🚓", layout="wide")

N_QUESTIONS = 30
DURATION_SECONDS = 30 * 60  # 30 minuti

# =========================
# SUPABASE
# =========================
def get_secret(name: str, default: str = "") -> str:
    # supporta sia secrets Streamlit che env
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

# =========================
# DB HELPERS
# =========================
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
    """
    Snapshot delle domande nella tabella quiz_answers (una riga per quiz).
    FIX: option_d non deve MAI essere NULL → se manca, stringa vuota.
    FIX: se option_d è vuota, la D non deve essere considerata corretta.
    """
    rows = []
    for q in questions:
        qa = (q.get("question_text") or "").strip()
        oa = (q.get("option_a") or "").strip()
        ob = (q.get("option_b") or "").strip()
        oc = (q.get("option_c") or "").strip()
        od = (q.get("option_d") or "").strip()  # può essere vuota

        co = (q.get("correct_option") or "").strip().upper()
        if co not in ["A", "B", "C", "D"]:
            co = "A"

        # se non esiste D, non può essere corretta
        if od == "" and co == "D":
            # fallback sicuro
            if oc:
                co = "C"
            elif ob:
                co = "B"
            else:
                co = "A"

        rows.append({
            "session_id": session_id,
            "topic_id": None,
            "question_text": qa,
            "option_a": oa,
            "option_b": ob,
            "option_c": oc,
            "option_d": od if od else "",   # <-- MAI NULL
            "correct_option": co,
            "chosen_option": None,
            "explanation": (q.get("explanation") or "").strip(),
        })

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

def update_chosen_option(row_id: int, session_id: str, chosen_letter: str) -> None:
    sb.table("quiz_answers").update({"chosen_option": chosen_letter}).eq("id", row_id).eq("session_id", session_id).execute()

# =========================
# SESSION STATE
# =========================
def ss_init():
    defaults = {
        "logged": False,
        "student": None,
        "session_id": None,
        "in_progress": False,
        "show_results": False,
        "started_ts": None,
        "duration_seconds": DURATION_SECONDS,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

ss_init()

# =========================
# UI
# =========================
st.title("🚓 Allenamento Quiz CDS")
st.caption("Simulazione: 30 domande random dalla banca dati. Timer 30 minuti. Correzione finale.")

tab_stud, tab_doc = st.tabs(["🎓 Studente", "🧑‍🏫 Docente (upload CSV)"])

# =========================
# DOCENTE
# =========================
with tab_doc:
    st.subheader("Carica banca dati (CSV)")

    st.write("CSV minimo: `question_text, option_a, option_b, option_c, option_d, correct_option` (+ opzionale `explanation`).")
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

        bad = ~df["correct_option"].isin(["A", "B", "C", "D"])
        if bad.any():
            st.error("Trovate righe con correct_option non valido (deve essere A/B/C/D).")
            st.dataframe(df.loc[bad, ["question_text", "correct_option"]].head(10))
            st.stop()

        bad_d = (df["option_d"].astype(str).str.strip() == "") & (df["correct_option"] == "D")
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

# =========================
# STUDENTE
# =========================
with tab_stud:
    st.subheader("Accesso studente")

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

    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("Logout"):
            # reset pulito
            st.session_state["logged"] = False
            st.session_state["student"] = None
            st.session_state["session_id"] = None
            st.session_state["in_progress"] = False
            st.session_state["show_results"] = False
            st.session_state["started_ts"] = None
            st.session_state["duration_seconds"] = DURATION_SECONDS
            st.rerun()

    bank_count = fetch_bank_count()
    st.write(f"📚 Domande in banca dati: **{bank_count}**")
    if bank_count < N_QUESTIONS:
        st.warning(f"Servono almeno {N_QUESTIONS} domande. Ora: {bank_count}")
        st.stop()

    st.divider()

    # 1) NON AVVIATA
    if not st.session_state["in_progress"] and not st.session_state["show_results"]:
        st.markdown("### Simulazione (30 domande – 30 minuti)")
        if st.button("Inizia simulazione"):
            try:
                sess = create_session(student_id=student["id"], n_questions=N_QUESTIONS)
                st.session_state["session_id"] = sess["id"]
                st.session_state["in_progress"] = True
                st.session_state["show_results"] = False
                st.session_state["started_ts"] = time.time()
                st.session_state["duration_seconds"] = DURATION_SECONDS

                all_q = fetch_all_bank_questions()
                picked = random.sample(all_q, N_QUESTIONS)

                insert_session_questions(sess["id"], picked)

                st.success("Simulazione avviata ✅")
                st.rerun()
            except Exception as e:
                st.error("Errore avvio simulazione.")
                st.exception(e)
                st.stop()

        st.stop()

    # 2) IN CORSO
    if st.session_state["in_progress"]:
        session_id = st.session_state["session_id"]
        rows = fetch_session_questions(session_id)

        if not rows:
            st.error("Sessione senza domande (quiz_answers vuota).")
            st.stop()

        elapsed = int(time.time() - float(st.session_state["started_ts"]))
        remaining = max(0, int(st.session_state["duration_seconds"]) - elapsed)

        mm = remaining // 60
        ss = remaining % 60
        st.markdown(f"## ⏱️ Tempo residuo: **{mm:02d}:{ss:02d}**")

        progress = 1.0 - (remaining / int(st.session_state["duration_seconds"]))
        st.progress(min(max(progress, 0.0), 1.0))

        if remaining <= 0:
            st.warning("Tempo scaduto! Correzione automatica…")
            st.session_state["in_progress"] = False
            st.session_state["show_results"] = True
            finish_session(session_id)
            st.rerun()

        st.divider()
        st.markdown("## 📝 Sessione in corso")

        for idx, row in enumerate(rows, start=1):
            st.markdown(f"### Q{idx}")
            st.write(row["question_text"])

            options_map = {
                "A": (row.get("option_a") or "").strip(),
                "B": (row.get("option_b") or "").strip(),
                "C": (row.get("option_c") or "").strip(),
                "D": (row.get("option_d") or "").strip(),
            }
            # mostra solo opzioni con testo
            letters = [k for k in ["A", "B", "C", "D"] if options_map[k] != ""]

            def fmt(letter: str) -> str:
                return f"{letter}) {options_map[letter]}"

            current = (row.get("chosen_option") or "").strip().upper()
            if current not in letters:
                current = None

            choice = st.radio(
                "Seleziona risposta",
                options=letters,
                index=(letters.index(current) if current in letters else 0),
                format_func=fmt,
                key=f"q_{row['id']}",
            )

            # salva immediatamente
            if choice and choice != row.get("chosen_option"):
                try:
                    update_chosen_option(row_id=row["id"], session_id=session_id, chosen_letter=choice)
                except Exception:
                    pass

            st.divider()

        if st.button("Termina simulazione e vedi correzione"):
            st.session_state["in_progress"] = False
            st.session_state["show_results"] = True
            finish_session(session_id)
            st.rerun()

        # ✅ TIMER LIVE: rerun interno (non perde login)
        time.sleep(1)
        st.rerun()

# 3) RISULTATI
if st.session_state["show_results"]:
    session_id = st.session_state["session_id"]
    rows = fetch_session_questions(session_id)

    st.markdown("## ✅ Correzione finale")

    # calcolo punteggio PRIMA (così lo mostri anche sopra)
    score = 0
    for row in rows:
        chosen = (row.get("chosen_option") or "").strip().upper()
        correct = (row.get("correct_option") or "").strip().upper()
        if chosen and chosen == correct:
            score += 1

    # PUNTEGGIO SOPRA
    st.success(f"📌 Punteggio: **{score} / {len(rows)}**")

    st.divider()

    def letter_to_text(row: dict, letter: str) -> str:
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

        st.markdown(f"### Q{idx} {'✅' if ok else '❌'}")
        st.write(row["question_text"])

        # Mostra LETTERA + TESTO (così capisci cosa hai selezionato)
        if chosen:
            st.write(f"**Tua risposta:** {chosen}) {chosen_text}")
        else:
            st.write("**Tua risposta:** — (non risposta)")

        st.write(f"**Corretta:** {correct}) {correct_text}")

        if row.get("explanation"):
            st.caption(row["explanation"])

        st.divider()

    # PUNTEGGIO SOTTO (lo lasciamo anche qui)
    st.success(f"📌 Punteggio: **{score} / {len(rows)}**")

    if st.button("Nuova simulazione"):
        st.session_state["session_id"] = None
        st.session_state["in_progress"] = False
        st.session_state["show_results"] = False
        st.session_state["started_ts"] = None
        st.session_state["duration_seconds"] = DURATION_SECONDS
        st.rerun()

