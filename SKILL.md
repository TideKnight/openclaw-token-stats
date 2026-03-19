---
name: openclaw-token-stats
description: Aggregate and report token/cost usage from local OpenClaw session logs. Use when you need token统计/花费统计 for OpenClaw (per model/provider/session, per day window), or when debugging sudden token spikes and want a breakdown without relying on the UI.
---

# openclaw-token-stats

Use this skill to produce **token / cost** usage reports from local OpenClaw logs (fast, offline, reproducible).

## Default workflow

1) Decide scope
- Last N days: `--days 1` / `--days 7`
- Since date: `--since YYYY-MM-DD`

2) Run the report

```bash
python3 scripts/openclaw_token_stats.py --agent main --days 1 --by model
```

Common variants:

- By provider:
```bash
python3 scripts/openclaw_token_stats.py --agent main --days 7 --by provider
```

- By session file:
```bash
python3 scripts/openclaw_token_stats.py --agent main --days 2 --by session
```

- JSON output:
```bash
python3 scripts/openclaw_token_stats.py --agent main --days 7 --by model --json
```

## Report mode

- 日报：
```bash
python3 scripts/openclaw_token_report.py --agent main --period daily
```

- 周报：
```bash
python3 scripts/openclaw_token_report.py --agent main --period weekly
```

- 月报：
```bash
python3 scripts/openclaw_token_report.py --agent main --period monthly
```

## Interpretation cheatsheet

- `input/output`: actual prompt+completion tokens
- `cacheRead/cacheWrite`: caching layer tokens
- `totalTokens`: total as recorded in logs
- `cost.total`: only present if provider/runtime already returned cost accounting

## Guardrails

- Read local logs only.
- Do not send anything externally.
- Treat output as approximate accounting; provider reporting differs.

## Files

- Scripts: `scripts/openclaw_token_stats.py`, `scripts/openclaw_token_report.py`
- Reference: `references/fields.md`
