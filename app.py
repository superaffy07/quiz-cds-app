import os
import random
import re
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from supabase import create_client

# ----------------------------
# Config
# ----------------------------
st.set_page_config(page_title="Quiz CDS", page_icon="🚓", layout="centered")

SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL", ""))
SUPABASE_ANON_KEY = st.secrets.get("SUPABASE_ANON_KEY", os.getenv("SUPABASE_ANON_KEY", ""))
ADMIN_CODE = st.secrets.get("ADMIN_CODE", os.getenv("ADMIN_CODE", "ADMIN123"))

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("Mancano le chiavi Supabase. Imposta SUPABASE_URL e SUPABASE_ANON_KEY nei Secrets di Streamlit.")
    st.stop()

sb = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ----------------------------
# Utils: simple sentence picker + distractors (FREE, no AI)
# ----------------------------
CONFUSION_SWAP = [
    ("revoca", "sospensione"),
    ("sospensione", "revoca"),
    ("prefetto", "giudice di pace"),
    ("giudice di pace", "prefetto"),
    ("centri abitati", "fuori dai centri abitati"),
    ("fuori dai centri abitati", "centri abitati"),
]

def split_sentences(text: str):
    text = re.sub(r"\s+", " ", (text or "")).strip()
    # split by . ; :
    parts = re.split(r"(?<=[\.\;\:])\s+", text)
    parts = [p.strip() for p in parts if len(p.strip()) > 40]
    return parts

def mutate_sentence(s: str):
    # negate modals
    s2 = s
    s2 = s2.replace(" deve ", " non deve ")
    s2 = s2.replace(" possono ", " non possono ")
    s2 = s2.replace(" può ", " non può ")
    # swap common confusions
    for a, b in CONFUSION_SWAP:
        if a in s2:
            s2 = s2.replace(a, b)
            break
    # tweak numbers (if any)
    nums = re.findall(r"\b\d+\b", s2)
    if nums:
        n = int(nums[0])
        s2 = re.sub(rf"\b{nums[0]}\b", str(max(1, n + random.choice([-1, 1, 2]))), s2, count=1)
    return s2

def build_mcq_from_source(argomento: str, fonte: str):
    sents = split_sentences(fonte)
    if not sents:
        # fallback: generic
        correct = f"Secondo la fonte, l'argomento '{argomento}' prevede regole e procedure specifiche da applicare correttamente."
    else:
        # pick a sentence that looks "normative"
        candidates = [s for s in sents if any(k in s.lower() for k in ["sanz", "entro", "giorni", "può", "deve", "viet", "pref", "giudice", "revoca", "sospensione"])]
        correct = random.choice(candidates) if candidates else random.choice(sents)

    # create 3 plausible wrong statements
    wrongs = set()
    tries = 0
    while len(wrongs) < 3 and tries < 30:
        tries += 1
        w = mutate_sentence(correct)
        if w != correct and len(w) > 30:
            wrongs.add(w)

    # if still not enough, add generic distractors
    while len(wrongs) < 3:
        wrongs.add(f"Per '{argomento}' si applica sempre una sola sanzione senza possibilità di ricorso o rateizzazione.")

    options = [correct] + list(wrongs)
    random.shuffle(options)
    correct_idx = options.index(correct)
    letters = ["A", "B", "C", "D"]
    correct_letter = letters[correct_idx]

    question = f"🧠 {argomento}\n\nQuale affermazione è corretta secondo la fonte?"
    explanation = "La risposta corretta è l’unica che coincide con quanto riportato nella fonte dell’argomento."
    return question, options, correct_letter, explanation

def build_practical_case(argomento: str):
    # Simple template-based cases (free)
    templates = [
        f"Durante un controllo, emerge un caso collegato a: {argomento}. Quali sono i passaggi operativi essenziali e quali conseguenze/sanzioni si applicano?",
        f"Scenario: pattuglia in servizio. Si verifica una situazione riconducibile a: {argomento}. Spiega cosa fai (atto/verbale/comunicazioni) e perché.",
    ]
    return random.choice(templates)

# ----------------------------
# DB helpers
# ----------------------------
def upsert_student(class_code: str, nickname: str):
    # try insert; if exists, fetch
    sb.table("students").upsert({"class_code": class_code, "nickname": nickname}).execute()
    res = sb.table("students").select("*").eq("class_code", class_code).eq("nickname", nickname).limit(1).execute()
    return res.data[0]

def fetch_topics():
    res = sb.table("topics").select("*").eq("is_active", True).order("id").execute()
    return res.data

