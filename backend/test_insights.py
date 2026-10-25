"""Smoke-test the five new VeriGate insight endpoints (read-only).

Usage: python test_insights.py
"""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"
OUT = r"C:\Users\bhang\AppData\Local\Temp\opencode"
failures = []


def call(method, path, token=None, data=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    body = None if data is None else json.dumps(data).encode()
    try:
        with urllib.request.urlopen(req, body, timeout=30) as resp:
            raw = resp.read()
            ct = resp.headers.get("Content-Type", "")
            if "json" in ct:
                return resp.status, json.loads(raw), ct, raw
            return resp.status, raw, ct, raw
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw), e.headers.get("Content-Type", ""), raw
        except Exception:
            return e.code, raw, "", raw


def check(name, ok, extra=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{extra}]" if extra else ""))
    if not ok:
        failures.append(name)


# ------------------------------------------------------------------ auth
status, tok, _, _ = call(
    "POST", "/auth/login", data={"username": "officer1", "password": "officer123"}
)
check("login as officer1", status == 200 and "access_token" in tok)
token = tok["access_token"]

status, tok2, _, _ = call(
    "POST", "/auth/login", data={"username": "auditor1", "password": "auditor123"}
)
token_auditor = tok2.get("access_token", "")

# ------------------------------------------------------- consistency view
status, cons, _, _ = call("GET", "/applications/1/consistency", token)
rows = cons.get("rows", []) if isinstance(cons, dict) else []
check(
    "consistency: app 1 returns 7 comparison rows",
    status == 200 and len(rows) == 7,
    f"status={status} rows={len(rows)} score={cons.get('score') if isinstance(cons, dict) else '?'}",
)
check(
    "consistency: master record found for app 1",
    isinstance(cons, dict) and cons.get("master_record") is not None,
    str((cons.get("master_record") or {}).get("aicte_id"))
    if isinstance(cons, dict)
    else "",
)
check(
    "consistency: app 1 rows all MATCH",
    all(r["status"] == "MATCH" for r in rows),
    ",".join(r["status"] for r in rows),
)

status, cons24, _, _ = call("GET", "/applications/24/consistency", token)
rows24 = cons24.get("rows", []) if isinstance(cons24, dict) else []
weakest24 = cons24.get("weakest_features", []) if isinstance(cons24, dict) else []
weak_names = [w["feature"] for w in weakest24]
check(
    "consistency: app 24 (scenario C) is below threshold with named weak signals",
    status == 200
    and cons24.get("below_threshold") is True
    and cons24.get("score", 1) < cons24.get("threshold", 0)
    and "tamper_ok" in weak_names
    and len(rows24) == 7,
    f"score={cons24.get('score')} weakest={weak_names}",
)

# ----------------------------------------------------------- duplicates
status, dup, _, _ = call("GET", "/applications/28/duplicates", token)
check(
    "duplicates: app 28 has 2 pairs",
    status == 200 and dup.get("count") == 2,
    f"status={status} count={dup.get('count') if isinstance(dup, dict) else '?'}",
)
pair = (dup.get("pairs") or [{}])[0] if isinstance(dup, dict) else {}
check(
    "duplicates: pair carries donor + distance + text similarity",
    pair.get("donor", {}).get("ref_no") == "EoA/2026/0001"
    and pair.get("distance") is not None
    and pair.get("text_sim", 0) > 0.9,
    f"donor={pair.get('donor', {}).get('ref_no')} dist={pair.get('distance')} sim={pair.get('text_sim')}",
)
status, dup1, _, _ = call("GET", "/applications/1/duplicates", token)
check(
    "duplicates: clean app 1 has none",
    status == 200 and dup1.get("count") == 0,
    f"count={dup1.get('count') if isinstance(dup1, dict) else '?'}",
)

# --------------------------------------------------------- issuer status
status, iss, _, _ = call("GET", "/issuer/status", token)
portals = iss.get("portals", []) if isinstance(iss, dict) else []
check(
    "issuer: 5 portals returned",
    status == 200 and len(portals) == 5,
    f"{len(portals)} portals",
)
fire = next((p for p in portals if p["id"] == "fire_dept"), {})
check(
    "issuer: fire_dept shows the scenario-D outage on FIRE/WB/2026/0053",
    fire.get("records_down") == 1
    and "SOURCE_UNAVAILABLE" in (fire.get("checks") or {}),
    f"down={fire.get('records_down')} checks={fire.get('checks')}",
)
check(
    "issuer: summary totals are sane",
    isinstance(iss, dict)
    and iss["summary"]["total_checks"] > 50
    and 0 < iss["summary"]["verified_rate"] <= 1,
    json.dumps(iss.get("summary", {})) if isinstance(iss, dict) else "",
)

# ------------------------------------------------------------ analytics
status, ana, _, _ = call("GET", "/dashboard/analytics", token)
t = ana.get("totals", {}) if isinstance(ana, dict) else {}
check(
    "analytics: totals match the seeded state (30 / 8 / 22)",
    status == 200 and t.get("applications") == 30 and t.get("verified") == 8
    and t.get("insufficient_evidence") == 22,
    json.dumps(t),
)
check(
    "analytics: category, rule, gap and risk buckets all populated",
    isinstance(ana, dict)
    and len(ana.get("by_category", [])) == 3
    and len(ana.get("flags_by_rule", [])) >= 5
    and len(ana.get("document_gaps", [])) >= 3
    and sum(b["count"] for b in ana.get("risk_buckets", [])) == 30,
    f"cats={len(ana.get('by_category', []))} rules={len(ana.get('flags_by_rule', []))} gaps={len(ana.get('document_gaps', []))}",
)

# ----------------------------------------------------------- PDF report
for app_id, tag in ((1, "A-verified"), (24, "C-tampered"), (5, "D-outage")):
    status, pdf, ct, raw = call("GET", f"/applications/{app_id}/report", token)
    ok = status == 200 and raw[:4] == b"%PDF" and "pdf" in ct
    check(
        f"report: app {app_id} ({tag}) is a real PDF",
        ok,
        f"status={status} ct={ct} bytes={len(raw)}",
    )
    if ok:
        with open(rf"{OUT}\report_{app_id}_{tag}.pdf", "wb") as fh:
            fh.write(raw)

# ------------------------------------------------------- auth + roles
status, _, _, _ = call("GET", "/dashboard/analytics")
check("analytics requires auth (401 anonymous)", status == 401, f"status={status}")
status, _, _, _ = call("GET", "/applications/1/report")
check("report requires auth (401 anonymous)", status == 401, f"status={status}")
status, cons3, _, _ = call("GET", "/applications/1/consistency", token_auditor)
check("auditor (read-only) can view insights", status == 200, f"status={status}")

print()
print("ALL INSIGHT CHECKS PASSED" if not failures else f"{len(failures)} FAILED: {failures}")
raise SystemExit(1 if failures else 0)
