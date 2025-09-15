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

# === UI language & i18n ===
if "ui_lang" not in st.session_state:
    # Default UI language: map from your existing answer-language code if present
    st.session_state.ui_lang = (st.session_state.get("lang_code") or "en")

UI_LANGS = {"en":"English", "fr":"Français", "nl":"Nederlands", "de":"Deutsch"}

I18N = {
    # App / navigation
    "app_title":   {"en":"📕 PDF Assistant", "fr":"📕 Assistant PDF", "nl":"📕 PDF-assistent", "de":"📕 PDF-Assistent"},
    "nav_home":    {"en":"📕 PDF Assistant", "fr":"📕 Assistant PDF", "nl":"📕 PDF-assistent", "de":"📕 PDF-Assistent"},
    "nav_how":     {"en":"📘 How to use",    "fr":"📘 Mode d’emploi",  "nl":"📘 Handleiding",   "de":"📘 Anleitung"},

    # Sidebar — section
    "sidebar_user":        {"en":"Access information", "fr":"Données d'accès", "nl":"Gebruikerstoegang", "de":"Benutzer"},
    "user_id":             {"en":"User ID", "fr":"Identifiant", "nl":"Gebruikers-ID", "de":"Benutzer-ID"},
    "user_id_ph":          {"en":"Enter the ID you received to use the tool",
                            "fr":"Entrez l’identifiant reçu pour utiliser l’outil",
                            "nl":"Voer de ontvangen ID in om de tool te gebruiken",
                            "de":"Geben Sie die erhaltene ID ein, um das Tool zu nutzen"},
    "user_id_help":        {"en":"An ID can be requested by email or by clicking on request button",
                            "fr":"Un identifiant peut être demandé par e-mail ou via le bouton de demande",
                            "nl":"Een ID kan per e-mail of via de aanvraagknop worden aangevraagd",
                            "de":"Eine ID kann per E-Mail oder über die Anforderungsschaltfläche angefordert werden"},
    "user_id_locked":      {"en":"User ID (locked)", "fr":"Identifiant (verrouillé)", "nl":"Gebruikers-ID (vergrendeld)", "de":"Benutzer-ID (gesperrt)"},
    "user_locked_note":    {"en":"🔒 User ID is locked. Use **Reset** to change it.",
                            "fr":"🔒 Identifiant verrouillé. Utilisez **Réinitialiser** pour le modifier.",
                            "nl":"🔒 ID is vergrendeld. Gebruik **Reset** om te wijzigen.",
                            "de":"🔒 ID ist gesperrt. Mit **Zurücksetzen** ändern."},

    # Sidebar — buttons
    "btn_start":   {"en":"Start session", "fr":"Démarrer la session", "nl":"Sessie starten", "de":"Sitzung starten"},
    "btn_request": {"en":"Request access", "fr":"Demander l’accès", "nl":"Toegang aanvragen", "de":"Zugang anfordern"},
    "btn_reset":   {"en":"Reset session", "fr":"Réinitialiser", "nl":"Reset sessie", "de":"Sitzung zurücksetzen"},
    "already_have_access_help": {"en":"Disabled because you already have access.",
                                 "fr":"Désactivé car vous avez déjà l’accès.",
                                 "nl":"Uitgeschakeld omdat je al toegang hebt.",
                                 "de":"Deaktiviert, da Sie bereits Zugang haben."},

    # Status banner
    "status_role":   {"en":"Role", "fr":"Rôle", "nl":"Rol", "de":"Rolle"},
    "status_access": {"en":"Access", "fr":"Accès", "nl":"Toegang", "de":"Zugriff"},
    "status_rights": {"en":"Rights", "fr":"Droits", "nl":"Rechten", "de":"Berechtigungen"},

    # Upload
    "h_upload":       {"en":"📄 Upload PDF", "fr":"📄 Charger un PDF", "nl":"📄 PDF uploaden", "de":"📄 PDF hochladen"},
    "uploader_label": {"en":"Choose a PDF", "fr":"Choisissez un PDF", "nl":"Kies een PDF", "de":"Wählen Sie eine PDF"},
    "btn_process":    {"en":"Process PDF", "fr":"Traiter le PDF", "nl":"PDF verwerken", "de":"PDF verarbeiten"},
    "no_processed":   {"en":"No processed document yet.", "fr":"Aucun document traité.", "nl":"Nog geen verwerkt document.", "de":"Noch kein verarbeitetes Dokument."},
    "new_selected":   {"en":"New file selected — not processed yet.", "fr":"Nouveau fichier sélectionné — non traité.", "nl":"Nieuw bestand geselecteerd — nog niet verwerkt.", "de":"Neue Datei ausgewählt — noch nicht verarbeitet."},
    "processed":      {"en":"Processed ✓", "fr":"Traité ✓", "nl":"Verwerkt ✓", "de":"Verarbeitet ✓"},
    "upload_failed":  {"en":"Upload failed", "fr":"Échec du chargement", "nl":"Upload mislukt", "de":"Upload fehlgeschlagen"},

    # Context & language (UI)
    "h_ctx_lang":     {"en":"⚙️ Context & language", "fr":"⚙️ Contexte & langue", "nl":"⚙️ Context & taal", "de":"⚙️ Kontext & Sprache"},
    "answer_lang":    {"en":"Answer language", "fr":"Langue de réponse", "nl":"Antwoordtaal", "de":"Antwortsprache"},
    "answer_lang_help":{"en":"This does not depend on the PDF’s language; it controls the answer language.",
                        "fr":"Indépendant de la langue du PDF ; définit la langue de réponse.",
                        "nl":"Staat los van de taal van de PDF; bepaalt de antwoordtaal.",
                        "de":"Unabhängig von der PDF-Sprache; steuert die Antwortsprache."},
    "ctx_label":      {"en":"Context", "fr":"Contexte", "nl":"Context", "de":"Kontext"},
    "ctx_help":       {"en":"Choose how the assistant should read your document.",
                       "fr":"Choisissez comment l’assistant doit lire votre document.",
                       "nl":"Kies hoe de assistent je document moet lezen.",
                       "de":"Wählen Sie, wie der Assistent Ihr Dokument lesen soll."},
    "selected":       {"en":"Selected", "fr":"Sélection", "nl":"Gekozen", "de":"Auswahl"},

    # Q&A
    "h_ask":          {"en":"❓ Ask a question", "fr":"❓ Poser une question", "nl":"❓ Stel een vraag", "de":"❓ Frage stellen"},
    "your_q":         {"en":"Your question", "fr":"Votre question", "nl":"Je vraag", "de":"Deine Frage"},
    "q_ph":           {"en":"At least {n} characters…", "fr":"Au moins {n} caractères…", "nl":"Minstens {n} tekens…", "de":"Mindestens {n} Zeichen…"},
    "verify":         {"en":"Verification", "fr":"Vérification", "nl":"Verificatie", "de":"Verifikation"},
    "followups":      {"en":"Suggest follow-up questions", "fr":"Suggérer des questions de suivi", "nl":"Vervolgvragen voorstellen", "de":"Rückfragen vorschlagen"},
    "btn_answer":     {"en":"Get answer", "fr":"Obtenir la réponse", "nl":"Antwoord ophalen", "de":"Antwort abrufen"},
    "working":        {"en":"Working on your answer…", "fr":"Préparation de votre réponse…", "nl":"Bezig met je antwoord…", "de":"Antwort wird vorbereitet…"},
    "answer_received":{"en":"Answer received in {s}", "fr":"Réponse reçue en {s}", "nl":"Antwoord ontvangen in {s}", "de":"Antwort erhalten in {s}"},
    "req_failed":     {"en":"Request failed", "fr":"Échec de la requête", "nl":"Aanvraag mislukt", "de":"Anfrage fehlgeschlagen"},
    "query_failed":   {"en":"Query failed", "fr":"Échec de la requête", "nl":"Aanvraag mislukt", "de":"Anfrage fehlgeschlagen"},

    # Answer + meta
    "h_answer":       {"en":"💬 Answer", "fr":"💬 Réponse", "nl":"💬 Antwoord", "de":"💬 Antwort"},
    "meta_conf":      {"en":"Confidence", "fr":"Confiance", "nl":"Betrouwbaarheid", "de":"Konfidenz"},
    "meta_model":     {"en":"Model", "fr":"Modèle", "nl":"Model", "de":"Modell"},
    "meta_time":      {"en":"Time", "fr":"Durée", "nl":"Tijd", "de":"Zeit"},

    # Follow-ups
    "h_fu":           {"en":"🔍 Follow-up questions", "fr":"🔍 Questions de suivi", "nl":"🔍 Vervolgvragen", "de":"🔍 Rückfragen"},
    "fu_clarify":     {"en":"Clarify", "fr":"Clarifier", "nl":"Verduidelijken", "de":"Klarstellen"},
    "fu_deepen":      {"en":"Deepen", "fr":"Approfondir", "nl":"Verdiepen", "de":"Vertiefen"},
    "fu_none_c":      {"en":"No clarify suggestions", "fr":"Aucune suggestion pour clarifier", "nl":"Geen verduidelijkingsvoorstellen", "de":"Keine Klarstellen-Vorschläge"},
    "fu_none_d":      {"en":"No deepen suggestions", "fr":"Aucune suggestion pour approfondir", "nl":"Geen verdiepingsvoorstellen", "de":"Keine Vertiefungs-Vorschläge"},

    # Citations & history
    "h_citations":    {"en":"📝 Citations", "fr":"📝 Citations", "nl":"📝 Bronnen", "de":"📝 Quellen"},
    "h_history":      {"en":"📚 Session history", "fr":"📚 Historique de session", "nl":"📚 Sessiegeschiedenis", "de":"📚 Sitzungsverlauf"},

    # General/misc
"unknown": {"en":"unknown","fr":"inconnu","nl":"onbekend","de":"unbekannt"},
"info_enter_id": {
  "en":"Enter a **User ID** in the sidebar, then click **Start session**.",
  "fr":"Saisissez un **identifiant** dans la barre latérale, puis cliquez **Démarrer la session**.",
  "nl":"Voer een **Gebruikers-ID** in de zijbalk in en klik **Sessie starten**.",
  "de":"Geben Sie in der Seitenleiste eine **Benutzer-ID** ein und klicken Sie auf **Sitzung starten**."
},
"admin_check_failed": {
  "en":"Admin check failed (missing/invalid admin key or /admin/keys error).",
  "fr":"Vérification admin échouée (clé admin manquante/invalide ou erreur /admin/keys).",
  "nl":"Admincontrole mislukt (ontbrekende/ongeldige adminkey of /admin/keys-fout).",
  "de":"Admin-Prüfung fehlgeschlagen (fehlender/ungültiger Admin-Schlüssel oder /admin/keys-Fehler)."
},

# Rights labels (for the toast)
"rights_all":           {"en":"✅ all rights","fr":"✅ tous droits","nl":"✅ alle rechten","de":"✅ alle Rechte"},
"rights_upload_query":  {"en":"✅ upload + query","fr":"✅ upload + requête","nl":"✅ upload + query","de":"✅ Upload + Abfrage"},
"rights_upload_only":   {"en":"⬆️ upload only","fr":"⬆️ upload seulement","nl":"⬆️ alleen uploaden","de":"⬆️ nur Upload"},
"rights_query_only":    {"en":"🔎 query only","fr":"🔎 requête seulement","nl":"🔎 alleen query","de":"🔎 nur Abfrage"},
"rights_none":          {"en":"⛔ no rights","fr":"⛔ aucun droit","nl":"⛔ geen rechten","de":"⛔ keine Rechte"},

"h_access_request": {"en":"✉️ Access request","fr":"✉️ Demande d’accès","nl":"✉️ Toegangsaanvraag","de":"✉️ Zugriffsanfrage"},
"first_name": {"en":"First name*","fr":"Prénom*","nl":"Voornaam*","de":"Vorname*"},
"last_name":  {"en":"Last name*","fr":"Nom*","nl":"Achternaam*","de":"Nachname*"},
"email_lbl":  {"en":"Email*","fr":"Email*","nl":"E-mail*","de":"E-Mail*"},
"mobile_opt": {"en":"Mobile phone (optional)","fr":"Téléphone portable (optionnel)","nl":"Mobiele telefoon (optioneel)","de":"Mobiltelefon (optional)"},
"company":    {"en":"Company / Organization*","fr":"Entreprise / Organisation*","nl":"Bedrijf / Organisatie*","de":"Firma / Organisation*"},
"reason_lbl": {"en":"Reason for request*","fr":"Motif de la demande*","nl":"Reden voor aanvraag*","de":"Grund der Anfrage*"},
"reason_ph":  {"en":"Tell us briefly why you need access…","fr":"Expliquez brièvement pourquoi vous avez besoin d’un accès…","nl":"Leg kort uit waarom je toegang nodig hebt…","de":"Warum benötigen Sie Zugriff? (kurz)…"},
"human_q":    {"en":"Human check: what is {a} + {b} ?","fr":"Vérification : combien font {a} + {b} ?","nl":"Menscheck: wat is {a} + {b} ?","de":"Prüfung: Wie viel ist {a} + {b} ?"},
"btn_submit": {"en":"Submit request","fr":"Envoyer la demande","nl":"Aanvraag versturen","de":"Anfrage senden"},
"form_success":{"en":"Thank you! Your request has been sent. We will be shortly in contact.",
                "fr":"Merci ! Votre demande a été envoyée. Nous vous contacterons prochainement.",
                "nl":"Bedankt! Je aanvraag is verzonden. We nemen spoedig contact op.",
                "de":"Danke! Ihre Anfrage wurde gesendet. Wir melden uns in Kürze."},
"form_failed": {"en":"Sending request failed.","fr":"Échec de l’envoi de la demande.","nl":"Verzenden van de aanvraag mislukt.","de":"Senden der Anfrage fehlgeschlagen."},
"backend_recorded":{"en":"Request recorded by backend.","fr":"Demande enregistrée par le backend.","nl":"Aanvraag door backend geregistreerd.","de":"Anfrage im Backend erfasst."},

# validation
"err_firstname":{"en":"First name invalid (2–40 letters, spaces, hyphens, apostrophes).",
                 "fr":"Prénom invalide (2–40 lettres, espaces, traits d’union, apostrophes).",
                 "nl":"Voornaam ongeldig (2–40 letters, spaties, koppeltekens, apostrofs).",
                 "de":"Vorname ungültig (2–40 Buchstaben, Leerzeichen, Bindestriche, Apostrophe)."},
"err_lastname":{"en":"Last name invalid (2–40 letters, spaces, hyphens, apostrophes).",
                "fr":"Nom invalide (2–40 lettres, espaces, traits d’union, apostrophes).",
                "nl":"Achternaam ongeldig (2–40 letters, spaties, koppeltekens, apostrofs).",
                "de":"Nachname ungültig (2–40 Buchstaben, Leerzeichen, Bindestriche, Apostrophe)."},
"err_email":{"en":"Please provide a valid email address.","fr":"Veuillez fournir une adresse e-mail valide.","nl":"Geef een geldig e-mailadres op.","de":"Bitte eine gültige E-Mail-Adresse angeben."},
"err_company":{"en":"Company / Organization is required.","fr":"Entreprise / Organisation obligatoire.","nl":"Bedrijf / Organisatie is verplicht.","de":"Firma / Organisation ist erforderlich."},
"err_reason":{"en":"Reason should be at least 10 characters.","fr":"Le motif doit contenir au moins 10 caractères.","nl":"Reden moet minstens 10 tekens bevatten.","de":"Der Grund muss mindestens 10 Zeichen haben."},
"err_mobile":{"en":"Mobile phone must be a valid international number (e.g., +3212345678).",
              "fr":"Le téléphone portable doit être un numéro international valide (ex. +3212345678).",
              "nl":"Mobiel nummer moet een geldig internationaal nummer zijn (bijv. +3212345678).",
              "de":"Mobilnummer muss eine gültige internationale Nummer sein (z. B. +3212345678)."},
"err_human_wrong":{"en":"Human check failed. Please try again.","fr":"Vérification échouée. Réessayez.","nl":"Menscheck mislukt. Probeer opnieuw.","de":"Prüfung fehlgeschlagen. Bitte erneut versuchen."},
"err_human_nan":{"en":"Human check failed. Please enter a number.","fr":"Vérification échouée. Entrez un nombre.","nl":"Menscheck mislukt. Voer een getal in.","de":"Prüfung fehlgeschlagen. Bitte eine Zahl eingeben."},
"ui_lang_label": {
  "en":"Interface language",
  "fr":"Langue de l’interface",
  "nl":"Taal van de interface",
  "de":"Sprache der Oberfläche"
},
}

