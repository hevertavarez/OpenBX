"""Open Bx backend: serves index.html and a small JSON API over Postgres.

Run locally:  DATABASE_URL=postgres://... python3 -m flask --app server run
On Render:    gunicorn server:app   (env: DATABASE_URL, SECRET_KEY)

Roles (users.role):
  admin      everything below + the app-questions inbox, location add/edit/import
  counselor  staff: the resource-help question queue (not app questions), search logs
  user       saved centers, "my questions" with replies
All role checks happen here on the server; the page only hides buttons for convenience.
"""
import gzip
import hashlib
import os
import re
import secrets
import time
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

import bcrypt
import psycopg
from flask import Flask, Response, jsonify, request, session
from psycopg.rows import dict_row

from openbx_data import (CATEGORIES, ValidationError, bulk_import, find_duplicates, geocode,
                         insert_resource, parse_bulk, update_resource, validate_resource)

HERE = Path(__file__).resolve().parent

app = Flask(__name__, static_folder=str(HERE / "static"), static_url_path="/static")
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_NAME="openbx_session",
    # static files are referenced with ?v=<hash of the static folder>, so they can be cached for a year
    SEND_FILE_MAX_AGE_DEFAULT=31536000,
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)
app.json.sort_keys = False  # keep hours rows in day order
NYC = ZoneInfo("America/New_York")

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_LABEL = {"mon": "Mon", "tue": "Tue", "wed": "Wed", "thu": "Thu",
             "fri": "Fri", "sat": "Sat", "sun": "Sun"}
# questionLang <select> in the page uses language names; the DB stores codes
LANG_CODES = {"English": "en", "Spanish": "es", "Vietnamese": "vi",
              "Chinese": "zh", "Arabic": "ar"}
LANG_NAMES = {v: k for k, v in LANG_CODES.items()}
STATUS_LABEL = {"pending": "New", "in_progress": "In Progress",
                "answered": "✓ Answered"}
TOPICS = ("resource", "app")
STAFF_ROLES = ("admin", "counselor")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------- database
@contextmanager
def db():
    """One short-lived connection per request; commits on success."""
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        yield conn


def new_id(prefix):
    return f"{prefix}_{secrets.token_hex(5)}"


def err(code, message, status):
    """Errors carry a stable `code` so the page can show them in the user's language."""
    return jsonify(error=message, code=code), status


# ---------------------------------------------------------------- adapters
def _fmt_time(t):
    h, m = map(int, t.split(":"))
    ap = "AM" if h < 12 or h == 24 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {ap}"


def _fmt_value(v):
    if not v or v.lower() == "closed":
        return "Closed"
    if v == "00:00-24:00":
        return "24 Hours"
    a, b = v.split("-")
    return f"{_fmt_time(a)} - {_fmt_time(b)}"


def format_hours(hours):
    """{"mon": "09:00-15:30", ...} -> {"Mon - Sat": "9:00 AM - 3:30 PM", "Sun": "Closed"}
    (English display shape; the page now formats `hoursRaw` per language itself)."""
    if not hours:
        return {}
    if not all(d in hours for d in DAYS):  # already free-form: pass through
        return hours
    if all(hours[d] == "00:00-24:00" for d in DAYS):
        return {"Mon - Sun": "24 Hours / 7 Days"}
    groups = {}  # value -> [day indexes], in first-seen order
    for i, d in enumerate(DAYS):
        groups.setdefault(hours[d], []).append(i)
    out = {}
    for value, idxs in groups.items():
        runs, start = [], idxs[0]
        for a, b in zip(idxs, idxs[1:] + [None]):
            if b != a + 1:
                runs.append((start, a))
                start = b
        label = ", ".join(DAY_LABEL[DAYS[s]] if s == e
                          else f"{DAY_LABEL[DAYS[s]]} - {DAY_LABEL[DAYS[e]]}"
                          for s, e in runs)
        out[label] = _fmt_value(value)
    return out


