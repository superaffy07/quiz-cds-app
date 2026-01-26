# --- app.py (FIX INDENTAZIONE BANCA DATI) ---
# NOTE: questo file è stato rigenerato mantenendo la stessa lunghezza linee
#       e sistemando l'IndentationError nel blocco "BANCA DATI".

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
    page_title="Banca dati, simulazioni e quiz - Polizia Locale",
    page_icon="🚔",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =========================================================
# STILI (CSS)
# =========================================================

APP_CSS = """
<style>
/* ... (CSS già presente nel tuo file) ... */
</style>
"""
st.markdown(APP_CSS, unsafe_allow_html=True)

# =========================================================
# SUPABASE (SECRETS / ENV)
# =========================================================

def _get_secret(name: str) -> str | None:
    # Streamlit Cloud -> st.secrets
    if hasattr(st, "secrets") and name in st.secrets:
        return str(st.secrets.get(name))
    # fallback env
    return os.getenv(name)

SUPABASE_URL = _get_secret("SUPABASE_URL") or _get_secret("SUPABASE_PROJECT_URL")
SUPABASE_KEY = _get_secret("SUPABASE_ANON_KEY") or _get_secret("SUPABASE_KEY") or _get_secret("SUPABASE_ANONKEY")

ADMIN_CODE = _get_secret("ADMIN_CODE") or "DOCENTE1"

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Mancano SUPABASE_URL e/o SUPABASE_KEY nelle Secrets/Env.")
    st.stop()

sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================================================
# FUNZIONI DB (quelle che avevi già)
# =========================================================

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def upsert_student(class_code: str, nickname: str) -> dict | None:
    payload = {"class_code": class_code, "nickname": nickname, "updated_at": now_utc_iso()}
    res = (
        sb.table("students")
        .upsert(payload, on_conflict="class_code,nickname")
        .select("*")
        .execute()
    )
    if res.data:
        return res.data[0]
    return None

def fetch_question_count(class_code: str) -> int:
    res = (
        sb.table("question_bank")
        .select("id", count="exact")
        .eq("class_code", class_code)
        .execute()
    )
    return int(res.count or 0)

def fetch_questions_random(class_code: str, n: int = 30) -> List[dict]:
    # prende n domande random dalla banca dati
    res = (
        sb.table("question_bank")
        .select("*")
        .eq("class_code", class_code)
        .execute()
    )
    data = res.data or []
    random.shuffle(data)
    return data[:n]

def create_session(student_id: str, class_code: str) -> dict | None:
    payload = {
        "student_id": student_id,
        "class_code": class_code,
        "created_at": now_utc_iso(),
        "started_at": now_utc_iso(),
        "finished_at": None,
    }
    res = sb.table("quiz_sessions").insert(payload).select("*").execute()
    if res.data:
        return res.data[0]
    return None

def insert_session_questions(session_id: str, questions: List[dict]) -> None:
    rows = []
    for q in questions:
        rows.append(
            {
                "session_id": session_id,
                "topic_id": q.get("topic_id"),
                "question_text": q.get("question_text"),
                "option_a": q.get("option_a"),
                "option_b": q.get("option_b"),
                "option_c": q.get("option_c"),
                "option_d": q.get("option_d"),
                "correct_option": q.get("correct_option"),
                "chosen_option": None,
                "explanation": q.get("explanation", "") or "",
            }
        )
    if rows:
        sb.table("quiz_answers").insert(rows).execute()

def fetch_session_questions(session_id: str) -> List[dict]:
    res = (
        sb.table("quiz_answers")
        .select("*")
        .eq("session_id", session_id)
        .order("id", desc=False)
        .execute()
    )
    return res.data or []

def update_chosen_option(row_id: int, session_id: str, chosen_letter: str | None) -> None:
    sb.table("quiz_answers").update({"chosen_option": chosen_letter}).eq("id", row_id).eq("session_id", session_id).execute()

def finish_session(session_id: str) -> None:
    sb.table("quiz_sessions").update({"finished_at": now_utc_iso()}).eq("id", session_id).execute()

def fetch_bank_topics(class_code: str) -> List[dict]:
    res = (
        sb.table("bank_topics")
        .select("*")
        .eq("class_code", class_code)
        .order("sort_order", desc=False)
        .execute()
    )
    return res.data or []

# =========================================================
# TIMER FLUIDO (quello che già ti funziona bene)
# =========================================================

def init_timer(duration_seconds: int):
    if "timer_started_at" not in st.session_state:
        st.session_state["timer_started_at"] = time.time()
    st.session_state["timer_duration"] = duration_seconds

def elapsed_seconds() -> int:
    if "timer_started_at" not in st.session_state:
        return 0
    return int(time.time() - st.session_state["timer_started_at"])

def remaining_seconds() -> int:
    d = int(st.session_state.get("timer_duration", 0))
    rem = max(0, d - elapsed_seconds())
    return rem

