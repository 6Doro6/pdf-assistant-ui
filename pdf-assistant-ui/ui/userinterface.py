import os
from dotenv import load_dotenv
load_dotenv(override=True)
from pathlib import Path
import streamlit as st
st.set_page_config(page_title="PDF Assistant", page_icon="📕", layout="wide", initial_sidebar_state="expanded",)
import time
import random
from helpers import (
    NAME_RE, PHONE_RE, EMAIL_RE,
    _req,
    fetch_user_access_via_admin,
    submit_access_request,
    _mask_first_last,
    _fmt_secs,
)

# --- Safe secrets/env bootstrap ---
def _secrets_available() -> bool:
    # Only probe st.secrets if a secrets file is present
    return Path(".streamlit/secrets.toml").exists() or Path.home().joinpath(".streamlit/secrets.toml").exists()

if _secrets_available():
    ST_SECRETS: dict = dict(st.secrets)
else:
    ST_SECRETS = {}

# Admin key (prefer secrets, fallback to env loaded by dotenv)
ak = (ST_SECRETS.get("admin", {}) or {}).get("api_key", "") or os.getenv("UI_ADMIN_API_KEY") or os.getenv("ADMIN_API_KEY", "")
if ak:
    os.environ["UI_ADMIN_API_KEY"] = str(ak).strip()


# ===== Admin/API diagnostics =====
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

def _mask(s: str | None) -> str:
    if not s:
        return "—"
    return (s[:3] + "..." + s[-3:]) if len(s) > 8 else "***"

ADMIN_KEY = os.getenv("UI_ADMIN_API_KEY") or os.getenv("ADMIN_API_KEY")

# ==================== CONFIG ====================
UPLOAD_PATH         = os.getenv("UPLOAD_PATH", "/documents")
QUERY_PATH          = os.getenv("QUERY_PATH", "/documents/query")
UPLOAD_FILE_FIELD   = os.getenv("UPLOAD_FILE_FIELD", "pdf")
MIN_QUESTION_CHARS  = int(os.getenv("MIN_QUESTION_CHARS", "10"))
LANG_LABEL_TO_CODE = {"NL":"nl","FR":"fr","DE":"de","EN":"en"}

# ---- Global styles + overview (RIGHT BELOW THE TITLE) ----

st.title("📕 PDF Assistant")

#st.markdown("""
#<style>
#/* Overview block */
#.app-overview{
#  margin-top:.25rem;
#  padding:.9rem 1rem;
#  border:1px solid rgba(49,51,63,.15);
#  border-radius:.6rem;
#  background: rgba(240,242,246,.55);
#}
#.app-overview p{
#  margin:0;
#  font-size:.98rem;
#  line-height:1.55;
#}

#/* Status cards */
#.status-card{
#  border:1px solid rgba(49,51,63,.15);
#  border-radius:.8rem;
#  padding:1rem 1rem .85rem;
#  #background: grey;
#}
#.status-title{
#  font-size:1.12rem;   /* title bigger than value */
#  font-weight:700;
#  margin:0 0 .15rem 0;
#}
#.status-value{
#  font-size:.96rem;    /* smaller than title */
#  opacity:.9;
#  margin:0;
#  word-break:break-word;
#}
#.status-icon{
#  font-size:1.9rem;    /* big icon only for Access */
#  line-height:1;
#  display:inline-block;
#  margin-top:.15rem;
#}
#</style>

#<div class="app-overview">
#  <p><strong>How it works:</strong> enter your <em>User ID</em> in the left sidebar and click <em>Start session</em>.
#  Then upload a PDF and press <em>Process PDF</em>. Finally, type a question about the document and click
#  <em>Get answer</em>. You can optionally enable verification and suggested follow-ups.</p>
# </div>
#""", unsafe_allow_html=True)


