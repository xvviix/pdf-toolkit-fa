#!/usr/bin/env python3
"""
PDF Toolkit v12 - Powerful Standalone PDF Utility (Responsive + Scrollable)
===========================================================================
- ONLY PDF features
- Fully scrollable UI → works on low resolution screens (800x600, 720p, etc.)
- Users can always scroll to reach all buttons and controls
- Smaller default window size + dynamic scrolling
- Persian UI
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import re
import os
import sys
import tempfile
from pathlib import Path
from PIL import Image
import queue

# ─────────────────────────────────────────────────────────────────────────────
#  OCR MODEL FOLDER (PADDLE_PDX_HOME) + PADDLE NATIVE LIBS
#  مدل‌های PaddleOCR (تشخیص فارسی) به‌صورت خودکار در اولین اجرا دانلود می‌شوند.
#  در حالت EXE (frozen) آن‌ها را در پوشه‌ی کنار فایل EXE نگه می‌داریم, نه در
#  پوشه‌ی خانه‌ی کاربر, تا:
#   ۱) روی سیستم‌های آفلاین کارمند هم کار کند (پوشه را کنار exe کپی می‌کنیم)
#   ۲) هر کاربر مجبور نباشد دوباره دانلود کند
#  همچنین کتابخانه‌های بومی Paddle (dll/so) را که PyInstaller در
#  `_internal/paddle/libs` می‌گذارد به مسیر جستجو اضافه می‌کنیم،
#  وگرنه خطای «libmklml_intel.so not found» می‌گیریم.
# ─────────────────────────────────────────────────────────────────────────────
def _setup_paddlex_home():
    try:
        if getattr(sys, "frozen", False):
            # در حال اجرا به‌صورت EXE
            base_dir = Path(sys.executable).resolve().parent
        else:
            # اجرای مستقیم با پایتون (اسکریپت)
            base_dir = Path(__file__).resolve().parent
        home_dir = base_dir / ".paddlex"
        try:
            home_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        os.environ.setdefault("PADDLE_PDX_HOME", str(home_dir))

        # پیدا کردن و افزودن کتابخانه‌های بومی Paddle به مسیر جستجو
        candidates = [
            base_dir / "_internal" / "paddle" / "libs",   # PyInstaller onedir
            base_dir / "paddle" / "libs",                 # حالت جایگزین
        ]
        for lib_dir in candidates:
            if lib_dir.is_dir():
                os.environ["PATH"] = str(lib_dir) + os.pathsep + os.environ.get("PATH", "")
                if os.name != "nt":   # لینوکس/مک
                    cur = os.environ.get("LD_LIBRARY_PATH", "")
                    os.environ["LD_LIBRARY_PATH"] = str(lib_dir) + (os.pathsep + cur if cur else "")
                # پیش‌بارگذاری کتابخانه‌های اصلی (برای ویندوز هم مفید است)
                try:
                    import ctypes
                    for lib in ("libphi_core.so", "libphi.so", "libmklml_intel.so",
                                "libdnnl.so.3", "libiomp5.so"):
                        p = lib_dir / lib
                        if p.exists():
                            try:
                                ctypes.CDLL(str(p))
                            except Exception:
                                pass
                except Exception:
                    pass
    except Exception:
        pass

_setup_paddlex_home()

# ─────────────────────────────────────────────────────────────────────────────
#  LAZY LOADED PDF LIBRARIES
# ─────────────────────────────────────────────────────────────────────────────
PYPDF_AVAILABLE = False
PYMUPDF_AVAILABLE = False

def _lazy_import(name):
    try:
        return __import__(name)
    except ImportError:
        return None

def ensure_pdf_libs():
    global PYPDF_AVAILABLE, PYMUPDF_AVAILABLE, PdfReader, PdfWriter, fitz
    if not PYPDF_AVAILABLE:
        try:
            from pypdf import PdfReader, PdfWriter as _PdfWriter
            PdfWriter = _PdfWriter
            PYPDF_AVAILABLE = True
        except Exception:
            try:
                from PyPDF2 import PdfReader as _PdfReader, PdfWriter as _PdfWriter
                PdfReader = _PdfReader
                PdfWriter = _PdfWriter
                PYPDF_AVAILABLE = True
            except Exception:
                PYPDF_AVAILABLE = False

    if not PYMUPDF_AVAILABLE:
        fitz = _lazy_import("fitz")
        PYMUPDF_AVAILABLE = fitz is not None
    return PYPDF_AVAILABLE

# ─────────────────────────────────────────────────────────────────────────────
#  THEME
# ─────────────────────────────────────────────────────────────────────────────
DARK_BG   = "#061a10"
PANEL_BG  = "#0a2318"
CARD_BG   = "#0f2e1f"
ACCENT    = "#10b981"
ACCENT_L  = "#34d399"
SUCCESS   = "#6ee7b7"
WARNING   = "#fbbf24"
ERROR     = "#f87171"
TEXT_P    = "#ecfdf5"
TEXT_S    = "#86efac"
BORDER    = "#14532d"
BORDER_L  = "#166534"

# The Persian font is detected lazily by _apply_persian_font() using the
# app's own Tk root — this avoids creating and destroying a spare Tk root
# at import time, which breaks on some platforms (e.g. macOS).
_PFONT = "Tahoma"
_PERSIAN_FONT_CANDIDATES = ["Vazir", "Vazirmatn", "Sahel", "B Nazanin", "IranSans", "Tahoma"]

FT = (_PFONT, 17, "bold")
FH = (_PFONT, 12, "bold")
FB = (_PFONT, 10)
FS = (_PFONT, 9)
FM = (_PFONT, 9)   # entries / listboxes now use the Persian font too

def _apply_persian_font(root):
    """Detect the best available Persian font using the app's real Tk root.

    Called from PDFToolkit.__init__ before any widget is built. Falls back
    to Tahoma when font introspection is unavailable (e.g. headless tests).
    """
    global _PFONT, FT, FH, FB, FS, FM
    try:
        import tkinter.font as _font
        families = set(_font.families(root))
        for f in _PERSIAN_FONT_CANDIDATES:
            if f in families:
                break
        else:
            return
        if f == _PFONT:
            return
        _PFONT = f
        FT = (_PFONT, 17, "bold")
        FH = (_PFONT, 12, "bold")
        FB = (_PFONT, 10)
        FS = (_PFONT, 9)
        FM = (_PFONT, 9)
    except Exception:
        pass

def _lighten(hex_c, n=18):
    try:
        r, g, b = int(hex_c[1:3], 16), int(hex_c[3:5], 16), int(hex_c[5:7], 16)
        return f'#{min(255, r+n):02x}{min(255, g+n):02x}{min(255, b+n):02x}'
    except:
        return hex_c

def _darken(hex_c, n=18):
    try:
        r, g, b = int(hex_c[1:3], 16), int(hex_c[3:5], 16), int(hex_c[5:7], 16)
        return f'#{max(0, r-n):02x}{max(0, g-n):02x}{max(0, b-n):02x}'
    except:
        return hex_c

# ─────────────────────────────────────────────────────────────────────────────
#  PAGE RANGE PARSER
# ─────────────────────────────────────────────────────────────────────────────
def parse_page_ranges(total: int, spec: str):
    if not spec or spec.lower() in ("all", "همه"):
        return list(range(total))
    spec = spec.strip().replace(" ", "")
    صفحه = set()
    for part in spec.split(","):
        if not part:
            continue
        if "-" in part:
            try:
                start_str, end_str = part.split("-", 1)
                if start_str.lower() in ("last", "آخر"):
                    n = int(end_str)
                    start = max(0, total - n)
                    end = total
                elif end_str == "" or end_str.lower() in ("end", "آخر"):
                    start = max(0, int(start_str) - 1)
                    end = total
                else:
                    start = max(0, int(start_str) - 1)
                    end = min(total, int(end_str))
                for p in range(start, end):
                    if 0 <= p < total:
                        صفحه.add(p)
            except ValueError:
                continue
        else:
            try:
                p = int(part) - 1
                if 0 <= p < total:
                    صفحه.add(p)
            except ValueError:
                continue
    return sorted(صفحه)

# ─────────────────────────────────────────────────────────────────────────────
#  ANIMATED BUTTON
# ─────────────────────────────────────────────────────────────────────────────
class AnimatedButton(tk.Button):
    def __init__(self, parent, hover_bg=None, press_bg=None, **kwargs):
        self._normal_bg = kwargs.get('bg', CARD_BG)
        self._hover_bg = hover_bg or _lighten(self._normal_bg, 22)
        self._press_bg = press_bg or _darken(self._normal_bg, 10)
        kwargs.setdefault('relief', 'flat')
        kwargs.setdefault('bd', 0)
        kwargs.setdefault('cursor', 'hand2')
        super().__init__(parent, **kwargs)
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<Button-1>', self._on_press)
        self.bind('<ButtonRelease-1>', self._on_release)

    def _on_enter(self, _):
        if str(self.cget('state')) != 'disabled':
            self.config(bg=self._hover_bg)
    def _on_leave(self, _):
        if str(self.cget('state')) != 'disabled':
            self.config(bg=self._normal_bg)
    def _on_press(self, _):
        if str(self.cget('state')) != 'disabled':
            self.config(bg=self._press_bg)
    def _on_release(self, _):
        if str(self.cget('state')) != 'disabled':
            self.config(bg=self._hover_bg)

def _styled_entry(parent, textvariable=None, width=None, ipady=5, **kw):
    frm = tk.Frame(parent, bg=BORDER, bd=0, padx=1, pady=1)
    ent = tk.Entry(frm, bg=PANEL_BG, fg=TEXT_P, insertbackground=ACCENT,
                   relief='flat', bd=0, font=FM, textvariable=textvariable,
                   width=width or 22)
    ent.pack(fill='both', expand=True, ipady=ipady)
    frm.pack(side="left", fill="x", expand=True, padx=3)
    return ent, frm

# ─────────────────────────────────────────────────────────────────────────────
#  MAIN APP - FULLY SCROLLABLE
# ─────────────────────────────────────────────────────────────────────────────
class PDFToolkit:
    def __init__(self, root):
        self.root = root
        _apply_persian_font(root)
        self.root.title("PDF Toolkit v12 — ابزار قدرتمند PDF")
        self.root.geometry("880x620")           # Smaller default size
        self.root.minsize(680, 460)             # Much lower minimum
        self.root.configure(bg=DARK_BG)
        self.root.resizable(True, True)

        # State
        self.pdf_files = []
        self.output_dir = tk.StringVar(value=str(Path.home() / "PDF_Toolkit_Output"))
        self.split_mode = tk.StringVar(value="extract")
        self.split_range = tk.StringVar(value="1-5,8")
        self.split_separate = tk.BooleanVar(value=True)
        self.split_prefix = tk.StringVar(value="{name}_p{page}")
        self.split_every_n = tk.IntVar(value=2)
        self.split_naming = tk.StringVar(value="manual")   # "manual" | "ocr"
        self.preview_listbox = None
        self._ocr_cached = None
        self.merge_out_name = tk.StringVar(value="merged_output.pdf")
        self.img_dpi = tk.IntVar(value=150)
        self.img_format = tk.StringVar(value="PNG")
        self.img_range = tk.StringVar(value="all")
        self.img_prefix = tk.StringVar(value="{name}_page{page}")
        self.image_files = []
        self.rotate_angle = tk.IntVar(value=90)
        self.rotate_range = tk.StringVar(value="all")
        self.compress_quality = tk.IntVar(value=70)
        self.text_range = tk.StringVar(value="all")
        self.processing = False
        self.log_q = queue.Queue()

        self._styles()
        self._build_ui()
        self._update_split_ui()
        self._poll_logs()

    def _styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TFrame", background=DARK_BG)
        s.configure("TProgressbar", background=ACCENT, troughcolor=BORDER_L, thickness=7)
        s.configure("TNotebook", background=DARK_BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=PANEL_BG, foreground=TEXT_S,
                    font=FB, padding=(14, 8))

    def _card(self, parent, title="", icon=""):
        outer = tk.Frame(parent, bg=CARD_BG, highlightbackground=BORDER_L, highlightthickness=1)
        outer.pack(fill="x", pady=(0, 11))
        if title:
            hdr = tk.Frame(outer, bg=CARD_BG)
            hdr.pack(fill="x")
            tk.Frame(hdr, bg=ACCENT, width=3).pack(side="left", fill="y", pady=(6, 0))
            tk.Label(hdr, text=f"{icon}  {title}", font=FH, bg=CARD_BG, fg=TEXT_P).pack(
                anchor="w", padx=11, pady=(5, 3), side="left")
        inner = tk.Frame(outer, bg=CARD_BG)
        inner.pack(fill="x", padx=12, pady=(4, 11))
        return inner

    def _build_ui(self):
        # ========== HEADER (fixed) ==========
        hdr = tk.Frame(self.root, bg=PANEL_BG, height=54)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=ACCENT, height=3).place(relx=0, rely=0, relwidth=1)

        inner = tk.Frame(hdr, bg=PANEL_BG)
        inner.place(relx=.5, rely=.48, anchor="center")
        tk.Label(inner, text="📄", font=(_PFONT, 19), bg=PANEL_BG, fg=ACCENT).pack(side="left", padx=(0, 8))
        tk.Label(inner, text="PDF Toolkit v12", font=FT, bg=PANEL_BG, fg=TEXT_P).pack(side="left")
        tk.Label(inner, text="— ابزار قدرتمند PDF", font=(_PFONT, 10), bg=PANEL_BG, fg=TEXT_S).pack(side="left")

        # ========== SCROLLABLE MAIN AREA ==========
        # This is the key fix for low resolution
        scroll_container = tk.Frame(self.root, bg=DARK_BG)
        scroll_container.pack(fill="both", expand=True, padx=8, pady=(4, 0))

        self.canvas = tk.Canvas(scroll_container, bg=DARK_BG, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=DARK_BG)

        # Create window inside canvas
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Bind scrolling
        self.scrollable_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

        # ========== CONTENT INSIDE SCROLLABLE FRAME ==========
        # Input section
        inp = self._card(self.scrollable_frame, "فایل‌های PDF ورودی", "📁")
        row = tk.Frame(inp, bg=CARD_BG)
        row.pack(fill="x")

        AnimatedButton(row, text="＋ افزودن PDF", font=FB, bg=ACCENT, fg=TEXT_P,
                       command=self._add_pdfs).pack(side="left", padx=3)
        AnimatedButton(row, text="📁 افزودن پوشه", font=FB, bg=BORDER_L, fg=TEXT_P,
                       command=self._add_pdf_folder).pack(side="left", padx=3)
        AnimatedButton(row, text="✕ پاک کردن لیست", font=FB, bg=CARD_BG, fg=ERROR,
                       command=self._clear_pdfs).pack(side="left", padx=3)

        self.pdf_listbox = tk.Listbox(inp, bg=PANEL_BG, fg=TEXT_S, font=FM, height=5,
                                      selectbackground=ACCENT, selectforeground=TEXT_P,
                                      activestyle="none")
        self.pdf_listbox.pack(fill="x", pady=5)
        self.pdf_listbox.bind("<<ListboxSelect>>", self._on_pdf_select)

        # Output dir
        outc = self._card(self.scrollable_frame, "پوشه خروجی", "📂")
        row2 = tk.Frame(outc, bg=CARD_BG)
        row2.pack(fill="x")
        _styled_entry(row2, textvariable=self.output_dir)
        AnimatedButton(row2, text="انتخاب...", font=FS, bg=BORDER_L, fg=TEXT_P,
                       command=self._pick_output).pack(side="left", padx=5)

        # Notebook (tabs)
        self.nb = ttk.Notebook(self.scrollable_frame)
        self.nb.pack(fill="both", expand=True, pady=(6, 0))

        self._build_split_tab()
        self._build_merge_tab()
        self._build_to_images_tab()
        self._build_from_images_tab()
        self._build_tools_tab()

        # ========== BOTTOM BAR (fixed - always visible) ==========
        bottom = tk.Frame(self.root, bg=PANEL_BG, height=78)
        bottom.pack(fill="x", side="bottom")
        bottom.pack_propagate(False)

        prog_frame = tk.Frame(bottom, bg=PANEL_BG)
        prog_frame.pack(fill="x", padx=14, pady=(8, 1))

        self.prog_var = tk.DoubleVar()
        ttk.Progressbar(prog_frame, variable=self.prog_var, maximum=100,
                        style="TProgressbar").pack(fill="x")

        self.status_lbl = tk.Label(prog_frame, text="آماده برای کار با PDF",
                                   font=FS, bg=PANEL_BG, fg=TEXT_S)
        self.status_lbl.pack(anchor="w", pady=(2, 0))

        btn_frame = tk.Frame(bottom, bg=PANEL_BG)
        btn_frame.pack(fill="x", padx=14, pady=4)

        self.run_btn = AnimatedButton(btn_frame, text="▶ اجرای عملیات انتخاب شده",
                                      font=FH, bg=ACCENT, fg=TEXT_P, hover_bg=ACCENT_L,
                                      command=self._start_operation)
        self.run_btn.pack(side="left")

        AnimatedButton(btn_frame, text="ℹ اطلاعات PDF انتخابی", font=FB, bg=CARD_BG, fg=TEXT_S,
                       command=self._show_pdf_info).pack(side="left", padx=10)

        AnimatedButton(btn_frame, text="پاک کردن لیست", font=FB, bg=CARD_BG, fg=ERROR,
                       command=self._clear_pdfs).pack(side="right")

    # ───────────────────── SCROLLING HELPERS ─────────────────────
    def _on_frame_configure(self, event=None):
        """Update scroll region when inner frame size changes"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        """Make the scrollable frame width match the canvas"""
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_linux(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")

    # ───────────────────── TABS ─────────────────────
    def _build_split_tab(self):
        tab = tk.Frame(self.nb, bg=DARK_BG)
        self.nb.add(tab, text="  ✂  تقسیم / استخراج  ")

        wrap = tk.Frame(tab, bg=DARK_BG)
        wrap.pack(fill="both", expand=True, padx=14, pady=8)

        c1 = self._card(wrap, "حالت تقسیم", "⚙")
        for val, txt in [
            ("extract", "استخراج صفحات انتخابی به PDF جدید"),
            ("split_all", "تقسیم همه صفحات به فایل‌های جدا"),
            ("every", "هر N صفحه یک فایل")
        ]:
            tk.Radiobutton(c1, text=txt, variable=self.split_mode, value=val,
                           bg=CARD_BG, fg=TEXT_S, selectcolor=PANEL_BG,
                           font=FS, command=self._update_split_ui).pack(anchor="w", pady=1)

        # ورودی N برای حالت «هر N صفحه یک فایل»
        self.every_frame = tk.Frame(c1, bg=CARD_BG)
        tk.Label(self.every_frame, text="تعداد صفحات هر فایل (N):", font=FS,
                 bg=CARD_BG, fg=TEXT_S).pack(side="left")
        tk.Spinbox(self.every_frame, from_=1, to=100, textvariable=self.split_every_n,
                   width=4, font=FM).pack(side="left", padx=4)

        c2 = self._card(wrap, "محدوده صفحات (مثال: 1-5,8 یا last-3)", "📑")
        row = tk.Frame(c2, bg=CARD_BG)
        row.pack(fill="x")
        tk.Label(row, text="محدوده:", font=FB, bg=CARD_BG, fg=TEXT_S).pack(side="left")
        _styled_entry(row, textvariable=self.split_range, width=26)

        tk.Label(c2, text="Example: all | 1-3 | 5 | 1-5,8- | last-3", font=FS, bg=CARD_BG, fg=TEXT_S).pack(anchor="w", pady=(2,0))

        c3 = self._card(wrap, "تنظیمات نام‌گذاری فایل‌ها", "📤")
        ttk.Checkbutton(c3, text="هر صفحه فایل جداگانه", variable=self.split_separate).pack(anchor="w")

        # انتخاب نوع نام‌گذاری: دستی یا تشخیص خودکار
        rowm = tk.Frame(c3, bg=CARD_BG)
        rowm.pack(fill="x", pady=(6, 2))
        tk.Label(rowm, text="نوع نام:", font=FS, bg=CARD_BG, fg=TEXT_S).pack(side="left", padx=(0, 6))
        tk.Radiobutton(rowm, text="دستی (الگو)", variable=self.split_naming, value="manual",
                       bg=CARD_BG, fg=TEXT_S, selectcolor=PANEL_BG, font=FS,
                       command=self._update_split_ui).pack(side="left", padx=4)
        tk.Radiobutton(rowm, text="تشخیص خودکار (OCR)", variable=self.split_naming, value="ocr",
                       bg=CARD_BG, fg=TEXT_S, selectcolor=PANEL_BG, font=FS,
                       command=self._update_split_ui).pack(side="left", padx=4)

        # فریم حالت دستی — اسم با الگو
        self.manual_frame = tk.Frame(c3, bg=CARD_BG)
        rowp = tk.Frame(self.manual_frame, bg=CARD_BG)
        rowp.pack(fill="x", pady=4)
        tk.Label(rowp, text="نام فایل:", font=FS, bg=CARD_BG, fg=TEXT_S).pack(side="left")
        _styled_entry(rowp, textvariable=self.split_prefix, width=20)
        tk.Label(self.manual_frame, text="مثال: {name}_p{page}  ←  نام اصلی + صفحه",
                 font=FS, bg=CARD_BG, fg=TEXT_S).pack(anchor="w")

        # فریم حالت OCR — تشخیص خودکار نام فرد
        self.ocr_frame = tk.Frame(c3, bg=CARD_BG)
        tk.Label(self.ocr_frame,
                 text="نام و نام خانوادگیِ هر فرد با OCR خوانده می‌شود و به‌عنوان نام فایل استفاده می‌شود.\n"
                      "مثال: صفحه‌ای با «نام: سهراب» و «نام خانوادگی: زارعی» → فایل «سهراب زارعی.pdf»\n\n"
                      "💡 اگر صفحه چند نام دارد: نام موردنظر را با رنگ زرد هایلایت کنید\n"
                      "   (در Adobe/Edge یا هر برنامه PDF) و فایل را ذخیره کنید —\n"
                      "   برنامه فقط همان ناحیهٔ هایلایت‌شده را می‌خواند.",
                 font=FS, bg=CARD_BG, fg=TEXT_S, wraplength=540, justify="right").pack(anchor="w", pady=(2, 0))

        # دکمه پیش‌نمایش اسامی
        AnimatedButton(
            self.ocr_frame, text="👁 پیش‌نمایش اسامی تشخیص داده شده",
            font=FS, bg=BORDER_L, fg=TEXT_P,
            command=self._preview_names).pack(anchor="w", pady=(6, 0))
        self.preview_listbox = tk.Listbox(self.ocr_frame, bg=PANEL_BG, fg=TEXT_S,
                                          font=FM, height=5,
                                          selectbackground=ACCENT, activestyle="none")

    def _build_merge_tab(self):
        tab = tk.Frame(self.nb, bg=DARK_BG)
        self.nb.add(tab, text="  🔗  ادغام PDFها  ")

        wrap = tk.Frame(tab, bg=DARK_BG)
        wrap.pack(fill="both", expand=True, padx=14, pady=8)

        c1 = self._card(wrap, "PDFهای انتخاب شده برای ادغام", "📚")
        self.merge_listbox = tk.Listbox(c1, bg=PANEL_BG, fg=TEXT_S, font=FM, height=4,
                                        selectbackground=ACCENT)
        self.merge_listbox.pack(fill="x", pady=3)

        row = tk.Frame(c1, bg=CARD_BG)
        row.pack(fill="x", pady=3)
        AnimatedButton(row, text="↑", font=FB, command=lambda: self._move_merge(-1)).pack(side="left", padx=2)
        AnimatedButton(row, text="↓", font=FB, command=lambda: self._move_merge(1)).pack(side="left", padx=2)
        AnimatedButton(row, text="✕ حذف", font=FB, bg=CARD_BG, fg=ERROR,
                       command=self._remove_selected_merge).pack(side="left", padx=6)

        c2 = self._card(wrap, "نام فایل خروجی ادغام شده", "📝")
        row2 = tk.Frame(c2, bg=CARD_BG)
        row2.pack(fill="x")
        _styled_entry(row2, textvariable=self.merge_out_name, width=26)

    def _build_to_images_tab(self):
        tab = tk.Frame(self.nb, bg=DARK_BG)
        self.nb.add(tab, text="  🖼  PDF به تصاویر  ")

        wrap = tk.Frame(tab, bg=DARK_BG)
        wrap.pack(fill="both", expand=True, padx=14, pady=8)

        c1 = self._card(wrap, "تنظیمات تبدیل به تصویر", "📸")
        row = tk.Frame(c1, bg=CARD_BG)
        row.pack(fill="x", pady=3)
        tk.Label(row, text="DPI (کیفیت):", font=FB, bg=CARD_BG, fg=TEXT_S).pack(side="left")
        dpi_spin = tk.Spinbox(row, from_=72, to=600, textvariable=self.img_dpi, width=5, font=FM)
        dpi_spin.pack(side="left", padx=5)
        tk.Label(row, text="(150-300 پیشنهاد می‌شود)", font=FS, bg=CARD_BG, fg=TEXT_S).pack(side="left", padx=4)

        row2 = tk.Frame(c1, bg=CARD_BG)
        row2.pack(fill="x", pady=3)
        tk.Label(row2, text="فرمت:", font=FB, bg=CARD_BG, fg=TEXT_S).pack(side="left")
        for fmt in ["PNG", "JPEG", "WEBP"]:
            tk.Radiobutton(row2, text=fmt, variable=self.img_format, value=fmt,
                           bg=CARD_BG, fg=TEXT_S, selectcolor=PANEL_BG, font=FS).pack(side="left", padx=8)

        row3 = tk.Frame(c1, bg=CARD_BG)
        row3.pack(fill="x", pady=3)
        tk.Label(row3, text="محدوده صفحات:", font=FB, bg=CARD_BG, fg=TEXT_S).pack(side="left")
        _styled_entry(row3, textvariable=self.img_range, width=20)

        row4 = tk.Frame(c1, bg=CARD_BG)
        row4.pack(fill="x", pady=3)
        tk.Label(row4, text="پیشوند نام فایل:", font=FB, bg=CARD_BG, fg=TEXT_S).pack(side="left")
        _styled_entry(row4, textvariable=self.img_prefix, width=22)

        c2 = self._card(wrap, "نکته", "💡")
        tk.Label(c2, text="• pip install pymupdf pypdf برای کیفیت بهتر", font=FS, bg=CARD_BG, fg=TEXT_S).pack(anchor="w")

    def _build_from_images_tab(self):
        tab = tk.Frame(self.nb, bg=DARK_BG)
        self.nb.add(tab, text="  📸  تصاویر به PDF  ")

        wrap = tk.Frame(tab, bg=DARK_BG)
        wrap.pack(fill="both", expand=True, padx=14, pady=8)

        c1 = self._card(wrap, "تصاویر ورودی (ترتیب مهم است)", "🖼")
        self.img_listbox = tk.Listbox(c1, bg=PANEL_BG, fg=TEXT_S, font=FM, height=4)
        self.img_listbox.pack(fill="x", pady=3)

        row = tk.Frame(c1, bg=CARD_BG)
        row.pack(fill="x")
        AnimatedButton(row, text="＋ افزودن تصاویر", font=FB, bg=ACCENT, fg=TEXT_P,
                       command=self._add_images).pack(side="left", padx=3)
        AnimatedButton(row, text="↑", font=FB, command=lambda: self._move_image(-1)).pack(side="left", padx=2)
        AnimatedButton(row, text="↓", font=FB, command=lambda: self._move_image(1)).pack(side="left", padx=2)
        AnimatedButton(row, text="✕ حذف", font=FB, bg=CARD_BG, fg=ERROR,
                       command=self._remove_image).pack(side="left", padx=5)

        c2 = self._card(wrap, "نام فایل PDF خروجی", "📄")
        row2 = tk.Frame(c2, bg=CARD_BG)
        row2.pack(fill="x")
        self.img_to_pdf_name = tk.StringVar(value="from_images.pdf")
        _styled_entry(row2, textvariable=self.img_to_pdf_name, width=24)

    def _build_tools_tab(self):
        tab = tk.Frame(self.nb, bg=DARK_BG)
        self.nb.add(tab, text="  🛠  ابزارهای پیشرفته  ")

        wrap = tk.Frame(tab, bg=DARK_BG)
        wrap.pack(fill="both", expand=True, padx=14, pady=8)

        c1 = self._card(wrap, "چرخاندن صفحات", "🔄")
        row = tk.Frame(c1, bg=CARD_BG)
        row.pack(fill="x")
        tk.Label(row, text="زاویه:", font=FB, bg=CARD_BG, fg=TEXT_S).pack(side="left")
        for ang in [90, 180, 270, -90]:
            tk.Radiobutton(row, text=f"{ang}°", variable=self.rotate_angle, value=ang,
                           bg=CARD_BG, fg=TEXT_S, selectcolor=PANEL_BG, font=FS).pack(side="left", padx=6)

        tk.Label(c1, text="محدوده صفحات:", font=FB, bg=CARD_BG, fg=TEXT_S).pack(anchor="w")
        _styled_entry(c1, textvariable=self.rotate_range, width=20)

        c2 = self._card(wrap, "فشرده‌سازی PDF", "📦")
        row = tk.Frame(c2, bg=CARD_BG)
        row.pack(fill="x")
        tk.Label(row, text="کیفیت (۳۰-۱۰۰):", font=FB, bg=CARD_BG, fg=TEXT_S).pack(side="left")
        tk.Scale(row, from_=30, to=100, orient="horizontal", variable=self.compress_quality,
                 bg=CARD_BG, fg=TEXT_S, length=160, troughcolor=BORDER).pack(side="left", padx=6)

        c3 = self._card(wrap, "استخراج متن", "📝")
        row = tk.Frame(c3, bg=CARD_BG)
        row.pack(fill="x")
        tk.Label(row, text="محدوده:", font=FB, bg=CARD_BG, fg=TEXT_S).pack(side="left")
        _styled_entry(row, textvariable=self.text_range, width=18)
        AnimatedButton(c3, text="استخراج متن به TXT", font=FB, bg=ACCENT, fg=TEXT_P,
                       command=self._run_text_extract).pack(anchor="w", pady=4)

    # ───────────────────── FILE HANDLERS ─────────────────────
    def _add_pdfs(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF files", "*.pdf")])
        for f in files:
            p = Path(f)
            if p not in self.pdf_files:
                self.pdf_files.append(p)
        self._refresh_pdf_list()

    def _add_pdf_folder(self):
        folder = filedialog.askdirectory()
        if not folder: return
        for f in Path(folder).glob("*.pdf"):
            if f not in self.pdf_files:
                self.pdf_files.append(f)
        self._refresh_pdf_list()

    def _clear_pdfs(self):
        self.pdf_files.clear()
        self._refresh_pdf_list()
        if hasattr(self, 'merge_listbox'):
            self.merge_listbox.delete(0, "end")

    def _refresh_pdf_list(self):
        self.pdf_listbox.delete(0, "end")
        for p in self.pdf_files:
            self.pdf_listbox.insert("end", p.name)
        if hasattr(self, 'merge_listbox'):
            self.merge_listbox.delete(0, "end")
            for p in self.pdf_files:
                self.merge_listbox.insert("end", p.name)

    def _on_pdf_select(self, event=None):
        pass

    def _pick_output(self):
        d = filedialog.askdirectory()
        if d: self.output_dir.set(d)

    def _move_merge(self, direction):
        sel = self.merge_listbox.curselection()
        if not sel: return
        idx = sel[0]
        new_idx = idx + direction
        if 0 <= new_idx < len(self.pdf_files):
            self.pdf_files[idx], self.pdf_files[new_idx] = self.pdf_files[new_idx], self.pdf_files[idx]
            self._refresh_pdf_list()
            self.merge_listbox.selection_set(new_idx)

    def _remove_selected_merge(self):
        sel = self.merge_listbox.curselection()
        if not sel: return
        idx = sel[0]
        del self.pdf_files[idx]
        self._refresh_pdf_list()

    def _add_images(self):
        files = filedialog.askopenfilenames(filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")])
        for f in files:
            p = Path(f)
            if p not in self.image_files:
                self.image_files.append(p)
        self._refresh_image_list()

    def _refresh_image_list(self):
        if not hasattr(self, 'img_listbox'): return
        self.img_listbox.delete(0, "end")
        for p in self.image_files:
            self.img_listbox.insert("end", p.name)

    def _move_image(self, direction):
        sel = self.img_listbox.curselection()
        if not sel: return
        idx = sel[0]
        new_idx = idx + direction
        if 0 <= new_idx < len(self.image_files):
            self.image_files[idx], self.image_files[new_idx] = self.image_files[new_idx], self.image_files[idx]
            self._refresh_image_list()
            self.img_listbox.selection_set(new_idx)

    def _remove_image(self):
        sel = self.img_listbox.curselection()
        if not sel: return
        idx = sel[0]
        del self.image_files[idx]
        self._refresh_image_list()

    # ───────────────────── OPERATIONS ─────────────────────
    def _update_split_ui(self):
        # نمایش/پنهان‌سازی فیلدهای نام‌گذاری بر اساس حالت انتخابی
        if not hasattr(self, 'manual_frame'):
            return
        if self.split_naming.get() == "ocr":
            self.manual_frame.pack_forget()
            self.ocr_frame.pack(fill="x", pady=2)
        else:
            self.ocr_frame.pack_forget()
            self.manual_frame.pack(fill="x", pady=2)

        # نمایش ورودی N فقط در حالت «هر N صفحه یک فایل»
        if hasattr(self, 'every_frame'):
            if self.split_mode.get() == "every":
                self.every_frame.pack(anchor="w", pady=(2, 0))
            else:
                self.every_frame.pack_forget()

    def _start_operation(self):
        if self.processing: return
        if not self.pdf_files and self.nb.index("current") != 3:
            messagebox.showwarning("خطا", "هیچ فایل PDF انتخاب نشده")
            return

        out_dir = Path(self.output_dir.get().strip())
        out_dir.mkdir(parents=True, exist_ok=True)

        self.processing = True
        self.run_btn.config(state="disabled", text="در حال پردازش...")
        self.prog_var.set(0)
        self.status_lbl.config(text="در حال اجرا...", fg=ACCENT)

        tab_index = self.nb.index("current")
        tab_name = self.nb.tab(tab_index, "text").strip()

        threading.Thread(target=self._run_worker,
                         args=(tab_index, tab_name, out_dir), daemon=True).start()

    def _run_worker(self, tab_index, tab_name, out_dir):
        try:
            # dispatch by tab index — independent of (reshaped) tab text
            _ops = {
                0: self._run_split,
                1: self._run_merge,
                2: self._run_pdf_to_images,
                3: self._run_images_to_pdf,
                4: self._run_advanced_tools,
            }
            _ops.get(tab_index, lambda _: None)(out_dir)
        except Exception as e:
            self.log_q.put((f"خطا: {str(e)}", "error"))
        finally:
            self.root.after(0, self._finish_operation)

    def _finish_operation(self):
        self.processing = False
        self.run_btn.config(state="normal", text="▶ اجرای عملیات انتخاب شده")
        self.prog_var.set(100)
        self.status_lbl.config(text="عملیات تمام شد ✓", fg=SUCCESS)

    def _poll_logs(self):
        while not self.log_q.empty():
            msg, level = self.log_q.get_nowait()
            if msg == "preview_done" and isinstance(level, list):
                self._finish_preview(level)
                continue
            if msg == "progress" and isinstance(level, (int, float)):
                self.prog_var.set(min(100.0, max(0.0, float(level))))
                continue
            if msg == "report_done" and isinstance(level, list):
                self._show_report(level)
                continue
            col = {"ok": SUCCESS, "error": ERROR, "warn": WARNING}.get(level, TEXT_S)
            self.status_lbl.config(text=msg[:80], fg=col)
        self.root.after(130, self._poll_logs)

    def _set_progress(self, value):
        """گزارش پیشرفت به thread اصلی (مقدار ۰ تا ۱۰۰)."""
        self.log_q.put(("progress", float(value)))

    def _show_report(self, entries):
        """پنجرهٔ گزارش نهایی عملیات را نشان می‌دهد.

        هر آیتم: {'name': نام فایل, 'src': فایل مبدأ, 'صفحه': تعداد صفحات}
        فایل‌های خروجی دوباره باز می‌شوند تا سالم بودن آن‌ها تأیید شود.
        """
        try:
            ensure_pdf_libs()
            win = tk.Toplevel(self.root)
            win.title("گزارش عملیات ✓")
            win.configure(bg=DARK_BG)
            win.geometry("600x430")
            win.transient(self.root)
            win.resizable(True, True)

            # ── خلاصه ──
            total_files = len(entries)
            total_out_صفحه = sum(e["صفحه"] for e in entries)
            ok_files = 0
            for e in entries:
                try:
                    r = PdfReader(str(Path(self.output_dir.get()) / f"{e['name']}.pdf"))
                    if len(r.pages) == e["صفحه"]:
                        ok_files += 1
                except Exception:
                    pass

            # چک کیفیت اسامی (فقط وقتی از OCR استفاده شده باشد)
            name_ok = name_warn = name_bad = 0
            name_issues_map = {}
            for e in entries:
                status, score, issues = self._validate_name(e["name"])
                if status == "ok":
                    name_ok += 1
                elif status == "suspect":
                    name_warn += 1
                else:
                    name_bad += 1
                name_issues_map[e["name"]] = (status, score, issues)

            head = tk.Frame(win, bg=PANEL_BG)
            head.pack(fill="x", padx=10, pady=(10, 6))
            tk.Label(head, text=f"📄 {total_files} فایل ساخته شد  |  جمع صفحات: {total_out_صفحه}  |  سالم: {ok_files}/{total_files}",
                     font=FH, bg=PANEL_BG, fg=SUCCESS if ok_files == total_files else WARNING).pack(anchor="w")
            if ok_files < total_files:
                tk.Label(head, text="⚠ برخی فایل‌ها سالم باز نشدند — آن‌ها را بررسی کنید",
                         font=FS, bg=PANEL_BG, fg=ERROR).pack(anchor="w")
            if name_warn or name_bad:
                tk.Label(head, text=f"⚠ نام‌های مشکوک: ⚠{name_warn}  ✗{name_bad}  — قبل از تحویل بررسی کنید",
                         font=FS, bg=PANEL_BG, fg=ERROR if name_bad else WARNING).pack(anchor="w")

            # ── لیست فایل‌ها ──
            lbl = tk.Label(win, text="فایل‌های ساخته‌شده:", font=FB, bg=DARK_BG, fg=TEXT_S)
            lbl.pack(anchor="w", padx=12)

            frame = tk.Frame(win, bg=DARK_BG)
            frame.pack(fill="both", expand=True, padx=10, pady=(4, 6))
            lb = tk.Listbox(frame, bg=PANEL_BG, fg=TEXT_S, font=FM, selectbackground=ACCENT,
                            activestyle="none")
            sb = ttk.Scrollbar(frame, orient="vertical", command=lb.yview)
            lb.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            lb.pack(side="left", fill="both", expand=True)

            for i, e in enumerate(entries):
                status, score, issues = name_issues_map.get(e["name"], ("ok", 100, []))
                icon = self._name_status_icon(status)
                line = f"{icon} {e['name']}.pdf   ({e['صفحه']} صفحه)   ← from {e['src']}"
                if status != "ok":
                    line += f"   [{score}٪ {', '.join(issues[:2])}]"
                lb.insert("end", line)
                lb.itemconfig(i, fg=self._name_status_color(status))

            # ── دکمه‌ها ──
            btns = tk.Frame(win, bg=DARK_BG)
            btns.pack(fill="x", padx=10, pady=(0, 10))
            tk.Button(btns, text="بستن", font=FB, bg=BORDER_L, fg=TEXT_P, relief="flat",
                      command=win.destroy).pack(side="left", padx=3)
            tk.Button(btns, text="Open پوشه خروجی", font=FB, bg=ACCENT, fg=TEXT_P,
                      relief="flat", command=lambda: self._open_output_folder()).pack(side="left", padx=3)
        except Exception:
            pass

    def _open_output_folder(self):
        """پوشهٔ خروجی را در سیستم‌عامل باز می‌کند."""
        try:
            folder = self.output_dir.get().strip()
            if not folder:
                return
            if os.name == "nt":
                os.startfile(folder)  # type: ignore
            elif sys.platform == "darwin":
                import subprocess as _sp
                _sp.Popen(["open", folder])
            else:
                import subprocess as _sp
                _sp.Popen(["xdg-open", folder])
        except Exception:
            pass

    # ───────────────────── IMPLEMENTATIONS ─────────────────────
    def _run_split(self, out_dir):
        ensure_pdf_libs()
        if not PYPDF_AVAILABLE:
            self.log_q.put(("pypdf نصب نیست", "error"))
            return

        mode = self.split_mode.get()
        range_spec = self.split_range.get().strip()
        separate = self.split_separate.get()
        naming = self.split_naming.get()          # "manual" | "ocr"
        prefix = self.split_prefix.get().strip() or "{name}_p{page}"
        every_n = max(1, int(self.split_every_n.get())) if mode == "every" else 1

        # در حالت OCR موتور تشخیص متن را آماده کن
        ocr_engine = None
        ocr_type = None
        if naming == "ocr":
            if not PYMUPDF_AVAILABLE:
                self.log_q.put(("برای تشخیص خودکار نام، PyMuPDF (pymupdf) نصب نیست", "error"))
                return
            ocr_type, ocr_engine = self._create_ocr_engine()
            if ocr_engine is None:
                _err = getattr(self, "_ocr_error", None)
                _detail = f" — {_err}" if _err else ""
                self.log_q.put(("برای تشخیص خودکار نام، هیچ موتور OCR کار نکرد" + _detail,
                                "error"))
                return
            self.log_q.put((f"تشخیص خودکار نام فعال شد ({ocr_type})", "ok"))

        total = 0
        grand_total = 0
        for pdf_path in self.pdf_files:
            try:
                _r = PdfReader(str(pdf_path))
                grand_total += len(parse_page_ranges(len(_r.pages), range_spec))
            except Exception:
                pass

        done = 0
        report_entries = []   # برای گزارش نهایی: {"name", "src", "صفحه"}
        for pdf_path in self.pdf_files:
            used_names = set()   # برای جلوگیری از overwrite اسامی تکراری
            try:
                reader = PdfReader(str(pdf_path))
                total_صفحه = len(reader.pages)
                صفحه = parse_page_ranges(total_صفحه, range_spec)
                if not صفحه: continue

                base = pdf_path.stem
                doc = None
                if ocr_engine is not None:
                    doc = fitz.open(str(pdf_path))

                try:
                    if mode == "split_all" or (mode == "extract" and separate):
                        for idx in صفحه:
                            writer = PdfWriter()
                            writer.add_page(reader.pages[idx])
                            fname = self._make_output_name(base, idx, prefix, naming,
                                                           ocr_type, ocr_engine, doc)
                            fname = self._unique_name(fname, used_names)
                            outf = out_dir / f"{fname}.pdf"
                            with open(outf, "wb") as f: writer.write(f)
                            total += 1
                            done += 1
                            report_entries.append({"name": fname, "src": pdf_path.name, "صفحه": 1})
                            if grand_total:
                                self._set_progress(done * 100.0 / grand_total)
                    elif mode == "every":
                        # هر N صفحه به یک فایل تبدیل می‌شود
                        for chunk_start in range(0, len(صفحه), every_n):
                            chunk = صفحه[chunk_start:chunk_start + every_n]
                            writer = PdfWriter()
                            for idx in chunk:
                                writer.add_page(reader.pages[idx])
                            # نام از اولین صفحهٔ هر گروه خوانده می‌شود
                            fname = prefix.format(name=base, page=chunk[0] + 1)
                            if ocr_engine is not None:
                                fname = self._make_output_name(base, chunk[0], prefix,
                                                               naming, ocr_type,
                                                               ocr_engine, doc)
                            fname = self._unique_name(fname, used_names)
                            outf = out_dir / f"{fname}.pdf"
                            with open(outf, "wb") as f: writer.write(f)
                            total += len(chunk)
                            done += len(chunk)
                            report_entries.append({"name": fname, "src": pdf_path.name, "صفحه": len(chunk)})
                            if grand_total:
                                self._set_progress(done * 100.0 / grand_total)
                    else:
                        writer = PdfWriter()
                        for idx in صفحه:
                            writer.add_page(reader.pages[idx])
                        # در حالت غیرجدا, نام فقط یک بار از اولین صفحهٔ انتخابی خوانده می‌شود
                        fname = prefix.format(name=base, page='sel')
                        if ocr_engine is not None and صفحه:
                            fname = self._make_output_name(base, صفحه[0], prefix, naming,
                                                           ocr_type, ocr_engine, doc)
                        fname = self._unique_name(fname, used_names)
                        outf = out_dir / f"{fname}.pdf"
                        with open(outf, "wb") as f: writer.write(f)
                        total += len(صفحه)
                        done += len(صفحه)
                        report_entries.append({"name": fname, "src": pdf_path.name, "صفحه": len(صفحه)})
                        if grand_total:
                            self._set_progress(done * 100.0 / grand_total)
                finally:
                    if doc is not None:
                        doc.close()
                self.log_q.put((f"✓ {pdf_path.name} → {len(صفحه)} صفحه", "ok"))
            except Exception as e:
                self.log_q.put((f"خطا in {pdf_path.name}: {e}", "error"))
        self.log_q.put((f"Done! {total} صفحه", "ok"))
        if report_entries:
            self.log_q.put(("report_done", report_entries))

    def _preview_names(self):
        """Preview the names detected by OCR for all صفحه (without creating files)."""
        if self.processing:
            return
        if not self.pdf_files:
            messagebox.showwarning("خطا", "هیچ فایل PDF انتخاب نشده")
            return
        if not self.preview_listbox:
            return

        self.processing = True
        self.run_btn.config(state="disabled", text="در حال تشخیص اسامی...")
        self.status_lbl.config(text="در حال OCR صفحات...", fg=ACCENT)
        self.preview_listbox.delete(0, "end")
        self.preview_listbox.insert("end", "⏳ در حال پردازش...")

        def worker():
            try:
                results = []
                for pdf_path in self.pdf_files:
                    doc = None
                    try:
                        import fitz
                        doc = fitz.open(str(pdf_path))
                        ocr_type, ocr_engine = self._create_ocr_engine()
                        if ocr_engine is None:
                            _err = getattr(self, "_ocr_error", "") or ""
                            results.append((pdf_path.name, f"⚠ موتور OCR کار نکرد: {_err[:60]}"))
                            continue
                        for i in range(len(doc)):
                            name = self._ocr_person_name(ocr_type, ocr_engine, doc, i)
                            results.append((f"{pdf_path.name} • صفحه {i+1}", name))
                    except Exception as e:
                        results.append((pdf_path.name, f"خطا: {e}"))
                    finally:
                        if doc is not None:
                            doc.close()
                self.log_q.put(("preview_done", results))
            except Exception as e:
                self.log_q.put(("preview_done", [("خطا", str(e))]))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_preview(self, results):
        self.processing = False
        self.run_btn.config(state="normal", text="▶ اجرای عملیات انتخاب شده")
        if not results:
            self.status_lbl.config(text="هیچ نتیجه‌ای نبود", fg=WARNING)
            return
        self.preview_listbox.delete(0, "end")
        ok_count = 0
        warn_count = 0
        bad_count = 0
        for i, (src_name, person) in enumerate(results):
            status = "bad"  # پیش‌فرض؛ در شاخه‌ی else بدون خطا باقی می‌ماند
            if person and person != "⚠ OCR engine not installed":
                status, score, issues = self._validate_name(person)
                icon = self._name_status_icon(status)
                if status == "ok":
                    ok_count += 1
                elif status == "suspect":
                    warn_count += 1
                else:
                    bad_count += 1
                detail = f" ({score}%)"
                if issues:
                    detail += f" — {', '.join(issues[:2])}"
                line = f"{icon} {src_name}  ←  {person}{detail}"
            else:
                bad_count += 1
                line = f"✗ {src_name}  ←  (تشخیص داده نشد)"
            self.preview_listbox.insert("end", line)
            self.preview_listbox.itemconfig(i, fg=self._name_status_color(status if person and person != "⚠ OCR engine not installed" else "bad"))
        self.preview_listbox.pack(fill="x", pady=(6, 0))
        total_found = ok_count + warn_count + bad_count
        self.status_lbl.config(
            text=f"Preview: ✓{ok_count}  ⚠{warn_count}  ✗{bad_count}  (of {len(results)} صفحه)",
            fg=SUCCESS if ok_count and bad_count == 0 else (WARNING if warn_count else ERROR))

    @staticmethod
    def _unique_name(name, used_names):
        """اگر اسم قبلاً استفاده شده، یک شماره به آن اضافه می‌کند تا فایل‌ها پاک نشوند."""
        base_name = name
        counter = 2
        while name in used_names:
            name = f"{base_name} {counter}"
            counter += 1
        used_names.add(name)
        return name

    # ───────────── نام‌گذاری خودکار (OCR) ─────────────
    @staticmethod
    def _sanitize_filename(name):
        """کاراکترهای غیرمجاز برای نام فایل را پاک می‌کند و طول را محدود می‌کند."""
        name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name)
        name = name.strip().strip(".")
        name = re.sub(r'\s+', " ", name)
        return name[:80]

    def _create_ocr_engine(self):
        """بهترین موتور OCR موجود را می‌سازد (و کش می‌کند).

        اولویت با PaddleOCR است چون از فارسی پشتیبانی می‌کند؛
        اگر نصب نباشد از RapidOCR (فقط انگلیسی/لاتین) استفاده می‌شود.
        برمی‌گرداند: (نوع موتور, نمونه) یا (None, None)
        دلیل خطا (اگر باشد) در self._ocr_error ذخیره می‌شود.
        """
        # موتور قبلاً ساخته شده؟ همان را برگردان (صرفه‌جویی در زمان)
        if getattr(self, "_ocr_cached", None) is not None:
            return self._ocr_cached

        self._ocr_error = None
        result = (None, None)

        # مطمئن شو پوشه‌ی مدل‌ها وجود دارد (در حالت EXE ممکن است کنار exe باشد)
        try:
            home = os.environ.get("PADDLE_PDX_HOME", "")
            if home:
                Path(home).mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        # ۱) PaddleOCR — پشتیبانی از فارسی
        try:
            os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
            import logging as _logging
            _logging.getLogger("ppocr").setLevel(_logging.ERROR)
            from paddleocr import PaddleOCR
            engine = PaddleOCR(
                lang="fa",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="arabic_PP-OCRv5_mobile_rec",
                enable_mkldnn=False,
            )
            result = ("paddle", engine)
        except Exception as e:
            self._ocr_error = f"paddleocr: {type(e).__name__}: {e}"

        # ۲) RapidOCR — فقط انگلیسی/لاتین
        if result[1] is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                result = ("rapid", RapidOCR())
            except Exception as e:
                if self._ocr_error is None:
                    self._ocr_error = f"rapidocr: {type(e).__name__}: {e}"
                result = (None, None)

        self._ocr_cached = result
        return result

    def _make_output_name(self, base, page_idx, prefix, naming, ocr_type, ocr_engine, doc):
        """نام فایل خروجی را بر اساس حالت نام‌گذاری می‌سازد."""
        if naming == "ocr" and ocr_engine is not None and doc is not None:
            title = self._ocr_person_name(ocr_type, ocr_engine, doc, page_idx)
            if title:
                return title
            # اگر OCR چیزی پیدا نکرد, به الگوی دستی برمی‌گردیم
            return prefix.format(name=base, page=page_idx + 1)
        return prefix.format(name=base, page=page_idx + 1)

    @staticmethod
    def _extract_person_name(lines):
        """از خطوط OCR شده, نام و نام خانوادگی فرد را استخراج می‌کند.

        خطوط باید لیستی از دیکشنری‌های {'y': float, 'text': str} باشند.
        الگوها بر اساس گواهی فوت فارسی تنظیم شده‌اند؛ OCR نویز دارد،
        بنابراین برچسب‌ها به شکل‌های مختلف پذیرفته می‌شوند و نویسه‌های
        فارسی نرمال‌سازی می‌شوند (ى→ی, ك→ک و...).
        """
        # الگوهای OCR با نویزهای رایج
        FAMILY_RE = re.compile(r'(?:خانواد|خاناد|خاواد|خاتواد|خائنواد|فاواد|خاواک)[ییکگستمع]*')
        FATHER_RE = re.compile(r'پدر|بدرن|بدرز|بددرن|یدر|بدو|بدر(?!ی)')
        MOTHER_RE = re.compile(r'مادر[زن]*|مادرة|مادز|معارن?')
        FIRST_RE = re.compile(r'^(بنام|نمام|نام|تامد|ناام|نامم|ذام|قام|تام|بام|ثام|فام|مان|ذم|ام)')
        NOISE_RE = re.compile(r'^(?:حیک|هی\s+|معی\s+|عی\s+|کی\s+|ی\s+)')

        def norm(text):
            """نرمال‌سازی نویسه‌های فارسی: ى/ي→ی, ك→ک, ة→ه و..."""
            text = text.replace("\u0649", "\u06CC")   # ى → ی
            text = text.replace("\u064A", "\u06CC")   # ي (عربی) → ی
            text = text.replace("\u0643", "\u06A9")   # ك → ک
            text = text.replace("\u0629", "\u0647")   # ة → ه
            text = text.replace("\u0623", "\u0627")   # أ → ا
            text = text.replace("\u0625", "\u0627")   # إ → ا
            text = text.replace("\u0622", "\u0627")   # آ → ا
            return text

        def val_after(text, m):
            rest = text[m.end():]
            rest = re.sub(r'^[\s;؛:،,.\-–]+', '', rest)
            rest = NOISE_RE.sub('', rest)
            rest = rest.strip(' ;؛:،.')
            # حذف نویز تک‌حرفی آخر (مثل «ی» جدا شده) که به اسم نچسبیده
            rest = re.sub(r'\s+[ی]\s*$', '', rest)
            return rest.strip()

        first = None
        family = None
        for line in lines:
            text = norm(str(line.get("text", "")))
            if "مامور" in text or "مامو" in text:
                continue
            if "امضا" in text:
                continue
            m = FAMILY_RE.search(text)
            if m:
                val = val_after(text, m)
                if val:
                    family = val
                continue
            if FATHER_RE.search(text) or MOTHER_RE.search(text):
                continue
            m = FIRST_RE.search(text)
            if m:
                val = val_after(text, m)
                if val and first is None:
                    first = val
        # اصلاح املایی امن (وقتی OCR حرف «ک» اول را می‌اندازد)
        if first == "شاورزی":
            first = "کشاورزی"
        if family == "شاورزی":
            family = "کشاورزی"
        return first, family

    @staticmethod
    def _validate_name(name):
        """اعتبارسنجی نام استخراج‌شده با OCR.

        برمی‌گرداند: (status, score, issues)
        - status: "ok" | "suspect" | "bad"
        - score: عدد ۰ تا ۱۰۰
        - issues: لیست دلایل
        """
        if not name:
            return ("bad", 0, ["خالی"])

        # نرمال‌سازی اولیه (ى/ي→ی, ك→ک) تا حروف عربی مشکل نسازند
        name = name.replace("\u0649", "\u06CC").replace("\u064A", "\u06CC")
        name = name.replace("\u0643", "\u06A9")

        score = 100
        issues = []

        # کلمات کلیدی که یعنی فیلد اشتباه گرفته شده
        KEYWORDS = ["مامور", "امضا", "نام خانواد", "نام پدر", "نام مادر",
                    "خانوادگي", "خانواده", "شماره", "تاريخ", "جنسيت"]
        for kw in KEYWORDS:
            if kw in name:
                return ("bad", 0, [f"کلمهٔ کلیدی: {kw}"])

        # طول نام
        if len(name) < 2:
            score -= 40
            issues.append("طول خیلی کوتاه")
        if len(name) > 60:
            score -= 20
            issues.append("طول خیلی بلند")

        # ارقام (فارسی ۰-۹ و عربی ٠-٩ و انگلیسی 0-9)
        digits = re.findall(r'[\u06F0-\u06F9\u0660-\u06690-9]', name)
        if digits:
            score -= 25
            issues.append(f"شامل عدد: {''.join(digits[:3])}")

        # حروف لاتین
        latin = re.findall(r'[A-Za-z]', name)
        if latin:
            score -= 30
            issues.append("حروف لاتین")

        # علائم و کاراکترهای غیرمجاز
        PUNCT = set(';؛:،,.-/\\()[]{}<>|!?@#$%^&*_+=`~')
        bad_chars = [c for c in name if c in PUNCT]
        if bad_chars:
            score -= 30
            issues.append(f"علائم: {''.join(bad_chars[:3])}")

        # کاراکترهای غیرفارسی (مثل ایموجی یا نماد)
        other = re.findall(r'[^\u0600-\u06FF\u200c\s\u06F0-\u06F9\u0660-\u0669A-Za-z0-9]', name)
        if other:
            score -= 10 * min(len(other), 3)
            issues.append("کاراکتر نامعمول")

        # نویزهای باقی‌ماندهٔ تک‌حرفی جدا (مثل «ي» تنها)
        if re.search(r'(^|\s)[یي]($|\s)', name):
            score -= 15
            issues.append('حرف «ی» تنها')

        score = max(0, min(100, score))
        if score >= 80:
            return ("ok", score, issues)
        elif score >= 45:
            return ("suspect", score, issues)
        else:
            return ("bad", score, issues)

    @staticmethod
    def _name_status_icon(status):
        """نماد وضعیت برای نمایش در لیست‌ها."""
        return {"ok": "✓", "suspect": "⚠", "bad": "✗"}.get(status, "?")

    @staticmethod
    def _name_status_color(status):
        return {"ok": SUCCESS, "suspect": WARNING, "bad": ERROR}.get(status, TEXT_S)

    def _ocr_person_name(self, ocr_type, ocr_engine, doc, page_num):
        """نام کامل فرد (نام + نام خانوادگی) را برمی‌گرداند.

        اگر کاربر روی صفحه هایلایت زده باشد (دیجیتال یا ماژیک دستی — هر رنگی),
        فقط همان ناحیه خوانده می‌شود؛ وگرنه کل صفحه OCR می‌شود.
        """
        try:
            try:
                import fitz
            except ImportError:
                return ""
            # ۱) اول: ناحیهٔ هایلایت شده (اگر باشد)
            hl_name = self._ocr_highlighted_name(ocr_type, ocr_engine, doc, page_num)
            if hl_name:
                return hl_name
            # ۲) در غیر این صورت: کل صفحه
            page = doc[page_num]
            # کل صفحه به تصویر تبدیل می‌شود (فیلدهای نام وسط صفحه هستند)
            pix = page.get_pixmap(dpi=150)
            tmp_name = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp_name = tmp.name
                pix.save(tmp_name)
                lines = []
                if ocr_type == "paddle":
                    result = ocr_engine.predict(tmp_name)
                    for res in result:
                        texts = res.get("rec_texts", [])
                        polys = res.get("rec_polys", [])
                        for i, t in enumerate(texts):
                            t = str(t)
                            if not t.strip():
                                continue
                            box = polys[i] if i < len(polys) else None
                            y = float(min(p[1] for p in box)) if box is not None else 0.0
                            lines.append({"y": y, "text": t})
                else:
                    result, _ = ocr_engine(tmp_name)
                    for item in result or []:
                        try:
                            box, text, score = item[0], item[1], float(item[2])
                            if score < 0.3:
                                continue
                            y = float(min(p[1] for p in box))
                            lines.append({"y": y, "text": str(text)})
                        except Exception:
                            continue
            finally:
                if tmp_name:
                    try:
                        os.unlink(tmp_name)
                    except OSError:
                        pass
            if not lines:
                return ""
            lines.sort(key=lambda d: d["y"])
            first, family = self._extract_person_name(lines)
            full = " ".join(x for x in (first, family) if x).strip()
            return self._sanitize_filename(full)
        except Exception:
            return ""

    def _find_highlight_rect(self, page):
        """مستطیل ناحیهٔ هایلایت‌شده را برمی‌گرداند (هر رنگی).

        هایلایت = انوتیشن از نوع Highlight/Underline/Squiggly/StrikeOut.
        رنگ انوتیشن مهم نیست: زرد، صورتی، سبز، آبی و... همه شمرده می‌شوند.
        """
        try:
            import fitz
        except ImportError:
            return None
        MARK_TYPES = (8, 9, 10, 11)   # Highlight, Underline, Squiggly, StrikeOut
        candidates = []
        try:
            annots = list(page.annots()) if page.annots() else []
        except Exception:
            annots = []
        for annot in annots:
            try:
                if annot.type is None:
                    continue
                atype = annot.type[0] if isinstance(annot.type, (list, tuple)) else annot.type
                if atype not in MARK_TYPES:
                    continue
                rect = annot.rect
                if rect.is_empty or rect.is_infinite:
                    continue
                candidates.append(rect)
            except Exception:
                continue
        return candidates[0] if candidates else None

    @staticmethod
    def _find_colored_regions(w, h, data, stride, sat_threshold=30, cell=6, min_cells=6, min_width_px=24, return_cells=False):
        """ناحیه‌های رنگیِ اشباع‌شده (غیر خاکستری/سیاه‌وسفید) را در بافر RGB پیدا می‌کند.

        data: بایت‌های خام RGB (مثل fitz.Pixmap.samples)؛ stride: طول هر ردیف.
        بازمی‌گرداند: فهرست مستطیل‌ها به مختصات پیکسل
        {"x0", "y0", "x1", "y1", "count", "width"} — هر ناحیه یک خوشه از
        سلول‌های رنگیِ همسایه است (مثلاً یک خط ماژیک). هر رنگی در نظر
        گرفته می‌شود، نه فقط زرد: هر پیکسلی که «سیاه‌وسفید/خاکستری نیست»
        یعنی max(r,g,b) - min(r,g,b) آستانه را رد کرده، رنگی است.
        اگر return_cells=True باشد، (regions, colored_cells) برمی‌گردد؛
        colored_cells مجموعهٔ سلول‌های رنگی به شبکهٔ ۶ پیکسلی است (برای
        تشخیص کلماتی که واقعاً رویش ماژیک خورده).
        """
        d = data
        st = stride
        th = sat_threshold
        cl = cell
        cells = set()
        cellcnt = {}
        for y in range(h):
            off = y * st
            gy = y // cl
            for x3 in range(0, w * 3, 3):
                r = d[off + x3]
                g = d[off + x3 + 1]
                b = d[off + x3 + 2]
                mx = r if r > g else g
                if b > mx:
                    mx = b
                mn = r if r < g else g
                if b < mn:
                    mn = b
                if mx - mn > th:
                    key = ((x3 // 3) // cl, gy)
                    cells.add(key)
                    cellcnt[key] = cellcnt.get(key, 0) + 1
        if not cells:
            return ([], None) if return_cells else []
        seen = set()
        regions = []
        for c in cells:
            if c in seen:
                continue
            stack = [c]
            seen.add(c)
            cnt = 1
            minx = maxx = c[0]
            miny = maxy = c[1]
            while stack:
                cx, cy = stack.pop()
                for dx in (-2, -1, 0, 1, 2):
                    nx = cx + dx
                    for dy in (-2, -1, 0, 1, 2):
                        n2 = (nx, cy + dy)
                        if n2 in cells and n2 not in seen:
                            seen.add(n2)
                            stack.append(n2)
                            cnt += 1
                            if n2[0] < minx: minx = n2[0]
                            if n2[0] > maxx: maxx = n2[0]
                            if n2[1] < miny: miny = n2[1]
                            if n2[1] > maxy: maxy = n2[1]
            if cnt < min_cells:
                continue
            px0, py0 = minx * cl, miny * cl
            px1, py1 = (maxx + 1) * cl, (maxy + 1) * cl
            if px1 - px0 < min_width_px:
                continue
            regions.append({"x0": px0, "y0": py0, "x1": px1, "y1": py1,
                            "count": cnt, "width": px1 - px0})
        if return_cells:
            return regions, cellcnt
        return regions

    def _find_pixel_marked_region(self, page):
        """هایلایت دستی (ماژیک روی کاغذ) را با رنگ پیکسل در صفحهٔ اسکن‌شده پیدا می‌کند.

        بازمی‌گرداند: (fitz.Rect, مجموعهٔ سلول‌های رنگی در مختصات صفحه
        (نقطه) بر شبکهٔ ۶pt) یا (None, None). مجموعهٔ سلول‌ها برای مشخص
        کردن کلماتی استفاده می‌شود که واقعاً رویش ماژیک هستند (ردیف‌های
        همسایهٔ جدول که ماژیک به‌اندازهٔ کافی روی آن‌ها نیامده، حذف می‌شوند).
        """
        try:
            import fitz
        except ImportError:
            return None, None
        try:
            pr = page.rect
            # محدود کردن تعداد پیکسل در صفحات خیلی بزرگ (~۱.۲ میلیون پیکسل)
            scale = min(1.0, (1_200_000.0 / max(1.0, pr.width * pr.height)) ** 0.5)
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            if pix.colorspace is not None and getattr(pix.colorspace, "name", "") != "DeviceRGB":
                pix = fitz.Pixmap(fitz.csRGB, pix)
            if pix.n < 3:
                return None, None
            regions, all_cells = self._find_colored_regions(
                pix.width, pix.height, pix.samples, pix.stride, return_cells=True)
            if not regions:
                return None, None
            best = max(regions, key=lambda r: (r["count"], r["width"]))
            cl = 6
            # فقط سلول‌های همین ناحیه (نویز پراکندهٔ سراسر صفحه حذف شود)
            x0c, y0c = best["x0"] // cl, best["y0"] // cl
            x1c, y1c = (best["x1"] - 1) // cl, (best["y1"] - 1) // cl
            cells = {c: n for c, n in all_cells.items()
                     if x0c <= c[0] <= x1c and y0c <= c[1] <= y1c}
            rect = fitz.Rect(
                max(0.0, best["x0"] / scale),
                max(0.0, best["y0"] / scale),
                min(pr.width, best["x1"] / scale),
                min(pr.height, best["y1"] / scale),
            )
            # مختصات سلول‌ها در شبکهٔ ۶pt صفحه (برای مقایسه با جعبه‌های کلمات)
            # مقدار هر سلول = تعداد پیکسل‌های رنگی آن (چگالی ماژیک)
            cells_pt = {}
            for (cx, cy), n in cells.items():
                k = (round(cx / scale), round(cy / scale))
                cells_pt[k] = cells_pt.get(k, 0) + n
            return rect, cells_pt
        except Exception:
            return None, None

    def _find_pixel_marked_rect(self, page):
        """سازگار با قبل: فقط مستطیل هایلایت."""
        rect, _cells = self._find_pixel_marked_region(page)
        return rect

    @staticmethod
    def _norm_fa(t):
        """نرمال‌سازی حروف فارسی (ی/ک) برای تطبیق مطمئن برچسب‌ها."""
        return t.replace("\u0649", "\u06CC").replace("\u064A", "\u06CC").replace("\u0643", "\u06A9").strip()

    def _word_on_marker(self, word, cells, pad=3.0, min_ratio=0.15, cl=6.0):
        """آیا کلمه واقعاً رویش ناحیهٔ رنگی (ماژیک) قرار دارد؟"""
        if not cells:
            return True
        x0, y0 = word["x0"] - pad, word["y0"] - pad
        x1, y1 = word["x1"] + pad, word["y1"] + pad
        gx0, gx1 = int(x0 // cl), int(x1 // cl)
        gy0, gy1 = int(y0 // cl), int(y1 // cl)
        total = 0
        hit = 0
        for gx in range(gx0, gx1 + 1):
            for gy in range(gy0, gy1 + 1):
                total += 1
                if (gx, gy) in cells:
                    hit += 1
        if total and hit >= 2 and hit / total >= min_ratio:
            return True
        # جایگزین: مرکز کلمه داخل محدودهٔ ماژیک
        cx, cy = (word["x0"] + word["x1"]) / 2, (word["y0"] + word["y1"]) / 2
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        return ((min(xs) * cl - 4) <= cx <= (max(xs) + 1) * cl + 4 and
                (min(ys) * cl - 4) <= cy <= (max(ys) + 1) * cl + 4)

    def _ocr_words_in_page(self, tmp_name, ocr_type, ocr_engine, clip):
        """تصویر ناحیه را OCR می‌کند و کلمات را با جعبه در مختصات صفحه (نقطه) برمی‌گرداند."""
        words = []
        s = 300.0 / 72.0
        try:
            if ocr_type == "paddle":
                result = ocr_engine.predict(tmp_name)
                for res in result:
                    texts = res.get("rec_texts", [])
                    polys = res.get("rec_polys", [])
                    for i, t in enumerate(texts):
                        t = str(t)
                        if not t.strip():
                            continue
                        box = polys[i] if i < len(polys) else None
                        if box is None:
                            continue
                        x0 = min(p[0] for p in box); x1 = max(p[0] for p in box)
                        y0 = min(p[1] for p in box); y1 = max(p[1] for p in box)
                        words.append({"x0": clip.x0 + x0 / s, "y0": clip.y0 + y0 / s,
                                      "x1": clip.x0 + x1 / s, "y1": clip.y0 + y1 / s,
                                      "text": t.strip()})
            else:
                result, _ = ocr_engine(tmp_name)
                for item in result or []:
                    try:
                        box, text, score = item[0], item[1], float(item[2])
                        if score < 0.3 or not str(text).strip():
                            continue
                        x0 = min(p[0] for p in box); x1 = max(p[0] for p in box)
                        y0 = min(p[1] for p in box); y1 = max(p[1] for p in box)
                        words.append({"x0": clip.x0 + x0 / s, "y0": clip.y0 + y0 / s,
                                      "x1": clip.x0 + x1 / s, "y1": clip.y0 + y1 / s,
                                      "text": str(text).strip()})
                    except Exception:
                        continue
        except Exception:
            return []
        return words

    @staticmethod
    def _cluster_lines(words, min_overlap=0.35):
        """کلمات را به سطوح متنی می‌رساند (بر اساس همپوشانی عمودی)."""
        ws = sorted(words, key=lambda w: (w["y0"] + w["y1"]) / 2)
        lines = []
        for w in ws:
            wh = w["y1"] - w["y0"]
            placed = False
            for L in lines:
                overlap = min(L["y1"], w["y1"]) - max(L["y0"], w["y0"])
                if overlap >= min_overlap * min(L["y1"] - L["y0"], wh):
                    L["words"].append(w)
                    L["y0"] = min(L["y0"], w["y0"])
                    L["y1"] = max(L["y1"], w["y1"])
                    placed = True
                    break
            if not placed:
                lines.append({"y0": w["y0"], "y1": w["y1"], "words": [w]})
        return lines

    @staticmethod
    def _line_rtl(line):
        """کلمات یک سطح به ترتیب خوانش راست‌به‌چپ (فارسی)."""
        return sorted(line["words"], key=lambda w: -((w["x0"] + w["x1"]) / 2))

    @staticmethod
    def _marker_cell_count_y(cells, y0, y1):
        """تعداد سلول‌های رنگی ماژیک در بازهٔ عمودی مشخص."""
        if not cells:
            return 0
        n = 0
        for (_gx, gy), c in cells.items():
            if (y0 - 1) <= gy * 6 + 3 <= (y1 + 1):
                n += c
        return n

    def _name_columns_from_words(self, words):
        """اگر برچسب‌های «نام» و «نام خانوادگی» در میان کلمات باشند، ستون‌هایشان را می‌دهد.

        بازمی‌گرداند: ((fam_x0, fam_x1), (first_x0, first_x1), مجموعهٔ id کلمات
        برچسبی) یا None. تطبیق دقیق «نام خانوادگی» اولویت دارد تا برچسب‌های
        مشابه (مثل «نام و نام خانوادگی» در جعبهٔ بالای صفحه) سردرگم نشوند.
        """
        fam_exact = None
        fam_any = None
        firsts = []
        for w in words:
            t = self._norm_fa(w["text"])
            if t in ("نام خانوادگی", "نام خانوادگي"):
                if fam_exact is None:
                    fam_exact = w
            elif "خانوادگی" in t or "خانوادگي" in t:
                if fam_any is None or len(t) < len(self._norm_fa(fam_any["text"])):
                    fam_any = w
            elif t == "نام":
                firsts.append(w)
        fam = fam_exact if fam_exact is not None else fam_any
        fam_range = None
        first_range = None
        if fam is not None:
            fam_range = (fam["x0"], fam["x1"])
        if firsts:
            if fam is not None:
                # ستون نام معمولاً راست‌تر از ستون نام خانوادگی است (چیدمان RTL)
                right = [w for w in firsts if w["x0"] >= fam["x1"] - 3]
                pick = min(right, key=lambda w: w["x0"]) if right else \
                       min(firsts, key=lambda w: abs(w["x0"] - fam["x1"]))
            else:
                pick = firsts[0]
            first_range = (pick["x0"], pick["x1"])
        if fam_range is None and first_range is None:
            return None
        labels = set()
        if fam is not None:
            labels.add(id(fam))
        if first_range is not None:
            labels.add(id(pick))
        return fam_range, first_range, labels

    def _name_columns_above(self, page, clip, ocr_type, ocr_engine):
        """برچسب‌های «نام»/«نام خانوادگی» را در سرِ جدول، بالای ناحیه جست‌وجو می‌کند."""
        try:
            import fitz
        except ImportError:
            return None
        try:
            pr = page.rect
            band = fitz.Rect(max(0, clip.x0 - 15), max(0, clip.y0 - 130),
                             min(pr.width, clip.x1 + 15), max(0, clip.y0 - 2))
            if band.height < 8 or band.width < 40:
                return None
            pix = page.get_pixmap(dpi=300, clip=band)
            tmp_name = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp_name = tmp.name
                pix.save(tmp_name)
                words = self._ocr_words_in_page(tmp_name, ocr_type, ocr_engine, band)
            finally:
                if tmp_name:
                    try:
                        os.unlink(tmp_name)
                    except OSError:
                        pass
            if not words:
                return None
            return self._name_columns_from_words(words)
        except Exception:
            return None

    def _best_name_run(self, word_list, first_range):
        """بهترین گروهِ هم‌پوشِ ۱ تا ۴ کلمهٔ شبیه‌به‌نام را برمی‌گرداند."""
        if not word_list:
            return ""
        best, best_score = "", 0
        n = len(word_list)
        for i in range(n):
            for j in range(i + 1, min(i + 5, n + 1)):
                run = " ".join(w["text"] for w in word_list[i:j])
                _status, score, _issues = self._validate_name(run)
                if j - i in (2, 3):
                    score += 5   # نام‌های ۲–۴ کلمه‌ای رایج‌ترند
                if len(run.split()) > 3:
                    score -= (len(run.split()) - 3) * 8   # کلمهٔ اضافه کم‌احتمال است
                if first_range is not None:
                    if any(first_range[0] - 5 <= (w["x0"] + w["x1"]) / 2 <= first_range[1] + 5
                           for w in word_list[i:j]):
                        score += 10   # گروه شامل کلمهٔ ستون «نام» مطمئن‌تر است
                if score > best_score:
                    best_score, best = score, run
        return best if best_score >= 45 else ""

    def _pick_name_from_words(self, words, page, clip, cells, ocr_type, ocr_engine):
        """فقط نام را از کلمات ناحیهٔ هایلایت‌شده استخراج می‌کند.

        ۱) کلماتی که واقعاً رویش ماژیک هستند (اگر اطلاعات پیکسلی باشد)
        ۲) ستون‌های «نام»/«نام خانوادگی» اگر سر جدول دیده شود (داخل ناحیه یا بالای آن)
        ۳) از سطوح به‌دست‌آمده، سطحی که ماژیک واقعاً روی آن است (بیشترین سلول رنگی)
        """
        if not words:
            return ""
        # ۱) حذف کلمات ردیف‌های همسایه (واقعاً رویش ماژیک نیستند)
        if cells:
            kept = [w for w in words if self._word_on_marker(w, cells)]
            if kept:
                words = kept
        # ۲) ستون‌های نام/نام خانوادگی
        first_range = None
        used_cols = False
        cols = self._name_columns_from_words(words)
        if cols is None:
            cols = self._name_columns_above(page, clip, ocr_type, ocr_engine)
        if cols:
            fam_range, first_range, labels = cols
            sel = []
            for w in words:
                if id(w) in labels:
                    continue
                cx = (w["x0"] + w["x1"]) / 2
                ok = (fam_range is not None and fam_range[0] - 5 <= cx <= fam_range[1] + 5) or \
                     (first_range is not None and first_range[0] - 5 <= cx <= first_range[1] + 5)
                if ok:
                    sel.append(w)
            if sel:
                words = sel
                used_cols = True
        lines = self._cluster_lines(words)
        if not lines:
            return ""
        # ناحیهٔ کوچک با یک سطح: رفتار قبلی (چسباندن کلمات)
        if len(words) <= 4 and len(lines) == 1 and not used_cols:
            text = " ".join(w["text"] for w in self._line_rtl(lines[0]))
            return self._clean_highlight_text(text)
        # ۳) چند سطح / کلمات زیاد → سطحی که ماژیک واقعاً روی آن است
        scored = []
        for L in lines:
            Lw = self._line_rtl(L)
            text = " ".join(w["text"] for w in Lw)
            _status, score, _issues = self._validate_name(text)
            weight = self._marker_cell_count_y(cells, L["y0"], L["y1"])
            scored.append((score, weight, (L["y0"] + L["y1"]) / 2, Lw, text))
        good = [s for s in scored if s[0] >= 45]
        if not good:
            text = " ".join(w["text"] for w in sorted(words, key=lambda w: -((w["x0"] + w["x1"]) / 2)))
            return self._clean_highlight_text(text)
        if cells:
            max_w = max(g[1] for g in good)
            if max_w > 0:
                top = max(good, key=lambda g: g[1])
                # اگر سطح دوم هم چگالی مقارن (≥۷۰٪) داشته باشد و ناحیه باریک باشد
                # → احتمالاً نام روی دو خط نوشته شده → هر دو را با هم بخوان
                near = [g for g in good if g[1] >= 0.7 * max_w]
                if len(near) == 2 and (clip.x1 - clip.x0) < 200:
                    allw = []
                    for g in sorted(near, key=lambda g: g[2]):
                        allw.extend(g[3])
                    allw.sort(key=lambda w: (round(w["y0"] / 4), -(w["x0"] + w["x1"]) / 2))
                    text = " ".join(w["text"] for w in allw)
                    return self._clean_highlight_text(text)
                best_score, _w, _ly, best_words, best_text = top
            else:
                best_score, _w, _ly, best_words, best_text = max(good, key=lambda g: g[0])
        else:
            best_score, _w, _ly, best_words, best_text = max(good, key=lambda g: g[0])
        # سطح انتخاب‌شده طولانی است (یا ستون‌ها معلوم است) → بهترین قطعهٔ نام درون آن
        if used_cols or len(best_words) > 4:
            run = self._best_name_run(best_words, first_range)
            if run:
                best_text = run
        return self._clean_highlight_text(best_text)

    def _ocr_highlighted_name(self, ocr_type, ocr_engine, doc, page_num):
        """نام را از ناحیهٔ هایلایت‌شده می‌خواند.

        - اگر PDF متنی باشد: همان متن داخل هایلایت گرفته می‌شود.
        - اگر PDF اسکن شده باشد: ناحیه به تصویر تبدیل و OCR می‌شود.
        - هایلایت دستی (ماژیک) روی اسکن‌ها پیکسل‌به‌پیکسل و با هر رنگی پیدا می‌شود.
        - اگر هایلایت پهن باشد (مثلاً یک ردیف کامل جدول)، فقط ستون‌های
          «نام»/«نام خانوادگی» خوانده می‌شوند و اسم‌های دیگر ردیف بیرون می‌مانند.
        برمی‌گرداند: نام تمیز شده یا رشتهٔ خالی.
        """
        try:
            try:
                import fitz
            except ImportError:
                return ""
            page = doc[page_num]
            cells = None
            rect = self._find_highlight_rect(page)
            if rect is None:
                # هایلایت دستی (ماژیک روی کاغذ) انوتیشن ندارد؛ روی صفحات
                # اسکن‌شده (بدون لایهٔ متن) ناحیهٔ رنگی را پیکسل‌به‌پیکسل
                # جست‌وجو می‌کنیم — هر رنگ غیرسیاه‌وسفید.
                try:
                    has_text = len(page.get_text("text").strip()) > 20
                except Exception:
                    has_text = False
                if not has_text:
                    rect, cells = self._find_pixel_marked_region(page)
            if rect is None:
                return ""
            # کمی حاشیه دور هایلایت برای خواندن بهتر
            margin = 3
            clip = fitz.Rect(
                max(0, rect.x0 - margin), max(0, rect.y0 - margin),
                rect.x1 + margin, rect.y1 + margin,
            )
            # ۱) اگر متن مستقیم داخل ناحیه هست (PDF متنی)
            direct = ""
            try:
                direct = page.get_textbox(clip).strip()
            except Exception:
                direct = ""
            if direct:
                name = self._clean_highlight_text(direct)
                if name:
                    return self._sanitize_filename(name)
            # ۲) وگرنه ناحیه را تصویر کرده و OCR کن (PDF اسکن شده)
            pix = page.get_pixmap(dpi=300, clip=clip)
            tmp_name = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp_name = tmp.name
                pix.save(tmp_name)
                words = self._ocr_words_in_page(tmp_name, ocr_type, ocr_engine, clip)
            finally:
                if tmp_name:
                    try:
                        os.unlink(tmp_name)
                    except OSError:
                        pass
            if not words:
                return ""
            name = self._pick_name_from_words(words, page, clip, cells, ocr_type, ocr_engine)
            return self._sanitize_filename(name) if name else ""
        except Exception:
            return ""

    @staticmethod
    def _clean_highlight_text(text):
        """متن ناحیهٔ هایلایت را به نام تمیز تبدیل می‌کند.

        - «نام: سهراب زارعی» → «سهراب زارعی»
        - «سهراب زارعی» → «سهراب زارعی»
        - نویزهای OCR (ى→ی, ك→ک, حروف لاتین تکی) حذف می‌شوند.
        """
        if not text:
            return ""
        # نرمال‌سازی نویسه‌های فارسی
        t = text.replace("\u0649", "\u06CC").replace("\u064A", "\u06CC")
        t = t.replace("\u0643", "\u06A9")
        # حذف برچسب‌های «نام» و «نام خانوادگی» و جداکننده‌ها
        t = re.sub(r'(?i)(نام خانوادگی|نام خانوادگي|نام و نام خانوادگی|نام و نام خانوادگي|نام کامل|نام:)', ' ', t)
        t = re.sub(r'(?i)نام\s*[::：]?', ' ', t)
        # حذف جداکننده‌ها و نویز
        t = re.sub(r'[;؛:،,|/_\\\-]+', ' ', t)
        t = re.sub(r'\s+', ' ', t).strip()
        # حذف حروف لاتین تکی (نویز OCR مثل I, L, O) وقتی اسم فارسی است
        if re.search(r'[\u0600-\u06FF]', t):
            t = re.sub(r'\b[A-Za-z]\b', '', t)
            t = re.sub(r'\s+', ' ', t).strip()
        return t


    def _run_merge(self, out_dir):
        ensure_pdf_libs()
        if not PYPDF_AVAILABLE or len(self.pdf_files) < 2:
            self.log_q.put(("حداقل ۲ فایل برای ادغام لازم است", "warn"))
            return

        out_name = self.merge_out_name.get().strip() or "merged.pdf"
        if not out_name.lower().endswith(".pdf"): out_name += ".pdf"

        try:
            writer = PdfWriter()
            total_صفحه = 0
            for pdf_path in self.pdf_files:
                reader = PdfReader(str(pdf_path))
                for page in reader.pages:
                    writer.add_page(page)
                total_صفحه += len(reader.pages)
            out_path = out_dir / out_name
            with open(out_path, "wb") as f: writer.write(f)
            self.log_q.put((f"✓ Merge success: {out_name} ({total_صفحه} صفحه)", "ok"))
        except Exception as e:
            self.log_q.put((f"خطا: {e}", "error"))

    def _run_pdf_to_images(self, out_dir):
        ensure_pdf_libs()
        if not PYPDF_AVAILABLE: return
        dpi = self.img_dpi.get()
        fmt = self.img_format.get()
        range_spec = self.img_range.get().strip()

        count = 0
        for pdf_path in self.pdf_files:
            try:
                if PYMUPDF_AVAILABLE:
                    doc = fitz.open(str(pdf_path))
                    صفحه = parse_page_ranges(len(doc), range_spec)
                    for idx in صفحه:
                        pix = doc[idx].get_pixmap(dpi=dpi)
                        ext = ".png" if fmt == "PNG" else (".jpg" if fmt == "JPEG" else ".webp")
                        out_path = out_dir / f"{pdf_path.stem}_p{idx+1}{ext}"
                        pix.save(str(out_path))
                        count += 1
                    doc.close()
                else:
                    self.log_q.put(("برای کیفیت خوب PyMuPDF نصب کنید", "warn"))
            except Exception as e:
                self.log_q.put((f"خطا: {e}", "error"))
        self.log_q.put((f"✓ {count} تصویر ساخته شد", "ok"))

    def _run_images_to_pdf(self, out_dir):
        if not self.image_files: return
        out_name = self.img_to_pdf_name.get().strip() or "output.pdf"
        if not out_name.lower().endswith(".pdf"): out_name += ".pdf"
        out_path = out_dir / out_name
        try:
            imgs = []
            for p in self.image_files:
                im = Image.open(p)
                if im.mode in ("RGBA", "P"): im = im.convert("RGB")
                imgs.append(im)
            if imgs:
                imgs[0].save(out_path, "PDF", save_all=True, append_images=imgs[1:])
                self.log_q.put((f"✓ PDF از {len(imgs)} تصویر ساخته شد", "ok"))
        except Exception as e:
            self.log_q.put((f"خطا: {e}", "error"))

    def _run_advanced_tools(self, out_dir):
        ensure_pdf_libs()
        if not PYPDF_AVAILABLE: return
        for pdf_path in self.pdf_files:
            try:
                reader = PdfReader(str(pdf_path))
                writer = PdfWriter()
                angle = self.rotate_angle.get()
                صفحه_rot = parse_page_ranges(len(reader.pages), self.rotate_range.get())
                for i, page in enumerate(reader.pages):
                    if i in صفحه_rot:
                        page.rotate(angle)
                    writer.add_page(page)
                outf = out_dir / f"{pdf_path.stem}_rotated.pdf"
                with open(outf, "wb") as f: writer.write(f)
                self.log_q.put((f"✓ چرخش انجام شد: {pdf_path.name}", "ok"))
            except Exception as e:
                self.log_q.put((f"خطا: {e}", "error"))

    def _run_text_extract(self):
        ensure_pdf_libs()
        if not PYPDF_AVAILABLE: return
        out_dir = Path(self.output_dir.get())
        out_dir.mkdir(parents=True, exist_ok=True)
        for pdf_path in self.pdf_files:
            try:
                reader = PdfReader(str(pdf_path))
                صفحه = parse_page_ranges(len(reader.pages), self.text_range.get())
                text = ""
                for i in صفحه:
                    text += f"\n=== صفحه {i+1} ===\n{reader.pages[i].extract_text() or ''}\n"
                outf = out_dir / f"{pdf_path.stem}_text.txt"
                with open(outf, "w", encoding="utf-8") as f: f.write(text)
                self.log_q.put((f"✓ متن استخراج شد: {outf.name}", "ok"))
            except Exception as e:
                self.log_q.put((f"خطا: {e}", "error"))

    def _show_pdf_info(self):
        if not self.pdf_files:
            messagebox.showinfo("اطلاعات", "No PDF selected")
            return
        ensure_pdf_libs()
        sel = self.pdf_listbox.curselection()
        idx = sel[0] if sel else 0
        pdf_path = self.pdf_files[idx]
        try:
            reader = PdfReader(str(pdf_path))
            txt = f"File: {pdf_path.name}\nPages: {len(reader.pages)}\nSize: {pdf_path.stat().st_size/1024:.1f} KB"
            messagebox.showinfo("اطلاعات PDF", txt)
        except Exception as e:
            messagebox.showerror("خطا", str(e))

def main():
    root = tk.Tk()
    app = PDFToolkit(root)
    root.mainloop()

if __name__ == "__main__":
    main()