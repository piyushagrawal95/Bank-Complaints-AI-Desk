"""CLI tool to reset any user password directly in the database."""
import getpass
import os
import sys

import psycopg
from dotenv import load_dotenv

sys.path.insert(0, "backend")
from app.security import hash_password  # noqa: E402


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/reset_password.py user@example.com")
    email = sys.argv[1].strip().lower()

    load_dotenv("backend/.env")
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is empty in backend/.env")

    password = getpass.getpass("New password (at least 8 characters): ")
    if len(password) < 8:
        raise SystemExit("The password must have at least 8 characters.")
    if password != getpass.getpass("Repeat the password: "):
        raise SystemExit("The two passwords are not the same.")

    with psycopg.connect(url) as conn:
        row = conn.execute(
            "UPDATE users SET password_hash = %s, is_active = TRUE WHERE email = %s RETURNING id",
            [hash_password(password), email],
        ).fetchone()

    if row is None:
        raise SystemExit(f"No user found with email: {email}")
    print(f"Password updated successfully for {email}.")


if __name__ == "__main__":
    main()