def resource_to_page(r, view="full"):
    """DB row -> the object shape index.html's JS expects.
    view="slim" is the compact list used for the map and cards; "full" adds the
    detail fields (hours, services, status, phone, website, source); "admin" adds
    the editing fields."""
    out = {
        "id": r["id"],
        "name": r["name"] or {},
        "category": r["category"],
        "emoji": r["emoji"],
        "lat": float(r["latitude"]) if r["latitude"] is not None else None,
        "lng": float(r["longitude"]) if r["longitude"] is not None else None,
        "address": r["address"],
        "neighborhood": r["neighborhood"],
        "requirements": r["requirements"] or {},
        "aiSummary": r["ai_summary"] or {},
        "source": r.get("source", "curated"),
    }
    if view == "slim":
        return out
    out.update({
        "phone": r["phone"],
        "website": r["website"],
        "openStatus": r["open_status"] or {},
        "openNow": r["open_now"],
        "hours": format_hours(r["hours"]),
        "hoursRaw": r["hours"] or {},
        "services": r["services"] or {},
        "sourceUrl": r.get("source_url"),
        "programType": r.get("program_type"),
        "geoStatus": r.get("geo_status"),
    })
    if view == "admin":
        out.update({"active": r.get("active", True), "displayOrder": r.get("display_order"),
                    "updatedAt": r["updated_at"].isoformat() if r.get("updated_at") else None})
    return out


def question_to_page(q, staff=True):
    """DB row -> the question shape used by the admin inbox (and "my questions")."""
    out = {
        "id": q["id"],
        "timestamp": q["created_at"].astimezone(NYC).strftime("%m/%d %I:%M %p"),
        "created_at": q["created_at"].isoformat(),
        "lang": LANG_NAMES.get(q["language"], q["language"]),
        "langCode": q["language"],
        "topic": q.get("topic") or "resource",
        "question": q["question"],
        "status": STATUS_LABEL.get(q["status"], q["status"]),
        "statusCode": q["status"],
        "reply": q.get("reply") or "",
        "repliedAt": q["replied_at"].isoformat() if q.get("replied_at") else None,
        "resourceId": q.get("resource_id"),
    }
    if staff:
        out.update({
            "phone": q["phone"] or "None Provided",
            "assignedTo": q["assigned_to"],
            "adminNotes": q["admin_notes"],
            "askerName": q.get("asker_name"),
            "askerEmail": q.get("asker_email"),
        })
    return out


def public_user(u):
    return {"id": u["id"], "email": u["email"], "full_name": u["full_name"],
            "role": u["role"], "language_preference": u["language_preference"],
            "saved_resources": list(u["saved_resources"] or [])}


# ---------------------------------------------------------------- auth helpers
def current_user(conn):
    uid = session.get("user_id")
    if not uid:
        return None
    return conn.execute("SELECT * FROM users WHERE id=%s", (uid,)).fetchone()


