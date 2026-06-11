"""Build a SQLite database for the observability dashboard.

Turns the synthetic telemetry into a real relational store the app queries with
SQL. Demonstrates the end-to-end pipeline:

    raw conversation events  ->  daily rollups (via SQL aggregation)
                             ->  domain / failure / intent / alert tables
                             ->  dashboard reads everything with SQL

Run once locally to (re)generate data/telemetry.db. The app reads from that file;
it does not rebuild on every start.

All data is fabricated for demonstration - no real traffic, models, or customers.
"""
from __future__ import annotations

import json
import random
import sqlite3
from pathlib import Path

random.seed(7)
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "telemetry.json"
DB = ROOT / "data" / "telemetry.db"

SCHEMA = """
DROP TABLE IF EXISTS conversation_events;
DROP TABLE IF EXISTS daily_metrics;
DROP TABLE IF EXISTS domain_health;
DROP TABLE IF EXISTS failure_modes;
DROP TABLE IF EXISTS intent_agreement;
DROP TABLE IF EXISTS alerts;
DROP TABLE IF EXISTS meta;

-- raw-ish event stream: a sampled row per conversation bucket per day.
-- (In a real system this would be one row per conversation; here we sample
--  a representative set per day so aggregation is demonstrable but the file
--  stays small.)
CREATE TABLE conversation_events (
    event_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    day               INTEGER NOT NULL,
    domain            TEXT    NOT NULL,
    intent_correct    INTEGER NOT NULL,   -- 1/0
    resolved          INTEGER NOT NULL,   -- 1/0
    contained         INTEGER NOT NULL,   -- 1/0 (no human handoff)
    hallucinated      INTEGER NOT NULL,   -- 1/0
    grounded          INTEGER NOT NULL,   -- 1/0
    escalated         INTEGER NOT NULL,   -- 1/0
    latency_ms        INTEGER NOT NULL,
    ttft_ms           INTEGER NOT NULL,
    tokens            INTEGER NOT NULL,
    cost_usd          REAL    NOT NULL,
    csat              REAL                -- nullable: not every convo is rated
);
CREATE INDEX idx_events_day ON conversation_events(day);
CREATE INDEX idx_events_domain ON conversation_events(domain);

-- pre-computed daily platform metrics (the full 30-metric daily series)
CREATE TABLE daily_metrics (
    day                       INTEGER PRIMARY KEY,
    volume                    INTEGER,
    intent_accuracy           REAL,
    unanswered_rate           REAL,
    containment_rate          REAL,
    resolution_rate           REAL,
    first_contact_resolution  REAL,
    repeat_contact_rate       REAL,
    turns_to_resolution       REAL,
    csat                      REAL,
    hallucination_rate        REAL,
    groundedness_rate         REAL,
    policy_violation_rate     REAL,
    pii_flags                 INTEGER,
    jailbreak_attempts        INTEGER,
    refusal_rate              REAL,
    latency_ms                INTEGER,
    ttft_ms                   INTEGER,
    p95_latency_ms            INTEGER,
    tool_failure_rate         REAL,
    uptime                    REAL,
    throughput_rps            REAL,
    cost_per_convo            REAL,
    tokens_per_convo          INTEGER,
    cache_hit_rate            REAL,
    cost_per_resolved         REAL,
    intent_drift              REAL,
    topic_drift               REAL,
    quality_drift             REAL,
    escalation_rate           REAL
);

CREATE TABLE domain_health (
    domain             TEXT PRIMARY KEY,
    volume             INTEGER,
    intent_accuracy    REAL,
    unanswered_rate    REAL,
    resolution_rate    REAL,
    hallucination_rate REAL,
    groundedness_rate  REAL,
    csat               REAL,
    containment_rate   REAL,
    intent_drift       REAL,
    cost_per_resolved  REAL
);

CREATE TABLE failure_modes (
    mode  TEXT PRIMARY KEY,
    share REAL
);

CREATE TABLE intent_agreement (
    intent    TEXT PRIMARY KEY,
    volume    INTEGER,
    agreement REAL
);

CREATE TABLE alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    severity TEXT,
    metric   TEXT,
    bucket   TEXT,
    detail   TEXT,
    domain   TEXT
);

CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

# columns of daily_metrics in order (minus `day`) for a clean insert
DAILY_COLS = [
    "volume", "intent_accuracy", "unanswered_rate", "containment_rate",
    "resolution_rate", "first_contact_resolution", "repeat_contact_rate",
    "turns_to_resolution", "csat", "hallucination_rate", "groundedness_rate",
    "policy_violation_rate", "pii_flags", "jailbreak_attempts", "refusal_rate",
    "latency_ms", "ttft_ms", "p95_latency_ms", "tool_failure_rate", "uptime",
    "throughput_rps", "cost_per_convo", "tokens_per_convo", "cache_hit_rate",
    "cost_per_resolved", "intent_drift", "topic_drift", "quality_drift",
    "escalation_rate",
]

EVENTS_PER_DAY = 60  # sampled representative events per day


def sample_events(day_row, domains):
    """Generate a representative set of raw events for one day, consistent with
    that day's aggregate rates (so SQL rollups match the daily series)."""
    rows = []
    intent_p = day_row["intent_accuracy"]
    res_p = day_row["resolution_rate"]
    con_p = day_row["containment_rate"]
    hal_p = day_row["hallucination_rate"]
    grd_p = day_row["groundedness_rate"]
    esc_p = day_row["escalation_rate"]
    lat = day_row["latency_ms"]
    ttft = day_row["ttft_ms"]
    tok = day_row["tokens_per_convo"]
    cost = day_row["cost_per_convo"]
    csat = day_row["csat"]
    for _ in range(EVENTS_PER_DAY):
        rows.append((
            day_row["day"],
            random.choice(domains),
            1 if random.random() < intent_p else 0,
            1 if random.random() < res_p else 0,
            1 if random.random() < con_p else 0,
            1 if random.random() < hal_p else 0,
            1 if random.random() < grd_p else 0,
            1 if random.random() < esc_p else 0,
            int(random.gauss(lat, lat * 0.25)),
            int(random.gauss(ttft, ttft * 0.25)),
            int(random.gauss(tok, tok * 0.15)),
            round(max(0.001, random.gauss(cost, cost * 0.2)), 5),
            round(min(5, max(1, random.gauss(csat, 0.5))), 1) if random.random() < 0.6 else None,
        ))
    return rows


