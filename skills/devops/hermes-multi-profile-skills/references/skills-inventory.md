# Инвентаризация скиллов по профилям (03.08.2026)

> **Исторический снапшот 03.08.2026.** Состояние профилей на момент восстановления после инцидента. Профиль tz-dev decommissioned 13.08.2026.

## Состояние ДО восстановления

### Бэкап куратора tz-dev от 29.07.2026 — 132 скилла (золотая копия)

Полный список: about_usr_skills, airtable, all-skills-hygiene, apple-notes, apple-reminders, architecture-diagram, arxiv, ascii-art, ascii-video, audiocraft, backlog-analyst, backlog-collector, baoyu-article-illustrator, baoyu-comic, baoyu-infographic, blogwatcher, check-cron-results, claude-code, claude-design, cleanup-after-sync, codebase-inspection, codex, comfyui, computer-use, creative-ideation, cron-journal-write, debugging-hermes-tui-commands, design-md, dogfood, dspy, excalidraw, exchange-monitor, findmy, find-proxy-task, full-workvault-backup, get-obsidian-link, gif-search, github-auth, github-code-review, github-issues, github-pr-workflow, github-repo-management, godmode, google-workspace, heartmula, hermes-agent, hermes-agent-skill-authoring, hermes-cost-optimization, hermes-desktop-plugins, hermes-feature, hermes-gateway-setup, hermes-llm-provider-switch, hermes-memory-hygiene, hermes-skills-discovery, hermes-upstream-check, himalaya, huggingface-hub, humanizer, imessage, jupyter-live-kernel, kanban-codex-lane, kanban-orchestrator, kanban-worker, linear, llama-cpp, llm-wiki, lm-evaluation-harness, macos-computer-use, manim-video, maps, mattermost-loop-api, minecraft-modpack-server, mofs-operations, moscow-suburban-trains, movefrom-confluence, movefromff, mpp-to-google-sheets, nano-pdf, native-mcp, node-inspect-debugger, notion, obliteratus, obsidian, ocr-and-documents, opencode, openhue, p5js, petdex, pixel-art, plan, pm-briefing, pm-requirement-review-simulator, pokemon-player, polymarket, popular-web-designs, powerpoint, pretext, protocolfromsummary, python-debugpy, requesting-code-review, research-paper-writing, segment-anything, simplify-code, sketch, skill-authoring-principles, skill-portability, songsee, songwriting-and-ai-music, spike, spotify, subagent-driven-development, systematic-debugging, taskrefresh, teams-meeting-pipeline, test-driven-development, touchdesigner-mcp, tutu-confluence-jira, tutu-jira-contract-approval, tutu-jira-okr, tutu-jira-sr, tz-workflow, vllm, webhook-subscriptions, weights-and-biases, workvault-entities, workvault-rag, workvault-sync-infra, writing-plans, xurl, youtube-content, yuanbao, zoom-api-integration

## Текущий tz-dev — 74 скилла

Только системные (bundled) + backlog-analyst, backlog-collector.

**Потеряно из tz-dev (58):** about_usr_skills, all-skills-hygiene, baoyu-article-illustrator, baoyu-comic, check-cron-results, cleanup-after-sync, creative-ideation, cron-journal-write, debugging-hermes-tui-commands, dspy, exchange-monitor, find-proxy-task, full-workvault-backup, get-obsidian-link, godmode, hermes-cost-optimization, hermes-feature, hermes-gateway-setup, hermes-llm-provider-switch, hermes-memory-hygiene, hermes-skills-discovery, hermes-upstream-check, kanban-codex-lane, kanban-orchestrator, kanban-worker, linear, macos-computer-use, mattermost-loop-api, minecraft-modpack-server, mofs-operations, moscow-suburban-trains, movefrom-confluence, movefromff, mpp-to-google-sheets, native-mcp, obliteratus, ocr-and-documents, pixel-art, pm-briefing, pm-requirement-review-simulator, pokemon-player, protocolfromsummary, skill-authoring-principles, skill-portability, spotify, subagent-driven-development, taskrefresh, tutu-confluence-jira, tutu-jira-contract-approval, tutu-jira-okr, tutu-jira-sr, tz-workflow, webhook-subscriptions, workvault-entities, workvault-rag, workvault-sync-infra, writing-plans, zoom-api-integration

## Текущий openai — 104 скилла

Содержит часть потерянных скиллов, которых нет в tz-dev: about_usr_skills, baoyu-article-illustrator, baoyu-comic, check-cron-results, cleanup-after-sync, creative-ideation, cron-journal-write, debugging-hermes-tui-commands, dialog-backlog, dspy, fireflies-obsidian-sync, godmode, hermes-cost-optimization, hermes-feature, hermes-gateway-setup, hermes-vm-migration, kanban-codex-lane, kanban-orchestrator, kanban-worker, linear, local-llm-hardware, macos-computer-use, minecraft-modpack-server, movefrom-confluence, movefromff, multi-document-coordination, native-mcp, obliteratus, ocr-and-documents, pixel-art, pokemon-player, sirene-chat-friends, spotify, subagent-driven-development, webhook-subscriptions, writing-plans

## Текущий anthropic — 77 скиллов

Содержит: about_usr_skills, aggregate-tz-opus-workflow, apple-macos, baoyu-article-illustrator, baoyu-comic, brief-mode, cloud-storage-webdav, creative-ideation, dialog-backlog, dspy, epic-development, exchange-meeting, fireflies-transcripts, godmode, hermes-feature, hermes-gateway-setup, jira-okr, jira-sr, jira-tutu, kanban-orchestrator, linear, media-utilities, minecraft-modpack-server, native-mcp, obliteratus, ocr-and-documents, photo-deduplication, pixel-art, pokemon-player, read-mpp, research-tools, sirene-chat-friends, spotify, status-snapshot, travel-writing, upstream-dependency-monitor, webhook-subscriptions, writing-plans

## Архив куратора anthropic (от 18.06.2026)

Заархивировано 8: excalidraw → architecture-diagram, hermes-cost-optimization → hermes-feature, llama-cpp → serving-llms-vllm, requesting-code-review → systematic-debugging, simplify-code → systematic-debugging, teams-meeting-pipeline → exchange-meeting, telegram-forum-topics → hermes-gateway-setup, test-driven-development → systematic-debugging

## Состояние ПОСЛЕ восстановления (03.08.2026)

### hermes-workspace (git, каноничный источник) — 150 скиллов

Все 132 из бэкапа + 18 добавленных из hermes-config: apple-macos, travel-writing, cloud-storage-webdav, hermes-bugfix-cursor, upstream-dependency-monitor, epic-development, aggregate-tz-opus-workflow, fireflies-transcripts, media-utilities, photo-deduplication, sirene-chat-friends, movefrom-instruments, dialog-backlog, read-mpp, exchange-meeting, status-snapshot, research-tools, brief-mode

### Профиль default — 145 скиллов (2 bundled + 143 симлинка на workspace)

### Профиль tz-dev — 149 скиллов (75 bundled + 74 симлинка на default)

### Архитектура

```
hermes-workspace (git, 150) ──symlink──▶ default (145) ──symlink──▶ tz-dev (149)
```

### Защита

- Крон `restore-skills-daily`: 3:00 ежедневно
- Автосинк GitHub: 2:00 ежедневно (исправлен — больше не стирает скиллы)
- Исправлен `autosync_github.sh`: удалён блок `rm -rf skills && cp ~/.hermes/skills/`
