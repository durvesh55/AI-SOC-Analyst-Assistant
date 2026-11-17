"""Create an Administrator - the safe way to bootstrap a PRODUCTION database.

    python -m app.create_admin --username alex --email alex@example.com --name "Alex Admin"

The password is read from the ADMIN_PASSWORD environment variable, or prompted for (hidden) if unset.
Unlike `python -m app.seed` this creates no sample users or alerts.
"""
import argparse
import getpass
import os
import sys

from pydantic import ValidationError

from .database import get_db, init_db
from .schemas import AdminCreateUser
from .security import hash_password
from .utils import utcnow


def create_admin(db, username: str, email: str, full_name: str, password: str) -> str:
    """Validate with the same rules as the API and insert an Admin. Returns the new user id."""
    data = AdminCreateUser(username=username, email=email, full_name=full_name, password=password, role="Admin")
    now = utcnow()
    doc = {"username": data.username, "email": data.email.lower(), "full_name": data.full_name.strip(),
           "password_hash": hash_password(data.password), "role": "Admin", "is_active": True,
           "created_at": now, "updated_at": now, "last_login": None}
    return str(db.users.insert_one(doc).inserted_id)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--username", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    args = p.parse_args()
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
    db = get_db()
    init_db(db)
    try:
        create_admin(db, args.username, args.email, args.name, password)
    except ValidationError as exc:
        print("Invalid input:", "; ".join(e["msg"] for e in exc.errors()))
        return 1
    except Exception as exc:  # e.g. duplicate username/email
        print("Could not create admin:", type(exc).__name__)
        return 1
    print(f"Administrator '{args.username.lower()}' created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
