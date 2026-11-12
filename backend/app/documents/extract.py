"""Raw content extraction: PDF text layer (pypdf, layout mode) + metadata + per-glyph-run fonts,
or OCR for images / image-only PDFs."""
from __future__ import annotations

import contextlib
import io
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from app.documents import ocr

AMOUNT_TOKEN = re.compile(r"(?<![\d,])\d{1,3}(?:,\d{2,3})*\.\d{2}(?!\d)")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp")


@dataclass
class RawContent:
    text: str
    mime_type: str
    pages: int = 1
    source: str = "text"          # "text" | "ocr" | "none"
    engine: str = "pdf-text"
    confidence: float = 0.99
    metadata: dict[str, Any] = field(default_factory=dict)
    amount_fonts: list[tuple[str, str]] = field(default_factory=list)  # (amount token, font family)
    notes: list[str] = field(default_factory=list)


def sniff_mime(filename: str, data: bytes) -> str:
    if data[:5] == b"%PDF-":
        return "application/pdf"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    low = filename.lower()
    if low.endswith(".pdf"):
        return "application/pdf"
    if low.endswith(IMAGE_EXT):
        return "image/" + low.rsplit(".", 1)[-1].replace("jpg", "jpeg")
    return "application/octet-stream"


def parse_pdf_date(v: Any) -> datetime | None:
    """``D:20261106224103+05'30'`` -> aware datetime."""
    if v is None:
        return None
    s = str(v).strip()
    m = re.match(r"D?:?(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?([Zz+\-])?(\d{2})?'?(\d{2})?", s)
    if not m:
        return None
    y = int(m.group(1))
    mo, d, hh, mi, ss = (int(m.group(i) or default) for i, default in ((2, 1), (3, 1), (4, 0), (5, 0), (6, 0)))
    tz = timezone.utc
    if m.group(7) in ("+", "-") and m.group(8):
        off = timedelta(hours=int(m.group(8)), minutes=int(m.group(9) or 0))
        tz = timezone(off if m.group(7) == "+" else -off)
    try:
        return datetime(y, mo, d, hh, mi, ss, tzinfo=tz)
    except ValueError:
        return None


def font_family(base_font: str) -> str:
    """'/ABCDEF+Helvetica-Bold' -> 'helvetica'; 'Times-Roman' -> 'times'."""
    name = base_font.lstrip("/")
    if "+" in name[:8]:
        name = name.split("+", 1)[1]
    name = re.split(r"[-,]", name)[0].lower()
    name = re.sub(r"(mt|ps|psmt|bold|italic|oblique|regular|roman)$", "", name)
    aliases = {"arial": "helvetica", "arialmt": "helvetica", "timesnewroman": "times"}
    return aliases.get(name, name)


def extract_pdf(data: bytes) -> RawContent:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:
        return RawContent(text="", mime_type="application/pdf", source="none", engine="none", confidence=0.0,
                          notes=[f"PDF could not be opened: {type(exc).__name__}"])
    info: dict[str, Any] = dict(reader.metadata or {})
    meta: dict[str, Any] = {
        "producer": str(info.get("/Producer", "") or ""),
        "creator": str(info.get("/Creator", "") or ""),
        "creation_date": None, "mod_date": None,
    }
    cd, md = parse_pdf_date(info.get("/CreationDate")), parse_pdf_date(info.get("/ModDate"))
    meta["creation_date"] = cd.isoformat() if cd else None
    meta["mod_date"] = md.isoformat() if md else None

    texts: list[str] = []
    amount_fonts: list[tuple[str, str]] = []
    fonts: set[str] = set()
    run_fonts: dict[str, int] = {}

    def visitor(text: str, cm: Any, tm: Any, font_dict: Any, font_size: Any) -> None:
        if not font_dict or not text:
            return
        fam = font_family(str(font_dict.get("/BaseFont", "")))
        fonts.add(fam)
        if text.strip():
            run_fonts[fam] = run_fonts.get(fam, 0) + 1
        for tok in AMOUNT_TOKEN.findall(text):
            amount_fonts.append((tok, fam))

    for page in reader.pages:
        try:
            texts.append(page.extract_text(extraction_mode="layout") or "")
        except Exception:
            texts.append(page.extract_text() or "")
        with contextlib.suppress(Exception):
            page.extract_text(visitor_text=visitor)
    text = "\n".join(texts)
    meta["fonts"] = sorted(fonts)
    meta["font_runs"] = run_fonts
    raw = RawContent(text=text, mime_type="application/pdf", pages=len(reader.pages), metadata=meta,
                     amount_fonts=amount_fonts)
    if len(text.strip()) < 30:
        # image-only (scanned) PDF: OCR embedded page images
        parts, confs, engine = [], [], "none"
        for page in reader.pages:
            try:
                for img in page.images:
                    res = ocr.ocr_image(img.data)
                    engine = res.engine
                    parts.append(res.text)
                    confs.append(res.confidence)
                    raw.notes.extend(res.notes)
            except Exception as exc:
                raw.notes.append(f"Could not read page images: {type(exc).__name__}")
        raw.text = "\n".join(parts)
        raw.source = "ocr" if raw.text.strip() else "none"
        raw.engine = engine
        raw.confidence = sum(confs) / len(confs) if confs else 0.0
    return raw


def extract_image(data: bytes, mime: str) -> RawContent:
    meta: dict[str, Any] = {}
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as im:
            meta = {"width": im.width, "height": im.height, "image_mode": im.mode}
            software = im.info.get("Software") or im.info.get("software")
            if software:
                meta["producer"] = str(software)
    except Exception as exc:
        return RawContent(text="", mime_type=mime, source="none", engine="none", confidence=0.0,
                          notes=[f"Image could not be decoded: {type(exc).__name__}"])
    res = ocr.ocr_image(data)
    return RawContent(text=res.text, mime_type=mime, source="ocr" if res.text.strip() else "none",
                      engine=res.engine, confidence=res.confidence, metadata=meta, notes=list(res.notes))


def extract(filename: str, data: bytes) -> RawContent:
    mime = sniff_mime(filename, data)
    if mime == "application/pdf":
        return extract_pdf(data)
    if mime.startswith("image/"):
        return extract_image(data, mime)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = ""
    return RawContent(text=text, mime_type=mime, source="text" if text else "none",
                      engine="plain-text" if text else "none")
