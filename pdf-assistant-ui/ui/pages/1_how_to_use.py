import streamlit as st
st.set_page_config(page_title="How to • PDF Assistant", page_icon="ℹ️", layout="wide")

lang = st.session_state.get("ui_lang", "en")

TITLE = {
    "en": "📘 How to use PDF Assistant",
    "fr": "📘 Mode d’emploi — Assistant PDF",
    "nl": "📘 Handleiding — PDF-assistent",
    "de": "📘 Anleitung — PDF-Assistent",
}[lang]

SUB = {
    "en": "A quick guide to uploading a PDF, picking the right context & language, asking questions, and reading results.",
    "fr": "Guide rapide : charger un PDF, choisir le bon contexte et la langue, poser des questions, lire les résultats.",
    "nl": "Snelgids: PDF uploaden, juiste context & taal kiezen, vragen stellen en resultaten lezen.",
    "de": "Kurzanleitung: PDF hochladen, passenden Kontext & Sprache wählen, Fragen stellen und Ergebnisse lesen.",
}[lang]

st.title(TITLE)
st.caption(SUB)

st.markdown("""
<style>
  .blk{border:1px solid rgba(49,51,63,.18);border-radius:.75rem;padding:1rem 1.2rem;margin:.35rem 0 .9rem 0;background:rgba(240,242,246,.35)}
  .blk h3{margin:.1rem 0 .6rem 0}
</style>
""", unsafe_allow_html=True)

