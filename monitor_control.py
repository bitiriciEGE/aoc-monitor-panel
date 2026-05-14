"""
AOC Monitor Kontrol Paneli v5.1
Desteklenen model: AOC Q27G42ZE (27" QHD 180Hz)
DDC/CI via Windows dxva2.dll — her komut icin taze handle (handle-sharing duzeltmesi)
Mavi Isik Filtresi: GDI Gamma Ramp (DDC/CI bagimsiz)
"""
import tkinter as tk
from tkinter import ttk, messagebox
import ctypes
from ctypes import wintypes, windll, byref
import threading

# ══════════════════════════════════════════════════════════════════════
# Design tokens
# ══════════════════════════════════════════════════════════════════════
BG       = "#07070c"
SURFACE  = "#14161f"
CARD     = "#1a1d2e"
BORDER   = "#1f2230"
BORDER_B = "#2a2d42"
FG       = "#e8ecf3"
FG_DIM   = "#8a93a6"
FG_MUTE  = "#5a627a"
CYAN     = "#00d4ff"
CYAN_BG  = "#051c24"
CYAN_B   = "#006680"
ORANGE   = "#ff6b2b"
ORANGE_B = "#7a2800"
GREEN    = "#4ade80"
GREEN_B  = "#16532d"
RED      = "#ff3b5c"
RED_B    = "#7a0c1c"
AMBER    = "#f5c451"
AMBER_B  = "#7a4a00"

MONO = "Consolas"
SANS = "Segoe UI"

# ── VCP codes ──────────────────────────────────────────────────────────
VCP_BRIGHTNESS  = 0x10
VCP_CONTRAST    = 0x12
VCP_COLOR_TEMP  = 0x14
VCP_RED_GAIN    = 0x16
VCP_GREEN_GAIN  = 0x18
VCP_BLUE_GAIN   = 0x1A
VCP_INPUT       = 0x60
VCP_VOLUME      = 0x62
VCP_POWER       = 0xD6
VCP_GAMING_MODE = 0xDC
VCP_RESTORE_ALL = 0x04
VCP_RESTORE_LUM = 0x05
VCP_RESTORE_CLR = 0x08

COLOR_TEMP_PRESETS = {
    "sRGB":   (0x01, "#ff7a3b", "#ffb56b", "~6500K"),
    "Warm":   (0x05, "#ffa15c", "#ffcfa3", "5000K"),
    "Normal": (0x06, "#fff2dc", "#fffaf0", "7500K"),
    "Cool":   (0x08, "#d6e6ff", "#a8c8ff", "9300K"),
    "User":   (0x0B, "#6b6b78", "#2c2c3a", "RGB"),
}

GAMING_MODES = {
    "Standard": 0x00, "FPS": 0x0B, "RTS": 0x0C,
    "Racing": 0x0D, "Gamer 1": 0x0E, "Gamer 2": 0x0F, "Gamer 3": 0x10,
}

INPUT_SOURCES = {"DisplayPort": 0x0F, "HDMI 1": 0x11, "HDMI 2": 0x12}

PROFILES = {
    "sabah_ders": {
        "name": "Sabah Dersi", "desc": "65% · Warm · Goz dostu",
        "bar": "#00d4ff", "bar2": "#0099cc",
        "icon": "☀", "brightness": 65, "contrast": 45,
        "color_temp": "Warm", "red_gain": 50, "green_gain": 50, "blue_gain": 50,
        "blue_filter": 80, "volume": 40,
    },
    "sabah_calis": {
        "name": "Sabah Calismasi", "desc": "85% · Cool · Ofis",
        "bar": "#f5c451", "bar2": "#ff9c1a",
        "icon": "💡", "brightness": 85, "contrast": 60,
        "color_temp": "Cool", "red_gain": 50, "green_gain": 50, "blue_gain": 50,
        "blue_filter": 100, "volume": 50,
    },
    "aksam_ders": {
        "name": "Aksam Dersi", "desc": "55% · User · Dusuk Mavi",
        "bar": "#ff6b2b", "bar2": "#c2410c",
        "icon": "🌙", "brightness": 55, "contrast": 50,
        "color_temp": "User", "red_gain": 58, "green_gain": 48, "blue_gain": 38,
        "blue_filter": 55, "volume": 35,
    },
    "counter_strike": {
        "name": "Counter Strike", "desc": "100% · FPS · Max",
        "bar": "#ff3b5c", "bar2": "#c2185b",
        "icon": "🎮", "brightness": 100, "contrast": 80,
        "color_temp": "Normal", "red_gain": 50, "green_gain": 50, "blue_gain": 50,
        "blue_filter": 100, "volume": 70,
    },
}


# ══════════════════════════════════════════════════════════════════════
# DDC/CI Engine
# Her DDC komutu icin taze handle alinir ve hemen yok edilir.
# Bu, Windows'un her iki monitore ayni handle vermesi sorununu cozer.
# ══════════════════════════════════════════════════════════════════════
class PhysMonStruct(ctypes.Structure):
    _fields_ = [("hPhysicalMonitor", ctypes.c_void_p),
                ("szDesc", ctypes.c_wchar * 128)]


