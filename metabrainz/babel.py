from flask_babel import Babel

from metabrainz.i18n import get_locale


def init_app(app):
    # Flask-Babel calls this selector per request, so both apps can share the
    # same cookie/header locale behavior.
    Babel(app, locale_selector=get_locale)
