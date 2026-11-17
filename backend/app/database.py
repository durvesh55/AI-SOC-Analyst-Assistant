"""MongoDB connection, collection validators and indexes."""
import logging

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database

from .config import get_settings

log = logging.getLogger("soc.db")
_client: MongoClient | None = None

SEVERITIES = ["Critical", "High", "Medium", "Low"]
ALERT_STATUSES = ["New", "Under Investigation", "Resolved", "False Positive"]
CASE_STATUSES = ["Open", "In Progress", "Closed"]
ROLES = ["Admin", "Analyst"]
CATEGORIES = [
    "Malware", "Phishing", "Brute Force", "Suspicious Login", "Network Intrusion",
    "Web Attack", "Data Exfiltration", "Privilege Escalation", "Denial of Service",
    "Policy Violation", "Other",
]


def get_db() -> Database:
    """FastAPI dependency. Tests replace this with an in-memory database."""
    global _client
    settings = get_settings()
    if _client is None:
        _client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    return _client[settings.mongo_db]


def _validator(required: list[str], props: dict) -> dict:
    return {"$jsonSchema": {"bsonType": "object", "required": required, "properties": props}}


VALIDATORS = {
    "users": _validator(
        ["username", "email", "password_hash", "role", "is_active", "created_at"],
        {"role": {"enum": ROLES}, "is_active": {"bsonType": "bool"},
         "username": {"bsonType": "string"}, "email": {"bsonType": "string"}},
    ),
    "alerts": _validator(
        ["alert_id", "title", "severity", "status", "category", "created_at"],
        {"severity": {"enum": SEVERITIES}, "status": {"enum": ALERT_STATUSES}},
    ),
    "cases": _validator(
        ["case_id", "title", "status", "severity", "created_at"],
        {"status": {"enum": CASE_STATUSES}, "severity": {"enum": SEVERITIES}},
    ),
    "audit_logs": _validator(
        ["timestamp", "action", "actor_username"],
        {"action": {"bsonType": "string"}},
    ),
}


def init_db(db: Database) -> None:
    """Create collections with $jsonSchema validation and all indexes (idempotent)."""
    existing = set(db.list_collection_names())
    for name, validator in VALIDATORS.items():
        try:
            if name in existing:
                db.command("collMod", name, validator=validator, validationLevel="moderate")
            else:
                db.create_collection(name, validator=validator)
        except Exception as exc:  # e.g. an in-memory test DB without validator support
            log.warning("Could not apply validator to %s: %s", name, type(exc).__name__)

    db.users.create_index("email", unique=True)
    db.users.create_index("username", unique=True)
    db.alerts.create_index("alert_id", unique=True)
    db.alerts.create_index([("severity", ASCENDING), ("status", ASCENDING)])
    db.alerts.create_index("assigned_to")
    db.alerts.create_index([("created_at", DESCENDING)])
    db.cases.create_index("case_id", unique=True)
    db.cases.create_index([("status", ASCENDING), ("assigned_to", ASCENDING)])
    db.audit_logs.create_index([("timestamp", DESCENDING)])
    db.audit_logs.create_index("actor_id")
    db.audit_logs.create_index("action")
    # Revoked (logged-out) tokens vanish automatically once the JWT itself would have expired.
    db.revoked_tokens.create_index("expires_at", expireAfterSeconds=0)
    db.revoked_tokens.create_index("jti", unique=True)
