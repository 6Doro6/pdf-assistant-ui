import os, time, requests, streamlit as st
from dotenv import load_dotenv; load_dotenv()

API_BASE = os.getenv("API_BASE_URL","http://localhost:8000")

def _ensure_id_token() -> str:
    """Return a valid (fresh) ID token; refresh if close to expiry."""
    if "id_token" not in st.session_state:
        raise RuntimeError("Not signed in")
    if time.time() > st.session_state.get("id_token_exp", 0) - 60:
        from app import auth  # pyrebase auth uit app.py
        refreshed = auth.refresh(st.session_state["refresh_token"])
        st.session_state["id_token"] = refreshed["idToken"]
        st.session_state["id_token_exp"] = time.time() + 55*60
    return st.session_state["id_token"]

def api_request(method: str, path: str, **kwargs) -> requests.Response:
    """Requests wrapper that injects the Firebase ID token header."""
    token = _ensure_id_token()
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {token}"
    url = f"{API_BASE}{path}"
    resp = requests.request(method, url, headers=headers, **kwargs)
    if resp.status_code == 401:
        st.warning("Your session expired. Please sign in again.")
        for k in ("id_token","refresh_token","id_token_exp","email"):
            st.session_state.pop(k, None)
    return resp
