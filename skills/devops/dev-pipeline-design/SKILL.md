---
name: dev-pipeline-design
description: "Проектируем dev-процесс Hermes: кейсы, блоки, глоссарий."
version: 0.1.0
author: Сирень (обобщение ProcessImprovement 08.09)
platforms: [linux]
metadata:
  hermes:
    tags: [devops, pipeline, kanban, glossary, process-design, hermes-development]
    related_skills: [tz-workflow, hermes-feature, kanban-dev-pipeline-orchestration]
---

# Проектирование / рефакторинг dev-пайплайна Hermes

Единый канон, по которому строится процесс разработки инструментов/скиллов Hermes через канбан. Это **мета-скилл про сам процесс** (а не операционная работа внутри него — то в user-owned `tz-workflow`/`hermes-feature`).

## Ключевые инварианты (проверены на реальной перестройке 07-08.09)
1. **Единый GLOSSARY как канон.** Все термины/фазы/роли/слои живут в одном `TZ/GLOSSARY.md`. Компакт коллизий — в USER.md (виден в каждой TG-сессии); полный — по `read_file` в скиллах перед первой фазой. Запрещённые синонимы — в §7.
2. **Слои различать строго:** кейс ≠ блок ≠ роль ≠ скилл ≠ документ ≠ фаза. Фаза = `PREFIX:фаза` (BRF:, GATE:, TZ:, HF:, ORCH:, REV:, BUG:, RS:, MIG:, DEC:, SK:). Карточка канбана = только фаза, НЕ блок и НЕ кейс.
3. **Блоки — переиспользуемые функции.** Не 8 рукописных цепочек, а библиотека блоков (BRF, BRIEF-CLOSE, TZ-WRITE, REV, TAKE-INTO-WORK, HF-COMPRESS, **PLAN-IMPL-TAIL** (план→гейт→backup→impl→test→docs→ORCH→done), HF-TAIL, DX, RS, MIG-TAIL, DEC-PRE, DECOMM-TAIL, SK-PRE). Кейс = вызов блоков + особые фазы.
4. **Бриф — в TG, не канбан.** Запрет `kanban_block(kind=needs_input)` на TZ/HF-фазах: silent-воркер не ведёт бриф. Граф создаётся после BRIEF-CLOSE.
5. **Манифест/restore/.env/jobs.json/entities.json — только фаза ORCH:shared-state** (Сирень). Исполнитель туда не пишет.
6. **1 agent -p = 1 модель = 1 роль.** Архитектор=cursor-grok-4.6-high, Ревизор=claude-sonnet-5-medium (опц.), Исполнитель/Компрессор/Координатор=composer-2.5.
7. **One-pass auto** проходите только: take-into-work, plan-approve, done. Никогда: diagnose-review, GATE:go, GATE:block-accept.

## Ошибки, которые делали (pitfalls)
- **«Глоссарий DEV» — плохое имя.** Глоссарий один на все кейсы, без суффикса.
- **Коллизии акронимов не очевидны человеку.** BRF/GATE/HF/ORCH «еле угадываются». При первом упоминании — русская расшифровка, дальше канон.
- **Не доверять self-report исполнителя.** composer-2.5 говорит «готово» — проверять `grep`/`read_file`, что файл реально изменён/НЕ изменён.
- **Не воскрешать старые фазы.** После рефакторинга `TZ:analyze`/`TZ:architect` не существуют (содержание в BRF+TZ-WRITE). Запрещённые синонимы: HF:fix, TZ:architect как бриф, HF:docs, HF-TAIL-min→DECOMM-TAIL, «хвост DEV»→PLAN-IMPL-TAIL.
- **Не принимать «утечку» кода за реализацию.** Черновики старой теневой ветки на диске — не основание пропускать ТЗ/план. «Заменить целиком», если логика сырая.
- **Согласование ТЗ ≠ разрешение реализации.** После записи ТЗ — обязательный гейт «берём в работу» перед кодом, даже в one-pass спросить явно на границе ТЗ→код.
- **Gateway НЕ рестартовать изнутри себя.** `hermes gateway restart` из сессии, идущей через gateway (Telegram/канбан-воркер), блокируется Hermes: «gateway would kill this command» (SIGTERM доходит до дочерних). Даже sleep+background детектится. Рестарт — только из внешнего SSH-шелла/`systemctl --user restart hermes-gateway`. НО: если правил `config.yaml` (напр. `kanban.max_in_progress_per_profile`) в live-сессии — не обязательно рестартовать сразу: значения читаются при следующем старте gateway/systemd-перезапуске. Проверка «применилось ли»: `systemctl --user status hermes-gateway | grep Active` — если uptime после записи конфига, значит прочитано.
- **Параллелизм диспетчера — `kanban.max_in_progress_per_profile`, НЕ `max_in_progress`.** Только первый распознаётся `hermes config set` (второй → warning «not recognized» + мусор в config.yaml, удалять вручную). Для параллельных графов: `hermes config set kanban.max_in_progress_per_profile 3`. Глобальный None = без потолка.

## Контракция контекста роли (anti-bloat)
Огромный входной контекст роли (десятки МБ против окна) — признак некорректной
сборки, а не штатного большого контекста: в роль уходит мусор (полные
request/inventory-снимки, дубли входов, широкие операторские команды «перешли всё»).
Лечить сборку — вычленять только нужное роли и фильтровать широкие команды, а НЕ
расширять лимиты и НЕ строить «свидетелей вместимости». Токенизатор и расчётная
константа лимитов — измерители, не основная защита. Диагностика разрастания:
каталог slug мал, большой объём из внешних входов/сгенерированных JSON — смотреть
крупнейшие `*-full-request-*`/`full-inventory*.json` в evidence; начать с
`grep -oE "path: /[^ ]+\.(md|json)" HF-plan.md | awk '{print $2}' | sort -u`.

