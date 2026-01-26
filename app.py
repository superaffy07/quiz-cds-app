# ... existing code ...
def render_top_hero(bank_count: int):
    st.markdown(
        f"""
        <div class="top-pill">🚓 <span>PLATFORM</span> <span style="opacity:.55;">•</span> <span>CORSO PL 2026</span></div>
        <div class="hero-title">Banca dati, simulazioni e quiz</div>
        <div class="hero-sub">
          Piattaforma didattica a cura di <b>Raffaele Sotero</b><br/>
          Correzione finale dettagliata • Casi pratici • Quiz • Banca dati
        </div>
        <div class="hero-actions">
          <div class="chip">📚 Banca dati: <b>{bank_count}</b> domande</div>
          <div class="chip">⏱️ Simulazione: <b>{DURATION_SECONDS_DEFAULT//60}</b> minuti</div>
          <div class="chip">✅ Valutazione: <b>1 punto</b> per risposta esatta</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_landing_login() -> tuple[str, str, bool]:
    """
    Landing page (solo quando NON loggato) stile 'hero + sirene + glass login'.
    Ritorna: (full_name, course_pass, clicked)
    """
    hero_bg_url = ""
    try:
        hero_bg_url = (st.secrets.get("HERO_BG_URL", "") or "").strip()
    except Exception:
        hero_bg_url = ""

    if not hero_bg_url:
        hero_bg_url = "https://example.invalid/hero-polizia-locale.jpg"  # placeholder

    st.markdown(
        f"""
<style>
/* ===== LANDING ONLY ===== */
.landing-wrap {{
  position: relative;
  width: 100%;
  min-height: calc(100vh - 120px);
  border-radius: 22px;
  overflow: hidden;
  box-shadow: 0 26px 70px rgba(0,0,0,.45);
  border: 1px solid rgba(255,255,255,.10);
}}

.landing-bg {{
  position:absolute;
  inset:0;
  background:
    linear-gradient(180deg, rgba(0,0,0,.55) 0%, rgba(0,0,0,.65) 70%, rgba(0,0,0,.70) 100%),
    url("{hero_bg_url}");
  background-size: cover;
  background-position: center;
  transform: scale(1.03);
  filter: saturate(1.05) contrast(1.05);
}}

.landing-bg-fallback {{
  position:absolute;
  inset:0;
  background:
    radial-gradient(1200px 600px at 18% 10%, rgba(26,92,255,.35), transparent 60%),
    radial-gradient(1200px 600px at 82% 10%, rgba(255,45,85,.35), transparent 60%),
    linear-gradient(180deg, #070A12 0%, #0B1220 100%);
}}

.landing-overlay {{
  position:absolute;
  inset:0;
  backdrop-filter: blur(10px);
  background: rgba(0,0,0,.25);
}}

.siren {{
  position:absolute;
  inset:-35% -20%;
  pointer-events:none;
  mix-blend-mode: screen;
  opacity: .95;
  filter: blur(2px);
}}
.siren:before, .siren:after {{
  content:"";
  position:absolute;
  width: 60%;
  height: 60%;
  border-radius: 999px;
}}
.siren:before {{
  left: -10%;
  top: 10%;
  background: radial-gradient(circle, rgba(26,92,255,.55), transparent 62%);
}}
.siren:after {{
  right: -10%;
  top: 10%;
  background: radial-gradient(circle, rgba(255,45,85,.55), transparent 62%);
}}

.landing-content {{
  position: relative;
  z-index: 2;
  padding: 42px 36px 40px;
}}
@media (max-width: 980px){{
  .landing-content {{ padding: 26px 16px 28px; }}
}}

.landing-top-pill {{
  display:inline-flex;
  align-items:center;
  gap:10px;
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(255,255,255,.10);
  border: 1px solid rgba(255,255,255,.16);
  backdrop-filter: blur(12px);
  box-shadow: 0 10px 28px rgba(0,0,0,.28);
  font-weight: 800;
  letter-spacing: .3px;
  color: rgba(255,255,255,.92);
}}

.landing-title {{
  margin: 18px 0 6px 0;
  font-family: Oswald, Inter, sans-serif;
  font-size: 56px;
  line-height: 1.02;
  color: rgba(255,255,255,.94);
  text-shadow: 0 14px 40px rgba(0,0,0,.45);
}}
.landing-kicker {{
  margin: 0 0 10px 0;
  font-family: Oswald, Inter, sans-serif;
  font-size: 28px;
  letter-spacing: .2px;
  color: rgba(255,255,255,.88);
}}

.landing-sub {{
  margin: 0;
  color: rgba(255,255,255,.78);
  font-size: 16px;
  line-height: 1.55;
}}

.landing-bul {{
  margin: 10px 0 0 0;
  color: rgba(255,255,255,.80);
  font-weight: 800;
}}

.shortcut-row {{
  margin-top: 16px;
  display:flex;
  gap:10px;
  flex-wrap: wrap;
}}

.shortcut-pill {{
  display:inline-flex;
  align-items:center;
  gap:8px;
  padding: 9px 12px;
  border-radius: 999px;
  background: rgba(255,255,255,.10);
  border: 1px solid rgba(255,255,255,.16);
  backdrop-filter: blur(12px);
  font-weight: 900;
  font-size: 12px;
  color: rgba(255,255,255,.90);
}}

.login-glass {{
  background: rgba(255,255,255,.10);
  border: 1px solid rgba(255,255,255,.16);
  border-radius: 22px;
  box-shadow: 0 26px 70px rgba(0,0,0,.38);
  backdrop-filter: blur(16px);
  overflow:hidden;
}}
.login-glass-inner {{
  padding: 18px 18px 16px;
}}

.login-h {{
  font-family: Oswald, Inter, sans-serif;
  font-size: 30px;
  margin: 0 0 6px 0;
  color: rgba(255,255,255,.94);
}}
.login-p {{
  margin: 0 0 14px 0;
  color: rgba(255,255,255,.72);
  line-height: 1.45;
}}

.login-foot {{
  margin-top: 10px;
  color: rgba(255,255,255,.70);
  font-size: 12.5px;
  line-height: 1.35;
}}
/* Rafforzo stile input/bottone solo qui (senza cambiare logica) */
.landing-scope div[data-baseweb="input"] > div {{
  background: rgba(255,255,255,.12) !important;
  border: 1px solid rgba(255,255,255,.18) !important;
}}
.landing-scope div[data-baseweb="base-input"] input {{
  color: rgba(255,255,255,.92) !important;
}}
.landing-scope div[data-baseweb="base-input"] input::placeholder {{
  color: rgba(255,255,255,.55) !important;
}}
.landing-scope .primary-gold .stButton > button {{
  width: 100%;
  background: linear-gradient(180deg, #F2C76D, #E6B25A) !important;
  color: #1b1b1b !important;
  border: 1px solid rgba(0,0,0,.12) !important;
  box-shadow: 0 14px 30px rgba(230,178,90,.28) !important;
  padding: 14px 16px !important;
  font-size: 16px !important;
  border-radius: 14px !important;
}}
.landing-scope .primary-gold .stButton > button:hover {{
  background: linear-gradient(180deg, #FFD98B, #F2C76D) !important;
}}
</style>

<div class="landing-wrap landing-scope">
  <div class="{('landing-bg' if hero_bg_url else 'landing-bg-fallback')}"></div>
  <div class="landing-overlay"></div>
  <div class="siren"></div>

  <div class="landing-content">
    <div class="landing-top-pill">🚓 PLATFORM <span style="opacity:.55;">•</span> CORSO PL 2026</div>

    <div class="landing-title">Banca dati, simulazioni e quiz</div>
    <div class="landing-kicker">Polizia Locale</div>

    <p class="landing-sub">Piattaforma didattica a cura di <b>Raffaele Sotero</b></p>
    <p class="landing-bul">• Correzione finale dettagliata</p>

    <div class="shortcut-row">
      <div class="shortcut-pill">Casi pratici</div>
      <div class="shortcut-pill">Quiz</div>
      <div class="shortcut-pill">Banca dati</div>
    </div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

    # Card centrata con columns (senza HTML "separato" che duplica testi: qui solo contenitore)
    left, mid, right = st.columns([1.2, 1.0, 1.2])
    with mid:
        st.markdown(
            """
            <div class="login-glass">
              <div class="login-glass-inner">
                <div class="login-h">Accesso corsista</div>
                <div class="login-p">Inserisci Nome e Cognome e la password del corso.</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Form vero Streamlit: niente duplicazioni “HTML parallele” dei campi
        with st.form("landing_login_form", clear_on_submit=False):
            full_name = st.text_input("Nome e Cognome", placeholder="Nome e Cognome (es. Mario Rossi)")
            course_pass = st.text_input("Password del corso", type="password", placeholder="Password del corso")
            st.markdown('<div class="primary-gold">', unsafe_allow_html=True)
            clicked = st.form_submit_button("Entra")
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            """
            <div class="login-foot">
              Accesso riservato ai corsisti • Inserisci Nome e Cognome e la password del corso.
            </div>
            """,
            unsafe_allow_html=True,
        )

    return full_name, course_pass, clicked
# ... existing code ...
```


---

## 2) Blocco ESATTO da incollare nel punto giusto (START/END LANDING)

Questo blocco va **dentro** `with tab_stud:` e **dentro** `if not st.session_state["logged"]:` (senza indent extra).

```python
# ... existing code ...
with tab_stud:
    if not st.session_state["logged"]:
        # ===== START LANDING =====
        full_name, course_pass, clicked = render_landing_login()

        if clicked:
            if not full_name.strip() or not course_pass.strip():
                st.error("Inserisci Nome e Cognome + Password.")
            elif course_pass != COURSE_PASSWORD:
                st.error("Password errata. Riprova.")
            else:
                try:
                    st.session_state["student"] = upsert_student(COURSE_CLASS_CODE, full_name)
                    st.session_state["logged"] = True
                    st.session_state["menu_page"] = "home"
                    st.success("Accesso OK ✅")
                    st.rerun()
                except Exception as e:
                    st.error("Errore accesso.")
                    st.exception(e)

        st.stop()
        # ===== END LANDING =====

    student = st.session_state["student"]
    st.info(f"Connesso come: {student['nickname']} (corso {student['class_code']})")
# ... existing code ...
```


> Nota: `st.stop()` viene eseguito **sempre** quando non loggato (come richiesto), così non renderizzi niente “dopo” la landing.

---

## 3) Dove inserirlo e cosa sostituire (solo login vecchio)

### A) Inserimento funzione
- Inserisci la funzione `render_landing_login()` **nella sezione UI blocks**, vicino a `render_top_hero()` (subito dopo va benissimo).

### B) Sostituzione login vecchio
- Nel tuo file, trova la parte:

```python
with tab_stud:
    if not st.session_state["logged"]:
        ...  # (vecchia landing/login)
        st.stop()
