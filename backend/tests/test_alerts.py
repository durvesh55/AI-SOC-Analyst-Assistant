"""Alert management: create, validate, search/filter, update, assign, ownership."""
import pytest


def test_create_alert_defaults_and_mitre(client, analyst, make_alert):
    a = make_alert(analyst["headers"])
    assert a["alert_id"] == "ALT-000001" and a["status"] == "New" and a["assigned_to"] is None
    assert a["history"][0]["action"] == "Created"
    assert any(m["technique_id"] == "T1110" for m in a["mitre_suggestions"])


def test_alert_ids_are_unique_and_sequential(client, analyst, make_alert):
    ids = [make_alert(analyst["headers"], title=f"Alert number {i}")["alert_id"] for i in range(3)]
    assert ids == ["ALT-000001", "ALT-000002", "ALT-000003"]


@pytest.mark.parametrize("override", [
    {"severity": "Urgent"}, {"category": "Aliens"}, {"title": "ab"}, {"source_ip": "999.1.1.1"},
    {"title": "x" * 201}, {"indicators": ["i"] * 21}, {"description": "d" * 5001},
])
def test_create_alert_invalid_input(client, analyst, override):
    from tests.conftest import ALERT
    r = client.post("/api/alerts", json={**ALERT, **override}, headers=analyst["headers"])
    assert r.status_code == 422


def test_create_alert_missing_required(client, analyst):
    assert client.post("/api/alerts", json={"title": "No severity"}, headers=analyst["headers"]).status_code == 422


def test_get_alert_and_not_found(client, analyst, make_alert):
    a = make_alert(analyst["headers"])
    assert client.get(f"/api/alerts/{a['id']}", headers=analyst["headers"]).json()["title"] == a["title"]
    assert client.get("/api/alerts/" + "0" * 24, headers=analyst["headers"]).status_code == 404
    assert client.get("/api/alerts/not-an-object-id", headers=analyst["headers"]).status_code == 404


def test_search_and_filters(client, analyst, make_alert):
    h = analyst["headers"]
    make_alert(h, title="Phishing mail reported", category="Phishing", severity="High")
    make_alert(h, title="Port scan from host", category="Network Intrusion", severity="Low")
    make_alert(h, title="Critical ransomware event", category="Malware", severity="Critical")
    get = lambda **p: client.get("/api/alerts", params=p, headers=h).json()
    assert get()["total"] == 3
    assert get(severity="Critical")["total"] == 1
    assert get(category="Phishing")["items"][0]["title"].startswith("Phishing")
    assert get(q="scan")["total"] == 1
    assert get(q=".*")["total"] == 0  # regex characters are escaped, not interpreted
    assert get(status="New")["total"] == 3 and get(status="Resolved")["total"] == 0
    assert get(page_size=2)["items"].__len__() == 2 and get(page_size=2)["total"] == 3
    assert client.get("/api/alerts", params={"severity": "Bogus"}, headers=h).status_code == 422


def test_date_filter(client, analyst, make_alert, db):
    from datetime import timedelta
    from app.utils import utcnow
    h = analyst["headers"]
    old = make_alert(h, title="Old alert from long ago")
    make_alert(h, title="Fresh alert today")
    from bson import ObjectId
    db.alerts.update_one({"_id": ObjectId(old["id"])}, {"$set": {"created_at": utcnow() - timedelta(days=30)}})
    today = utcnow().date().isoformat()
    r = client.get("/api/alerts", params={"date_from": today}, headers=h).json()
    assert r["total"] == 1 and r["items"][0]["title"] == "Fresh alert today"
    old_day = (utcnow() - timedelta(days=30)).date().isoformat()
    r = client.get("/api/alerts", params={"date_from": old_day, "date_to": old_day}, headers=h).json()
    assert r["total"] == 1 and r["items"][0]["title"] == "Old alert from long ago"


def test_update_status_and_fields_recorded_in_history(client, analyst, make_alert):
    h = analyst["headers"]
    a = make_alert(h)
    r = client.patch(f"/api/alerts/{a['id']}", json={"status": "Under Investigation"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "Under Investigation"
    r = client.patch(f"/api/alerts/{a['id']}", json={"severity": "Critical", "title": "Renamed alert"}, headers=h)
    hist = r.json()["history"]
    assert [x["action"] for x in hist] == ["Created", "Status changed", "Updated"]
    assert "severity" in hist[-1]["detail"]


def test_update_invalid_status(client, analyst, make_alert):
    a = make_alert(analyst["headers"])
    assert client.patch(f"/api/alerts/{a['id']}", json={"status": "Deleted"}, headers=analyst["headers"]).status_code == 422


def test_mitre_recomputed_on_update(client, analyst, make_alert):
    h = analyst["headers"]
    a = make_alert(h, title="Odd event", description="nothing interesting", category="Other")
    assert a["mitre_suggestions"] == []
    r = client.patch(f"/api/alerts/{a['id']}", json={"description": "mimikatz accessed lsass"}, headers=h)
    assert any(m["technique_id"] == "T1003" for m in r.json()["mitre_suggestions"])


def test_assignment_rules(client, admin, analyst, analyst2, make_alert):
    a = make_alert(analyst["headers"])
    aid = a["id"]
    me, other = str(analyst["user"]["_id"]), str(analyst2["user"]["_id"])
    # analyst can claim for self but not assign to someone else
    assert client.post(f"/api/alerts/{aid}/assign", json={"assignee_id": other}, headers=analyst["headers"]).status_code == 403
    r = client.post(f"/api/alerts/{aid}/assign", json={"assignee_id": me}, headers=analyst["headers"])
    assert r.status_code == 200 and r.json()["assigned_to_user"]["username"] == "analyst1"
    # other analyst cannot touch an alert owned by analyst1
    assert client.patch(f"/api/alerts/{aid}", json={"status": "Resolved"}, headers=analyst2["headers"]).status_code == 403
    assert client.post(f"/api/alerts/{aid}/assign", json={"assignee_id": other}, headers=analyst2["headers"]).status_code == 403
    # admin can reassign to anybody
    r = client.post(f"/api/alerts/{aid}/assign", json={"assignee_id": other}, headers=admin["headers"])
    assert r.status_code == 200 and r.json()["assigned_to_user"]["username"] == "analyst2"
    assert client.post(f"/api/alerts/{aid}/assign", json={"assignee_id": "f" * 24}, headers=admin["headers"]).status_code == 404
    # filter by assignee
    mine = client.get("/api/alerts", params={"assigned_to": "me"}, headers=analyst2["headers"]).json()
    assert mine["total"] == 1


def test_admin_can_edit_any_alert(client, admin, analyst, make_alert):
    a = make_alert(analyst["headers"])
    client.post(f"/api/alerts/{a['id']}/assign", json={"assignee_id": str(analyst["user"]["_id"])}, headers=analyst["headers"])
    r = client.patch(f"/api/alerts/{a['id']}", json={"status": "False Positive"}, headers=admin["headers"])
    assert r.status_code == 200 and r.json()["status"] == "False Positive"
