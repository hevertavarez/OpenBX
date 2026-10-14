"""Bulk-import locations from a CSV or JSON file (same rules as the admin form).

    DATABASE_URL=postgres://... python3 import_resources.py locations.csv            # dry run
    DATABASE_URL=postgres://... python3 import_resources.py locations.csv --apply    # insert

Required per row: name, category (food, health, rehab, education, jobs, clothing,
community), address. latitude/longitude are optional: missing coordinates are
geocoded (NYC GeoSearch, then OpenStreetMap Nominatim). Every row is validated
(coordinates must be in the Bronx) and checked against existing locations for
duplicates (same normalized name + address, or < 40 m apart with a similar
name); duplicates and invalid rows are reported and skipped, never overwritten.

CSV columns (header row required; only name/category/address are required):
  id, name, name_es, name_vi, name_zh, name_ar, category, address, neighborhood,
  latitude, longitude, phone, website, summary, summary_es, summary_vi, summary_zh,
  summary_ar, services (';'-separated), services_es, ..., no_id, no_proof_income,
  walk_in, multilingual_staff, wheelchair, near_transit (yes/no),
  mon, tue, wed, thu, fri, sat, sun ("09:00-17:00" or "closed")
JSON: a list of objects with the same keys, or in the API shape
  ({"name": {"en": ..., "es": ...}, "category": ..., "lat": ..., "lng": ..., ...}).
See sample_locations.csv.
"""
import argparse
import os
import sys
from collections import Counter

import psycopg
from psycopg.rows import dict_row

from migrate import migrate
from openbx_data import bulk_import, parse_bulk


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--apply", action="store_true", help="insert valid rows (default: dry run)")
    ap.add_argument("--no-geocode", action="store_true", help="do not geocode rows without coordinates")
    args = ap.parse_args()
    with open(args.file, encoding="utf-8") as fh:
        rows = parse_bulk(fh.read(), "json" if args.file.endswith(".json") else None)
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        if args.apply:
            migrate(conn)
        report = bulk_import(conn, rows, dry_run=not args.apply, geocode_missing=not args.no_geocode)
    for e in report:
        print(f"  row {e['row']:>3} {e['status']:<9} {str(e.get('id') or ''):<22} {(e['name'] or '')[:40]:<40} {'; '.join(e['messages'])}")
    print(dict(Counter(e["status"] for e in report)), "" if args.apply else "(dry run: nothing written)")
    return 0 if all(e["status"] in ("ok", "inserted") for e in report) else 1


if __name__ == "__main__":
    sys.exit(main())