## Правки владельца в полёте и на паузе по лимиту
- **Владелец изменил правило после запуска роли** (константа, маршрут, фильтр):
  убить уже запущенный invoke ДО того, как роль сделала реальную работу; проверить
  в state, что фаза не вышла из `prepare` (pid жив, awaiting False, artefact_ready
  None) — значит роль штатно не стартовала; затем repair-writer'ом сбросить фазу к
  `awaiting_invoke`, обновить директиву, re-emit и заново invoke-role.
- **На паузе по лимиту/провайдеру** фиксировать решения владельца и результаты
  исследований как дарект-файлы `evidence/.../owner-*.md` и регистрировать их во
  входы контракта (HF-plan.md, phase ORCH, запись `path:`+`purpose:`), чтобы
  возобновлённая роль увидела их без потери. Роли НЕ перезапускать до восстановления.
- Точка подстановки native/default-модели (какой backend/функция читает модель)
  определяется по коду перед изменением; менять в одном месте, не хардкодя имя.

## Resume / где остановился инструмент
Как восстановить прерванную разработку (архив ветки + сохранённый каркас): `references/resume-interrupted-dev.md`.
Прогон тестов USERTOOLS — обязательно через tool-local `.venv` (глобальный python не имеет зависимостей): `references/run-tests-with-tool-venv.md`.
**CHANGE-LIGHT пример обкатки (09.09):** пилот «компрессор ТЗ → deepseek-оркестратор в Hermes» прогнан прямыми правками канона (4 файла: tz-compressor-prompt.md, tz-workflow Шаг 0, GLOSSARY §3, hermes-feature) — минуты против 162+115 мин полного CHANGE. Правки канона ≤3-4 файла — прямыми правками, не разворачивая 16-карточный граф.

## Запуск по триггерам (маршрутизация запроса → кейс → цепочка)
Когда Саша формулирует dev-задачу, сначала определи КЕЙС по триггер-словам, затем выбери цепочку (= сборку блоков из §Ключевые инварианты + каталог кейсов). Таблица (проверена на реальной задаче exchange-contact-upsert 08.09):

| Если Саша говорит… (триггеры) | Кейс | Скиллы / цепочка (блоки) | Модели |
|---|---|---|---|
| «разработай / новый инструмент / создай фичу / сделай новый скилл» | **DEV** (SKILL-DEV для скилла) | `tz-workflow` → BRF(full) → BRIEF-CLOSE → TZ-WRITE(new) → TAKE-INTO-WORK → [comp] → `hermes-feature`: PLAN-IMPL-TAIL | арх grok / рев sonnet / испол composer |
| «доработай / измени / добавь в существующий / поправь инструмент» | **CHANGE** (SKILL-CHANGE для скилла) | `tz-workflow` → BRF(light) → TZ-WRITE(full) → TAKE-INTO-WORK → `hermes-feature`: PLAN-IMPL-TAIL | те же |
| «мелкая доработка существующего **≤3 файла кода + тест + SKILL.md**, аддитивная секция ТЗ, без новых сущностей/cron/.env» | **CHANGE-LIGHT** (добавлен 09.09) | `BRF(light)` → `TZ-WRITE(light)` (patch+version+инвентарь в одном; stabilize/compress/REV skip) → `HF:impl` → `HF:test` → `HF:docs-handoff` → `GATE:done` (скриптовый preflight, без отдельного LLM-воркера) | арх grok-medium или composer; REV OFF вне shared-модулей |
| «почини / баг / не работает / ошибка» | **BUGFIX** | `hermes-feature` → DX (BUG:diagnose→GATE:diagnose-review) → BRF(delta) → TZ-WRITE(patch) → TAKE-INTO-WORK → PLAN-IMPL-TAIL | арх grok (диагноз read-only) |
| «исследуй / проанализируй / разбери» | **RESEARCH** | `hermes-feature` (research-метод) → BRF(scope) → RS (collect→analyze→[REV:report]→done) | арх / исполнитель |
| «мигрируй / перенеси на новую среду» | **MIGRATION** | `tz-workflow`→`hermes-feature` → BRF(light) → TZ-WRITE(freeze) → TAKE-INTO-WORK → MIG-TAIL | арх |
| «удали инструмент / выключи крон / сними» | **DECOMM** | `hermes-feature` → BRF(confirm) → DEC-PRE → DECOMM-TAIL | арх+коорд |

Правила маршрутизации:
- **ТЗ-процесс (бриф, ТЗ, кейсы)** → `tz-workflow`; **реализация/код/тесты/исследование** → `hermes-feature`; вызов Cursor → `cursor-cli`+`cursor-task-context`.
- **Бриф всегда в TG** (архитектор готовит вопросы с 2-3 вариантами + рекомендацию; Сирень транслирует, не выдумывает). Канбан-граф — **после** BRIEF-CLOSE.
- **Ревизор** опционален: DEV/MIGRATION/SKILL-DEV — рекомендую ON; BUGFIX/мелочь/≤2 файла — OFF.
- Реализация — только после явного «берём в работу» (граница ТЗ→код); даже в one-pass спросить явно.
- «Делай в 1 проход» на границе ТЗ→код ≠ автоматическое разрешение кода: гейт по-прежнему нужен, но одно подтверждение вместо цепочки.

## Что НЕ трогать
Ядро канбана (по DevKanbanPipeline). User-owned скиллы tz-workflow/hermes-feature/cursor-cli/cursor-task-context — правит Cursor в hermes-workspace, не напрямую.

## Верификация
После смены скиллов — `restore-all-skills.sh`; проверить `grep ^version` в `~/.hermes/profiles/default/skills/devops/<skill>/SKILL.md`.