# LLM Observability & Evals — Model-Health Dashboard

> A runnable **observability and evals dashboard** for a customer-facing **conversational / agentic AI assistant** — one screen that answers *"is the model healthy right now?"* across **quality, safety, performance, cost, and drift**, with an executive summary and one-click export to **PDF, PowerPoint, and clipboard**.

Built as an AI-product-management portfolio piece: it demonstrates the *judgment* behind LLM observability — knowing which signals matter in production, how to read them, and how to turn a model-health incident into a prioritized, communicable decision.

---

## 📊 What it does

The dashboard tracks a production conversational-AI system over a 30-day window and tells a real operational story: a **hallucination incident on day 22**, a **new model release on day 18**, and a **slow intent-drift trend** building across the month. It's organized around five buckets a product team actually monitors:

| Bucket | Question it answers | Headline metrics |
|---|---|---|
| **Quality** | Is it understanding and resolving? | intent accuracy · resolution rate · first-contact resolution · repeat-contact rate · CSAT |
| **Safety** | Is it grounded and within policy? | hallucination risk · groundedness · policy violations · PII flags · jailbreak attempts · refusal rate |
| **Performance** | Is it fast and reliable? | median latency · time-to-first-token · p95 latency · tool-call failure · uptime |
| **Cost** | Is it economical per unit of value? | cost / conversation · **cost / resolved** · tokens / conversation · cache-hit rate |
| **Drift** | Is the world moving away from the model? | intent drift · topic drift · quality drift · model-release marker |

Plus an **Executive Summary** (health verdict, what changed, top recommendation), **By Domain** (seven journeys scored side by side + crowd-vs-predicted intent agreement), **Failure Analysis** (failed conversations bucketed by root cause), and **Alerts** (severity-ranked, bucket-tagged).

---

## 🧠 Why it's built this way (the PM judgment)

This is less about plotting numbers and more about the decisions behind them:

- **Resolution rate, not just containment.** A bot can look "contained" (no human involved) while silently failing the customer. Tracking *resolution* and *repeat-contact* catches that gap — and that gap is where quality investment pays off.
- **Cost per *resolved* conversation.** Raw cost-per-conversation rewards cutting corners; a cheap conversation that fails is expensive. Normalizing cost by successful outcomes is the metric tied to value.
- **Drift as a leading indicator.** Drift usually rises *before* accuracy falls. Pairing a drift chart with a model-release marker lets you attribute a step-change to a specific deployment.
- **Failure modes route to owners.** "Quality dropped" isn't actionable. Bucketing failures (missing knowledge → content/retrieval; wrong intent → retraining; tool failure → engineering) turns a metric into a work item with an owner.
- **Safety as a first-class bucket.** Groundedness, policy violations, PII exposure, and jailbreak attempts are tracked alongside quality — the trust signals an AI PM is accountable for.

---

## 🚀 Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Regenerate the synthetic dataset (optional):

```bash
python scripts/generate_telemetry.py
```

---

## 📤 Export & share

The Executive Summary tab has three working actions:

- **Copy executive summary** → ready-to-paste plain text for email.
- **Download PDF report** → a one-page formatted brief (summary, key numbers, per-bucket verdicts, recommendation).
- **Download PowerPoint deck** → title · summary · one slide per bucket · recommendation.

> **On email:** a public app can't send mail without storing credentials, so the email action copies a ready-to-paste summary rather than sending directly. Wiring a real SMTP/SendGrid sender is a one-function swap for internal deployment.

---

## 🗂 Project structure

```
streamlit_app.py                 # the dashboard (9 views)
scripts/generate_telemetry.py    # synthetic telemetry generator
scripts/report_builders.py       # PDF / PPTX / text export builders
data/telemetry.json              # generated demo dataset (30 days · 7 domains · 30 metrics/day)
.streamlit/config.toml           # light theme
requirements.txt · runtime.txt
```

---

## 📈 Metrics tracked (full list)

**Quality:** intent accuracy · resolution rate · first-contact resolution · repeat-contact rate · unanswered rate · turns-to-resolution · CSAT · containment
**Safety:** hallucination risk · groundedness / citation rate · policy-violation rate · PII flags · jailbreak / prompt-injection attempts · refusal / over-refusal rate
**Performance:** median latency · time-to-first-token · p95 latency · tool-call failure rate · uptime · throughput
**Cost:** cost / conversation · cost / resolved · tokens / conversation · cache-hit rate
**Drift:** intent drift · topic drift · quality drift · model-version marker
**Cross-cutting:** conversation volume · escalation rate · per-domain breakdown · crowd-vs-predicted intent agreement · failure-mode distribution

---

## 🛠 Built with

`Python` · `Streamlit` · `reportlab` (PDF) · `python-pptx` (slides) · inline SVG charts (no charting dependency)

---

## ⚠️ Data Disclaimer

All telemetry, metrics, domains, and alerts in this repository are **fabricated for demonstration**, generated by `scripts/generate_telemetry.py`. Nothing here is derived from any employer, customer, or production system, and the repository contains no proprietary, confidential, or company-specific data.

---

## 🎯 Scope

Intentionally lightweight — no backend, no production data dependencies. It exists to communicate **LLM observability, evals, metric design across quality/safety/performance/cost/drift, and the product judgment to act on model-health signals** — readable end to end by a product manager or hiring team.