T = {
  "qs_h":  {"en":"🚀 Quick start","fr":"🚀 Démarrage rapide","nl":"🚀 Snel starten","de":"🚀 Schnellstart"},
  "qs_b":  {
      "en":"1. Enter your **User ID** in the sidebar and click **Start session**.\n2. **Upload a PDF** and click **Process PDF**.\n3. In the main area, choose **Context** and **Answer language**.\n4. Type your question and hit **Get answer**.\n5. (Optional) Toggle **Verification** and **Suggest follow-up questions**.\n6. Review **Answer**, **Verification**, and click a **Follow-up** to continue.",
      "fr":"1. Saisissez votre **identifiant** dans la barre latérale puis **Démarrer la session**.\n2. **Chargez un PDF** et cliquez **Traiter le PDF**.\n3. Dans la zone principale, choisissez **Contexte** et **Langue de réponse**.\n4. Tapez votre question puis **Obtenir la réponse**.\n5. (Facultatif) Activez **Vérification** et **Questions de suivi**.\n6. Consultez **Réponse**, **Vérification**, puis cliquez sur un **Suivi** pour continuer.",
      "nl":"1. Vul je **Gebruikers-ID** in de zijbalk in en klik **Sessie starten**.\n2. **Upload een PDF** en klik **PDF verwerken**.\n3. Kies in het hoofddeel **Context** en **Antwoordtaal**.\n4. Typ je vraag en klik **Antwoord ophalen**.\n5. (Optioneel) Zet **Verificatie** en **Vervolgvragen** aan.\n6. Bekijk **Antwoord**, **Verificatie** en klik op een **Vervolgvraag**.",
      "de":"1. Gib deine **Benutzer-ID** in der Seitenleiste ein und klicke **Sitzung starten**.\n2. **Lade ein PDF hoch** und klicke **PDF verarbeiten**.\n3. Wähle im Hauptbereich **Kontext** und **Antwortsprache**.\n4. Tippe deine Frage und klicke **Antwort abrufen**.\n5. (Optional) **Verifikation** und **Rückfragen** aktivieren.\n6. Lies **Antwort**, **Verifikation** und klicke eine **Rückfrage**.",
  },
  "acc_h": {"en":"🔑 Access & roles","fr":"🔑 Accès & rôles","nl":"🔑 Toegang & rollen","de":"🔑 Zugriff & Rollen"},
  "acc_b": {
      "en":"Your rights are checked via your **User ID**. Status shows: ✅ all rights, ⬆️ upload only, 🔎 query only, ⛔ no rights.",
      "fr":"Vos droits sont vérifiés via votre **identifiant**. Statut : ✅ tous droits, ⬆️ upload seul, 🔎 requête seule, ⛔ aucun droit.",
      "nl":"Je rechten worden via je **Gebruikers-ID** gecontroleerd. Status: ✅ alle rechten, ⬆️ alleen upload, 🔎 alleen query, ⛔ geen rechten.",
      "de":"Ihre Rechte werden über Ihre **Benutzer-ID** geprüft. Status: ✅ alle Rechte, ⬆️ nur Upload, 🔎 nur Abfrage, ⛔ keine Rechte.",
  },
  "up_h":  {"en":"📄 Uploading a PDF","fr":"📄 Charger un PDF","nl":"📄 PDF uploaden","de":"📄 PDF hochladen"},
  "up_b":  {
      "en":"Use **Upload PDF** → select a *.pdf* → **Process PDF**. After processing you’ll see **Processed ✓** and Q&A is enabled.",
      "fr":"Utilisez **Charger un PDF** → choisissez un *.pdf* → **Traiter le PDF**. Après traitement : **Traité ✓** et Q&R activés.",
      "nl":"Gebruik **PDF uploaden** → kies een *.pdf* → **PDF verwerken**. Na verwerking zie je **Verwerkt ✓** en Q&A is actief.",
      "de":"**PDF hochladen** → *.pdf* wählen → **PDF verarbeiten**. Danach erscheint **Verarbeitet ✓** und Q&A ist aktiv.",
  },
  "cl_h": {"en":"🎛️ Pick context & language","fr":"🎛️ Choisir contexte & langue","nl":"🎛️ Kies context & taal","de":"🎛️ Kontext & Sprache wählen"},
  "cl_b": {
      "en":"**Context** guides how the assistant reads the document. **Answer language** controls the response language.",
      "fr":"Le **Contexte** guide la lecture du document. La **Langue de réponse** contrôle la langue de la réponse.",
      "nl":"**Context** stuurt hoe het document gelezen wordt. **Antwoordtaal** bepaalt de taal van het antwoord.",
      "de":"Der **Kontext** steuert das Lesen des Dokuments. Die **Antwortsprache** bestimmt die Sprache der Antwort.",
  },
  "aq_h": {"en":"❓ Asking good questions","fr":"❓ Bien poser ses questions","nl":"❓ Goede vragen stellen","de":"❓ Gute Fragen stellen"},
  "aq_b": {
      "en":"Be specific; cite sections/pages; use context-aware prompts. Avoid very broad prompts.",
      "fr":"Soyez précis ; citez sections/pages ; utilisez le bon contexte. Évitez les requêtes trop générales.",
      "nl":"Wees specifiek; verwijs naar secties/pagina’s; gebruik context. Vermijd te brede prompts.",
      "de":"Seien Sie spezifisch; nennen Sie Abschnitte/Seiten; nutzen Sie den Kontext. Vermeiden Sie zu breite Prompts.",
  },
  "vf_h": {"en":"🔍 Verification","fr":"🔍 Vérification","nl":"🔍 Verificatie","de":"🔍 Verifikation"},
  "vf_b": {
      "en":"With **Verification**, you’ll see a confidence indicator, an explanation and issues. Use **Citations** to double-check.",
      "fr":"Avec **Vérification**, vous voyez un niveau de confiance, une explication et des problèmes. Utilisez **Citations** pour vérifier.",
      "nl":"Met **Verificatie** zie je betrouwbaarheid, uitleg en eventuele issues. **Bronnen** helpen bij het checken.",
      "de":"Mit **Verifikation** sehen Sie Konfidenz, Erklärung und Probleme. **Quellen** helfen beim Prüfen.",
  },
  "fu_h": {"en":"➡️ Follow-up questions","fr":"➡️ Questions de suivi","nl":"➡️ Vervolgvragen","de":"➡️ Rückfragen"},
  "fu_b": {
      "en":"Click a suggested **Clarify** or **Deepen** item to prefill the question box, then press **Get answer**.",
      "fr":"Cliquez sur **Clarifier** ou **Approfondir** pour préremplir la question puis **Obtenir la réponse**.",
      "nl":"Klik op **Verduidelijken** of **Verdiepen** om de vraag te vullen en klik **Antwoord ophalen**.",
      "de":"Klicken Sie **Klarstellen** oder **Vertiefen**, dann **Antwort abrufen**.",
  },
  "tr_h": {"en":"🧰 Troubleshooting","fr":"🧰 Dépannage","nl":"🧰 Probleemoplossing","de":"🧰 Fehlerbehebung"},
  "tr_b": {
      "en":"If a request times out, try a shorter question or smaller PDF; ask an admin to increase server timeout.",
      "fr":"En cas d’expiration, essayez une question plus courte ou un PDF plus petit ; demandez un délai serveur plus long.",
      "nl":"Bij time-outs: kortere vraag of kleiner PDF; vraag admin om hogere server-timeout.",
      "de":"Bei Timeout: kürzere Frage oder kleinere PDF; Admin um höhere Server-Timeout bitten.",
  },
}

def sec(h,b):
    st.markdown("<div class='blk'>", unsafe_allow_html=True)
    st.header(h); st.markdown(b)
    st.markdown("</div>", unsafe_allow_html=True)

sec(T["qs_h"][lang], T["qs_b"][lang])
sec(T["acc_h"][lang], T["acc_b"][lang])
sec(T["up_h"][lang],  T["up_b"][lang])
sec(T["cl_h"][lang],  T["cl_b"][lang])
sec(T["aq_h"][lang],  T["aq_b"][lang])
sec(T["vf_h"][lang],  T["vf_b"][lang])
sec(T["fu_h"][lang],  T["fu_b"][lang])
sec(T["tr_h"][lang],  T["tr_b"][lang])
