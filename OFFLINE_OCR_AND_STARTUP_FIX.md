# Offline OCR startup crash & monitor enumeration fix (v2.2.2)

This note records two problems seen when launching the latest `fastshot` on a
locked-down / offline corporate (intranet) Windows machine, their root causes,
the permanent code fix shipped in **v2.2.2**, and a manual workaround that
unblocks an already-installed build without upgrading.

## Symptoms

Running `fastshot` printed a monitor error and then crashed on startup:

```
ERROR getting monitors via Win32 API: module 'ctypes' has no attribute 'c_ulongptr'
...
Config file path: ...\site-packages\fastshot\config.ini
...
[RapidOCR] Initiating download: https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.8.0/onnx/PP-OCRv4/cls/ch_ppocr_mobile_v2.0_cls_mobile.onnx
[RapidOCR] Download failed: ... ([Errno 11001] getaddrinfo failed)
...
requests.exceptions.ConnectionError: HTTPSConnectionPool(host='www.modelscope.cn', port=443):
    Failed to resolve 'www.modelscope.cn' ([Errno 11001] getaddrinfo failed)
...
  File ".../fastshot/main.py", line 144, in __init__
    self.ocr_engine = PluginOCR()
  File ".../fastshot/plugin_ocr.py", line 16, in __init__
    self.ocr_engine = RapidOCR(params={...})
rapidocr.utils.download_file.DownloadFileException:
    Failed to download https://www.modelscope.cn/.../ch_ppocr_mobile_v2.0_cls_mobile.onnx
```

These are **two independent problems**.

## Problem 1 (fatal) — OCR tries to download a model at startup

`fastshot` bundles the OCR **detection** and **recognition** models under
`fastshot/resources/` and passes their local paths to RapidOCR. It did **not**
bundle or configure the **angle-classifier (cls)** model. RapidOCR therefore
treated cls as "not provided" and tried to download
`ch_ppocr_mobile_v2.0_cls_mobile.onnx` from `modelscope.cn` during
`RapidOCR(...)` construction. On an offline / intranet machine DNS resolution
fails, RapidOCR raises `DownloadFileException`, and because the OCR engine was
created unconditionally in `SnipasteApp.__init__`, the **whole app crashed**.

Important version nuance:

- **RapidOCR 3.9.x** builds the classifier eagerly in `RapidOCR.__init__`
  (`_initialize` → `TextClassifier(cfg.Cls)`) and does **not** honour the
  `Global.use_cls` flag. So "just disable cls" does **not** stop the download on
  that version.
- Newer RapidOCR (e.g. 3.10.x) loads cls lazily and does honour `use_cls`.

The only fix that works across both is to give cls an explicit **local**
`model_path`, exactly like det and rec.

## Problem 2 (non-fatal) — monitor enumeration used a non-existent ctypes type

`fastshot/app_platform/windows.py` built the `EnumDisplayMonitors` callback with
`ctypes.c_ulongptr`, which **is not a real ctypes type**, and used 32-bit
`ctypes.c_ulong` for pointer-sized handles. The branch always raised
`AttributeError` (hence the printed `ERROR getting monitors via Win32 API`) and
silently fell back to `screeninfo`. On 64-bit Windows the handles would also
have been truncated. This did not crash the app but meant the Win32 multi-monitor
path never actually ran.

## The permanent fix (v2.2.2)

1. **Bundle the cls model** `fastshot/resources/ch_ppocr_mobile_v2.0_cls_mobile.onnx`
   and set `Cls.model_path` to it in `fastshot/plugin_ocr.py`, next to the
   existing `Det.model_path` / `Rec.model_path`. All three OCR stages now run
   fully offline from bundled models — **no network access at startup**.
   - The bundled file's SHA-256 is
     `e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c`,
     which matches the hash RapidOCR expects for this model.
   - `MANIFEST.in` (`recursive-include fastshot/resources *`) and `setup.py`
     (`package_data: resources/*.onnx`) already package every `resources/*.onnx`,
     so no packaging change was needed.
2. **Make OCR init non-fatal**: `PluginOCR()` in `fastshot/main.py` is wrapped in
   `try/except`; on any OCR/model/engine failure it logs a warning and sets
   `self.ocr_engine = None`. Callers already null-guard it, so the app always
   launches even if OCR cannot start.
3. **Fix the monitor path**: use `ctypes.c_void_p` for HMONITOR / HDC / LPRECT /
   LPARAM and pin `argtypes` on `EnumDisplayMonitors` and `GetMonitorInfoW` so
   handles are not truncated on 64-bit Windows. The `screeninfo` fallback is kept.

Commit: `Fix offline OCR startup crash and monitor enumeration; v2.2.2`.

## Manual workaround (no upgrade needed)

If you are stuck on an already-installed build (e.g. v2.2.1) on an offline
machine and cannot upgrade yet, you only need to place **one file** — the cls
model — where RapidOCR looks for it. (det + rec are already bundled by fastshot.)

1. On a machine **with** internet, download the exact file (use the version in
   your own error log so the SHA-256 check passes; the URL below is for the
   rapidocr 3.8.0/3.9.x model set):

   ```
   https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.8.0/onnx/PP-OCRv4/cls/ch_ppocr_mobile_v2.0_cls_mobile.onnx
   ```

2. Copy it onto the offline machine at (create the `models` folder if absent;
   do not rename the file):

   ```
   <python-user-site>\site-packages\rapidocr\models\ch_ppocr_mobile_v2.0_cls_mobile.onnx
   ```

   e.g. `C:\Users\<you>\AppData\Roaming\Python\Python3xx\site-packages\rapidocr\models\...`

RapidOCR skips the download when the file already exists **and** its SHA-256
matches the expected value (verified in `rapidocr/utils/download_file.py`
`_should_skip_download`). The expected hash is listed in
`site-packages/rapidocr/default_models.yaml` under the `cls` entry. Downloading
from the official URL above guarantees a match.

## How to verify

- The det model loads locally (log: `Using ...\fastshot\resources\ch_PP-OCRv5_mobile_det.onnx`).
- With v2.2.2 or the manual workaround in place, launch shows **no**
  `Initiating download` / `getaddrinfo failed` lines, and the app starts.
- OCR (the screenshot → text hotkey) copies recognized text to the clipboard.

## Related

The GitHub Actions release build was also fixed earlier (v2.2.1): `config.ini`
is intentionally untracked (it can hold local secrets), so the publish workflow
now generates a secret-free `config.ini` from `config.ini.example` before
building. See `GITHUB_ACTIONS_BUILD_FIX.md` if present, or the
`.github/workflows/python-publish.yml` "Prepare config.ini from template" step.
