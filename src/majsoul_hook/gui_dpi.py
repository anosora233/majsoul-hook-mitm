"""Windows DPI awareness and Tk pixel geometry, without a GUI dependency."""

import ctypes
import sys
from ctypes import wintypes
from tkinter import font, ttk


def enable_dpi_awareness():
    """Call before Tk creates an HWND. Older Windows versions use a fallback."""
    if sys.platform != "win32":
        return
    try:
        user32 = ctypes.windll.user32
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass
    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def window_dpi(root):
    if sys.platform == "win32":
        try:
            api = ctypes.windll.user32.GetDpiForWindow
            api.argtypes = [wintypes.HWND]
            api.restype = wintypes.UINT
            if dpi := api(root.winfo_id()):
                return float(dpi)
        except (AttributeError, OSError):
            pass
    return float(root.winfo_fpixels("1i"))


def work_area(root):
    """Return the current monitor's usable bounds, excluding its taskbar."""
    if sys.platform == "win32":
        try:

            class MonitorInfo(ctypes.Structure):
                _fields_ = [
                    ("size", wintypes.DWORD),
                    ("monitor", wintypes.RECT),
                    ("work", wintypes.RECT),
                    ("flags", wintypes.DWORD),
                ]

            user32 = ctypes.windll.user32
            monitor_from_window = user32.MonitorFromWindow
            monitor_from_window.argtypes = [wintypes.HWND, wintypes.DWORD]
            monitor_from_window.restype = wintypes.HANDLE
            get_info = user32.GetMonitorInfoW
            get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
            get_info.restype = wintypes.BOOL
            info = MonitorInfo(size=ctypes.sizeof(MonitorInfo))
            if get_info(monitor_from_window(root.winfo_id(), 2), ctypes.byref(info)):
                return info.work.left, info.work.top, info.work.right, info.work.bottom
        except (AttributeError, OSError):
            pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


def native_window(root):
    api = ctypes.windll.user32.GetAncestor
    api.argtypes = [wintypes.HWND, wintypes.UINT]
    api.restype = wintypes.HWND
    return api(root.winfo_id(), 2)


def window_bounds(root):
    """Include the native frame and title bar when available."""
    if sys.platform == "win32":
        api = ctypes.windll.user32.GetWindowRect
        api.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        api.restype = wintypes.BOOL
        rect = wintypes.RECT()
        if api(native_window(root), ctypes.byref(rect)):
            return rect.left, rect.top, rect.right, rect.bottom
    x, y = root.winfo_rootx(), root.winfo_rooty()
    return x, y, x + root.winfo_width(), y + root.winfo_height()


def place_window(root, x, y, width, height):
    if sys.platform == "win32":
        api = ctypes.windll.user32.SetWindowPos
        api.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        api.restype = wintypes.BOOL
        # Absolute virtual-desktop coordinates also support monitors left of zero.
        if api(native_window(root), None, x, y, width, height, 0x0004 | 0x0010):
            return
    root.geometry(f"{width}x{height}+{x}+{y}")


class DpiLayout:
    def __init__(self, root):
        self.root = root
        self.dpi = window_dpi(root)
        root.tk.call("tk", "scaling", self.dpi / 72)
        self._constraint = None
        root.bind("<Map>", self._mapped, add=True)

    def _mapped(self, event):
        if event.widget is self.root:
            self._schedule_constraint()

    def _schedule_constraint(self):
        if self._constraint is not None:
            self.root.after_cancel(self._constraint)
        self._constraint = self.root.after_idle(self.constrain_window)

    def constrain_window(self):
        self._constraint = None
        if not self.root.winfo_ismapped() or self.root.state() != "normal":
            return
        left, top, right, bottom = work_area(self.root)
        x, y, far_x, far_y = window_bounds(self.root)
        width, height = min(far_x - x, right - left), min(far_y - y, bottom - top)
        frame_width = far_x - x - self.root.winfo_width()
        frame_height = far_y - y - self.root.winfo_height()
        min_width, min_height = self.root.minsize()
        self.root.minsize(
            min(min_width, max(1, width - frame_width)),
            min(min_height, max(1, height - frame_height)),
        )
        target_x = max(left, min(x, right - width))
        target_y = max(top, min(y, bottom - height))
        if (x, y, far_x - x, far_y - y) != (target_x, target_y, width, height):
            place_window(self.root, target_x, target_y, width, height)

    def pixels(self, value):
        return max(1, round(value * self.dpi / 96))

    def fit_window(self, width=None, height=None):
        left, top, right, bottom = work_area(self.root)
        available_width, available_height = right - left, bottom - top
        width = min(width or self.pixels(1320), round(available_width * 0.94))
        height = min(height or self.pixels(850), round(available_height * 0.90))
        self.root.minsize(min(self.pixels(1080), width), min(self.pixels(680), height))
        self.root.geometry(f"{width}x{height}")
        self._schedule_constraint()

    def scale_widgets(self, ratio):
        """Scale our explicit pixel distances, leaving character widths in font units."""

        def distances(value):
            parts = (
                value if isinstance(value, (tuple, list)) else self.root.tk.splitlist(str(value))
            )
            return tuple(round(self.root.winfo_pixels(part) * ratio) for part in parts)

        def visit(widget):
            options = widget.keys()
            if "padding" in options and str(widget.cget("padding")):
                widget.configure(padding=distances(widget.cget("padding")))
            manager = widget.winfo_manager()
            if manager in ("grid", "pack"):
                info = widget.grid_info() if manager == "grid" else widget.pack_info()
                update = {
                    key: distances(info[key])
                    for key in ("padx", "pady", "ipadx", "ipady")
                    if key in info
                }
                if manager == "grid":
                    widget.grid_configure(**update)
                else:
                    widget.pack_configure(**update)
            if isinstance(widget, ttk.Treeview):
                for column in widget["columns"]:
                    widget.column(
                        column,
                        width=round(widget.column(column, "width") * ratio),
                        minwidth=round(widget.column(column, "minwidth") * ratio),
                    )
            for child in widget.winfo_children():
                visit(child)

        for child in self.root.winfo_children():
            visit(child)
        line_height = font.nametofont("TkDefaultFont", root=self.root).metrics("linespace")
        ttk.Style(self.root).configure(
            "Treeview", rowheight=max(self.pixels(27), line_height + self.pixels(8))
        )

    def refresh(self):
        dpi = window_dpi(self.root)
        if abs(dpi - self.dpi) < 1:
            return
        ratio = dpi / self.dpi
        self.dpi = dpi
        self.root.tk.call("tk", "scaling", dpi / 72)
        # Tk 8.6 caches font metrics: reconfigure named fonts after scaling changes.
        for name in font.names(self.root):
            current = font.nametofont(name, root=self.root)
            current.configure(size=current.cget("size"))
        self.scale_widgets(ratio)
        self.fit_window(
            round(self.root.winfo_width() * ratio), round(self.root.winfo_height() * ratio)
        )
