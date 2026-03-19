# OpenClaw usage fields (observed)

Most session jsonl lines may contain a `usage` object either at top-level or under `message.usage`.

Common keys:
- `usage.input`
- `usage.output`
- `usage.cacheRead`
- `usage.cacheWrite`
- `usage.totalTokens`

Optional cost object:
- `usage.cost.input`
- `usage.cost.output`
- `usage.cost.cacheRead`
- `usage.cost.cacheWrite`
- `usage.cost.total`

Not all providers populate `cost`.
