"""
database/db.py — SQLite persistence layer.

Every tick of the simulation can be safely interrupted (Replit free tier
restarts containers). This module is responsible for making sure that when
the process comes back up, the rest of the app can reconstruct everything
exactly where it left off: world regions, clan state, the character roster,
the event log, the relations ledger, and the yearly chronicle.

All write functions commit immediately. Reads return plain dicts/lists so
the rest of the codebase never has to touch a `sqlite3.Row` directly.
"""

import sqlite3
import json
import os
import threading

import config

_LOCAL = threading.local()


def get_connection():
    """Each thread gets its own sqlite3 connection (sqlite3 objects are not
    thread-safe to share)."""
    if not hasattr(_LOCAL, "conn"):
        os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
        conn = sqlite3.connect(config.DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        _LOCAL.conn = conn
    return _LOCAL.conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS regions (
    id INTEGER PRIMARY KEY,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    name TEXT,
    biome TEXT,
    elevation REAL,
    resources TEXT,            -- JSON list, up to 3
    owner_clan TEXT,           -- NULL/'' = neutral
    population_density INTEGER DEFAULT 0,
    fortification INTEGER DEFAULT 0,
    is_rare_node INTEGER DEFAULT 0,
    rare_node_resource TEXT,
    rare_node_discovered_by TEXT,  -- JSON list of clan names
    is_last_bastion_for TEXT,      -- clan name if this region is a hidden stronghold
    last_bastion_discovered_by TEXT  -- JSON list of clan names that found it
);
CREATE INDEX IF NOT EXISTS idx_regions_owner ON regions(owner_clan);

CREATE TABLE IF NOT EXISTS clans (
    name TEXT PRIMARY KEY,
    population INTEGER,
    peak_population INTEGER,
    territory_count INTEGER,
    evolution_index INTEGER DEFAULT 0,
    is_eliminated INTEGER DEFAULT 0,
    is_last_bastion INTEGER DEFAULT 0,
    rebuild_momentum_until INTEGER DEFAULT 0,  -- sim_year the bonus expires
    grief_until INTEGER DEFAULT 0,             -- Aura Knights leader-death penalty expiry
    extra_state TEXT  -- JSON blob: anything clan-specific that doesn't need its own column
);

CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY,
    clan TEXT,
    name TEXT,
    role TEXT,
    birth_year INTEGER,
    death_year INTEGER,
    status TEXT,           -- alive, dead, crippled, captured, defected, legendary
    is_legendary INTEGER DEFAULT 0,
    notable_deeds TEXT,    -- JSON list of strings
    injuries TEXT          -- JSON list of strings
);
CREATE INDEX IF NOT EXISTS idx_characters_clan ON characters(clan);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sim_year INTEGER,
    sim_day INTEGER,
    category TEXT,
    severity TEXT,         -- minor, major, catastrophic
    clans_involved TEXT,   -- JSON list
    title TEXT,
    narrative TEXT,
    region_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_events_year ON events(sim_year);
CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);

CREATE TABLE IF NOT EXISTS relations (
    clan_a TEXT,
    clan_b TEXT,
    status TEXT,           -- ally, neutral, cold_war, at_war, blood_war
    grudge_score INTEGER DEFAULT 0,
    history TEXT,           -- JSON list of {year, type, note}
    PRIMARY KEY (clan_a, clan_b)
);

