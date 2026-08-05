#!/usr/bin/env python3
"""Smoke tests for PDF Toolkit v12.

Runs without a display / without OCR models — validates the core logic
(page ranges, sanitizing, validation, name extraction, highlight cleanup,
duplicate names, UI construction with a mocked tkinter).
Run:  python test_smoke.py
"""
import sys
import types

# ───────────────────────────── mock tkinter ─────────────────────────────
tk_mod = types.ModuleType("tkinter")


class _Var:
    def __init__(self, value=None):
        self._v = value

    def get(self):
        return self._v

    def set(self, v):
        self._v = v


tk_mod.StringVar = _Var
tk_mod.IntVar = _Var
tk_mod.DoubleVar = _Var
tk_mod.BooleanVar = _Var


def _dummy(*a, **k):
    return None


class _Widget:
    def __init__(self, parent=None, **kw):
        self.parent = parent
        self.kw = kw
        self._text = kw.get("text", "")

    def pack(self, *a, **k):
        pass

    def pack_forget(self):
        pass

    def place(self, *a, **k):
        pass

    def config(self, **kw):
        if "text" in kw:
            self._text = kw["text"]
        self.kw.update(kw)

    def cget(self, k):
        return self.kw.get(k, self._text if k == "text" else "")

    def bind(self, *a, **k):
        pass

    def bind_all(self, *a, **k):
        pass

    def configure(self, **kw):
        if "text" in kw:
            self._text = kw["text"]
        self.kw.update(kw)

    def itemconfig(self, *a, **k):
        pass

    def destroy(self):
        pass

    def __getattr__(self, name):
        return _dummy


class _Frame(_Widget):
    pass


class _Label(_Widget):
    pass


class _Button(_Widget):
    pass


class _Entry(_Widget):
    pass


class _Listbox(_Widget):
    def __init__(self, parent=None, **kw):
        super().__init__(parent, **kw)
        self.items = []

    def delete(self, a, b=None):
        self.items = []

    def insert(self, idx, item):
        self.items.append(item)


class _Canvas(_Widget):
    pass


class _Radiobutton(_Widget):
    pass


class _Spinbox(_Widget):
    pass


class _Scale(_Widget):
    pass


class _Toplevel(_Widget):
    pass


class _Notebook(_Widget):
    def __init__(self, parent=None):
        self.parent = parent
        self._tabs = []

    def pack(self, *a, **k):
        pass

    def add(self, frame, **kw):
        self._tabs.append(kw.get("text", ""))

    def index(self, x):
        return 0

    def tab(self, i, k):
        return self._tabs[i] if i < len(self._tabs) else ""


tk_mod.Tk = lambda: _Frame()
tk_mod.Toplevel = _Toplevel
tk_mod.Frame = _Frame
tk_mod.Label = _Label
tk_mod.Button = _Button
tk_mod.Entry = _Entry
tk_mod.Listbox = _Listbox
tk_mod.Canvas = _Canvas
tk_mod.Radiobutton = _Radiobutton
tk_mod.Spinbox = _Spinbox
tk_mod.Scale = _Scale

ttk_mod = types.ModuleType("tkinter.ttk")


class _Style:
    def theme_use(self, *a):
        pass

    def configure(self, *a, **k):
        pass


class _Progressbar(_Widget):
    pass


class _Scrollbar(_Widget):
    pass


ttk_mod.Style = _Style
ttk_mod.Notebook = _Notebook
ttk_mod.Progressbar = _Progressbar
ttk_mod.Scrollbar = _Scrollbar
ttk_mod.Checkbutton = _Radiobutton

filedialog = types.ModuleType("tkinter.filedialog")
filedialog.askopenfilenames = lambda **k: ()
filedialog.askdirectory = lambda **k: ""

messagebox = types.ModuleType("tkinter.messagebox")
messagebox.showinfo = lambda *a: None
messagebox.showwarning = lambda *a: None
messagebox.showerror = lambda *a: None

tk_mod.filedialog = filedialog
tk_mod.messagebox = messagebox
tk_mod.ttk = ttk_mod

sys.modules["tkinter"] = tk_mod
sys.modules["tkinter.ttk"] = ttk_mod
sys.modules["tkinter.filedialog"] = filedialog
sys.modules["tkinter.messagebox"] = messagebox

# ───────────────────────────── import module ─────────────────────────────
import pdf_toolkit_v12 as m  # noqa: E402


class FakeRoot:
    def __init__(self):
        self._after_cb = []

    def after(self, ms, fn):
        self._after_cb.append(fn)
        return len(self._after_cb)

    def title(self, t):
        self._t = t

    def geometry(self, g):
        pass

    def minsize(self, a, b):
        pass

    def resizable(self, a, b):
        pass

    def configure(self, **k):
        pass

    def mainloop(self):
        pass


# ───────────────────────────── tests ─────────────────────────────
def test_parse_page_ranges():
    assert m.parse_page_ranges(10, "all") == list(range(10))
    assert m.parse_page_ranges(10, "1-3") == [0, 1, 2]
    assert m.parse_page_ranges(10, "1,3,5") == [0, 2, 4]
    assert m.parse_page_ranges(10, "8-") == [7, 8, 9]
    assert m.parse_page_ranges(10, "last-2") == [8, 9]


def test_sanitize_filename():
    sf = m.PDFToolkit._sanitize_filename
    assert "\\" not in sf("a\\b")
    assert "/" not in sf("a/b")
    assert len(sf("x" * 200)) <= 80


def test_validate_name():
    v = m.PDFToolkit._validate_name
    assert v("سهراب زارعی")[0] == "ok"
    assert v("")[0] == "bad"
    assert v("مامور ثبت")[0] == "bad"
    assert v("علی123")[0] == "suspect"
    assert v("سهراب ABC")[0] == "suspect"


def test_extract_person_name():
    lines = [
        {"y": 100, "text": "نام سهراب"},
        {"y": 150, "text": "نام خانوادگي زارعي"},
        {"y": 200, "text": "نام پدر حاجی خان"},
    ]
    first, family = m.PDFToolkit._extract_person_name(lines)
    assert first == "سهراب"
    assert "زارعی" in family or "زارعي" in family


def test_clean_highlight_text():
    c = m.PDFToolkit._clean_highlight_text
    assert c("نام: سهراب زارعی") == "سهراب زارعی"
    assert c("سهراب زارعی") == "سهراب زارعی"
    assert c("John Smith") == "John Smith"


def test_unique_name():
    used = set()
    assert m.PDFToolkit._unique_name("تک", used) == "تک"
    assert m.PDFToolkit._unique_name("تک", used) == "تک 2"
    assert m.PDFToolkit._unique_name("تک", used) == "تک 3"


def test_ui_builds():
    root = FakeRoot()
    app = m.PDFToolkit(root)
    # toggle naming modes
    app.split_naming.set("ocr")
    app._update_split_ui()
    app.split_naming.set("manual")
    app._update_split_ui()
    app.split_mode.set("every")
    app._update_split_ui()


def main():
    tests = [
        test_parse_page_ranges,
        test_sanitize_filename,
        test_validate_name,
        test_extract_person_name,
        test_clean_highlight_text,
        test_unique_name,
        test_ui_builds,
    ]
    passed = 0
    for t in tests:
        t()
        passed += 1
        print(f"  ✓ {t.__name__}")
    print(f"\n✅ All {passed} tests passed!")


if __name__ == "__main__":
    main()
