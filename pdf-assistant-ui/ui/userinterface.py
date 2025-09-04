import os
from dotenv import load_dotenv
load_dotenv(override=True)
from pathlib import Path
import streamlit as st
st.set_page_config(page_title="PDF Assistant", page_icon="📕", layout="wide")
import time
import random
from helpers import (
    NAME_RE, PHONE_RE, EMAIL_RE,
    _req,
    fetch_user_access_via_admin,
    submit_access_request,
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

st.title("📕 PDF Assistant")
st.caption(
    "Enter your **User ID**. We’ll verify your role & rights server-side and enable features accordingly."
)

# ==================== UI helpers ====================
def show_verification(v: dict | None):
    if not v: return
    ok = v.get("is_accurate")
    conf = v.get("confidence")
    st.markdown(
        f"**Verification:** {'✅ accurate' if ok else '⚠️ please double-check'}"
        + (f" — {conf}" if conf is not None else "")
    )
    if v.get("explanation"): st.write(v["explanation"])
    if v.get("issues_found"): st.caption("Issues: " + ", ".join(v["issues_found"]))

def show_citations(cits: list | None):
    if not cits: return
    st.subheader("📝 Citations")
    for c in cits:
        meta = " · ".join(filter(None, [
            f"ID {c.get('id','?')}",
            f"p.{c.get('page')}" if c.get("page") else None,
            c.get("section") or None
        ]))
        snippet = c.get("snippet", "")
        st.markdown(f"- **{meta}** — {snippet}")

# ==================== SESSION ====================
if "public_user_id" not in st.session_state: st.session_state.public_user_id = ""
if "role" not in st.session_state: st.session_state.role = None
if "can_query" not in st.session_state: st.session_state.can_query = False
if "doc_id" not in st.session_state: st.session_state.doc_id = None
if "history" not in st.session_state: st.session_state.history = []
if "q_text" not in st.session_state: st.session_state.q_text = ""
if "lang_code" not in st.session_state: st.session_state.lang_code = "fr"   # default FR
if "show_request_form" not in st.session_state: st.session_state.show_request_form = False
if "hc_a" not in st.session_state: st.session_state.hc_a = None
if "hc_b" not in st.session_state: st.session_state.hc_b = None
if "rights" not in st.session_state: st.session_state.rights = []
if "can_upload_right" not in st.session_state: st.session_state.can_upload_right = False
if "can_query_right"  not in st.session_state: st.session_state.can_query_right  = False


# ==================== SIDEBAR ====================
with st.sidebar:
    st.subheader("User")
    st.session_state.public_user_id = st.text_input(
        "User ID",
        value=st.session_state.public_user_id,
        placeholder="Enter the ID you received to use the tool",
        help=f"An ID can be requested by email or by clicking on request button"
    )

    st.subheader("Language")
    lang_choice = st.radio(
        "Define the language you would like to get your responses in.",
        options=["NL","FR","DE","EN"],
        index=["NL","FR","DE","EN"].index(st.session_state.get("lang_code","nl").upper()) if st.session_state.get("lang_code") else 3,
        horizontal=True,
        help="The pdf you'll submit is independant of the language you chose here."
    )
    st.session_state.lang_code = LANG_LABEL_TO_CODE[lang_choice]

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Start session", type="primary",
                    disabled=len(st.session_state.public_user_id.strip()) < 3):
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
                # legacy flag used elsewhere
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
    with c2:
        if st.button("Request access"
                     #, disabled=len(st.session_state.public_user_id.strip()) < 3
                     ):
            # Show the form on click; generate a simple human check (math) if not set
            st.session_state.show_request_form = True
            if not (st.session_state.hc_a and st.session_state.hc_b):
                st.session_state.hc_a = random.randint(3, 9)
                st.session_state.hc_b = random.randint(2, 8)

    with c3:
        if st.button("Reset"):
            for k in ("role", "can_query", "doc_id", "history", "q_text", "show_request_form", "hc_a", "hc_b"):
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

# ==================== STATUS BANNER ====================
uid  = st.session_state.public_user_id.strip()
role = st.session_state.role
rights = set(st.session_state.rights or [])
can_upload = st.session_state.can_upload_right
can_query_right = st.session_state.can_query_right

cols = st.columns([1,1,2,3])
with cols[0]: st.metric("User ID", uid or "—")
with cols[1]: st.metric("Role", role or "unknown")
with cols[2]:
    if "*" in rights: acc = "✅ all"
    elif can_upload and can_query_right: acc = "✅ upload+query"
    elif can_upload: acc = "✅ upload only"
    elif can_query_right: acc = "✅ query only"
    else: acc = "⛔ blocked"
    st.metric("Access", acc)
