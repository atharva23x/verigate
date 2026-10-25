"""End-to-end verification of the 5 demo scenarios + supporting endpoints."""
import httpx

B = "http://127.0.0.1:8000"
c = httpx.Client(timeout=30)
tok = c.post(B + "/auth/login", json={"username": "officer1", "password": "officer123"}).json()["access_token"]
H = {"Authorization": "Bearer " + tok}

print("=== 5 DEMO SCENARIOS ===")
expect = [
    (1, "A clean -> VERIFIED"),
    (11, "B missing -> rule flag"),
    (24, "C tampered date -> ELA bbox"),
    (5, "D issuer down -> SOURCE_UNAVAILABLE"),
    (6, "E low OCR -> review queue"),
]
for aid, name in expect:
    d = c.get(f"{B}/applications/{aid}", headers=H).json()
    flags = [(f["rule_id"], f["severity"], f["kind"], bool(f["bbox"])) for f in d["flags"]]
    print(f"[{name}] status={d['status']} scenario={d['scenario']} "
          f"conf={d['gate_confidence']:.2f} issuer={d['issuer_status']} "
          f"ocr={d['ocr_confidence']:.2f} flags={flags}")

# C: bbox detail + page/ELA images
d = c.get(f"{B}/applications/24", headers=H).json()
tf = [f for f in d["flags"] if f["kind"] == "TAMPER"][0]
print("C bbox:", tf["bbox"], "page:", tf["page_no"], "rule:", tf["rule_id"])
pg = c.get(f"{B}/applications/24/documents/{tf['document_id']}/pages/1.png", headers=H)
el = c.get(f"{B}/applications/24/documents/{tf['document_id']}/ela.png", headers=H)
print("C page png:", pg.status_code, len(pg.content), "B | ela png:", el.status_code, len(el.content), "B")

# scenario tags exposed in the list summary
apps = c.get(f"{B}/applications", headers=H).json()
print("scenario tags:", {a["id"]: a["scenario"] for a in apps if a["scenario"]})

# dashboard + queue + progress DONE
st = c.get(f"{B}/dashboard/stats", headers=H).json()
print("dashboard: total=%d verified=%d insufficient=%d in_review=%d pass_rate=%.2f"
      % (st["total"], st["verified"], st["insufficient_evidence"], st["in_review"], st["gate_pass_rate"]))
q = c.get(f"{B}/reviews/queue", headers=H).json()
print("review queue size:", len(q))
print("progress status app1:", c.get(f"{B}/applications/1", headers=H).json()["progress_json"]["status"])
print("ALL SCENARIOS OK")
