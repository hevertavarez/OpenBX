"""Import Bronx community resources from NYC Open Data into `resources`.

    DATABASE_URL=postgres://... python3 import_nyc_open_data.py           # dry run (report only)
    DATABASE_URL=postgres://... python3 import_nyc_open_data.py --apply   # write to the DB

Source: NYC Department of City Planning "Facilities Database" (FacDB),
https://data.cityofnewyork.us/d/ji82-xba5 (Socrata API, no key needed).
FacDB combines city/state agency lists (Food Bank For NYC pantries, NYS DOH
health facilities, NYPL branches, DYCD/MOEO programs, HRA centers, NYCHA
community centers, ...) and geocodes every address with the city's own
geocoder, so its coordinates are a good reference. NYC Open Data is free to
use under the NYC Open Data Terms of Use; we credit "NYC Open Data / NYC
Department of City Planning (Facilities Database)" on the map and in the
location details.

Rules:
- only the Bronx, only categories the app already has (food, health, rehab,
  education, jobs, clothing, community), only sites with an address and a Bronx ZIP;
- specialist clinics (dialysis, surgery, imaging, ...) and Rikers Island programs
  are skipped;
- duplicates inside the source (same category + same address) are merged;
- rows that duplicate a curated / admin-entered location are skipped
  (curated rows stay authoritative);
- re-running updates rows from this source unless an admin has edited them
  (`updated_by` set); nothing is ever deleted.
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
from collections import Counter, OrderedDict

import psycopg
from psycopg.rows import dict_row

from migrate import migrate
from openbx_data import (BRONX_ZIP_RE, LANGS, ValidationError, _get_json, find_duplicates,
                         format_address, insert_resource, normalize_address, smart_title,
                         update_resource, validate_resource)
from program_types import CALL_AHEAD, PROGRAM_TYPES

DATASET = "ji82-xba5"
DATASET_URL = f"https://data.cityofnewyork.us/d/{DATASET}"
SOURCE = "nyc_open_data"
SUBGROUPS = (
    "SOUP KITCHENS AND FOOD PANTRIES", "HOSPITALS AND CLINICS",
    "SUBSTANCE USE DISORDER TREATMENT PROGRAMS", "PUBLIC LIBRARIES",
    "ADULT AND IMMIGRANT LITERACY", "GED AND ALTERNATIVE HIGH SCHOOL EQUIVALENCY",
    "WORKFORCE DEVELOPMENT", "COMMUNITY CENTERS AND COMMUNITY PROGRAMS",
    "FINANCIAL ASSISTANCE AND SOCIAL SERVICES", "IMMIGRANT SERVICES",
    "NON-RESIDENTIAL HOUSING AND HOMELESS SERVICES",
)
# Corrections for source rows that the suspicious-locations report (audit_locations.py
# --geocode-all) found to be wrong. Keyed by FacDB uid.
SOURCE_FIXES = {
    # DeWitt Clinton HS HSE site: source ZIP 10466 is wrong and its point was 3.6 km off
    "6658a3994c4d318141d22718cff0f1a4": {"address": "100 WEST MOSHOLU PARKWAY SOUTH", "zipcode": "10468",
                                         "latitude": "40.8812883504", "longitude": "-73.8874847783"},
}
SPECIALIST = re.compile(r"DIALYSIS|RENAL|KIDNEY|ENDOSCOPY|SURG|\bASC\b|IMAGING|\bGI\b|\bEYE\b|"
                        r"PHYSICAL MEDICINE|REHABILITATION|AMBULATORY|SMILE|DENTAL|STARLING", re.I)


def classify(f):
    """FacDB row -> (program_type, rank) or None. Lower rank wins when merging."""
    g, t, name = f["facsubgrp"], f["factype"], f.get("facname", "")
    if g == "SOUP KITCHENS AND FOOD PANTRIES":
        return ("soup_kitchen", 1) if t == "SOUP KITCHEN" else ("food_pantry", 2)
    if g == "HOSPITALS AND CLINICS":
        if t in ("HOSPITAL", "ACUTE CARE HOSPITAL"):
            return ("hospital", 1)
        if t in ("DIAGNOSTIC AND TREATMENT CENTER", "DIAGNOSTIC & TREATMENT CENTER"):
            return None if SPECIALIST.search(name) else ("health_center", 2)
        if t == "CHILD HEALTH CENTER":
            return ("child_health", 3)
        return None
    if g == "SUBSTANCE USE DISORDER TREATMENT PROGRAMS":
        return ("opioid_treatment", 1 if t == "METHADONE MAINTENANCE" else 2)
    if g == "PUBLIC LIBRARIES":
        return ("library", 1)
    if g == "ADULT AND IMMIGRANT LITERACY":
        return ("esl", 2) if "ENGLISH" in t else ("adult_education", 1)
    if g == "GED AND ALTERNATIVE HIGH SCHOOL EQUIVALENCY":
        return ("hse_prep", 1) if t.startswith("GED") else None
    if g == "WORKFORCE DEVELOPMENT":
        if t == "WORKFORCE1 CAREER CENTER":
            return ("workforce1", 1)
        if t == "WORKFORCE 1 CAREER CENTERS":
            return ("workforce1", 2)       # same centers listed under the operator's name
        if t == "JOBS AND SERVICE CENTER":
            return ("benefits_center", 1)
        if t in ("JOBS PLUS", "WORKS PLUS", "EMPLOYMENT WORKS", "YOUTHPATHWAYS", "VOCATIONAL SERVICES-OMH"):
            return ("job_program", 1)
        return None
    if g == "COMMUNITY CENTERS AND COMMUNITY PROGRAMS":
        return ("community_center", 1) if t.startswith("NYCHA") else None
    if g == "FINANCIAL ASSISTANCE AND SOCIAL SERVICES":
        return {"SNAP CENTER": ("benefits_center", 2), "MEDICAID OFFICE": ("benefits_center", 3)}.get(t)
    if g == "IMMIGRANT SERVICES":
        return ("civics_classes", 2) if t == "CIVICS CLASSES" else ("immigrant_services", 1)
    if g == "NON-RESIDENTIAL HOUSING AND HOMELESS SERVICES":
        return ("drop_in_center", 1) if t == "DROP-IN CENTERS" else None
    return None


def _clean_org(s):
    s = smart_title(s or "")
    s = re.sub(r",?\s+(Inc\.?|LLC|Corp\.?|Corporation)$", "", s, flags=re.I).strip(" ,")
    return s


def build_name(f, ptype):
    """Returns {lang: name}. English always; other languages when we add a translated suffix."""
    fac = re.sub(r"\s+", " ", f.get("facname", "")).strip()
    op = re.sub(r"\s+", " ", f.get("opname", "") or "").strip()
    suffix = PROGRAM_TYPES[ptype].get("name_suffix")
    # prefer the operator name when it is the same text in proper case
    base = op if op and op.upper() == fac.upper() and op != op.upper() else fac

    def with_suffix(org):
        return {lang: f"{org} – {suffix[lang]}" for lang in LANGS}

    if ptype in ("food_pantry", "soup_kitchen"):
        parts = [p.strip() for p in base.split(" : ")]
        if len(parts) == 2:
            org, prog = _clean_org(parts[0]), _clean_org(parts[1])
            if prog.lower() == org.lower() or org.lower() in prog.lower():
                name = prog
            elif prog.lower() in org.lower():
                name = org
            else:
                name = f"{prog} ({org})" if len(prog) + len(org) < 80 else prog
        else:
            name = _clean_org(base)
        return {"en": name}
    if ptype == "hse_prep":
        site = re.sub(r"^GED\s*-?\s*(P2G|P26|RESTART|NYC)?\s*-?\s*", "", fac, flags=re.I)
        site = re.sub(r"\s*-\s*AHSEP$|-AHSEP$|/(AM|PM|DAY)\b.*$", "", site, flags=re.I).strip(" -/")
        return {lang: f"{suffix[lang]} – {smart_title(site)}" for lang in LANGS}
    if ptype == "community_center":
        return with_suffix(smart_title(fac))
    if ptype == "opioid_treatment":
        org = _clean_org(re.sub(r"\s+(OTP\s*\d*|MTA-R)$", "", base, flags=re.I))
        return with_suffix(org)
    if ptype in ("adult_education", "esl", "civics_classes", "job_program", "drop_in_center"):
        return with_suffix(_clean_org(op or fac))
    if ptype == "immigrant_services":
        if op and fac.upper() != op.upper() and "LSNY" in op.upper():
            return {"en": smart_title(fac)}          # LSNY program names are descriptive
        return with_suffix(_clean_org(op or fac))
    if ptype == "benefits_center" and f["factype"] == "MEDICAID OFFICE":
        return {"en": f"HRA Medicaid Office – {smart_title(fac)}"}
    return {"en": _clean_org(fac)}


def fetch_facdb():
    where = "boro='BRONX' AND facsubgrp in (" + ",".join(f"'{g}'" for g in SUBGROUPS) + ")"
    url = (f"https://data.cityofnewyork.us/resource/{DATASET}.json?"
           + urllib.parse.urlencode({"$where": where, "$limit": 5000, "$order": "uid"}))
    return _get_json(url, timeout=60)


def fetch_nta_names():
    url = ("https://data.cityofnewyork.us/resource/9nt8-h7nd.json?"
           + urllib.parse.urlencode({"$select": "nta2020,ntaname", "boroname": "Bronx", "$limit": 500}))
    return {r["nta2020"]: r["ntaname"] for r in _get_json(url)}


def build_records(facdb, nta):
    skipped = Counter()
    candidates = []
    for f in facdb:
        f = {**f, **SOURCE_FIXES.get(f.get("uid"), {})}
        c = classify(f)
        if not c:
            skipped["not a matching program type"] += 1
            continue
        ptype, rank = c
        if not f.get("address") or not f.get("latitude"):
            skipped["no address / coordinates in source"] += 1
            continue
        zipcode = (f.get("zipcode") or "").strip()
        if not BRONX_ZIP_RE.search(zipcode) or "HAZEN" in f["address"].upper():
            skipped["not a Bronx ZIP (e.g. Rikers Island)"] += 1
            continue
        pt = PROGRAM_TYPES[ptype]
        rec = {
            "name": build_name(f, ptype),
            "category": pt["category"],
            "address": format_address(f["address"], zipcode),
            "neighborhood": nta.get(f.get("nta2020"), None),
            "latitude": f["latitude"], "longitude": f["longitude"],
            "summary": dict(pt["summary"]),
            "services": {k: list(v) for k, v in pt["services"].items()},
            "open_status": dict(CALL_AHEAD),
            "requirements": {},
        }
        try:
            clean, warnings = validate_resource(rec)
        except ValidationError as e:
            skipped["invalid: " + e.errors[0][:60]] += 1
            continue
        clean.update(source=SOURCE, source_id=f["uid"], source_url=DATASET_URL,
                     program_type=ptype, geo_status="source", hours={}, requirements={})
        clean["_rank"] = rank
        clean["id"] = f"nyc_{clean['category']}_{f['uid'][:10]}"
        candidates.append(clean)

    # merge duplicates inside the source: same category + same normalized address
    candidates.sort(key=lambda r: (r["category"], r["_rank"], r["name"]["en"]))
    merged = OrderedDict()
    for r in candidates:
        key = (r["category"], normalize_address(r["address"]))
        keep = merged.get(key)
        if keep is None:  # same program listed twice with slightly different address text
            near = find_duplicates(list(merged.values()), r, max_m=40)
            keep = next((m for m in merged.values() if near and m["id"] == near[0]["id"]), None)
        if keep is not None:
            for lang in LANGS:  # keep the other program's services too
                for s in r["services"].get(lang, []):
                    if s not in keep["services"].setdefault(lang, []):
                        keep["services"][lang].append(s)
            skipped["merged duplicate inside source"] += 1
            continue
        merged[key] = r
    return list(merged.values()), skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write to the database (default: dry run)")
    ap.add_argument("--json", help="also write the records that would be imported to this file")
    args = ap.parse_args()

    print("fetching NYC Open Data Facilities Database (Bronx) ...")
    facdb = fetch_facdb()
    nta = fetch_nta_names()
    records, skipped = build_records(facdb, nta)
    print(f"  {len(facdb)} source rows -> {len(records)} candidate locations")

    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        if args.apply:
            migrate(conn)
        cols = "id, category, name, address, latitude, longitude, source, source_id, updated_by"
        existing = conn.execute(f"SELECT {cols} FROM resources").fetchall()
        authoritative = [r for r in existing if r.get("source", "curated") != SOURCE]
        by_uid = {r["source_id"]: r for r in existing if r.get("source") == SOURCE}

        stats = Counter()
        dup_of_curated = []
        for rec in records:
            rec.pop("_rank", None)
            dups = find_duplicates(authoritative, rec, max_m=60)
            if dups:
                dup_of_curated.append((rec["name"]["en"], rec["address"], dups[0]["id"], dups[0]["distance_m"]))
                stats["skipped: duplicate of a curated/admin location"] += 1
                continue
            old = by_uid.get(rec["source_id"])
            if old and old["updated_by"]:
                stats["skipped: edited by an admin"] += 1
                continue
            if not args.apply:
                stats["would update" if old else "would insert"] += 1
                continue
            if old:
                rec.pop("id", None)
                update_resource(conn, old["id"], rec)
                conn.execute("UPDATE resources SET updated_by=NULL WHERE id=%s", (old["id"],))
                stats["updated"] += 1
            else:
                insert_resource(conn, rec)
                stats["inserted"] += 1
        seen = {r["source_id"] for r in records}
        gone = [r["id"] for r in by_uid.values() if r["source_id"] not in seen]

        by_cat = Counter(r["category"] for r in records)
        print("\ncandidates by category:", dict(sorted(by_cat.items())))
        print("source rows skipped:", dict(skipped))
        print("result:", dict(stats))
        if dup_of_curated:
            print("\nmatched existing curated locations (kept the curated row):")
            for name, addr, rid, dist in dup_of_curated:
                print(f"  {rid:<14} <- {name} | {addr} | {dist} m apart")
        if gone:
            print(f"\n{len(gone)} previously imported rows are no longer in the source (left as-is): {gone[:20]}")
        total = conn.execute("SELECT count(*) AS n FROM resources").fetchone()["n"]
        print(f"\nresources table now has {total} rows" + ("" if args.apply else " (dry run: nothing written)"))
        if args.json:
            with open(args.json, "w") as fh:
                json.dump(records, fh, ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    sys.exit(main())
