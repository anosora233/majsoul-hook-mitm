"""Tkinter entry point; all capture, network and extraction work runs out of process."""

import json
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, font, ttk

from .cli import capture_process
from .gui_backend import ACTION_LABELS, BackendProcess, MessageHistory, local_resource_status
from .gui_dpi import DpiLayout, enable_dpi_awareness
from .gui_i18n import (
    LANGUAGES,
    MESSAGE_LABELS,
    N_,
    detect_language,
    load_language,
    save_language,
    translate,
)
from .gui_widgets import ScrollableHeader
from .resources import DEFAULT_BASE_URL

MESSAGE_COLUMNS = (
    ("time", N_("Time"), 88),
    ("direction", N_("Direction"), 60),
    ("kind", N_("Type"), 60),
    ("action", N_("Actions"), 62),
    ("flow", N_("Flow"), 60),
    ("id", N_("ID"), 38),
    ("name", N_("Protocol message"), 440),
    ("status", N_("Status"), 70),
)


class InspectorApp:
    def __init__(self, root: tk.Tk, backend=None, *, settings_path=Path("data/gui-settings.json")):
        self.root = root
        self.settings_path = settings_path
        self.language_preference = load_language(settings_path)
        self.language = (
            detect_language() if self.language_preference == "auto" else self.language_preference
        )
        self._text_targets = []
        self._tab_targets = []
        self._variable_sources = {}
        self._resource_status = None
        self.dpi_layout = DpiLayout(root)
        self.backend = backend or BackendProcess()
        self.history = MessageHistory()
        self.closing = False
        self.failed = False
        self.stopping = False
        self.process = tk.StringVar(value="Jantama_MahjongSoul")
        self.cosmetics = tk.BooleanVar(value=True)
        self.schema = tk.StringVar(value=str(Path("data/protocol.json").resolve()))
        self.base_url = tk.StringVar(value=DEFAULT_BASE_URL)
        self.search = tk.StringVar()
        self.action_filters = {action: tk.BooleanVar(value=True) for action in ACTION_LABELS}
        self.status = tk.StringVar()
        self.resource_summary = tk.StringVar()
        self.count = tk.StringVar()
        self._set(self.status, "Idle")
        self._set(self.resource_summary, "Reading local resources...")
        self._set(self.count, "0 messages")
        root.title(self.tr("Mahjong Soul | Traffic Inspector"))
        self.dpi_layout.fit_window()
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        self.title_font = font.nametofont("TkDefaultFont", root=root).copy()
        self.title_font.configure(size=17, weight="bold")
        self.code_font = font.nametofont("TkFixedFont", root=root).copy()
        self.code_font.configure(size=10)
        style.configure("Title.TLabel", font=self.title_font)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._build()
        self._clear_details()
        self.dpi_layout.scale_widgets(self.dpi_layout.dpi / 96)
        root.bind("<Configure>", self._wrap_labels, add=True)
        self._local_resources()
        self.search.trace_add("write", lambda *_: self._rebuild())
        for selected in self.action_filters.values():
            selected.trace_add("write", lambda *_: self._rebuild())
        self._timer = root.after(100, self._poll)

    def tr(self, source, **values):
        return translate(self.language, source, **values)

    def _widget(self, factory, *args, **options):
        source = options.get("text")
        if source is not None:
            options["text"] = self.tr(source)
        widget = factory(*args, **options)
        if source is not None:
            self._text_targets.append((widget, source))
        return widget

    def _set(self, variable, source, **values):
        self._variable_sources[str(variable)] = (variable, source, values)
        variable.set(self.tr(source, **values))

    def _language_options(self):
        self.language_combo.configure(values=[self.tr(label) for label in LANGUAGES.values()])
        self.language_combo.current(list(LANGUAGES).index(self.language_preference))

    def set_language(self, preference):
        if preference not in LANGUAGES:
            raise ValueError(f"Unsupported GUI language: {preference}")
        self.language_preference = preference
        self.language = detect_language() if preference == "auto" else preference
        self.root.title(self.tr("Mahjong Soul | Traffic Inspector"))
        self._language_options()
        for widget, source in self._text_targets:
            widget.configure(text=self.tr(source))
        for notebook, frame, source in self._tab_targets:
            notebook.tab(frame, text=self.tr(source))
        for column, source, _ in MESSAGE_COLUMNS:
            self.tree.heading(column, text=self.tr(source))
        for variable, source, values in self._variable_sources.values():
            variable.set(self.tr(source, **values))
        if self._resource_status is not None:
            self._show_resources(self._resource_status)
        xview, yview = self.tree.xview(), self.tree.yview()
        self._rebuild()
        self.inspect()
        self.tree.xview_moveto(xview[0])
        self.tree.yview_moveto(yview[0])
        self._layout_header()
        try:
            save_language(self.settings_path, preference)
        except OSError as exc:
            self._set(self.status, "Cannot save language preference: {error}", error=str(exc))

    def _build(self):
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)
        self.header = ScrollableHeader(outer, self._layout_header)
        self.header.grid(row=0, column=0, sticky="ew")
        setup = self.header.content
        title_bar = ttk.Frame(setup)
        title_bar.pack(fill="x")
        self._widget(
            ttk.Label, title_bar, text=N_("Mahjong Soul Traffic Inspector"), style="Title.TLabel"
        ).pack(side="left")
        self.language_combo = ttk.Combobox(title_bar, state="readonly", width=20)
        self._language_options()
        self.language_combo.pack(side="right")
        self._widget(ttk.Label, title_bar, text=N_("Language")).pack(side="right", padx=8)
        self.language_combo.bind(
            "<<ComboboxSelected>>",
            lambda _: self.set_language(list(LANGUAGES)[self.language_combo.current()]),
        )
        self._widget(
            ttk.Label,
            setup,
            text=N_("Local capture | Protocol decoding | Local cosmetics | Message inspection"),
        ).pack(anchor="w", pady=(2, 12))

        capture = self._widget(ttk.LabelFrame, setup, text=N_("Capture"), padding=10)
        capture.pack(fill="x", pady=(0, 8))
        self._widget(ttk.Label, capture, text=N_("Process name / PID")).grid(
            row=0, column=0, padx=(0, 8)
        )
        self.process_entry = ttk.Entry(capture, textvariable=self.process, width=33)
        self.process_entry.grid(row=0, column=1, sticky="ew")
        self.cosmetics_check = self._widget(
            ttk.Checkbutton, capture, text=N_("Local cosmetics"), variable=self.cosmetics
        )
        self.cosmetics_check.grid(row=0, column=2, padx=16)
        self.start_button = self._widget(
            ttk.Button, capture, text=N_("Start capture"), command=self.start_capture
        )
        self.start_button.grid(row=0, column=3, padx=4)
        self.stop_button = self._widget(
            ttk.Button,
            capture,
            text=N_("Stop capture"),
            command=self.stop_capture,
            state="disabled",
        )
        self.stop_button.grid(row=0, column=4, padx=4)
        self._widget(ttk.Label, capture, textvariable=self.status).grid(
            row=0, column=5, sticky="e", padx=12
        )
        capture.columnconfigure(1, weight=1)
        capture.columnconfigure(5, weight=1)

        resources = self._widget(ttk.LabelFrame, setup, text=N_("Resources"), padding=10)
        resources.pack(fill="x", pady=(0, 10))
        self._widget(ttk.Label, resources, text=N_("Resource file")).grid(
            row=0, column=0, padx=(0, 8)
        )
        self.schema_entry = ttk.Entry(resources, textvariable=self.schema)
        self.schema_entry.grid(row=0, column=1, sticky="ew")
        self.schema_entry.bind("<FocusOut>", lambda _: self._local_resources())
        self.browse_button = self._widget(
            ttk.Button, resources, text=N_("Browse..."), command=self.browse
        )
        self.browse_button.grid(row=0, column=2, padx=6)
        self.check_button = self._widget(
            ttk.Button,
            resources,
            text=N_("Check version"),
            command=lambda: self.resource_task("check"),
        )
        self.check_button.grid(row=0, column=3, padx=4)
        self.update_button = self._widget(
            ttk.Button,
            resources,
            text=N_("Update resources"),
            command=lambda: self.resource_task("update"),
        )
        self.update_button.grid(row=0, column=4, padx=4)
        self._widget(ttk.Label, resources, text=N_("Base URL")).grid(row=1, column=0, pady=(8, 0))
        self.url_entry = ttk.Entry(resources, textvariable=self.base_url)
        self.url_entry.grid(row=1, column=1, columnspan=4, sticky="ew", pady=(8, 0))
        self.resource_label = self._widget(ttk.Label, resources, textvariable=self.resource_summary)
        self.resource_label.grid(row=2, column=0, columnspan=5, sticky="w", pady=(8, 0))
        resources.columnconfigure(1, weight=1)

        self.filter_bar = tools = ttk.Frame(outer)
        tools.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self._widget(ttk.Label, tools, text=N_("Search")).pack(side="left")
        ttk.Entry(tools, textvariable=self.search, width=34).pack(side="left", padx=8)
        self._widget(ttk.Button, tools, text=N_("Clear messages"), command=self.clear).pack(
            side="left", padx=8
        )
        self._widget(ttk.Label, tools, textvariable=self.count).pack(side="right")
        self.actions_bar = actions = ttk.Frame(outer)
        actions.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self._widget(ttk.Label, actions, text=N_("Actions")).pack(side="left", padx=(0, 8))
        self.action_checks = {}
        for action, label in ACTION_LABELS.items():
            check = self._widget(
                ttk.Checkbutton, actions, text=label, variable=self.action_filters[action]
            )
            check.pack(side="left", padx=(0, 12))
            self.action_checks[action] = check
        self.header.install_bindings()

        self.tabs = ttk.Notebook(outer)
        self.tabs.grid(row=3, column=0, sticky="nsew")
        stream = ttk.Frame(self.tabs)
        self.tabs.add(stream, text=self.tr("Messages"))
        self._tab_targets.append((self.tabs, stream, N_("Messages")))
        log_frame = ttk.Frame(self.tabs)
        self.tabs.add(log_frame, text=self.tr("Logs"))
        self._tab_targets.append((self.tabs, log_frame, N_("Logs")))
        self.log = self._text(log_frame)
        pane = ttk.Panedwindow(stream, orient="horizontal")
        pane.pack(fill="both", expand=True)
        list_frame, inspect_frame = ttk.Frame(pane), ttk.Frame(pane, padding=(10, 0, 0, 0))
        pane.add(list_frame, weight=3)
        pane.add(inspect_frame, weight=2)
        columns = tuple(name for name, _, _ in MESSAGE_COLUMNS)
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            displaycolumns=tuple(name for name in columns if name != "name") + ("name",),
            show="headings",
            selectmode="browse",
        )
        for name, label, width in MESSAGE_COLUMNS:
            self.tree.heading(name, text=self.tr(label))
            self.tree.column(
                name,
                width=width,
                minwidth=240 if name == "name" else 28,
                stretch=name == "name",
                anchor="w" if name == "name" else "center",
            )
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll = ttk.Scrollbar(list_frame, orient="horizontal", command=self.tree.xview)
        xscroll.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        for action, color in {
            "pass": "#525966",
            "modified": "#8a4b12",
            "intercepted": "#7040a0",
            "local": "#16734b",
            "error": "#b42318",
        }.items():
            self.tree.tag_configure(action, foreground=color)
        self.tree.bind("<<TreeviewSelect>>", self.inspect)
        bar = ttk.Frame(inspect_frame)
        bar.pack(fill="x", pady=(0, 6))
        self._widget(ttk.Label, bar, text=N_("Select a message to inspect")).pack(side="left")
        self._widget(ttk.Button, bar, text=N_("Copy details"), command=self.copy_details).pack(
            side="right"
        )
        self.details = ttk.Notebook(inspect_frame)
        self.details.pack(fill="both", expand=True)
        self.detail_texts = {}
        for key, title in (
            ("summary", N_("Overview")),
            ("before", N_("Before")),
            ("after", N_("Actual content")),
            ("wire", N_("Wire bytes")),
        ):
            frame = ttk.Frame(self.details)
            self.details.add(frame, text=self.tr(title))
            self._tab_targets.append((self.details, frame, title))
            self.detail_texts[key] = self._text(frame)
        self.footer_label = self._widget(
            ttk.Label,
            outer,
            text=N_(
                "In-memory history: latest 2,000 messages / approx. 64 MiB. "
                "Select a row to inspect original, modified, or injected content."
            ),
        )
        self.footer_label.grid(row=4, column=0, sticky="ew", pady=(8, 0))

    def _layout_header(self):
        filters_height = (
            self.filter_bar.winfo_reqheight()
            + self.actions_bar.winfo_reqheight()
            + self.dpi_layout.pixels(16)
        )
        budget = max(
            self.dpi_layout.pixels(60), round(self.root.winfo_height() * 0.42) - filters_height
        )
        height = min(
            self.header.content.winfo_reqheight() + self.header.horizontal.winfo_reqheight(), budget
        )
        self.header.configure(height=height)

    def _wrap_labels(self, event):
        if event.widget is self.root:
            self._layout_header()
            width = max(100, event.width - self.dpi_layout.pixels(60))
            for label in (self.resource_label, self.footer_label):
                label.configure(wraplength=width)

    def _text(self, parent):
        text = tk.Text(parent, wrap="none", font=self.code_font, state="disabled", undo=False)
        yscroll = ttk.Scrollbar(parent, orient="vertical", command=text.yview)
        xscroll = ttk.Scrollbar(parent, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        return text

    @staticmethod
    def _replace(text, content):
        text.configure(state="normal")
        text.delete("1.0", "end")
        text.insert("1.0", content)
        text.configure(state="disabled")

    def _busy(self, task=None):
        state = "disabled" if task else "normal"
        for widget in (
            self.process_entry,
            self.cosmetics_check,
            self.schema_entry,
            self.url_entry,
            self.browse_button,
            self.check_button,
            self.update_button,
            self.start_button,
        ):
            widget.configure(state=state)
        self.stop_button.configure(state="normal" if task == "capture" else "disabled")

    def _start(self, task):
        config = {
            "process": capture_process(self.process.get()) if task == "capture" else "",
            "schema": str(Path(self.schema.get()).resolve()),
            "state": str(Path("data/cosmetics-state.json").resolve()),
            "cache": str(Path(".cache/bundles").resolve()),
            "cosmetics": self.cosmetics.get(),
            "base_url": self.base_url.get().strip(),
        }
        self.backend.start(task, config)
        self.failed = False
        self.stopping = False
        self._busy(task)

    def start_capture(self):
        try:
            if not Path(self.schema.get()).is_file():
                self._set(self.status, "Resource file missing. Update resources first.")
                return
            self._start("capture")
            self._set(self.status, "Starting capture...")
        except (OSError, ValueError, RuntimeError) as exc:
            self._set(self.status, str(exc))

    def stop_capture(self):
        if self.backend.task == "capture":
            self.stopping = True
            self.backend.stop()
            self._set(self.status, "Stopping capture...")
            self.stop_button.configure(state="disabled")

    def resource_task(self, task):
        try:
            self._start(task)
            self._set(
                self.status,
                N_("Checking resource version...")
                if task == "check"
                else N_("Updating resources..."),
            )
        except (OSError, ValueError, RuntimeError) as exc:
            self._set(self.status, str(exc))

    def browse(self):
        path = filedialog.askopenfilename(
            title=self.tr("Choose a resource file"), filetypes=[("JSON", "*.json")]
        )
        if path:
            self.schema.set(path)
            self._local_resources()

    def _local_resources(self):
        try:
            status = local_resource_status(Path(self.schema.get()))
            self._show_resources(status)
            self.base_url.set(status["base_url"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self._resource_status = None
            self._set(self.resource_summary, "Cannot read local resources: {error}", error=str(exc))

    def _show_resources(self, status):
        self._resource_status = status
        if not status["exists"]:
            self.resource_summary.set(
                self.tr(
                    "No local resources. Click Update resources to build "
                    "protocol and cosmetic data."
                )
            )
        else:
            version = (status.get("version") or self.tr("unknown"))[:16]
            self.resource_summary.set(
                self.tr(
                    "Local index {version} | Generated {generated_at} | RPC {methods} / "
                    "Characters {characters} / Skins {skins} / Titles {titles}",
                    **{**status, "version": version},
                )
                + (self.tr(" | No cosmetic configuration") if not status["cosmetics"] else "")
            )
        if "update_available" in status:
            result = (
                N_("Remote index has changed")
                if status["update_available"]
                else N_("Local index matches the remote index")
            )
            self.resource_summary.set(
                self.resource_summary.get()
                + f"\n{self.tr(result)} ({status['remote_version'][:16]}); "
                + self.tr(
                    "An index change does not mean every protocol or configuration table changed."
                )
            )

    def _matches(self, record, display_values):
        if not self.action_filters.get(record.get("action"), self.action_filters["pass"]).get():
            return False
        query = self.search.get().casefold()
        if not query:
            return True
        raw = [
            str(record.get(key) or "")
            for key in ("name", "flow_id", "direction", "kind", "status", "action")
        ]
        return query in " ".join([*raw, *(str(value) for value in display_values)]).casefold()

    def _row_values(self, record):
        stamp = datetime.fromtimestamp(record.get("timestamp", 0)).strftime("%H:%M:%S.%f")[:-3]
        return (
            stamp,
            "C→S" if record.get("direction") == "client_to_server" else "S→C",
            self.tr(MESSAGE_LABELS.get(record.get("kind"), record.get("kind", ""))),
            self.tr(ACTION_LABELS.get(record.get("action"), record.get("action", ""))),
            record.get("flow_id", "")[:8],
            record.get("request_id") if record.get("request_id") is not None else "",
            record.get("name") or self.tr("<unknown message>"),
            self.tr(MESSAGE_LABELS.get(record.get("status"), record.get("status", ""))),
        )

    def _insert(self, key, record):
        values = self._row_values(record)
        if not self._matches(record, values):
            return
        self.tree.insert(
            "",
            "end",
            iid=key,
            values=values,
            tags=(record.get("action", "pass"),),
        )

    def _rebuild(self):
        selected = self.tree.selection()
        if children := self.tree.get_children():
            self.tree.delete(*children)
        for key, (record, _) in self.history.items.items():
            self._insert(key, record)
        if selected and self.tree.exists(selected[0]):
            self.tree.selection_set(selected[0])
        else:
            self._clear_details()

    def _append(self, record):
        selected = self.tree.selection()
        key, removed = self.history.append(record)
        for old in removed:
            if self.tree.exists(old):
                self.tree.delete(old)
        if selected and selected[0] in removed:
            self._clear_details()
        self._insert(key, record)
        if not selected and self.tree.exists(key):
            self.tree.see(key)
        self._set(
            self.count,
            "{retained} retained / {dropped} dropped",
            retained=len(self.history.items),
            dropped=self.backend.inbox.dropped,
        )

    def _selected(self):
        selected = self.tree.selection()
        item = self.history.items.get(selected[0]) if selected else None
        return item[0] if item else None

    def inspect(self, _event=None):
        record = self._selected()
        if record is None:
            self._clear_details()
            return
        metadata = {
            k: v
            for k, v in record.items()
            if k not in {"before", "after", "data", "wire_before", "wire_after", "payload_base64"}
        }

        def dump(value):
            return json.dumps(value, ensure_ascii=False, indent=2)

        self._replace(self.detail_texts["summary"], dump(metadata))
        self._replace(self.detail_texts["before"], dump(record.get("before")))
        after = (
            record.get("after")
            if record.get("retained", True)
            else {
                "blocked": True,
                "note": self.tr(
                    "Local responses and notifications appear as separate Injected rows."
                ),
            }
        )
        self._replace(self.detail_texts["after"], dump(after))
        self._replace(
            self.detail_texts["wire"],
            dump(
                {
                    "encoding": "Base64 (complete protocol frame)",
                    "Before": record.get("wire_before"),
                    "forwarded_or_injected": record.get("wire_after"),
                }
            ),
        )

    def _clear_details(self):
        for text in self.detail_texts.values():
            self._replace(text, self.tr("Select a message."))

    def copy_details(self):
        record = self._selected()
        if record:
            self.root.clipboard_clear()
            self.root.clipboard_append(json.dumps(record, ensure_ascii=False, indent=2))

    def clear(self):
        self.history.clear()
        if children := self.tree.get_children():
            self.tree.delete(*children)
        self._set(self.count, "0 messages")
        self._clear_details()

    def _event(self, event):
        kind = event.get("event")
        if kind == "message":
            self._append(event)
        elif kind == "ready":
            if not self.closing and not self.stopping:
                self._set(self.status, "Capturing")
        elif kind == "resources":
            self._show_resources(event["status"])
            self._set(
                self.status,
                N_("Resources updated")
                if self.backend.task == "update"
                else N_("Resource check complete"),
            )
        elif kind in ("error", "log"):
            content = event.get("message") or event.get("text", "")
            self.log.configure(state="normal")
            self.log.insert("end", content + "\n")
            # Keep diagnostics bounded as well as decoded messages.
            lines = int(self.log.index("end-1c").split(".")[0])
            if lines > 2000:
                self.log.delete("1.0", f"{lines - 2000}.0")
            self.log.see("end")
            self.log.configure(state="disabled")
            if kind == "error":
                self.failed = True
                self._set(self.status, "Failed: {error}", error=content)
                self.tabs.select(1)
        elif kind == "finished":
            self.backend.acknowledge_finished()
            self._busy()
            if not self.failed:
                if event["code"]:
                    self._set(
                        self.status, "Worker exited with code {code}; see Logs", code=event["code"]
                    )
                elif event["task"] == "capture":
                    self._set(self.status, "Capture stopped")

    def _poll(self):
        self.dpi_layout.refresh()
        for event in self.backend.inbox.drain():
            self._event(event)
        if self.closing and not self.backend.running:
            self.root.destroy()
            return
        self._timer = self.root.after(100, self._poll)

    def close(self):
        if self.closing:
            return
        self.closing = True
        self._busy("closing")
        self._set(self.status, "Stopping the worker and closing...")
        self.backend.stop(timeout=15 if self.backend.task == "capture" else 2)


def main():
    enable_dpi_awareness()
    root = tk.Tk()
    InspectorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
