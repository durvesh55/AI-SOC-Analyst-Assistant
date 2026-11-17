"""Audit logging, MITRE mapping, PDF report generation and dashboard statistics."""
from app.services.mitre import suggest_techniques
from tests.conftest import login
from tests.test_cases import make_case


# ---------------- MITRE ----------------
def test_mitre_category_and_keywords_with_explanation():
    res = suggest_techniques({"title": "Failed logins", "description": "password spray detected",
                              "category": "Brute Force"})
    top = res[0]
    assert top["technique_id"] == "T1110" and top["tactic"] == "Credential Access"
    assert top["technique_name"] == "Brute Force" and top["confidence"] == "Medium"
    assert "password spray" in top["matched_terms"] and "Brute Force" in top["reason"]
    assert top["status"] == "Suggested" and "validated by an analyst" in top["disclaimer"]


def test_mitre_keyword_only_and_word_boundaries():
    assert suggest_techniques({"title": "x", "description": "rdp session opened", "category": "Other"})[0]["technique_id"] == "T1021"
    # "scheduled" must not accidentally match short tokens inside other words ("iex" in "indexed")
    assert suggest_techniques({"title": "Index rebuilt", "description": "indexed 4000 docs", "category": "Other"}) == []


def test_mitre_no_match_returns_empty():
    assert suggest_techniques({"title": "Routine patch", "description": "applied updates", "category": "Other"}) == []


def test_mitre_catalog_endpoint(client, analyst):
    r = client.get("/api/mitre/techniques", headers=analyst["headers"])
    assert r.status_code == 200 and any(t["technique_id"] == "T1566" for t in r.json())
    assert client.get("/api/mitre/techniques").status_code == 401


def test_case_aggregates_mitre_without_duplicates(client, analyst, make_alert):
    h = analyst["headers"]
    a1, a2 = make_alert(h, title="Failed logins A"), make_alert(h, title="Failed logins B")
    case = make_case(client, h, [a1["id"], a2["id"]])
    ids = [m["technique_id"] for m in case["mitre_suggestions"]]
    assert len(ids) == len(set(ids)) and "T1110" in ids


# ---------------- Audit logs ----------------
def actions_for(db):
    return [e["action"] for e in db.audit_logs.find({}).sort("timestamp", 1)]


def test_audit_covers_required_events(client, db, admin, analyst, make_alert):
    h = analyst["headers"]
    a = make_alert(h)
    client.patch(f"/api/alerts/{a['id']}", json={"severity": "Critical"}, headers=h)
    client.patch(f"/api/alerts/{a['id']}", json={"status": "Under Investigation"}, headers=h)
    client.post(f"/api/alerts/{a['id']}/assign", json={"assignee_id": str(analyst["user"]["_id"])}, headers=h)
    case = make_case(client, h, [a["id"]])
    client.post(f"/api/cases/{case['id']}/notes", json={"text": "note one"}, headers=h)
    client.patch(f"/api/cases/{case['id']}", json={"status": "In Progress"}, headers=h)
    client.get(f"/api/cases/{case['id']}/report", headers=h)
    client.post(f"/api/cases/{case['id']}/close", json={"conclusion": "Resolved the thing.", "outcome": "Resolved"}, headers=h)
    client.post(f"/api/cases/{case['id']}/reopen", json={"reason": "more evidence"}, headers=admin["headers"])
    client.post("/api/users", headers=admin["headers"],
                json={"username": "zed", "email": "z@z.com", "full_name": "Z", "password": "Passw0rd123"})
    client.post("/api/auth/logout", headers=h)
    client.post("/api/auth/login", json={"identifier": "analyst1", "password": "bad-password1"})
    got = set(actions_for(db))
    required = {"LOGIN", "LOGIN_FAILED", "LOGOUT", "ALERT_CREATED", "ALERT_UPDATED", "ALERT_STATUS_CHANGED",
                "ALERT_ASSIGNED", "CASE_CREATED", "NOTE_ADDED",
                "CASE_STATUS_CHANGED", "REPORT_GENERATED", "CASE_CLOSED", "CASE_REOPENED", "USER_CREATED"}
    assert required <= got, required - got


def test_audit_case_assignment_logged(client, db, admin, analyst, make_alert):
    case = make_case(client, analyst["headers"], [make_alert(analyst["headers"])["id"]])
    client.post(f"/api/cases/{case['id']}/assign", json={"assignee_id": str(admin["user"]["_id"])}, headers=admin["headers"])
    assert "CASE_ASSIGNED" in actions_for(db)


def test_audit_never_contains_passwords(client, db, analyst):
    client.post("/api/auth/login", json={"identifier": "analyst1", "password": "SuperSecret999"})
    client.post("/api/auth/change-password", headers=analyst["headers"],
                json={"current_password": "Analyst#Pass123", "new_password": "NewSecret#4567"})
    dump = str(list(db.audit_logs.find({})))
    for secret in ("SuperSecret999", "NewSecret#4567", "Analyst#Pass123", "$2b$"):
        assert secret not in dump


def test_audit_visibility_admin_all_analyst_own(client, admin, analyst, analyst2, make_alert):
    make_alert(analyst["headers"])
    make_alert(analyst2["headers"], title="Another alert here")
    adm = client.get("/api/audit-logs", headers=admin["headers"]).json()
    assert {e["actor_username"] for e in adm["items"]} >= {"admin", "analyst1", "analyst2"}
    mine = client.get("/api/audit-logs", params={"actor": "analyst2"}, headers=analyst["headers"]).json()
    assert mine["total"] > 0 and {e["actor_username"] for e in mine["items"]} == {"analyst1"}


