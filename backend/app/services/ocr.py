"""OCR with a graceful engine chain:

    MOCK ground truth (seeded docs, MOCK_MODE)  ->  PaddleOCR (en+hi)
        -> pytesseract (eng+hin)  ->  embedded PDF text layer  ->  blank page

Every path returns the same shape: tokens with normalized bounding boxes and a
per-token confidence, so downstream extraction and the UI overlay never care
which engine produced them. Nothing here may raise - failures degrade to the
next engine, and MOCK_MODE bypasses heavy engines entirely.
"""

import json
from pathlib import Path
from typing import Optional

from .. import config
from . import render

_ENGINE_STATE: dict = {"paddle": None, "paddle_failed": False,
                       "tesseract_failed": False}


# --------------------------------------------------------------------- ground truth
def load_ground_truth(doc_id: int) -> Optional[dict]:
    p = config.MOCK_OCR_DIR / f"doc_{doc_id}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# ------------------------------------------------------------------ real engines
def _paddle():
    """Lazy PaddleOCR init; heavy, so only used when MOCK_MODE=False."""
    if _ENGINE_STATE["paddle_failed"]:
        return None
    if _ENGINE_STATE["paddle"] is not None:
        return _ENGINE_STATE["paddle"]
    try:
        from paddleocr import PaddleOCR  # type: ignore

        _ENGINE_STATE["paddle"] = PaddleOCR(
            use_angle_cls=True, lang="en", show_log=False, use_gpu=False
        )
    except Exception as exc:  # install failed / model download failed
        print(f"[ocr] PaddleOCR unavailable: {exc}")
        _ENGINE_STATE["paddle_failed"] = True
        return None
    return _ENGINE_STATE["paddle"]


def _ocr_paddle(png_path: str) -> list[dict]:
    ocr = _paddle()
    if ocr is None:
        raise RuntimeError("paddle unavailable")
    from PIL import Image

    img = Image.open(png_path)
    w, h = img.size
    result = ocr.ocr(png_path, cls=True)
    tokens = []
    for line in result or []:
        for entry in line or []:
            box, (text, conf) = entry[0], entry[1]
            xs = [p[0] / w for p in box]
            ys = [p[1] / h for p in box]
            tokens.append(
                {
                    "text": text,
                    "box": [min(xs), min(ys), max(xs), max(ys)],
                    "conf": float(conf),
                }
            )
    return tokens


def _ocr_tesseract(png_path: str) -> list[dict]:
    if _ENGINE_STATE["tesseract_failed"]:
        raise RuntimeError("tesseract unavailable")
    try:
        import pytesseract  # type: ignore
        from PIL import Image
        from pytesseract import Output

        img = Image.open(png_path)
        w, h = img.size
        data = pytesseract.image_to_data(
            img, lang="eng+hin", output_type=Output.DICT
        )
        tokens = []
        for i, text in enumerate(data["text"]):
            text = (text or "").strip()
            conf = float(data["conf"][i])
            if not text or conf < 0:
                continue
            x, y, bw, bh = (
                data["left"][i],
                data["top"][i],
                data["width"][i],
                data["height"][i],
            )
            tokens.append(
                {
                    "text": text,
                    "box": [x / w, y / h, (x + bw) / w, (y + bh) / h],
                    "conf": conf / 100.0,
                }
            )
        return tokens
    except Exception as exc:
        print(f"[ocr] pytesseract unavailable: {exc}")
        _ENGINE_STATE["tesseract_failed"] = True
        raise


# ----------------------------------------------------------------------- driver
def ocr_page(doc_id: int, page_no: int, png_path: str, stored_path: str) -> dict:
    """Returns {tokens, engine, avg_conf}. Never raises."""
    tokens: list[dict] = []
    engine = "none"

    # 1) Seeded ground truth (used in MOCK_MODE and as demo safety net)
    gt = load_ground_truth(doc_id)
    if gt and (config.MOCK_MODE or not _has_real_engine()):
        for page in gt.get("pages", []):
            if page.get("page_no") == page_no:
                tokens = page.get("tokens", [])
                engine = "mock-gt"
                break

    # 2) Real engines (only when MOCK_MODE=False)
    if engine == "none" and not config.MOCK_MODE:
        for fn, name in ((_ocr_paddle, "paddleocr"), (_ocr_tesseract, "tesseract")):
            try:
                tokens = fn(png_path)
                engine = name
                break
            except Exception:
                continue

    # 3) Embedded PDF text layer - free, deterministic, box-accurate
    if engine == "none":
        tokens = render.text_layer_words(stored_path, page_no)
        engine = "pdf-text-layer" if tokens else "none"

    # 4) Blank / unreadable page
    if not tokens:
        engine = engine if engine != "none" else "none"
        avg = 0.15 if engine == "none" else 0.99
        return {"tokens": [], "engine": engine, "avg_conf": avg}

    avg = sum(t.get("conf", 0.9) for t in tokens) / max(1, len(tokens))
    return {"tokens": tokens, "engine": engine, "avg_conf": round(avg, 4)}


def _has_real_engine() -> bool:
    if not _ENGINE_STATE["paddle_failed"]:
        try:
            import paddleocr  # noqa: F401

            return True
        except Exception:
            _ENGINE_STATE["paddle_failed"] = True
    if not _ENGINE_STATE["tesseract_failed"]:
        try:
            import pytesseract  # noqa: F401

            return True
        except Exception:
            _ENGINE_STATE["tesseract_failed"] = True
    return False


def engine_report() -> dict:
    return {
        "mock_mode": config.MOCK_MODE,
        "paddle_available": not _ENGINE_STATE["paddle_failed"],
        "tesseract_available": not _ENGINE_STATE["tesseract_failed"],
    }
