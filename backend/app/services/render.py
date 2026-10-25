"""Render uploaded PDFs/images to page PNGs used by the document viewer
and by the ELA / pHash analysis. PDF rendering uses PyMuPDF (fitz); if it is
unavailable we degrade to a blank page rather than crash (demo safeguard)."""

from pathlib import Path

from PIL import Image

from .. import config

try:  # PyMuPDF - no external binaries needed
    import pymupdf as fitz  # type: ignore
except Exception:  # pragma: no cover
    try:
        import fitz  # type: ignore  # older package name
    except Exception:
        fitz = None

PAGE_DPI = 110


def render_document(stored_path: str, mime: str, doc_id: int) -> list[dict]:
    """Returns [{page_no, png_path, width, height}] and persists page PNGs."""
    out_dir = config.PAGE_DIR / str(doc_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    is_pdf = "pdf" in (mime or "").lower() or stored_path.lower().endswith(".pdf")

    if is_pdf and fitz is not None:
        pages = []
        with fitz.open(stored_path) as doc:
            for i, page in enumerate(doc, start=1):
                pix = page.get_pixmap(dpi=PAGE_DPI)
                png_path = out_dir / f"page_{i}.png"
                pix.save(str(png_path))
                pages.append(
                    {
                        "page_no": i,
                        "png_path": str(png_path),
                        "width": pix.width,
                        "height": pix.height,
                    }
                )
        return pages or _blank_page(out_dir)

    if is_pdf and fitz is None:
        return _blank_page(out_dir)

    # Plain image upload
    try:
        img = Image.open(stored_path).convert("RGB")
    except Exception:
        return _blank_page(out_dir)
    png_path = out_dir / "page_1.png"
    img.save(png_path, "PNG")
    return [
        {
            "page_no": 1,
            "png_path": str(png_path),
            "width": img.width,
            "height": img.height,
        }
    ]


def _blank_page(out_dir: Path) -> list[dict]:
    img = Image.new("RGB", (874, 1240), "white")
    png_path = out_dir / "page_1.png"
    img.save(png_path, "PNG")
    return [{"page_no": 1, "png_path": str(png_path), "width": 874, "height": 1240}]


def page_png(doc_id: int, page_no: int) -> Path | None:
    p = config.PAGE_DIR / str(doc_id) / f"page_{page_no}.png"
    return p if p.exists() else None


def page_count_of(stored_path: str, mime: str) -> int:
    is_pdf = "pdf" in (mime or "").lower() or stored_path.lower().endswith(".pdf")
    if is_pdf and fitz is not None:
        try:
            with fitz.open(stored_path) as doc:
                return max(1, doc.page_count)
        except Exception:
            return 1
    return 1


def text_layer_words(stored_path: str, page_no: int) -> list[dict]:
    """Extract embedded PDF text with real word boxes (no OCR engine needed).
    Used as a graceful fallback when OCR engines are unavailable."""
    if fitz is None or not stored_path.lower().endswith(".pdf"):
        return []
    try:
        with fitz.open(stored_path) as doc:
            if page_no - 1 >= doc.page_count:
                return []
            page = doc[page_no - 1]
            rect = page.rect
            words = []
            for x0, y0, x1, y1, text, *_ in page.get_text("words"):
                words.append(
                    {
                        "text": text,
                        "box": [
                            x0 / rect.width,
                            y0 / rect.height,
                            x1 / rect.width,
                            y1 / rect.height,
                        ],
                        "conf": 0.99,
                    }
                )
            return words
    except Exception:
        return []
