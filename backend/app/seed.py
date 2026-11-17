"""Seed DEVELOPMENT data: 3 dev accounts + simulated alerts + 2 sample cases.

    python -m app.seed            # add data if the database is empty
    python -m app.seed --reset    # wipe this app's collections first (development only!)

All alerts are SIMULATED. The dev passwords come from SEED_*_PASSWORD in .env (defaults are in
.env.example) - never use these accounts outside local development.
"""
import sys
from datetime import timedelta

from .config import get_settings
from .database import get_db, init_db
from .routers import alerts as alerts_router
from .routers import cases as cases_router
from .schemas import AlertCreate, CaseClose, CaseCreate, NoteCreate
from .security import hash_password
from .utils import utcnow

COLLECTIONS = ["users", "alerts", "cases", "audit_logs", "counters", "revoked_tokens"]


class _FakeRequest:  # the routers only read request.client for the audit-log IP
    client = None


SAMPLE_ALERTS = [
    ("Multiple failed SSH logins from external IP", "Brute Force", "High", "203.0.113.45", "10.0.0.12", "srv-ssh-01", "root",
     "47 failed login attempts for 'root' in 5 minutes. Possible password spray."),
    ("Impossible travel: login from two countries", "Suspicious Login", "Medium", "198.51.100.23", "10.0.0.50", "vpn-gw", "jsmith",
     "User logged in from India and Brazil within 20 minutes. Possible compromised account."),
    ("Phishing email with malicious attachment reported", "Phishing", "High", None, None, "mail-gw", "mlee",
     "User reported a suspicious email. Attachment invoice.docm contains a macro enabled document."),
    ("Encoded PowerShell command executed", "Malware", "Critical", None, None, "ws-fin-07", "akhan",
     "powershell.exe -EncodedCommand spawned by winword.exe. User opened attachment before execution."),
    ("Outbound beaconing to rare domain", "Malware", "High", "10.0.0.77", "192.0.2.99", "ws-hr-02", "rpatel",
     "Periodic callback every 60s to an uncategorised domain - possible C2 beacon."),
    ("Port scan detected from internal host", "Network Intrusion", "Medium", "10.0.0.31", "10.0.0.0/24", "ws-dev-11", None,
     "nmap-style port scan hitting 1,200 ports across 40 hosts."),
    ("SQL injection attempt on customer portal", "Web Attack", "High", "203.0.113.200", "10.0.1.5", "web-portal-01", None,
     "WAF blocked requests containing UNION SELECT in the id parameter."),
    ("Large outbound transfer to cloud storage", "Data Exfiltration", "Critical", "10.0.0.64", "192.0.2.150", "ws-eng-03", "dnair",
     "4.2 GB uploaded to an unsanctioned dropbox account outside business hours."),
    ("Ransomware note and mass file rename", "Malware", "Critical", None, None, "fs-share-01", None,
     "Thousands of files renamed to .locked and README ransom note created on file share."),
    ("UAC bypass attempt on workstation", "Privilege Escalation", "Medium", None, None, "ws-it-04", "tcole",
     "Process attempted a UAC bypass via fodhelper registry key."),
    ("Credential dumping tool detected (mimikatz)", "Privilege Escalation", "Critical", None, None, "dc-02", None,
     "EDR flagged mimikatz accessing lsass.exe memory on a domain controller."),
    ("SYN flood against public web server", "Denial of Service", "Medium", "203.0.113.0/24", "10.0.1.5", "web-portal-01", None,
     "Traffic spike: 90k SYN packets/s from many sources. Possible ddos."),
    ("Event log cleared on server", "Policy Violation", "High", None, None, "app-srv-09", "svc_backup",
     "Windows Security log cleared using wevtutil cl Security."),
    ("RDP lateral movement between workstations", "Network Intrusion", "High", "10.0.0.88", "10.0.0.89", "ws-sales-05", "bwong",
     "Successful RDP login from a workstation that never used RDP before - possible lateral movement."),
    ("New scheduled task created by unknown user", "Policy Violation", "Low", None, None, "ws-ops-12", "unknown",
     "schtasks /create observed running a script from the Temp folder."),
    ("Failed logins to VPN portal", "Brute Force", "Low", "198.51.100.77", "10.0.0.50", "vpn-gw", "admin",
     "6 failed logins then lockout; low volume."),
    ("Suspicious login at 03:12 local time", "Suspicious Login", "Low", "192.0.2.10", "10.0.0.50", "vpn-gw", "pnguyen",
     "Off-hours login from a known device; user is travelling."),
    ("Web shell file uploaded to server", "Web Attack", "Critical", "203.0.113.99", "10.0.1.8", "web-cms-02", None,
     "File cmd.php written to uploads directory; matches known web shell signature."),
    ("Antivirus disabled on endpoint", "Policy Violation", "High", None, None, "ws-mkt-09", "lchen",
     "Defender real-time protection disabled by a non-admin process."),
    ("Unusual DNS query volume", "Network Intrusion", "Low", "10.0.0.45", "10.0.0.2", "ws-fin-02", None,
     "Spike in TXT record lookups - possible DNS tunneling; likely misconfigured app."),
]


