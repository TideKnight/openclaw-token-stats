# openclaw-token-stats 仓库建议结构

```text
openclaw-token-stats/
├── README.md
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

## 仓库命名建议
首选：`openclaw-token-stats`

## 发布顺序
1. 创建独立 GitHub 仓库
2. 放入 skill 主体文件
3. 补 README 和 examples
4. 首次 commit + push
5. 如需分发，再补 release / .skill 包