def login_required(staff=False, admin=False):
    """staff=True: admin or counselor. admin=True: admin only. Enforced server-side."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            with db() as conn:
                user = current_user(conn)
                if not user:
                    return err("login_required", "Login required", 401)
                if admin and user["role"] != "admin":
                    return err("admin_only", "Admins only", 403)
                if staff and user["role"] not in STAFF_ROLES:
                    return err("staff_only", "Staff only", 403)
                return fn(conn, user, *a, **kw)
        return wrapper
    return deco


def body():
    return request.get_json(silent=True) or {}


# ---------------------------------------------------------------- caching / compression
def _static_version():
    h = hashlib.sha1()
    for p in sorted((HERE / "static").rglob("*")):
        if p.is_file():
            h.update(p.name.encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:10]


ASSET_VERSION = _static_version()
_COMPRESSIBLE = ("text/", "application/json", "application/javascript", "image/svg+xml")


@app.after_request
def compress(resp):
    """gzip text responses (the resource list shrinks ~10x)."""
    if (resp.status_code != 200 or "gzip" not in request.headers.get("Accept-Encoding", "")
            or "Content-Encoding" in resp.headers
            or not (resp.mimetype or "").startswith(_COMPRESSIBLE)):
        return resp
    resp.direct_passthrough = False
    data = resp.get_data()
    if len(data) < 1024:
        return resp
    resp.set_data(gzip.compress(data, 6))
    resp.headers["Content-Encoding"] = "gzip"
    resp.headers["Content-Length"] = str(len(resp.get_data()))
    resp.vary.add("Accept-Encoding")
    return resp


_cache = {}  # small per-process cache for the public resource list
CACHE_TTL = 60


def cached_json(key, build):
    hit = _cache.get(key)
    if hit and hit[0] > time.time():
        payload = hit[1]
    else:
        payload = app.json.dumps(build()).encode()
        _cache[key] = (time.time() + CACHE_TTL, payload)
    resp = Response(payload, mimetype="application/json")
    resp.add_etag()
    resp.headers["Cache-Control"] = f"public, max-age={CACHE_TTL}"
    return resp.make_conditional(request)


def invalidate_resource_cache():
    _cache.clear()


# ---------------------------------------------------------------- page
@app.get("/")
def index():
    html = (HERE / "index.html").read_text(encoding="utf-8").replace("__ASSET_VERSION__", ASSET_VERSION)
    resp = Response(html, mimetype="text/html")
    resp.add_etag()
    resp.headers["Cache-Control"] = "no-cache"
    return resp.make_conditional(request)


# ---------------------------------------------------------------- resources
RESOURCE_ORDER = "ORDER BY display_order NULLS LAST, category, name->>'en', id"


@app.get("/api/resources")
def list_resources():
    """Public list of active locations.
    ?view=slim  compact objects for the map/cards (default: full objects, as before)
    ?category=food  ?q=text  filter
    ?page=1&per_page=50  paginate -> {items, page, per_page, total, pages}"""
    view = "slim" if request.args.get("view") == "slim" else "full"
    category = request.args.get("category") or None
    if category and category not in CATEGORIES:
        return err("bad_category", "Unknown category", 400)
    q = (request.args.get("q") or "").strip()[:100]
    page = request.args.get("page", type=int)
    per_page = min(max(request.args.get("per_page", 50, type=int), 1), 200)

    def build():
        where, vals = ["active"], []
        if category:
            where.append("category=%s")
            vals.append(category)
        if q:
            where.append("(name::text ILIKE %s OR address ILIKE %s OR neighborhood ILIKE %s)")
            vals += [f"%{q}%"] * 3
        sql = f"FROM resources WHERE {' AND '.join(where)}"
        with db() as conn:
            if page:
                total = conn.execute(f"SELECT count(*) AS n {sql}", vals).fetchone()["n"]
                rows = conn.execute(f"SELECT * {sql} {RESOURCE_ORDER} LIMIT %s OFFSET %s",
                                    (*vals, per_page, (max(page, 1) - 1) * per_page)).fetchall()
                return {"items": [resource_to_page(r, view) for r in rows], "page": max(page, 1),
                        "per_page": per_page, "total": total, "pages": -(-total // per_page)}
            rows = conn.execute(f"SELECT * {sql} {RESOURCE_ORDER}", vals).fetchall()
        return [resource_to_page(r, view) for r in rows]

    return cached_json(("list", view, category, q, page, per_page), build)


@app.get("/api/resources/<rid>")
def get_resource(rid):
    with db() as conn:
        r = conn.execute("SELECT * FROM resources WHERE id=%s AND active", (rid,)).fetchone()
    if not r:
        return err("not_found", "Not found", 404)
    resp = jsonify(resource_to_page(r))
    resp.add_etag()
    resp.headers["Cache-Control"] = f"public, max-age={CACHE_TTL}"
    return resp.make_conditional(request)


# ---------------------------------------------------------------- admin: locations
@app.get("/api/admin/resources")
@login_required(admin=True)
def admin_list_resources(conn, user):
    q = (request.args.get("q") or "").strip()[:100]
    category = request.args.get("category") or None
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 25, type=int), 1), 200)
    where, vals = ["TRUE"], []
    if request.args.get("include_inactive") != "1":
        where.append("active")
    if category:
        where.append("category=%s")
        vals.append(category)
    if q:
        where.append("(id ILIKE %s OR name::text ILIKE %s OR address ILIKE %s)")
        vals += [f"%{q}%"] * 3
    sql = f"FROM resources WHERE {' AND '.join(where)}"
    total = conn.execute(f"SELECT count(*) AS n {sql}", vals).fetchone()["n"]
    rows = conn.execute(f"SELECT * {sql} {RESOURCE_ORDER} LIMIT %s OFFSET %s",
                        (*vals, per_page, (page - 1) * per_page)).fetchall()
    return jsonify(items=[resource_to_page(r, "admin") for r in rows], page=page,
                   per_page=per_page, total=total, pages=-(-total // per_page))


@app.get("/api/admin/resources/<rid>")
@login_required(admin=True)
def admin_get_resource(conn, user, rid):
    r = conn.execute("SELECT * FROM resources WHERE id=%s", (rid,)).fetchone()
    if not r:
        return err("not_found", "Not found", 404)
    return jsonify(resource_to_page(r, "admin"))


def _dupe_rows(conn):
    return conn.execute("SELECT id, category, name, address, latitude, longitude FROM resources").fetchall()


def _geo_status(d):
    return d.get("geo_status") if d.get("geo_status") in ("geocoded", "manual") else "manual"


@app.post("/api/admin/resources")
@login_required(admin=True)
def admin_create_resource(conn, user):
    d = body()
    try:
        clean, warnings = validate_resource(d)
    except ValidationError as e:
        return jsonify(error="; ".join(e.errors), errors=e.errors, code="invalid"), 400
    dups = find_duplicates(_dupe_rows(conn), clean)
    if dups and not d.get("force"):
        return jsonify(error="Looks like a duplicate", code="duplicate", duplicates=dups), 409
    clean.update(source="admin", geo_status=_geo_status(d))
    r = insert_resource(conn, clean, user["id"])
    invalidate_resource_cache()
    return jsonify(resource=resource_to_page(r, "admin"), warnings=warnings), 201


@app.patch("/api/admin/resources/<rid>")
@login_required(admin=True)
def admin_update_resource(conn, user, rid):
    old = conn.execute("SELECT * FROM resources WHERE id=%s", (rid,)).fetchone()
    if not old:
        return err("not_found", "Not found", 404)
    d = body()
    try:
        clean, warnings = validate_resource(d, partial=True)
    except ValidationError as e:
        return jsonify(error="; ".join(e.errors), errors=e.errors, code="invalid"), 400
    if {"name", "address", "latitude", "category"} & clean.keys() and not d.get("force"):
        dups = find_duplicates(_dupe_rows(conn), {**old, **clean}, ignore_id=rid)
        if dups:
            return jsonify(error="Looks like a duplicate", code="duplicate", duplicates=dups), 409
    if "latitude" in clean:
        clean["geo_status"] = _geo_status(d)
    r = update_resource(conn, rid, clean, user["id"])
    invalidate_resource_cache()
    return jsonify(resource=resource_to_page(r, "admin"), warnings=warnings)


@app.post("/api/admin/resources/import")
@login_required(admin=True)
def admin_import_resources(conn, user):
    """{data: "<csv or json text>" | [rows], format?: "csv"|"json", dry_run: true}"""
    d = body()
    data = d.get("data")
    try:
        rows = data if isinstance(data, list) else parse_bulk(data or "", d.get("format"))
    except (ValueError, TypeError) as e:
        return err("bad_file", f"Could not read the file: {e}", 400)
    if not rows:
        return err("empty", "No rows found", 400)
    if len(rows) > 500:
        return err("too_many", "Import at most 500 rows at a time", 400)
    dry = d.get("dry_run", True) is not False
    report = bulk_import(conn, rows, user["id"], dry_run=dry)
    if not dry:
        invalidate_resource_cache()
    counts = {}
    for e in report:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    return jsonify(dry_run=dry, counts=counts, rows=report)


@app.post("/api/admin/geocode")
@login_required(admin=True)
def admin_geocode(conn, user):
    address = (body().get("address") or "").strip()[:255]
    if len(address) < 5:
        return err("address_required", "Enter an address first", 400)
    g = geocode(address)
    if not g:
        return err("geocode_failed", "Could not find that address in the Bronx", 404)
    return jsonify(g)


# ---------------------------------------------------------------- auth
@app.post("/api/login")
def login():
    d = body()
    email = (d.get("email") or "").strip().lower()
    password = d.get("password") or ""
    with db() as conn:
        u = conn.execute("SELECT * FROM users WHERE lower(email)=%s", (email,)).fetchone()
    ok = False
    if u:
        try:
            ok = bcrypt.checkpw(password.encode(), u["password_hash"].encode())
        except ValueError:
            ok = False
    if not ok:
        return err("invalid_login", "Invalid email or password", 401)
    session.clear()
    session["user_id"] = u["id"]
    return jsonify(user=public_user(u))


@app.post("/api/signup")
def signup():
    d = body()
    email = (d.get("email") or "").strip().lower()
    password = d.get("password") or ""
    name = (d.get("full_name") or d.get("name") or "").strip()[:100]
    lang = d.get("language_preference") or "en"
    if not EMAIL_RE.match(email) or len(email) > 255:
        return err("bad_email", "Enter a valid email", 400)
    if len(password) < 8:
        return err("short_password", "Password must be at least 8 characters", 400)
    if not name:
        return err("name_required", "Enter your name", 400)
    if lang not in LANG_NAMES:
        lang = "en"
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()
    with db() as conn:
        if conn.execute("SELECT 1 FROM users WHERE lower(email)=%s", (email,)).fetchone():
            return err("email_taken", "An account with that email already exists", 409)
        u = conn.execute(
            "INSERT INTO users (id, email, password_hash, role, full_name, language_preference) "
            "VALUES (%s, %s, %s, 'user', %s, %s) RETURNING *",
            (new_id("usr"), email, pw_hash, name, lang)).fetchone()
    session.clear()
    session["user_id"] = u["id"]
    return jsonify(user=public_user(u)), 201


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
def me():
    with db() as conn:
        u = current_user(conn)
    return jsonify(user=public_user(u) if u else None)


@app.patch("/api/me")
@login_required()
def update_me(conn, user):
    """Remember the user's language on their profile."""
    lang = body().get("language_preference")
    if lang not in LANG_NAMES:
        return err("bad_language", "Unsupported language", 400)
    u = conn.execute("UPDATE users SET language_preference=%s WHERE id=%s RETURNING *",
                     (lang, user["id"])).fetchone()
    return jsonify(user=public_user(u))