def insert_topic(materia, argomento, fonte_testo, difficolta="intermedio", tags=""):
    sb.table("topics").insert({
        "materia": materia,
        "argomento": argomento,
        "fonte_testo": fonte_testo,
        "difficolta": difficolta,
        "tags": tags,
        "is_active": True
    }).execute()

# ----------------------------
# UI
# ----------------------------
st.title("🚓 Allenamento Quiz CDS")
st.caption("Correzione solo a fine sessione. Tutto salvato nel database.")

tabs = st.tabs(["🎓 Studente", "🛠️ Docente (carica argomenti)"])

# ----------------------------
# DOCENTE
# ----------------------------
with tabs[1]:
    st.subheader("Area docente (gratis, super semplice)")
    code = st.text_input("Codice docente", type="password")
    if code != ADMIN_CODE:
        st.info("Inserisci il codice docente per caricare argomenti nel DB.")
    else:
        st.success("Accesso docente OK.")
        st.write("Carica un CSV con colonne: materia,argomento,fonte_testo,difficolta,tags")
        uploaded = st.file_uploader("Carica CSV argomenti", type=["csv"])
        if uploaded:
            df = pd.read_csv(uploaded)
            required = {"argomento", "fonte_testo"}
            if not required.issubset(set(df.columns)):
                st.error("CSV non valido. Minimo: argomento, fonte_testo. (materia/difficolta/tags opzionali)")
            else:
                for _, row in df.iterrows():
                    insert_topic(
                        materia=row.get("materia", "CDS"),
                        argomento=str(row["argomento"]),
                        fonte_testo=str(row["fonte_testo"]),
                        difficolta=str(row.get("difficolta", "intermedio")),
                        tags=str(row.get("tags", "")),
                    )
                st.success("Argomenti caricati nel database ✅")

        st.divider()
        topics = fetch_topics()
        st.write(f"Argomenti attivi nel DB: {len(topics)}")
        if topics:
            st.dataframe(pd.DataFrame(topics)[["id","materia","argomento","difficolta","tags"]], use_container_width=True)

