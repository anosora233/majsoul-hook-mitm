from types import SimpleNamespace

import pytest

from majsoul_hook.gui_backend import DEFAULT_BASE_URL, EventInbox, MessageHistory


@pytest.fixture
def app(tmp_path, monkeypatch):
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
    instance = InspectorApp(root, Backend())
    path = tmp_path / "protocol.json"
    path.write_text("{}")
    instance.schema.set(str(path))
    yield instance
    root.after_cancel(instance._timer)
    root.destroy()


def test_capture_controls_and_stop_before_ready(app):
    app.process.set("custom-game.exe")
    app.cosmetics.set(True)
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
    width, height = app.root.winfo_width(), app.root.winfo_height()
    monkeypatch.setattr(
        "majsoul_hook.gui_dpi.window_bounds",
        lambda _: (-1400, 300, -1400 + width + 26, 300 + height + 71),
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


def test_small_hidpi_view_keeps_messages_and_setup_accessible(app, monkeypatch):
    monkeypatch.setattr("majsoul_hook.gui_dpi.window_dpi", lambda _: 192)
    monkeypatch.setattr("majsoul_hook.gui_dpi.work_area", lambda _: (0, 0, 1366, 728))
    app.dpi_layout.refresh()
    app.dpi_layout.fit_window()
    app.root.deiconify()
    app.root.update()
    assert app.tree.winfo_ismapped() and app.tree.winfo_height() >= 140
    assert app.details.winfo_ismapped() and app.details.winfo_width() >= 200
    assert app.footer_label.winfo_ismapped()
    assert app.header.canvas.yview()[1] - app.header.canvas.yview()[0] < 1
    for check in app.action_checks.values():
        assert check.winfo_ismapped()
        assert check.winfo_rootx() >= app.root.winfo_rootx()
        assert check.winfo_rootx() + check.winfo_width() <= (
            app.root.winfo_rootx() + app.root.winfo_width()
        )
        assert check.winfo_rooty() >= app.header.winfo_rooty() + app.header.winfo_height()
        assert check.winfo_rooty() + check.winfo_height() <= app.tabs.winfo_rooty()
    checkbox_positions = [check.winfo_rooty() for check in app.action_checks.values()]
    for widget in (app.update_button, app.process_entry, app.stop_button):
        app.header._focus(SimpleNamespace(widget=widget))
        app.root.update()
        canvas = app.header.canvas
        assert canvas.winfo_rootx() <= widget.winfo_rootx()
        assert widget.winfo_rootx() + widget.winfo_width() <= (
            canvas.winfo_rootx() + canvas.winfo_width()
        )
        assert canvas.winfo_rooty() <= widget.winfo_rooty()
        assert widget.winfo_rooty() + widget.winfo_height() <= (
            canvas.winfo_rooty() + canvas.winfo_height()
        )
    assert [check.winfo_rooty() for check in app.action_checks.values()] == checkbox_positions
