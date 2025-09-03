# app_public.py
import os
import time
import requests
import streamlit as st

# ==================== CONFIG ====================
API_BASE            = os.getenv("API_BASE_URL", "http://localhost:8000")
USER_ID_HEADER      = os.getenv("USER_ID_HEADER", "X-User-Id")
ROLE_PATH_GET       = os.getenv("ROLE_PATH_GET", "/me/role")            # fallback to /auth/me if this fails
ROLE_PATH_REQUEST   = os.getenv("ROLE_PATH_REQUEST", "/me/role/request")
UPLOAD_PATH         = os.getenv("UPLOAD_PATH", "/documents")
QUERY_PATH          = os.getenv("QUERY_PATH", "/documents/query")
UPLOAD_FILE_FIELD   = os.getenv("UPLOAD_FILE_FIELD", "pdf")
MIN_QUESTION_CHARS  = int(os.getenv("MIN_QUESTION_CHARS", "10"))

st.set_page_config(page_title="PDF Assistant (Public UI)", page_icon="📕", layout="wide")
st.title("📕 PDF Assistant — Public UI (no login)")
st.caption(
    "Backend verifies your role based on the **User ID** you provide. "
    f"All requests include this ID via the **{USER_ID_HEADER}** header. "
    "If your role isn’t assigned yet, uploading and Q&A will be disabled."
)

# ==================== HELPERS ====================
def _req(method: str, path: str, user_id: str | None = None, **kwargs) -> requests.Response:
    headers = kwargs.pop("headers", {}) or {}
    if user_id:
        headers[USER_ID_HEADER] = user_id
    url = f"{API_BASE}{path}"
    try:
        return requests.request(method, url, headers=headers, timeout=60, **kwargs)
    except requests.RequestException as e:
        class _R:
            ok=False; status_code=0; text=f"Network error: {e}"
            def json(self): return {"error": self.text}
        return _R()

def fetch_role_status(user_id: str) -> dict:
    # 1) Try configured role endpoint
    r = _req("GET", ROLE_PATH_GET, user_id=user_id)
    if r.ok:
        j = r.json()
        # Normalize to {role, can_query}
        if "role" in j and "can_query" in j:
            return {"role": j.get("role"), "can_query": bool(j.get("can_query"))}
        role = j.get("role") or j.get("claims", {}).get("role") or j.get("user", {}).get("role")
        can  = (role in ("user", "admin"))
        return {"role": role, "can_query": can}
    # 2) Fallback to /auth/me if available
    if ROLE_PATH_GET != "/auth/me":
        r2 = _req("GET", "/auth/me", user_id=user_id)
        if r2.ok:
            j = r2.json()
            role = j.get("role") or j.get("claims", {}).get("role") or j.get("user", {}).get("role")
            can  = (role in ("user", "admin"))
            return {"role": role, "can_query": can}
    # 3) If nothing works: no access
    return {"role": None, "can_query": False}

def request_role_access(user_id: str) -> bool:
    r = _req("POST", ROLE_PATH_REQUEST, user_id=user_id)
    return bool(getattr(r, "ok", False))

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
if "lang_code" not in st.session_state: st.session_state.lang_code = "en"   # default EN

LANG_LABEL_TO_CODE = {"NL":"nl","FR":"fr","DE":"de","EN":"en"}

