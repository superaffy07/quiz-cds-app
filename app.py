import os
import time
import random
from datetime import datetime, timezone

import streamlit as st
from supabase import create_client


# =========================
# Config & Style
# =========================
st.set_page_config(
    page_title="Simulazioni & Quiz - Polizia Locale",
    page_icon="🚓",
    layout="wide",
)

CSS = """
<style>
/* Base */
.block-container { padding-top: 1.8rem; padding-bottom: 2rem; max-width: 1050px; }
h1, h2, h3 { letter-spacing: -0.02em; }
small, .muted { color: rgba(0,0,0,0.55); }

/* Header card */
.header-card{
  border: 1px solid rgba(0,0,0,0.08);
  background: linear-gradient(180deg, rgba(250,250,250,1) 0%, rgba(245,246,247,1) 100%);
  border-radius: 18px;
  padding: 18px 18px 14px 18px;
  margin-bottom: 14px;
}
.badges { display:flex; gap:8px; flex-wrap:wrap; margin-top:8px; }
.badge{
  border: 1px solid rgba(0,0,0,0.10);
  background: rgba(255,255,255,0.75);
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
}

/* Cards */
.card{
  border: 1px solid rgba(0,0,0,0.08);
  background: rgba(255,255,255,0.85);
  border-radius: 18px;
  padding: 16px;
  margin-bottom: 12px;
}
.card-title{ font-size: 16px; font-weight: 700; margin-bottom: 6px; }

/* Quiz */
.qtitle{ font-size: 18px; font-weight: 750; margin: 0 0 8px 0; }
.qtext{ font-size: 15px; line-height: 1.5; margin-bottom: 8px; }
.hr { border-top: 1px solid rgba(0,0,0,0.08); margin: 12px 0; }

.kpi-row{ display:flex; gap:10px; flex-wrap:wrap; margin: 6px 0 10px 0; }
.kpi{
  border: 1px solid rgba(0,0,0,0.08);
  background: rgba(255,255,255,0.85);
  border-radius: 14px;
  padding: 10px 12px;
  font-size: 13px;
}
.kpi b{ font-size: 14px; }

/* Footer */
.footer{
  margin-top: 18px;
  padding-top: 10px;
  border-top: 1px solid rgba(0,0,0,0.08);
  font-size: 12px;
  color: rgba(0,0,0,0.55);
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# Timer autorefresh (1s) – fallback se non installato
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except Exception:
    HAS_AUTOREFRESH = False


# =========================
# Secrets / Supabase
# =========================
def get_secret(name: str, default: str = "") -> str:
    """Try st.secrets then env vars."""
    try:
        if name in st.secrets:
            v = st.secrets.get(name, default)
            if v:
                return str(v)
    except Exception:
        pass
    return os.getenv(name, default) or default


def get_supabase():
    url = get_secret("SUPABASE_URL")
    # accetta sia SUPABASE_ANON_KEY che SUPABASE_KEY
    key = get_secret("SUPABASE_ANON_KEY") or get_secret("SUPABASE_KEY")

    if not url or not key:
        st.error("❌ Mancano SUPABASE_URL e/o SUPABASE_ANON_KEY (o SUPABASE_KEY) nei Secrets/Env di Streamlit.")
        st.stop()

    return create_client(url, key)


sb = get_supabase()
ADMIN_CODE = get_secret("ADMIN_CODE", "DOCENTE1")


# =========================
# DB helpers
# =========================
def db_count_questions() -> int:
    try:
        res = sb.table("question_bank").select("id", count="exact").execute()
        return int(res.count or 0)
    except Exception:
        return 0


def db_random_questions(n: int = 30) -> list[dict]:
    """
    Prende più righe e poi randomizza in Python (compatibile con PostgREST).
    Se hai 1000+ domande, va benissimo: qui prendiamo un batch e poi scegliamo.
    """
    total = db_count_questions()
    if total <= 0:
        return []

    # batch: prendo un po' di righe per randomizzare; almeno n, massimo 400
    batch = min(max(n * 5, n), 400)
    try:
        res = sb.table("question_bank").select(
            "id,source_pdf,question_no,question_text,option_a,option_b,option_c,option_d,correct_option"
        ).limit(batch).execute()
        rows = res.data or []
    except Exception:
        rows = []

    # se il dataset è grande ma la limit non pesca abbastanza variabile,
    # una seconda pesca (semplice) aiuta un po'
    if len(rows) < n and total > batch:
        try:
            res2 = sb.table("question_bank").select(
                "id,source_pdf,question_no,question_text,option_a,option_b,option_c,option_d,correct_option"
            ).range(batch, batch + batch - 1).execute()
            rows += (res2.data or [])
        except Exception:
            pass

    random.shuffle(rows)
    return rows[:n]


def upsert_student(class_code: str, nickname: str) -> dict:
    class_code = (class_code or "").strip()
    nickname = (nickname or "").strip()

    payload = {"class_code": class_code, "nickname": nickname}

    # 1) Prova UPSERT (compatibile con più versioni supabase/postgrest)
    try:
        # molte versioni accettano on_conflict
        sb.table("students").upsert(payload, on_conflict="class_code,nickname").execute()
    except TypeError:
        # alcune versioni non accettano on_conflict
        sb.table("students").upsert(payload).execute()
    except Exception:
        # se l'upsert fallisce per qualche motivo (es. policy), proviamo insert "safe"
        try:
            sb.table("students").insert(payload).execute()
        except Exception:
            pass

    # 2) Recupera SEMPRE il record con una SELECT separata (evita problemi di response .data / .select dopo upsert)
    res = sb.table("students").select("*").eq("class_code", class_code).eq("nickname", nickname).limit(1).execute()

    data = None
    if hasattr(res, "data"):
        data = res.data
    elif isinstance(res, dict):
        data = res.get("data")

    if not data:
        raise RuntimeError("Impossibile recuperare lo studente dopo l'upsert. Controlla RLS/policies su 'students'.")

    return data[0]



def create_session(student_id: int, n_questions: int) -> dict:
    payload = {
        "student_id": student_id,
        "mode": "simulation",
        "topic_scope": "bank",
        "n_questions": int(n_questions),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    res = sb.table("sessions").insert(payload).select("*").execute()
    return (res.data or [])[0]


def save_session_questions(session_id: str, questions: list[dict]):
    rows = []
    for q in questions:
        # normalizza corretta
        corr = (q.get("correct_option") or "").strip().upper()

        rows.append({
            "session_id": session_id,
            "topic_id": None,
            "question_text": q.get("question_text") or "",
            "option_a": q.get("option_a") or "",
            "option_b": q.get("option_b") or "",
            "option_c": q.get("option_c") or "",
            "option_d": q.get("option_d") or "",  # NON NULL in tabella quiz_answers → metti stringa vuota
            "correct_option": corr if corr in ["A","B","C","D"] else "A",
            "chosen_option": None,
            "explanation": "",
        })

    sb.table("quiz_answers").insert(rows).execute()


def fetch_session_questions(session_id: str) -> list[dict]:
    res = sb.table("quiz_answers").select(
        "id,question_text,option_a,option_b,option_c,option_d,correct_option,chosen_option"
    ).eq("session_id", session_id).order("id").execute()
    return res.data or []


def update_chosen(answer_row_id: int, chosen: str):
    sb.table("quiz_answers").update({"chosen_option": chosen}).eq("id", answer_row_id).execute()


def close_session(session_id: str):
    sb.table("sessions").update({"finished_at": datetime.now(timezone.utc).isoformat()}).eq("id", session_id).execute()


# =========================
# UI helpers
# =========================
def fmt_mmss(seconds: int) -> str:
    seconds = max(0, int(seconds))
    m = seconds // 60
    s = seconds % 60
    return f"{m}m {s:02d}s"


def option_map(row: dict) -> list[tuple[str, str]]:
    """
    Ritorna solo le opzioni NON vuote.
    """
    opts = []
    for letter, key in [("A","option_a"),("B","option_b"),("C","option_c"),("D","option_d")]:
        txt = (row.get(key) or "").strip()
        if txt:
            opts.append((letter, txt))
    return opts


def header_ui():
    st.markdown(
        """
        <div class="header-card">
          <div style="display:flex; align-items:center; gap:10px;">
            <div style="font-size:28px;">🚓</div>
            <div>
              <div style="font-size:26px; font-weight:850;">Simulazioni & Quiz</div>
              <div class="muted">Piattaforma didattica per concorsi – a cura di <b>Raffaele Sotero</b></div>
            </div>
          </div>
          <div class="badges">
            <div class="badge">⏱️ 30 domande / 30 minuti</div>
            <div class="badge">✅ Correzione finale</div>
            <div class="badge">🗃️ Banca dati Supabase</div>
            <div class="badge">👨‍🏫 Upload CSV (Docente)</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def kpi_bar(score: int, total: int, elapsed_s: int):
    st.markdown('<div class="kpi-row">', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi">🎯 Punteggio: <b>{score} / {total}</b></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi">⏱️ Tempo impiegato: <b>{fmt_mmss(elapsed_s)}</b></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


# =========================
# State init
# =========================
if "logged" not in st.session_state:
    st.session_state.logged = False
if "student" not in st.session_state:
    st.session_state.student = None
if "active_session_id" not in st.session_state:
    st.session_state.active_session_id = None
if "session_started_ts" not in st.session_state:
    st.session_state.session_started_ts = None
if "session_duration_s" not in st.session_state:
    st.session_state.session_duration_s = 30 * 60
if "finished" not in st.session_state:
    st.session_state.finished = False


# =========================
# App
# =========================
header_ui()

tab_student, tab_doc = st.tabs(["🎓 Studente", "🧑‍🏫 Docente (upload CSV)"])

# -------------------------
# DOCENTE TAB (solo info base, l’upload vero lo stai già usando)
# -------------------------
with tab_doc:
    st.markdown('<div class="card"><div class="card-title">Area Docente</div>', unsafe_allow_html=True)
    st.write("Qui puoi caricare CSV nella tabella **question_bank** (Supabase).")
    st.info(f"Codice docente (ADMIN_CODE): **{ADMIN_CODE}**")
    st.write("Suggerimento: carica sempre CSV con colonne coerenti e opzioni vuote come stringa vuota.")
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# STUDENTE TAB
# -------------------------
with tab_student:
    st.markdown('<div class="card"><div class="card-title">Accesso studente</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])
    with col1:
        if not st.session_state.logged:
            with st.form("login_form", clear_on_submit=False):
                class_code = st.text_input("Codice classe", value="CDS2026")
                nickname = st.text_input("Nickname (es. Mirko)", value="")
                submitted = st.form_submit_button("Entra ✅")
                if submitted:
                    if not class_code.strip() or not nickname.strip():
                        st.error("Inserisci codice classe e nickname.")
                    else:
                        student = upsert_student(class_code.strip(), nickname.strip())
                        st.session_state.student = student
                        st.session_state.logged = True
                        st.success("Accesso OK ✅")
                        st.rerun()
        else:
            student = st.session_state.student
            st.success(f"Connesso come: {student['nickname']} (classe {student['class_code']})")
            if st.button("Logout"):
                st.session_state.logged = False
                st.session_state.student = None
                st.session_state.active_session_id = None
                st.session_state.session_started_ts = None
                st.session_state.finished = False
                st.rerun()

    with col2:
        tot = db_count_questions()
        st.metric("Domande in banca dati", tot)

    st.markdown("</div>", unsafe_allow_html=True)

    if not st.session_state.logged:
        st.stop()

    # -------------------------
    # SIMULAZIONE
    # -------------------------
    st.markdown('<div class="card"><div class="card-title">Simulazione</div>', unsafe_allow_html=True)
    st.write("30 domande random dalla banca dati. Timer 30 minuti. Correzione finale.")

    # Stato: se non c’è sessione attiva
    if st.session_state.active_session_id is None and not st.session_state.finished:
        if st.button("Inizia simulazione 🚀"):
            picked = db_random_questions(30)
            if not picked or len(picked) < 5:
                st.error("Banca dati vuota o insufficiente. Carica altre domande in question_bank.")
                st.stop()

            sess = create_session(st.session_state.student["id"], 30)
            st.session_state.active_session_id = sess["id"]
            st.session_state.session_started_ts = time.time()
            st.session_state.session_duration_s = 30 * 60
            st.session_state.finished = False

            # “fotografa” le domande in quiz_answers (così non cambiano durante la prova)
            save_session_questions(sess["id"], picked)

            st.rerun()

    # Se c’è sessione attiva: mostra timer + domande
    if st.session_state.active_session_id and not st.session_state.finished:
        session_id = st.session_state.active_session_id
        questions = fetch_session_questions(session_id)

        started_ts = st.session_state.session_started_ts or time.time()
        elapsed = int(time.time() - started_ts)
        remaining = st.session_state.session_duration_s - elapsed

        # autorefresh ogni 1s (timer fluido)
        if HAS_AUTOREFRESH:
            st_autorefresh(interval=1000, key="tick")
        else:
            st.caption("⚠️ Per timer super fluido, aggiungi `streamlit-autorefresh` al requirements.txt")

        st.markdown('<div class="kpi-row">', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi">⏳ Tempo residuo: <b>{fmt_mmss(remaining)}</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi">🧩 Domande: <b>{len(questions)} / 30</b></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.progress(min(max(elapsed / (30 * 60), 0.0), 1.0))

        if remaining <= 0:
            st.warning("⏰ Tempo scaduto. Chiudo la sessione e mostro la correzione.")
            close_session(session_id)
            st.session_state.finished = True
            st.rerun()

        for i, row in enumerate(questions, start=1):
            st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="qtitle">Q{i}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="qtext">{row["question_text"]}</div>', unsafe_allow_html=True)

            opts = option_map(row)
            # radio con label "A) testo"
            labels = [f"{L}) {T}" for L, T in opts]
            letters = [L for L, _ in opts]

            # valore predefinito scelto (se già cliccato)
            chosen = row.get("chosen_option")
            idx = letters.index(chosen) if chosen in letters else 0

            picked_label = st.radio(
                "Seleziona risposta",
                labels,
                index=idx,
                key=f"q_{row['id']}",
            )
            new_letter = picked_label.split(")")[0].strip().upper()
            if new_letter != chosen:
                update_chosen(row["id"], new_letter)

        st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
        if st.button("Termina simulazione e vedi correzione ✅"):
            close_session(session_id)
            st.session_state.finished = True
            st.rerun()

    # -------------------------
    # CORREZIONE FINALE
    # -------------------------
    if st.session_state.finished and st.session_state.active_session_id:
        session_id = st.session_state.active_session_id
        answers = fetch_session_questions(session_id)

        # calcolo punteggio
        score = 0
        for r in answers:
            if (r.get("chosen_option") or "").strip().upper() == (r.get("correct_option") or "").strip().upper():
                score += 1

        started_ts = st.session_state.session_started_ts or time.time()
        elapsed_s = int(time.time() - started_ts)

        st.markdown('<div class="card"><div class="card-title">✅ Correzione finale</div>', unsafe_allow_html=True)
        kpi_bar(score, len(answers), elapsed_s)

        st.success(f"Risultato: **{score} / {len(answers)}**")
        st.caption(f"Prova completata in **{fmt_mmss(elapsed_s)}**")

        st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

        for i, r in enumerate(answers, start=1):
            opts = dict(option_map(r))  # letter -> text
            chosen = (r.get("chosen_option") or "").strip().upper()
            correct = (r.get("correct_option") or "").strip().upper()

            ok = chosen == correct and chosen != ""
            icon = "✅" if ok else "❌"

            st.markdown(f"### {icon} Q{i}")
            st.write(r["question_text"])

            chosen_txt = opts.get(chosen, "(non risposta)")
            correct_txt = opts.get(correct, "(manca opzione corretta nel DB)")

            st.write(f"**Tua risposta:** {chosen if chosen else '-'} → {chosen_txt}")
            st.write(f"**Corretta:** {correct if correct else '-'} → {correct_txt}")

            st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

        colA, colB = st.columns([1, 1])
        with colA:
            if st.button("Nuova simulazione 🔁"):
                # reset session
                st.session_state.active_session_id = None
                st.session_state.session_started_ts = None
                st.session_state.finished = False
                st.rerun()

        with colB:
            if st.button("Logout"):
                st.session_state.logged = False
                st.session_state.student = None
                st.session_state.active_session_id = None
                st.session_state.session_started_ts = None
                st.session_state.finished = False
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="footer">
          © {datetime.now().year} – Simulazioni & Quiz · Polizia Locale · a cura di Raffaele Sotero
        </div>
        """,
        unsafe_allow_html=True
    )

