"""Generate synthetic model-health telemetry for the observability dashboard.

Everything here is fabricated for demonstration — no real traffic, models, or
customers. Produces a 30-day daily dataset across several conversational-AI
domains plus per-domain snapshots, organized around five buckets:
Quality, Safety, Performance, Cost, and Drift.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

random.seed(42)
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "telemetry.json"

DOMAINS = [
    "Order tracking", "Returns & refunds", "Product search",
    "Substitutions", "Account & payment", "Store info", "Pharmacy",
]
DAYS = 30
MODEL_RELEASE_DAY = 18


def _wave(base, amp, i, period=7, phase=0.0):
    return base + amp * math.sin((i / period) * 2 * math.pi + phase)


def gen_daily():
    rows = []
    for i in range(DAYS):
        drift_creep = i * 0.0011
        incident = 1.0 if 22 <= i <= 24 else 0.0
        post_release = 1.0 if i >= MODEL_RELEASE_DAY else 0.0

        volume = int(_wave(48000, 9000, i, phase=-1) + random.uniform(-2500, 2500))

        intent_acc = max(0.80, _wave(0.946, 0.006, i) - drift_creep * 0.6 - incident * 0.03 + post_release * 0.004 + random.uniform(-0.004, 0.004))
        unanswered = min(0.16, _wave(0.052, 0.008, i) + drift_creep * 0.7 + incident * 0.035 + random.uniform(-0.003, 0.003))
        containment = max(0.55, _wave(0.78, 0.03, i) - drift_creep - incident * 0.06 + random.uniform(-0.01, 0.01))
        resolution = max(0.55, _wave(0.74, 0.03, i) - drift_creep * 1.2 - incident * 0.07 + random.uniform(-0.01, 0.01))
        fcr = max(0.50, _wave(0.69, 0.025, i) - drift_creep - incident * 0.05 + random.uniform(-0.01, 0.01))
        repeat_contact = min(0.25, _wave(0.116, 0.012, i) + drift_creep + incident * 0.03 + random.uniform(-0.004, 0.004))
        turns = max(2.4, _wave(3.6, 0.3, i) + incident * 0.7 + random.uniform(-0.1, 0.1))
        csat = max(3.6, _wave(4.31, 0.06, i) - drift_creep * 8 - incident * 0.18 + random.uniform(-0.03, 0.03))

        halluc = min(0.09, _wave(0.021, 0.004, i) + drift_creep + incident * 0.028 + random.uniform(-0.002, 0.002))
        groundedness = max(0.82, _wave(0.945, 0.008, i) - drift_creep - incident * 0.04 + random.uniform(-0.004, 0.004))
        policy_violation = min(0.03, _wave(0.006, 0.002, i) + incident * 0.006 + random.uniform(-0.0008, 0.0008))
        pii_flags = max(0, int(_wave(7, 4, i) + incident * 9 + random.uniform(-2, 2)))
        jailbreak_attempts = max(0, int(_wave(31, 12, i) + random.uniform(-6, 6)))
        refusal = min(0.10, _wave(0.032, 0.005, i) + incident * 0.012 + random.uniform(-0.002, 0.002))

        latency = _wave(1180, 140, i) + incident * 520 + random.uniform(-40, 40)
        ttft = _wave(420, 60, i) + incident * 180 + random.uniform(-20, 20)
        p95 = latency * 2.35 + incident * 800
        tool_fail = min(0.12, _wave(0.028, 0.006, i) + incident * 0.03 + random.uniform(-0.002, 0.002))
        uptime = min(1.0, max(0.985, 1.0 - incident * 0.004 - random.uniform(0, 0.0008)))
        throughput = max(20, _wave(54, 9, i) - incident * 8 + random.uniform(-3, 3))

        cost = _wave(0.0094, 0.0008, i) + incident * 0.0011 + random.uniform(-0.0003, 0.0003)
        tokens = int(_wave(2150, 220, i) + incident * 380 + random.uniform(-80, 80))
        cache_hit = max(0.30, _wave(0.46, 0.04, i) + post_release * 0.03 + random.uniform(-0.01, 0.01))
        cost_resolved = cost / max(0.5, resolution)

        intent_drift = min(0.30, _wave(0.07, 0.015, i) + drift_creep * 3 + incident * 0.06 + random.uniform(-0.006, 0.006))
        topic_drift = min(0.30, _wave(0.06, 0.012, i) + drift_creep * 2.4 + random.uniform(-0.006, 0.006))
        quality_drift = min(0.20, drift_creep * 9 + incident * 0.05 + random.uniform(-0.004, 0.004))

        escal = min(0.20, _wave(0.084, 0.01, i) + drift_creep * 0.5 + incident * 0.03 + random.uniform(-0.004, 0.004))

        rows.append({
            "day": i + 1, "volume": volume,
            "intent_accuracy": round(intent_acc, 4), "unanswered_rate": round(unanswered, 4),
            "containment_rate": round(containment, 4), "resolution_rate": round(resolution, 4),
            "first_contact_resolution": round(fcr, 4), "repeat_contact_rate": round(repeat_contact, 4),
            "turns_to_resolution": round(turns, 2), "csat": round(csat, 3),
            "hallucination_rate": round(halluc, 4), "groundedness_rate": round(groundedness, 4),
            "policy_violation_rate": round(policy_violation, 5), "pii_flags": pii_flags,
            "jailbreak_attempts": jailbreak_attempts, "refusal_rate": round(refusal, 4),
            "latency_ms": round(latency), "ttft_ms": round(ttft), "p95_latency_ms": round(p95),
            "tool_failure_rate": round(tool_fail, 4), "uptime": round(uptime, 5),
            "throughput_rps": round(throughput, 1),
            "cost_per_convo": round(cost, 5), "tokens_per_convo": tokens,
            "cache_hit_rate": round(cache_hit, 4), "cost_per_resolved": round(cost_resolved, 5),
            "intent_drift": round(intent_drift, 4), "topic_drift": round(topic_drift, 4),
            "quality_drift": round(quality_drift, 4), "escalation_rate": round(escal, 4),
        })
    return rows


def gen_domains():
    rows = []
    for d in DOMAINS:
        rows.append({
            "domain": d, "volume": random.randint(2200, 9800),
            "intent_accuracy": round(random.uniform(0.88, 0.975), 4),
            "unanswered_rate": round(random.uniform(0.03, 0.12), 4),
            "resolution_rate": round(random.uniform(0.60, 0.84), 4),
            "hallucination_rate": round(random.uniform(0.008, 0.06), 4),
            "groundedness_rate": round(random.uniform(0.88, 0.97), 4),
            "csat": round(random.uniform(3.8, 4.6), 2),
            "containment_rate": round(random.uniform(0.62, 0.86), 4),
            "intent_drift": round(random.uniform(0.03, 0.22), 4),
            "cost_per_resolved": round(random.uniform(0.011, 0.022), 5),
        })
    return rows


def gen_failure_modes():
    modes = [
        ("Missing knowledge / no answer", 0.27), ("Wrong intent classified", 0.19),
        ("Tool / API call failed", 0.16), ("Hallucinated detail", 0.12),
        ("Over-refusal (declined valid ask)", 0.09), ("Lost context mid-conversation", 0.08),
        ("Tone / unhelpful phrasing", 0.06), ("Other", 0.03),
    ]
    return [{"mode": m, "share": round(s, 3)} for m, s in modes]


def gen_intent_matrix():
    intents = ["track_order", "return_item", "find_product", "substitute",
               "store_hours", "payment_help", "pharmacy_refill"]
    return [{"intent": it, "volume": random.randint(800, 5200),
             "agreement": round(random.uniform(0.78, 0.965), 3)} for it in intents]


def gen_alerts():
    return [
        {"severity": "critical", "metric": "Hallucination rate", "bucket": "Safety",
         "detail": "Spiked to 4.9% on day 22 (baseline 2.1%) - coincides with retrieval index refresh.",
         "domain": "Product search"},
        {"severity": "warning", "metric": "Intent drift", "bucket": "Drift",
         "detail": "Crept from 7% to 17% over 30 days in Substitutions - labels may be stale.",
         "domain": "Substitutions"},
        {"severity": "warning", "metric": "p95 latency", "bucket": "Performance",
         "detail": "Breached 3s SLA during the day-22 incident; recovered by day 25.",
         "domain": "Platform-wide"},
        {"severity": "warning", "metric": "Groundedness", "bucket": "Safety",
         "detail": "Dipped to 90% during the incident - fewer answers backed by a source.",
         "domain": "Product search"},
        {"severity": "info", "metric": "Unanswered rate", "bucket": "Quality",
         "detail": "Slow upward creep (5.2% to 6.8%); watch for knowledge-gap growth.",
         "domain": "Pharmacy"},
        {"severity": "info", "metric": "Model version", "bucket": "Drift",
         "detail": "New model shipped on day 18 - small step-up in accuracy and cache-hit rate.",
         "domain": "Platform-wide"},
    ]


def main():
    data = {
        "meta": {
            "note": "Fabricated demo telemetry. Not derived from any employer, "
                    "customer, or production system.",
            "window_days": DAYS, "domains": DOMAINS, "model_release_day": MODEL_RELEASE_DAY,
        },
        "daily": gen_daily(), "domains": gen_domains(),
        "failure_modes": gen_failure_modes(), "intent_matrix": gen_intent_matrix(),
        "alerts": gen_alerts(),
    }
    OUT.write_text(json.dumps(data, indent=2))
    print(f"wrote {OUT} - {DAYS} days, {len(DOMAINS)} domains, {len(data['daily'][0])} daily fields")


if __name__ == "__main__":
    main()
