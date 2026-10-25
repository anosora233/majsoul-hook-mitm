from types import SimpleNamespace

import pytest

from majsoul_hook.gui_backend import DEFAULT_BASE_URL, EventInbox, MessageHistory


@pytest.fixture
def app(tmp_path, monkeypatch, request):
    tk = pytest.importorskip("tkinter")
    from majsoul_hook.gui import InspectorApp

    monkeypatch.setattr(
        "majsoul_hook.gui.local_resource_status",
        lambda _: {"exists": False, "base_url": DEFAULT_BASE_URL},
    )

    class Backend:
        task = None
        inbox = EventInbox()
        stopped = False

        @property
        def running(self):
            return self.task is not None

        def start(self, task, config):
            assert self.task is None
            self.task, self.config = task, config

        def stop(self, **kwargs):
            self.stopped = True

        def acknowledge_finished(self):
            self.task = None

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk display unavailable: {exc}")
    root.withdraw()
    options = getattr(request, "param", {})
    monkeypatch.setattr("majsoul_hook.gui.detect_language", lambda: options.get("system", "en"))
    settings_path = tmp_path / "gui-settings.json"
    if preference := options.get("preference"):
        from majsoul_hook.gui_i18n import save_language

        save_language(settings_path, preference)
    instance = InspectorApp(root, Backend(), settings_path=settings_path)
    path = tmp_path / "protocol.json"
    path.write_text("{}")
    instance.schema.set(str(path))
    yield instance
    root.after_cancel(instance._timer)
    root.destroy()


def test_capture_controls_and_stop_before_ready(app):
    app.process.set("custom-game.exe")
    assert app.cosmetics.get() is True
    app.start_button.invoke()
    assert app.backend.config["process"] == "custom-game.exe"
    assert app.backend.config["cosmetics"] is True
    assert app.start_button.instate(["disabled"])
    assert app.stop_button.instate(["!disabled"])
    app.stop_button.invoke()
    assert app.backend.stopped and app.stopping
    app._event({"event": "ready"})
    assert "Stopping" in app.status.get()
    app._event({"event": "finished", "task": "capture", "code": 0})
    assert app.start_button.instate(["!disabled"])
    assert app.stop_button.instate(["disabled"])
    assert app.status.get() == "Capture stopped"


def test_resources_independent_of_process_and_recover_from_error(app):
    app.process.set("")
    app.check_button.invoke()
    assert app.backend.task == "check"
    assert app.update_button.instate(["disabled"])
    app._event({"event": "error", "message": "network unavailable"})
    app._event({"event": "finished", "task": "check", "code": 1})
    assert "network unavailable" in app.status.get()
    assert app.update_button.instate(["!disabled"])
    app.update_button.invoke()
    assert app.backend.task == "update" and app.backend.config["schema"] == app.schema.get()
    app.close()
    assert app.backend.stopped and app.closing


def test_inspect_filter_eviction_and_empty_clear(app):
    app.clear()
    app.history = MessageHistory(max_items=2)
    record = {
        "event": "message",
        "timestamp": 1,
        "flow_id": "flow-1",
        "direction": "server_to_client",
        "name": ".lq.Lobby.test",
        "action": "modified",
        "before": {"value": 1},
        "after": {"value": 2},
        "wire_after": "YWJj",
    }
    app._event(record)
    key = app.tree.get_children()[0]
    app.tree.selection_set(key)
    app.inspect()
    assert '"value": 1' in app.detail_texts["before"].get("1.0", "end")
    assert '"value": 2' in app.detail_texts["after"].get("1.0", "end")
    assert "YWJj" in app.detail_texts["wire"].get("1.0", "end")
    for action, selected in app.action_filters.items():
        selected.set(action == "local")
    assert not app.tree.get_children()
    app._event({**record, "action": "local", "synthetic": True})
    assert len(app.tree.get_children()) == 1
    app.action_filters["modified"].set(True)
    assert len(app.tree.get_children()) == 2
    for selected in app.action_filters.values():
        selected.set(False)
    assert not app.tree.get_children() and len(app.history.items) == 2
    for selected in app.action_filters.values():
        selected.set(True)
    app.search.set("missing")
    assert not app.tree.get_children()
    app.search.set("")
    app.tree.selection_set(key)
    app.inspect()
    app._event(record)
    assert not app.tree.exists(key)
    assert "Select a message" in app.detail_texts["before"].get("1.0", "end")
    app.clear()
    app.clear()
    assert not app.history.items and not app.tree.get_children()


