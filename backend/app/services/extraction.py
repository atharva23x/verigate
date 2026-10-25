"""Field extraction from OCR tokens.

Works identically over mock ground truth, PaddleOCR, tesseract or the PDF text
layer - it only sees tokens with boxes + confidence. Every extracted field keeps
its page number, bounding box and the mean confidence of the tokens it came
from, which is what the UI uses to draw the highlight overlay.
"""

import datetime as dt
import re

PATTERNS = {
    "aicte_id": r"AICTE-[A-Z]{2}\d{4}-\d{5}",
    "doc_number": r"(?:Doc|Licence|Certificate|Registration|Application)\s*"
    r"(?:No\.?|Number)\s*[:\-]?\s*([^\n\s][^\n]{3,23})",
    "qr_token": r"QR[:\s]+([A-Z0-9]{6,14})",
    "signature": r"SIGN[:\s]+([0-9a-f]{32,48})",
    "approved_intake": r"(?:Approved\s+Intake|intake\s+at\s+present|Total\s+Intake)"
    r"\s*[:\-]?\s*(\d{1,5})",
    "issue_date": r"(?:Date\s+of\s+Issue|Issued?\s+On|Dated)\s*[:\-]?\s*"
    r"(\d{2}[-/]\d{2}[-/]\d{4})",
    "expiry_date": r"(?:Valid\s+(?:up\s+to|upto|till|until)|Expir[ye](?:s|d)?\s+on)"
    r"\s*[:\-]?\s*(\d{2}[-/]\d{2}[-/]\d{4})",
    "issuing_authority": r"(?:Issuing\s+Authority|Authorized\s+Signatory)"
    r"\s*[:\-]?\s*([^\n]{4,70})",
    "institution_name": r"(?:Institution|College|Institute)\s*(?:Name)?\s*[:\-]\s*"
    r"([^\n]{4,90})",
}

DATE_FMT = "%d-%m-%Y"


def parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    value = value.strip().replace("/", "-")
    try:
        return dt.datetime.strptime(value, DATE_FMT).date()
    except ValueError:
        return None


def _union_box(tokens: list[dict]) -> list[float]:
    x0 = min(t["box"][0] for t in tokens)
    y0 = min(t["box"][1] for t in tokens)
    x1 = max(t["box"][2] for t in tokens)
    y1 = max(t["box"][3] for t in tokens)
    return [round(x0, 4), round(y0, 4), round(x1 - x0, 4), round(y1 - y0, 4)]


def _group_lines(tokens: list[dict]) -> list[list[dict]]:
    """Group tokens into visual lines by vertical centre, so regex matches
    cannot bleed across line boundaries ([^\\n] in patterns relies on this)."""
    for tok in tokens:
        tok["_yc"] = (tok["box"][1] + tok["box"][3]) / 2.0
    lines: list[list[dict]] = []
    for tok in sorted(tokens, key=lambda t: (t["_yc"], t["box"][0])):
        for ln in lines:
            if abs(ln[0]["_yc"] - tok["_yc"]) < 0.012:
                ln.append(tok)
                break
        else:
            lines.append([tok])
    for ln in lines:
        ln.sort(key=lambda t: t["box"][0])
    return lines


def extract_fields(pages: list[dict]) -> dict:
    """pages: [{page_no, tokens:[{text, box, conf}]}] -> {field: {value, conf, page_no, bbox}}"""
    fields: dict[str, dict] = {}

    for page in pages:
        tokens = [t for t in page.get("tokens", []) if t.get("text")]
        if not tokens:
            continue
        # Join tokens into visual lines; track each token's char span so a
        # regex match can be mapped back to the exact words (and boxes).
        lines = _group_lines(tokens)
        joined_lines: list[str] = []
        spans: list[tuple[int, int, dict]] = []  # start, end, token
        idx = 0
        for li, line in enumerate(lines):
            if li:
                idx += 1  # the "\n" separator
            for ti, tok in enumerate(line):
                text = str(tok["text"])
                if ti:
                    idx += 1  # the " " separator
                spans.append((idx, idx + len(text), tok))
                idx += len(text)
            joined_lines.append(" ".join(str(t["text"]) for t in line))
        joined = "\n".join(joined_lines)

        def tokens_for(m: re.Match) -> list[dict]:
            s, e = m.start(), m.end()
            return [t for (a, b, t) in spans if b >= s and a <= e] or [tokens[0]]

        def add(name: str, m: re.Match, group: int = 1):
            try:
                value = m.group(group)
            except Exception:
                value = m.group(0)
            value = (value or "").strip()
            if not value:
                return
            toks = tokens_for(m)
            conf = sum(t.get("conf", 0.9) for t in toks) / len(toks)
            # First occurrence wins unless we found nothing yet
            prev = fields.get(name)
            if prev is None or prev.get("confidence", 0) < conf:
                fields[name] = {
                    "value": value,
                    "confidence": round(float(conf), 4),
                    "page_no": page["page_no"],
                    "bbox": _union_box(toks),
                }

        for name, pattern in PATTERNS.items():
            m = re.search(pattern, joined, re.IGNORECASE)
            if m:
                add(name, m)

    return fields


def field_value(fields: dict, name: str) -> str:
    f = fields.get(name) or {}
    return (f.get("value") or "").strip()


def mean_field_confidence(fields: dict) -> float:
    vals = [f.get("confidence", 0) for f in fields.values() if f.get("value")]
    return round(sum(vals) / len(vals), 4) if vals else 0.0


def name_similarity(a: str, b: str) -> float:
    """Token-jaccard similarity, ignoring case/punctuation - robust to OCR noise."""
    stop = {"of", "the", "and", "for", "in", "at", "a", "an"}
    ta = {w for w in re.findall(r"[a-z0-9]+", (a or "").lower()) if w not in stop}
    tb = {w for w in re.findall(r"[a-z0-9]+", (b or "").lower()) if w not in stop}
    if not ta or not tb:
        return 0.0
    return round(len(ta & tb) / len(ta | tb), 4)
