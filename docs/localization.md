# GUI localization

The GUI uses Python's standard-library `gettext`, following the catalog organization used by [Thonny](https://github.com/thonny/thonny/blob/master/docs/translate.md). [Babel](https://babel.pocoo.org/en/latest/messages.html) extracts, merges, and compiles the catalogs during development and builds. Babel is not a runtime dependency. Tk widgets receive translated text through the existing refresh registry; changing a gettext catalog alone does not update existing widgets.

## Files

```text
src/majsoul_hook/
  gui_i18n.py                       # gettext loading, language detection, preferences
  locale/
    messages.pot                   # extracted English source template
    ja/LC_MESSAGES/messages.po      # Japanese translations
    zh/LC_MESSAGES/messages.po      # Simplified Chinese translations
    */LC_MESSAGES/messages.mo      # generated, ignored by Git
```

English uses the original source strings through `gettext.NullTranslations`; it does not need a duplicate English PO file. Language IDs remain `en`, `ja`, and `zh` in `data/gui-settings.json`; `auto` detects the system UI language at startup. Unsupported languages use English.

`babel.cfg` limits extraction to the GUI modules. `hatch_build.py` compiles PO files for wheels and editable installs, rejecting fuzzy, empty, or invalid translations. Source distributions include PO/POT files and the build hook; wheels also contain MO files. Never edit or commit MO files. uv's cache keys include PO files so a changed translation triggers rebuilding on the next `uv run` or `uv sync`.

## Mark source strings

Use an English literal with `self.tr()` for immediate translation, or `_set()` for a dynamic status that must be refreshed when the language changes:

```python
self.tr("Choose a resource file")
self._set(self.status, "Failed: {error}", error=str(exc))
```

Mark deferred labels with `N_()`, which returns the English string unchanged. `_widget()` stores that source string and translates it when creating or refreshing the widget:

```python
from .gui_i18n import N_

self._widget(ttk.Button, parent, text=N_("Start capture"), command=self.start_capture)
```

Use `N_()` for labels in tuples, mappings, and conditional branches too. `tr`, `_set:2`, and `N_` are the extraction keywords. Translate the template before formatting values: do not pass f-strings to translation functions. Keep named placeholders such as `{error}` identical in every translation. Protocol method names, field names, payloads, and raw diagnostics remain unchanged.

## Update translations

Run from the repository root:

```powershell
uv sync --locked
uv run --locked pybabel extract -F babel.cfg -k N_ -k tr -k _set:2 --project majsoul-hook-mitm --version 0.1.0 --no-wrap -o src/majsoul_hook/locale/messages.pot src/majsoul_hook
uv run --locked pybabel update -i src/majsoul_hook/locale/messages.pot -d src/majsoul_hook/locale --no-fuzzy-matching
```

Edit each PO file's `msgstr` with a text editor or a gettext editor such as Poedit. Review changed strings and remove fuzzy flags only after checking the translation. Keep the `msgid` and format placeholders intact. Complete both locales before the next build; builds intentionally reject untranslated entries. Then compile, test, and restart any running GUI:

```powershell
uv run --locked pybabel compile -d src/majsoul_hook/locale --statistics
uv run --locked pytest tests/test_gui_i18n.py tests/test_gui.py
uv run --locked majsoul-hook gui
```

The tests check source/template parity, translation completeness, placeholders, compiled catalog contents, startup preferences, live switching, and the three languages at HiDPI. For distribution, `uv build` recompiles the catalogs automatically. Runtime loading uses `importlib.resources` and the class-based [gettext API](https://docs.python.org/3/library/gettext.html#class-based-api), without installing a global `_()` function or changing the process locale.
