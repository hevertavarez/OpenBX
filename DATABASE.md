# Open Bx: how it works

`index.html` is served by a small Flask app (`server.py`) that reads and writes a
PostgreSQL database. No build step, no framework: one HTML page with vanilla JS,
Leaflet for the map, and JSON files for translations.

- JS changes from the first database wiring are marked `[DB]`.
- JS changes from the v2 update are marked `[I18N]`, `[MAP]`, `[MAP THEME]`,
  `[ADMIN]`, `[QUESTIONS]`, `[PERF]`. New CSS is in one block at the end of the
  `<style>` tag and only targets new `obx-*` classes, `#leafletMap` or the admin
  panel; the original styles are unchanged.

## Stack

| Piece | What |
|---|---|
| Page | `index.html`: HTML + CSS + vanilla JS. Leaflet 1.9.4 + Leaflet.markercluster 1.5.3 (unpkg CDN). |
| Server | `server.py`: Flask 3, psycopg 3, bcrypt, cookie sessions (`openbx_session`). `gunicorn server:app` on Render. |
| Database | Render Postgres (`resources`, `users`, `questions`, `search_logs`), see `schema.sql`. |
| Shared data code | `openbx_data.py` (validation, dedupe, geocoding, bulk import), `program_types.py` (translated text for imported locations). |
| Static files | `static/` (served by Flask with a 1-year cache; URLs carry `?v=<hash of static/>` so a deploy busts the cache). |

## Tables (see `schema.sql`)

| Table | What it holds |
|---|---|
| `resources` | Bronx locations. Text fields (`name`, `open_status`, `ai_summary`, `services`) are JSON keyed by language (`en`, `es`, `vi`, `zh`, `ar`). `hours` is per day: `{"mon": "09:00-15:30", ..., "sun": "closed"}`. v2 adds `source` (curated / nyc_open_data / admin / import), `source_id`, `source_url`, `program_type`, `active` (FALSE = hidden), `geo_status`, `created_at`, `updated_at`, `updated_by`. |
| `users` | Accounts (`admin`, `counselor`, `user`). `saved_resources` is a list of resource ids; `language_preference` remembers the chosen language. Passwords are bcrypt hashes. |
| `questions` | "Ask Question" submissions. `topic` is `resource` (finding help) or `app` (about Open Bx). `status` is `pending` (shown as "New") / `in_progress` / `answered`. `reply` is shown to the asker if they were logged in. |
| `search_logs` | Queries typed into the AI search box (query, matched category, result count). No location is stored. |

Schema changes: `python3 migrate.py` (idempotent, additive only, so older code keeps working).

## API

| Method & path | Who | Does |
|---|---|---|
| `GET /` | anyone | the page |
| `GET /api/resources` | anyone | active locations. `?view=slim` = compact list the page uses (map + cards); default = full objects (as before). `?category=`, `?q=`, `?page=&per_page=` (paginated: `{items, page, per_page, total, pages}`). gzip + ETag + `Cache-Control: max-age=60`. |
| `GET /api/resources/<id>` | anyone | one location with hours (`hoursRaw`), services, status, phone, website, source |
| `POST /api/signup`, `POST /api/login`, `POST /api/logout`, `GET /api/me` | anyone | session login |
| `PATCH /api/me` `{language_preference}` | logged in | remember the language |
| `GET/POST/DELETE /api/saved[/<id>]` | logged in | saved centers |
| `POST /api/questions` `{lang, question, phone, topic, resource_id}` | anyone | submit a question |
| `GET /api/my-questions` | logged in | your questions + replies |
| `GET /api/questions`, `PATCH /api/questions/<id>` | admin, counselor | staff queue (counselors: `resource` questions only) |
| `GET /api/admin/questions?topic=&status=`, `PATCH /api/admin/questions/<id>` `{status, reply, admin_notes}` | **admin** | the inbox: app questions + resource questions |
| `GET /api/admin/resources`, `GET /api/admin/resources/<id>` | **admin** | locations incl. hidden ones |
| `POST /api/admin/resources`, `PATCH /api/admin/resources/<id>` | **admin** | add / edit (validated, duplicate check; `force: true` to save anyway) |
| `POST /api/admin/resources/import` `{data, dry_run}` | **admin** | CSV/JSON bulk import (dry run first) |
| `POST /api/admin/geocode` `{address}` | **admin** | address -> coordinates for the form |
| `POST /api/search-logs` / `GET /api/search-logs` | anyone / staff | search log |

Errors are `{"error": "...", "code": "..."}`; the page translates the `code`.

## Admin model (who can do what)

- **No shared password any more.** The student's original page compared the
  "Admin Access" box against a password written in the page's JavaScript. That
  password is still visible in the public git history, but it no longer unlocks
  anything (it was never a real account password).