@pytest.mark.parametrize(
    ("language", "queries"),
    [("zh", ("响应", "已解析", "修改")), ("ja", ("レスポンス", "解析済み", "変更"))],
)
def test_search_matches_localized_cells_and_raw_values(app, language, queries):
    app.set_language(language)
    record = {
        "name": ".lq.Lobby.test",
        "flow_id": "flow-1",
        "direction": "server_to_client",
        "kind": "response",
        "status": "decoded",
        "action": "modified",
        "request_id": 0,
    }
    app._append(record)
    key = app.tree.get_children()[0]
    app._append({**record, "kind": "notify", "status": "unknown_schema", "action": "pass"})
    for query in (*queries, "RESPONSE", "decoded", "modified"):
        app.search.set(query)
        assert app.tree.get_children() == (key,)
    app.action_filters["modified"].set(False)
    assert not app.tree.get_children()
    app.action_filters["modified"].set(True)
    assert app.tree.get_children() == (key,)
    app.set_language("en")
    assert app.tree.get_children() == (key,)
    app.search.set(queries[0])
    assert not app.tree.get_children()
    app.search.set("")
    assert len(app.tree.get_children()) == len(app.history.items) == 2
    assert app.history.items[key][0] == record


def test_language_switch_preserves_capture_and_inspection(app, monkeypatch):
    from importlib.resources import files

    from babel.messages.pofile import read_po

    from majsoul_hook.gui_i18n import LANGUAGES, load_language

    with files("majsoul_hook").joinpath("locale/messages.pot").open("rb") as stream:
        source_messages = {message.id for message in read_po(stream) if message.id}

    record = {
        "name": ".lq.Lobby.test",
        "action": "modified",
        "kind": "response",
        "status": "decoded",
        "before": {"value": "原文"},
        "after": {"value": 2},
    }
    app._append(record)
    key = app.tree.get_children()[0]
    app.tree.selection_set(key)
    app.inspect()
    original = app.detail_texts["before"].get("1.0", "end")
    app.start_capture()
    app._event({"event": "ready"})
    for language, button, status, action in (
        ("ja", "キャプチャ開始", "キャプチャ中", "変更"),
        ("zh", "开始捕获", "捕获中", "修改"),
        ("en", "Start capture", "Capturing", "Modified"),
    ):
        app.language_combo.current(list(LANGUAGES).index(language))
        app.language_combo.event_generate("<<ComboboxSelected>>")
        assert app.start_button["text"] == button
        assert app.status.get() == status
        assert app.tree.set(key, "action") == action
        assert app.tree.selection() == (key,)
        assert app.detail_texts["before"].get("1.0", "end") == original
        assert app.history.items[key][0] == record
        assert app.backend.task == "capture" and app.start_button.instate(["disabled"])
        assert load_language(app.settings_path) == language
        assert all(source in source_messages for _, source in app._text_targets)
    monkeypatch.setattr("majsoul_hook.gui.detect_language", lambda: "zh")
    app.set_language("auto")
    assert app.language == "zh" and load_language(app.settings_path) == "auto"
    assert app.resource_summary.get().startswith("没有本地资源")
    app._event({"event": "error", "message": "raw diagnostic"})
    app.set_language("ja")
    assert app.status.get() == "失敗：raw diagnostic"
    assert "raw diagnostic" in app.log.get("1.0", "end")


def test_language_preference_save_failure_is_visible(app, monkeypatch):
    def fail(*_):
        raise OSError("read only")

    monkeypatch.setattr("majsoul_hook.gui.save_language", fail)
    app.set_language("zh")
    assert app.start_button["text"] == "开始捕获"
    assert app.status.get() == "无法保存语言设置：read only"


@pytest.mark.parametrize(
    "app",
    [{"system": "ja"}, {"system": "zh", "preference": "en"}, {"system": "en", "preference": "zh"}],
    indirect=True,
)
def test_startup_language_detection_and_saved_override(app, request):
    options = request.node.callspec.params["app"]
    expected = options.get("preference", options["system"])
    assert app.language == expected
    assert app.start_button["text"] == app.tr("Start capture")
    assert app.root.title() == app.tr("Mahjong Soul | Traffic Inspector")


def test_resource_result_is_retranslated_without_another_task(app):
    app._show_resources(
        {
            "exists": True,
            "version": "abcdef",
            "generated_at": "2026-10-24",
            "methods": 466,
            "characters": 12,
            "skins": 34,
            "titles": 56,
            "cosmetics": False,
            "update_available": True,
            "remote_version": "1234567890",
        }
    )
    app.set_language("zh")
    assert "角色 12 / 皮肤 34 / 称号 56" in app.resource_summary.get()
    assert "远端索引已变化" in app.resource_summary.get()
    app.set_language("ja")
    assert "キャラクター 12 / 衣装 34 / 称号 56" in app.resource_summary.get()
    assert "リモート索引が変更されています" in app.resource_summary.get()
    assert app.backend.task is None


