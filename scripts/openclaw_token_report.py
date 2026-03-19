#!/usr/bin/env python3
"""Generate daily/weekly/monthly OpenClaw token reports from local session logs.

Provides both:
- 总账（includes archived .reset/.deleted historical files)
- 活跃口径（excludes archived)
"""
from __future__ import annotations
import argparse, datetime as dt, glob, json, os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from zoneinfo import ZoneInfo


def parse_iso(ts: str):
    if not ts:
        return None
    try:
        if ts.endswith('Z'):
            return dt.datetime.fromisoformat(ts[:-1]).replace(tzinfo=dt.timezone.utc)
        return dt.datetime.fromisoformat(ts)
    except Exception:
        return None


def iter_jsonl(path: Path):
    with path.open('r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def add(dst: Dict[str, float], key: str, val: Any):
    if val is None:
        return
    try:
        dst[key] = dst.get(key, 0.0) + float(val)
    except Exception:
        pass


def fmt_num(n: float) -> str:
    if abs(n) >= 1_000_000:
        return f'{n/1_000_000:.2f}M'
    if abs(n) >= 1_000:
        return f'{n/1_000:.1f}k'
    if float(int(n)) == n:
        return str(int(n))
    return f'{n:.2f}'


def fmt_delta(cur: float, prev: float) -> str:
    if prev == 0:
        if cur == 0:
            return '持平'
        return f'+{fmt_num(cur)}（上期为 0）'
    diff = cur - prev
    pct = (diff / prev) * 100
    sign = '+' if diff >= 0 else ''
    return f'{sign}{fmt_num(diff)} / {sign}{pct:.1f}%'


def daterange(kind: str, now: dt.datetime, tz_name: str, periods_ago: int = 0):
    local_tz = ZoneInfo(tz_name)
    now_local = now.astimezone(local_tz)
    if kind == 'daily':
        base = now_local.date() - dt.timedelta(days=periods_ago)
        start_local = dt.datetime(base.year, base.month, base.day, tzinfo=local_tz)
        end_local = start_local + dt.timedelta(days=1)
        label = start_local.strftime('%Y-%m-%d')
    elif kind == 'weekly':
        monday = now_local.date() - dt.timedelta(days=now_local.weekday()) - dt.timedelta(days=7 * periods_ago)
        start_local = dt.datetime(monday.year, monday.month, monday.day, tzinfo=local_tz)
        end_local = start_local + dt.timedelta(days=7)
        label = f'{start_local.date()} ~ {(end_local - dt.timedelta(days=1)).date()}'
    elif kind == 'monthly':
        y, m = now_local.year, now_local.month
        for _ in range(periods_ago):
            if m == 1:
                y, m = y - 1, 12
            else:
                m -= 1
        start_local = dt.datetime(y, m, 1, tzinfo=local_tz)
        if m == 12:
            end_local = dt.datetime(y + 1, 1, 1, tzinfo=local_tz)
        else:
            end_local = dt.datetime(y, m + 1, 1, tzinfo=local_tz)
        label = start_local.strftime('%Y-%m')
    else:
        raise ValueError(kind)
    return start_local.astimezone(dt.timezone.utc), end_local.astimezone(dt.timezone.utc), label, start_local, end_local


def usage_from_obj(obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if isinstance(obj.get('usage'), dict):
        return obj['usage']
    if isinstance(obj.get('message'), dict) and isinstance(obj['message'].get('usage'), dict):
        return obj['message']['usage']
    return None


def summarize_bucket(rows: Iterable[Dict[str, Any]]):
    total_u: Dict[str, float] = {}
    total_c: Dict[str, float] = {}
    by_model: Dict[str, Dict[str, float]] = {}
    count = 0
    session_files = set()
    for row in rows:
        usage = row['usage']
        count += 1
        session_files.add((row['agent'], row['file']))
        model = row.get('model') or 'unknown'
        by_model.setdefault(model, {})
        for k in ['input', 'output', 'cacheRead', 'cacheWrite', 'totalTokens']:
            add(total_u, k, usage.get(k))
            add(by_model[model], k, usage.get(k))
        cost = usage.get('cost') if isinstance(usage.get('cost'), dict) else {}
        for k in ['input', 'output', 'cacheRead', 'cacheWrite', 'total']:
            add(total_c, k, cost.get(k))
    top = sorted(by_model.items(), key=lambda kv: kv[1].get('totalTokens', 0), reverse=True)[:5]
    return {'count': count, 'sessions': len(session_files), 'usage': total_u, 'cost': total_c, 'top': top}


def load_session_map(root: Path, agent: str):
    p = root / 'agents' / agent / 'sessions' / 'sessions.json'
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    out = {}
    for key, item in data.items():
        if not isinstance(item, dict):
            continue
        session_file = item.get('sessionFile')
        if session_file:
            out[Path(session_file).name] = key
        sid = item.get('sessionId') or item.get('id')
        if sid:
            out[f'{sid}.jsonl'] = key
            out[f'{sid}.jsonl.reset'] = key
        spr = item.get('systemPromptReport')
        if isinstance(spr, dict):
            sid2 = spr.get('sessionId')
            if sid2:
                out[f'{sid2}.jsonl'] = key
                out[f'{sid2}.jsonl.reset'] = key
    return out


def classify_session_key(key: str, main_key: str):
    if key == main_key:
        return 'main'
    if ':cron:' in key:
        return 'cron'
    if ':subagent:' in key:
        return 'subagent'
    if ':group:' in key:
        return 'group'
    if ':telegram:' in key or ':discord:' in key or ':signal:' in key:
        return 'chat-other'
    return 'other'


def classify_file(path: Path, agent_name: str, primary_agent: str, mapped_key: Optional[str]):
    name = path.name
    if '.reset.' in name or '.deleted.' in name:
        return 'archived'
    if agent_name != primary_agent:
        return 'external-agent'
    if mapped_key:
        return classify_session_key(mapped_key, f'agent:{primary_agent}:main')
    return 'unmapped-live'


def collect_rows(root: Path, start: dt.datetime, end: dt.datetime, primary_agent: str):
    session_map = load_session_map(root, primary_agent)
    all_files = sorted(glob.glob(str(root / 'agents' / '*' / 'sessions' / '*.jsonl*')))
    rows = []
    for fp in all_files:
        p = Path(fp)
        agent_name = p.parent.parent.name
        mapped_key = session_map.get(p.name) if agent_name == primary_agent else None
        bucket = classify_file(p, agent_name, primary_agent, mapped_key)
        for obj in iter_jsonl(p):
            ts = parse_iso(obj.get('timestamp')) if isinstance(obj.get('timestamp'), str) else None
            if ts is None or ts < start or ts >= end:
                continue
            usage = usage_from_obj(obj)
            if not usage:
                continue
            rows.append({
                'agent': agent_name,
                'file': p.name,
                'session_key': mapped_key,
                'bucket': bucket,
                'model': obj.get('model') or (obj.get('message', {}) or {}).get('model') or 'unknown',
                'usage': usage,
            })
    return rows


def observations_and_actions(total_sum, active_sum, prev_total_sum, prev_active_sum, bg_sum, archived_sum):
    obs, actions = [], []
    total = total_sum['usage'].get('totalTokens', 0.0)
    active = active_sum['usage'].get('totalTokens', 0.0)
    prev_total = prev_total_sum['usage'].get('totalTokens', 0.0)
    prev_active = prev_active_sum['usage'].get('totalTokens', 0.0)
    in_tok = active_sum['usage'].get('input', 0.0)
    out_tok = active_sum['usage'].get('output', 0.0)
    cache = active_sum['usage'].get('cacheRead', 0.0)

    if prev_active > 0:
        ratio = active / prev_active
        if ratio >= 1.3:
            obs.append(f'- 活跃口径明显高于上期（{fmt_delta(active, prev_active)}）。')
        elif ratio <= 0.7:
            obs.append(f'- 活跃口径明显低于上期（{fmt_delta(active, prev_active)}）。')
        else:
            obs.append(f'- 活跃口径与上期接近（{fmt_delta(active, prev_active)}）。')

    if total > 0 and archived_sum['usage'].get('totalTokens', 0.0) > 0:
        share = archived_sum['usage'].get('totalTokens', 0.0) / total * 100
        obs.append(f'- 历史残留文件（reset/deleted）占总账 {share:.1f}% ，会放大“今天看起来很贵”的错觉。')

    if in_tok > 0 and out_tok > 0 and in_tok / max(out_tok, 1) >= 20:
        obs.append('- 活跃口径里输入远高于输出，说明主要成本来自上下文体积，而不是回复长度。')
        actions.append('- 若准备换题，优先开新窗口；别让旧上下文继续滚雪球。')

    if cache > in_tok and active > 0:
        obs.append('- 活跃口径里 cacheRead 高于 input，说明历史上下文/缓存命中占大头。')
        actions.append('- 检查是否有长会话长期续聊；必要时分题、新开、压缩。')

    if active_sum['top']:
        model, u = active_sum['top'][0]
        share = u.get('totalTokens', 0.0) / max(active, 1.0) * 100
        obs.append(f'- 当前活跃消耗最大模型是 `{model}`，约占活跃 token 的 {share:.1f}% 。')
        if share >= 75:
            actions.append(f'- 若要降活跃消耗，先盯 `{model}` 这条线，优先级最高。')

    if bg_sum['usage'].get('totalTokens', 0.0) > 0 and active > 0:
        bg_share = bg_sum['usage'].get('totalTokens', 0.0) / active * 100
        if bg_share >= 35:
            obs.append(f'- 当前活跃后台/其他占比不低（约 {bg_share:.1f}%），不能只盯主聊天。')
            actions.append('- 排查 cron / 子代理 / 群聊是否有不必要的长任务或高频任务。')

    if not actions:
        actions.append('- 当前未见特别离谱的异常，继续观察 1-2 个周期再下手优化。')
    return obs, actions


def bucket_rows(rows, name):
    return [r for r in rows if r['bucket'] == name]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--period', choices=['daily', 'weekly', 'monthly'], required=True)
    ap.add_argument('--agent', default='main')
    ap.add_argument('--root', default=str(Path.home() / '.openclaw'))
    ap.add_argument('--tz', default='Asia/Shanghai')
    ap.add_argument('--periods-ago', type=int, default=0, help='0=current period, 1=previous period, 2=two periods ago')
    args = ap.parse_args()

    root = Path(os.path.expanduser(args.root))
    start, end, label, start_local, end_local = daterange(args.period, dt.datetime.now(dt.timezone.utc), args.tz, periods_ago=args.periods_ago)
    pstart, pend, plabel, _, _ = daterange(args.period, dt.datetime.now(dt.timezone.utc), args.tz, periods_ago=args.periods_ago + 1)

    rows = collect_rows(root, start, end, args.agent)
    prev_rows = collect_rows(root, pstart, pend, args.agent)

    main_sum = summarize_bucket(bucket_rows(rows, 'main'))
    archived_sum = summarize_bucket(bucket_rows(rows, 'archived'))
    bg_rows = [r for r in rows if r['bucket'] not in ('main', 'archived')]
    bg_sum = summarize_bucket(bg_rows)
    total_sum = summarize_bucket(rows)
    active_rows = [r for r in rows if r['bucket'] != 'archived']
    active_sum = summarize_bucket(active_rows)

    prev_main_sum = summarize_bucket(bucket_rows(prev_rows, 'main'))
    prev_bg_sum = summarize_bucket([r for r in prev_rows if r['bucket'] not in ('main', 'archived')])
    prev_total_sum = summarize_bucket(prev_rows)
    prev_active_sum = summarize_bucket([r for r in prev_rows if r['bucket'] != 'archived'])

    cron_sum = summarize_bucket(bucket_rows(rows, 'cron'))
    sub_sum = summarize_bucket(bucket_rows(rows, 'subagent'))
    group_sum = summarize_bucket(bucket_rows(rows, 'group'))
    chat_other_sum = summarize_bucket(bucket_rows(rows, 'chat-other'))
    unmapped_live_sum = summarize_bucket(bucket_rows(rows, 'unmapped-live'))
    ext_sum = summarize_bucket(bucket_rows(rows, 'external-agent'))

    obs, actions = observations_and_actions(total_sum, active_sum, prev_total_sum, prev_active_sum, bg_sum, archived_sum)

    period_zh = {'daily':'日报','weekly':'周报','monthly':'月报'}[args.period]
    lines = []
    lines.append(f'OpenClaw Token {period_zh}｜{label}')
    lines.append('')
    lines.append('今日结论')
    lines.extend(obs[:6] if obs else ['- 本期暂无明显异常。'])
    lines.append('')

    lines.append('总账（含历史残留）')
    lines.append(f'- 时区：{args.tz}')
    lines.append(f'- 统计窗口（本地）：{start_local.isoformat()} ~ {end_local.isoformat()}')
    lines.append(f'- 总 tokens：{fmt_num(total_sum["usage"].get("totalTokens", 0.0))}')
    lines.append(f'- 输入 / 输出：{fmt_num(total_sum["usage"].get("input", 0.0))} / {fmt_num(total_sum["usage"].get("output", 0.0))}')
    lines.append(f'- cache read：{fmt_num(total_sum["usage"].get("cacheRead", 0.0))}')
    lines.append(f'- 对比上期（{plabel}）：{fmt_delta(total_sum["usage"].get("totalTokens", 0.0), prev_total_sum["usage"].get("totalTokens", 0.0))}')
    if total_sum['cost'].get('total'):
        lines.append(f'- 成本汇总（按日志已有 cost 字段，默认按 USD 理解）：{total_sum["cost"].get("total", 0.0):.4f}')
    lines.append('')

    lines.append('活跃口径（排除 archived）')
    lines.append(f'- 活跃 tokens：{fmt_num(active_sum["usage"].get("totalTokens", 0.0))}')
    lines.append(f'- 输入 / 输出：{fmt_num(active_sum["usage"].get("input", 0.0))} / {fmt_num(active_sum["usage"].get("output", 0.0))}')
    lines.append(f'- cache read：{fmt_num(active_sum["usage"].get("cacheRead", 0.0))}')
    lines.append(f'- 对比上期：{fmt_delta(active_sum["usage"].get("totalTokens", 0.0), prev_active_sum["usage"].get("totalTokens", 0.0))}')
    if total_sum['usage'].get('totalTokens', 0.0) > 0:
        share = active_sum['usage'].get('totalTokens', 0.0) / total_sum['usage'].get('totalTokens', 1.0) * 100
        lines.append(f'- 占总账比例：{share:.1f}%')
    lines.append('')

    lines.append('主会话')
    lines.append(f'- tokens：{fmt_num(main_sum["usage"].get("totalTokens", 0.0))}')
    lines.append(f'- 输入 / 输出：{fmt_num(main_sum["usage"].get("input", 0.0))} / {fmt_num(main_sum["usage"].get("output", 0.0))}')
    lines.append(f'- cache read：{fmt_num(main_sum["usage"].get("cacheRead", 0.0))}')
    lines.append(f'- 对比上期：{fmt_delta(main_sum["usage"].get("totalTokens", 0.0), prev_main_sum["usage"].get("totalTokens", 0.0))}')
    if main_sum['top']:
        model, u = main_sum['top'][0]
        lines.append(f'- 主消耗模型：{model}（{fmt_num(u.get("totalTokens", 0.0))}）')
    lines.append('')

    lines.append('后台 / 其他（当前活跃）')
    lines.append(f'- tokens：{fmt_num(bg_sum["usage"].get("totalTokens", 0.0))}')
    lines.append(f'- 输入 / 输出：{fmt_num(bg_sum["usage"].get("input", 0.0))} / {fmt_num(bg_sum["usage"].get("output", 0.0))}')
    lines.append(f'- cache read：{fmt_num(bg_sum["usage"].get("cacheRead", 0.0))}')
    lines.append(f'- 对比上期：{fmt_delta(bg_sum["usage"].get("totalTokens", 0.0), prev_bg_sum["usage"].get("totalTokens", 0.0))}')
    lines.append('')

    lines.append('后台细分')
    lines.append(f'- cron：{fmt_num(cron_sum["usage"].get("totalTokens", 0.0))}')
    lines.append(f'- subagent：{fmt_num(sub_sum["usage"].get("totalTokens", 0.0))}')
    lines.append(f'- group：{fmt_num(group_sum["usage"].get("totalTokens", 0.0))}')
    lines.append(f'- 其他聊天：{fmt_num(chat_other_sum["usage"].get("totalTokens", 0.0))}')
    lines.append(f'- unmapped-live：{fmt_num(unmapped_live_sum["usage"].get("totalTokens", 0.0))}')
    lines.append(f'- external-agent：{fmt_num(ext_sum["usage"].get("totalTokens", 0.0))}')
    lines.append('')

    lines.append('历史残留（archived）')
    lines.append(f'- reset/deleted 历史文件：{fmt_num(archived_sum["usage"].get("totalTokens", 0.0))}')
    lines.append('')

    lines.append('模型分布（活跃口径 Top）')
    for model, u in active_sum['top']:
        lines.append(f'- {model}: {fmt_num(u.get("totalTokens", 0.0))}（in {fmt_num(u.get("input", 0.0))} / out {fmt_num(u.get("output", 0.0))} / cache {fmt_num(u.get("cacheRead", 0.0))}）')
    lines.append('')

    lines.append('建议动作')
    lines.extend(actions[:5])
    lines.append('')

    lines.append('说明')
    lines.append('- 成本不是手算单价，而是直接汇总日志里的 `usage.cost.*`；没写 cost 的 provider 不会被我硬估。当前默认按 USD 口径理解，不做人民币换算。')
    lines.append('- 总账会扫 `~/.openclaw/agents/*/sessions/*.jsonl*`，因此包含主会话、cron、子代理、其他 agent 会话。')
    lines.append('- 主会话/cron/subagent 拆分优先使用 `sessions.json` 里的 `sessionFile/sessionId` 映射。')
    lines.append('- `archived` 指 `.reset` / `.deleted` 历史文件；它们不是当前活跃会话，但仍会计入这个统计窗口内的历史 token。')

    print('\n'.join(lines))


if __name__ == '__main__':
    main()
