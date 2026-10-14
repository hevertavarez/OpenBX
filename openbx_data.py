"""Shared location-data helpers for Open Bx (used by server.py and the scripts).

- CATEGORIES / emoji, Bronx bounds and boundary polygon
- normalize + validate a location record (required: name, category, address,
  coordinates inside the Bronx)
- duplicate detection (normalized name + address, near-identical coordinates)
- geocoding (NYC GeoSearch first, OpenStreetMap Nominatim as a fallback)
- insert / update of `resources` rows
"""
import json
import math
import re
import secrets
import time
import urllib.parse
import urllib.request
from pathlib import Path

from psycopg.types.json import Jsonb

HERE = Path(__file__).resolve().parent
LANGS = ("en", "es", "vi", "zh", "ar")
CATEGORIES = {
    "food": "🍞", "health": "🩺", "rehab": "🌱", "education": "📚",
    "jobs": "💼", "clothing": "👕", "community": "🤝",
}
REQUIREMENT_KEYS = ("noID", "noProofIncome", "walkIn", "spanish", "wheelchair", "transit")
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# Bronx bounding box (lat 40.785-40.918, lng -73.935 to -73.748) plus a small margin
BRONX_BBOX = (40.780, -73.940, 40.920, -73.745)   # south, west, north, east
BRONX_ZIP_RE = re.compile(r"\b104(5[1-9]|6\d|7[0-5])\b")
USER_AGENT = "OpenBx/1.0 (Congressional App Challenge project; Computer Science High School, Bronx NY)"


