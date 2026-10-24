"""GUI translations and system UI language detection, independent of Tk."""

import ctypes
import gettext
import json
import locale
import os
import sys
from functools import cache
from importlib.resources import files
from pathlib import Path

from .resources import atomic_write


def N_(source: str) -> str:
    """Mark a deferred label for extraction without translating it yet."""
    return source


LANGUAGES = {"auto": N_("System default"), "en": "English", "ja": "日本語", "zh": "简体中文"}
MESSAGE_LABELS = {
    "request": N_("request"),
    "response": N_("response"),
    "notify": N_("notify"),
    "decoded": N_("decoded"),
    "orphan_response": N_("orphan_response"),
    "unknown_schema": N_("unknown_schema"),
    "malformed": N_("malformed"),
}


@cache
def translations(language: str) -> gettext.NullTranslations:
    if language not in ("ja", "zh"):
        return gettext.NullTranslations()
    resource = files("majsoul_hook").joinpath("locale", language, "LC_MESSAGES", "messages.mo")
    with resource.open("rb") as stream:
        return gettext.GNUTranslations(stream)


def translate(language: str, source: str, **values) -> str:
    text = translations(language).gettext(source)
    return text.format(**values) if values else text


def normalize_language(value: str | None) -> str:
    language = (value or "").lower().replace("-", "_").split("_")[0].split(".")[0]
    return language if language in ("en", "ja", "zh") else "en"


def detect_language() -> str:
    # Windows UI language can differ from the locale used for dates and numbers.
    if sys.platform == "win32":
        try:
            language_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            if language := locale.windows_locale.get(language_id):
                return normalize_language(language)
        except (AttributeError, OSError):
            pass
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        if value := os.environ.get(name):
            return normalize_language(value)
    try:
        return normalize_language(locale.getlocale()[0])
    except (ValueError, TypeError):
        return "en"


def load_language(path: Path) -> str:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        value = document.get("language") if isinstance(document, dict) else None
        return value if isinstance(value, str) and value in LANGUAGES else "auto"
    except (OSError, ValueError):
        return "auto"


def save_language(path: Path, language: str):
    if language not in LANGUAGES:
        raise ValueError(f"Unsupported GUI language: {language}")
    atomic_write(path, json.dumps({"language": language}).encode("utf-8"))
