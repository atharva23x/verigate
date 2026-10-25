"""Cross-record consistency scoring with XGBoost (CPU-only).

The model is trained once at startup on synthetic labelled feature rows that
mimic "does this application match the AICTE master record?" decisions, then
scored per application. If XGBoost cannot be imported/trained, a deterministic
weighted fallback is used - the pipeline must never crash (demo safeguard).
"""

import numpy as np

FEATURE_NAMES = [
    "name_sim",          # extracted institution name vs master record (jaccard)
    "aicte_id_match",    # exact AICTE ID match
    "category_match",    # category match
    "address_sim",       # address similarity
    "intake_match",      # approved intake match
    "issue_plausible",   # issue date inside the record's validity window
    "expiry_aligned",    # document expiry consistent with record validity
    "issuer_ok_ratio",   # fraction of issuer checks that came back VERIFIED
    "ocr_conf",          # mean OCR confidence
    "tamper_ok",         # 1 - tamper score
    "not_duplicate",     # 1 - (is duplicate)
]

_model = None
_trained = False
_fallback = False


def _generate_training_data(n: int = 700, seed: int = 42):
    """Synthetic labelled rows: consistent applications vs noisy/forged ones."""
    rng = np.random.default_rng(seed)
    X = np.zeros((n, len(FEATURE_NAMES)), dtype=np.float32)
    y = np.zeros(n, dtype=np.int32)

    good = n // 2
    # Consistent applications: features cluster high
    X[:good, 0] = rng.beta(12, 2, good)          # name_sim
    X[:good, 1] = 1.0
    X[:good, 2] = rng.binomial(1, 0.97, good)
    X[:good, 3] = rng.beta(9, 2, good)
    X[:good, 4] = rng.binomial(1, 0.95, good)
    X[:good, 5] = rng.binomial(1, 0.96, good)
    X[:good, 6] = rng.beta(10, 2, good)
    X[:good, 7] = rng.beta(14, 2, good)
    X[:good, 8] = rng.beta(14, 2, good)
    X[:good, 9] = rng.beta(14, 3, good)
    X[:good, 10] = rng.binomial(1, 0.97, good)
    y[:good] = 1

    bad = n - good
    # Forged / inconsistent: a few features collapse
    X[good:, 0] = rng.beta(2, 6, bad)
    X[good:, 1] = rng.binomial(1, 0.35, bad)
    X[good:, 2] = rng.binomial(1, 0.6, bad)
    X[good:, 3] = rng.beta(2, 5, bad)
    X[good:, 4] = rng.binomial(1, 0.4, bad)
    X[good:, 5] = rng.binomial(1, 0.3, bad)
    X[good:, 6] = rng.beta(2, 5, bad)
    X[good:, 7] = rng.beta(2, 6, bad)
    X[good:, 8] = rng.beta(4, 4, bad)
    X[good:, 9] = rng.beta(3, 5, bad)
    X[good:, 10] = rng.binomial(1, 0.3, bad)
    y[good:] = 0

    # Label noise so the model learns to generalise rather than memorise
    flip = rng.random(n) < 0.04
    y[flip] = 1 - y[flip]
    return X, y


def warmup() -> dict:
    """Train (or fall back). Called once from startup; safe to call repeatedly."""
    global _model, _trained, _fallback
    if _trained:
        return status()
    try:
        from xgboost import XGBClassifier

        X, y = _generate_training_data()
        _model = XGBClassifier(
            n_estimators=80,
            max_depth=3,
            learning_rate=0.15,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="binary:logistic",
            eval_metric="logloss",
            verbosity=0,
            random_state=42,
        )
        _model.fit(X, y)
    except Exception as exc:
        print(f"[consistency] XGBoost unavailable, using heuristic fallback: {exc}")
        _model, _fallback = None, True
    _trained = True
    return status()


def status() -> dict:
    return {
        "trained": _trained,
        "engine": "heuristic-fallback" if _fallback else "xgboost",
        "features": FEATURE_NAMES,
    }


def _heuristic(f: np.ndarray) -> float:
    weights = np.array(
        [0.22, 0.16, 0.05, 0.10, 0.08, 0.09, 0.07, 0.10, 0.08, 0.03, 0.02],
        dtype=np.float32,
    )
    return float(np.clip(np.dot(f, weights), 0.0, 1.0))


def score(features: dict) -> float:
    """features: {name: float 0..1} -> consistency score 0..1"""
    if not _trained:
        warmup()
    vec = np.array(
        [[float(features.get(name, 0.0)) for name in FEATURE_NAMES]], dtype=np.float32
    )
    try:
        if _model is not None:
            return round(float(_model.predict_proba(vec)[0][1]), 4)
    except Exception:
        pass
    return round(_heuristic(vec[0]), 4)


def top_features(features: dict, k: int = 3) -> list[dict]:
    """Largest mismatches vs 1.0 - human-readable explanation of a low score."""
    if not _trained:
        warmup()
    importances = None
    try:
        if _model is not None:
            importances = _model.feature_importances_
    except Exception:
        importances = None
    gaps = []
    for i, name in enumerate(FEATURE_NAMES):
        val = float(features.get(name, 0.0))
        weight = float(importances[i]) if importances is not None else 1.0
        gaps.append({"feature": name, "value": round(val, 3), "weight": round(weight, 4)})
    gaps.sort(key=lambda g: (g["value"] - 1.0) * g["weight"])
    return gaps[:k]