# ---------------------------------------------------------------- geometry
def haversine_m(lat1, lng1, lat2, lng2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


_BOUNDARY = None


def _boundary():
    global _BOUNDARY
    if _BOUNDARY is None:
        g = json.loads((HERE / "static" / "bronx-boundary.json").read_text())
        _BOUNDARY = [poly[0] for poly in g["geometry"]["coordinates"]]
    return _BOUNDARY


def _in_ring(lng, lat, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lng < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def in_bronx_bbox(lat, lng):
    s, w, n, e = BRONX_BBOX
    return s <= lat <= n and w <= lng <= e


def in_bronx_polygon(lat, lng, tolerance_m=150):
    """True if the point is inside the (simplified) Bronx boundary, or within
    `tolerance_m` of a boundary vertex (the outline is simplified ~25 m)."""
    for ring in _boundary():
        if _in_ring(lng, lat, ring):
            return True
    if tolerance_m:
        for ring in _boundary():
            for x, y in ring:
                if haversine_m(lat, lng, y, x) <= tolerance_m:
                    return True
    return False


# ---------------------------------------------------------------- text normalization
_SMALL = {"a", "an", "and", "at", "by", "de", "del", "for", "in", "la", "of", "on", "or", "the", "to"}
_ACRONYMS = {
    "NYC", "NY", "NYS", "NYCHA", "HRA", "SNAP", "POTS", "YMCA", "YWCA", "SDA", "AME", "CUNY",
    "NYPL", "ESL", "ESOL", "GED", "HSE", "HIV", "AIDS", "LGBT", "LGBTQ", "ACS", "DHS", "II",
    "III", "IV", "LLC", "PS", "MS", "IS", "HS", "CC", "SBH", "USA", "COGIC", "BCC", "OTP",
    "VIP", "UHP", "CHN", "MMCC", "PO", "JHS", "DYCD", "SBS", "FC", "MLK", "SOBO", "P2G", "OASAS",
}
_SPECIAL = {"BRONXWORKS": "BronxWorks", "BRONXCARE": "BronxCare", "WORKFORCE1": "Workforce1",
            "MONTEFIORE": "Montefiore", "DR": "Dr.", "JR": "Jr.", "ST": "St."}


def smart_title(s):
    """'PART OF THE SOLUTION (POTS)' -> 'Part of the Solution (POTS)'.
    Only used for ALL-CAPS source strings; mixed-case strings are kept."""
    s = re.sub(r"\s+", " ", (s or "").strip())
    if not s or s != s.upper():
        return s

    def fix(word, first):
        core = re.sub(r"[^A-Z0-9']", "", word.upper())
        if word.upper() in _SPECIAL:
            return _SPECIAL[word.upper()]
        if core in _ACRONYMS:
            return word.upper()
        if re.fullmatch(r"\d+(ST|ND|RD|TH)", core):
            return word.lower()
        low = word.lower()
        if not first and low in _SMALL:
            return low
        # capitalize each hyphen/slash/paren-separated part; O'Neil, McKinley
        out = re.sub(r"(^|[-/(\"])([a-z])", lambda m: m.group(1) + m.group(2).upper(), low)
        out = re.sub(r"^([OD])'([a-z])", lambda m: m.group(1) + "'" + m.group(2).upper(), out)
        out = re.sub(r"^Mc([a-z])", lambda m: "Mc" + m.group(1).upper(), out)
        return out

    words = s.split(" ")
    return " ".join(fix(w, i == 0) for i, w in enumerate(words))


def _ordinal(n):
    n = int(n)
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


_STREET_WORDS = r"(STREET|ST|PLACE|PL|AVENUE|AVE|ROAD|RD)"


def format_address(street, zipcode=None, city="Bronx"):
    """'333 EAST 149 STREET', '10451' -> '333 East 149th Street, Bronx, NY 10451'"""
    s = re.sub(r"\s+", " ", (street or "").strip()).upper()
    s = re.sub(r"\bBRONX,? NY\b.*$", "", s).strip(" ,")
    # ordinal street numbers that are not the house number: 'EAST 149 STREET', '3 AVENUE'
    s = re.sub(r"(?<=\s)(\d{1,3})(?=\s+" + _STREET_WORDS + r"\b)", lambda m: _ordinal(m.group(1)).upper(), s)
    s = smart_title(s)
    s = re.sub(r"\bSt Ann's\b", "St. Ann's", s)
    parts = [s, f"{city}, NY" + (f" {zipcode}" if zipcode else "")]
    return ", ".join(p for p in parts if p)


_ABBR = {
    "avenue": "ave", "av": "ave", "street": "st", "road": "rd", "place": "pl", "boulevard": "blvd",
    "parkway": "pkwy", "east": "e", "west": "w", "north": "n", "south": "s", "drive": "dr",
    "terrace": "ter", "expressway": "expy", "saint": "st", "reverend": "rev", "concourse": "concourse",
    "third": "3", "first": "1", "second": "2",
}


def normalize_address(addr):
    """Comparable key: house number + street, lowercased and abbreviated, no city/zip."""
    a = (addr or "").lower()
    a = a.split(",")[0]
    a = re.sub(r"\bbronx\b.*$", "", a)
    a = re.sub(r"[^a-z0-9\- ]", " ", a)
    a = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", a)
    words = [_ABBR.get(w, w) for w in a.split()]
    return " ".join(words).strip()


_NAME_STOP = {"the", "inc", "of", "and", "nyc", "at", "llc", "center", "centre", "corp", "corporation", "for", "a", "bronx"}


def name_tokens(name):
    n = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower().replace("&", " and "))
    return {w for w in n.split() if w not in _NAME_STOP and len(w) > 1}


def name_similarity(a, b):
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


# ---------------------------------------------------------------- validation
class ValidationError(Exception):
    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


def _lang_map(value, field, errors, list_values=False, max_len=2000):
    """Accept a plain string (=English) or {lang: text}. Returns a clean dict."""
    if value in (None, ""):
        return {}
    if isinstance(value, str) or (list_values and isinstance(value, list)):
        value = {"en": value}
    if not isinstance(value, dict):
        errors.append(f"{field} must be text or a {{language: text}} object")
        return {}
    out = {}
    for lang, v in value.items():
        if lang not in LANGS:
            continue
        if list_values:
            if isinstance(v, str):
                v = [x.strip() for x in re.split(r"[;\n]", v)]
            if not isinstance(v, list):
                errors.append(f"{field}.{lang} must be a list")
                continue
            v = [str(x).strip()[:200] for x in v if str(x).strip()][:20]
            if v:
                out[lang] = v
        else:
            v = str(v).strip()[:max_len]
            if v:
                out[lang] = v
    return out


_HOURS_RE = re.compile(r"^([01]\d|2[0-4]):[0-5]\d-([01]\d|2[0-4]):[0-5]\d$")


def _hours(value, errors):
    if not value:
        return {}
    if not isinstance(value, dict):
        errors.append("hours must be an object like {\"mon\": \"09:00-17:00\", ...}")
        return {}
    out = {}
    for d in DAYS:
        v = str(value.get(d, "") or "").strip().lower()
        if not v:
            continue
        if v == "closed" or _HOURS_RE.match(v):
            out[d] = v
        else:
            errors.append(f"hours.{d} must be HH:MM-HH:MM or 'closed' (got {v!r})")
    if out:  # days left out are closed
        for d in DAYS:
            out.setdefault(d, "closed")
    return out


def _to_float(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return "bad"


def validate_resource(data, partial=False):
    """Normalize and validate an incoming location (API / CSV / JSON shape).

    Required: name (English), category, address, latitude/longitude inside the
    Bronx. Swapped lat/lng are fixed automatically (reported as a warning).
    Returns (clean_dict, warnings). Raises ValidationError.
    With partial=True only the provided fields are checked (for PATCH)."""
    errors, warnings = [], []
    clean = {}

    def has(k):
        return k in data

    if not partial or "name" in data:
        name = _lang_map(data.get("name"), "name", errors, max_len=200)
        if not name.get("en"):
            errors.append("name (English) is required")
        clean["name"] = name

    if not partial or "category" in data:
        cat = str(data.get("category") or "").strip().lower()
        if cat not in CATEGORIES:
            errors.append(f"category must be one of: {', '.join(CATEGORIES)}")
        clean["category"] = cat
        if not data.get("emoji"):
            clean["emoji"] = CATEGORIES.get(cat)

    if data.get("emoji"):
        clean["emoji"] = str(data["emoji"])[:10]

    if not partial or "address" in data:
        addr = re.sub(r"\s+", " ", str(data.get("address") or "")).strip()
        if len(addr) < 5:
            errors.append("address is required")
        elif len(addr) > 255:
            errors.append("address is too long")
        clean["address"] = addr
        if addr and not BRONX_ZIP_RE.search(addr):
            warnings.append("address has no Bronx ZIP code (10451-10475)")

    lat_in = data.get("lat", data.get("latitude"))
    lng_in = data.get("lng", data.get("longitude"))
    if not partial or lat_in is not None or lng_in is not None:
        lat, lng = _to_float(lat_in), _to_float(lng_in)
        if lat is None or lng is None:
            errors.append("latitude and longitude are required")
        elif lat == "bad" or lng == "bad":
            errors.append("latitude/longitude must be numbers")
        else:
            if not in_bronx_bbox(lat, lng) and in_bronx_bbox(lng, lat):
                lat, lng = lng, lat
                warnings.append("latitude/longitude were swapped; fixed")
            if not in_bronx_bbox(lat, lng):
                errors.append(f"coordinates ({lat:.5f}, {lng:.5f}) are outside the Bronx")
            elif not in_bronx_polygon(lat, lng):
                warnings.append("coordinates are inside the Bronx box but outside the borough outline (water / Manhattan / Westchester?)")
            clean["latitude"], clean["longitude"] = round(lat, 6), round(lng, 6)

    for key, maxlen in (("neighborhood", 100), ("phone", 30)):
        if has(key):
            v = re.sub(r"\s+", " ", str(data.get(key) or "")).strip()
            if len(v) > maxlen:
                errors.append(f"{key} is too long (max {maxlen})")
            clean[key] = v or None

    if has("website"):
        w = str(data.get("website") or "").strip()
        if w and not re.match(r"^https?://[^\s]+\.[^\s]+$", w):
            errors.append("website must start with http:// or https://")
        clean["website"] = w or None

    if has("requirements"):
        req = data.get("requirements") or {}
        if not isinstance(req, dict):
            errors.append("requirements must be an object")
            req = {}
        clean["requirements"] = {k: bool(req[k]) for k in REQUIREMENT_KEYS if k in req and req[k] is not None}

    if has("hours"):
        clean["hours"] = _hours(data.get("hours"), errors)

    src_summary = data.get("ai_summary", data.get("aiSummary", data.get("summary")))
    if has("ai_summary") or has("aiSummary") or has("summary") or not partial:
        clean["ai_summary"] = _lang_map(src_summary, "summary", errors)
    if has("services") or not partial:
        clean["services"] = _lang_map(data.get("services"), "services", errors, list_values=True)
    src_status = data.get("open_status", data.get("openStatus"))
    if has("open_status") or has("openStatus") or not partial:
        clean["open_status"] = _lang_map(src_status, "open_status", errors, max_len=200)

    if "active" in data:
        clean["active"] = bool(data["active"])

    if errors:
        raise ValidationError(errors)
    return clean, warnings


# ---------------------------------------------------------------- duplicates
def find_duplicates(rows, rec, ignore_id=None, max_m=40):
    """rows: iterable of dicts with id, name (dict or str), address, latitude, longitude.
    A duplicate is: same normalized address and similar name, or within `max_m`
    metres with a similar name, or identical normalized name+address."""
    name = rec["name"]["en"] if isinstance(rec.get("name"), dict) else rec.get("name", "")
    addr = normalize_address(rec.get("address"))
    lat, lng = rec.get("latitude"), rec.get("longitude")
    out = []
    cat = rec.get("category")
    for r in rows:
        if r["id"] == ignore_id:
            continue
        if cat and r.get("category") and r["category"] != cat:
            continue  # same building, different kind of service (e.g. hospital vs. its rehab clinic)
        rname = r["name"].get("en", "") if isinstance(r["name"], dict) else (r["name"] or "")
        sim = name_similarity(name, rname)
        same_addr = addr and addr == normalize_address(r.get("address"))
        dist = None
        if None not in (lat, lng, r.get("latitude"), r.get("longitude")):
            dist = haversine_m(float(lat), float(lng), float(r["latitude"]), float(r["longitude"]))
        if (same_addr and sim >= 0.5) or (dist is not None and dist <= max_m and sim >= 0.5):
            out.append({"id": r["id"], "name": rname, "address": r.get("address"),
                        "distance_m": round(dist) if dist is not None else None,
                        "name_similarity": round(sim, 2)})
    return out


# ---------------------------------------------------------------- geocoding
def _get_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


_last_nominatim = [0.0]


def geocode(address):
    """Return {lat, lng, label, source, confidence} or None.
    1) NYC GeoSearch (NYC Planning Labs, built on the city's PAD address file; free, no key)
    2) OpenStreetMap Nominatim (max 1 request/second, identified User-Agent)"""
    q = address if re.search(r"bronx", address, re.I) else f"{address}, Bronx, NY"
    try:
        d = _get_json("https://geosearch.planninglabs.nyc/v2/search?" + urllib.parse.urlencode({"text": q, "size": 1}))
        if d.get("features"):
            f = d["features"][0]
            p = f["properties"]
            lng, lat = f["geometry"]["coordinates"]
            want = re.match(r"\s*(\d+[-\d]*)", address)
            got = re.match(r"\s*(\d+[-\d]*)", p.get("label") or "")
            same_number = not want or (got and got.group(1) == want.group(1))
            if (p.get("borough") or "").lower() == "bronx" and same_number:
                return {"lat": round(lat, 6), "lng": round(lng, 6), "label": p.get("label"),
                        "source": "nyc_geosearch", "confidence": p.get("confidence")}
    except Exception:
        pass
    try:
        wait = 1.1 - (time.time() - _last_nominatim[0])
        if wait > 0:
            time.sleep(wait)
        _last_nominatim[0] = time.time()
        s, w, n, e = BRONX_BBOX
        d = _get_json("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
            "q": q, "format": "jsonv2", "limit": 1, "countrycodes": "us",
            "viewbox": f"{w},{n},{e},{s}", "bounded": 1}))
        if d:
            return {"lat": round(float(d[0]["lat"]), 6), "lng": round(float(d[0]["lon"]), 6),
                    "label": d[0].get("display_name"), "source": "nominatim", "confidence": None}
    except Exception:
        pass
    return None


