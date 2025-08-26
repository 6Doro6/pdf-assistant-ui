import os, time, requests, streamlit as st
from dotenv import load_dotenv; load_dotenv()
import pyrebase
from utils import _ensure_id_token, api_request

API_BASE = os.getenv("API_BASE_URL","http://localhost:8000")
API_KEY  = os.getenv("API_KEY","")

st.set_page_config(page_title="PDF assistant", page_icon="📕", layout="wide", initial_sidebar_state="collapsed")
st.title("📕 PDF assistant")

FIREBASE = {
    "apiKey": os.getenv("FIREBASE_API_KEY"),
    "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
    "projectId": os.getenv("FIREBASE_PROJECT_ID"),
    "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
    "messagingSenderId": os.getenv("FIREBASE_SENDER_ID"),
    "appId": os.getenv("FIREBASE_APP_ID"),
}
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

fb = pyrebase.initialize_app(FIREBASE)
auth = fb.auth()

# --- Sign in UI (sidebar) ---
if "id_token" not in st.session_state:
    with st.sidebar:
        st.subheader("Sign in")
        email = st.text_input("Email")
        pwd   = st.text_input("Password", type="password")
        if st.button("Sign in", type="primary", disabled=not (email and pwd)):
            user = auth.sign_in_with_email_and_password(email, pwd)
            st.session_state["id_token"] = user["idToken"]
            st.session_state["refresh_token"] = user["refreshToken"]
            # naive expiry tracking (Firebase ID tokens last ~1h)
            st.session_state["id_token_exp"] = time.time() + 55*60
            st.session_state["email"] = email
            st.rerun()
else:
    st.sidebar.success(f"Signed in: {st.session_state.email}")
    if st.sidebar.button("Sign out"):
        for k in ("id_token","refresh_token","id_token_exp","email","doc_id"):
            st.session_state.pop(k, None)
        st.rerun()

with st.sidebar:
    st.text_input("API base", API_BASE, key="base", help="Backend base URL")
    st.text_input("API key", API_KEY, key="key", type="password")

st.header("📄 Upload PDF")
upload = st.file_uploader("Choose a PDF", type="pdf")
if upload and st.button("Process"):
    r = api_request(
        "POST", "/v1/documents",
        files={"pdf": (up.name, up.getvalue(), "application/pdf")}
    )
    if r.ok:
        st.session_state.doc_id = r.json()["doc_id"]
        st.success(f"Processed. doc_id={st.session_state.doc_id}")
    else:
        st.error(f"Upload failed: {r.status_code} {r.text}")

if st.session_state.get("doc_id"):
    st.header("❓ Ask a question")
    q = st.text_area("Your question", key="q_text", height=100)
    col1, col2 = st.columns([1,1])
    with col1:
        do_verify = st.checkbox("Verify", value=True, key="opt_verify")
    with col2:
        do_followups = st.checkbox("Follow-ups", value=True, key="opt_followups")
    run = st.button("Get Answer", type="primary", disabled=not q.strip())
    if run:
        payload = {
            "doc_id": st.session_state.doc_id,
            "question": q,
            "do_verify": do_verify,
            "do_followups": do_followups,
        }
        r = requests.post(f"{st.session_state.base}/v1/queries", json=payload, headers={"X-API-Key": st.session_state.key})
        if not r.ok:
            st.error(f"Query failed: {r.status_code} {r.text}")
        else:
            res = r.json()
            st.subheader("💬 Answer")
            st.write(res["answer"])
            st.caption(f'🎯 Confidence: {res.get("confidence_score",0):.2f}')
            if res.get("verification"):
                v = res["verification"]
                st.markdown(f"**Verification:** {'✅ Accurate' if v['is_accurate'] else '❌ Issues found'} — {v['confidence']}")
                st.write(v["explanation"])
            if res.get("citations"):
                st.subheader("📝 Citations")
                for c in res["citations"]:
                    st.markdown(f"- **ID {c['id']}** · p.{c.get('page','?')} · {c.get('section','')} — {c.get('snippet','')}")
            if res.get("followups"):
                st.subheader("🔍 Follow-up questions")
                for i, q2 in enumerate(res["followups"].get("clarify", []), 1):
                    if st.button(f"{i}. {q2}", key=f"clarify_{i}"):
                        st.session_state.q_text = q2; st.rerun()
                for i, q2 in enumerate(res["followups"].get("deepen", []), 1):
                    if st.button(f"{i}. {q2}", key=f"deepen_{i}"):
                        st.session_state.q_text = q2; st.rerun()