def _tr(key: str, **fmt) -> str:
    lang = st.session_state.get("ui_lang", "en")
    val = (I18N.get(key, {}) or {}).get(lang) or (I18N.get(key, {}) or {}).get("en") or key
    return val.format(**fmt)

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
st.title(_tr("app_title"))

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

    st.subheader(f"🚦{_tr('verify')}")   # same level/size as “💬 Answer”
    st.markdown("<div class='verif-card'>", unsafe_allow_html=True)

    #st.markdown(f"<div class='verif-title'>{title}</div>", unsafe_allow_html=True)

    meta_bits = []
    if conf is not None:
        meta_bits.append(f"{_tr('meta_conf')}: {icon} **{conf}**")
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

    with st.expander(f"{_tr('h_citations')} ({len(cits_sorted)})", expanded=False):
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

st.markdown("""
<style>
/* hide any anchor linking to your repo anywhere on the page */
a[href*="github.com/your-org/your-repo"] { display: none !important; }

/* hide a specific image (choose one selector that matches yours) */
img[src*="avatars.githubusercontent.com/"] { display: none !important; }  /* GH avatar */
img[alt="Your Avatar"] { display: none !important; }                      /* by alt text */
</style>
""", unsafe_allow_html=True)

# ==================== STATUS BANNER ====================
uid  = st.session_state["public_user_id"].strip()
role = st.session_state["role"]
rights = set(st.session_state["rights"])
can_upload = st.session_state["can_upload_right"]
can_query_right = st.session_state["can_query_right"]
has_access = ("*" in rights) or can_upload or can_query_right