class MonitorDDC:
    def __init__(self, number: int):
        self.number    = number
        self._last_err = ""
        self._apply_ok = True
        self._sim = {
            "brightness": 75, "contrast": 50, "color_temp": 0x06,
            "red_gain": 50, "green_gain": 50, "blue_gain": 50,
            "volume": 50, "blue_filter": 100, "gaming_mode": 0x00,
        }
        self.available = self._check()

    # ── Internal helpers ─────────────────────────────────────────────

    def _enum_hmons(self):
        mons = []
        PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                                  ctypes.c_void_p, ctypes.POINTER(wintypes.RECT),
                                  ctypes.c_void_p)
        def cb(h, *_): mons.append(h); return True
        windll.user32.EnumDisplayMonitors(None, None, PROC(cb), 0)
        return mons

    def _check(self) -> bool:
        try:
            mons = self._enum_hmons()
            return self.number <= len(mons)
        except:
            return False

    def _with_handle(self, fn):
        """
        Taze fiziksel monitor handle'i al -> fn(handle) cagir -> yok et.
        Her cagri kendi bagimsiz handle'ine sahiptir; paylasim olmaz.
        """
        try:
            mons = self._enum_hmons()
            if self.number > len(mons):
                return None
            hmon  = mons[self.number - 1]
            count = ctypes.c_ulong(0)
            ok = windll.dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(
                hmon, byref(count))
            if not ok or not count.value:
                return None
            arr = (PhysMonStruct * count.value)()
            windll.dxva2.GetPhysicalMonitorsFromHMONITOR(hmon, count.value, arr)
            handle = arr[0].hPhysicalMonitor
            try:
                return fn(handle)
            finally:
                windll.dxva2.DestroyPhysicalMonitors(count.value, arr)
        except Exception as e:
            self._last_err = str(e)
            return None

    def _display_name(self) -> str:
        class MINFOEX(ctypes.Structure):
            _fields_ = [("cbSize",    wintypes.DWORD),
                        ("rcMonitor", wintypes.RECT),
                        ("rcWork",    wintypes.RECT),
                        ("dwFlags",   wintypes.DWORD),
                        ("szDevice",  ctypes.c_wchar * 32)]
        try:
            mons = self._enum_hmons()
            if self.number > len(mons):
                return ""
            mi = MINFOEX()
            mi.cbSize = ctypes.sizeof(MINFOEX)
            windll.user32.GetMonitorInfoW(mons[self.number - 1], byref(mi))
            return mi.szDevice
        except:
            return ""

    def _set_vcp(self, code: int, value: int) -> bool:
        def do(h):
            ret = windll.dxva2.SetVCPFeature(
                h, ctypes.c_ubyte(code), ctypes.c_uint(value))
            if not ret:
                self._last_err = f"VCP 0x{code:02X}={value}: hata {ctypes.GetLastError()}"
            return bool(ret)
        result = self._with_handle(do)
        return result if result is not None else True  # handle yoksa sim modu

    # ── Brightness / Contrast ────────────────────────────────────────

    def get_brightness(self) -> int:
        def do(h):
            mn, cur, mx = ctypes.c_uint(0), ctypes.c_uint(0), ctypes.c_uint(0)
            windll.dxva2.GetMonitorBrightness(h, byref(mn), byref(cur), byref(mx))
            return int((cur.value / mx.value) * 100) if mx.value else cur.value
        v = self._with_handle(do)
        return v if v is not None else self._sim["brightness"]

    def set_brightness(self, v: int) -> bool:
        v = max(0, min(100, v))
        self._sim["brightness"] = v
        def do(h):
            ret = windll.dxva2.SetMonitorBrightness(h, ctypes.c_uint(v))
            if not ret:
                self._last_err = f"Brightness: {ctypes.GetLastError()}"
            return bool(ret)
        result = self._with_handle(do)
        return result if result is not None else True

    def get_contrast(self) -> int:
        def do(h):
            mn, cur, mx = ctypes.c_uint(0), ctypes.c_uint(0), ctypes.c_uint(0)
            windll.dxva2.GetMonitorContrast(h, byref(mn), byref(cur), byref(mx))
            return int((cur.value / mx.value) * 100) if mx.value else cur.value
        v = self._with_handle(do)
        return v if v is not None else self._sim["contrast"]

    def set_contrast(self, v: int) -> bool:
        v = max(0, min(100, v))
        self._sim["contrast"] = v
        def do(h):
            windll.dxva2.SetMonitorContrast(h, ctypes.c_uint(v))
            return True
        result = self._with_handle(do)
        return result if result is not None else True

    # ── Color Temp / RGB Gains ───────────────────────────────────────

    def get_color_temp_vcp(self): return self._sim["color_temp"]
    def set_color_temp(self, vcp):
        self._sim["color_temp"] = vcp
        return self._set_vcp(VCP_COLOR_TEMP, vcp)

    def get_red_gain(self):   return self._sim["red_gain"]
    def get_green_gain(self): return self._sim["green_gain"]
    def get_blue_gain(self):  return self._sim["blue_gain"]

    def set_red_gain(self, v: int) -> bool:
        v = max(0, min(100, v))
        self._sim["red_gain"] = v
        if self._sim["color_temp"] != 0x0B:
            self.set_color_temp(0x0B)
        return self._set_vcp(VCP_RED_GAIN, v)

    def set_green_gain(self, v: int) -> bool:
        v = max(0, min(100, v))
        self._sim["green_gain"] = v
        if self._sim["color_temp"] != 0x0B:
            self.set_color_temp(0x0B)
        return self._set_vcp(VCP_GREEN_GAIN, v)

    def set_blue_gain(self, v: int) -> bool:
        v = max(0, min(100, v))
        self._sim["blue_gain"] = v
        if self._sim["color_temp"] != 0x0B:
            self.set_color_temp(0x0B)
        return self._set_vcp(VCP_BLUE_GAIN, v)

    # ── Volume / Gaming / Input / Power ─────────────────────────────

    def get_volume(self): return self._sim["volume"]
    def set_volume(self, v: int) -> bool:
        v = max(0, min(100, v))
        self._sim["volume"] = v
        return self._set_vcp(VCP_VOLUME, v)

    def set_gaming_mode(self, vcp):
        self._sim["gaming_mode"] = vcp
        return self._set_vcp(VCP_GAMING_MODE, vcp)

    def set_input(self, vcp):  return self._set_vcp(VCP_INPUT, vcp)
    def set_power(self, state):
        return self._set_vcp(VCP_POWER, {"on": 1, "standby": 4, "off": 5}.get(state, 1))
    def restore_all(self):       self._set_vcp(VCP_RESTORE_ALL, 1)
    def restore_luminance(self): self._set_vcp(VCP_RESTORE_LUM, 1)
    def restore_color(self):     self._set_vcp(VCP_RESTORE_CLR, 1)

    # ── Blue Light Filter (GDI Gamma Ramp) ──────────────────────────

    def get_blue_filter(self): return self._sim["blue_filter"]
    def set_blue_filter(self, v: int) -> bool:
        v = max(0, min(100, v))
        self._sim["blue_filter"] = v
        try:
            name = self._display_name()
            if not name:
                return False
            hdc = windll.gdi32.CreateDCW(name, None, None, None)
            if not hdc:
                return False
            s = v / 100.0
            ramp = (ctypes.c_uint16 * 768)()
            for i in range(256):
                b = min(65535, i * 257)
                ramp[i] = b
                ramp[256 + i] = b
                ramp[512 + i] = int(b * s)
            result = windll.gdi32.SetDeviceGammaRamp(hdc, ramp)
            windll.gdi32.DeleteDC(hdc)
            return bool(result)
        except:
            return False

    # ── Profile apply ────────────────────────────────────────────────

    def apply_profile(self, p: dict) -> bool:
        b_ok = self.set_brightness(p["brightness"])
        c_ok = self.set_contrast(p["contrast"])
        ct_key = p.get("color_temp", "Normal")
        if ct_key in COLOR_TEMP_PRESETS:
            vcp_val = COLOR_TEMP_PRESETS[ct_key][0]
            self.set_color_temp(vcp_val)
            if vcp_val == 0x0B:
                self._set_vcp(VCP_RED_GAIN,   p.get("red_gain",   50))
                self._set_vcp(VCP_GREEN_GAIN, p.get("green_gain", 50))
                self._set_vcp(VCP_BLUE_GAIN,  p.get("blue_gain",  50))
        self.set_blue_filter(p.get("blue_filter", 100))
        self.set_volume(p.get("volume", 50))
        self._apply_ok = b_ok and c_ok
        return True


