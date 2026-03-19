# 示例：日报输出

> 下面是示意样例，用于展示汇报风格，不代表真实账单。

## OpenClaw Token 日报
- 时间范围：2026-03-18 00:00 ~ 2026-03-18 23:59（北京时间）
- 统计口径：总账优先

### 总览
- 总 tokens：1.82M
- input：210.4k
- output：96.8k
- cacheRead：1.47M
- cacheWrite：42.3k
- cost.total：$1.92

### Top 模型
1. `nvidia/qwen/qwen3.5-397b-a17b` — 1.11M
2. `nvidia/moonshotai/kimi-k2.5` — 402.7k
3. `baishan/GLM-5` — 188.5k
4. `openai-codex/gpt-5.1-codex-mini` — 97.1k

### 今日结论
- 今日总消耗主要集中在 Qwen 397B。
- cacheRead 占比很高，说明重复上下文命中明显。
- 成本没有异常跳变，属于可接受范围。

### 对比上期
- totalTokens：+320.5k / +21.4%
- cost.total：+0.36 / +23.1%

### 异常判断
- 无明显异常。
- 若明天继续增长，优先检查长上下文任务和批量扫描任务。

### 建议动作
- 继续优先看总账，不急着细抠主会话 / 后台拆分。
- 若出现单日突刺，再用 session 维度排查热点文件。
