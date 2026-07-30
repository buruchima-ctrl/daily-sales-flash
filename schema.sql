-- Daily Sales Flash — SQLite schema (PRD §3). Stdlib sqlite3 only.
-- One row per date in `calendar`; date × entity grain in the fact tables.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS flash_archive;
DROP TABLE IF EXISTS plan_day;
DROP TABLE IF EXISTS sales_day;
DROP TABLE IF EXISTS calendar;
DROP TABLE IF EXISTS stores;

-- Entities: the 25 Lumière stores (ported from Leases/src/roster.py) plus one
-- virtual ECOM channel. `entity_id` = lease_id for stores, 'ECOM' for e-comm.
CREATE TABLE stores (
    entity_id        TEXT PRIMARY KEY,
    store_number     INTEGER,              -- NULL for ECOM
    name             TEXT NOT NULL,
    channel          TEXT NOT NULL,        -- 'STORE' | 'ECOM'
    region           TEXT NOT NULL,        -- 5 US regions, or 'ECOM'
    open_date        TEXT NOT NULL,        -- ISO; drives comp eligibility (BR-2)
    close_date       TEXT,                 -- ISO or NULL
    remodel_start    TEXT,                 -- ISO or NULL (comp-excluded window)
    remodel_end      TEXT,                 -- ISO or NULL (NULL = still down)
    rentable_sf      INTEGER,
    target_sales_psf REAL,
    annual_volume    REAL NOT NULL         -- synthesized base-year anchor
);

-- One row per calendar date. ly_aligned_date is MATERIALIZED at seed time so
-- every downstream comp is a join, not a computation (BR-5 applied to dates).
CREATE TABLE calendar (
    date            TEXT PRIMARY KEY,      -- ISO YYYY-MM-DD
    fiscal_year     INTEGER NOT NULL,
    period          INTEGER NOT NULL,      -- 1..12
    week            INTEGER NOT NULL,      -- 1..52/53 (fiscal week)
    day_of_week     INTEGER NOT NULL,      -- 1=Sun .. 7=Sat
    holiday_code    TEXT,                  -- NULL if no holiday
    ly_aligned_date TEXT NOT NULL,         -- same fiscal week + DOW, prior FY
    restated        INTEGER NOT NULL DEFAULT 0   -- 53-week NRF shift in effect
);
CREATE INDEX idx_calendar_fy ON calendar(fiscal_year, period, week);

-- Date × entity actuals. A MISSING (unposted) store has NO row (BR-3: missing,
-- never zero). posted_at is materialized from the data, never now() (NFR-2).
CREATE TABLE sales_day (
    date             TEXT NOT NULL,
    entity_id        TEXT NOT NULL,
    net_sales        REAL NOT NULL,        -- for ECOM: = demand_sales (BR-4)
    transactions     INTEGER NOT NULL,
    units            INTEGER NOT NULL,
    demand_sales     REAL,                 -- ECOM only
    shipped_sales    REAL,                 -- ECOM only (settled)
    returns_recorded REAL,                 -- ECOM only (settled)
    posted_at        TEXT NOT NULL,
    PRIMARY KEY (date, entity_id),
    FOREIGN KEY (entity_id) REFERENCES stores(entity_id),
    FOREIGN KEY (date) REFERENCES calendar(date)
);
CREATE INDEX idx_sales_entity ON sales_day(entity_id, date);

CREATE TABLE plan_day (
    date        TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    plan_sales  REAL NOT NULL,
    PRIMARY KEY (date, entity_id),
    FOREIGN KEY (entity_id) REFERENCES stores(entity_id),
    FOREIGN KEY (date) REFERENCES calendar(date)
);

-- One row per generated flash version. Immutable once written (BR-7);
-- restatements append version+1 with a reason string.
CREATE TABLE flash_archive (
    date         TEXT NOT NULL,
    version      INTEGER NOT NULL,
    computed_json TEXT NOT NULL,
    reason       TEXT,                     -- restatement reason (version>1)
    created_at   TEXT NOT NULL,            -- from data, never now()
    PRIMARY KEY (date, version)
);
