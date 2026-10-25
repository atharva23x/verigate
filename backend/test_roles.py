"""Live proof of role-based access control (DPDP-style)."""
import httpx

B = "http://127.0.0.1:8000"
c = httpx.Client(timeout=20)

def login(u, p):
    r = c.post(B + "/auth/login", json={"username": u, "password": p})
    return {"Authorization": "Bearer " + r.json()["access_token"]}

roles = {
    "officer  (officer1)   ": login("officer1", "officer123"),
    "reviewer (reviewer1)  ": login("reviewer1", "reviewer123"),
    "auditor  (auditor1)   ": login("auditor1", "auditor123"),
}

def show(name, r):
    mark = "ALLOW" if r.status_code < 300 else f"DENY {r.status_code}"
    print(f"    {name:38} -> {mark}")

print("=== WRITE operations ===")
for label, h in roles.items():
    print(label)
    # create application (needs officer)
    r = c.post(B + "/applications", json={"institution_name": "Perm Test Institute of Technology", "category": "Engineering"}, headers=h)
    show("POST /applications (create)", r)
    app_id = r.json().get("id") if r.status_code < 300 else 11
    # make a review decision on an open flag (needs officer OR reviewer)
    fid = c.get(B + "/applications/11/flags", headers=roles["officer  (officer1)   "]).json()[0]["id"]
    r = c.post(B + f"/reviews/{fid}/decision", json={"decision": "REQUEST_INFO", "comment": "role check"}, headers=h)
    show("POST /reviews/{id}/decision", r)

print()
print("=== READ operations (all roles) ===")
for label, h in roles.items():
    print(label)
    r = c.get(B + "/applications", headers=h); show("GET /applications", r)
    r = c.get(B + "/audit-log?limit=1", headers=h); show("GET /audit-log", r)
    r = c.get(B + "/audit-log/export", headers=h); show("GET /audit-log/export (CSV)", r)
    r = c.get(B + "/reviews/queue", headers=h); show("GET /reviews/queue", r)

print()
print("=== No token at all ===")
r = c.get(B + "/applications"); show("GET /applications (anonymous)", r)