# Access icon (only icon in the Access column)
if "*" in rights:
    access_icon, access_tip = _tr("rights_all"), "✅"
elif can_upload and can_query_right:
    access_icon, access_tip =  _tr("rights_upload_only"), "✅"
elif can_upload:
    access_icon, access_tip = _tr("rights_upload_only"), "⬆️"
elif can_query_right:
    access_icon, access_tip = _tr("rights_query_only"), "🔎"
else:
    access_icon, access_tip = _tr("rights_none"), "⛔"

rights_value = "*" if "*" in rights else (", ".join(sorted(rights)) if rights else "—")

cols = st.columns(3, gap="large")  # gives space between items
with cols[0]:
    st.markdown(f"**{_tr('status_role')}:** {role or _tr('unknown')}")
with cols[1]:
    st.markdown(f"**{_tr('status_access')}:** {access_icon}")
with cols[2]:
    st.markdown(f"**{_tr('status_rights')}:** {rights_value}")

# little vertical breathing room below the row
st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

# ==================== SIDEBAR ====================
# Hide Streamlit's default sidebar nav
st.markdown("<style>[data-testid='stSidebarNav']{display:none}</style>", unsafe_allow_html=True)

# UI language selector
st.sidebar.radio(
    _tr("ui_lang_label"),
    options=list(UI_LANGS.keys()),
    format_func=lambda k: UI_LANGS[k],
    key="ui_lang",
    horizontal=False,
)

