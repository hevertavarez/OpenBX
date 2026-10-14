"""Suspicious-locations report for Open Bx.

    DATABASE_URL=postgres://... python3 audit_locations.py                  # checks that need no network
    DATABASE_URL=postgres://... python3 audit_locations.py --geocode        # + geocode curated/admin rows
    DATABASE_URL=postgres://... python3 audit_locations.py --geocode-all    # + geocode every row (slow)
    DATABASE_URL=postgres://... python3 audit_locations.py --geocode --fix  # move pins that are >150 m
                                                                            #   from their geocoded address
    ... --csv report.csv   also writes the findings as CSV

Checks:
  missing_coords     no latitude/longitude
  swapped_coords     latitude/longitude look swapped
  outside_bronx      outside the Bronx bounding box (lat 40.785-40.918, lng -73.935 to -73.748)
  outside_outline    inside the box but outside the borough outline (water, Manhattan, Westchester)
  non_bronx_zip      address has no Bronx ZIP code (10451-10475)
  missing_field      no English name, unknown category, or no address
  duplicate          same normalized name+address as another row, or < 40 m apart with a similar name
  shared_coords      several different locations on exactly the same point (markers would stack;
                     usually fine for programs in one building, listed as info)
  geocode_mismatch   pin is > 150 m from where the address geocodes (NYC GeoSearch / Nominatim)
  geocode_failed     the address could not be geocoded
Geocoding results are cached in .geocode_cache.json (not committed).
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from openbx_data import (BRONX_ZIP_RE, CATEGORIES, find_duplicates, geocode, haversine_m,
                         in_bronx_bbox, in_bronx_polygon, normalize_address, name_similarity)

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".geocode_cache.json"
MISMATCH_M = 150


def audit(rows, do_geocode=False, geocode_all=False):
    findings = []

    def add(r, check, severity, detail, **extra):
        findings.append(dict(id=r["id"], name=(r["name"] or {}).get("en", ""), source=r["source"],
                             check=check, severity=severity, detail=detail, **extra))

    for r in rows:
        lat, lng = r["latitude"], r["longitude"]
        if not (r["name"] or {}).get("en") or r["category"] not in CATEGORIES or not r["address"]:
            add(r, "missing_field", "error", "missing English name, valid category or address")
        if r["address"] and not BRONX_ZIP_RE.search(r["address"]):
            add(r, "non_bronx_zip", "warning", r["address"])
        if lat is None or lng is None:
            add(r, "missing_coords", "error", "no coordinates")
            continue
        lat, lng = float(lat), float(lng)
        if not in_bronx_bbox(lat, lng):
            if in_bronx_bbox(lng, lat):
                add(r, "swapped_coords", "error", f"({lat}, {lng}) looks like lng/lat")
            else:
                add(r, "outside_bronx", "error", f"({lat}, {lng})")
        elif not in_bronx_polygon(lat, lng):
            add(r, "outside_outline", "warning", f"({lat}, {lng}) is outside the borough outline")

    # duplicates (pairs reported once)
    seen_pairs = set()
    for r in rows:
        if r["latitude"] is None:
            continue
        for d in find_duplicates(rows, r, ignore_id=r["id"]):
            pair = tuple(sorted((r["id"], d["id"])))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            add(r, "duplicate", "warning",
                f"looks like {d['id']} ({d['name']}), {d['distance_m']} m apart", other_id=d["id"])
    # same normalized name + address across categories is also worth a look
    by_key = defaultdict(list)
    for r in rows:
        by_key[((r["name"] or {}).get("en", "").lower().strip(), normalize_address(r["address"]))].append(r)
    for (nm, _), group in by_key.items():
        if nm and len(group) > 1:
            ids = [g["id"] for g in group]
            pair = tuple(sorted(ids))
            if pair not in seen_pairs:
                add(group[0], "duplicate", "warning", f"same name and address as {', '.join(ids[1:])}")

    # identical coordinates
    by_point = defaultdict(list)
    for r in rows:
        if r["latitude"] is not None:
            by_point[(round(float(r["latitude"]), 5), round(float(r["longitude"]), 5))].append(r)
    for pt, group in by_point.items():
        if len(group) > 1:
            add(group[0], "shared_coords", "info",
                f"{len(group)} locations at {pt}: " + ", ".join(g["id"] for g in group))

    if do_geocode or geocode_all:
        cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
        try:
            for r in rows:
                if not r["address"] or r["latitude"] is None:
                    continue
                if not geocode_all and r["source"] == "nyc_open_data":
                    continue  # FacDB coordinates come from the city's own geocoder
                if r["address"] not in cache:
                    cache[r["address"]] = geocode(r["address"])
                g = cache[r["address"]]
                if not g:
                    add(r, "geocode_failed", "warning", r["address"])
                    continue
                dist = haversine_m(float(r["latitude"]), float(r["longitude"]), g["lat"], g["lng"])
                if dist > MISMATCH_M:
                    add(r, "geocode_mismatch", "error" if dist > 500 else "warning",
                        f"pin is {dist:.0f} m from '{g['label']}' ({g['source']})",
                        geocoded_lat=g["lat"], geocoded_lng=g["lng"], distance_m=round(dist))
        finally:
            CACHE.write_text(json.dumps(cache, indent=1))
    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--geocode", action="store_true", help="geocode curated / admin-entered rows")
    ap.add_argument("--geocode-all", action="store_true", help="geocode every row")
    ap.add_argument("--fix", action="store_true", help="move mismatched pins to the geocoded point")
    ap.add_argument("--csv", help="write findings to this CSV file")
    ap.add_argument("--include-hidden", action="store_true", help="also check rows with active = false")
    args = ap.parse_args()

    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        where = "" if args.include_hidden else "WHERE active"
        rows = conn.execute(f"SELECT id, name, category, address, latitude, longitude, source "
                            f"FROM resources {where} ORDER BY id").fetchall()
        findings = audit(rows, args.geocode, args.geocode_all)

        order = {"error": 0, "warning": 1, "info": 2}
        findings.sort(key=lambda f: (order[f["severity"]], f["check"], f["id"]))
        print(f"checked {len(rows)} locations: "
              + ", ".join(f"{sum(1 for f in findings if f['severity'] == s)} {s}" for s in order))
        for f in findings:
            print(f"  [{f['severity']:<7}] {f['check']:<16} {f['id']:<22} {f['name'][:40]:<40} {f['detail']}")

        if args.fix:
            fixed = 0
            for f in findings:
                if f["check"] == "geocode_mismatch":
                    conn.execute("UPDATE resources SET latitude=%s, longitude=%s, geo_status='geocoded', "
                                 "updated_at=now() WHERE id=%s",
                                 (f["geocoded_lat"], f["geocoded_lng"], f["id"]))
                    print(f"  fixed {f['id']}: moved {f['distance_m']} m to ({f['geocoded_lat']}, {f['geocoded_lng']})")
                    fixed += 1
            print(f"moved {fixed} pin(s)")

    if args.csv:
        keys = ["severity", "check", "id", "name", "source", "detail", "other_id",
                "geocoded_lat", "geocoded_lng", "distance_m"]
        with open(args.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(findings)
        print(f"wrote {args.csv}")
    return 1 if any(f["severity"] == "error" for f in findings) and not args.fix else 0


if __name__ == "__main__":
    sys.exit(main())
