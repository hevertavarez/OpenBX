-- Open Bx database schema (PostgreSQL). Matches the live database.
-- Columns marked "added" were introduced when wiring the page to the database;
-- columns marked "v2" were added with the locations / i18n / admin update.
-- migrate.py applies all of them idempotently (ADD COLUMN IF NOT EXISTS), and
-- every addition has a default, so older code keeps working.

CREATE TABLE users (
    id                  VARCHAR(40)  PRIMARY KEY,
    email               VARCHAR(255) NOT NULL UNIQUE,
    password_hash       VARCHAR(255) NOT NULL,              -- bcrypt
    role                VARCHAR(20)  NOT NULL DEFAULT 'user'
                        CHECK (role IN ('admin', 'counselor', 'user')),
    full_name           VARCHAR(100) NOT NULL,
    language_preference VARCHAR(5)   NOT NULL DEFAULT 'en',
    saved_resources     TEXT[]       NOT NULL DEFAULT '{}'  -- resource ids
);

CREATE TABLE resources (
    id            VARCHAR(40)  PRIMARY KEY,                 -- e.g. bx_food_1
    category      VARCHAR(30)  NOT NULL,                    -- food, health, rehab, education, jobs, ...
    emoji         VARCHAR(10),
    name          JSONB        NOT NULL,                    -- {"en": "...", "es": "...", "vi", "zh", "ar"}
    address       VARCHAR(255),
    neighborhood  VARCHAR(100),
    phone         VARCHAR(30),
    website       TEXT,
    longitude     NUMERIC(9,6),
    latitude      NUMERIC(9,6),
    open_status   JSONB,                                    -- {lang: "Open Today • ..."}
    requirements  JSONB,                                    -- {noID, noProofIncome, walkIn, spanish, wheelchair, transit}
    hours         JSONB,                                    -- {"mon": "09:00-15:30", ..., "sun": "closed"}
    ai_summary    JSONB,                                    -- {lang: "..."}
    services      JSONB,                                    -- {lang: ["...", ...]}
    open_now      BOOLEAN      NOT NULL DEFAULT TRUE,       -- added (page field openNow)
    display_order INTEGER,                                  -- added (page list order; NULL sorts last)
    source        VARCHAR(30)  NOT NULL DEFAULT 'curated',  -- v2: curated | nyc_open_data | admin | import
    source_id     TEXT,                                     -- v2: record id in the source dataset (FacDB uid)
    source_url    TEXT,                                     -- v2: dataset link shown as attribution
    program_type  VARCHAR(40),                              -- v2: key in program_types.py (imported rows)
    active        BOOLEAN      NOT NULL DEFAULT TRUE,       -- v2: FALSE = hidden from the public map
    geo_status    VARCHAR(20),                              -- v2: verified | source | geocoded | manual
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),      -- v2
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),      -- v2
    updated_by    VARCHAR(40)  REFERENCES users(id) ON DELETE SET NULL  -- v2: last admin editor
);
CREATE UNIQUE INDEX resources_source_uid ON resources (source, source_id) WHERE source_id IS NOT NULL;
CREATE INDEX resources_category ON resources (category);

CREATE TABLE questions (
    id          VARCHAR(40) PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    language    VARCHAR(5)  NOT NULL DEFAULT 'en',
    question    TEXT        NOT NULL,
    phone       VARCHAR(30),
    status      VARCHAR(20) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'in_progress', 'answered')),  -- pending is shown as "New"
    assigned_to VARCHAR(40) REFERENCES users(id) ON DELETE SET NULL,
    admin_notes TEXT        NOT NULL DEFAULT '',
    user_id     VARCHAR     REFERENCES users(id) ON DELETE SET NULL, -- added (asker, NULL for guests)
    topic       VARCHAR(20) NOT NULL DEFAULT 'resource',               -- v2: resource | app
    resource_id VARCHAR(40),                                           -- v2: location the question was asked from
    reply       TEXT        NOT NULL DEFAULT '',                       -- v2: shown to a logged-in asker
    replied_at  TIMESTAMPTZ,                                           -- v2
    replied_by  VARCHAR(40) REFERENCES users(id) ON DELETE SET NULL    -- v2
);
CREATE INDEX questions_user ON questions (user_id);

CREATE TABLE search_logs (
    id               VARCHAR(40) PRIMARY KEY,
    searched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    query            TEXT        NOT NULL,
    category_matched VARCHAR(30),
    results_count    INTEGER     NOT NULL DEFAULT 0,
    user_lat         NUMERIC(9,6),                          -- not written by the app
    user_lng         NUMERIC(9,6)                           -- not written by the app
);