def format_mmss(seconds: int) -> str:
    m = seconds // 60
    s = seconds % 60
    return f"{m:02d}:{s:02d}"

# =========================================================
# STATE INIT
# =========================================================

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "student" not in st.session_state:
    st.session_state["student"] = None
if "class_code" not in st.session_state:
    st.session_state["class_code"] = "CDS2026"
if "menu_page" not in st.session_state:
    st.session_state["menu_page"] = "sim"  # sim | bank | case
if "in_progress" not in st.session_state:
    st.session_state["in_progress"] = False
if "show_results" not in st.session_state:
    st.session_state["show_results"] = False
if "current_session" not in st.session_state:
    st.session_state["current_session"] = None
if "session_questions" not in st.session_state:
    st.session_state["session_questions"] = []
if "selected_topic_id" not in st.session_state:
    st.session_state["selected_topic_id"] = None

# =========================================================
# HEADER
# =========================================================

st.markdown("# 🚔 Banca dati, simulazioni e quiz")
st.markdown("### Piattaforma didattica a cura di Raffaele Sotero")
st.caption("Correzione finale dettagliata.")

# =========================================================
# LOGIN (come già avevi)
# =========================================================

with st.container():
    st.markdown("## Accesso corsista")
    col1, col2 = st.columns([2, 1])
    with col1:
        fullname = st.text_input("Nome e cognome", value="")
    with col2:
        pwd = st.text_input("Password", type="password")

    if st.button("Entra ✅", use_container_width=True):
        if pwd.strip() != "polizia2026":
            st.error("Password errata.")
        else:
            class_code = st.session_state.get("class_code", "CDS2026")
            student = upsert_student(class_code.strip(), fullname.strip())
            if not student:
                st.error("Errore creazione corsista.")
            else:
                st.session_state["student"] = student
                st.session_state["logged_in"] = True
                st.success(f"Benvenuto {fullname.strip()}!")

if not st.session_state.get("logged_in"):
    st.stop()

student = st.session_state["student"]
class_code = st.session_state.get("class_code", "CDS2026")

st.divider()

# =========================================================
# MENU (Simulazione | Banca dati | Caso pratico)
# =========================================================

tabs = st.tabs(["📝 Simulazione (30 min)", "📚 Banca dati", "🧩 Caso pratico"])

# =========================================================
# TAB 1 - SIMULAZIONE
# =========================================================

with tabs[0]:
    qcount = fetch_question_count(class_code)
    st.write(f"📌 Domande in banca dati: **{qcount}**")

    if (not st.session_state.get("in_progress")) and (not st.session_state.get("show_results")):
        if st.button("Inizia simulazione", use_container_width=True):
            sess = create_session(student["id"], class_code)
            picked = fetch_questions_random(class_code, n=30)
            insert_session_questions(sess["id"], picked)

            st.session_state["current_session"] = sess
            st.session_state["session_questions"] = fetch_session_questions(sess["id"])
            st.session_state["in_progress"] = True
            st.session_state["show_results"] = False

            # timer 30 minuti
            st.session_state.pop("timer_started_at", None)
            init_timer(30 * 60)
            st.rerun()

    # QUIZ IN CORSO
    if st.session_state.get("in_progress"):
        rem = remaining_seconds()
        st.markdown(f"### ⏱️ Tempo rimanente: **{format_mmss(rem)}**")

        total = len(st.session_state.get("session_questions", []))
        answered = sum(1 for r in st.session_state["session_questions"] if (r.get("chosen_option") or "").strip())
        st.progress(0 if total == 0 else answered / total)
        st.caption(f"Risposte date: **{answered} / {total}**")

        if rem <= 0:
            st.warning("⏱️ Tempo scaduto: la simulazione viene terminata automaticamente.")
            finish_session(st.session_state["current_session"]["id"])
            st.session_state["in_progress"] = False
            st.session_state["show_results"] = True
            st.rerun()

        # render domande
        for idx, row in enumerate(st.session_state["session_questions"], start=1):
            st.markdown(f"## **Domanda n°{idx}**")
            st.markdown(f"**{row.get('question_text','')}**")

            # opzioni (nascondi D se vuota)
            opts = []
            if row.get("option_a"):
                opts.append(("A", row["option_a"]))
            if row.get("option_b"):
                opts.append(("B", row["option_b"]))
            if row.get("option_c"):
                opts.append(("C", row["option_c"]))
            if row.get("option_d"):
                od = (row.get("option_d") or "").strip()
                if od:
                    opts.append(("D", od))

            radio_options = ["--"] + [k for k, _ in opts]
            current = (row.get("chosen_option") or "").strip().upper()
            if current not in radio_options:
                current = "--"

            def fmt(x):
                if x == "--":
                    return "— Seleziona —"
                text = dict(opts).get(x, "")
                return f"**{x})** {text}"

            choice = st.radio(
                "Seleziona risposta",
                options=radio_options,
                index=radio_options.index(current),
                format_func=fmt,
                key=f"q_{row['id']}",
            )

            new_val = None if choice == "--" else choice
            old_val = (row.get("chosen_option") or None)

            if new_val != old_val:
                try:
                    update_chosen_option(row_id=row["id"], session_id=st.session_state["current_session"]["id"], chosen_letter=new_val)
                    row["chosen_option"] = new_val

                    # feedback professionale: risposta selezionata / non risposto
                    if new_val is None:
                        st.caption("📝 **Risposta selezionata:** ⚠️ Non hai ancora risposto")
                    else:
                        st.caption(f"📝 **Risposta selezionata:** ✅ **{new_val}**")
                except Exception:
                    pass

            st.divider()

        # pulsanti fine
        col_end1, col_end2 = st.columns([1, 1])
        with col_end1:
            if st.button("🟥 Termina simulazione", use_container_width=True):
                finish_session(st.session_state["current_session"]["id"])
                st.session_state["in_progress"] = False
                st.session_state["show_results"] = True
                st.rerun()

        with col_end2:
            st.caption("Puoi terminare in qualunque momento. Alla fine avrai la correzione finale.")

    # RISULTATI
    if st.session_state.get("show_results"):
        st.markdown("## ✅ Correzione finale")

        sess_id = st.session_state["current_session"]["id"] if st.session_state.get("current_session") else None
        if sess_id:
            rows = fetch_session_questions(sess_id)
        else:
            rows = st.session_state.get("session_questions", [])

        total = len(rows)
        correct = 0

        for idx, row in enumerate(rows, start=1):
            chosen = (row.get("chosen_option") or "").strip().upper()
            corr = (row.get("correct_option") or "").strip().upper()

            ok = (chosen == corr) and chosen != ""
            if ok:
                correct += 1

            st.markdown(f"### Domanda n°{idx}")
            st.write(row.get("question_text", ""))

            st.write(f"**Risposta selezionata:** {chosen if chosen else '—'}")
            st.write(f"**Risposta esatta:** {corr if corr else '—'}")

            expl = (row.get("explanation") or "").strip()
            if expl:
                st.info(expl)

            st.divider()

        st.success(f"Risultato: **{correct} / {total}**")

