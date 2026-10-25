"""DELETE /applications - role guards + behaviour.

Run with the backend up:
    .\\venv\\Scripts\\python.exe test_delete.py

This script creates and deletes applications (including one seeded one), so
reseed afterwards for a pristine demo state:
    Remove-Item verigate.db,storage ; restart uvicorn
"""

import json
import urllib.error
import urllib.request
from pathlib import Path

B = "http://localhost:8000"
STORAGE = Path(__file__).resolve().parent / "storage"

_results: list[bool] = []


def check(name: str, ok: bool, extra: str = "") -> None:
    _results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{extra}]" if extra else ""))


def call(method: str, path: str, token: str | None = None, data=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(B + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return e.code, {}


def login(username: str, password: str) -> str:
    _, payload = call(
        "POST", "/auth/login", data={"username": username, "password": password}
    )
    return payload["access_token"]


officer = login("officer1", "officer123")
reviewer = login("reviewer1", "reviewer123")
auditor = login("auditor1", "auditor123")

NEW_APP = {
    "institution_name": "Temp Institute for Delete Test",
    "category": "Engineering",
    "aicte_id": "AICTE-DEL-0001",
    "address": "Test street",
    "approved_intake": 60,
}

print("=== create fixtures ===")
_, x = call("POST", "/applications", officer, NEW_APP)
_, y = call("POST", "/applications", officer, {**NEW_APP, "aicte_id": "AICTE-DEL-0002"})
check("fixture X created", x.get("id") is not None, f"ref={x.get('ref_no')}")
check("fixture Y created", y.get("id") is not None, f"ref={y.get('ref_no')}")
existing_refs = set()
_, listing = call("GET", "/applications?limit=500", officer)
for a in listing:
    existing_refs.add(a["ref_no"])

print("\n=== role guards ===")
code, _ = call("DELETE", f"/applications/{x['id']}", reviewer)
check("reviewer DELETE -> 403", code == 403, str(code))
code, _ = call("DELETE", f"/applications/{x['id']}", auditor)
check("auditor DELETE -> 403", code == 403, str(code))
code, _ = call("DELETE", f"/applications/{x['id']}")
check("anonymous DELETE -> 401", code == 401, str(code))
code, _ = call("GET", f"/applications/{x['id']}", reviewer)
check("fixture X still alive after denials", code == 200, str(code))

print("\n=== officer delete ===")
code, payload = call("DELETE", f"/applications/{x['id']}", officer)
check("officer DELETE -> 200", code == 200, str(code))
check("response says deleted", payload.get("deleted") is True)
check("response echoes ref", payload.get("ref_no") == x["ref_no"], str(payload.get("ref_no")))
code, _ = call("GET", f"/applications/{x['id']}", officer)
check("GET deleted app -> 404", code == 404, str(code))
code, _ = call("DELETE", f"/applications/{x['id']}", officer)
check("second DELETE -> 404", code == 404, str(code))

print("\n=== ref_no stays unique after a delete ===")
_, z = call("POST", "/applications", officer, {**NEW_APP, "aicte_id": "AICTE-DEL-0003"})
code = 200 if z.get("id") else 500
check("create after delete works", z.get("id") is not None, f"ref={z.get('ref_no')}")
check(
    "new ref is not a duplicate",
    z.get("ref_no") is not None and z["ref_no"] not in existing_refs,
    f"{z.get('ref_no')}",
)

print("\n=== files are cleaned up (seeded app #30) ===")
_, app30 = call("GET", "/applications/30", officer)
doc_ids = [d["id"] for d in app30.get("documents", [])]
upload_dir = STORAGE / "uploads" / "app_30"
page_dirs = [STORAGE / "pages" / str(d) for d in doc_ids]
ela_dirs = [STORAGE / "ela" / str(d) for d in doc_ids]
check("app #30 has documents", len(doc_ids) > 0, f"{len(doc_ids)} docs")
check("app #30 upload dir exists", upload_dir.exists())
code, payload = call("DELETE", "/applications/30", officer)
check("deleted app #30", code == 200, str(code))
check("upload dir removed", not upload_dir.exists())
check("page renders removed", not any(p.exists() for p in page_dirs))
check("ela heatmaps removed", not any(p.exists() for p in ela_dirs))

print("\n=== audit trail keeps the record ===")
_, audit_payload = call("GET", "/audit-log?action=APP_DELETE&limit=20", officer)
entries = audit_payload.get("entries", [])
deletes = [e for e in entries if e.get("action") == "APP_DELETE"]
check("APP_DELETE entries written", len(deletes) >= 2, f"{len(deletes)} entries")
top = deletes[0] if deletes else {}
check(
    "actor resolved to a person",
    top.get("detail", {}).get("actor_name") == "Atharva Bhangale",
    str(top.get("detail", {}).get("actor_name")),
)
check(
    "deleted ref recorded",
    any(e.get("detail", {}).get("ref_no") == "EoA/2026/0030" for e in deletes),
)

print("\n=== cleanup of fixtures ===")
for app in (y, z):
    if app.get("id"):
        code, _ = call("DELETE", f"/applications/{app['id']}", officer)
        check(f"removed fixture ref={app.get('ref_no')}", code == 200, str(code))

print()
if all(_results):
    print(f"ALL DELETE CHECKS OK ({len(_results)} checks)")
else:
    print(f"{_results.count(False)} of {len(_results)} checks FAILED")
    raise SystemExit(1)
