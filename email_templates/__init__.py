from html import escape

DEFAULT_LOCALE = "en"


def normalize_locale(locale, templates_by_locale):
    if locale and locale in templates_by_locale:
        return locale
    if DEFAULT_LOCALE in templates_by_locale:
        return DEFAULT_LOCALE
    return next(iter(templates_by_locale), DEFAULT_LOCALE)


def sanitize_html_value(value):
    if value is None:
        return ""
    return escape(str(value), quote=True)


def sanitize_text_value(value):
    if value is None:
        return ""
    text = str(value)
    return "".join(ch for ch in text if ch >= " " or ch in "\n\t")


def sanitize_template_values(values, *, html):
    sanitizer = sanitize_html_value if html else sanitize_text_value
    return {key: sanitizer(value) for key, value in values.items()}


def render_localized_template(templates_by_locale, locale, values, *, html):
    selected_locale = normalize_locale(locale, templates_by_locale)
    template = templates_by_locale[selected_locale]
    safe_values = sanitize_template_values(values, html=html)
    return template.safe_substitute(**safe_values)
