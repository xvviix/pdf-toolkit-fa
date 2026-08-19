# 🐛 گزارش باگ‌ها — PDF Toolkit v12 (نسخه فارسی)

## خلاصه

| # | نوع | شدت | شرح |
|---|------|------|------|
| 1 | `Importخطا` به‌جای `ImportError` | 🔴 بحرانی | کرش هنگام خطای import |
| 2 | `Valueخطا` به‌جای `ValueError` | 🔴 بحرانی | کرش هنگام ورودی نامعتبر |
| 3 | `OSخطا` به‌جای `OSError` | 🔴 بحرانی | کرش هنگام حذف فایل موقت |
| 4 | `reader.صفحه` به‌جای `reader.pages` | 🔴 بحرانی | کرش در تمام عملیات PDF |
| 5 | `status` تعریف‌نشده در `_finish_preview` | 🟡 متوسط | کرش احتمالی در پیش‌نمایش |
| 6 | CI با Python 3.9 ولی `run.bat` نیاز به 3.10+ | 🟡 متوسط | ناسازگاری CI |
| 7 | `_best_persian_font()` ساخت Tk root اضافی | 🟠 کم | مشکل احتمالی در macOS |
| 8 | `PdfReader = PdfReader` انتساب بیهوده | 🟠 کم | کد گیج‌کننده |

---

## 🔴 باگ #1: `Importخطا` به‌جای `ImportError`

**خطوط:** 88, 1326, 1388, 1439

**مشکل:** کلمه فارسی «خطا» جایگزین `Error` شده. پایتون این رو به‌عنوان یک exception class نمی‌شناسه و `NameError` می‌ده.

**تأثیر:** هر بار که `import` ناموفق باشه، برنامه به‌جای مدیریت خطا، کرش می‌کنه.

```python
# ❌ کد فعلی
def _lazy_import(name):
    try:
        return __import__(name)
    except Importخطا:       # ← NameError!
        return None

# ✅ اصلاح
def _lazy_import(name):
    try:
        return __import__(name)
    except ImportError:
        return None
```

**اثبات:**
```
>>> _lazy_import('nonexistent_module_xyz')
NameError: name 'Importخطا' is not defined
```

---

## 🔴 باگ #2: `Valueخطا` به‌جای `ValueError`

**خطوط:** 195, 202

**مشکل:** در `parse_page_ranges()` — هر ورودی نامعتبر (مثل `"abc"`) باعث کرش می‌شه.

```python
# ❌ کد فعلی
            except Valueخطا:
                continue

# ✅ اصلاح
            except ValueError:
                continue
```

**اثبات:**
```
>>> parse_page_ranges(10, "abc-def")
NameError: name 'Valueخطا' is not defined
```

---

## 🔴 باگ #3: `OSخطا` به‌جای `OSError`

**خطوط:** 1369, 1480

**مشکل:** هنگام حذف فایل موقت (temp)، اگر حذف ناموفق باشه، برنامه کرش می‌کنه.

```python
# ❌ کد فعلی
                try:
                    os.unlink(tmp_name)
                except OSخطا:
                    pass

# ✅ اصلاح
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
```

---

## 🔴 باگ #4: `reader.صفحه` به‌جای `reader.pages`

**خطوط:** 814, 927, 937, 950, 967, 985, 1531, 1533, 1591, 1592, 1610, 1613, 1630

**مشکل:** کتابخانه `pypdf` از `PdfReader.pages` استفاده می‌کنه، نه `PdfReader.صفحه`. این باگ باعث می‌شه **تمام عملیات‌های اصلی** (تقسیم، ادغام، تبدیل به تصویر، چرخش، استخراج متن، اطلاعات PDF) با `AttributeError` کرش کنن.

**تأثیر:** هیچ‌کدام از عملیات‌های PDF کار نمی‌کنن!

```python
# ❌ کد فعلی
reader = PdfReader(str(pdf_path))
total_صفحه = len(reader.صفحه)     # ← AttributeError!
writer.add_page(reader.صفحه[idx])  # ← AttributeError!

# ✅ اصلاح
reader = PdfReader(str(pdf_path))
total_صفحه = len(reader.pages)
writer.add_page(reader.pages[idx])
```

