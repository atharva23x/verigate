"""THE EVIDENCE GATE - VeriGate's core safety property.

    ALL of these hold            ->  VERIFIED
      * OCR confidence > 0.90     (the machine can read the text)
      * every issuer-backed document confirmed by its portal
      * no CRITICAL rule flag
      * tamper score < 0.30 and zero pHash duplicates
      * cross-record consistency >= 0.70 (XGBoost vs AICTE master)
    otherwise                     ->  INSUFFICIENT_EVIDENCE

The reported `confidence` is the weakest link in the evidence chain
(min of OCR, consistency, 1-tamper, issuer score) - an explanation for the
human, NOT the pass condition itself.

The gate abstains rather than guesses. Anything it cannot vouch for is routed
to the Manual Review Queue with a structured, explainable reason list.
Humans make all final decisions - this module never approves anything on its
own; it only certifies that the evidence is strong enough for a VERIFIED mark.
"""

from .. import config


def evaluate(ctx: dict) -> dict:
    """ctx: {
        ocr_confidence, consistency_score, tamper_score,
        issuer_results: [{doc_type, portal, status, detail}],
        critical_flags: [flag dicts], duplicate_count,
    } -> {status, confidence, reasons: [{rule_id, message}]}"""
    reasons: list[dict] = []

    ocr_conf = float(ctx.get("ocr_confidence", 0.0))
    consistency = float(ctx.get("consistency_score", 0.0))
    tamper = float(ctx.get("tamper_score", 0.0))
    issuer_results = ctx.get("issuer_results", []) or []
    critical_flags = ctx.get("critical_flags", []) or []
    duplicates = int(ctx.get("duplicate_count", 0))

    # --- Gate condition 1: machine confidence must clear the threshold ------
    if ocr_conf <= config.OCR_CONFIDENCE_THRESHOLD:
        reasons.append(
            {
                "rule_id": "APH-GEN-O01",
                "message": f"OCR confidence {ocr_conf:.2f} <= "
                f"{config.OCR_CONFIDENCE_THRESHOLD:.2f} gate threshold - "
                "the machine cannot vouch for the extracted text.",
            }
        )

    # --- Gate condition 2: every issuer-backed document must be confirmed ---
    unconfirmed = [
        r for r in issuer_results if r.get("status") != "VERIFIED"
    ]
    for r in unconfirmed:
        reasons.append(
            {
                "rule_id": "APH-GEN-I01",
                "message": f"{r.get('portal_name', r.get('portal'))}: "
                f"{r.get('status')} for document '{r.get('doc_number')}' "
                f"({r.get('doc_type')}). {r.get('detail', '')}".strip(),
            }
        )

    # --- Gate condition 3: no critical rule violations ----------------------
    for f in critical_flags:
        if f.get("severity") == "CRITICAL":
            reasons.append(
                {"rule_id": f.get("rule_id"), "message": f.get("reason", f.get("title"))}
            )

    # --- Gate condition 4: tamper + duplicate ------------------------------
    if tamper >= config.TAMPER_SCORE_THRESHOLD:
        reasons.append(
            {
                "rule_id": "APH-GEN-T01",
                "message": f"Tamper score {tamper:.2f} >= "
                f"{config.TAMPER_SCORE_THRESHOLD:.2f} (ELA anomaly).",
            }
        )
    if duplicates:
        reasons.append(
            {
                "rule_id": "APH-GEN-D01",
                "message": f"{duplicates} document(s) are perceptual-hash duplicates "
                "of documents already on record.",
            }
        )

    # --- Gate condition 5: cross-record consistency -------------------------
    if consistency < config.CONSISTENCY_THRESHOLD:
        reasons.append(
            {
                "rule_id": "APH-GEN-C01",
                "message": f"Cross-record consistency {consistency:.2f} < "
                f"{config.CONSISTENCY_THRESHOLD:.2f} - extracted fields do not "
                "match the AICTE master record.",
            }
        )

    # --- Confidence = the weakest link in the evidence chain ----------------
    issuer_score = (
        min(
            (1.0 if r.get("status") == "VERIFIED" else 0.4
             if r.get("status") == "SOURCE_UNAVAILABLE" else 0.0)
            for r in issuer_results
        )
        if issuer_results
        else 1.0
    )
    confidence = round(
        min(ocr_conf, consistency, max(0.0, 1.0 - tamper), issuer_score), 4
    )

    status = "VERIFIED" if not reasons else "INSUFFICIENT_EVIDENCE"
    return {"status": status, "confidence": confidence, "reasons": reasons}