# ==================== UI helpers ====================
def show_verification(v: dict | None):
    if not v:
        return

    ok   = bool(v.get("is_accurate"))
    conf = v.get("confidence")
    #issues = v.get("issues_found") or []
    expl   = (v.get("explanation") or "").strip()

    icon  = "✅" if ok else "⚠️"
    #title = "Accurate" if ok else "Please double-check"

    st.markdown("""
    <style>

      .verif-title{
        font-weight:800;
        font-size:1.1rem;
        margin:0 0 .25rem 0;
      }
      .verif-meta{ opacity:.9; margin-bottom:.5rem }
      .verif-list li{ margin-bottom:.15rem }
    </style>
    """, unsafe_allow_html=True)

    st.subheader(f"🚦Verification")   # same level/size as “💬 Answer”
    st.markdown("<div class='verif-card'>", unsafe_allow_html=True)

    #st.markdown(f"<div class='verif-title'>{title}</div>", unsafe_allow_html=True)

    meta_bits = []
    if conf is not None:
        meta_bits.append(f"Confidence: {icon} **{conf}**")
    if meta_bits:
        st.markdown("<div class='verif-meta'>" + " • ".join(meta_bits) + "</div>", unsafe_allow_html=True)

    if expl:
        st.write(expl)

    #if issues:
    #    st.markdown("**Issues found:**")
    #    st.markdown("\n".join(f"- {i}" for i in issues))

    st.markdown("</div>", unsafe_allow_html=True)

#def show_citations(cits: list | None):
#    if not cits: return
#    st.subheader("📝 Citations")
#    for c in cits:
#        meta = " · ".join(filter(None, [
#            f"ID {c.get('id','?')}",
#            f"p.{c.get('page')}" if c.get("page") else None,
#            c.get("section") or None
#        ]))
#        snippet = c.get("snippet", "")
#        st.markdown(f"- **{meta}** — {snippet}")

def show_citations(cits: list | None):
    if not cits:
        return

    # Sort by page if available (so opening the block feels organized)
    try:
        cits_sorted = sorted(cits, key=lambda x: (x.get("page") is None, x.get("page")))
    except Exception:
        cits_sorted = cits

    st.markdown("""
    <style>
      .cite-item{
        border:1px solid rgba(49,51,63,.15);
        border-radius:.5rem;
        padding:.6rem .75rem;
        margin:.5rem 0;
        background: rgba(240,242,246,.25);
      }
      .page-pill{
        display:inline-block;
        padding:.15rem .6rem;
        border-radius:999px;
        font-weight:700;
        border:1px solid rgba(49,51,63,.25);
        margin-right:.5rem;
      }
      .cite-meta{
        font-weight:600;
        opacity:.85;
      }
      .cite-snippet{
        margin-top:.35rem;
      }
    </style>
    """, unsafe_allow_html=True)

    with st.expander(f"📝 Citations ({len(cits_sorted)})", expanded=False):
        for c in cits_sorted:
            page = c.get("page")
            section = c.get("section")
            snippet = (c.get("snippet") or "").strip()

            page_txt = f"Page {page}" if page else "Page —"
            section_txt = f"— {section}" if section else ""

            st.markdown(f"""
            <div class="cite-item">
              <span class="page-pill">{page_txt}</span>
              <span class="cite-meta">{section_txt}</span>
              <div class="cite-snippet">{snippet}</div>
            </div>
            """, unsafe_allow_html=True)