# ---------------------------------------------------------------- saved resources
@app.get("/api/saved")
@login_required()
def get_saved(conn, user):
    return jsonify(saved_resources=list(user["saved_resources"]))


@app.post("/api/saved/<rid>")
@login_required()
def add_saved(conn, user, rid):
    if not conn.execute("SELECT 1 FROM resources WHERE id=%s", (rid,)).fetchone():
        return err("not_found", "Unknown resource", 404)
    row = conn.execute(
        "UPDATE users SET saved_resources = CASE WHEN %s = ANY(saved_resources) "
        "THEN saved_resources ELSE array_append(saved_resources, %s) END "
        "WHERE id=%s RETURNING saved_resources", (rid, rid, user["id"])).fetchone()
    return jsonify(saved_resources=list(row["saved_resources"]))


@app.delete("/api/saved/<rid>")
@login_required()
def remove_saved(conn, user, rid):
    row = conn.execute(
        "UPDATE users SET saved_resources = array_remove(saved_resources, %s) "
        "WHERE id=%s RETURNING saved_resources", (rid, user["id"])).fetchone()
    return jsonify(saved_resources=list(row["saved_resources"]))


# ---------------------------------------------------------------- questions
@app.post("/api/questions")
def submit_question():
    """Anyone can ask. topic: "resource" (help finding a service) or "app" (about Open Bx itself)."""
    d = body()
    text = (d.get("question") or "").strip()
    if not text:
        return err("question_required", "Question is required", 400)
    lang = d.get("lang") or d.get("language") or "en"
    lang = LANG_CODES.get(lang, lang)
    if lang not in LANG_NAMES:
        lang = "en"
    topic = d.get("topic") if d.get("topic") in TOPICS else "resource"
    phone = (d.get("phone") or "").strip()[:30] or None  # column is varchar(30)
    resource_id = (str(d.get("resource_id") or "")[:40]) or None
    with db() as conn:
        user = current_user(conn)
        if resource_id and not conn.execute("SELECT 1 FROM resources WHERE id=%s", (resource_id,)).fetchone():
            resource_id = None
        q = conn.execute(
            "INSERT INTO questions (id, language, question, phone, user_id, topic, resource_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *",
            (new_id("q"), lang, text[:4000], phone, user["id"] if user else None,
             topic, resource_id)).fetchone()
    return jsonify(question=question_to_page(q, staff=False)), 201