# Localized custom nav
st.sidebar.page_link("userinterface.py",      label=_tr("nav_home"))
st.sidebar.page_link("pages/1_how_to_use.py", label=_tr("nav_how"))

with st.sidebar:
    st.subheader(_tr("sidebar_user"))
    if not st.session_state.uid_locked:
        st.session_state.public_user_id = st.text_input(
            _tr("user_id"),
            value=st.session_state.public_user_id,
            placeholder=_tr("user_id_ph"),
            help=_tr("user_id_help"),
            key="user_id_input",
        )
    else:
        st.text_input(
            _tr("user_id_locked"),
            value=_mask_first_last(st.session_state.public_user_id),
            disabled=True,
        )
        st.caption(_tr("user_locked_note"))

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button(
            _tr("btn_start"),
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
                st.toast(_tr("admin_check_failed"), icon="⚠️")
            else:
                st.session_state.role   = status.get("role")
                st.session_state.rights = status.get("rights") or []
                st.session_state.can_upload_right = bool(status.get("can_upload"))
                st.session_state.can_query_right  = bool(status.get("can_query"))
                st.session_state.can_query = st.session_state.can_query_right

                rights = set(st.session_state.rights)
                if "*" in rights:
                    access_icon, access_tip = "✅", _tr("rights_all")
                elif can_upload and can_query_right:
                    access_icon, access_tip = "✅", _tr("rights_upload_query")
                elif can_upload:
                    access_icon, access_tip = "⬆️", _tr("rights_upload_only")
                elif can_query_right:
                    access_icon, access_tip = "🔎", _tr("rights_query_only")
                else:
                    access_icon, access_tip = "⛔", _tr("rights_none")
                st.toast(f"{_tr('status_role')}: {st.session_state.role or _tr('unknown')} — {label}", icon=icon)

            # 🔒 Lock the ID after attempting to start the session
            st.session_state.uid_locked = True
            st.rerun()

        with c2:
            if st.button(_tr("btn_request"), disabled=has_access, help=_tr("already_have_access_help")):
                st.session_state.show_request_form = True
                if not (st.session_state.hc_a and st.session_state.hc_b):
                    st.session_state.hc_a = random.randint(3, 9)
                    st.session_state.hc_b = random.randint(2, 8)

        with c3:
            if st.button(_tr("btn_reset")):
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

# --- Access request form ---
    if st.session_state.show_request_form:
        st.markdown("### " + _tr("h_access_request"))
        with st.form("role_request_form", clear_on_submit=False):
            colA, colB = st.columns(2)
            with colA:
                first  = st.text_input(_tr("first_name"), max_chars=40, placeholder="Jane")
                email  = st.text_input(_tr("email_lbl"), max_chars=254, placeholder="jane.doe@example.com")
                mobile = st.text_input(_tr("mobile_opt"), max_chars=20, placeholder="+32...")
            with colB:
                last    = st.text_input(_tr("last_name"), max_chars=40, placeholder="Doe")
                company = st.text_input(_tr("company"), max_chars=80, placeholder="example")
                reason  = st.text_area(_tr("reason_lbl"), max_chars=500, height=120, placeholder=_tr("reason_ph"))

            # Simple human check (math)
            a, b = st.session_state.hc_a, st.session_state.hc_b
            human_ok = st.number_input(_tr("human_q", a=a, b=b), step=1, format="%d", value=0)

            submitted = st.form_submit_button(_tr("btn_submit"), type="primary")

            if submitted:
                errors = []

                # Basic validations
                if not NAME_RE.match(first.strip()):
                    errors.append(_tr("err_firstname"))
                if not NAME_RE.match(last.strip()):
                    errors.append(_tr("err_lastname"))
                if not EMAIL_RE.match(email.strip()):
                    errors.append(_tr("err_email"))
                if not company.strip():
                    errors.append(_tr("err_company"))
                if len((reason or "").strip()) < 10:
                    errors.append(_tr("err_reason"))
                if mobile.strip() and not PHONE_RE.match(mobile.strip()):
                    errors.append(_tr("err_mobile"))
                try:
                    if int(human_ok) != (a + b):
                        errors.append(_tr("err_human_wrong"))
                except Exception:
                    errors.append(_tr("err_human_nan"))

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
                        st.success(_tr("form_success"))
                        st.toast(_tr("backend_recorded"), icon="🗂️")
                        # Hide form after success & reset human check
                        st.session_state.show_request_form = False
                        st.session_state.hc_a = None
                        st.session_state.hc_b = None
                    else:
                        st.error("Sending request failed.")
                        st.caption(str(resp))

if not uid:
    st.info(_tr("info_enter_id"))
    st.stop()

# ==================== UPLOAD ====================
st.header(_tr("h_upload"))

# Always compute can_upload from session to avoid stale locals
can_upload = bool(st.session_state.can_upload_right)

# Use a stable key so we can reset uploader later if needed
upload = st.file_uploader(_tr("uploader_label"), type="pdf", disabled=not can_upload, key="pdf_uploader")

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
        st.success(f"{_tr('processed')} — {shown_name}")
    elif is_new_unprocessed:
        st.warning(_tr("new_selected"))
    else:
        st.info(_tr("no_processed"))

with status_col2:
    # Show "Process PDF" only when a new file is selected
    show_process_btn = can_upload and is_new_unprocessed and (upload is not None)
    if show_process_btn and st.button(_tr("btn_process"), type="primary", use_container_width=True):
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
            st.toast(_tr("processed"), icon="✅")
            st.rerun()  # immediately reflect that Q&A can be shown
        else:
            st.error(f"{_tr('upload_failed')}: {getattr(r, 'status_code', '?')} {getattr(r, 'text', '')}")
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
    st.subheader(_tr("h_ctx_lang"))

    # ---- Language (moved from sidebar to main)
    lang_choice = st.radio(
        _tr("answer_lang"),
        options=["NL","FR","DE","EN"],
        index=["NL","FR","DE","EN"].index(st.session_state.get("lang_code","nl").upper()) if st.session_state.get("lang_code") else 1,
        horizontal=True,
        help=_tr("answer_lang_help")
    )
    st.session_state.lang_code = LANG_LABEL_TO_CODE[lang_choice]

    # ---- Context (dropdown)
    label_key = f"label_{st.session_state.ui_lang.lower()}"
    ctx_ids = list(CONTEXTS.keys())
    # current index
    cur_idx = next((i for i, cid in enumerate(ctx_ids) if cid == st.session_state.context_id), 0)
    selected_ctx_id = st.selectbox(
        _tr("ctx_label"),
        options=ctx_ids,
        index=cur_idx,
        format_func=lambda cid: CONTEXTS[cid].get(label_key) or CONTEXTS[cid]["label_en"],
        help=_tr("ctx_help")
    )
    st.session_state.context_id = selected_ctx_id

    # (optional) tiny caption with the chosen label
    st.caption(f"{_tr('selected')}: {_ctx_label(st.session_state.context_id, st.session_state.ui_lang)}")
    st.header(_tr("h_ask"))
    auto_q = st.session_state.pop("followup_q", None)
    if auto_q:
        st.session_state.q_text = auto_q
    q = st.text_area(_tr("your_q"), key="q_text", height=120,
                     placeholder=_tr("q_ph", n=MIN_QUESTION_CHARS),
                     disabled=not can_query_right)
    qlen = len((q or "").strip())
    st.caption(("📝 " if qlen < MIN_QUESTION_CHARS else "✅ ") + f"{qlen}/{MIN_QUESTION_CHARS}")

    c1, c2, c3 = st.columns([1,1,1])
    with c1: do_verify    = st.checkbox(_tr("verify"), value=True, key="opt_verify", disabled=not can_query_right)
    with c2: do_followups = st.checkbox(_tr("followups"), value=True, key="opt_followups", disabled=not can_query_right)
    with c3: run_click    = st.button(_tr("btn_answer"), type="primary", disabled=(not can_query_right or qlen < MIN_QUESTION_CHARS))

    should_run = run_click

    if should_run:
        t_total_start = time.perf_counter()
        # Create placeholders to remove later
        status_ph = st.empty()
        prog_ph = st.empty()

        try:
            # Show a temporary status + progress while we prepare/send/wait
            with status_ph.status(_tr("working"), expanded=True) as status:
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

                status.update(label=_tr("working"))
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
                status.update(label=_tr("answer_received", s=_fmt_secs(total_elapsed)), state="complete")

            prog_ph.empty()
            status_ph.empty()

            if not getattr(r, "ok", False):
                status.update(label="❌ " + _tr("req_failed"), state="error")
                st.error(f"{_tr('query_failed')}: {r.status_code} {r.text}")
            else:
                res = r.json() or {}
                st.subheader(_tr("h_answer"))
                st.write(res.get("answer", ""))
                conf = res.get("confidence_score", 0)
                model = res.get("model") or res.get("model_used") or "unknown"
                total_elapsed = time.perf_counter() - t_total_start
                m1, m2, m3 = st.columns([1,1,1])
                with m1: st.caption(f'🎯 {_tr("meta_conf")}: {conf if isinstance(conf,(int,float)) else str(conf)}')
                with m2: st.caption(f'🧠 {_tr("meta_model")}: {model}')
                with m3: st.caption(f'⏱️ {_tr("meta_time")}: {_fmt_secs(total_elapsed)}')
                #with m3: st.caption(f'🌐 Language hint: {st.session_state.lang_code.upper()}')

                # Verification & citations
                show_verification(res.get("verification"))
                show_citations(res.get("citations"))

                # Follow-ups (clickable) — this block stays as-is; see tweak below
                f = res.get("followups") or {}
                clarify = f.get("clarify") or []
                deepen  = f.get("deepen") or []
                if clarify or deepen:
                    st.subheader(_tr("h_fu"))

                    col_c, col_d = st.columns(2, gap="large")

                    with col_c:
                        st.markdown('<div class="fu-card"><div class="fu-title">🧼 '+_tr("fu_clarify")+'</div>', unsafe_allow_html=True)
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
                            st.markdown('<div class="fu-empty">'+_tr("fu_none_c")+'</div>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                    with col_d:
                        st.markdown('<div class="fu-card"><div class="fu-title">🧠 '+_tr("fu_deepen")+'</div>', unsafe_allow_html=True)
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
                            st.markdown('<div class="fu-empty">'+_tr("fu_none_d")+'</div>', unsafe_allow_html=True)
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
    st.header(_tr("h_history"))
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
