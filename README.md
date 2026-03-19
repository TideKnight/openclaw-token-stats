# openclaw-token-stats

Offline token and cost reporting for local OpenClaw session logs.

`openclaw-token-stats` is a small OpenClaw skill + script bundle for turning raw session jsonl logs into practical token and cost reports.

It is built for questions like:

- How many tokens did OpenClaw burn today?
- Which model caused the spike?
- How much of the total came from cache?
- What did the last day / week / month cost?

It reads local logs only. It does not rely on the OpenClaw UI and does not upload usage data anywhere.

---

## What it includes

- `scripts/openclaw_token_stats.py`  
  Aggregate token / cost usage from local session logs.

- `scripts/openclaw_token_report.py`  
  Generate daily / weekly / monthly Markdown reports.

- `SKILL.md`  
  AgentSkill entry point for OpenClaw usage.

- `references/`  
  Supporting notes for observed fields and cron prompts.

---

## What it does

- Reads OpenClaw session logs under `~/.openclaw/agents/<agent>/sessions/*.jsonl*`
- Aggregates usage fields such as:
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
- Breaks usage down by:
  - model
  - provider
  - session file
- Generates chat-ready daily / weekly / monthly reports

---

## Why this exists

OpenClaw logs already contain useful accounting data, but raw logs are annoying to reason about at speed.

This project is for the practical layer in between:

- daily accounting
- anomaly detection
- model cost observation
- “what just happened?” debugging

The goal is not fancy dashboards. The goal is fast, offline answers.

---

## Project layout

```text
openclaw-token-stats/
├── README.md
├── LICENSE
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
    ├── sample-daily-report.md
    └── sample-weekly-report.md
```

---

## Quick start

### Aggregate by model

```bash
python3 scripts/openclaw_token_stats.py --agent main --days 1 --by model
```

### Aggregate by provider

```bash
python3 scripts/openclaw_token_stats.py --agent main --days 7 --by provider
```

### Find spikes by session file

```bash
python3 scripts/openclaw_token_stats.py --agent main --days 2 --by session
```

### Output JSON

```bash
python3 scripts/openclaw_token_stats.py --agent main --days 7 --by model --json
```

### Generate a daily report

```bash
python3 scripts/openclaw_token_report.py --agent main --period daily
```

### Generate a weekly report

```bash
python3 scripts/openclaw_token_report.py --agent main --period weekly
```

### Generate a monthly report

```bash
python3 scripts/openclaw_token_report.py --agent main --period monthly
```

---

## Use it in two ways

### 1. As a plain script bundle
Use the Python scripts directly if you just want local reporting.

### 2. As an OpenClaw skill
Keep `SKILL.md`, `scripts/`, and `references/` together inside a skill directory if you want another agent instance to trigger and use it as a reusable skill.

---

## Example output

- Daily: [`examples/sample-daily-report.md`](examples/sample-daily-report.md)
- Weekly: [`examples/sample-weekly-report.md`](examples/sample-weekly-report.md)

---

## Accounting philosophy

This project intentionally prefers the stable view first:

> Start with the overall ledger: total usage + top models + cache + cost.

Why:

- overall totals are usually the most stable signal
- per-session drilldown is useful, but should be treated as a debugging view
- “main conversation vs background work” reconstruction is helpful, but not always perfect from logs alone

In other words: total first, drill down second.

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

## Best fit

This project is best for:

- OpenClaw users who want offline token accounting
- operators debugging usage spikes
- people running scheduled daily / weekly / monthly summaries
- anyone who wants a lightweight observability layer without building a dashboard first

---

## Privacy / safety

- Reads local files only
- No external upload path in the reporting scripts
- Best used on a machine where OpenClaw logs are already present

---

## License

MIT

---

## Status

Usable now.

The current focus is practical observability, not polished visualization. If you want charts later, build them on top of the JSON output instead of bloating the core scripts.
