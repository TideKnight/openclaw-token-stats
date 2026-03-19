#!/usr/bin/env python3
"""Aggregate token/cost usage from OpenClaw agent session jsonl files.

This reads OpenClaw session logs at:
  ~/.openclaw/agents/<agent>/sessions/*.jsonl*

It sums any message objects that contain a `usage` object:
  usage.input, usage.output, usage.cacheRead, usage.cacheWrite, usage.totalTokens
and cost fields if present:
  usage.cost.{input,output,cacheRead,cacheWrite,total}

Outputs a JSON report and a human-readable table.

Examples:
  python3 openclaw_token_stats.py --agent main --days 1
  python3 openclaw_token_stats.py --agent main --since 2026-03-18
  python3 openclaw_token_stats.py --agent main --glob 'cb9e*.jsonl*'
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple


def parse_iso(ts: str) -> Optional[dt.datetime]:
    # Best-effort ISO parse (OpenClaw logs use Z sometimes).
    if not ts:
        return None
    try:
        if ts.endswith('Z'):
            return dt.datetime.fromisoformat(ts[:-1]).replace(tzinfo=dt.timezone.utc)
        return dt.datetime.fromisoformat(ts)
    except Exception:
        return None


def to_date(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open('r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def add_num(dst: Dict[str, float], key: str, val: Any) -> None:
    if val is None:
        return
    try:
        v = float(val)
    except Exception:
        return
    dst[key] = dst.get(key, 0.0) + v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--agent', default='main', help='Agent name under ~/.openclaw/agents/')
    ap.add_argument('--root', default=str(Path.home() / '.openclaw'), help='OpenClaw home dir')
    ap.add_argument('--glob', default='*.jsonl*', help='Session file glob inside sessions/')

    g = ap.add_mutually_exclusive_group()
    g.add_argument('--days', type=int, help='Only include events within the last N days (UTC)')
    g.add_argument('--since', help='Only include events on/after YYYY-MM-DD (local date, interpreted as UTC midnight)')

    ap.add_argument('--by', choices=['none', 'model', 'provider', 'session'], default='model')
    ap.add_argument('--json', action='store_true', help='Output JSON only')

    args = ap.parse_args()

    root = Path(os.path.expanduser(args.root))
    sessions_dir = root / 'agents' / args.agent / 'sessions'
    if not sessions_dir.exists():
        raise SystemExit(f'No sessions dir: {sessions_dir}')

    # Time filter in UTC
    since_dt: Optional[dt.datetime] = None
    if args.days is not None:
        since_dt = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.days)
    elif args.since:
        d = to_date(args.since)
        since_dt = dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc)

    files = sorted([Path(p) for p in glob.glob(str(sessions_dir / args.glob))])

    total_usage: Dict[str, float] = {}
    total_cost: Dict[str, float] = {}

    buckets: Dict[str, Dict[str, Dict[str, float]]] = {}  # bucket -> {'usage':{}, 'cost':{}}
    counts: Dict[str, int] = {}

    def get_bucket(obj: Dict[str, Any]) -> str:
        if args.by == 'none':
            return 'all'
        if args.by == 'session':
            return obj.get('_file', 'unknown')
        u = obj.get('message', {}).get('usage') or obj.get('usage')
        # In our logs, model/provider sit near top-level sometimes.
        model = obj.get('model') or (obj.get('message', {}) or {}).get('model')
        provider = obj.get('provider') or (obj.get('message', {}) or {}).get('provider')
        if args.by == 'provider':
            return provider or 'unknown'
        if args.by == 'model':
            return model or 'unknown'
        return 'all'

    for f in files:
        for obj in iter_jsonl(f):
            obj['_file'] = f.name
            # Determine timestamp
            ts = obj.get('timestamp')
            t = parse_iso(ts) if isinstance(ts, str) else None
            if since_dt and t and t < since_dt:
                continue

            # Find usage
            usage = None
            if isinstance(obj.get('usage'), dict):
                usage = obj['usage']
            elif isinstance(obj.get('message'), dict) and isinstance(obj['message'].get('usage'), dict):
                usage = obj['message']['usage']
            if not usage:
                continue

            bucket = get_bucket(obj)
            if bucket not in buckets:
                buckets[bucket] = {'usage': {}, 'cost': {}}
                counts[bucket] = 0
            counts[bucket] += 1

            for k in ['input', 'output', 'cacheRead', 'cacheWrite', 'totalTokens']:
                add_num(total_usage, k, usage.get(k))
                add_num(buckets[bucket]['usage'], k, usage.get(k))

            cost = usage.get('cost') if isinstance(usage.get('cost'), dict) else {}
            for k in ['input', 'output', 'cacheRead', 'cacheWrite', 'total']:
                add_num(total_cost, k, cost.get(k))
                add_num(buckets[bucket]['cost'], k, cost.get(k))

    report = {
        'agent': args.agent,
        'sessions_dir': str(sessions_dir),
        'file_glob': args.glob,
        'since_utc': since_dt.isoformat() if since_dt else None,
        'total': {
            'usage': total_usage,
            'cost': total_cost,
        },
        'buckets': {
            b: {'count': counts.get(b, 0), **buckets[b]} for b in sorted(buckets.keys())
        },
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    # Human table
    def fmt(n: float) -> str:
        if n is None:
            return '-'
        if abs(n) >= 1000000:
            return f'{n/1000000:.2f}M'
        if abs(n) >= 1000:
            return f'{n/1000:.1f}k'
        if float(int(n)) == n:
            return str(int(n))
        return f'{n:.4f}'

    print('OpenClaw token stats')
    print('  agent:', args.agent)
    if since_dt:
        print('  since (UTC):', since_dt.isoformat())
    print('  sessions_dir:', sessions_dir)
    print('')
    print('TOTAL')
    print('  tokens:', {k: fmt(total_usage.get(k, 0.0)) for k in ['input','output','cacheRead','cacheWrite','totalTokens']})
    if total_cost:
        print('  cost:', {k: fmt(total_cost.get(k, 0.0)) for k in ['input','output','cacheRead','cacheWrite','total']})
    print('')

    # bucket summary (top 30 by tokens)
    items: list[Tuple[str,float]] = []
    for b, data in buckets.items():
        items.append((b, float(data['usage'].get('totalTokens', 0.0))))
    items.sort(key=lambda x: x[1], reverse=True)

    print(f'BY {args.by.upper()} (top 30 by totalTokens)')
    print('  ' + ' | '.join(['bucket', 'count', 'totalTokens', 'in', 'out', 'cacheR', 'cost.total']))
    for b, _ in items[:30]:
        u = buckets[b]['usage']
        c = buckets[b]['cost']
        print('  ' + ' | '.join([
            b[:60],
            str(counts.get(b, 0)),
            fmt(u.get('totalTokens', 0.0)),
            fmt(u.get('input', 0.0)),
            fmt(u.get('output', 0.0)),
            fmt(u.get('cacheRead', 0.0)),
            fmt(c.get('total', 0.0)),
        ]))

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