@pytest.mark.parametrize("dpi", [120, 144, 192])
def test_dpi_change_scales_layout_and_preserves_inspection(app, monkeypatch, dpi):
    from tkinter import font, ttk

    initial_dpi = app.dpi_layout.dpi
    width = app.tree.column("time", "width")
    padding = app.stop_button.grid_info()["padx"]
    app._append({"name": "test", "action": "pass", "before": {"value": 1}})
    key = app.tree.get_children()[0]
    app.tree.selection_set(key)
    app.inspect()
    original_content = app.detail_texts["before"].get("1.0", "end")
    monkeypatch.setattr("majsoul_hook.gui_dpi.window_dpi", lambda _: dpi)
    monkeypatch.setattr("majsoul_hook.gui_dpi.work_area", lambda _: (0, 0, 3840, 2160))
    app.dpi_layout.refresh()
    assert app.tree.column("time", "width") == round(width * dpi / initial_dpi)
    assert app.stop_button.grid_info()["padx"] == round(padding * dpi / initial_dpi)
    assert float(app.root.tk.call("tk", "scaling")) == pytest.approx(dpi / 72, rel=0.01)
    line_height = font.nametofont("TkDefaultFont", root=app.root).metrics("linespace")
    assert int(ttk.Style(app.root).lookup("Treeview", "rowheight")) > line_height
    assert app.tree.selection() == (key,)
    assert app.detail_texts["before"].get("1.0", "end") == original_content
    # Polling the same DPI must not repeatedly enlarge the layout.
    app.dpi_layout.refresh()
    assert app.tree.column("time", "width") == round(width * dpi / initial_dpi)


def test_dpi_geometry_fits_small_work_area(app, monkeypatch):
    monkeypatch.setattr("majsoul_hook.gui_dpi.work_area", lambda _: (-1280, 0, 0, 720))
    app.dpi_layout.dpi = 192
    app.dpi_layout.fit_window()
    # Geometry requests are applied on the next idle pass.
    app.root.update_idletasks()
    requested = app.root.geometry().split("+")[0].split("x")
    assert int(requested[0]) <= 1280 and int(requested[1]) <= 720
    assert app.root.minsize()[0] <= 1280 and app.root.minsize()[1] <= 720


def test_constraint_accounts_for_frame_and_negative_monitor(app, monkeypatch):
    app.root.deiconify()
    app.root.update()
    monkeypatch.setattr("majsoul_hook.gui_dpi.work_area", lambda _: (-1280, 0, 0, 720))
    # Fix client and frame dimensions independently of the runner's DPI/display.
    monkeypatch.setattr(app.root, "winfo_width", lambda: 1400)
    monkeypatch.setattr(app.root, "winfo_height", lambda: 800)
    monkeypatch.setattr(
        "majsoul_hook.gui_dpi.window_bounds",
        lambda _: (-1400, 300, 26, 1171),
    )
    placed = []
    monkeypatch.setattr(
        "majsoul_hook.gui_dpi.place_window", lambda _, *bounds: placed.append(bounds)
    )
    app.dpi_layout.constrain_window()
    assert placed == [(-1280, 0, 1280, 720)]
    assert app.root.minsize()[0] <= 1280 - 26
    assert app.root.minsize()[1] <= 720 - 71


def test_real_window_frame_stays_inside_work_area(app):
    from majsoul_hook.gui_dpi import window_bounds, work_area

    app.root.deiconify()
    app.root.update()
    left, top, right, bottom = work_area(app.root)
    x, y, far_x, far_y = window_bounds(app.root)
    assert left <= x < far_x <= right
    assert top <= y < far_y <= bottom


def test_small_window_keeps_messages_and_setup_accessible(app, monkeypatch):
    monkeypatch.setattr("majsoul_hook.gui_dpi.work_area", lambda _: (0, 0, 1366, 728))
    app.dpi_layout.fit_window()
    app.root.deiconify()
    app.root.update()
    for widget in (app.tree, app.details, app.footer_label, *app.action_checks.values()):
        assert widget.winfo_ismapped()
        assert widget.winfo_width() > 1 and widget.winfo_height() > 1
    assert app.header.canvas.yview()[1] - app.header.canvas.yview()[0] < 1
    assert app.actions_bar.winfo_rooty() >= app.header.winfo_rooty() + app.header.winfo_height()
    assert app.actions_bar.winfo_rooty() + app.actions_bar.winfo_height() <= app.tabs.winfo_rooty()
    checkbox_positions = [check.winfo_rooty() for check in app.action_checks.values()]
    for widget in (app.update_button, app.process_entry, app.stop_button, app.language_combo):
        app.header._focus(SimpleNamespace(widget=widget))
        app.root.update()
        canvas = app.header.canvas
        x = widget.winfo_rootx() - canvas.winfo_rootx()
        y = widget.winfo_rooty() - canvas.winfo_rooty()
        assert 0 <= x <= canvas.winfo_width() - widget.winfo_width()
        assert 0 <= y <= canvas.winfo_height() - widget.winfo_height()
    assert [check.winfo_rooty() for check in app.action_checks.values()] == checkbox_positions