# ---------------------------------------------------------------- database writes
COLUMNS = ("category", "emoji", "name", "address", "neighborhood", "phone", "website",
           "latitude", "longitude", "open_status", "requirements", "hours", "ai_summary",
           "services", "active", "source", "source_id", "source_url", "program_type",
           "geo_status", "display_order")
JSON_COLUMNS = {"name", "open_status", "requirements", "hours", "ai_summary", "services"}


def new_resource_id(category):
    return f"bx_{category}_{secrets.token_hex(4)}"


def insert_resource(conn, rec, user_id=None):
    rec = dict(rec)
    rec.setdefault("id", new_resource_id(rec["category"]))
    rec.setdefault("emoji", CATEGORIES.get(rec["category"]))
    for k in ("open_status", "requirements", "hours", "ai_summary", "services"):
        rec.setdefault(k, {})
    cols = ["id"] + [c for c in COLUMNS if c in rec]
    vals = [rec["id"]] + [Jsonb(rec[c]) if c in JSON_COLUMNS else rec[c] for c in cols[1:]]
    sql = (f"INSERT INTO resources ({', '.join(cols)}, updated_by) "
           f"VALUES ({', '.join(['%s'] * len(cols))}, %s) RETURNING *")
    return conn.execute(sql, (*vals, user_id)).fetchone()


