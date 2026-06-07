import gettext
import os
from urllib.parse import urlencode

from flask import redirect, request


LANGUAGE_COOKIE_NAME = "metabrainz_lang"
DEFAULT_LOCALE = "en"
# Keep this list small until real translation coverage exists in Weblate.
SUPPORTED_LANGUAGES = (
    {"code": "en", "name": "English"},
    {"code": "fr", "name": "Français"},
    {"code": "de", "name": "Deutsch"},
)


def get_supported_locale_codes():
    return [language["code"] for language in SUPPORTED_LANGUAGES]


def normalize_locale(locale):
    """Normalize browser/cookie locale values to the base language code."""
    if not locale:
        return None
    return locale.replace("_", "-").split("-")[0].lower()


def get_locale():
    """Select one locale for both Flask-Babel and React translation props."""
    # A user-selected cookie should win over the browser language.
    cookie_locale = normalize_locale(request.cookies.get(LANGUAGE_COOKIE_NAME))
    if cookie_locale in get_supported_locale_codes():
        return cookie_locale

    # Fall back to the best language advertised by the browser.
    accepted_locale = request.accept_languages.best_match(get_supported_locale_codes())
    if accepted_locale:
        return accepted_locale

    return DEFAULT_LOCALE


def handle_locale_change():
    """Persist a selected language and redirect back to the same clean URL."""
    requested_locale = normalize_locale(request.args.get("set_language"))
    if requested_locale not in get_supported_locale_codes():
        return None

    # Remove the one-shot language switch parameter before redirecting.
    query_args = request.args.to_dict(flat=False)
    query_args.pop("set_language", None)
    query_string = urlencode(query_args, doseq=True)
    redirect_url = request.path
    if query_string:
        redirect_url = f"{redirect_url}?{query_string}"

    response = redirect(redirect_url)
    response.set_cookie(
        LANGUAGE_COOKIE_NAME,
        requested_locale,
        max_age=365 * 24 * 60 * 60,
        httponly=False,
        samesite="Lax",
    )
    return response


def get_locale_context():
    """Expose locale data to shared Jinja templates."""
    locale = get_locale()
    return {
        "current_locale": locale,
        "get_language_url": get_language_url,
        "language_cookie_name": LANGUAGE_COOKIE_NAME,
        "supported_languages": SUPPORTED_LANGUAGES,
    }


def get_language_url(locale):
    """Build a language-switch URL while preserving existing query params."""
    query_args = request.args.to_dict(flat=False)
    query_args["set_language"] = [locale]
    return f"{request.path}?{urlencode(query_args, doseq=True)}"


def get_frontend_translations(locale=None):
    """Return gettext catalog entries as a plain object for React code."""
    locale = locale or get_locale()
    if locale == DEFAULT_LOCALE:
        return {}

    # OAuth is a separate Flask app, so resolve the translations dir from this
    # module instead of current_app.root_path.
    localedir = os.path.join(os.path.dirname(__file__), "translations")
    translation = gettext.translation(
        "messages",
        localedir=localedir,
        languages=[locale],
        fallback=True,
    )
    catalog = getattr(translation, "_catalog", {})
    # Only send useful string translations; metadata and untranslated entries
    # are intentionally omitted to keep global props small.
    return {
        msgid: msgstr
        for msgid, msgstr in catalog.items()
        if isinstance(msgid, str)
        and msgid
        and isinstance(msgstr, str)
        and msgstr
        and msgid != msgstr
    }
