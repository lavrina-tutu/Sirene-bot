# qmd — история внедрения и отказа (архив)

## Хронология

- **08-09.07.2026** — внедрён qmd (`@tobilu/qmd`) как MCP semantic search сервер поверх WorkVault. 3 коллекции: `meetings-summary` (542 дока), `tz-backlog` (22), `confluence` (4). CPU-only VM, без GPU.
- **13.07.2026** — обнаружен питфолл: `mcp_qmd_query` может зависать по таймауту 300с целиком на простых запросах (не деградирует до частичного ответа).
- **16.07.2026** — Саша распорядился полностью исключить qmd из системы как ненадёжный инструмент. План отката составлен Opus (cron job `62516215d819`), реализован Sonnet в тот же день.

## Причина отказа

- CPU-only эмбеддинг: индексация 568 файлов заняла ~30-87 минут, с сотнями сбоев "LLM session expired before embedding chunk" в последних прогонах — индекс не завершался чисто.
- Зависания по 300с на простых запросах в рантайме — непредсказуемо, не деградирует gracefully.
- Полный LLM-rerank (`rerank: true`) — >90с, неприемлемо для живого диалога без постоянно прогретого daemon.
- На практике даже при рабочем qmd — реальные запросы Саши ("что ожидает X на встрече") надёжнее решались прямым `search_files` по имени файла + `read_file`, чем через qmd.
- Ни один skill/cron/USERTOOLS-скрипт не был на нём завязан — единственный потребитель была сама Сирень через MCP tools.

## Что было удалено (16.07.2026)

- systemd user-сервис `qmd-daemon.service` (юнит-файл, автозапуск)
- Регистрация MCP-сервера в `~/.hermes/config.yaml` (`mcp_servers.qmd`)
- npm-пакет `@tobilu/qmd` глобально + бинарник `~/.local/bin/qmd`
- Кэш моделей эмбеддинга `~/.cache/qmd` (~2.2GB)
- Индексы коллекций `~/.local/share/qmd-collections` (~12MB)
- Упоминания в скилле `research-paper-writing` (точечные строки)

## Бэкапы (на случай отката)

Созданы перед удалением в `~/backups/qmd-removal-2026-07-16/`:
- `config.yaml.bak` — конфиг с рабочей регистрацией MCP
- `qmd-daemon.service.bak` — systemd unit-файл
- `qmd-collections.bak` — снимок индексов (12MB, экономит ~30-87 мин переиндексации)
- `npm-version.txt` — точная версия пакета (`@tobilu/qmd@2.5.3`)

## Полное восстановление (если понадобится в будущем)

```bash
npm install -g @tobilu/qmd@2.5.3
cp ~/backups/qmd-removal-2026-07-16/qmd-daemon.service.bak ~/.config/systemd/user/qmd-daemon.service
systemctl --user daemon-reload
cp -a ~/backups/qmd-removal-2026-07-16/qmd-collections.bak ~/.local/share/qmd-collections
cp ~/backups/qmd-removal-2026-07-16/config.yaml.bak ~/.hermes/config.yaml
systemctl --user enable --now qmd-daemon.service
sleep 30   # первый старт долгий — скачивание моделей эмбеддинга (~2.2GB, не забэкаплено)
bash ~/.hermes/scripts/restart_gateway_MANUAL_ONLY.sh
```

Скилл `workvault-rag` в текущем виде (2.0.0) не содержит qmd-механики — если qmd
восстанавливается, нужно вручную вернуть недостающие разделы из git-истории:
```bash
cd ~/hermes-workspace
git log --all --oneline -- skills/research/workvault-rag/ | head -5
git show <hash-до-16.07.2026>:skills/research/workvault-rag/SKILL.md
```

## Известные питфоллы qmd (для справки, если возвращать)

1. qmd НЕ резолвит симлинки (`fast-glob` не следует по `ln -sf`) — нужен copy-based filter-farm.
2. `npm install -g @tobilu/qmd` может упасть на компиляции native-биндингов без `cmake`/`gcc-c++`.
3. На VM может быть несколько независимых установок Node.js — проверять `which node`/`npm config get prefix` перед хардкодом путей.
4. `hermes mcp add` требует интерактивного stdin (`printf "n\ny\n" | hermes mcp add ...`).
5. Systemd unit + собственный `--daemon`-флаг инструмента = конфликт (используй foreground + `Restart=on-failure`).
6. Первый `qmd embed` на CPU может занять кратно дольше плана (568 файлов — ~87 минут).
7. qmd не подходит для exhaustive-запросов "все X от Y за период Z" — не индексирует дату как фильтруемое поле, текстовый намёк на период не работает как фильтр.