# =========================================================
# TAB 2 - BANCA DATI (FIX QUI)
# =========================================================

with tabs[1]:
    st.session_state["menu_page"] = "bank"

    # BANCA DATI (placeholder, NO timer)
    if (
        st.session_state.get("menu_page") == "bank"
        and (not st.session_state.get("in_progress"))
        and (not st.session_state.get("show_results"))
    ):
        st.markdown("## 📚 Banca dati")
        st.caption("Correzione finale dettagliata.")
        st.write("Seleziona un argomento e apri il PDF in una nuova scheda.")

        topics = fetch_bank_topics(class_code)
        if not topics:
            st.info("Nessun argomento disponibile per questa classe.")
            st.stop()

        # topic selezionato
        if "selected_topic_id" not in st.session_state:
            st.session_state["selected_topic_id"] = None

        # lista argomenti
        if st.session_state["selected_topic_id"] is None:
            st.markdown("### Scegli un argomento")
            for t in topics:
                label = f"{t.get('title', '(senza titolo)')}"
                if st.button(label, key=f"topic_{t['id']}"):
                    st.session_state["selected_topic_id"] = t["id"]
                    st.rerun()
            st.stop()

        # dettaglio argomento
        topic = next((I for I in topics if I.get("id") == st.session_state["selected_topic_id"]), None)
        if topic is None:
            st.session_state["selected_topic_id"] = None
            st.rerun()

        colA, colB = st.columns([1, 4])
        with colA:
            if st.button("⬅️ Indietro", key="back_topics"):
                st.session_state["selected_topic_id"] = None
                st.rerun()
        with colB:
            st.markdown(f"### {topic.get('title', '(senza titolo)')}")

        descr = topic.get("description") or ""
        if descr.strip():
            st.write(descr)

        pdf_url = topic.get("pdf_url")
        if pdf_url:
            st.link_button("📄 Apri PDF", pdf_url, use_container_width=True)
        else:
            st.warning("PDF non disponibile per questo argomento.")

        # (Opzionale) anteprima inline — disattivata per evitare problemi iframe/CORS
        if False and pdf_url:  # imposta True se vuoi provare l'embed
            st.markdown("#### Anteprima (opzionale)")
            components.iframe(pdf_url, height=600, scrolling=True)

        # --- padding (non rimuovere)
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        #
        st.stop()

# =========================================================
# TAB 3 - CASO PRATICO (placeholder)
# =========================================================

with tabs[2]:
    st.session_state["menu_page"] = "case"
    st.markdown("## 🧩 Caso pratico")
    st.info("Sezione in costruzione: qui inseriremo i casi pratici per argomento.")
