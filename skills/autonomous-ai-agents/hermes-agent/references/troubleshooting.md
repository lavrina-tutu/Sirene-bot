> Verify config keys and operational steps against the current code before applying these recipes. Examples describe their original environment.

## Troubleshooting

### Voice not working
1. Check `stt.enabled: true` in config.yaml
2. Verify provider: `pip install faster-whisper` or set API key
3. In gateway: `/restart`. In CLI: exit and relaunch.

### Tool not available
1. `hermes tools` — check if toolset is enabled for your platform
2. Some tools need env vars (check `.env`)
3. `/reset` after enabling tools

### Model/provider issues
1. `hermes doctor` — check config and dependencies
2. `hermes login` — re-authenticate OAuth providers
3. Check `.env` has the right API key
4. **Copilot 403**: `gh auth login` tokens do NOT work for Copilot API. You must use the Copilot-specific OAuth device code flow via `hermes model` → GitHub Copilot.

### Changes not taking effect
- **Tools/skills:** `/reset` starts a new session with updated toolset
- **Config changes:** In gateway: `/restart`. In CLI: exit and relaunch.
- **Code changes:** Restart the CLI or gateway process

### Skills not showing
1. `hermes skills list` — verify installed
2. `hermes skills config` — check platform enablement
3. Load explicitly: `/skill name` or `hermes -s name`

### Gateway issues
Check logs first:
```bash
grep -i "failed to send\|error" ~/.hermes/logs/gateway.log | tail -20
```

Common gateway problems:
- **Gateway dies on SSH logout**: Enable linger: `sudo loginctl enable-linger $USER`
- **Gateway dies on WSL2 close**: WSL2 requires `systemd=true` in `/etc/wsl.conf` for systemd services to work. Without it, gateway falls back to `nohup` (dies when session closes).
- **Gateway crash loop**: Reset the failed state: `systemctl --user reset-failed hermes-gateway`

### Platform-specific issues
- **Discord bot silent**: Must enable **Message Content Intent** in Bot → Privileged Gateway Intents.
- **Slack bot only works in DMs**: Must subscribe to `message.channels` event. Without it, the bot ignores public channels.
- **Windows-specific issues** (`Alt+Enter` newline, WinError 10106, UTF-8 BOM config, test suite, line endings): see the dedicated **Windows-Specific Quirks** section above.

### session_search returns empty results for recent sessions

**Symptom:** `session_search` with keyword queries returns 0 results even for sessions that clearly exist (visible in `session_search` recent mode).

**Root cause (verified May 2026):** FTS5 combines all tokens with AND — a query like `"runtime_header не существует вариант 1 вариант 2 модель ответ"` requires a single message containing ALL those words simultaneously. No such message exists → empty result.

The index is almost certainly fine. `messages = messages_fts` row counts match; insert/update/delete triggers are present.

**Fix: use short, 1-3 word queries.** Examples:
- ❌ `"runtime_header не существует вариант 1 вариант 2 модель ответ"` → 0 results
- ✅ `"runtime_header вариант"` → finds the session immediately
- ✅ `"вариант runtime_footer"` → same

When unsure what keywords to use, first call `session_search` with no query (recent mode) to confirm the session ID exists, then search with the 2-3 most distinctive words from the topic.

**Verify the index is healthy (if in doubt):**
```bash
sqlite3 "$LOCALAPPDATA/hermes/state.db" \
  "SELECT (SELECT COUNT(*) FROM messages) AS msg, (SELECT COUNT(*) FROM messages_fts) AS fts;"
# Both counts should match
```

### Настройка персонажа (personality) в config.yaml

**Добавить кастомную личность** в `personalities` и активировать через `display.personality`:

```yaml
agent:
  personalities:
    my_persona: "Описание персонажа здесь."

display:
  personality: my_persona
```

**Важно:** вступает в силу только с новой сессией (`/new` или новый запуск). `display.personality` работает — выбирает один из ключей из `personalities`. Стандартные личности: `helpful`, `concise`, `kawaii`, `catgirl`, `pirate`, `shakespeare` и др.

**Для Саши настроена личность `sirene`** — см. скилл `sirene-chat-friends` для деталей персонажа.

### Идентичность агента: SOUL.md vs agent.personalities — не дублировать

Hermes даёт ДВА независимых механизма для идентичности агента, и это частый источник путаницы/дублирования:

