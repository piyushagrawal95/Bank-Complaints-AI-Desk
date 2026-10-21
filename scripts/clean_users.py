"""Utility script to inspect and clean the users table in Supabase PostgreSQL."""

import os
import sys
from dotenv import load_dotenv
import psycopg

# Load environment variables from backend/.env or root .env
for env_path in ["backend/.env", ".env"]:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        break

db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("[ERROR] DATABASE_URL not found in backend/.env")
    sys.exit(1)

def show_users():
    with psycopg.connect(db_url) as conn:
        users = conn.execute("SELECT id, email, full_name, role, created_at FROM users ORDER BY id").fetchall()
        print(f"\n[CURRENT USERS IN DATABASE]: {len(users)} found")
        for u in users:
            print(f"  ID #{u[0]}: {u[1]} ({u[2] or 'No Name'}) - Role: {u[3]}")
    return len(users)

def delete_all_users():
    with psycopg.connect(db_url) as conn:
        conn.execute("DELETE FROM users")
        conn.execute("DELETE FROM password_reset_tokens")
        conn.commit()
    print("\n[SUCCESS] All users and password reset tokens have been deleted.")

def delete_user_by_email(email):
    with psycopg.connect(db_url) as conn:
        conn.execute("DELETE FROM users WHERE email = %s", [email])
        conn.execute("DELETE FROM password_reset_tokens WHERE email = %s", [email])
        conn.commit()
    print(f"\n[SUCCESS] User with email '{email}' deleted.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        delete_all_users()
        show_users()
    elif len(sys.argv) > 1 and sys.argv[1].startswith("--email="):
        target = sys.argv[1].split("=", 1)[1]
        delete_user_by_email(target)
        show_users()
    else:
        count = show_users()
        print("\nCommands you can run:")
        print("  1. Delete ALL users:          python scripts/clean_users.py --all")
        print("  2. Delete a specific email:   python scripts/clean_users.py --email=your_email@gmail.com")