# ══════════════════════════════════════════════════════════════════════
# Custom Canvas Slider
# ══════════════════════════════════════════════════════════════════════
class CSlider(tk.Canvas):
    H = 28; PAD = 10; TH = 6; TR = 9

    def __init__(self, parent, from_=0, to=100, value=50,
                 color=CYAN, dark=CYAN_BG, command=None, bg=SURFACE, **kw):
        super().__init__(parent, height=self.H, bg=bg,
                         highlightthickness=0, cursor="hand2", **kw)
        self._bg = bg
        self.from_ = from_; self.to = to; self._v = value
        self.color = color; self.dark = dark; self.command = command
        self.bind("<Configure>",      lambda e: self.after(10, self._draw))
        self.bind("<Button-1>",       self._press)
        self.bind("<B1-Motion>",      self._drag)

    def _x(self, v):
        w = self.winfo_width()
        if w <= 2 * self.PAD: return self.PAD
        return self.PAD + int((v - self.from_) / (self.to - self.from_) * (w - 2 * self.PAD))

    def _v_from_x(self, x):
        w = self.winfo_width()
        r = (x - self.PAD) / (w - 2 * self.PAD)
        return int(max(self.from_, min(self.to, self.from_ + r * (self.to - self.from_))))

    def _draw(self):
        self.delete("all")
        w = self.winfo_width(); h = self.H
        if w < 20: return
        cx = self._x(self._v); cy = h // 2
        self.create_rectangle(self.PAD, cy - self.TH // 2,
                               w - self.PAD, cy + self.TH // 2,
                               fill="#0d0d18", outline=BORDER, width=1)
        if cx > self.PAD:
            self.create_rectangle(self.PAD + 1, cy - self.TH // 2 + 1,
                                   cx, cy + self.TH // 2 - 1,
                                   fill=self.color, outline="")
        self.create_oval(cx - self.TR - 2, cy - self.TR - 2,
                         cx + self.TR + 2, cy + self.TR + 2,
                         fill=self.dark, outline="")
        self.create_oval(cx - self.TR, cy - self.TR,
                         cx + self.TR, cy + self.TR,
                         fill=self.color, outline="#ffffff", width=1.5)
        self.create_oval(cx - 3, cy - 3, cx + 3, cy + 3,
                         fill="white", outline="")

    def _press(self, e):
        self._v = self._v_from_x(e.x); self._draw()
        if self.command: self.command(self._v)

    def _drag(self, e):
        self._v = self._v_from_x(e.x); self._draw()
        if self.command: self.command(self._v)

    def get(self): return self._v

    def set(self, v):
        self._v = max(self.from_, min(self.to, int(v)))
        self.after(10, self._draw)


