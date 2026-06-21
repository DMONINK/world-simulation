"""
web/app.py — Flask application: dashboard, world map, clan pages, event
log, and the yearly chronicle. Also hosts the SocketIO server that pushes
live tick updates to connected browsers.

This module is the only place that imports both Flask and the simulation
engine — engine.py itself has no knowledge of Flask, so the coupling lives
entirely here via engine.set_tick_callback().
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO

import config
from database import db
from simulation import engine
from simulation import clans as clans_module
from simulation import world as world_module
from simulation import diplomacy
from simulation import characters as characters_module

app = Flask(__name__)
app.config["SECRET_KEY"] = config.FLASK_SECRET_KEY
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")


def _on_tick(summary):
    socketio.emit("tick_update", summary)


engine.set_tick_callback(_on_tick)


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    sim_year = db.get_meta("sim_year", 0)
    day_of_year = db.get_meta("sim_day_of_year", 0)
    summary = engine.build_summary(sim_year, day_of_year)
    ascii_map = _build_ascii_map()
    victory = db.get_meta("victory")
    return render_template("index.html", summary=summary, ascii_map=ascii_map,
                            clan_lore=clans_module.CLAN_LORE, victory=victory,
                            sim_year=sim_year)


def _build_ascii_map():
    """A tiny ASCII-art preview of clan territory for the dashboard
    (separate from the full interactive /map page)."""
    w, h = config.ASCII_MAP_WIDTH, config.ASCII_MAP_HEIGHT
    block_w = config.WORLD_WIDTH / w
    block_h = config.WORLD_HEIGHT / h
    glyphs = {name: lore["icon"] for name, lore in clans_module.CLAN_LORE.items()}
    grid = []
    for row in range(h):
        line = []
        sample_y = min(config.WORLD_HEIGHT - 1, int(row * block_h))
        for col in range(w):
            sample_x = min(config.WORLD_WIDTH - 1, int(col * block_w))
            region_id = sample_y * config.WORLD_WIDTH + sample_x
            region = db.get_region(region_id)
            owner = region["owner_clan"] if region else None
            line.append(glyphs.get(owner, "·"))
        grid.append("".join(line))
    return grid


@app.route("/api/summary")
def api_summary():
    sim_year = db.get_meta("sim_year", 0)
    day_of_year = db.get_meta("sim_day_of_year", 0)
    return jsonify(engine.build_summary(sim_year, day_of_year))


# ---------------------------------------------------------------------------
# WORLD MAP
# ---------------------------------------------------------------------------
@app.route("/map")
def map_page():
    return render_template("map.html", clan_lore=clans_module.CLAN_LORE)


@app.route("/api/map/grid")
def api_map_grid():
    """Downsampled 100x50 grid for canvas rendering. Each cell reports the
    owning clan's color and one representative region_id for click-to-inspect."""
    rw, rh = config.MAP_RENDER_WIDTH, config.MAP_RENDER_HEIGHT
    block_w = config.WORLD_WIDTH / rw
    block_h = config.WORLD_HEIGHT / rh
    colors = {name: lore["color"] for name, lore in clans_module.CLAN_LORE.items()}

    conn = db.get_connection()
    rows = conn.execute("SELECT id, x, y, owner_clan, biome FROM regions").fetchall()
    # Build a lookup grid in memory (40,000 rows is small).
    lookup = {}
    for r in rows:
        lookup[(r["x"], r["y"])] = (r["owner_clan"], r["biome"], r["id"])

    cells = []
    for ry in range(rh):
        sample_y = min(config.WORLD_HEIGHT - 1, int(ry * block_h))
        for rx in range(rw):
            sample_x = min(config.WORLD_WIDTH - 1, int(rx * block_w))
            owner, biome, region_id = lookup.get((sample_x, sample_y), (None, None, None))
            cells.append({
                "rx": rx, "ry": ry,
                "color": colors.get(owner, "#2a2a30"),
                "owner": owner,
                "region_id": region_id,
            })
    return jsonify({"width": rw, "height": rh, "cells": cells})


@app.route("/api/region/<int:region_id>")
def api_region_detail(region_id):
    region = db.get_region(region_id)
    if not region:
        return jsonify({"error": "not found"}), 404
    return jsonify(region)


# ---------------------------------------------------------------------------
# CLAN PAGE
# ---------------------------------------------------------------------------
@app.route("/clan/<clan_name>")
def clan_page(clan_name):
    if clan_name not in clans_module.CLAN_NAMES:
        return "Unknown clan", 404

    lore = clans_module.CLAN_LORE[clan_name]
    state = db.get_clan(clan_name)
    roster = db.get_characters_by_clan(clan_name)
    role_priority = {
        characters_module.ROLE_SUPREME_LEADER: 0,
        characters_module.ROLE_GENERAL: 1,
        characters_module.ROLE_CHAMPION: 2,
        characters_module.ROLE_INNOVATOR: 3,
        characters_module.ROLE_SHADOW_FIGURE: 4,
    }
    roster.sort(key=lambda c: (c["status"] == "dead", not c["is_legendary"], role_priority.get(c["role"], 9)))

    clan_events = db.get_events_filtered(clan=clan_name, limit=60)

    relations = []
    for other in clans_module.CLAN_NAMES:
        if other == clan_name:
            continue
        rel = db.get_relation(clan_name, other)
        relations.append({
            "clan": other,
            "icon": clans_module.CLAN_LORE[other]["icon"],
            "color": clans_module.CLAN_LORE[other]["color"],
            "status": diplomacy.relationship_label(rel["status"] if rel else "neutral"),
            "grudge": rel["grudge_score"] if rel else 0,
        })

    evolution_index = state["evolution_index"] if state else 0
    return render_template(
        "clan.html", clan_name=clan_name, lore=lore, state=state, roster=roster,
        events=clan_events, relations=relations, evolution_index=evolution_index,
        characters_module=characters_module,
    )


# ---------------------------------------------------------------------------
# EVENT LOG
# ---------------------------------------------------------------------------
@app.route("/events")
def events_page():
    clan_filter = request.args.get("clan") or None
    category_filter = request.args.get("category") or None
    search = request.args.get("q") or None
    events = db.get_events_filtered(clan=clan_filter, category=category_filter, search=search, limit=300)
    return render_template("events.html", events=events, clan_names=clans_module.CLAN_NAMES,
                            clan_lore=clans_module.CLAN_LORE,
                            categories=["MILITARY", "DISCOVERY", "POLITICAL", "NATURAL",
                                        "EVOLUTION", "CHARACTER", "BETRAYAL", "WONDER"],
                            current_clan=clan_filter, current_category=category_filter, current_search=search or "")


# ---------------------------------------------------------------------------
# CHRONICLE
# ---------------------------------------------------------------------------
@app.route("/chronicle")
def chronicle_page():
    summaries = db.get_all_yearly_summaries()
    summaries.sort(key=lambda s: s["sim_year"])
    return render_template("chronicle.html", summaries=summaries)


# ---------------------------------------------------------------------------
# ENTRYPOINT (used by main.py)
# ---------------------------------------------------------------------------
def create_app():
    return app, socketio
