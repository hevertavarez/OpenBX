"""Set (rotate) a user's password without putting it in code or the shell history.

    DATABASE_URL=postgres://... python3 set_password.py admin@openbx.org

Prompts for the new password twice (not echoed) and stores a bcrypt hash.
Use this to replace the public demo password (demo1234) on staff accounts
before the app is shown to real users.
"""
import getpass
import os
import sys

import bcrypt
import psycopg


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    email = sys.argv[1].strip().lower()
    pw = getpass.getpass("New password (min 12 characters): ")
    if len(pw) < 12:
        print("Too short.")
        return 1
    if pw != getpass.getpass("Repeat: "):
        print("Passwords do not match.")
        return 1
    h = bcrypt.hashpw(pw.encode(), bcrypt.gensalt(12)).decode()
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        row = conn.execute("UPDATE users SET password_hash=%s WHERE lower(email)=%s RETURNING id, role",
                           (h, email)).fetchone()
    print(f"updated {row[0]} ({row[1]})" if row else "no user with that email")
    return 0 if row else 1


if __name__ == "__main__":
    sys.exit(main())