# ══════════════════════════════════════════════════════════════════════
# UI Helpers
# ══════════════════════════════════════════════════════════════════════
def lbl(parent, text, font_size=11, bold=False, color=FG, bg=SURFACE, **kw):
    weight = "bold" if bold else "normal"
    return tk.Label(parent, text=text, bg=bg,
                    font=(SANS, font_size, weight), fg=color, **kw)


def mono(parent, text, font_size=9, color=FG_MUTE, bg=SURFACE, **kw):
    return tk.Label(parent, text=text, bg=bg,
                    font=(MONO, font_size), fg=color, **kw)


def card(parent, bg=CARD):
    return tk.Frame(parent, bg=bg, highlightthickness=1,
                    highlightbackground=BORDER)


def section_header(parent, title, vcp_hint="", bg=BG):
    row = tk.Frame(parent, bg=bg)
    row.pack(fill="x", pady=(14, 6))
    tk.Label(row, text=title.upper(), bg=bg, fg=FG,
             font=(SANS, 9, "bold")).pack(side="left")
    if vcp_hint:
        tk.Label(row, text=f"  {vcp_hint}", bg=bg, fg=FG_MUTE,
                 font=(MONO, 8)).pack(side="left")
    tk.Frame(row, bg=BORDER, height=1).pack(
        side="left", fill="x", expand=True, padx=(8, 0), pady=6)


def slider_row(parent, label, getter, setter, color=CYAN, dark=CYAN_BG,
               val_color=CYAN, hint="", bg=SURFACE):
    outer = tk.Frame(parent, bg=bg)
    outer.pack(fill="x", pady=5)

    hdr = tk.Frame(outer, bg=bg)
    hdr.pack(fill="x", pady=(0, 4))
    tk.Label(hdr, text=label, bg=bg, fg=FG, font=(SANS, 11)).pack(side="left")
    if hint:
        tk.Label(hdr, text=f"  {hint}", bg=bg, fg=FG_MUTE,
                 font=(MONO, 9)).pack(side="left")
    val_lbl = tk.Label(hdr, text="", bg=bg, fg=val_color,
                       font=(MONO, 11, "bold"))
    val_lbl.pack(side="right")

    def on_change(v):
        setter(int(v))
        val_lbl.config(text=f"{int(v)}%")

    sl = CSlider(outer, 0, 100, getter(), color=color, dark=dark,
                 command=on_change, bg=bg)
    sl.pack(fill="x")

    def load():
        v = getter()
        sl.set(v)
        val_lbl.config(text=f"{v}%")

    sl.after(300, load)
    return sl