def test_audit_filters(client, admin, analyst, make_alert):
    make_alert(analyst["headers"])
    r = client.get("/api/audit-logs", params={"action": "ALERT_CREATED"}, headers=admin["headers"]).json()
    assert r["total"] == 1 and r["items"][0]["resource_id"] == "ALT-000001"
    r = client.get("/api/audit-logs", params={"q": "ALT-000001"}, headers=admin["headers"]).json()
    assert r["total"] == 1
    assert client.get("/api/audit-logs/actions", headers=admin["headers"]).status_code == 200


def test_audit_records_cannot_be_modified_via_api(client, admin, analyst):
    """No write route exists for audit logs, for ANY role (incl. Admin)."""
    for who in (analyst, admin):
        h = who["headers"]
        assert client.post("/api/audit-logs", json={"action": "X"}, headers=h).status_code == 405
        assert client.delete("/api/audit-logs", headers=h).status_code == 405
        entry_id = client.get("/api/audit-logs", headers=h).json()["items"][0]["id"]
        assert client.patch(f"/api/audit-logs/{entry_id}", json={"action": "X"}, headers=h).status_code == 404
        assert client.delete(f"/api/audit-logs/{entry_id}", headers=h).status_code == 404
        assert client.put(f"/api/audit-logs/{entry_id}", json={}, headers=h).status_code == 404


# ---------------- PDF ----------------
def test_pdf_report(client, db, analyst, make_alert):
    h = analyst["headers"]
    case = make_case(client, h, [make_alert(h, title="Alert <b>with</b> markup & ampersand")["id"]])
    client.post(f"/api/cases/{case['id']}/notes", json={"text": "Found <script>alert(1)</script> in logs"}, headers=h)
    client.patch(f"/api/cases/{case['id']}", json={"findings": "Brute force from one IP"}, headers=h)
    r = client.get(f"/api/cases/{case['id']}/report", headers=h)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF") and len(r.content) > 1500
    assert "CASE-000001-report.pdf" in r.headers["content-disposition"]
    assert db.audit_logs.count_documents({"action": "REPORT_GENERATED"}) == 1


def test_pdf_requires_auth_and_valid_case(client, analyst, make_alert):
    case = make_case(client, analyst["headers"], [make_alert(analyst["headers"])["id"]])
    assert client.get(f"/api/cases/{case['id']}/report").status_code == 401
    assert client.get("/api/cases/" + "c" * 24 + "/report", headers=analyst["headers"]).status_code == 404


def test_pdf_for_closed_case(client, analyst, make_alert):
    h = analyst["headers"]
    case = make_case(client, h, [make_alert(h)["id"]])
    client.post(f"/api/cases/{case['id']}/close", json={"conclusion": "Blocked the IP.", "outcome": "Resolved"}, headers=h)
    assert client.get(f"/api/cases/{case['id']}/report", headers=h).content.startswith(b"%PDF")


# ---------------- Dashboard ----------------
def test_dashboard_empty(client, analyst):
    d = client.get("/api/dashboard", headers=analyst["headers"]).json()
    assert d["total_alerts"] == 0 and d["open_cases"] == 0 and d["resolved_cases"] == 0
    assert d["alerts_by_severity"] == {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    assert len(d["alert_trend"]) == 14 and all(p["count"] == 0 for p in d["alert_trend"])


def test_dashboard_reflects_real_data(client, admin, analyst, make_alert):
    h = analyst["headers"]
    a1 = make_alert(h, severity="Critical", title="Critical alert one")
    a2 = make_alert(h, severity="High", title="High alert two")
    make_alert(h, severity="High", title="High alert three")
    c1 = make_case(client, h, [a1["id"]])
    c2 = make_case(client, h, [a2["id"]])
    client.post(f"/api/cases/{c1['id']}/close", json={"conclusion": "Benign activity.", "outcome": "False Positive"}, headers=h)
    d = client.get("/api/dashboard", headers=admin["headers"]).json()
    assert d["total_alerts"] == 3
    assert d["alerts_by_severity"]["Critical"] == 1 and d["alerts_by_severity"]["High"] == 2
    assert d["false_positives"] == 1
    assert d["open_cases"] == 1 and d["resolved_cases"] == 1 and d["total_cases"] == 2
    assert d["alert_trend"][-1]["count"] == 3  # all created "today"
    work = {w["username"]: w for w in d["analyst_workload"]}
    assert work["analyst1"]["open_cases"] == 1 and work["analyst1"]["open_alerts"] == 1 and work["admin"]["open_cases"] == 0
    assert len(d["recent_activities"]) > 0


def test_dashboard_recent_activity_scoped_for_analyst(client, admin, analyst, make_alert):
    make_alert(admin["headers"], title="Admin made this alert")
    d = client.get("/api/dashboard", headers=analyst["headers"]).json()
    assert {e["actor_username"] for e in d["recent_activities"]} <= {"analyst1"}


def test_meta_is_public_and_health_reports_db(client):
    m = client.get("/api/meta").json()
    assert m["severities"] == ["Critical", "High", "Medium", "Low"] and "Brute Force" in m["categories"]


def test_unhandled_errors_are_masked(client, analyst, monkeypatch):
    from app import main
    from fastapi.testclient import TestClient
    import app.routers.dashboard as dash

    def boom(*a, **k):
        raise RuntimeError("secret internal detail")
    monkeypatch.setattr(dash, "_group", boom)
    r = TestClient(main.app, raise_server_exceptions=False).get("/api/dashboard", headers=analyst["headers"])
    assert r.status_code == 500 and r.json() == {"detail": "Internal server error"}
    assert "secret" not in r.text


def test_security_headers_and_cors(client):
    r = client.get("/api/meta", headers={"Origin": "http://localhost:5173"})
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    r = client.get("/api/meta", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r.headers