CREATE TABLE IF NOT EXISTS yearly_summaries (
    sim_year INTEGER PRIMARY KEY,
    title TEXT,
    embed_json TEXT,
    posted INTEGER DEFAULT 0
);
"""


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()


# ---------------------------------------------------------------------------
# META / TIME
# ---------------------------------------------------------------------------
def set_meta(key, value):
    conn = get_connection()
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, json.dumps(value)),
    )
    conn.commit()


def get_meta(key, default=None):
    conn = get_connection()
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    if row is None:
        return default
    return json.loads(row["value"])


# ---------------------------------------------------------------------------
# REGIONS
# ---------------------------------------------------------------------------
def bulk_insert_regions(region_rows):
    """region_rows: list of tuples matching the regions column order
    (excluding id, which is the region's index and primary key)."""
    conn = get_connection()
    conn.executemany(
        """INSERT OR REPLACE INTO regions
           (id, x, y, name, biome, elevation, resources, owner_clan,
            population_density, fortification, is_rare_node, rare_node_resource,
            rare_node_discovered_by, is_last_bastion_for, last_bastion_discovered_by)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        region_rows,
    )
    conn.commit()


def update_region_owner(region_id, owner_clan, population_density=None, fortification=None):
    conn = get_connection()
    if population_density is not None and fortification is not None:
        conn.execute(
            "UPDATE regions SET owner_clan=?, population_density=?, fortification=? WHERE id=?",
            (owner_clan, population_density, fortification, region_id),
        )
    else:
        conn.execute("UPDATE regions SET owner_clan=? WHERE id=?", (owner_clan, region_id))
    conn.commit()


def set_last_bastion(region_id, clan_name):
    conn = get_connection()
    conn.execute(
        "UPDATE regions SET owner_clan=?, is_last_bastion_for=?, fortification=9 WHERE id=?",
        (clan_name, clan_name, region_id),
    )
    conn.commit()


def get_last_bastion_region(clan_name):
    conn = get_connection()
    row = conn.execute("SELECT * FROM regions WHERE is_last_bastion_for=?", (clan_name,)).fetchone()
    return _region_row_to_dict(row) if row else None


def mark_last_bastion_discovered(region_id, clan_name):
    region = get_region(region_id)
    discovered = region["last_bastion_discovered_by"]
    if clan_name not in discovered:
        discovered.append(clan_name)
    conn = get_connection()
    conn.execute(
        "UPDATE regions SET last_bastion_discovered_by=? WHERE id=?",
        (json.dumps(discovered), region_id),
    )
    conn.commit()


def get_all_regions():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM regions").fetchall()
    return [_region_row_to_dict(r) for r in rows]


def get_region(region_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM regions WHERE id=?", (region_id,)).fetchone()
    return _region_row_to_dict(row) if row else None


def get_regions_owned_by(clan_name):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM regions WHERE owner_clan=?", (clan_name,)).fetchall()
    return [_region_row_to_dict(r) for r in rows]


def get_neutral_regions_near(cx, cy, radius):
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM regions WHERE owner_clan IS NULL
           AND x BETWEEN ? AND ? AND y BETWEEN ? AND ?""",
        (cx - radius, cx + radius, cy - radius, cy + radius),
    ).fetchall()
    return [_region_row_to_dict(r) for r in rows]


def count_regions_owned_by(clan_name):
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) c FROM regions WHERE owner_clan=?", (clan_name,)).fetchone()
    return row["c"]


def _region_row_to_dict(row):
    d = dict(row)
    d["resources"] = json.loads(d["resources"]) if d["resources"] else []
    d["rare_node_discovered_by"] = json.loads(d["rare_node_discovered_by"]) if d["rare_node_discovered_by"] else []
    d["last_bastion_discovered_by"] = json.loads(d["last_bastion_discovered_by"]) if d["last_bastion_discovered_by"] else []
    return d


# ---------------------------------------------------------------------------
# CLANS
# ---------------------------------------------------------------------------
def upsert_clan(clan_dict):
    conn = get_connection()
    conn.execute(
        """INSERT INTO clans (name, population, peak_population, territory_count,
                evolution_index, is_eliminated, is_last_bastion, rebuild_momentum_until,
                grief_until, extra_state)
           VALUES (?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(name) DO UPDATE SET
                population=excluded.population,
                peak_population=excluded.peak_population,
                territory_count=excluded.territory_count,
                evolution_index=excluded.evolution_index,
                is_eliminated=excluded.is_eliminated,
                is_last_bastion=excluded.is_last_bastion,
                rebuild_momentum_until=excluded.rebuild_momentum_until,
                grief_until=excluded.grief_until,
                extra_state=excluded.extra_state
        """,
        (
            clan_dict["name"], clan_dict["population"], clan_dict["peak_population"],
            clan_dict["territory_count"], clan_dict["evolution_index"],
            int(clan_dict["is_eliminated"]), int(clan_dict["is_last_bastion"]),
            clan_dict["rebuild_momentum_until"], clan_dict["grief_until"],
            json.dumps(clan_dict.get("extra_state", {})),
        ),
    )
    conn.commit()


def get_all_clans():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM clans").fetchall()
    return [_clan_row_to_dict(r) for r in rows]


def get_clan(name):
    conn = get_connection()
    row = conn.execute("SELECT * FROM clans WHERE name=?", (name,)).fetchone()
    return _clan_row_to_dict(row) if row else None


def _clan_row_to_dict(row):
    d = dict(row)
    d["is_eliminated"] = bool(d["is_eliminated"])
    d["is_last_bastion"] = bool(d["is_last_bastion"])
    d["extra_state"] = json.loads(d["extra_state"]) if d["extra_state"] else {}
    return d


# ---------------------------------------------------------------------------
# CHARACTERS
# ---------------------------------------------------------------------------
def insert_character(c):
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO characters (clan, name, role, birth_year, death_year, status,
                is_legendary, notable_deeds, injuries)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            c["clan"], c["name"], c["role"], c["birth_year"], c.get("death_year"),
            c["status"], int(c.get("is_legendary", False)),
            json.dumps(c.get("notable_deeds", [])), json.dumps(c.get("injuries", [])),
        ),
    )
    conn.commit()
    return cur.lastrowid


