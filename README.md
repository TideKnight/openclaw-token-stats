# openclaw-token-stats

Offline token and cost reporting for local OpenClaw session logs.

`openclaw-token-stats` is an AgentSkill plus a pair of local scripts for aggregating OpenClaw usage from session jsonl logs. It is designed for people who want a practical answer to questions like:

- How many tokens did OpenClaw burn today?
- Which model caused the spike?
- How much of the total came from cache?
- What did the last day / week / month cost?

This tool reads local logs only. It does not depend on the OpenClaw UI and does not send usage data to external services.

---

## What it does

- Reads OpenClaw session logs under `~/.openclaw/agents/<agent>/sessions/*.jsonl*`
- Aggregates usage fields like:
  - `input`
  - `output`
  - `cacheRead`
  - `cacheWrite`
  - `totalTokens`
- Aggregates provider-reported cost fields when present:
  - `usage.cost.input`
  - `usage.cost.output`
  - `usage.cost.cacheRead`
  - `usage.cost.cacheWrite`
  - `usage.cost.total`
- Breaks down usage by:
  - model
  - provider
  - session file
- Generates chat-ready daily / weekly / monthly markdown reports

---

## Why this exists

OpenClaw logs already contain a lot of useful usage data, but:

- the UI is not always the fastest way to investigate a spike
- historical totals are easier to compare offline
- model / provider / session breakdowns are often more useful than a single total number

This project turns raw session logs into something you can actually use for:

- daily accounting
- anomaly detection
- model cost observation
- “what just happened?” debugging

---

## Project layout

```text
openclaw-token-stats/
├── SKILL.md
├── scripts/
│   ├── openclaw_token_stats.py
│   └── openclaw_token_report.py
├── references/
│   ├── fields.md
│   ├── cron-prompt-daily.txt
│   ├── cron-prompt-weekly.txt
│   └── cron-prompt-monthly.txt
└── examples/
    └── sample-daily-report.md
```

---

## Quick start

### 1. Aggregate by model

```bash
python3 scripts/openclaw_token_stats.py --agent main --days 1 --by model
```

### 2. Aggregate by provider

```bash
python3 scripts/openclaw_token_stats.py --agent main --days 7 --by provider
```

### 3. Find spikes by session file

```bash
python3 scripts/openclaw_token_stats.py --agent main --days 2 --by session
```

### 4. Output JSON

```bash
python3 scripts/openclaw_token_stats.py --agent main --days 7 --by model --json
```

### 5. Generate a daily report

```bash
python3 scripts/openclaw_token_report.py --agent main --period daily
```

### 6. Generate a weekly report

```bash
python3 scripts/openclaw_token_report.py --agent main --period weekly
```

### 7. Generate a monthly report

```bash
python3 scripts/openclaw_token_report.py --agent main --period monthly
```

---

## Example use cases

- Check total token burn for the last 24 hours
- Compare model usage over the last 7 days
- See whether cost is coming from active inference or cache
- Debug a sudden token spike without relying on UI state
- Send a lightweight daily usage summary into chat or cron output

---

## Example output

See: [`examples/sample-daily-report.md`](examples/sample-daily-report.md)

---

## Important limits

This tool is intentionally conservative.

### It does
- read local session logs
- sum fields that are already present in those logs
- report cost only when the provider/runtime already returned cost data

### It does not
- estimate price from public pricing tables
- invent missing cost fields
- guarantee perfect session-role mapping in every OpenClaw setup
- send your logs anywhere

---

## Current accounting philosophy

The current recommended reading is:

> Prefer the overall ledger first: total usage + top models + cache + cost.

Why:

- OpenClaw session mapping for “main conversation vs background work” is useful, but not always perfectly reconstructible from logs alone
- the overall ledger is the most stable first view
- per-session drilldown still works, but should be treated as a debugging view, not absolute truth

---

## Best fit

This project is best for:

- OpenClaw users who want offline token accounting
- operators debugging usage spikes
- people running scheduled daily / weekly / monthly summaries
- anyone who wants a lightweight observability layer without building a dashboard first

---

## Safety / privacy

- Reads local files only
- No external upload path in the reporting scripts
- Best used on a machine where OpenClaw logs are already present

---

## Status

Usable now. The current focus is practical observability, not fancy visualization.

If you want charts later, build them on top of the JSON output rather than bloating the core scripts.