**اثبات:**
```
>>> from pypdf import PdfReader
>>> hasattr(PdfReader, 'صفحه')
False
>>> hasattr(PdfReader, 'pages')
True
```

---

## 🟡 باگ #5: متغیر `status` تعریف‌نشده در `_finish_preview`

**خط:** ~1075

**مشکل:** در حلقه `for` تابع `_finish_preview`، شاخه `else` از `status` استفاده می‌کنه که فقط در شاخه `if` تعریف شده:

```python
for i, (src_name, person) in enumerate(results):
    if person and person != "⚠ OCR engine not installed":
        status, score, issues = self._validate_name(person)
        ...
    else:
        bad_count += 1
        ...
    # ← اگر اولین iteration به else بره، status تعریف نشده!
    self.preview_listbox.itemconfig(i,
        fg=self._name_status_color(
            status if person ... else "bad"  # ← NameError احتمالی
        ))
```

**اصلاح:** مقداردهی اولیه `status` قبل از `if`:
```python
for i, (src_name, person) in enumerate(results):
    status = "bad"  # ← پیش‌فرض
    if person and person != "⚠ OCR engine not installed":
        status, score, issues = self._validate_name(person)
        ...
```

---

## 🟡 باگ #6: ناسازگاری CI و `run.bat`

**مشکل:** CI از Python 3.9 تست می‌کنه، ولی `run.bat` صراحتاً Python 3.10 تا 3.13 رو قبول می‌کنه:

```yaml
# ci.yml
matrix:
  python-version: ["3.9", "3.10", "3.11", "3.12"]  # ← 3.9 نباید باشه
```

```bat
REM run.bat
python -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,13) else 1)"
```

**اصلاح:** حذف `"3.9"` از CI matrix و اضافه کردن `"3.13"`.

---

## 🟠 باگ #7: `_best_persian_font()` — ساخت Tk root اضافی

**مشکل:** این تابع در زمان `import` (module level) اجرا می‌شه و یک `Tk()` root می‌سازه و بعد `destroy()` می‌کنه. بعداً برنامه اصلی یک `Tk()` دیگه می‌سازه. روی بعضی پلتفرم‌ها (مخصوصاً macOS) ساخت و تخریب Tk root قبل از root اصلی مشکل‌ساز می‌شه.

**اصلاح پیشنهادی:** فونت رو lazy بگیر (داخل `__init__`) یا از `tk._default_root` استفاده کن.

---

## 🟠 باگ #8: `PdfReader = PdfReader` — انتساب بیهوده

**خط:** ~98

```python
def ensure_pdf_libs():
    global PYPDF_AVAILABLE, PYMUPDF_AVAILABLE, PdfReader, PdfWriter, fitz
    if not PYPDF_AVAILABLE:
        try:
            from pypdf import PdfReader, PdfWriter as _PdfWriter
            PdfReader = PdfReader      # ← no-op!
            PdfWriter = _PdfWriter
```

**مشکل:** `global PdfReader` + `from pypdf import PdfReader` باعث می‌شه import مستقیماً global رو ست کنه. خط `PdfReader = PdfReader` بیهوده‌ست.

**اصلاح:** حذف خط اضافی یا استفاده از alias:
```python
from pypdf import PdfReader as _PR, PdfWriter as _PW
PdfReader = _PR
PdfWriter = _PW
```

---

## 📋 خلاصه تأثیر

| عملیات | وضعیت فعلی | علت |
|--------|-----------|------|
| تقسیم PDF | ❌ کرش | باگ #4 (`reader.صفحه`) |
| ادغام PDF | ❌ کرش | باگ #4 |
| PDF به تصویر | ❌ کرش | باگ #4 |
| تصاویر به PDF | ✅ کار می‌کنه | از Pillow استفاده می‌کنه |
| چرخش | ❌ کرش | باگ #4 |
| فشرده‌سازی | ❌ کرش | باگ #4 (از ابزار پیشرفته) |
| استخراج متن | ❌ کرش | باگ #4 |
| اطلاعات PDF | ❌ کرش | باگ #4 |
| OCR | ❌ کرش | باگ #1 + #3 + #4 |
| parse_page_ranges | ⚠️ کرش با ورودی بد | باگ #2 |

**نتیجه:** عملاً همه عملیات‌های PDF (به جز تصاویر به PDF) کرش می‌کنن.