def update_character(char_id, **fields):
    if not fields:
        return
    conn = get_connection()
    cols, vals = [], []
    for k, v in fields.items():
        if k in ("notable_deeds", "injuries"):
            v = json.dumps(v)
        if k == "is_legendary":
            v = int(v)
        cols.append(f"{k}=?")
        vals.append(v)
    vals.append(char_id)
    conn.execute(f"UPDATE characters SET {', '.join(cols)} WHERE id=?", vals)
    conn.commit()


def get_characters_by_clan(clan_name, alive_only=False):
    conn = get_connection()
    if alive_only:
        rows = conn.execute(
            "SELECT * FROM characters WHERE clan=? AND status NOT IN ('dead')", (clan_name,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM characters WHERE clan=?", (clan_name,)).fetchall()
    return [_char_row_to_dict(r) for r in rows]


def get_character(char_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM characters WHERE id=?", (char_id,)).fetchone()
    return _char_row_to_dict(row) if row else None


def _char_row_to_dict(row):
    d = dict(row)
    d["is_legendary"] = bool(d["is_legendary"])
    d["notable_deeds"] = json.loads(d["notable_deeds"]) if d["notable_deeds"] else []
    d["injuries"] = json.loads(d["injuries"]) if d["injuries"] else []
    return d


# ---------------------------------------------------------------------------
# EVENTS
# ---------------------------------------------------------------------------
def insert_event(sim_year, sim_day, category, severity, clans_involved, title, narrative, region_id=None):
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO events (sim_year, sim_day, category, severity, clans_involved, title, narrative, region_id)
           VALUES (?,?,?,?,?,?,?,?)""",
        (sim_year, sim_day, category, severity, json.dumps(clans_involved), title, narrative, region_id),
    )
    conn.commit()
    return cur.lastrowid


def get_recent_events(limit=20):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [_event_row_to_dict(r) for r in rows]


def get_events_for_year(sim_year, limit=2000):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM events WHERE sim_year=? ORDER BY id ASC LIMIT ?", (sim_year, limit)
    ).fetchall()
    return [_event_row_to_dict(r) for r in rows]


def get_events_filtered(clan=None, category=None, search=None, limit=200):
    conn = get_connection()
    query = "SELECT * FROM events WHERE 1=1"
    params = []
    if clan:
        query += " AND clans_involved LIKE ?"
        params.append(f'%"{clan}"%')
    if category:
        query += " AND category = ?"
        params.append(category)
    if search:
        query += " AND (narrative LIKE ? OR title LIKE ?)"
        params.append(f"%{search}%")
        params.append(f"%{search}%")
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [_event_row_to_dict(r) for r in rows]


def _event_row_to_dict(row):
    d = dict(row)
    d["clans_involved"] = json.loads(d["clans_involved"]) if d["clans_involved"] else []
    return d


# ---------------------------------------------------------------------------
# RELATIONS LEDGER
# ---------------------------------------------------------------------------
def _ordered_pair(a, b):
    return tuple(sorted([a, b]))


def upsert_relation(clan_a, clan_b, status, grudge_score, history):
    a, b = _ordered_pair(clan_a, clan_b)
    conn = get_connection()
    conn.execute(
        """INSERT INTO relations (clan_a, clan_b, status, grudge_score, history)
           VALUES (?,?,?,?,?)
           ON CONFLICT(clan_a, clan_b) DO UPDATE SET
                status=excluded.status, grudge_score=excluded.grudge_score, history=excluded.history""",
        (a, b, status, grudge_score, json.dumps(history)),
    )
    conn.commit()


def get_relation(clan_a, clan_b):
    a, b = _ordered_pair(clan_a, clan_b)
    conn = get_connection()
    row = conn.execute("SELECT * FROM relations WHERE clan_a=? AND clan_b=?", (a, b)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["history"] = json.loads(d["history"]) if d["history"] else []
    return d


def get_all_relations():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM relations").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["history"] = json.loads(d["history"]) if d["history"] else []
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# YEARLY SUMMARIES (chronicle)
# ---------------------------------------------------------------------------
def save_yearly_summary(sim_year, title, embed_dict, posted=False):
    conn = get_connection()
    conn.execute(
        """INSERT INTO yearly_summaries (sim_year, title, embed_json, posted)
           VALUES (?,?,?,?)
           ON CONFLICT(sim_year) DO UPDATE SET title=excluded.title, embed_json=excluded.embed_json, posted=excluded.posted""",
        (sim_year, title, json.dumps(embed_dict), int(posted)),
    )
    conn.commit()


def get_all_yearly_summaries():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM yearly_summaries ORDER BY sim_year ASC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["embed_json"] = json.loads(d["embed_json"]) if d["embed_json"] else {}
        out.append(d)
    return out


def is_db_initialized():
    """Returns True if the world has already been generated (i.e. this is a
    resume, not a fresh start)."""
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) c FROM regions").fetchone()
    return row["c"] > 0