# ----------------------------
# STUDENTE
# ----------------------------
with tabs[0]:
    st.subheader("Accesso studente")
    class_code = st.text_input("Codice classe (decidi tu, es. CDS2026)")
    nickname = st.text_input("Nickname (es. Mirko)")
    if st.button("Entra"):
        if not class_code or not nickname:
            st.error("Inserisci codice classe e nickname.")
        else:
            st.session_state["student"] = upsert_student(class_code.strip(), nickname.strip())
            st.session_state["logged"] = True
            st.success("Accesso OK ✅")

    if st.session_state.get("logged"):
        student = st.session_state["student"]
        st.info(f"Connesso come: {student['nickname']} (classe {student['class_code']})")

        topics = fetch_topics()
        if not topics:
            st.warning("Nessun argomento nel DB. Il docente deve caricare un CSV nell’area Docente.")
            st.stop()

        scope = st.radio("Allenamento su:", ["Tutti gli argomenti", "Un solo argomento"], horizontal=True)
        if scope == "Un solo argomento":
            labels = [f"{t['id']} - {t['argomento']}" for t in topics]
            chosen = st.selectbox("Seleziona argomento", labels)
            chosen_id = int(chosen.split(" - ")[0])
            selected_topics = [t for t in topics if t["id"] == chosen_id]
        else:
            selected_topics = topics

        n_questions = st.slider("Numero quiz (multiple choice)", 5, 30, 10)
        include_case = st.checkbox("Includi anche 1 caso pratico (a fine sessione)", value=True)

        if st.button("Inizia sessione"):
            # create session
            topic_scope = "single" if scope == "Un solo argomento" else "all"
            selected_topic_id = selected_topics[0]["id"] if topic_scope == "single" else None

    sess = sb.table("sessions").insert({
        "student_id": student["id"],
        "mode": "mix" if include_case else "quiz",
        "topic_scope": topic_scope,
        "selected_topic_id": selected_topic_id,
        "n_questions": int(n_questions),
    }).execute().data[0]

    st.session_state["session_id"] = sess["id"]
    st.session_state["quiz_items"] = []
    st.session_state["answers"] = {}

    # ✅ genera tutte le domande in memoria
    batch_payload = []
    for _ in range(int(n_questions)):
        t = random.choice(selected_topics)
        q, opts, correct, expl = build_mcq_from_source(t["argomento"], t["fonte_testo"])
        payload = {
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
        batch_payload.append(payload)
        st.session_state["quiz_items"].append(payload)

    # ✅ UNA SOLA insert (evita blocco)
    sb.table("quiz_answers").insert(batch_payload).execute()

    if include_case:
        tcase = random.choice(selected_topics)
        st.session_state["case_topic"] = tcase
        st.session_state["case_prompt"] = build_practical_case(tcase["argomento"])
        st.session_state["case_answer"] = ""

    st.session_state["in_progress"] = True
    st.success("Sessione creata ✅ Scorri sotto per le domande.")

        # Session in progress
        if st.session_state.get("in_progress"):
            st.subheader("Sessione in corso (correzione alla fine)")
            quiz_items = st.session_state["quiz_items"]

            for idx, item in enumerate(quiz_items, start=1):
                st.markdown(f"### Domanda {idx}")
                st.write(item["question_text"])
                choice = st.radio(
                    "Scegli:",
                    ["A", "B", "C", "D"],
                    index=None,
                    key=f"q_{idx}"
                )
                st.write(f"**A)** {item['option_a']}")
                st.write(f"**B)** {item['option_b']}")
                st.write(f"**C)** {item['option_c']}")
                st.write(f"**D)** {item['option_d']}")
                st.session_state["answers"][idx] = choice

                st.divider()

            if "case_prompt" in st.session_state:
                st.markdown("## Caso pratico (rispondi in modo sintetico ma completo)")
                st.write(st.session_state["case_prompt"])
                st.session_state["case_answer"] = st.text_area("Risposta:", value=st.session_state.get("case_answer",""), height=140)

            if st.button("Termina sessione e vedi correzione"):
                session_id = st.session_state["session_id"]

                # fetch stored quiz rows in DB (ordered by id)
                db_rows = sb.table("quiz_answers").select("*").eq("session_id", session_id).order("id").execute().data

                score = 0
                results = []
                for i, row in enumerate(db_rows, start=1):
                    chosen = st.session_state["answers"].get(i)
                    sb.table("quiz_answers").update({"chosen_option": chosen}).eq("id", row["id"]).execute()
                    is_ok = (chosen == row["correct_option"])
                    score += 1 if is_ok else 0
                    results.append((i, chosen, row["correct_option"], is_ok, row["question_text"], row["explanation"]))

                # grade practical case (simple rubric: keyword overlap with fonte)
                if "case_prompt" in st.session_state:
                    t = st.session_state["case_topic"]
                    fonte = (t["fonte_testo"] or "").lower()
                    ans = (st.session_state["case_answer"] or "").lower()

                    # extract some keywords from fonte (very simple)
                    keywords = [w for w in re.findall(r"[a-zàèéìòù]+", fonte) if len(w) >= 7]
                    keywords = list(dict.fromkeys(keywords))[:25]
                    hits = sum(1 for k in keywords if k in ans)

                    if hits >= 6:
                        grade = "IDONEO"
                    elif hits >= 3:
                        grade = "PARZIALE"
                    else:
                        grade = "NON_IDONEO"

                    feedback = (
                        "Valutazione basata sulla coerenza con la fonte dell’argomento. "
                        "Per migliorare: cita passaggi operativi, termini, tempi e conseguenze/sanzioni presenti nella fonte."
                    )

                    sb.table("practical_cases").insert({
                        "session_id": session_id,
                        "topic_id": t["id"],
                        "case_prompt": st.session_state["case_prompt"],
                        "student_answer": st.session_state["case_answer"],
                        "grade": grade,
                        "feedback": feedback,
                    }).execute()

                # close session
                sb.table("sessions").update({"finished_at": datetime.now(timezone.utc).isoformat()}).eq("id", session_id).execute()

                # show results
                st.session_state["in_progress"] = False
                st.subheader("✅ Correzione (fine sessione)")
                st.write(f"Punteggio quiz: **{score} / {len(results)}**")

                for (i, chosen, correct, ok, qtext, expl) in results:
                    st.markdown(f"### Domanda {i} — {'✅' if ok else '❌'}")
                    st.write(qtext)
                    st.write(f"Risposta data: **{chosen}** | Corretta: **{correct}**")
                    st.caption(expl)

                if "case_prompt" in st.session_state:
                    case_row = sb.table("practical_cases").select("*").eq("session_id", session_id).order("id", desc=True).limit(1).execute().data
                    if case_row:
                        st.markdown("## Caso pratico — Esito")
                        st.write(f"**Valutazione:** {case_row[0]['grade']}")
                        st.caption(case_row[0]["feedback"])

                st.success("Sessione salvata nel database ✅")
