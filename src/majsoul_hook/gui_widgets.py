"""Scrollable setup controls that leave room for the message inspector."""

import tkinter as tk
from tkinter import ttk


class ScrollableHeader(ttk.Frame):
    def __init__(self, parent, on_resize):
        super().__init__(parent)
        self.on_resize = on_resize
        self.grid_propagate(False)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vertical = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.vertical.grid(row=0, column=1, sticky="ns")
        self.horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.horizontal.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=self.vertical.set, xscrollcommand=self.horizontal.set)
        self.content = ttk.Frame(self.canvas)
        self.item = self.canvas.create_window(0, 0, anchor="nw", window=self.content)
        self.canvas.bind("<Configure>", self._sync)
        self.content.bind("<Configure>", self._sync)
        self.tag = f"HeaderScroll:{self}"
        self.bind_class(self.tag, "<MouseWheel>", self._wheel)
        self.bind_class(self.tag, "<Shift-MouseWheel>", lambda e: self._wheel(e, horizontal=True))
        self.bind_class(self.tag, "<Button-4>", self._wheel)
        self.bind_class(self.tag, "<Button-5>", self._wheel)
        self.bind_class(self.tag, "<FocusIn>", self._focus)

    def install_bindings(self):
        def visit(widget):
            widget.bindtags((widget.bindtags()[0], self.tag, *widget.bindtags()[1:]))
            for child in widget.winfo_children():
                visit(child)

        visit(self.content)
        self.canvas.bindtags((str(self.canvas), self.tag, *self.canvas.bindtags()[1:]))

    def _sync(self, _event=None):
        width = max(self.canvas.winfo_width(), self.content.winfo_reqwidth())
        self.canvas.itemconfigure(self.item, width=width)
        self.canvas.configure(scrollregion=(0, 0, width, self.content.winfo_reqheight()))
        self.on_resize()

    def _wheel(self, event, horizontal=False):
        view = self.canvas.xview if horizontal else self.canvas.yview
        if view() == (0.0, 1.0):
            return
        direction = (
            (-1 if event.num == 4 else 1) if event.num in (4, 5) else (-1 if event.delta > 0 else 1)
        )
        scroll = self.canvas.xview_scroll if horizontal else self.canvas.yview_scroll
        scroll(direction * 3, "units")
        return "break"

    def _focus(self, event):
        widget = event.widget
        if not widget.winfo_ismapped():
            return
        for position, length, viewport, total, view, move in (
            (
                widget.winfo_rootx() - self.content.winfo_rootx(),
                widget.winfo_width(),
                self.canvas.winfo_width(),
                self.content.winfo_width(),
                self.canvas.xview,
                self.canvas.xview_moveto,
            ),
            (
                widget.winfo_rooty() - self.content.winfo_rooty(),
                widget.winfo_height(),
                self.canvas.winfo_height(),
                self.content.winfo_height(),
                self.canvas.yview,
                self.canvas.yview_moveto,
            ),
        ):
            start = view()[0] * total
            if position < start:
                move(position / max(1, total))
            elif position + length > start + viewport:
                move((position + length - viewport) / max(1, total))