# ==================== SIDEBAR ====================
with st.sidebar:
    st.subheader("User")
    st.session_state.public_user_id = st.text_input(
        "User ID (email or internal ID)",
        value=st.session_state.public_user_id,
        placeholder="e.g., jane@example.com or employee ID",
        help=f"This ID is sent in header {USER_ID_HEADER} to the API to verify your role."
    )

    st.subheader("Language")
    lang_choice = st.radio(
        "Answer language",
        options=["NL","FR","DE","EN"],
        index=["NL","FR","DE","EN"].index(st.session_state.get("lang_code","en").upper()) if st.session_state.get("lang_code") else 3,
        horizontal=True,
        help="This will be sent as lang_hint to the backend."
    )
    st.session_state.lang_code = LANG_LABEL_TO_CODE[lang_choice]

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Start session", type="primary",
                     disabled=len(st.session_state.public_user_id.strip()) < 3):
            status = fetch_role_status(st.session_state.public_user_id.strip())
            st.session_state.role = status.get("role")
            st.session_state.can_query = bool(status.get("can_query"))
            st.toast(
                f"Role: {st.session_state.role or 'unknown'} — "
                + ("access enabled" if st.session_state.can_query else "access blocked"),
                icon="✅" if st.session_state.can_query else "⚠️"
            )
    with c2:
        if st.button("Request access", disabled=len(st.session_state.public_user_id.strip()) < 3):
            ok = request_role_access(st.session_state.public_user_id.strip())
            st.toast("Request sent" if ok else "Request failed", icon="✉️" if ok else "⚠️")
    with c3:
        if st.button("Reset"):
            for k in ("role", "can_query", "doc_id", "history", "q_text"):
                st.session_state.pop(k, None)
            st.rerun()

    with st.expander("⚙️ Advanced (UI ↔ API)"):
        st.code("\n".join([
            f"API_BASE          = {API_BASE!r}",
            f"USER_ID_HEADER    = {USER_ID_HEADER!r}",
            f"ROLE_PATH_GET     = {ROLE_PATH_GET!r}",
            f"ROLE_PATH_REQUEST = {ROLE_PATH_REQUEST!r}",
            f"UPLOAD_PATH       = {UPLOAD_PATH!r}",
            f"QUERY_PATH        = {QUERY_PATH!r}",
            f"UPLOAD_FILE_FIELD = {UPLOAD_FILE_FIELD!r}",
            f"MIN_QUESTION_CHARS= {MIN_QUESTION_CHARS!r}",
            f"lang_hint (current)= {st.session_state.lang_code!r}",
        ]), language="python")

# ==================== STATUS BANNER ====================
uid  = st.session_state.public_user_id.strip()
role = st.session_state.role
can  = st.session_state.can_query

cols = st.columns([1,1,2])
with cols[0]: st.metric("User ID", uid or "—")
with cols[1]: st.metric("Role", role or "unknown")
with cols[2]: st.metric("Access", "✅ enabled" if can else "⛔ blocked")

if not uid:
    st.info("Enter a **User ID** in the sidebar, then click **Start session**.")
    st.stop()

# ==================== UPLOAD ====================
st.header("📄 Upload PDF")
u1, u2 = st.columns([3,1])
with u1:
    upload = st.file_uploader("Choose a PDF", type="pdf", disabled=not can)
with u2:
    if st.button("Process PDF", disabled=(not can or upload is None)):
        files = {UPLOAD_FILE_FIELD: (upload.name, upload.getvalue(), "application/pdf")}
        r = _req("POST", UPLOAD_PATH, user_id=uid, files=files)
        if r.ok:
            st.session_state.doc_id = (r.json() or {}).get("doc_id")
            st.success(f"Processed ✓  doc_id = {st.session_state.doc_id}")
        elif r.status_code == 403 and "NO_ROLE" in r.text:
            st.session_state.can_query = False
            st.error("You don’t have a role yet. Please request access.")
        else:
            st.error(f"Upload failed: {r.status_code} {r.text}")

# ==================== Q&A ====================
if st.session_state.get("doc_id"):
    st.header("❓ Ask a question")
    q = st.text_area(
        "Your question",
        key="q_text",
        height=120,
        placeholder=f"At least {MIN_QUESTION_CHARS} characters…",
        disabled=not can
    )
    qlen = len((q or "").strip())
    st.caption(("📝 " if qlen < MIN_QUESTION_CHARS else "✅ ") + f"{qlen}/{MIN_QUESTION_CHARS}")

    c1, c2, c3 = st.columns([1,1,1])
    with c1: do_verify    = st.checkbox("Verification", value=True, key="opt_verify", disabled=not can)
    with c2: do_followups = st.checkbox("Suggest follow-up questions", value=True, key="opt_followups", disabled=not can)
    with c3: run          = st.button("Get answer", type="primary", disabled=(not can or qlen < MIN_QUESTION_CHARS))

    if run:
        payload = {
            "doc_id": st.session_state.doc_id,
            "question": q,
            "do_verify": do_verify,
            "do_followups": do_followups,
            "lang_hint": st.session_state.lang_code,  # ⬅️ pass selected language
        }
        r = _req("POST", QUERY_PATH, user_id=uid, json=payload)
        if not getattr(r, "ok", False):
            if r.status_code == 403 and "NO_ROLE" in r.text:
                st.session_state.can_query = False
                st.warning("You don’t have a role yet. Please request access in the sidebar.")
            else:
                st.error(f"Query failed: {r.status_code} {r.text}")
        else:
            res = r.json() or {}

            # Answer
            st.subheader("💬 Answer")
            st.write(res.get("answer", ""))

            # Meta
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