- Admin access is the normal account login + the `role` column:
  - **admin**: "🔒 Admin Access" opens the Admin Panel directly once logged in
    (no extra password): Questions inbox (app + resource questions, reply/status),
    Locations (add/edit/hide), Bulk Import.
  - **counselor**: "Admin Access" opens a Counselor Question Queue with resource-help
    questions only. Counselors cannot see app questions or edit locations.
  - **user / guest**: "Admin Access" shows the login box (guests) or "no admin access".
- Every check is on the server (`login_required(admin=True)` / `staff=True` in
  `server.py`); hiding buttons in the page is only for convenience.
- To rotate a password: `python3 set_password.py admin@openbx.org` (prompts, stores a bcrypt hash).

## Demo logins (password `demo1234` for all)

- `admin@openbx.org`: Rosa Martinez, admin
- `counseling@openbx.org`: David Chen, counselor
- `community_user@gmail.com`: Maria Santos, user

**These passwords are public (this file and `seed_from_page.py` are in a public
repo), so anyone can log in as the demo admin and edit locations.** Change the
admin and counselor passwords with `set_password.py` before real use.

## Locations: data sources and licensing

| Source | Rows | License / attribution |
|---|---|---|
| Open Bx team (hand-curated by the student, `source = curated`) | 8 | n/a |
| NYC Open Data: NYC Department of City Planning **Facilities Database (FacDB)**, dataset `ji82-xba5` (https://data.cityofnewyork.us/d/ji82-xba5). FacDB compiles agency lists: Food Bank For NYC pantries & soup kitchens, NYS DOH hospitals and clinics, NYS OASAS treatment programs, NYPL branches, city adult-literacy and immigrant programs, DOE Pathways to Graduation, SBS Workforce1, HRA centers, NYCHA community centers, DHS drop-in centers. | 309 | NYC Open Data Terms of Use: free to use; attribution requested. Shown as "Location data: NYC Open Data (NYC Dept. of City Planning)" in the map's attribution bar and "Listing from NYC Open Data" on each imported location. |
| Neighborhood names: NYC DCP 2020 Neighborhood Tabulation Areas (`9nt8-h7nd`) | (lookup) | NYC Open Data Terms of Use |
| Bronx outline: NYC DCP Borough Boundaries (`gthc-hcne`), simplified into `static/bronx-boundary.json` | 1 | NYC Open Data Terms of Use |
| Geocoding (audit, admin form, bulk import): NYC GeoSearch (NYC Planning Labs, built on the city's PAD address file), then OpenStreetMap Nominatim as a fallback | – | GeoSearch: free, no key. Nominatim: ODbL data, max 1 request/second, identified User-Agent (only used for occasional admin/audit lookups). |
| Map tiles: OpenStreetMap standard tiles | – | "© OpenStreetMap contributors" (shown on the map), OSM tile usage policy (fine at this traffic). |

Imported rows only have English names (organization names are proper nouns; where
a source name was not descriptive, e.g. a NYCHA development name, a translated
suffix such as "Community Center (NYCHA)" was added in all languages). Their
description, services and "call ahead to confirm hours" line are filled in all
five languages from `program_types.py`. Imported rows have no hours, phone or
requirements; the page says "call ahead" instead of guessing.

### Run the importers

```bash
python3 migrate.py                                   # schema (idempotent)
python3 import_nyc_open_data.py                      # dry run: prints what would change
python3 import_nyc_open_data.py --apply              # insert/update from NYC Open Data
python3 import_resources.py my_locations.csv         # CSV/JSON bulk import, dry run
python3 import_resources.py my_locations.csv --apply # (see sample_locations.csv for columns)
```

NYC Open Data import rules: Bronx only; categories the app already has; skips
specialist clinics (dialysis, surgery, imaging...), Rikers Island programs and
rows without a Bronx ZIP; merges duplicates inside the source (same category and
address, or < 40 m apart with a similar name); skips anything that duplicates a
curated/admin location (curated rows stay authoritative); re-runs update rows from
the source unless an admin edited them; never deletes. Known bad source rows are
corrected in `SOURCE_FIXES`.

All inputs (admin form, CSV/JSON import, importer) go through
`openbx_data.validate_resource`: English name, valid category, address, and
coordinates inside the Bronx are required; swapped lat/lng are fixed; a missing
Bronx ZIP is a warning.

### Suspicious-locations report

```bash
python3 audit_locations.py                 # bounds, swapped/missing coords, duplicates, shared points
python3 audit_locations.py --geocode       # + compares curated/admin pins with their geocoded address
python3 audit_locations.py --geocode-all   # + every row
python3 audit_locations.py --geocode --fix # moves pins that are > 150 m from their address
python3 audit_locations.py --geocode-all --csv reports/location_audit.csv
```

`reports/location_audit.csv` is the latest run (0 errors, 0 warnings; the "info"
rows are different programs in the same building).

## Map

- Initial view: the Bronx bounding box; panning is limited to the Bronx area (`maxBounds`), min zoom 10.
- Pins are clustered (Leaflet.markercluster); the active pin is highlighted; the
  list view renders 24 cards at a time ("Show more").
- The page loads a compact list (`?view=slim`, ~40 KB gzipped for 317 locations)
  and fetches one location's details when it is opened.

### Light map + Bronx imagery: one switch

In `index.html`:

```js
const MAP_THEME_CONFIG = { enabled: true };
```

- `true`: OpenStreetMap tiles softened by a CSS filter on `#leafletMap.obx-light .leaflet-tile-pane`,
  a dashed Bronx outline, and 9 📷 photo markers. Photos load only when a photo
  popup is opened (`loading="lazy"`, 560 px JPEGs, 23-80 KB each); the outline and
  photo list load after the page is ready. Nothing outside the map changes.
- `false`: the student's original Esri street map, no outline, no photos.
- (CARTO Positron now returns an "API key required" tile, so it is not used.)

Photos (`static/img/bronx/`, metadata and credits in `static/bronx-photos.json`, credit shown in each popup):

| Photo | Author | License |
|---|---|---|
| Yankee Stadium | Paulo JC Nogueira | CC BY-SA 3.0 |
| Grand Concourse | MMZach | CC BY-SA 3.0 |
| NYBG Haupt Conservatory | Acroterion | CC BY-SA 4.0 |
| Arthur Avenue Retail Market | Joe Mabel | CC BY-SA 4.0 |
| Orchard Beach | Bebo2good1 | CC BY-SA 4.0 |
| City Island and Hart Island | Doc Searls | CC BY 2.0 |
| Bronx Library Center | Julian A. Henderson | CC BY-SA 3.0 |
| Bronx River in the NYBG | Krzysztof Ziarnek, Kenraiz | CC BY-SA 4.0 |
| Hall of Fame for Great Americans | Hugo L. González | CC BY-SA 4.0 |

All from Wikimedia Commons (links in `bronx-photos.json`), resized (noted in the credit).

## Languages (i18n)

- UI text: `static/i18n/en.json`, `es.json`, `vi.json`, `zh.json`, `ar.json`
  (same keys in every file). HTML uses `data-i18n="key"` (text) and
  `data-i18n-placeholder` / `-title` / `-aria-label` / `-alt`; JS uses `t('key', {vars})`.
  Missing keys fall back to English.
- Numbers, dates, times and weekday names use `Intl` in the chosen language.
- The choice is saved in `localStorage` and, when logged in, on the user's
  profile. `<html lang>` follows the language; Arabic sets `dir="rtl"` (the map
  itself stays left-to-right).
- Location content uses the database translation for the language, else English
  (marked `lang="en"`).
- Map tiles: OpenStreetMap raster tiles only have local (English) street labels;
  no free keyless raster provider offers per-language labels, so street names on
  the map stay English. Everything we draw on the map (popups, buttons, zoom
  tooltips, attribution text) is translated.
- `python3 check_i18n.py` checks that every language file is complete, that every
  key used in `index.html` exists, and that no visible text in `index.html` is
  missing a `data-i18n` key. `--db` lists location content without translations.

### Add a language

1. Copy `static/i18n/en.json` to `static/i18n/<code>.json` and translate every value
   (keep `{placeholders}`).
2. In `index.html` add the code to `SUPPORTED_LANGS` (and `RTL_LANGS` if
   right-to-left), a locale in `LOCALES`, an `<option>` in `#languageSelect`
   and in `#questionLang`, and `LANG_SELECT_VALUE`.
3. In `server.py` add it to `LANG_CODES`; in `openbx_data.py` / `program_types.py`
   add it to `LANGS` and translate the program-type texts; re-run
   `import_nyc_open_data.py --apply`.
4. Run `python3 check_i18n.py`.

## Run locally

```bash
pip install -r requirements.txt
export DATABASE_URL='postgresql://...'      # never commit this
export SECRET_KEY='any-long-random-string'  # optional locally
python3 migrate.py
python3 -m flask --app server run           # http://127.0.0.1:5000
```

Production (Render): start command `gunicorn server:app`, with `DATABASE_URL` and
`SECRET_KEY` set as environment variables. No new environment variables.

## Seeding

`python3 seed_from_page.py` (with `DATABASE_URL` set) loads `page_resources.json`
(the resource list that used to be hard-coded in `index.html`) into `resources`
and sets the demo passwords. Safe to re-run: existing rows win.
