# ⚔️ World Simulation

A fully automated civilization simulation: six fantasy clans evolve, expand, fight,
ally, and betray each other across a procedurally generated 200×200 world, with a
live web dashboard and (optionally) yearly chronicle posts to Discord.

## Running it on Replit

1. **Import this project** into a new Replit (Python template).
2. **Install dependencies** — Replit should auto-install from `requirements.txt` on
   first run. If not: `pip install -r requirements.txt`.
3. **(Optional) Set up Discord updates:**
   - In your Discord server, create a webhook (Server Settings → Integrations → Webhooks).
   - Copy the webhook URL.
   - In Replit, open **Secrets** (the lock icon) and add:
     - Key: `DISCORD_WEBHOOK_URL`
     - Value: *(paste your webhook URL)*
   - If you skip this, the simulation runs exactly the same — the yearly chronicle
     just won't post to Discord. You can still read it on the `/chronicle` page.
4. **Click Run.** This executes `main.py`, which:
   - Generates the world on first run (takes under a second).
   - Starts the simulation ticking once per real second in a background thread.
   - Starts the web dashboard.
5. Open the web preview — you'll land on the dashboard. Use the nav bar for the
   **Map**, **Events** log, and **Chronicle**.

The simulation **persists to SQLite** (`database/simulation.db`) and resumes exactly
where it left off if Replit restarts your container — it will not regenerate the
world or reset any clan's progress.

## Time scale

- 1 real second = 609 simulated minutes (~10 hours)
- 1 simulated year ≈ 14.4 real minutes
- Year 100 ≈ 24 real hours of uptime
- Year 300 (the earliest a clan can actually be eliminated) ≈ 3 real days of uptime

## Pages

| Route | What it shows |
|---|---|
| `/` | Live dashboard: clan status cards, an ASCII world preview, a live event ticker |
| `/map` | The full 200×200 world map (rendered at reduced resolution), click any cell for details |
| `/clan/<name>` | A clan's lore, traits, weaknesses, evolution progress, named character roster, relations, and recent history |
| `/events` | The full searchable/filterable event log |
| `/chronicle` | Every completed year's story, written like a history book |

## A few implementation notes (read if something seems different from the original spec)

This was built faithfully to the original design brief, with a small number of
deliberate engineering calls where the brief's literal wording would have produced
a worse simulation in practice. Each is called out here for transparency:

- **AI decisions and ambient events resolve once per simulated day, not once per
  609-minute tick.** Taken completely literally, "every tick" would mean roughly
  863 AI decisions and event rolls per clan per simulated year — at the brief's own
  probabilities, that's hundreds of wars/betrayals/assassinations per clan per year,
  which reads as chaos rather than a chronicle and produces an unmanageable event
  log over a multi-century run. Daily resolution keeps the same probabilities and
  randomness but at a pace that actually produces yearly chronicles worth reading.
  The 609-minute tick itself, the 525,600-minute year, and the once-per-sim-year
  Discord post are all implemented exactly as specified.
- **A clan can take at most one "dramatic" action (declare war, betray an alliance,
  or use its clan-special ability) per simulated year.** Without this, a clan whose
  personality favors a special action (Void Reapers' assassinations, especially)
  would attempt it dozens of times against the same target in a single year.
  Routine actions (expand, fortify, research, recruit, raid) are unaffected.
- **`numpy` was added** to `requirements.txt` (the only dependency beyond the
  brief's original four) purely to generate fast, naturally-clustered biome
  placement across 40,000 regions. No paid APIs or external services were added —
  it's a free, standard library install.
- **Population growth is its own daily process**, separate from the EXPAND/RECRUIT
  AI decisions. Tying population growth directly to how often an AI decision fires
  produced runaway, unrealistic numbers (the AI choosing "recruit" often shouldn't
  make population grow exponentially faster than choosing it rarely). Growth rates
  per clan still reflect the brief's traits (Iron Covenant's Workforce bonus, the
  Conclave's Slow Blood, Void Reapers' Population Cap, etc.).

Everything else — the six clans' traits/weaknesses/evolution paths, the survival
rules (population floors, Last Bastion Protocol, Cornered Beast, Rebuilding
Momentum, the 300-year hard lock), the combat/weakness-cycle system, the narrative
template engine, and the Discord embed format — follows the original spec directly.

## Project structure

```
main.py                  Entry point
config.py                All tunable constants
requirements.txt

simulation/
  engine.py              The tick loop, genesis, day/year rollover, victory checks
  world.py                Map generation (biomes, resources, rare nodes, clan starts)
  clans.py                Static lore/traits/weaknesses/evolution paths/AI weights
  characters.py           Named character generation and lifecycle
  combat.py               Battle resolution, weakness-cycle matchups
  diplomacy.py            Relations ledger, grudge memory, alliance/war status
  ai.py                   Per-clan decision-making and target selection
  evolution.py            Evolution milestone detection
  survival.py             All anti-elimination rules
  events.py               Turns AI decisions + ambient rolls into real game state
  narrative.py            Every prose template bank + the yearly chronicle builder

discord_webhook/
  sender.py               Posts the yearly chronicle to your Discord webhook

web/
  app.py                  Flask + SocketIO routes
  templates/              Dashboard, map, clan, events, chronicle pages
  static/                 Dark-fantasy CSS + the SocketIO client script

database/
  db.py                   SQLite schema and all persistence
  simulation.db           Auto-created on first run — this is your entire world's save file
```
