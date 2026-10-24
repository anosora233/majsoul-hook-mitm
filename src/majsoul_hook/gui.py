"""Tkinter entry point; all capture, network and extraction work runs out of process."""

import json
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, font, ttk

from .cli import capture_process
from .gui_backend import ACTION_LABELS, BackendProcess, MessageHistory, local_resource_status
from .gui_dpi import DpiLayout, enable_dpi_awareness
from .gui_widgets import ScrollableHeader
from .resources import DEFAULT_BASE_URL


class InspectorApp:
    def __init__(self, root: tk.Tk, backend=None):
        self.root = root
        self.dpi_layout = DpiLayout(root)
        self.backend = backend or BackendProcess()
        self.history = MessageHistory()
        self.closing = False
        self.failed = False
        self.stopping = False
        self.process = tk.StringVar(value="Jantama_MahjongSoul")
        self.cosmetics = tk.BooleanVar(value=False)
        self.schema = tk.StringVar(value=str(Path("data/protocol.json").resolve()))
        self.base_url = tk.StringVar(value=DEFAULT_BASE_URL)
        self.search = tk.StringVar()
        self.action_filters = {action: tk.BooleanVar(value=True) for action in ACTION_LABELS}
        self.status = tk.StringVar(value="Idle")
        self.resource_summary = tk.StringVar(value="Reading local resources...")
        self.count = tk.StringVar(value="0 messages")
        root.title("Mahjong Soul | Traffic Inspector")
        self.dpi_layout.fit_window()
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        self.title_font = font.Font(root, family="Segoe UI", size=17, weight="bold")
        self.code_font = font.Font(root, family="Consolas", size=10)
        style.configure("Title.TLabel", font=self.title_font)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._build()
        self.dpi_layout.scale_widgets(self.dpi_layout.dpi / 96)
        root.bind("<Configure>", self._wrap_labels, add=True)
        self._local_resources()
        self.search.trace_add("write", lambda *_: self._rebuild())
        for selected in self.action_filters.values():
            selected.trace_add("write", lambda *_: self._rebuild())
        self._timer = root.after(100, self._poll)

    def _build(self):
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)
        self.header = ScrollableHeader(outer, self._layout_header)
        self.header.grid(row=0, column=0, sticky="ew")
        setup = self.header.content
        ttk.Label(setup, text="Mahjong Soul Traffic Inspector", style="Title.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            setup, text="Local capture | Protocol decoding | Local cosmetics | Message inspection"
        ).pack(anchor="w", pady=(2, 12))

        capture = ttk.LabelFrame(setup, text="Capture", padding=10)
        capture.pack(fill="x", pady=(0, 8))
        ttk.Label(capture, text="Process name / PID").grid(row=0, column=0, padx=(0, 8))
        self.process_entry = ttk.Entry(capture, textvariable=self.process, width=33)
        self.process_entry.grid(row=0, column=1, sticky="ew")
        self.cosmetics_check = ttk.Checkbutton(
            capture, text="Local cosmetics", variable=self.cosmetics
        )
        self.cosmetics_check.grid(row=0, column=2, padx=16)
        self.start_button = ttk.Button(capture, text="Start capture", command=self.start_capture)
        self.start_button.grid(row=0, column=3, padx=4)
        self.stop_button = ttk.Button(
            capture, text="Stop capture", command=self.stop_capture, state="disabled"
        )
        self.stop_button.grid(row=0, column=4, padx=4)
        ttk.Label(capture, textvariable=self.status).grid(row=0, column=5, sticky="e", padx=12)
        capture.columnconfigure(1, weight=1)
        capture.columnconfigure(5, weight=1)

        resources = ttk.LabelFrame(setup, text="Resources", padding=10)
        resources.pack(fill="x", pady=(0, 10))
        ttk.Label(resources, text="Resource file").grid(row=0, column=0, padx=(0, 8))
        self.schema_entry = ttk.Entry(resources, textvariable=self.schema)
        self.schema_entry.grid(row=0, column=1, sticky="ew")
        self.schema_entry.bind("<FocusOut>", lambda _: self._local_resources())
        self.browse_button = ttk.Button(resources, text="Browse...", command=self.browse)
        self.browse_button.grid(row=0, column=2, padx=6)
        self.check_button = ttk.Button(
            resources, text="Check version", command=lambda: self.resource_task("check")
        )
        self.check_button.grid(row=0, column=3, padx=4)
        self.update_button = ttk.Button(
            resources, text="Update resources", command=lambda: self.resource_task("update")
        )
        self.update_button.grid(row=0, column=4, padx=4)
        ttk.Label(resources, text="Base URL").grid(row=1, column=0, pady=(8, 0))
        self.url_entry = ttk.Entry(resources, textvariable=self.base_url)
        self.url_entry.grid(row=1, column=1, columnspan=4, sticky="ew", pady=(8, 0))
        self.resource_label = ttk.Label(resources, textvariable=self.resource_summary)
        self.resource_label.grid(row=2, column=0, columnspan=5, sticky="w", pady=(8, 0))
        resources.columnconfigure(1, weight=1)

        self.filter_bar = tools = ttk.Frame(outer)
        tools.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(tools, text="Search").pack(side="left")
        ttk.Entry(tools, textvariable=self.search, width=34).pack(side="left", padx=8)
        ttk.Button(tools, text="Clear messages", command=self.clear).pack(side="left", padx=8)
        ttk.Label(tools, textvariable=self.count).pack(side="right")
        self.actions_bar = actions = ttk.Frame(outer)
        actions.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(actions, text="Actions").pack(side="left", padx=(0, 8))
        self.action_checks = {}
        for action, label in ACTION_LABELS.items():
            check = ttk.Checkbutton(actions, text=label, variable=self.action_filters[action])
            check.pack(side="left", padx=(0, 12))
            self.action_checks[action] = check
        self.header.install_bindings()

        self.tabs = ttk.Notebook(outer)
        self.tabs.grid(row=3, column=0, sticky="nsew")
        stream = ttk.Frame(self.tabs)
        self.tabs.add(stream, text="Messages")
        log_frame = ttk.Frame(self.tabs)
        self.tabs.add(log_frame, text="Logs")
        self.log = self._text(log_frame)
        pane = ttk.Panedwindow(stream, orient="horizontal")
        pane.pack(fill="both", expand=True)
        list_frame, inspect_frame = ttk.Frame(pane), ttk.Frame(pane, padding=(10, 0, 0, 0))
        pane.add(list_frame, weight=3)
        pane.add(inspect_frame, weight=2)
        columns = ("time", "direction", "kind", "action", "flow", "id", "name", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        for name, label, width in zip(
            columns,
            ("Time", "Direction", "Type", "Actions", "Flow", "ID", "Protocol message", "Status"),
            (92, 70, 72, 62, 82, 45, 330, 105),
            strict=True,
        ):
            self.tree.heading(name, text=label)
            self.tree.column(name, width=width, minwidth=40, stretch=name == "name")
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
        ttk.Label(bar, text="Select a message to inspect").pack(side="left")
        ttk.Button(bar, text="Copy details", command=self.copy_details).pack(side="right")
        self.details = ttk.Notebook(inspect_frame)
        self.details.pack(fill="both", expand=True)
        self.detail_texts = {}
        for key, title in (
            ("summary", "Overview"),
            ("before", "Before"),
            ("after", "Actual content"),
            ("wire", "Wire bytes"),
        ):
            frame = ttk.Frame(self.details)
            self.details.add(frame, text=title)
            self.detail_texts[key] = self._text(frame)
        self.footer_label = ttk.Label(
            outer,
            text="In-memory history: latest 2,000 messages / approx. 64 MiB. "
            "Select a row to inspect original, modified, or injected content.",
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
                raise ValueError("Resource file missing. Update resources first.")
            self._start("capture")
            self.status.set("Starting capture...")
        except (OSError, ValueError, RuntimeError) as exc:
            self.status.set(str(exc))

    def stop_capture(self):
        if self.backend.task == "capture":
            self.stopping = True
            self.backend.stop()
            self.status.set("Stopping capture...")
            self.stop_button.configure(state="disabled")

    def resource_task(self, task):
        try:
            self._start(task)
            self.status.set(
                "Checking resource version..." if task == "check" else "Updating resources..."
            )
        except (OSError, ValueError, RuntimeError) as exc:
            self.status.set(str(exc))

    def browse(self):
        path = filedialog.askopenfilename(
            title="Choose a resource file", filetypes=[("JSON", "*.json")]
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
            self.resource_summary.set(f"Cannot read local resources: {exc}")

    def _show_resources(self, status):
        if not status["exists"]:
            self.resource_summary.set(
                "No local resources. Click Update resources to build protocol and cosmetic data."
            )
        else:
            version = (status.get("version") or "unknown")[:16]
            self.resource_summary.set(
                f"Local index {version} | Generated {status['generated_at']} | "
                f"RPC {status['methods']} / Characters {status['characters']} / "
                f"Skins {status['skins']} / Titles {status['titles']}"
                + (" | No cosmetic configuration" if not status["cosmetics"] else "")
            )
        if "update_available" in status:
            result = (
                "Remote index has changed"
                if status["update_available"]
                else "Local index matches the remote index"
            )
            self.resource_summary.set(
                self.resource_summary.get() + f"\n{result} ({status['remote_version'][:16]}); "
                "An index change does not mean every protocol or configuration table changed."
            )

    def _matches(self, record):
        return (
            self.action_filters.get(record.get("action"), self.action_filters["pass"]).get()
            and self.search.get().lower()
            in " ".join(
                str(record.get(key) or "")
                for key in ("name", "flow_id", "direction", "kind", "status")
            ).lower()
        )

    def _insert(self, key, record):
        if not self._matches(record):
            return
        stamp = datetime.fromtimestamp(record.get("timestamp", 0)).strftime("%H:%M:%S.%f")[:-3]
        self.tree.insert(
            "",
            "end",
            iid=key,
            values=(
                stamp,
                "C -> S" if record.get("direction") == "client_to_server" else "S -> C",
                record.get("kind", ""),
                ACTION_LABELS.get(record.get("action"), record.get("action", "")),
                record.get("flow_id", "")[:8],
                record.get("request_id") if record.get("request_id") is not None else "",
                record.get("name") or "<unknown message>",
                record.get("status", ""),
            ),
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
        self.count.set(f"{len(self.history.items)} retained / {self.backend.inbox.dropped} dropped")

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
                "note": "Local responses and notifications appear as separate Injected rows.",
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
            self._replace(text, "Select a message.")

    def copy_details(self):
        record = self._selected()
        if record:
            self.root.clipboard_clear()
            self.root.clipboard_append(json.dumps(record, ensure_ascii=False, indent=2))

    def clear(self):
        self.history.clear()
        if children := self.tree.get_children():
            self.tree.delete(*children)
        self.count.set("0 messages")
        self._clear_details()

    def _event(self, event):
        kind = event.get("event")
        if kind == "message":
            self._append(event)
        elif kind == "ready":
            if not self.closing and not self.stopping:
                self.status.set("Capturing")
        elif kind == "resources":
            self._show_resources(event["status"])
            self.status.set(
                "Resources updated" if self.backend.task == "update" else "Resource check complete"
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
                self.status.set(f"Failed: {content}")
                self.tabs.select(1)
        elif kind == "finished":
            self.backend.acknowledge_finished()
            self._busy()
            if not self.failed:
                if event["code"]:
                    self.status.set(f"Worker exited with code {event['code']}; see Logs")
                elif event["task"] == "capture":
                    self.status.set("Capture stopped")

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
        self.status.set("Stopping the worker and closing...")
        self.backend.stop(timeout=15 if self.backend.task == "capture" else 2)


def main():
    enable_dpi_awareness()
    root = tk.Tk()
    InspectorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