def main():
    data = json.loads(SRC.read_text())
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.executescript(SCHEMA)

    domains = data["meta"]["domains"]

    # daily_metrics
    for d in data["daily"]:
        vals = [d["day"]] + [d[c] for c in DAILY_COLS]
        placeholders = ",".join("?" * len(vals))
        cur.execute(f"INSERT INTO daily_metrics (day,{','.join(DAILY_COLS)}) VALUES ({placeholders})", vals)

    # raw events
    all_events = []
    for d in data["daily"]:
        all_events.extend(sample_events(d, domains))
    cur.executemany(
        "INSERT INTO conversation_events "
        "(day,domain,intent_correct,resolved,contained,hallucinated,grounded,"
        "escalated,latency_ms,ttft_ms,tokens,cost_usd,csat) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", all_events)

    # domain_health
    for r in data["domains"]:
        cur.execute(
            "INSERT INTO domain_health VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (r["domain"], r["volume"], r["intent_accuracy"], r["unanswered_rate"],
             r["resolution_rate"], r["hallucination_rate"], r["groundedness_rate"],
             r["csat"], r["containment_rate"], r["intent_drift"], r["cost_per_resolved"]))

    # failure_modes
    for r in data["failure_modes"]:
        cur.execute("INSERT INTO failure_modes VALUES (?,?)", (r["mode"], r["share"]))

    # intent_agreement
    for r in data["intent_matrix"]:
        cur.execute("INSERT INTO intent_agreement VALUES (?,?,?)",
                    (r["intent"], r["volume"], r["agreement"]))

    # alerts
    for r in data["alerts"]:
        cur.execute("INSERT INTO alerts (severity,metric,bucket,detail,domain) VALUES (?,?,?,?,?)",
                    (r["severity"], r["metric"], r.get("bucket", ""), r["detail"], r["domain"]))

    # meta
    for k, v in [("window_days", data["meta"]["window_days"]),
                 ("model_release_day", data["meta"]["model_release_day"]),
                 ("note", data["meta"]["note"]),
                 ("domains", json.dumps(domains)),
                 ("events_per_day", EVENTS_PER_DAY)]:
        cur.execute("INSERT INTO meta VALUES (?,?)", (k, str(v)))

    con.commit()

    # ---- verify the raw-events rollup matches the daily series (sanity) ----
    cur.execute("""
        SELECT e.day,
               AVG(e.intent_correct) AS intent_acc,
               AVG(e.resolved)       AS resolution
        FROM conversation_events e GROUP BY e.day ORDER BY e.day LIMIT 1
    """)
    row = cur.fetchone()
    print(f"rollup check (day {row[0]}): intent_acc~{row[1]:.2f}, resolution~{row[2]:.2f}")

    cur.execute("SELECT COUNT(*) FROM conversation_events")
    n_events = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM daily_metrics")
    n_days = cur.fetchone()[0]
    con.close()
    print(f"wrote {DB} - {n_events:,} raw events, {n_days} daily rows, "
          f"7 tables")


if __name__ == "__main__":
    main()
