import os
import re
import requests

# ==================== Validators ====================
NAME_RE   = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ' -]{2,40}$")
PHONE_RE  = re.compile(r"^\+?[1-9]\d{7,14}$")  # E.164-like
EMAIL_RE  = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ==================== Config ====================
API_BASE           = os.getenv("API_BASE_URL", "http://localhost:8000")
USER_ID_HEADER     = os.getenv("USER_ID_HEADER", "X-User-Id")
FORM_SUBMIT_PATH = os.getenv("FORM_SUBMIT_PATH", "/forms/submit")


# ==================== HTTP core ====================
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

# ==================== Admin-key lookup for UI ====================
def _get_admin_api_key() -> str | None:
    return os.getenv("UI_ADMIN_API_KEY") or os.getenv("ADMIN_API_KEY")

def fetch_user_access_via_admin(user_id: str) -> dict:
    admin_key = _get_admin_api_key()
    if not admin_key:
        return {"error": "NO_ADMIN_KEY"}
    r = _req("GET", "/admin/keys", headers={"X-API-Key": admin_key})
    if not getattr(r, "ok", False):
        return {"error": f"HTTP_{getattr(r,'status_code',0)}", "detail": getattr(r, "text", "")}
    data = r.json() or {}
    items = data.get("keys") or []
    matches = [it for it in items if it.get("user_id") == user_id and bool(it.get("enabled", True))]
    rights = set(); role = None
    for it in matches:
        rts = set(it.get("rights") or [])
        rights |= rts
        if it.get("role") == "admin" or "*" in rts:
            role = "admin"
    if role != "admin" and matches:
        role = "user"
    return {
        "role": role,
        "rights": sorted(list(rights)),
        "can_upload": ("*" in rights) or ("upload" in rights),
        "can_query":  ("*" in rights) or ("query" in rights),
        "matches": len(matches),
    }

def submit_access_request(user_id: str, payload: dict) -> tuple[bool, dict | str]:
    r = _req("POST", FORM_SUBMIT_PATH, user_id=user_id, json=payload)
    if getattr(r, "ok", False):
        try:
            return True, r.json()
        except Exception:
            return True, {}
    return False, getattr(r, "text", "Request failed")

def _mask_first_last(s: str | None) -> str:
    if not s:
        return "—"
    s = str(s).strip()
    return s[0] + "…" + s[-1] if len(s) >= 2 else s