# ==================== SESSION ====================
for k, v in {
    "public_user_id": "",
    "role": None,
    "can_query": False,
    "doc_id": None,
    "history": [],
    "q_text": "",
    "lang_code": "fr",  # default FR
    "show_request_form": False,
    "hc_a": None,
    "hc_b": None,
    "rights": [],
    "can_upload_right": False,
    "can_query_right": False,
    "uid_locked": False,
    "processed_token": None,
    "processed_name": None,
    "processed_size": None,
    "context_id": "755890001",
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ==================== STATUS BANNER ====================
uid  = st.session_state["public_user_id"].strip()
role = st.session_state["role"]
rights = set(st.session_state["rights"])
can_upload = st.session_state["can_upload_right"]
can_query_right = st.session_state["can_query_right"]
has_access = ("*" in rights) or can_upload or can_query_right

# Access icon (only icon in the Access column)
if "*" in rights:
    access_icon, access_tip = "✅", "all rights"
elif can_upload and can_query_right:
    access_icon, access_tip = "✅", "upload + query"
elif can_upload:
    access_icon, access_tip = "⬆️", "upload only"
elif can_query_right:
    access_icon, access_tip = "🔎", "query only"
else:
    access_icon, access_tip = "⛔", "no rights"

rights_value = "*" if "*" in rights else (", ".join(sorted(rights)) if rights else "—")

cols = st.columns(3, gap="large")  # gives space between items
with cols[0]:
    st.markdown(f"**Role:** {role or 'unknown'}")
with cols[1]:
    st.markdown(f"**Access:** {access_icon}")
with cols[2]:
    st.markdown(f"**Rights:** {rights_value}")

# little vertical breathing room below the row
st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

# ==================== SIDEBAR ====================
with st.sidebar:
    st.subheader("User")
    if not st.session_state.uid_locked:
        st.session_state.public_user_id = st.text_input(
            "User ID",
            value=st.session_state.public_user_id,
            placeholder="Enter the ID you received to use the tool",
            help="An ID can be requested by email or by clicking on request button",
            key="user_id_input",
        )
    else:
        st.text_input(
            "User ID (locked)",
            value=_mask_first_last(st.session_state.public_user_id),
            disabled=True,
        )
        st.caption("🔒 User ID is locked. Use **Reset** to change it.")

    #st.subheader("Language")
    #lang_choice = st.radio(
    #    "Define the language you would like to get your responses in.",
    #    options=["NL","FR","DE","EN"],
    #    index=["NL","FR","DE","EN"].index(st.session_state.get("lang_code","nl").upper()) if st.session_state.get("lang_code") else 3,
    #    horizontal=True,
    #    help="The pdf you'll submit is independant of the language you chose here."
    #)
    #st.session_state.lang_code = LANG_LABEL_TO_CODE[lang_choice]

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button(
            "Start session",
            type="primary",
            disabled=(st.session_state.uid_locked or len(st.session_state.public_user_id.strip()) < 3),
        ):
            uid = st.session_state.public_user_id.strip()
            status = fetch_user_access_via_admin(uid)

            if status.get("error"):
                st.session_state.role = None
                st.session_state.rights = []
                st.session_state.can_upload_right = False
                st.session_state.can_query_right  = False
                st.toast("Admin check failed (missing/invalid admin key or /admin/keys error).", icon="⚠️")
            else:
                st.session_state.role   = status.get("role")
                st.session_state.rights = status.get("rights") or []
                st.session_state.can_upload_right = bool(status.get("can_upload"))
                st.session_state.can_query_right  = bool(status.get("can_query"))
                st.session_state.can_query = st.session_state.can_query_right

                rights = set(st.session_state.rights)
                if "*" in rights:
                    label, icon = "✅ all rights", "✅"
                elif st.session_state.can_upload_right and st.session_state.can_query_right:
                    label, icon = "✅ upload+query", "✅"
                elif st.session_state.can_upload_right:
                    label, icon = "✅ upload only", "✅"
                elif st.session_state.can_query_right:
                    label, icon = "✅ query only", "✅"
                else:
                    label, icon = "⛔ no rights", "⚠️"
                st.toast(f"Role: {st.session_state.role or 'unknown'} — {label}", icon=icon)

            # 🔒 Lock the ID after attempting to start the session
            st.session_state.uid_locked = True
            st.rerun()

        with c2:
            if st.button("Request access", disabled=has_access, help="Disabled because you already have access."):
                st.session_state.show_request_form = True
                if not (st.session_state.hc_a and st.session_state.hc_b):
                    st.session_state.hc_a = random.randint(3, 9)
                    st.session_state.hc_b = random.randint(2, 8)
            #if has_access:
            #    st.caption("✅ You already have access.")

        with c3:
            if st.button("Reset session"):
                # Fully reset: clear widget + app state
                for k in (
                    "user_id_input",        # ← the text_input widget's state
                    "public_user_id",
                    "role",
                    "rights",
                    "can_upload_right",
                    "can_query_right",
                    "can_query",
                    "doc_id",
                    "history",
                    "q_text",
                    "show_request_form",
                    "hc_a",
                    "hc_b",
                    "uid_locked",
                    "processed_token",
                    "processed_name",
                    "processed_size"
                ):
                    st.session_state.pop(k, None)
                st.rerun()

    #with st.expander("⚙️ Advanced (UI ↔ API)"):
    #    st.code("\n".join([
    #       f"API_BASE          = {API_BASE!r}",
    #       f"USER_ID_HEADER    = {USER_ID_HEADER!r}",
    #       f"ROLE_PATH_GET     = {ROLE_PATH_GET!r}",
    #       f"ROLE_PATH_REQUEST = {ROLE_PATH_REQUEST!r}",
    #       f"UPLOAD_PATH       = {UPLOAD_PATH!r}",
    #       f"QUERY_PATH        = {QUERY_PATH!r}",
    #       f"UPLOAD_FILE_FIELD = {UPLOAD_FILE_FIELD!r}",
    #       f"MIN_QUESTION_CHARS= {MIN_QUESTION_CHARS!r}",
    #       f"lang_hint (current)= {st.session_state.lang_code!r}",
    #   ]), language="python")

#    with st.expander("⚙️ Debug (admin)", expanded=False):
#        st.caption(f"API_BASE_URL: {API_BASE}")
#        st.caption(f"Admin key present: {bool(ADMIN_KEY)}  ({_mask(ADMIN_KEY)})")

#        if st.button("Test /admin/keys", use_container_width=True):
#            r = _req("GET", "/admin/keys", headers={"X-API-Key": ADMIN_KEY or ""})
#            st.write("Status:", getattr(r, "status_code", 0))
#            try:
#                st.json(r.json())
#            except Exception:
#                st.code(getattr(r, "text", ""))

# --- NEW: Access request form ---
    if st.session_state.show_request_form:
        st.markdown("### ✉️ Access request")
        with st.form("role_request_form", clear_on_submit=False):
            colA, colB = st.columns(2)
            with colA:
                first = st.text_input("First name*", max_chars=40, placeholder="Jane")
                email = st.text_input("Email*", max_chars=254, placeholder="jane.doe@example.com")
                mobile = st.text_input("Mobile phone (optional)", max_chars=20, placeholder="+32...")
            with colB:
                last = st.text_input("Last name*", max_chars=40, placeholder="Doe")
                company = st.text_input("Company / Organization*", max_chars=80, placeholder="example")
                reason = st.text_area("Reason for request*", max_chars=500, height=120, placeholder="Tell us briefly why you need access…")

            # Simple human check (math)
            a, b = st.session_state.hc_a, st.session_state.hc_b
            human_ok = st.number_input(f"Human check: what is {a} + {b} ?", step=1, format="%d", value=0)

            submitted = st.form_submit_button("Submit request", type="primary")

            if submitted:
                errors = []

                # Basic validations
                if not NAME_RE.match(first.strip()):
                    errors.append("First name invalid (2–40 letters, spaces, hyphens, apostrophes).")
                if not NAME_RE.match(last.strip()):
                    errors.append("Last name invalid (2–40 letters, spaces, hyphens, apostrophes).")
                if not EMAIL_RE.match(email.strip()):
                    errors.append("Please provide a valid email address.")
                if not company.strip():
                    errors.append("Company / Organization is required.")
                if len((reason or "").strip()) < 10:
                    errors.append("Reason should be at least 10 characters.")
                if mobile.strip() and not PHONE_RE.match(mobile.strip()):
                    errors.append("Mobile phone must be a valid international number (e.g., +3212345678).")
                try:
                    if int(human_ok) != (a + b):
                        errors.append("Human check failed. Please try again.")
                except Exception:
                    errors.append("Human check failed. Please enter a number.")

                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    # Build payload for your backend form submission
                    uid = st.session_state.public_user_id.strip()
                    payload = {
                        "form": "access_request",
                        "user_id": uid,
                        "first_name": first.strip(),
                        "last_name": last.strip(),
                        "email": email.strip(),
                        "company": company.strip(),
                        "reason": reason.strip(),
                        "mobile": mobile.strip() or None,
                        "lang_hint": st.session_state.lang_code,
                    }

                    ok, resp = submit_access_request(uid, payload)

                    if ok:
                        st.success("Thank you! Your request has been sent. We will be shortly in contact.")
                        st.toast("Request recorded by backend.", icon="🗂️")
                        # Hide form after success & reset human check
                        st.session_state.show_request_form = False
                        st.session_state.hc_a = None
                        st.session_state.hc_b = None
                    else:
                        st.error("Sending request failed.")
                        st.caption(str(resp))

if not uid:
    st.info("Enter a **User ID** in the sidebar, then click **Start session**.")
    st.stop()

# ==================== UPLOAD ====================
st.header("📄 Upload PDF")

# Always compute can_upload from session to avoid stale locals
can_upload = bool(st.session_state.can_upload_right)

# Use a stable key so we can reset uploader later if needed
upload = st.file_uploader("Choose a PDF", type="pdf", disabled=not can_upload, key="pdf_uploader")

def _upload_token(u):
    if not u:
        return None
    try:
        size = len(u.getbuffer())  # reliable across reruns
    except Exception:
        size = len(u.getvalue())
    return f"{u.name}:{size}", u.name, size

# Derive current selection token (if any)
if upload:
    current_token, current_name, current_size = _upload_token(upload)
else:
    current_token, current_name, current_size = None, None, None

# Is there a new (unprocessed) selection?
is_new_unprocessed = bool(upload) and (st.session_state.processed_token != current_token)

# --- Persistent processed status badge ---
status_col1, status_col2 = st.columns([0.8, 0.2])

with status_col1:
    if st.session_state.doc_id and not is_new_unprocessed:
        # Show the processed badge even if no file is currently selected
        shown_name = current_name or st.session_state.processed_name or "document"
        st.success(f"Processed ✓ — {shown_name}")
    elif is_new_unprocessed:
        st.warning("New file selected — not processed yet.")
    else:
        st.info("No processed document yet.")

with status_col2:
    # Show "Process PDF" only when a new file is selected
    show_process_btn = can_upload and is_new_unprocessed and (upload is not None)
    if show_process_btn and st.button("Process PDF", type="primary", use_container_width=True):
        files = {UPLOAD_FILE_FIELD: (upload.name, upload.getvalue(), "application/pdf")}

        # ---- ensure API key is attached ----
        api_key = os.getenv("UI_ADMIN_API_KEY") or os.getenv("ADMIN_API_KEY") or ""
        headers = {"X-User-Id": st.session_state.public_user_id.strip()}
        if api_key:
            headers["X-API-Key"] = api_key

        r = _req("POST", UPLOAD_PATH, user_id=st.session_state.public_user_id.strip(), files=files, headers=headers)
        if getattr(r, "ok", False):
            st.session_state.doc_id = (r.json() or {}).get("doc_id")
            st.session_state.processed_token = current_token
            st.session_state.processed_name  = current_name
            st.session_state.processed_size  = current_size
            st.toast("Processed ✓", icon="✅")
            st.rerun()  # immediately reflect that Q&A can be shown
        else:
            st.error(f"Upload failed: {getattr(r, 'status_code', '?')} {getattr(r, 'text', '')}")
# ==================== Context & language ====================
CONTEXTS = {
    "755890001": {
        "label_en":"📜 Legal text",
        "label_fr":"📜 Texte juridique",
        "label_nl":"📜 Juridische tekst",
        "label_de":"📜 Rechtstext",
        "followup_hint":"Ask for article numbers, definitions, exceptions, effective dates."
        },
    "755890002": {
        "label_en":"🧩 Specifications",
        "label_fr":"🧩 Cahier des charges",
        "label_nl":"🧩 Lastenboek",
        "label_de":"🧩 Pflichtenheft",
        "followup_hint":"Probe priorities, acceptance criteria, dependencies, deadlines."
        },
    "755890003": {
        "label_en":"🔧 User manual",
        "label_fr":"🔧 Mode d’emploi",
        "label_nl":"🔧 Handleiding",
        "label_de":"🔧 Bedienungsanleitung",
        "followup_hint":"Offer variants per OS/model, safety notes, quick-start tips."
        },
    "755890004": {
        "label_en":"📘 Course",
        "label_fr":"📘 Cours",
        "label_nl":"📘 Cursus",
        "label_de":"📘 Kurs",
        "followup_hint":"Suggest exercises, prerequisite refreshers, exam-style questions."
        },
    "755890005": {
        "label_en":"📊 Financial report",
        "label_fr":"📊 Rapport financier",
        "label_nl":"📊 Financieel rapport",
        "label_de":"📊 Finanzbericht",
        "followup_hint":"Probe unusual variances, accounting policies, and segment notes."
        },
    "755890006": {
        "label_en":"🔬 Scientific paper",
        "label_fr":"🔬 Article scientifique",
        "label_nl":"🔬 Wetenschappelijk artikel",
        "label_de":"🔬 Wissenschaftliche Arbeit",
        "followup_hint":"Ask about sample size, controls, effect sizes, confidence intervals."
        },
    "755890007": {
        "label_en":"📑 Policy / Compliance",
        "label_fr":"📑 Politique / Conformité",
        "label_nl":"📑 Beleid / Compliance",
        "label_de":"📑 Richtlinie / Compliance",
        "followup_hint":"Probe ownership, timelines, and evidence needed for compliance."
        },
}
LANG_LABEL_TO_CODE = {"NL":"nl","FR":"fr","DE":"de","EN":"en"}

def _ctx_label(cid: str, lang_code: str) -> str:
    d = CONTEXTS.get(cid, {})
    key = f"label_{(lang_code or 'en').lower()}"
    return d.get(key) or d.get("label_en") or cid

def _choose_followup(q2: str):
    st.session_state.q_text = q2
    st.session_state.followup_q = q2    # so the prefill block above runs
    st.session_state._from_followup = True   # optional: to auto-run
    st.rerun()

# ==================== Q&A ====================
can_show_qna = bool(st.session_state.get("doc_id")) and not is_new_unprocessed

if can_show_qna:
    st.subheader("⚙️ Context & language")

    # ---- Language (moved from sidebar to main)
    lang_choice = st.radio(
        "Answer language",
        options=["NL","FR","DE","EN"],
        index=["NL","FR","DE","EN"].index(st.session_state.get("lang_code","nl").upper()) if st.session_state.get("lang_code") else 1,
        horizontal=True,
        help="This does not depend on the PDF’s language; it controls the answer language."
    )
    st.session_state.lang_code = LANG_LABEL_TO_CODE[lang_choice]

    # ---- Context (dropdown)
    label_key = f"label_{st.session_state.lang_code.lower()}"
    ctx_ids = list(CONTEXTS.keys())
    # current index
    cur_idx = next((i for i, cid in enumerate(ctx_ids) if cid == st.session_state.context_id), 0)
    selected_ctx_id = st.selectbox(
        "Context",
        options=ctx_ids,
        index=cur_idx,
        format_func=lambda cid: CONTEXTS[cid].get(label_key) or CONTEXTS[cid]["label_en"],
        help="Choose how the assistant should read your document."
    )
    st.session_state.context_id = selected_ctx_id

    # (optional) tiny caption with the chosen label
    st.caption(f"Selected: {_ctx_label(st.session_state.context_id, st.session_state.lang_code)}")
    st.header("❓ Ask a question")
    auto_q = st.session_state.pop("followup_q", None)
    if auto_q:
        st.session_state.q_text = auto_q
    q = st.text_area("Your question", key="q_text", height=120,
                     placeholder=f"At least {MIN_QUESTION_CHARS} characters…",
                     disabled=not can_query_right)
    qlen = len((q or "").strip())
    st.caption(("📝 " if qlen < MIN_QUESTION_CHARS else "✅ ") + f"{qlen}/{MIN_QUESTION_CHARS}")

    c1, c2, c3 = st.columns([1,1,1])
    with c1: do_verify    = st.checkbox("Verification", value=True, key="opt_verify", disabled=not can_query_right)
    with c2: do_followups = st.checkbox("Suggest follow-up questions", value=True, key="opt_followups", disabled=not can_query_right)
    with c3: run_click    = st.button("Get answer", type="primary", disabled=(not can_query_right or qlen < MIN_QUESTION_CHARS))

    should_run = run_click

    if should_run:
        t_total_start = time.perf_counter()
        # Create placeholders to remove later
        status_ph = st.empty()
        prog_ph = st.empty()

        try:
            # Show a temporary status + progress while we prepare/send/wait
            with status_ph.status("🔄 Working on your answer…", expanded=True) as status:
                #prog = prog_ph.progress(0)
                #status.write("Preparing answer")
                #prog.progress(10)
                payload = {
                    "doc_id": st.session_state.doc_id,
                    "question": q,
                    "do_verify": do_verify,
                    "do_followups": do_followups,
                    "lang_hint": st.session_state.lang_code,
                    "context_id": st.session_state.context_id,
                }

                status.update(label="🔄 Working on your answer…")
                #prog.progress(40)

                api_key = (os.getenv("UI_ADMIN_API_KEY") or os.getenv("ADMIN_API_KEY") or "").strip()
                headers = {"X-User-Id": uid}
                if api_key:
                    headers["X-API-Key"] = api_key

                # ⏱️ API timing
                t_api_start = time.perf_counter()
                r = _req("POST", QUERY_PATH, user_id=uid, json=payload, headers=headers)
                api_elapsed = time.perf_counter() - t_api_start

                #prog.progress(100)
                total_elapsed = time.perf_counter() - t_total_start
                status.update(label=f"✅ Answer received in {_fmt_secs(total_elapsed)}", state="complete")

            prog_ph.empty()
            status_ph.empty()

            if not getattr(r, "ok", False):
                status.update(label="❌ Request failed", state="error")
                st.error(f"Query failed: {r.status_code} {r.text}")
            else:
                #status.update(label="✅ Answer received — rendering…", state="running")
                res = r.json() or {}
                st.subheader("💬 Answer")
                st.write(res.get("answer", ""))
                conf = res.get("confidence_score", 0)
                model = res.get("model") or res.get("model_used") or "unknown"
                total_elapsed = time.perf_counter() - t_total_start
                m1, m2, m3 = st.columns([1,1,1])
                with m1: st.caption(f'🎯 Confidence: {conf if isinstance(conf, (int,float)) else str(conf)}')
                with m2: st.caption(f'🧠 Model: {model}')
                with m3: st.caption(f'⏱️ Time: {_fmt_secs(total_elapsed)}')
                #with m3: st.caption(f'🌐 Language hint: {st.session_state.lang_code.upper()}')

                # Verification & citations
                show_verification(res.get("verification"))
                show_citations(res.get("citations"))

                # Follow-ups (clickable) — this block stays as-is; see tweak below
                f = res.get("followups") or {}
                clarify = f.get("clarify") or []
                deepen  = f.get("deepen") or []
                if clarify or deepen:
                    st.subheader("🔍 Follow-up questions")
                    st.markdown("""
                    <style>
                    .fu-card{border:1px solid rgba(49,51,63,.18);border-radius:.6rem;padding:.75rem 1rem;margin-top:.25rem}
                    .fu-title{font-weight:700;margin:0 0 .5rem}
                    .fu-empty{opacity:.6}
                    </style>
                    """, unsafe_allow_html=True)

                    col_c, col_d = st.columns(2, gap="large")

                    with col_c:
                        st.markdown('<div class="fu-card"><div class="fu-title">🧼 Clarify</div>', unsafe_allow_html=True)
                        if clarify:
                            for i, q2 in enumerate(clarify, 1):
                                if st.button(
                                    q2,
                                    key=f"clarify_{i}_{abs(hash(q2))}",
                                    use_container_width=True,
                                    on_click=_choose_followup,
                                    args=(q2,),
                                    ):
                                    st.session_state.followup_q = q2   # triggers auto-run on next render
                                    st.session_state.q_text = q2
                                    st.rerun()
                        else:
                            st.markdown('<div class="fu-empty">No clarify suggestions</div>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                    with col_d:
                        st.markdown('<div class="fu-card"><div class="fu-title">🧠 Deepen</div>', unsafe_allow_html=True)
                        if deepen:
                            for i, q2 in enumerate(deepen, 1):
                                if st.button(
                                    q2,
                                    key=f"deepen_{i}_{abs(hash(q2))}",
                                    use_container_width=True,
                                    on_click=_choose_followup,
                                    args=(q2,),
                                    ):
                                    st.session_state.followup_q = q2   # triggers auto-run on next render
                                    st.session_state.q_text = q2
                                    st.rerun()
                        else:
                            st.markdown('<div class="fu-empty">No deepen suggestions</div>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                # Session history
                st.session_state.history.append({
                    "q": q,
                    "res": res,
                    "ts": time.time(),
                    "total_s": total_elapsed,
                    "api_s": api_elapsed,
                    })

        except Exception as e:
            # Make sure the loaders are gone even on error
            prog_ph.empty()
            status_ph.empty()
            st.error(f"Something went wrong: {type(e).__name__}: {e}")


# ==================== HISTORY ====================
if st.session_state.get("history"):
    st.header("📚 Session history")
    total_count = len(st.session_state.history)
    for idx, item in enumerate(reversed(st.session_state.history), start=1):
        q = item["q"]; res = item["res"]
        with st.expander(f"Q{total_count - idx + 1}: {q[:80]}…"):
            st.write(res.get("answer", ""))
            conf  = res.get("confidence_score", 0)
            model = res.get("model") or res.get("model_used") or "unknown"

            total_s = item.get("total_s")
            api_s   = item.get("api_s")

            st.caption(
                f'🎯 {conf if isinstance(conf,(int,float)) else str(conf)} • '
                f'🧠 {model} • '
                f'⏱️ {_fmt_secs(total_s) if total_s is not None else "—"} '
                #f'• 🔌 {_fmt_secs(api_s) if api_s is not None else "—"}'
            )