@app.get("/api/my-questions")
@login_required()
def my_questions(conn, user):
    rows = conn.execute("SELECT * FROM questions WHERE user_id=%s ORDER BY created_at DESC LIMIT 50",
                        (user["id"],)).fetchall()
    return jsonify([question_to_page(q, staff=False) for q in rows])


QUESTION_SELECT = ("SELECT q.*, u.full_name AS asker_name, u.email AS asker_email "
                   "FROM questions q LEFT JOIN users u ON u.id = q.user_id")


def _question_filters(args, topics):
    where, vals = ["q.topic = ANY(%s)"], [list(topics)]
    status = args.get("status", "all")
    if status == "open":
        where.append("q.status <> 'answered'")
    elif status in STATUS_LABEL:
        where.append("q.status = %s")
        vals.append(status)
    return " WHERE " + " AND ".join(where), vals


def _update_question(conn, user, qid, allowed_topics):
    q = conn.execute("SELECT * FROM questions WHERE id=%s", (qid,)).fetchone()
    if not q:
        return err("not_found", "Not found", 404)
    if (q.get("topic") or "resource") not in allowed_topics:
        return err("admin_only", "Admins only", 403)
    d = body()
    sets, vals = [], []
    if "status" in d:
        if d["status"] not in STATUS_LABEL:
            return err("bad_status", "Bad status", 400)
        sets.append("status=%s")
        vals.append(d["status"])
        if d["status"] != "pending" and "assigned_to" not in d:
            sets.append("assigned_to=COALESCE(assigned_to, %s)")
            vals.append(user["id"])
    if "admin_notes" in d:
        sets.append("admin_notes=%s")
        vals.append(str(d["admin_notes"])[:4000])
    if "reply" in d:
        reply = str(d["reply"] or "").strip()[:4000]
        if reply:
            sets += ["reply=%s", "replied_at=now()", "replied_by=%s"]
            vals += [reply, user["id"]]
            if "status" not in d:
                sets.append("status='answered'")
        else:
            sets += ["reply=''", "replied_at=NULL", "replied_by=NULL"]
    if "assigned_to" in d:
        if d["assigned_to"] and not conn.execute(
                "SELECT 1 FROM users WHERE id=%s AND role = ANY(%s)",
                (d["assigned_to"], list(STAFF_ROLES))).fetchone():
            return err("bad_assignee", "Can only assign to staff", 400)
        sets.append("assigned_to=%s")
        vals.append(d["assigned_to"] or None)
    if not sets:
        return err("nothing_to_update", "Nothing to update", 400)
    conn.execute(f"UPDATE questions SET {', '.join(sets)} WHERE id=%s", (*vals, qid))
    q = conn.execute(QUESTION_SELECT + " WHERE q.id=%s", (qid,)).fetchone()
    return jsonify(question=question_to_page(q))