def main(reset: bool = False) -> None:
    s = get_settings()
    db = get_db()
    if reset:
        for c in COLLECTIONS:
            db[c].drop()
        print("Collections dropped.")
    init_db(db)

    if db.users.count_documents({}) > 0:
        print("Database already has users - nothing seeded (use --reset to start over).")
        return

    now = utcnow()
    users = [
        ("admin", "admin@soc.local", "Alex Admin", "Admin", s.seed_admin_password),
        ("analyst1", "analyst1@soc.local", "Priya Analyst", "Analyst", s.seed_analyst_password),
        ("analyst2", "analyst2@soc.local", "Sam Analyst", "Analyst", s.seed_analyst_password),
    ]
    docs = {}
    for username, email, name, role, pw in users:
        doc = {"username": username, "email": email, "full_name": name, "password_hash": hash_password(pw),
               "role": role, "is_active": True, "created_at": now, "updated_at": now, "last_login": None}
        doc["_id"] = db.users.insert_one(doc).inserted_id
        docs[username] = doc

    admin, a1, a2 = docs["admin"], docs["analyst1"], docs["analyst2"]
    created = []
    for i, (title, cat, sev, src, dst, host, usr, desc) in enumerate(SAMPLE_ALERTS):
        body = AlertCreate(title=title, category=cat, severity=sev, description="[SIMULATED] " + desc,
                           source_ip=src if src and "/" not in src else None,
                           destination_ip=dst if dst and "/" not in dst else None,
                           hostname=host, affected_user=usr)
        res = alerts_router.create_alert(body, _FakeRequest(), admin, db)
        # Spread creation dates over the last two weeks so the trend chart has shape.
        when = now - timedelta(days=(i * 3) % 14, hours=(i * 5) % 20)
        assignee = [None, a1, a2][i % 3]
        db.alerts.update_one({"alert_id": res["alert_id"]},
                             {"$set": {"created_at": when, "event_time": when,
                                       "assigned_to": assignee["_id"] if assignee else None}})
        created.append(res)

    # Two sample cases so the case pages and dashboard have data.
    c1 = cases_router.create_case(CaseCreate(alert_ids=[created[3]["id"]]), _FakeRequest(), a1, db)
    cases_router.add_note(c1["id"], NoteCreate(text="Confirmed winword.exe spawned powershell. Isolating host ws-fin-07."),
                          _FakeRequest(), a1, db)
    c2 = cases_router.create_case(CaseCreate(alert_ids=[created[15]["id"]]), _FakeRequest(), a2, db)
    cases_router.add_note(c2["id"], NoteCreate(text="Small number of attempts, no success. Source is a known scanner."),
                          _FakeRequest(), a2, db)
    cases_router.close_case(c2["id"], CaseClose(conclusion="Low-volume noise from an internet scanner. No compromise.",
                                                outcome="False Positive"), _FakeRequest(), a2, db)

    print(f"Seeded {len(users)} users, {len(created)} simulated alerts, 2 cases.")
    print("DEV logins -> admin / analyst1 / analyst2 (passwords from SEED_* values in .env or .env.example)")


if __name__ == "__main__":
    main(reset="--reset" in sys.argv)
