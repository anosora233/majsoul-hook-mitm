import json
from importlib.resources import files
from string import Formatter
from types import SimpleNamespace

import pytest
from babel.messages.extract import extract_from_dir
from babel.messages.pofile import read_po

from majsoul_hook import gui_i18n


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("ja_JP", "ja"),
        ("zh-TW", "zh"),
        ("zh_CN.UTF-8", "zh"),
        ("en-US", "en"),
        ("fr_FR", "en"),
        ("C", "en"),
        (None, "en"),
    ],
)
def test_language_matching(value, expected):
    assert gui_i18n.normalize_language(value) == expected


def test_windows_detects_ui_language_instead_of_formatting_locale(monkeypatch):
    monkeypatch.setattr(gui_i18n, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(
        gui_i18n.ctypes,
        "windll",
        SimpleNamespace(kernel32=SimpleNamespace(GetUserDefaultUILanguage=lambda: 0x0411)),
        raising=False,
    )
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.setattr(gui_i18n.locale, "getlocale", lambda: ("zh_CN", "UTF-8"))
    assert gui_i18n.detect_language() == "ja"


def test_locale_priority_and_fallback(monkeypatch):
    monkeypatch.setattr(gui_i18n, "sys", SimpleNamespace(platform="linux"))
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(gui_i18n.locale, "getlocale", lambda: ("ja_JP", "UTF-8"))
    assert gui_i18n.detect_language() == "ja"
    monkeypatch.setenv("LANG", "zh_CN.UTF-8")
    assert gui_i18n.detect_language() == "zh"
    monkeypatch.setenv("LC_MESSAGES", "ja_JP.UTF-8")
    assert gui_i18n.detect_language() == "ja"
    monkeypatch.setenv("LC_ALL", "de_DE.UTF-8")
    assert gui_i18n.detect_language() == "en"


def test_language_preferences_and_invalid_settings(tmp_path):
    path = tmp_path / "data" / "gui-settings.json"
    assert gui_i18n.load_language(path) == "auto"
    for language in gui_i18n.LANGUAGES:
        gui_i18n.save_language(path, language)
        assert gui_i18n.load_language(path) == language
    original = path.read_bytes()
    with pytest.raises(ValueError, match="Unsupported"):
        gui_i18n.save_language(path, "de")
    assert path.read_bytes() == original
    for value in ([], {"language": []}, {"language": "de"}, None):
        path.write_text(json.dumps(value))
        assert gui_i18n.load_language(path) == "auto"
    path.write_text("{broken")
    assert gui_i18n.load_language(path) == "auto"


def test_catalog_preserves_format_fields_and_unknown_diagnostics():
    def fields(text):
        return {field for _, field, _, _ in Formatter().parse(text) if field is not None}

    directory = files("majsoul_hook").joinpath("locale")
    with directory.joinpath("messages.pot").open("rb") as stream:
        source_messages = {message.id for message in read_po(stream) if message.id}
    for language in ("ja", "zh"):
        with directory.joinpath(language, "LC_MESSAGES", "messages.po").open("rb") as stream:
            catalog = read_po(stream)
        assert not catalog.fuzzy and not list(catalog.check())
        assert {message.id for message in catalog if message.id} == source_messages
        for message in catalog:
            if message.id:
                assert message.string and not message.fuzzy
                assert fields(message.string) == fields(message.id)
                assert gui_i18n.translate(language, message.id) == message.string
    assert gui_i18n.translate("zh", "Failed: {error}", error="{raw}") == "失败：{raw}"
    assert gui_i18n.translate("ja", "raw {diagnostic}") == "raw {diagnostic}"
    assert gui_i18n.translate("en", "Start capture") == "Start capture"
    assert gui_i18n.translate("fr", "Start capture") == "Start capture"


def test_extracted_template_matches_source():
    directory = files("majsoul_hook")
    methods = [(name, "python") for name in ("gui.py", "gui_backend.py", "gui_i18n.py")]
    extracted = {
        message
        for _, _, message, _, _ in extract_from_dir(
            str(directory),
            method_map=methods,
            keywords={"N_": None, "tr": None, "_set": (2,)},
        )
    }
    with directory.joinpath("locale/messages.pot").open("rb") as stream:
        template = read_po(stream)
    assert extracted == {message.id for message in template if message.id}