| Механизм | Как работает | Когда выбирать |
|---|---|---|
| `~/.hermes/SOUL.md` (или `~/.hermes/profiles/<profile>/SOUL.md`) | **Primary identity slot** (slot #1 системного промпта). `agent/prompt_builder.py::load_soul_md()` читает файл первым; если существует и непустой — заменяет хардкодную заглушку `DEFAULT_AGENT_IDENTITY`. Не зависит от `display.personality`, не переключается. | Основной, стабильный дом идентичности: кто агент, характер, ценности. Не требует активного переключателя — грузится всегда. |
| `agent.personalities.<name>` + `display.personality` | Overlay-слой, переключаемый на лету через `/personality` или `hermes config set display.personality <name>`. | Когда нужно быстро переключаться между несколькими готовыми личностями (helpful/kawaii/pirate/своя) без правки файла. |

**Правило:** выбрать ОДИН как источник правды для идентичности, не писать одно и то же в оба + в скилл персоны. Три копии одного текста (SOUL.md + personalities + скилл персоны) гарантированно рассинхронизируются при следующей правке — кто-то обновит одну копию и забудет остальные.

**Рекомендуемая схема** (проверена на практике, 02.07.2026): идентичность (имя, характер, soul-ценности, принципы) → `SOUL.md`. Процедуры/воркфлоу для этой персоны (модели по задачам, инфраструктура, специфичные правила) → отдельный скилл персоны, который явно ссылается на `SOUL.md` вместо копирования из него. `agent.personalities.<name>` держать пустым/дефолтным, если переключение личностей не нужно; `display.personality` можно оставить `''`.

**Изменения SOUL.md/config.yaml требуют новой сессии** (`/new`) или рестарта gateway — system_prompt кэшируется на весь сеанс, live-редактирование не подхватывается на лету.

**При ревизии скилла-персоны — держите под рукой источник правды по каждому правилу.** Правила выбора модели для делегирования (какая модель для каких задач, cronjob vs delegate_task) естественно принадлежат `agent.system_prompt` — не копировать их в скилл персоны отдельной формулировкой, иначе при смене основной модели придётся править в двух местах и они разойдутся. В скилле персоны — только ссылка вида «полные правила см. agent.system_prompt».

### Compression model vs main model context mismatch

**Symptom:** на старте сессии появляется предупреждение:
`⚠ Compression model claude-haiku-4-5 context is 200,000 tokens, but the main model claude-sonnet-4-6's compression threshold was 500,000 tokens. Auto-lowered this session's threshold to 200,000 tokens`

**Причина:** `compression.threshold` (0.5) × context_length основной модели (1M) = 500K > лимита compression model (200K).

**Решение (рекомендуемое):** поставить Sonnet как compression model — тогда порог 500K корректен и предупреждение исчезает:
```yaml
auxiliary:
  compression:
    provider: anthropic
    model: claude-sonnet-4-6   # вместо claude-haiku-4-5
```

**Альтернатива:** снизить threshold до 0.17 (1M × 0.17 = 170K < 200K лимита Haiku) — дешевле, но сжатие начинается раньше.

**Важно:** Haiku остаётся доступен для delegate_task и других явных вызовов — это не конфликтует с выбором compression model.

**Механизм (из кода):** `run_agent.py::_check_compression_model_feasibility()` — при старте сессии сравнивает `aux_context` и `threshold_tokens`, при несоответствии жёстко затирает threshold до aux_context. Изменить per-model пороги через config.yaml невозможно — только один глобальный `compression.threshold`.

### Auxiliary models not working
If `auxiliary` tasks (vision, compression, session_search) fail silently, the `auto` provider can't find a backend. Either set `OPENROUTER_API_KEY` or `GOOGLE_API_KEY`, or explicitly configure each auxiliary task's provider:
```bash
hermes config set auxiliary.vision.provider <your_provider>
hermes config set auxiliary.vision.model <model_name>
```

### Switching between Anthropic and OpenAI provider groups

For temporary provider outages or cost optimization, maintain two complete configuration profiles.

**`hermes model` requires an interactive terminal** — it cannot be scripted or piped. For programmatic switching, use `hermes config set`:

```bash
# Switch main model to OpenAI
hermes config set model.default chat-latest
hermes config set model.provider custom
hermes config set model.base_url https://api.openai.com/v1

# Switch main model to Anthropic
hermes config set model.default claude-sonnet-4-6
hermes config set model.provider anthropic
# base_url not needed for anthropic provider — clear it:
hermes config set model.base_url ""
```

**After switching, restart the gateway** so it picks up the new config:
```bash
systemctl --user restart hermes-gateway.service
```

**Recommended: keep backup config snapshots** in `~/.hermes/profiles-backup/` with descriptive names (e.g. `openai-profile-active-20260603.yaml`, `anthropic-profile-active-20260603.yaml`) so you can diff against them when switching.

**Important verification steps** — changing the main model does NOT cascade:
- `hermes config set` only touches the key you specify; delegation, auxiliary, compression, and cron-job models remain unchanged.
- Audit cron jobs with `hermes cron list` — they may still point to the old provider.
- A system may be in a mixed state (chat on OpenAI, cron jobs still on Anthropic) even though the interactive session works.

Before declaring a full provider migration complete, verify:
1. Main model (`model.default` + `model.provider`)
2. Delegation configuration (`delegation.model` + `delegation.provider`)
3. Auxiliary configuration (`auxiliary.*.provider` + `auxiliary.*.model`)
4. Compression configuration (`auxiliary.compression.*`)
5. Every cron job model/provider override

