"""Optional, lazily-loaded OCR for scanned documents (PNG/JPG, image-only PDFs).

Engines (select with env ``OCR_ENGINE``; default ``auto``):
  * ``rapidocr``  - rapidocr-onnxruntime: PaddleOCR (PP-OCR) detection + recognition models run on
                    ONNX Runtime, CPU-only, ~15 MB. Reported as ``rapidocr(paddleocr-onnx)``.
  * ``tesseract`` - pytesseract + a system tesseract binary (fallback).
  * ``doctr``     - python-doctr (PyTorch). Heavy; optional, lazily imported only when requested.
  * ``none``      - OCR disabled; image documents are flagged DOC_UNREADABLE.
``auto`` tries rapidocr, then tesseract, else none. Nothing is imported at module import time,
so the API boots without any OCR dependency installed.

Results are cached by image sha256 in memory and on disk (``OCR_CACHE_DIR``, default
``backend/.data/ocr_cache``), images are downscaled to ``OCR_MAX_SIDE`` (1600 px) on the long side,
and the rapidocr text-angle classifier is skipped (scans are upright).

All engines return text rebuilt into *layout lines*: words on the same visual row are joined and
padded with spaces proportional to their x position (after de-skewing), so the same regex parsers
work on PDF text layers and on OCR output.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any

RAPIDOCR_NAME = "rapidocr(paddleocr-onnx)"


@dataclass
class OcrResult:
    text: str
    engine: str
    confidence: float = 0.0
    boxes: int = 0
    notes: list[str] = field(default_factory=list)


_lock = threading.Lock()
_engine: tuple[str, Callable[[bytes], list[tuple[list[list[float]], str, float]]]] | None = None
_engine_tried = False
_cache: OrderedDict[str, OcrResult] = OrderedDict()
_CACHE_MAX = 256
MAX_SIDE = int(os.environ.get("OCR_MAX_SIDE", "1600"))
CACHE_VERSION = "v1"


def _disk_cache_dir() -> Path | None:
    """``OCR_CACHE_DIR`` (default ``backend/.data/ocr_cache``); ``OCR_CACHE_DIR=off`` disables it."""
    raw = os.environ.get("OCR_CACHE_DIR", "")
    if raw.lower() in ("off", "none", "0"):
        return None
    return Path(raw) if raw else Path(__file__).resolve().parents[2] / ".data" / "ocr_cache"


def _disk_get(key: str) -> OcrResult | None:
    d = _disk_cache_dir()
    if d is None:
        return None
    try:
        data = json.loads((d / f"{key}.json").read_text())
        return OcrResult(text=data["text"], engine=data["engine"], confidence=float(data["confidence"]),
                         boxes=int(data["boxes"]), notes=["ocr-cache:disk"])
    except (OSError, ValueError, KeyError):
        return None


def _disk_put(key: str, res: OcrResult) -> None:
    d = _disk_cache_dir()
    if d is None:
        return
    try:
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / f"{key}.tmp{os.getpid()}"
        tmp.write_text(json.dumps({"text": res.text, "engine": res.engine, "confidence": res.confidence,
                                   "boxes": res.boxes}))
        tmp.replace(d / f"{key}.json")
    except OSError:
        pass


def _load_rapidocr() -> Callable[[bytes], list[tuple[list[list[float]], str, float]]]:
    from rapidocr_onnxruntime import RapidOCR  # type: ignore[import-untyped]

    # one shared instance (model load ~0.3 s); documents are upright scans, so the 0/180-degree
    # text-angle classifier is not loaded at all
    eng = RapidOCR(use_angle_cls=False)

    def run(data: bytes) -> list[tuple[list[list[float]], str, float]]:
        res, _ = eng(_prepare(data))
        return [(box, txt, float(score)) for box, txt, score in (res or [])]

    return run


def _prepare(data: bytes) -> Any:
    """Decode to an RGB ndarray, downscaled so the long side is at most ``OCR_MAX_SIDE`` px (default 1600)."""
    import numpy as np
    from PIL import Image

    img = Image.open(io.BytesIO(data)).convert("RGB")
    if max(img.size) > MAX_SIDE:
        scale = MAX_SIDE / max(img.size)
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    return np.asarray(img)[:, :, ::-1].copy()  # RGB -> BGR (OpenCV order)


def _load_tesseract() -> Callable[[bytes], list[tuple[list[list[float]], str, float]]]:
    import pytesseract  # type: ignore[import-untyped]
    from PIL import Image

    pytesseract.get_tesseract_version()

    def run(data: bytes) -> list[tuple[list[list[float]], str, float]]:
        img = Image.open(io.BytesIO(data)).convert("L")
        d = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        out = []
        for i, txt in enumerate(d["text"]):
            if not str(txt).strip():
                continue
            x, y, w, h = d["left"][i], d["top"][i], d["width"][i], d["height"][i]
            conf = max(float(d["conf"][i]), 0.0) / 100.0
            out.append(([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], str(txt), conf))
        return out

    return run


def _load_doctr() -> Callable[[bytes], list[tuple[list[list[float]], str, float]]]:
    from doctr.io import DocumentFile  # type: ignore[import-not-found]
    from doctr.models import ocr_predictor  # type: ignore[import-not-found]

    model = ocr_predictor(pretrained=True)

    def run(data: bytes) -> list[tuple[list[list[float]], str, float]]:
        doc = DocumentFile.from_images([data])
        page = model(doc).pages[0]
        h, w = page.dimensions
        out = []
        for block in page.blocks:
            for line in block.lines:
                for word in line.words:
                    (x0, y0), (x1, y1) = word.geometry
                    out.append(([[x0 * w, y0 * h], [x1 * w, y0 * h], [x1 * w, y1 * h], [x0 * w, y1 * h]],
                                word.value, float(word.confidence)))
        return out

    return run


_LOADERS: dict[str, tuple[str, Callable[[], Callable[[bytes], list[tuple[list[list[float]], str, float]]]]]] = {
    "rapidocr": (RAPIDOCR_NAME, _load_rapidocr),
    "tesseract": ("tesseract", _load_tesseract),
    "doctr": ("doctr", _load_doctr),
}


def _get_engine() -> tuple[str, Callable[[bytes], list[tuple[list[list[float]], str, float]]]] | None:
    global _engine, _engine_tried
    with _lock:
        if _engine_tried:
            return _engine
        _engine_tried = True
        choice = os.environ.get("OCR_ENGINE", "auto").strip().lower()
        order = ["rapidocr", "tesseract"] if choice in ("", "auto") else [choice]
        for key in order:
            if key not in _LOADERS:
                continue
            name, loader = _LOADERS[key]
            try:
                _engine = (name, loader())
                break
            except Exception:  # missing package / binary / model
                continue
        return _engine


def engine_name() -> str:
    """Name of the OCR engine that will be used (loads it on first call), or ``none``."""
    eng = _get_engine()
    return eng[0] if eng else "none"


def reset_engine() -> None:
    """Forget the loaded engine (tests switch ``OCR_ENGINE``)."""
    global _engine, _engine_tried
    with _lock:
        _engine, _engine_tried = None, False
        _cache.clear()


def layout_lines(items: list[tuple[list[list[float]], str, float]]) -> str:
    """Rebuild reading-order text lines from word/line boxes, de-skewing first."""
    if not items:
        return ""
    angles = []
    for box, _txt, _ in items:
        (x0, y0), (x1, y1) = box[0], box[1]
        if x1 - x0 > 60:
            angles.append(math.atan2(y1 - y0, x1 - x0))
    ang = median(angles) if angles else 0.0
    ca, sa = math.cos(-ang), math.sin(-ang)
    recs: list[dict[str, Any]] = []
    for box, txt, _conf in items:
        pts = [(p[0] * ca - p[1] * sa, p[0] * sa + p[1] * ca) for p in box]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        recs.append({"x0": min(xs), "x1": max(xs), "yc": (min(ys) + max(ys)) / 2, "h": max(ys) - min(ys),
                     "t": txt.strip()})
    hs = [r["h"] for r in recs if r["h"] > 0]
    med_h = median(hs) if hs else 20.0
    widths = [(r["x1"] - r["x0"]) / max(len(r["t"]), 1) for r in recs if r["t"]]
    char_w = max(median(widths) if widths else 10.0, 1.0)
    min_x = min(r["x0"] for r in recs)
    recs.sort(key=lambda r: r["yc"])
    rows: list[list[dict[str, Any]]] = []
    for r in recs:
        if rows and abs(r["yc"] - median(x["yc"] for x in rows[-1])) < 0.5 * max(med_h, min(r["h"], 2 * med_h)):
            rows[-1].append(r)
        else:
            rows.append([r])
    out = []
    for row in rows:
        row.sort(key=lambda r: r["x0"])
        line = ""
        for r in row:
            col = int((r["x0"] - min_x) / char_w)
            pad = max(col - len(line), 2 if line else 0)
            line += " " * pad + r["t"]
        out.append(line.rstrip())
    return "\n".join(out)


def ocr_image(data: bytes) -> OcrResult:
    """OCR an image (bytes of PNG/JPG). Never raises: failures yield empty text + note."""
    eng = _get_engine()
    if eng is None:
        return OcrResult(text="", engine="none", notes=["No OCR engine available (pip install rapidocr-onnxruntime)"])
    name, run = eng
    key = f"{hashlib.sha256(data).hexdigest()}-{name.split('(')[0]}-{MAX_SIDE}-{CACHE_VERSION}"
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    cached = _disk_get(key)
    if cached is not None:
        with _lock:
            _cache[key] = cached
        return cached
    try:
        items = run(data)
    except Exception as exc:  # corrupt image etc.
        return OcrResult(text="", engine=name, notes=[f"OCR failed: {type(exc).__name__}"])
    conf = sum(i[2] for i in items) / len(items) if items else 0.0
    res = OcrResult(text=layout_lines(items), engine=name, confidence=round(conf, 3), boxes=len(items))
    with _lock:
        _cache[key] = res
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)
    if res.text:
        _disk_put(key, res)
    return res


def warm(images: list[bytes], workers: int = 3) -> None:
    """OCR several images concurrently (ONNX Runtime releases the GIL) to fill the caches."""
    if len(images) < 2 or _get_engine() is None:
        for img in images:
            ocr_image(img)
        return
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=min(workers, len(images))) as pool:
        list(pool.map(ocr_image, images))