with cols[3]:
    st.metric("Rights", "*" if "*" in rights else (", ".join(sorted(rights)) if rights else "—"))

if not uid:
    #st.info("Enter a **User ID** in the sidebar, then click **Start session**.")
    st.stop()

# ==================== UPLOAD ====================
st.header("📄 Upload PDF")
u1, u2 = st.columns([3,1])
with u1:
    upload = st.file_uploader("Choose a PDF", type="pdf", disabled=not can_upload)
with u2:
    if st.button("Process PDF", disabled=(not can_upload or upload is None)):
        files = {UPLOAD_FILE_FIELD: (upload.name, upload.getvalue(), "application/pdf")}
        r = _req("POST", UPLOAD_PATH, user_id=uid, files=files)
        if r.ok:
            st.session_state.doc_id = (r.json() or {}).get("doc_id")
            st.success(f"Processed ✓  doc_id = {st.session_state.doc_id}")
        else:
            st.error(f"Upload failed: {r.status_code} {r.text}")

# ==================== Q&A ====================
if st.session_state.get("doc_id"):
    st.header("❓ Ask a question")
    q = st.text_area("Your question", key="q_text", height=120,
                     placeholder=f"At least {MIN_QUESTION_CHARS} characters…",
                     disabled=not can_query_right)
    qlen = len((q or "").strip())
    st.caption(("📝 " if qlen < MIN_QUESTION_CHARS else "✅ ") + f"{qlen}/{MIN_QUESTION_CHARS}")

    c1, c2, c3 = st.columns([1,1,1])
    with c1: do_verify    = st.checkbox("Verification", value=True, key="opt_verify", disabled=not can_query_right)
    with c2: do_followups = st.checkbox("Suggest follow-up questions", value=True, key="opt_followups", disabled=not can_query_right)
    with c3: run          = st.button("Get answer", type="primary", disabled=(not can_query_right or qlen < MIN_QUESTION_CHARS))

    if run:
        payload = {
            "doc_id": st.session_state.doc_id,
            "question": q,
            "do_verify": do_verify,
            "do_followups": do_followups,
            "lang_hint": st.session_state.lang_code,
        }
        r = _req("POST", QUERY_PATH, user_id=uid, json=payload)
        if not getattr(r, "ok", False):
            st.error(f"Query failed: {r.status_code} {r.text}")
        else:
            res = r.json() or {}
            st.subheader("💬 Answer")
            st.write(res.get("answer", ""))
            conf = res.get("confidence_score", 0)
            model = res.get("model") or res.get("model_used") or "unknown"
            m1, m2, m3 = st.columns([1,1,1])
            with m1: st.caption(f'🎯 Confidence: {conf if isinstance(conf, (int,float)) else str(conf)}')
            with m2: st.caption(f'🧠 Model: {model}')
            with m3: st.caption(f'🌐 Language hint: {st.session_state.lang_code.upper()}')

            # Verification & citations
            show_verification(res.get("verification"))
            show_citations(res.get("citations"))

            # Follow-ups (clickable)
            f = res.get("followups") or {}
            clarify = f.get("clarify") or []
            deepen  = f.get("deepen") or []
            if clarify or deepen:
                st.subheader("🔍 Follow-up questions")
                a, b = st.columns(2)
                with a:
                    for i, q2 in enumerate(clarify, 1):
                        if st.button(f"{i}. {q2}", key=f"clarify_{i}"):
                            st.session_state.q_text = q2
                            st.rerun()
                with b:
                    for i, q2 in enumerate(deepen, 1):
                        if st.button(f"{i}. {q2}", key=f"deepen_{i}"):
                            st.session_state.q_text = q2
                            st.rerun()

            # Session history
            st.session_state.history.append({"q": q, "res": res, "ts": time.time()})

# ==================== HISTORY ====================
if st.session_state.get("history"):
    st.header("📚 Session history")
    for idx, item in enumerate(reversed(st.session_state.history), start=1):
        q = item["q"]; res = item["res"]
        with st.expander(f"Q{len(st.session_state.history)-idx+1}: {q[:80]}…"):
            st.write(res.get("answer", ""))
            conf = res.get("confidence_score", 0)
            model = res.get("model") or res.get("model_used") or "unknown"
            st.caption(f'🎯 {conf if isinstance(conf, (int,float)) else str(conf)} • 🧠 {model} • 🌐 {st.session_state.lang_code.upper()}')
