import os, time, requests, streamlit as st
from dotenv import load_dotenv; load_dotenv()
import pyrebase
from utils import api_request

API_BASE = os.getenv("API_BASE_URL","http://localhost:8000")

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
fb = pyrebase.initialize_app(FIREBASE)
auth = fb.auth()

# ---------- Sign in ----------
if "id_token" not in st.session_state:
    with st.sidebar:
        st.subheader("Sign in")
        email = st.text_input("Email")
        pwd   = st.text_input("Password", type="password")
        if st.button("Sign in", type="primary", disabled=not (email and pwd)):
            user = auth.sign_in_with_email_and_password(email, pwd)
            st.session_state["id_token"] = user["idToken"]
            st.session_state["refresh_token"] = user["refreshToken"]
            st.session_state["id_token_exp"] = time.time() + 55*60
            st.session_state["email"] = email
            # UID ophalen
            info = auth.get_account_info(user["idToken"])
            st.session_state["uid"] = info["users"][0]["localId"]
            st.rerun()
else:
    st.sidebar.success(f"Ingelogd: {st.session_state.email}")
    if st.sidebar.button("Sign out"):
        for k in ("id_token","refresh_token","id_token_exp","email","uid","doc_id","history","q_text"):
            st.session_state.pop(k, None)
        st.rerun()

# ---------- Per-user vendor key ----------
st.sidebar.markdown("---")
st.sidebar.subheader("🔑 Mijn LLM-key")
colA, colB = st.sidebar.columns([1,1])
with colA:
    provider = st.selectbox("Provider", ["openai","google"], index=0, key="prov")
with colB:
    show = st.checkbox("Toon key", value=False)
key_val = st.sidebar.text_input("API key", type="default" if show else "password")

c1, c2, c3 = st.sidebar.columns(3)
with c1:
    if st.button("Opslaan", use_container_width=True, disabled=("id_token" not in st.session_state)):
        r = api_request("POST","/me/key", json={"provider": st.session_state.prov, "api_key": key_val})
        st.sidebar.success("Key opgeslagen") if r.ok else st.sidebar.error(r.text)
with c2:
    if st.button("Ophalen", use_container_width=True, disabled=("id_token" not in st.session_state)):
        r = api_request("GET","/me/key")
        if r.ok:
            data = r.json()
            st.sidebar.info(f"Status: {'✅' if data.get('has_key') else '❌'} • Provider: {data.get('provider') or '-'}")
        else:
            st.sidebar.error(r.text)
with c3:
    if st.button("Verwijderen", use_container_width=True, disabled=("id_token" not in st.session_state)):
        r = api_request("DELETE","/me/key")
        st.sidebar.success("Key verwijderd") if r.ok else st.sidebar.error(r.text)

# ---------- Upload PDF ----------
st.header("📄 Upload PDF")
upload = st.file_uploader("Kies een PDF", type="pdf")
if upload and st.button("Verwerken", disabled=("id_token" not in st.session_state)):
    r = api_request("POST", "/documents", files={"pdf": (upload.name, upload.getvalue(), "application/pdf")})
    if r.ok:
        st.session_state.doc_id = r.json()["doc_id"]
        st.success(f"Verwerkt. doc_id={st.session_state.doc_id}")
    else:
        st.error(f"Upload mislukt: {r.status_code} {r.text}")

# ---------- Q&A ----------
if "history" not in st.session_state: st.session_state.history = []

if st.session_state.get("doc_id"):
    st.header("❓ Stel een vraag")
    q = st.text_area("Je vraag", key="q_text", height=120, placeholder="Min. 10 karakters…")
    MIN_CHARS = 10
    qlen = len((q or "").strip())
    st.caption(("📝 " if qlen<MIN_CHARS else "✅ ") + f"{qlen}/{MIN_CHARS}")

    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        do_verify = st.checkbox("Verificatie", value=True, key="opt_verify")
    with col2:
        do_followups = st.checkbox("Vervolgvraag suggesties", value=True, key="opt_followups")
    with col3:
        run = st.button("Antwoord ophalen", type="primary", disabled=(qlen<MIN_CHARS))

    if run:
        payload = {
            "doc_id": st.session_state.doc_id,
            "question": q,
            "do_verify": do_verify,
            "do_followups": do_followups,
        }
        r = api_request("POST", "/documents/query", json=payload)
        if not r.ok:
            st.error(f"Query fout: {r.status_code} {r.text}")
        else:
            res = r.json()
            # ------- Output -------
            st.subheader("💬 Antwoord")
            st.write(res.get("answer",""))
            st.caption(f'🎯 Confidence: {res.get("confidence_score",0):.2f}')
            st.caption(f'🧠 Model: {res.get("model") or res.get("model_used") or "onbekend"}')

            if res.get("verification"):
                v = res["verification"]
                st.markdown(f"**Verificatie:** {'✅ correct' if v.get('is_accurate') else '❌ mogelijk onjuist'} — {v.get('confidence')}")
                if v.get("explanation"): st.write(v["explanation"])
                if v.get("issues_found"): st.caption("Issues: " + ", ".join(v["issues_found"]))

            if res.get("citations"):
                st.subheader("📝 Citaten")
                for c in res["citations"]:
                    st.markdown(f"- **ID {c.get('id','?')}** · p.{c.get('page','?')} · {c.get('section','')} — {c.get('snippet','')}")

            # Follow-ups klikbaar
            if res.get("followups"):
                st.subheader("🔍 Vervolgvragen")
                cl = res["followups"].get("clarify", [])
                dp = res["followups"].get("deepen", [])
                colA, colB = st.columns(2)
                with colA:
                    for i, q2 in enumerate(cl, 1):
                        if st.button(f"{i}. {q2}", key=f"clarify_{i}"):
                            st.session_state.q_text = q2; st.rerun()
                with colB:
                    for i, q2 in enumerate(dp, 1):
                        if st.button(f"{i}. {q2}", key=f"deepen_{i}"):
                            st.session_state.q_text = q2; st.rerun()

            # Historiek
            st.session_state.history.append({"q": q, "res": res, "ts": time.time()})

# ---------- Historiek tonen ----------
if st.session_state.get("history"):
    st.header("📚 Historiek (sessie)")
    for idx, item in enumerate(reversed(st.session_state.history), start=1):
        q = item["q"]; res = item["res"]
        with st.expander(f"Q{len(st.session_state.history)-idx+1}: {q[:80]}…"):
            st.write(res.get("answer",""))
            st.caption(f'🎯 {res.get("confidence_score",0):.2f} • 🧠 {res.get("model") or res.get("model_used") or "onbekend"}')
