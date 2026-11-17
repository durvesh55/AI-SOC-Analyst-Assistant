"""Case management: creation from alerts, permissions, notes, close/reopen, timeline."""


def make_case(client, headers, alert_ids, **extra):
    r = client.post("/api/cases", json={"alert_ids": alert_ids, **extra}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_case_links_alerts(client, analyst, make_alert):
    h = analyst["headers"]
    a1 = make_alert(h, severity="Low", title="Low severity brute force")
    a2 = make_alert(h, severity="Critical", title="Critical thing happened", category="Malware")
    case = make_case(client, h, [a1["id"], a2["id"]])
    assert case["case_id"] == "CASE-000001" and case["status"] == "Open"
    assert case["severity"] == "Critical"  # highest of linked alerts
    assert case["assigned_to_user"]["username"] == "analyst1"
    assert case["timeline"][0]["action"] == "Case created"
    assert {a["alert_id"] for a in case["alerts"]} == {a1["alert_id"], a2["alert_id"]}
    for aid in (a1["id"], a2["id"]):
        alert = client.get(f"/api/alerts/{aid}", headers=h).json()
        assert alert["status"] == "Under Investigation" and alert["case"]["case_id"] == "CASE-000001"


def test_case_ids_unique(client, analyst, make_alert):
    h = analyst["headers"]
    c1 = make_case(client, h, [make_alert(h, title="First alert here")["id"]])
    c2 = make_case(client, h, [make_alert(h, title="Second alert here")["id"]])
    assert c1["case_id"] != c2["case_id"]


def test_alert_cannot_join_two_cases(client, analyst, make_alert):
    h = analyst["headers"]
    a = make_alert(h)
    make_case(client, h, [a["id"]])
    assert client.post("/api/cases", json={"alert_ids": [a["id"]]}, headers=h).status_code == 409


def test_create_case_invalid_input(client, analyst):
    h = analyst["headers"]
    assert client.post("/api/cases", json={"alert_ids": []}, headers=h).status_code == 422
    assert client.post("/api/cases", json={"alert_ids": ["nope"]}, headers=h).status_code == 404
    assert client.post("/api/cases", json={"alert_ids": ["a" * 24]}, headers=h).status_code == 404
    assert client.post("/api/cases", json={}, headers=h).status_code == 422


def test_cannot_open_case_on_someone_elses_alert(client, analyst, analyst2, make_alert):
    a = make_alert(analyst["headers"])
    client.post(f"/api/alerts/{a['id']}/assign", json={"assignee_id": str(analyst["user"]["_id"])}, headers=analyst["headers"])
    assert client.post("/api/cases", json={"alert_ids": [a["id"]]}, headers=analyst2["headers"]).status_code == 403


def test_notes_and_timeline(client, analyst, make_alert):
    h = analyst["headers"]
    case = make_case(client, h, [make_alert(h)["id"]])
    r = client.post(f"/api/cases/{case['id']}/notes", json={"text": "Checked firewall logs."}, headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["notes"][0]["text"] == "Checked firewall logs." and body["notes"][0]["author_username"] == "analyst1"
    assert body["timeline"][-1]["action"] == "Note added"
    assert client.post(f"/api/cases/{case['id']}/notes", json={"text": ""}, headers=h).status_code == 422
    assert client.post(f"/api/cases/{case['id']}/notes", json={"text": "x" * 5001}, headers=h).status_code == 422


def test_ownership_enforced_on_case_changes(client, analyst, analyst2, admin, make_alert):
    case = make_case(client, analyst["headers"], [make_alert(analyst["headers"])["id"]])
    cid = case["id"]
    o = analyst2["headers"]
    assert client.post(f"/api/cases/{cid}/notes", json={"text": "intruder note"}, headers=o).status_code == 403
    assert client.patch(f"/api/cases/{cid}", json={"findings": "x"}, headers=o).status_code == 403
    assert client.post(f"/api/cases/{cid}/close", json={"conclusion": "closing it", "outcome": "Resolved"}, headers=o).status_code == 403
    assert client.post(f"/api/cases/{cid}/assign", json={"assignee_id": str(analyst2["user"]["_id"])}, headers=o).status_code == 403
    # admin may act on anyone's case, and reassign it
    assert client.post(f"/api/cases/{cid}/notes", json={"text": "admin note"}, headers=admin["headers"]).status_code == 201
    r = client.post(f"/api/cases/{cid}/assign", json={"assignee_id": str(analyst2["user"]["_id"])}, headers=admin["headers"])
    assert r.status_code == 200 and r.json()["assigned_to_user"]["username"] == "analyst2"
    # viewing remains open to all analysts
    assert client.get(f"/api/cases/{cid}", headers=o).status_code == 200


def test_update_findings_and_status(client, analyst, make_alert):
    h = analyst["headers"]
    case = make_case(client, h, [make_alert(h)["id"]])
    r = client.patch(f"/api/cases/{case['id']}", json={"status": "In Progress", "findings": "Source IP is a known scanner."}, headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "In Progress" and r.json()["findings"].startswith("Source IP")
    assert client.patch(f"/api/cases/{case['id']}", json={"status": "Closed"}, headers=h).status_code == 422  # must use /close


def test_close_updates_alerts_and_blocks_edits(client, analyst, make_alert):
    h = analyst["headers"]
    a = make_alert(h)
    case = make_case(client, h, [a["id"]])
    assert client.post(f"/api/cases/{case['id']}/close", json={"conclusion": "ok", "outcome": "Resolved"}, headers=h).status_code == 422
    r = client.post(f"/api/cases/{case['id']}/close", json={"conclusion": "Confirmed brute force; IP blocked.", "outcome": "Resolved"}, headers=h)
    assert r.status_code == 200
    closed = r.json()
    assert closed["status"] == "Closed" and closed["outcome"] == "Resolved" and closed["closed_at"]
    assert client.get(f"/api/alerts/{a['id']}", headers=h).json()["status"] == "Resolved"
    assert client.post(f"/api/cases/{case['id']}/notes", json={"text": "late note"}, headers=h).status_code == 409
    assert client.post(f"/api/cases/{case['id']}/close", json={"conclusion": "again again", "outcome": "Resolved"}, headers=h).status_code == 409


def test_close_as_false_positive(client, analyst, make_alert):
    h = analyst["headers"]
    a = make_alert(h)
    case = make_case(client, h, [a["id"]])
    client.post(f"/api/cases/{case['id']}/close", json={"conclusion": "Benign scanner traffic.", "outcome": "False Positive"}, headers=h)
    assert client.get(f"/api/alerts/{a['id']}", headers=h).json()["status"] == "False Positive"


def test_reopen_requires_admin(client, analyst, admin, make_alert):
    h = analyst["headers"]
    a = make_alert(h)
    case = make_case(client, h, [a["id"]])
    client.post(f"/api/cases/{case['id']}/close", json={"conclusion": "Done with it.", "outcome": "Resolved"}, headers=h)
    assert client.post(f"/api/cases/{case['id']}/reopen", json={"reason": "new evidence"}, headers=h).status_code == 403
    r = client.post(f"/api/cases/{case['id']}/reopen", json={"reason": "new evidence found"}, headers=admin["headers"])
    assert r.status_code == 200 and r.json()["status"] == "In Progress" and r.json()["closed_at"] is None
    assert r.json()["timeline"][-1]["action"] == "Case reopened"
    assert client.get(f"/api/alerts/{a['id']}", headers=h).json()["status"] == "Under Investigation"
    # reopening a case that is not closed is a conflict
    assert client.post(f"/api/cases/{case['id']}/reopen", json={"reason": "again please"}, headers=admin["headers"]).status_code == 409


def test_list_and_filter_cases(client, analyst, admin, make_alert):
    h = analyst["headers"]
    c1 = make_case(client, h, [make_alert(h, severity="Low", title="Low one here")["id"]])
    make_case(client, h, [make_alert(h, severity="High", title="High one here")["id"]])
    client.post(f"/api/cases/{c1['id']}/close", json={"conclusion": "All good here.", "outcome": "Resolved"}, headers=h)
    get = lambda **p: client.get("/api/cases", params=p, headers=h).json()
    assert get()["total"] == 2 and get(status="Closed")["total"] == 1 and get(status="Open")["total"] == 1
    assert get(severity="High")["total"] == 1 and get(q="CASE-000002")["total"] == 1
    assert get(assigned_to="me")["total"] == 2
    assert "notes" not in get()["items"][0]  # list view stays light
    assert client.get("/api/cases/" + "b" * 24, headers=h).status_code == 404