def _topics_for(user):
    return TOPICS if user["role"] == "admin" else ("resource",)


@app.get("/api/questions")
@login_required(staff=True)
def list_questions(conn, user):
    """Staff queue. Counselors see resource-help questions only; admins see everything."""
    where, vals = _question_filters(request.args, _topics_for(user))
    rows = conn.execute(QUESTION_SELECT + where + " ORDER BY q.created_at", vals).fetchall()
    return jsonify([question_to_page(q) for q in rows])


@app.patch("/api/questions/<qid>")
@login_required(staff=True)
def update_question(conn, user, qid):
    return _update_question(conn, user, qid, _topics_for(user))


@app.get("/api/admin/questions")
@login_required(admin=True)
def admin_list_questions(conn, user):
    """Admin inbox: questions about the app and about resources.
    ?topic=all|app|resource  ?status=all|open|pending|in_progress|answered"""
    topic = request.args.get("topic", "all")
    topics = (topic,) if topic in TOPICS else TOPICS
    where, vals = _question_filters(request.args, topics)
    rows = conn.execute(QUESTION_SELECT + where + " ORDER BY q.created_at DESC LIMIT 500", vals).fetchall()
    return jsonify([question_to_page(q) for q in rows])


@app.patch("/api/admin/questions/<qid>")
@login_required(admin=True)
def admin_update_question(conn, user, qid):
    return _update_question(conn, user, qid, TOPICS)


# ---------------------------------------------------------------- search logs
@app.post("/api/search-logs")
def log_search():
    d = body()
    query = (d.get("query") or "").strip()[:500]
    if not query:
        return err("query_required", "query required", 400)
    try:
        count = int(d.get("results_count") or 0)
    except (TypeError, ValueError):
        count = 0
    cat = (str(d.get("category_matched") or "")[:30]) or None
    with db() as conn:
        row = conn.execute(
            "INSERT INTO search_logs (id, query, category_matched, results_count) "
            "VALUES (%s, %s, %s, %s) RETURNING id", (new_id("log"), query, cat, count)).fetchone()
    return jsonify(id=row["id"]), 201


@app.get("/api/search-logs")
@login_required(staff=True)
def list_search_logs(conn, user):
    rows = conn.execute(
        "SELECT id, searched_at, query, category_matched, results_count "
        "FROM search_logs ORDER BY searched_at DESC LIMIT 200").fetchall()
    for r in rows:
        r["searched_at"] = r["searched_at"].isoformat()
    return jsonify(rows)


if __name__ == "__main__":
    app.run(debug=True)
