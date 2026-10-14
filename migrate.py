"""Idempotent, additive schema migrations for Open Bx.

    DATABASE_URL=postgres://... python3 migrate.py

Everything here only ADDS columns / indexes with defaults, so code that was
deployed before these changes keeps working against the migrated database.
Safe to run any number of times. `schema.sql` shows the resulting schema.
"""
import os

import psycopg

MIGRATIONS = [
    # --- from seed_from_page.py (kept here too so one script brings a DB up to date)
    "ALTER TABLE resources ADD COLUMN IF NOT EXISTS open_now BOOLEAN NOT NULL DEFAULT TRUE",
    "ALTER TABLE resources ADD COLUMN IF NOT EXISTS display_order INTEGER",
    "ALTER TABLE questions ADD COLUMN IF NOT EXISTS user_id VARCHAR REFERENCES users(id) ON DELETE SET NULL",

    # --- locations: provenance, soft-hide, audit trail
    # source: curated (hand-entered by the Open Bx team), nyc_open_data, admin (added in the
    # admin form), import (CSV/JSON bulk import)
    "ALTER TABLE resources ADD COLUMN IF NOT EXISTS source VARCHAR(30) NOT NULL DEFAULT 'curated'",
    "ALTER TABLE resources ADD COLUMN IF NOT EXISTS source_id TEXT",            # id in the source dataset
    "ALTER TABLE resources ADD COLUMN IF NOT EXISTS source_url TEXT",           # dataset / record link
    "ALTER TABLE resources ADD COLUMN IF NOT EXISTS program_type VARCHAR(40)",  # see program_types.py
    "ALTER TABLE resources ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE",  # FALSE = hidden
    # geo_status: source (coords from the source dataset), geocoded (address geocoded),
    # manual (entered/checked by an admin), unverified
    "ALTER TABLE resources ADD COLUMN IF NOT EXISTS geo_status VARCHAR(20)",
    "ALTER TABLE resources ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now()",
    "ALTER TABLE resources ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now()",
    "ALTER TABLE resources ADD COLUMN IF NOT EXISTS updated_by VARCHAR(40) REFERENCES users(id) ON DELETE SET NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS resources_source_uid ON resources (source, source_id) WHERE source_id IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS resources_category ON resources (category)",

    # --- questions: app questions vs resource questions, replies visible to the asker
    "ALTER TABLE questions ADD COLUMN IF NOT EXISTS topic VARCHAR(20) NOT NULL DEFAULT 'resource'",  # resource | app
    "ALTER TABLE questions ADD COLUMN IF NOT EXISTS resource_id VARCHAR(40)",   # set when asked from a location
    "ALTER TABLE questions ADD COLUMN IF NOT EXISTS reply TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE questions ADD COLUMN IF NOT EXISTS replied_at TIMESTAMPTZ",
    "ALTER TABLE questions ADD COLUMN IF NOT EXISTS replied_by VARCHAR(40) REFERENCES users(id) ON DELETE SET NULL",
    "CREATE INDEX IF NOT EXISTS questions_user ON questions (user_id)",
]


def migrate(conn):
    for sql in MIGRATIONS:
        conn.execute(sql)


if __name__ == "__main__":
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        migrate(conn)
    print(f"applied {len(MIGRATIONS)} idempotent migration statements")