# ══════════════════════════════════════════════════════════════════════
# Main App
# ══════════════════════════════════════════════════════════════════════
class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("AOC Monitor Kontrol Paneli")
        root.geometry("920x860")
        root.minsize(800, 640)
        root.configure(bg=BG)

        st = ttk.Style()
        st.theme_use("clam")
        st.configure("TNotebook",     background=BG,      borderwidth=0)
        st.configure("TNotebook.Tab", background=SURFACE, foreground=FG_DIM,
                     padding=[0, 0],  font=(SANS, 1))
        st.configure("TScrollbar",    background=SURFACE, troughcolor=BG,
                     borderwidth=0,   arrowcolor=FG_MUTE)

        self.monitors      = [MonitorDDC(1), MonitorDDC(2)]
        self._active_tab   = 0
        self._gaming_btns  = [[], []]
        self._input_btns   = [[], []]
        self._temp_btns    = [[], []]
        self._profile_btns = [[], []]

        self._build()

    # ── Window structure ──────────────────────────────────────────────

    def _build(self):
        self._titlebar()
        self._header()
        self._tab_bar()
        self._tab_frames = []
        self._content = tk.Frame(self.root, bg=BG)
        self._content.pack(fill="both", expand=True)
        for i in range(2):
            f = tk.Frame(self._content, bg=BG)
            self._tab_frames.append(f)
            self._build_tab(f, i)
        self._show_tab(0)
        self._footer()

    # ── Title bar ─────────────────────────────────────────────────────

    def _titlebar(self):
        bar = tk.Frame(self.root, bg="#0e0f1b", height=38)
        bar.pack(fill="x"); bar.pack_propagate(False)

        tl = tk.Frame(bar, bg="#0e0f1b")
        tl.pack(side="left", padx=14)
        for color in [RED, AMBER, GREEN]:
            c = tk.Canvas(tl, width=12, height=12, bg="#0e0f1b",
                          highlightthickness=0)
            c.create_oval(1, 1, 11, 11, fill=color, outline="")
            c.pack(side="left", padx=3, pady=13)

        tk.Label(bar, text="AOC Monitor Kontrol Paneli",
                 font=(SANS, 10), bg="#0e0f1b", fg=FG_DIM).pack(side="left", padx=4)
        mono(bar, "v5.1 · py3", 9, FG_MUTE, "#0e0f1b").pack(side="right", padx=14)

        bar.bind("<Button-1>",
                 lambda e: setattr(self, "_drag_xy",
                                   (e.x_root - self.root.winfo_x(),
                                    e.y_root - self.root.winfo_y())))
        bar.bind("<B1-Motion>",
                 lambda e: self.root.geometry(
                     f"+{e.x_root - self._drag_xy[0]}+{e.y_root - self._drag_xy[1]}"
                 ) if hasattr(self, "_drag_xy") else None)

    # ── Header ────────────────────────────────────────────────────────

    def _header(self):
        hdr = tk.Frame(self.root, bg=CARD, height=68)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        inner = tk.Frame(hdr, bg=CARD)
        inner.pack(fill="both", expand=True, padx=18, pady=10)

        logo = tk.Canvas(inner, width=40, height=40, bg=CARD, highlightthickness=0)
        logo.create_rectangle(0, 0, 40, 40, fill="#003a52", outline=CYAN, width=1)
        logo.create_rectangle(8, 8, 32, 32, fill="", outline="white", width=2)
        logo.create_line(8, 8, 20, 4, fill=CYAN, width=2)
        logo.pack(side="left", padx=(0, 12))

        tg = tk.Frame(inner, bg=CARD)
        tg.pack(side="left")
        tk.Label(tg, text="Q27G42ZE  ·  ", bg=CARD, fg=FG_MUTE,
                 font=(SANS, 14, "bold")).pack(side="left")
        tk.Label(tg, text="Kontrol Paneli", bg=CARD, fg=CYAN,
                 font=(SANS, 14, "bold")).pack(side="left")
        tk.Label(tg, text="DDC/CI · VCP · 27\" QHD 180Hz",
                 bg=CARD, fg=FG_MUTE, font=(MONO, 9)).pack(anchor="w")

        right = tk.Frame(inner, bg=CARD)
        right.pack(side="right")
        any_ddc = any(m.available for m in self.monitors)
        bdg_bg  = "#051c0e" if any_ddc else "#1c1000"
        bdg_fg  = GREEN    if any_ddc else AMBER
        bdg_txt = "● DDC/CI · Bagli" if any_ddc else "● Simulasyon"
        badge = tk.Label(right, text=bdg_txt, bg=bdg_bg, fg=bdg_fg,
                         font=(SANS, 9, "bold"), padx=10, pady=4)
        badge.pack(side="left", padx=(0, 8))
        badge.config(highlightthickness=1,
                     highlightbackground=GREEN_B if any_ddc else AMBER_B)

    # ── Custom Tab Bar ────────────────────────────────────────────────

    def _tab_bar(self):
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")
        bar = tk.Frame(self.root, bg=BG, height=50)
        bar.pack(fill="x"); bar.pack_propagate(False)

        inner = tk.Frame(bar, bg=BG)
        inner.pack(side="left", padx=14, pady=10)

        self._tab_btns = []
        for i, mon in enumerate(self.monitors):
            sim = "" if mon.available else " (Sim)"
            btn = tk.Button(
                inner,
                text=f"  Monitor {i + 1}{sim}  ",
                font=(SANS, 9),
                relief="flat", cursor="hand2",
                command=lambda idx=i: self._show_tab(idx)
            )
            btn.pack(side="left", padx=(0, 6))
            self._tab_btns.append(btn)

        self._style_tabs()
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

    def _style_tabs(self):
        for i, btn in enumerate(self._tab_btns):
            if i == self._active_tab:
                btn.config(bg=CARD, fg=CYAN,
                           highlightthickness=1, highlightbackground=CYAN_B,
                           pady=6)
            else:
                btn.config(bg=SURFACE, fg=FG_DIM,
                           highlightthickness=1, highlightbackground=BORDER,
                           pady=6)

    def _show_tab(self, idx: int):
        for f in self._tab_frames: f.pack_forget()
        self._tab_frames[idx].pack(fill="both", expand=True)
        self._active_tab = idx
        self._style_tabs()

    # ── Monitor Tab ───────────────────────────────────────────────────

    def _build_tab(self, parent, idx: int):
        mon = self.monitors[idx]
        columns = tk.Frame(parent, bg=BG)
        columns.pack(fill="both", expand=True)

        left = tk.Frame(columns, bg=BG, width=290)
        left.pack(side="left", fill="y", padx=(12, 0), pady=12)
        left.pack_propagate(False)

        tk.Frame(columns, bg=BORDER, width=1).pack(side="left", fill="y", pady=12)

        right_wrap = tk.Frame(columns, bg=BG)
        right_wrap.pack(side="left", fill="both", expand=True)

        self._left_panel(left, mon, idx)
        self._right_panel(right_wrap, mon, idx)

    # ── LEFT panel ────────────────────────────────────────────────────

    def _left_panel(self, parent, mon, idx):
        section_header(parent, "Hizli Profiller", bg=BG)
        grid = tk.Frame(parent, bg=BG)
        grid.pack(fill="x", pady=(0, 4))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        for col_i, (key, p) in enumerate(PROFILES.items()):
            self._profile_card(grid, p, mon, idx, col_i // 2, col_i % 2)

        section_header(parent, "Gaming Mode", "VCP 0xDC", bg=BG)
        chip_wrap = tk.Frame(parent, bg=BG)
        chip_wrap.pack(fill="x", pady=(0, 4))
        self._gaming_btns[idx] = []
        row_f = None
        for i, (label, vcp) in enumerate(GAMING_MODES.items()):
            if i % 4 == 0:
                row_f = tk.Frame(chip_wrap, bg=BG)
                row_f.pack(fill="x", pady=2)
            btn = self._chip(row_f, label,
                             lambda v=vcp, m=mon, ix=idx: self._set_gaming(v, m, ix))
            self._gaming_btns[idx].append((btn, vcp))

        section_header(parent, "Giris Kaynagi", "VCP 0x60", bg=BG)
        src_row = tk.Frame(parent, bg=BG)
        src_row.pack(fill="x", pady=(0, 4))
        self._input_btns[idx] = []
        for label, vcp in INPUT_SOURCES.items():
            btn = self._seg_btn(src_row, label,
                                lambda v=vcp, m=mon: m.set_input(v))
            btn.pack(side="left", padx=(0, 6), pady=2)
            self._input_btns[idx].append(btn)

        section_header(parent, "Guc Modu", "VCP 0xD6", bg=BG)
        pw_row = tk.Frame(parent, bg=BG)
        pw_row.pack(fill="x")
        for label, state, fg, hl in [
            ("⏻  Ac",      "on",      GREEN, GREEN_B),
            ("☽  Bekleme", "standby", AMBER, AMBER_B),
            ("✕  Kapat",   "off",     RED,   RED_B),
        ]:
            tk.Button(pw_row, text=label,
                      command=lambda s=state, m=mon: m.set_power(s),
                      bg=CARD, fg=fg, font=(SANS, 9, "bold"),
                      relief="flat", cursor="hand2",
                      padx=8, pady=8,
                      highlightthickness=1, highlightbackground=hl,
                      activebackground=BORDER
                      ).pack(side="left", padx=(0, 6))

    def _profile_card(self, grid, p, mon, idx, row, col):
        frm = tk.Frame(grid, bg=CARD, cursor="hand2",
                       highlightthickness=1, highlightbackground=BORDER)
        frm.grid(row=row, column=col,
                 padx=(0, 6) if col == 0 else 0,
                 pady=(0, 6), sticky="nsew")

        def click():
            threading.Thread(
                target=lambda: self._apply_profile(p, mon), daemon=True
            ).start()

        inner = tk.Frame(frm, bg=CARD)
        inner.pack(fill="both", padx=(10, 8), pady=8)

        bar_c = tk.Canvas(frm, width=3, bg=CARD, highlightthickness=0)
        bar_c.place(x=0, y=0, relheight=1)
        frm.update_idletasks()
        bar_c.create_rectangle(0, 4, 3, 60, fill=p["bar"], outline="")

        top = tk.Frame(inner, bg=CARD)
        top.pack(fill="x")
        tk.Label(top, text=p["icon"], bg=CARD, fg=FG_DIM,
                 font=(SANS, 10)).pack(side="left", padx=(0, 4))
        tk.Label(top, text=p["name"], bg=CARD, fg=FG,
                 font=(SANS, 9, "bold")).pack(side="left")
        tk.Label(inner, text=p["desc"], bg=CARD, fg=FG_MUTE,
                 font=(MONO, 8), anchor="w").pack(fill="x", pady=(3, 0))

        for w in [frm, inner, top] + list(inner.winfo_children()):
            w.bind("<Button-1>", lambda e: click())

    def _chip(self, parent, label, command):
        btn = tk.Button(parent, text=label,
                        command=command,
                        bg=SURFACE, fg=FG_DIM,
                        font=(SANS, 9, "bold"),
                        relief="flat", cursor="hand2",
                        padx=8, pady=5,
                        highlightthickness=1, highlightbackground=BORDER,
                        activebackground=BORDER, activeforeground=FG)
        btn.pack(side="left", padx=(0, 4), pady=1)
        orig_cmd = command
        def click_and_glow():
            orig_cmd()
            btn.config(bg=CYAN_BG, fg=CYAN, highlightbackground=CYAN_B)
        btn.config(command=click_and_glow)
        return btn

    def _seg_btn(self, parent, label, command):
        return tk.Button(parent, text=label, command=command,
                         bg=SURFACE, fg=FG_DIM,
                         font=(SANS, 9, "bold"),
                         relief="flat", cursor="hand2",
                         padx=10, pady=7,
                         highlightthickness=1, highlightbackground=BORDER,
                         activebackground=CARD, activeforeground=CYAN)

    # ── RIGHT: Sliders panel ──────────────────────────────────────────

    def _right_panel(self, parent, mon, idx):
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        canvas.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=12)
        sb.pack(side="right", fill="y", pady=12)
        self._sliders(inner, mon, idx)

    def _sliders(self, parent, mon, idx):
        p = parent

        section_header(p, "Goruntu", bg=BG)
        fc = tk.Frame(p, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        fc.pack(fill="x", pady=(0, 4))
        fi = tk.Frame(fc, bg=SURFACE); fi.pack(fill="x", padx=14, pady=10)
        slider_row(fi, "Parlaklik", mon.get_brightness, mon.set_brightness,
                   CYAN, CYAN_BG, CYAN, bg=SURFACE)
        tk.Frame(fi, bg=BORDER, height=1).pack(fill="x", pady=6)
        slider_row(fi, "Kontrast", mon.get_contrast, mon.set_contrast,
                   CYAN, CYAN_BG, CYAN, bg=SURFACE)

        section_header(p, "Renk Sicakligi", "VCP 0x14", bg=BG)
        self._temp_panel(p, mon, idx)

        section_header(p, "RGB Kazanci", "VCP 0x16 / 0x18 / 0x1A", bg=BG)
        note = tk.Frame(p, bg="#1c1208", highlightthickness=1,
                        highlightbackground=ORANGE_B)
        note.pack(fill="x", pady=(0, 8))
        tk.Label(note,
                 text="⚠  Yalnizca User modunda etkindir. "
                      "Slider'a dokunulunca otomatik User moda gecilir.",
                 bg="#1c1208", fg="#ffb38e", font=(SANS, 9),
                 anchor="w", padx=10, pady=6, wraplength=420).pack(fill="x")

        rgb = tk.Frame(p, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        rgb.pack(fill="x", pady=(0, 4))
        ri = tk.Frame(rgb, bg=SURFACE); ri.pack(fill="x", padx=14, pady=10)
        slider_row(ri, "Kirmizi Gain", mon.get_red_gain, mon.set_red_gain,
                   RED, RED_B, "#ff7c92", bg=SURFACE)
        tk.Frame(ri, bg=BORDER, height=1).pack(fill="x", pady=5)
        slider_row(ri, "Yesil Gain", mon.get_green_gain, mon.set_green_gain,
                   GREEN, GREEN_B, "#6ee9a0", bg=SURFACE)
        tk.Frame(ri, bg=BORDER, height=1).pack(fill="x", pady=5)
        slider_row(ri, "Mavi Gain", mon.get_blue_gain, mon.set_blue_gain,
                   "#3b82f6", "#1e3a8a", "#93b9ff", bg=SURFACE, hint="DDC")

        section_header(p, "Mavi Isik Filtresi", "Gamma Ramp", bg=BG)
        tk.Label(p,
                 text="100 = filtre yok  ·  dusuk deger = daha az mavi isik  ·  DDC/CI'dan bagimsiz",
                 bg=BG, fg=FG_MUTE, font=(MONO, 8), anchor="w").pack(fill="x", pady=(0, 6))
        bf = tk.Frame(p, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        bf.pack(fill="x", pady=(0, 4))
        bi = tk.Frame(bf, bg=SURFACE); bi.pack(fill="x", padx=14, pady=10)
        slider_row(bi, "Mavi Isik Filtresi", mon.get_blue_filter, mon.set_blue_filter,
                   ORANGE, ORANGE_B, "#ffa173", bg=SURFACE)

        section_header(p, "Ses", "VCP 0x62", bg=BG)
        sf = tk.Frame(p, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        sf.pack(fill="x", pady=(0, 4))
        si = tk.Frame(sf, bg=SURFACE); si.pack(fill="x", padx=14, pady=10)
        slider_row(si, "Ses Seviyesi", mon.get_volume, mon.set_volume,
                   CYAN, CYAN_BG, CYAN, bg=SURFACE)

        section_header(p, "OSD Uzerinden Degistirilebilir", bg=BG)
        tk.Label(p, text="DDC/CI desteklenmez — monitör OSD menüsünden ayarlayin",
                 bg=BG, fg=FG_MUTE, font=(MONO, 8), anchor="w").pack(fill="x", pady=(0, 6))
        osd_card = tk.Frame(p, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        osd_card.pack(fill="x", pady=(0, 16))
        OSD_ITEMS = [
            ("Keskinlik",      "Sharpness"),
            ("Gamma",          "1.8 / 2.0 / 2.2 / 2.4 / 2.6"),
            ("Dark Boost",     "Off / L1 / L2 / L3"),
            ("DCR",            "Dynamic Contrast Ratio"),
            ("HDR Modu",       "Off / DisplayHDR / Picture / Movie / Game"),
            ("LowBlue Mode",   "Off / Multimedia / Internet / Office / Reading"),
            ("Overdrive",      "Off / Normal / Fast / Faster / Fastest / Extreme"),
            ("Adaptive-Sync",  "On / Off"),
            ("Game Color",     "0–20"),
            ("Shadow Control", "0–20"),
            ("Image Ratio",    "Full / Aspect / 1:1"),
            ("Dial Point",     "Sniper Scope / Frame Counter"),
        ]
        for name, opts in OSD_ITEMS:
            row = tk.Frame(osd_card, bg=CARD)
            row.pack(fill="x", padx=12, pady=3)
            tk.Label(row, text=name, bg=CARD, fg=FG,
                     font=(SANS, 10), width=16, anchor="w").pack(side="left")
            tk.Label(row, text=opts, bg=CARD, fg=FG_MUTE,
                     font=(MONO, 8), anchor="w").pack(side="left")
            tk.Label(row, text="OSD", bg="#1c1208", fg="#ffb38e",
                     font=(MONO, 8), padx=5, pady=1).pack(side="right")
            tk.Frame(osd_card, bg=BORDER, height=1).pack(fill="x", padx=12)

    # ── Color Temp Buttons ────────────────────────────────────────────

    def _temp_panel(self, parent, mon, idx):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=(0, 8))
        self._temp_btns[idx] = []

        btns = []
        for key, (vcp_val, c1, c2, k_label) in COLOR_TEMP_PRESETS.items():
            wrap = tk.Frame(row, bg=BG)
            wrap.pack(side="left", padx=(0, 6), fill="x", expand=True)
            outer = tk.Frame(wrap, bg=CARD, highlightthickness=1,
                             highlightbackground=BORDER, cursor="hand2")
            outer.pack(fill="x")
            sw = tk.Canvas(outer, height=28, bg=c1, highlightthickness=0)
            sw.pack(fill="x")
            sw.create_rectangle(0, 0, 200, 28, fill=c1, outline="")
            sw.create_rectangle(60, 0, 200, 28, fill=c2, outline="")
            tk.Label(outer, text=key, bg=CARD, fg=FG_DIM,
                     font=(SANS, 8, "bold"), pady=3).pack()
            tk.Label(outer, text=k_label, bg=CARD, fg=FG_MUTE,
                     font=(MONO, 7)).pack(pady=(0, 4))
            btns.append(((None, None, outer), key))

        for _, (_, __, outer_w), key in [(i, t[0], t[1]) for i, t in enumerate(btns)]:
            pass  # unused

        for i, ((_, __, outer_w), key) in enumerate(btns):
            vcp_val = COLOR_TEMP_PRESETS[key][0]
            def make_cmd(k=key, v=vcp_val):
                def cmd():
                    mon.set_color_temp(v)
                    for (__, ___, ow), kk in btns:
                        ow.config(highlightbackground=CYAN if kk == k else BORDER,
                                  highlightthickness=2 if kk == k else 1)
                return cmd
            outer_w.bind("<Button-1>", lambda e, c=make_cmd(): c())
            for child in outer_w.winfo_children():
                child.bind("<Button-1>", lambda e, c=make_cmd(): c())

        self._temp_btns[idx] = btns

    # ── Footer ────────────────────────────────────────────────────────

    def _footer(self):
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")
        foot = tk.Frame(self.root, bg=CARD, height=52)
        foot.pack(fill="x"); foot.pack_propagate(False)
        inner = tk.Frame(foot, bg=CARD)
        inner.pack(fill="both", expand=True, padx=16)

        def reset_lum():
            if messagebox.askyesno("Sifirla",
                                    "Parlaklik/Kontrast fabrika degerine donduruluyor?"):
                for m in self.monitors: m.restore_luminance()

        def reset_clr():
            if messagebox.askyesno("Sifirla", "Renk ayarlari sifirlanacak?"):
                for m in self.monitors:
                    m.restore_color()
                    m.set_blue_filter(100)

        def reset_all():
            if messagebox.askyesno("Sifirla",
                                    "TUM ayarlar fabrika degerine donduruluyor?"):
                for m in self.monitors:
                    m.restore_all()
                    m.set_blue_filter(100)

        btn_style = dict(bg=SURFACE, fg=FG_DIM, font=(SANS, 9),
                         relief="flat", cursor="hand2", padx=10, pady=7,
                         highlightthickness=1, highlightbackground=BORDER,
                         activebackground=CARD, activeforeground=FG)

        tk.Button(inner, text="↺  Goruntu Sifirla",
                  command=reset_lum, **btn_style).pack(side="left", pady=8, padx=(0, 6))
        tk.Button(inner, text="↺  Renk Sifirla",
                  command=reset_clr, **btn_style).pack(side="left", pady=8, padx=(0, 6))
        tk.Button(inner, text="🗑  Tumunu Sifirla",
                  command=reset_all,
                  **{**btn_style, "fg": "#ff7c92",
                     "highlightbackground": RED_B}).pack(side="left", pady=8)

        any_ddc = any(m.available for m in self.monitors)
        meta = tk.Frame(inner, bg=CARD)
        meta.pack(side="right", pady=8)
        tk.Label(meta, text="●", bg=CARD, fg=GREEN if any_ddc else AMBER,
                 font=(SANS, 9)).pack(side="left")
        tk.Label(meta,
                 text="  DDC/CI · Aktif" if any_ddc else "  Simulasyon",
                 bg=CARD, fg=FG_MUTE, font=(MONO, 9)).pack(side="left")

    # ── Profile apply ─────────────────────────────────────────────────

    def _apply_profile(self, p: dict, mon: MonitorDDC):
        mon.apply_profile(p)
        mode = "DDC-CI" if mon.available else "Simulasyon"
        if not mon._apply_ok and mon.available:
            self.root.after(0, lambda: messagebox.showerror(
                "Hata", f"DDC komutu basarisiz.\n{mon._last_err}"))
        else:
            msg = (f"✓  {p['name']}  ({mode})\n\n"
                   f"Parlaklik: {p['brightness']}%  ·  Kontrast: {p['contrast']}%\n"
                   f"Renk: {p['color_temp']}  ·  Mavi filtre: {p['blue_filter']}%")
            self.root.after(0, lambda: messagebox.showinfo("Profil Uygulandi", msg))

    def _set_gaming(self, vcp, mon, idx):
        mon.set_gaming_mode(vcp)
        for btn, v in self._gaming_btns[idx]:
            if v == vcp:
                btn.config(bg=CYAN_BG, fg=CYAN, highlightbackground=CYAN_B)
            else:
                btn.config(bg=SURFACE, fg=FG_DIM, highlightbackground=BORDER)


# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