def update_resource(conn, rid, rec, user_id=None):
    cols = [c for c in COLUMNS if c in rec]
    if not cols:
        return conn.execute("SELECT * FROM resources WHERE id=%s", (rid,)).fetchone()
    sets = ", ".join(f"{c}=%s" for c in cols)
    vals = [Jsonb(rec[c]) if c in JSON_COLUMNS else rec[c] for c in cols]
    return conn.execute(
        f"UPDATE resources SET {sets}, updated_at=now(), updated_by=%s WHERE id=%s RETURNING *",
        (*vals, user_id, rid)).fetchone()


# ---------------------------------------------------------------- bulk import parsing
def flat_to_resource(row):
    """CSV / flat JSON row -> API-shaped dict. Columns:
    name, name_es, name_vi, name_zh, name_ar, category, address, neighborhood,
    latitude, longitude, phone, website, summary[_lang], services[_lang] (';'-separated),
    no_id, no_proof_income, walk_in, multilingual_staff, wheelchair, near_transit (yes/no),
    mon..sun (HH:MM-HH:MM or closed)."""
    if isinstance(row.get("name"), dict):  # already API-shaped
        return row
    g = {k.strip().lower(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}
    out = {
        "name": {"en": g.get("name") or g.get("name_en") or ""},
        "category": g.get("category"),
        "address": g.get("address"),
        "neighborhood": g.get("neighborhood"),
        "latitude": g.get("latitude", g.get("lat")),
        "longitude": g.get("longitude", g.get("lng", g.get("lon"))),
        "phone": g.get("phone"),
        "website": g.get("website"),
        "summary": {}, "services": {},
    }
    for lang in LANGS:
        sfx = "" if lang == "en" else f"_{lang}"
        if g.get(f"name{sfx}"):
            out["name"][lang] = g[f"name{sfx}"]
        if g.get(f"summary{sfx}"):
            out["summary"][lang] = g[f"summary{sfx}"]
        if g.get(f"services{sfx}"):
            out["services"][lang] = g[f"services{sfx}"]
    yes = lambda v: None if v in (None, "") else str(v).strip().lower() in ("1", "y", "yes", "true", "x")
    req = {"noID": yes(g.get("no_id")), "noProofIncome": yes(g.get("no_proof_income")),
           "walkIn": yes(g.get("walk_in")), "spanish": yes(g.get("multilingual_staff")),
           "wheelchair": yes(g.get("wheelchair")), "transit": yes(g.get("near_transit"))}
    out["requirements"] = {k: v for k, v in req.items() if v is not None}
    hours = {d: g[d] for d in DAYS if g.get(d)}
    if hours:
        out["hours"] = hours
    if g.get("id"):
        out["id"] = g["id"]
    return out


def parse_bulk(text, fmt=None):
    """CSV or JSON text -> list of row dicts."""
    import csv
    import io
    text = (text or "").lstrip("﻿").strip()
    if fmt == "json" or (fmt is None and text[:1] in "[{"):
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("resources") or data.get("items") or [data]
        if not isinstance(data, list):
            raise ValueError("JSON must be a list of locations")
        return data
    return list(csv.DictReader(io.StringIO(text)))


def bulk_import(conn, rows, user_id=None, dry_run=True, source="import", geocode_missing=True,
                max_geocode=50):
    """Validate, geocode (if coordinates are missing), dedupe and insert many locations.
    Existing rows are never overwritten. Returns a per-row report."""
    existing = conn.execute("SELECT id, category, name, address, latitude, longitude FROM resources").fetchall()
    report, geocoded = [], 0
    for i, raw in enumerate(rows, start=1):
        entry = {"row": i, "status": None, "name": None, "messages": []}
        try:
            data = flat_to_resource(raw)
            entry["name"] = (data.get("name") or {}).get("en") if isinstance(data.get("name"), dict) else data.get("name")
            if data.get("latitude", data.get("lat")) in (None, "") and data.get("address") and geocode_missing:
                if geocoded >= max_geocode:
                    raise ValidationError([f"no coordinates (geocoding limit of {max_geocode} rows reached)"])
                g = geocode(data["address"])
                geocoded += 1
                if not g:
                    raise ValidationError(["no coordinates and the address could not be geocoded"])
                data["latitude"], data["longitude"] = g["lat"], g["lng"]
                entry["messages"].append(f"geocoded via {g['source']}")
                data["_geo"] = "geocoded"
            clean, warnings = validate_resource(data)
            entry["messages"] += warnings
            dups = find_duplicates(existing, clean)
            if dups:
                entry["status"] = "duplicate"
                entry["messages"].append(f"duplicate of {dups[0]['id']} ({dups[0]['name']})")
                report.append(entry)
                continue
            clean["source"] = source
            clean["geo_status"] = data.get("_geo", "manual")
            if data.get("id") and re.fullmatch(r"[a-z0-9_]{3,40}", str(data["id"])):
                if any(r["id"] == data["id"] for r in existing):
                    raise ValidationError([f"id {data['id']} already exists"])
                clean["id"] = data["id"]
            else:
                clean["id"] = new_resource_id(clean["category"])
            entry["id"] = clean["id"]
            if dry_run:
                entry["status"] = "ok"
            else:
                insert_resource(conn, clean, user_id)
                entry["status"] = "inserted"
            existing.append({"id": clean["id"], "category": clean["category"], "name": clean["name"],
                             "address": clean["address"], "latitude": clean["latitude"],
                             "longitude": clean["longitude"]})
        except ValidationError as e:
            entry["status"] = "invalid"
            entry["messages"] += e.errors
        except (ValueError, TypeError) as e:
            entry["status"] = "invalid"
            entry["messages"].append(str(e))
        report.append(entry)
    return report
