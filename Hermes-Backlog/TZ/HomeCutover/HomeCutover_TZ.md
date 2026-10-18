---
tool: HomeCutover
type: infra_plan
title: "Переезд корп. ВМ на домашнюю персональную машину: ownCloud-сервер + личный Hermes + Obsidian, один пользователь"
version: 0.1.0
date: 2026-10-18
status: draft
author: архитектор (cursor-grok-4.6-high, TZ:patch → TZ:finalize, slug pereezd-vm-na-domashnyuyu-mashinu-personalnuyu-o)
last-section-added: 2026-10-18 — v0.1.0 TZ:finalize канон + инвентарь; Q-1…Q-7 открыты
case: MIGRATION
slug: pereezd-vm-na-domashnyuyu-mashinu-personalnuyu-o
packet_slug: pereezd-vm-na-domashnyuyu-mashinu-personalnuyu-o
source_research:
  - Hermes-Backlog/research/20261016_sobstvennaya-mashina-pod-siren-collect.md
  - Hermes-Backlog/research/20261016_sobstvennaya-mashina-pod-siren-analyze.md
  - Hermes-Backlog/dev/sobstvennaya-mashina-pod-siren-so-vsemi-modulyam/AC-report.md
  - Hermes-Backlog/dev/sobstvennaya-mashina-pod-siren-so-vsemi-modulyam/journal.md
precedent: Hermes-Backlog/MigrationToVM/TZ.md
reuse_first: "не USERTOOL; не rsync с ВМ; не второй клон MigrationToVM; cutover + [NEW-ENTITY] ownCloud-сервер"
---

# HomeCutover — freeze-ТЗ переезда ВМ → домашняя машина

выжимка ≠ SoT. При расхождении открыть **этот файл**. RESEARCH 16.10 (`sobstvennaya-mashina-…`) — факты AS-IS и таблица рисков; **вердикт «ВМ оставить, mini не покупать, ownCloud = rclone-клиент» проигрывает ответам Саши Q-2=2 и Q-3=3**.

Маркер `[NEW-ENTITY, требует согласования Саши]` **не сглаживать** общими словами «просто ownCloud» / «синк как на ВМ».

**Оркестратору:** это master-ТЗ пакета. `tz_path` / `tz_version=0.1.0` уже в `_state.json` после `TZ:patch`. `TZ:finalize` (этот ход) пишет строку `MAIN_TZ_INVENTORY.md` под `LOCK_EX`; bump version **нет** (текст freeze не менялся). `status: draft` остаётся: Q-1…Q-7 открыты (`approved` только при закрытых Q). Stub `tools.home_cutover` в манифесте — зона `ORCH:shared-state` (status `draft`, `tz_ref` → этот файл), не `TZ:finalize`. Маркер `[NEW-ENTITY, требует согласования Саши]` ownCloud-сервер **не** внедрять в `EcosystemManifest.json` / `entities.json` из этой фазы.

Код, закупка, установка ownCloud, cutover ВМ, `jobs.json`, рестарт gateway — **не** пишутся. План блоков — фаза `MIG:plan`, не этот файл как IAC.

---

## Цель

Зафиксировать нормы **cutover** корп. ВМ `hermes-agents.devel.tutu.ru` на **домашнюю персональную машину одного пользователя (Саша)**:

1. **Личный Hermes** — аналог текущего стека ВМ (gateway, serve, кроны, USERTOOLS, личность Сирени), не второй вечный клон рядом с ВМ.
2. **ownCloud-сервер на своей машине** — `[NEW-ENTITY, требует согласования Саши]` (Q-2=2, 16.10). Это **не** rclone-клиент к `owncloud.tutu.ru`.
3. **Obsidian** — vault на личном сервере, GUI на домашней машине.
4. **Один пользователь** — не multi-tenant, не семейный NAS «на всех».
5. **Диагностика рисков** (этот freeze) + **план cutover** (фаза `MIG:plan` + `MIG:block-k`).

Миссия Sabotages RESEARCH-дефолт: Саша **осознанно** выбрал замену ВМ и новый сервер. Архитектор не откатывает выбор к «дешевле оставить ВМ».

---

## Зафиксированные решения (вход freeze)

Источник: ответы Саши на Q-1..Q-3 слага `sobstvennaya-mashina-pod-siren-so-vsemi-modulyam` (journal 2026-10-16T19:55; RESEARCH уже `GATE:done`). Слаг `lichnyy-nezavisimyy-ot-kompanii-agent-na-svoem-z` заведён, **фазы RESEARCH не исполнялись** — дешевле/базовая M6 оцениваются **здесь**, отдельного отчёта ждать нельзя.

| ID | Вопрос | Ответ Саши | Следствие этого ТЗ |
|---|---|---|---|
| Q-1 (16.10) | Счёт $150 Tutu/OpenRouter | **1** — корпоративный Tutu, для Саши $0 поверх | opex железа = capex машины; пилот GLM не стартовать из этого слага |
| Q-2 (16.10) | ownCloud | **2** — **СЕРВЕР на своей машине** | `[NEW-ENTITY, требует согласования Саши]`; rclone-клиент к `owncloud.tutu.ru` **не** закрывает норму |
| Q-3 (16.10) | Личный mini | **3** — **замена ВМ, cutover** | кейс **MIGRATION**; прецедент MigrationToVM (два клона) **не** копировать как целевую модель |

Дополнения периметра (journal `lichnyy-…`, 16.10, RESEARCH не бежал): смотреть **дешевле** M6/M5 Pro (б/у, x86/NUC); проверить, хватит ли **базовой M6 16 ГБ/256 ГБ**. Ответ freeze: **базовая 16/256 для этой миссии недостаточна** (§5).

Не пересматривается соседними поездами 16.10 (не этот слаг): Cursor снят с ролей; архитектор/исполнитель — Codex `gpt-6.1-sol`; ревизор — Tutu Sonnet 5.5; Claude Pro / Kimi-первым / локальная LLM как замена Tutu — **нет**. Профиль **B** (M5 Pro 64 ГБ, локальные 27–32B) **вне скоупа**.

---

## Reuse-first

| Уже есть | Почему не закрывает | Что делаем |
|---|---|---|
| ВМ AlmaLinux 9.7, 4c / 11 ГиБ / 199 ГБ, swap 1.8 ГБ used | это **источник** cutover, не целевой хост | инвентарь AS-IS; не выключать до принятого блока отката |
| rclone WebDAV `owncloud:` → `https://owncloud.tutu.ru/remote.php/webdav` (user `tkachenkoav`) | **корп. клиент**, сервера на ВМ нет | паттерн timers `owncloud-sync` / `owncloud-inbox-pull` **reuse как клиент ноутбука** к *новому* серверу; сам сервер — новая сущность |
| `owncloud-sync.timer` / `owncloud-inbox-pull.timer` (~10 мин) | держат синк WorkVault с **tutu.ru** | после cutover перенацелить remote; на ВМ до cutover **не ломать** |
| Obsidian AppImage `~/obsidian.AppImage` + VNC :1 / XFCE | GUI на ВМ, не домашний UX | Linux-цель: тот же AppImage; Mac-цель: нативный Obsidian. Vault не копировать «мимо» сервера |
| MigrationToVM (`Hermes-Backlog/MigrationToVM/TZ.md`) | **Windows→ВМ**, два бота, **без** cutover Windows | reuse: блоки + приёмка Саши + отдельный бот на время параллели; **не** reuse «два вечных клона» |
| `TZ-storage-system` + rclone WorkVault | шина ВМ↔ноут через **корп.** ownCloud; `~/WorkVault_backup/` **не** синкается | личный сервер = новая шина; backup-контур VM-only обязан войти в план блоков |
| USERTOOLS / 25 enabled jobs / gateway+serve systemd | Linux-venv, tutu-сеть, `llm-gateway.tutu.ru` | копирование стека = MIGRATION, не rsync; без VPN MoveFrom* слепнут |
| Honcho в digest | на ВМ **не запущен** | не поднимать «за компанию» на домашней машине |
| RESEARCH 16.10 SKU M6 32/512 «если второй инстанс» | Саша выбрал **замену**, плюс **сервер** | пересчитать RAM/диск: минимум **32 ГБ / 512 ГБ**; 16/256 отвергнут |

---

## AS-IS (живая ВМ 2026-10-18)

Сверка с collect 16.10: диск 57→**58 ГБ**; остальное в допусках. Секреты (пароли VNC/rclone/Yandex) в это ТЗ **не** копировать.

| Параметр | Значение |
|---|---|
| Хост | `hermes-agents.devel.tutu.ru`, AlmaLinux 9.7, 4 vCPU |
| RAM / swap | 11 ГиБ; swap 4 ГБ, **used ~1.8 ГБ** (узкое место — RAM) |
| Корень `/` | 199 ГБ, **58 ГБ** used (29%) |
| `~/.hermes` | ~18 ГБ (`_Archives` ~8.3 + `state.db` ~3.9 + installs/tools/cache) |
| WorkVault | ~151 МБ (маркер `.obsidian` есть) |
| USERTOOLS | ~1.4 ГБ |
| hermes-workspace | ~128 МБ |
| cursor-agent cache | ~1.7 ГБ |
| Кроны | `jobs.json` n=30, **enabled=25** |
| Systemd --user running | `hermes-gateway`, `hermes-serve` |
| ownCloud | **только клиент** rclone WebDAV на `owncloud.tutu.ru`; timers каждые ~10 мин |
| Obsidian процесс | не обязателен; AppImage на диске; Xvnc `:1` порт 5901 жив |
| Шлюз моделей | `https://llm-gateway.tutu.ru/api/openrouter/v1` (Tutu) |
| Сеть корп. API | Loop / Exchange / Confluence / Zoom / Fireflies — с этой сети / VPN 10.254.0.0/16 |

Рабочий минимум без `_Archives` ≈ 10 ГБ `.hermes` + 1.4 USERTOOLS + vault + запас. **Сервер ownCloud этого объёма не ест** — ест данные пользователей и версии; на ВМ пользовательских данных ownCloud **нет**, они на `owncloud.tutu.ru`.

---

## TO-BE (freeze, не раскладка кабелей)

Целевой хост — **домашняя персональная машина Саши**, always-on относительно бытового UPS (не датацентр tutu). На ней сосуществуют три слоя:

```
[домашняя машина, 1 пользователь]
├── ownCloud-сервер          # [NEW-ENTITY] HTTP(S) + БД + диск данных
│     └── vault Саши         # WorkVault + личный Obsidian-vault (Q-7)
├── личный Hermes            # gateway + serve + jobs + USERTOOLS + память Сирени
└── Obsidian GUI             # клиент к локальному/WebDAV vault
```

Ноутбук Саши после cutover ходит в **личный** сервер (rclone/офиц. клиент), не обязан писать в `owncloud.tutu.ru`. Корп. ownCloud **не декомится этим слагом** (чужой контур компании).

Личный Hermes = **замена** ВМ-инстанса, не третий вечный клон. Параллель ВМ+дом **только** на время блоков, с **разными** Telegram-токенами (иначе `getUpdates` дерутся). После принятого cutover ВМ-gateway гасится блоком с `GATE:block-accept`.

Оркестрация моделей **остаётся внешней** (Tutu DeepSeek-flash + Sonnet REV + Codex Sol). Локальная LLM **не** входит. После cutover доступ к `llm-gateway.tutu.ru` и MoveFrom* = функция **VPN** (Q-3), не «магия mini».

---

## `[NEW-ENTITY, требует согласования Саши]`

Не сглаживать. Не создавать записи в `EcosystemManifest.json` / `entities.json` в этом ходе (ORCH).

| Сущность | Статус | Почему новая | Что запрещено называть «уже есть» |
|---|---|---|---|
| **ownCloud/ownCloud-family сервер** на домашней машине | **[NEW-ENTITY, требует согласования Саши]** (Q-2=2 уже выбрал сервер; продукт CE vs Nextcloud = Q-2 этого ТЗ) | на ВМ сервера нет; remote — корп. `owncloud.tutu.ru` | rclone-клиент, «папка OwnCloud», Yandex.Disk, Syncthing |
| **HomeCutover** (этот infra-plan) | stub манифеста на ORCH | нет `tools.home_cutover` в digest | MigrationToVM, EntitiesMigration |
| Личный Telegram-бот cutover | опция Q-4; если новый бот — сущность канала, не USERTOOL | `@sirene_vm_bot` = ВМ | «тот же токен на двух хостах» |
| Личный WebDAV/ownCloud remote ноутбука | следствие сервера | сейчас ноут, скорее всего, тоже смотрит tutu.ru | не менять remote ВМ до блока cutover |

`[NEW-ENTITY]` чужой Claude внутри Codex / custom Responses — **не предлагать** (соседи 16.10).

---

## Железо (freeze скоупа A+C, cutover)

Профиль **A** (аналог ВМ без локальной LLM) **плюс** профиль **C** (ownCloud-сервер) **на той же** машине, без ВМ как overflow.

| | Норма |
|---|---|
| RAM | **32 ГБ минимум**. 16 ГБ = комфорт одного A; C даёт +2–4 ГБ PHP/DB/индекса; пики gateway+Cursor/Codex+GUI уже жрут swap на 11 ГБ. 16 ГБ на cutover = снова swap, плюс сервер |
| Диск | **512 ГБ минимум**. 256 ГБ: сейчас 58/199 на ВМ без пользовательского стора сервера; `_Archives` 8+ ГБ, кэши агентов, версии ownCloud, ОС. Для сервера+стек 256 ГБ — впритык и без запаса |
| CPU | 4 ядра достаточно (узкое место RAM/диск, не ядра); 8 — запас GUI+индекс ownCloud |
| Профиль B / M5 Pro 64 ГБ | **отвергнут** (локальная LLM не в скоупе; TCO) |
| **Mac mini M6 16 ГБ / 256 ГБ ($899)** | **отвергнут для этой миссии**. Ответ на «хватит ли базовой?»: **нет** |
| Минимум SKU | **32 ГБ RAM / 512 ГБ диск**, независимо от вендора |
| macOS vs Linux | Linux ближе к Alma (systemd, venv, ownCloud/Nextcloud штатно, Obsidian AppImage уже проверен). Mac — нативный Obsidian, но **systemd→launchd**, Linux-USERTOOLS, сервер в Docker/brew. Выбор = **Q-1** |
| Дешевле Apple | x86 mini-PC / NUC / рефурб 32/512 обычно ниже capex M6 32/512 (~$1499). Для A+C и «как можно дешевле» Linux-коробка **допустима и рекомендуется**, если Саша не ставит нативный macOS-Obsidian выше TCO |

Закупка **не** этот `TZ:patch`. `MIG:plan` ставит блок «железо на столе» с `GATE:block-accept`.

---

## Диагностика рисков

R2/R3/R4 из RESEARCH 16.10 **переводятся из «не делать cutover» в «делать cutover явно, с блоками и приёмкой»**. Не чинить код в этом ходе.

| ID | Риск | Серьёзность | Норма freeze / куда |
|---|---|---|---|
| R-NET | Дом без tutu-сети: `llm-gateway.tutu.ru`, Loop, Exchange, Confluence, Zoom, Fireflies слепнут | критический для «аналога ВМ» | VPN always-on **или** сознательный отказ от корп. коннекторов (Q-3). Cutover без ответа Q-3 запрещён |
| R-OC | Сгладить сервер до rclone-клиента | критический для Q-2 | AC-002; маркер `[NEW-ENTITY]` |
| R-CORP-OC | Спутать личный сервер с `owncloud.tutu.ru` | высокий | личный сервер **не** деплой корп. ownCloud; данные WorkVault копируются **осознанным** блоком, не «переездом tutu.ru» |
| R-TOKEN | Один Telegram-токен на ВМ и дома | высокий | запрет; параллель = два бота (как MigrationToVM) |
| R-OS | macOS ≠ Alma systemd/venv | высокий | если Q-1=Mac — блоки launchd+venv, не rsync unit-файлов |
| R-BACKUP | `~/WorkVault_backup/` VM-only, не в rclone | высокий | блок бэкапа **до** гашения ВМ; иначе архив ТЗ/снапшоты исчезают с хостом |
| R-ARCH | Тащить `_Archives` 8+ ГБ и `state.db` 3.9 ГБ | средний | по умолчанию **не** тащить `_Archives` на домашний диск; state.db — решение блока (новый vs копия) |
| R-PII | Личный сервер + копия WorkVault/сессий | высокий | один пользователь, TLS/оверлей (Q-6), не выставлять WebDAV в открытый интернет без аутентификации |
| R-UPS | Дом: свет / канал / рестарт | высокий | always-on = UPS + автозапуск gateway/сервера; иначе это не замена ВМ |
| R-DUAL | Два Hermes пишут в один vault | высокий | на время параллели — разные боты **и** либо разные префиксы записи, либо дом read-only vault до cutover |
| R-SECRET | Секреты `.env` в git / в ТЗ / в чат | критический | scp/SSH, chmod 600; **не** коммитить; в этом файле секретов нет |
| R-KANBAN | Смешать этот MIGRATION с W4 выключением канбана | средний | AC-017/018 **чужого** DevWorkflow-W4; сюда не брать |
| R-16G | Купить 16/256 «как базовую» | высокий | отвергнуто §5; блок закупки сверяет 32/512 |
| R-HONCHO | Поднять Honcho «раз уж своя машина» | низкий | вне скоупа |
| R-GLM | MiniMax/GLM wizard пишет `~/.hermes/config.yaml` | средний | не запускать без отдельного CHANGE |
| R-DECOMM-VM | Выключить ВМ в день покупки | критический | ВМ жива до блока cutover + окно отката (Q-5) |

---

## Cutover — нормы для `MIG:plan` (не IAC, не exec)

Порядок смысла. Имена `MIG:block-k` даёт `MIG:plan` через `pipeline recipe-add`. Этот freeze **запрещает** `GATE:done` слага с пустым списком блоков, пока цель — переезд, а не «положили текст в TZ».

1. **Freeze принят** (этот файл + `TZ:finalize` + AC в origin).
2. **`MIG:plan`** — блоки с приёмкой Саши (`GATE:block-accept` never auto). Минимум блоков по смыслу (имена — плану):
   - B0 ответы Q-1..Q-7, которые план ещё не закрыл;
   - B1 железо 32/512 на столе;
   - B2 сеть (VPN/оверлей/TLS) по Q-3/Q-6;
   - B3 `[NEW-ENTITY]` сервер ownCloud-family, один пользователь, бэкап сервера;
   - B4 личный Hermes (systemd или launchd), **новый** бот, параллель с ВМ;
   - B5 Obsidian на vault сервера;
   - B6 перенос WorkVault/памяти **без** слепого `_Archives`;
   - B7 перенацел rclone ноутбука на личный сервер;
   - B8 бэкап `WorkVault_backup` + секреты ВМ **до** гашения;
   - B9 cutover: стоп gateway ВМ, дом = SoT;
   - B10 окно отката (ВМ не destroy).
3. **`HF:backup`** — снапшот конфигов/ТЗ **до** exec блоков, не вместо B8.
4. Exec блока без фразы Саши на `GATE:block-accept` — запрещён.
5. Пока ВМ жива: не отключать `owncloud-sync` на ВМ «на глаз»; не класть старый токен в домашний `.env`.

Откат: включить `hermes-gateway` на ВМ, вернуть polling её боту, дом-gateway остановить. Vault: копия на ВМ + последний бэкап B8. Сервер дома можно оставить как стор, не как оркестратор.

---

## Что НЕ трогать

| Объект | Запрет |
|---|---|
| Боевой ВМ-контур до принятого блока cutover | не гасить `hermes-gateway` / `hermes-serve`; не revoke токена `@sirene_vm_bot`; не ломать rclone `owncloud:` → tutu.ru |
| `jobs.json` / кроны | не создавать и не переносить без «ставь кроны» |
| Gateway процесс | не рестартовать из этого слага |
| `EcosystemManifest.json`, `entities.json`, per-tool `.env`, секреты в YAML | не писать в TZ:patch / MIG:plan; stub HomeCutover — только ORCH |
| `~/hermes-agent` ядро | не патчить «ради macOS» в этом freeze |
| `TZ/DevWorkflow/**`, DKP, GLOSSARY канон кейсов/фаз | не смешивать с W4 канбана; AC-017/018 не сюда |
| Профильные USERTOOLS (PFS, MOFS, MoveFrom*, Loop, Exchange) | не переписывать «под дом» в freeze; адаптация — блоки после VPN-решения |
| `TZ/ProtocolFromSummary/**` / `task_slug` | чужой поезд |
| Профиль B, Ollama, M5 Pro, локальная LLM как замена Tutu | не закладывать |
| Honcho docker | не поднимать |
| GLM/MiniMax wizard | не запускать |
| Корп. `owncloud.tutu.ru` как хост | не админить, не DECOMM, не требовать root у компании |
| Секреты | не вносить в ТЗ, journal origin, git |
| MigrationToVM STATUS.md пароли | не копировать |
| Закупка / установка сервера / rsync боевых `.env` | не этот `TZ:patch` |

---

## Связи с экосистемой

| Компонент | Роль | Как вызывать | Ограничение |
|---|---|---|---|
| RESEARCH 16.10 collect/analyze | AS-IS + таблица слотов моделей | читать файлы research | вердикт «не покупать / клиент» **проигрывает** Q-2/Q-3 Саши |
| MigrationToVM | прецедент блоков и двух ботов | `MigrationToVM/TZ.md` | целевая модель — cutover, не вечный клон |
| rclone `owncloud:` | текущая шина WorkVault | systemd timer на ВМ | remote = корп. WebDAV; после cutover — новый remote |
| TZ-storage-system | канон где живут ТЗ | vault path | backup VM-only |
| USERTOOLS / MoveFrom* | корп. коннекторы | CLI как сейчас | зависят от Q-3 VPN |
| Tutu llm-gateway | оркестрация + REV | config.yaml provider tutu | после cutover — VPN или потеря |
| Codex Business | архитектор/исполнитель | отдельный CHANGE, не этот слаг | не внедрять из MIGRATION |
| DevWorkflow | машина этого поезда | `pipeline` + `dev/<slug>/` | не патчить ради HomeCutover |
| ErrorBus | сбои CLI | `--tool` после stub | не до ORCH stub |
| Yandex.Disk / rclone yandex (MigrationToVM) | личные заметки **другой** контур | не смешивать с ownCloud-сервером | вне обязательного TO-BE, пока Q-7 не скажет иначе |

---

## Контракты экосистемы

### Источник истины

- Владелец freeze-норм: HomeCutover (этот файл).
- Владелец хода слага: `dev/pereezd-vm-na-domashnyuyu-mashinu-personalnuyu-o/_state.json`.
- Владелец текущих файлов WorkVault на ВМ: диск ВМ + корп. ownCloud как **зеркало**, не личный сервер (сервера ещё нет).
- Выжимка `extract.md` — индекс, не SoT.

### Входные контракты

| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| sasha_q2_owncloud | enum[server] | required | journal sobstvennaya-mashina 2026-10-16 | ровно server; client отвергнут |
| sasha_q3_role | enum[cutover] | required | journal sobstvennaya-mashina 2026-10-16 | ровно cutover; second/none отвергнуты этим слагом |
| users_count | int | required | title слага | 1 |
| vm_rclone_url | str | required | rclone.conf remote owncloud | URL WebDAV корп. инстанса, без пароля в ТЗ |
| sku_ram_gb_min | int | required | этот freeze §5 | 32 |
| sku_disk_gb_min | int | required | этот freeze §5 | 512 |

### Выходные контракты

| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| tz_path | str | pipeline `_state.json`, emit-prompt | абсолютный путь этого файла |
| tz_version | str | pipeline G1 | semver frontmatter |
| new_entity_owncloud_server | bool | ORCH:shared-state, MIG:plan | true |
| min_ram_gb | int | MIG:plan блок закупки | 32 |
| min_disk_gb | int | MIG:plan блок закупки | 512 |
| dual_bot_during_parallel | bool | MIG:plan блок Hermes | true |
| empty_block_list_forbidden | bool | MIG:plan / GATE:done | true |

### Зависимости

- Получает от: [RESEARCH sobstvennaya-mashina, MigrationToVM, TZ-storage-system, живая ВМ]
- Отдаёт: [MIG:plan этого слага, ORCH stub `home_cutover`, будущие блоки GATE:block-accept]

### Breaking changes policy

- Версионирование формата: semver поля `version` frontmatter этого ТЗ (не отдельный schema_version данных — сервера ещё нет).
- При breaking change нормы cutover: bump `version`, новая секция, `TZ:patch`; не молчаливый impl.
- Появление файлов сервера / `.env` / манифеста — не breaking этого ТЗ, а exec блоков.

### Границы («что НЕ трогать»)

- Совпадают с разделом «Что НЕ трогать» выше. Контракт не даёт права писать манифест или гасить ВМ.

---

## Критерии приёмки (AC)

Default класс **S**. Класс **O** — только с `depends: operator:answer:Q-n`. Показ AC ≠ ожидание. Исполнение Q и `GATE:block-accept` ≠ показ.

| ID | Класс | Формулировка | Якорь |
|---|---|---|---|
| AC-001 | S | Freeze фиксирует **cutover** (Q-3=3), не второй вечный клон и не «оставить только ВМ» | §цель, §решения |
| AC-002 | S | ownCloud = **сервер** `[NEW-ENTITY, требует согласования Саши]`; rclone к `owncloud.tutu.ru` норму не закрывает | §NEW-ENTITY, R-OC |
| AC-003 | S | Один пользователь; multi-tenant не входит | title, §TO-BE |
| AC-004 | S | RAM min 32 ГБ, диск min 512 ГБ; M6 16/256 отвергнут; M5 Pro / профиль B отвергнуты | §5, R-16G |
| AC-005 | S | AS-IS ВМ описан без секретов; remote = корп. WebDAV tutu.ru | §AS-IS |
| AC-006 | S | Параллель ВМ+дом только с **двумя** ботами; один токен запрещён | R-TOKEN |
| AC-007 | S | `WorkVault_backup` VM-only обязан быть в блоках **до** гашения ВМ | R-BACKUP |
| AC-008 | S | Корп. коннекторы и Tutu-шлюз после cutover явно завязаны на Q-3 (VPN vs отказ) | R-NET |
| AC-009 | S | Этот `TZ:patch` не ставит сервер, не покупает железо, не гасит ВМ, не пишет манифест/jobs/ядро | §границы |
| AC-010 | S | `MIG:plan` обязан выдать непустой список `MIG:block-k` (B1–B10 по смыслу); `GATE:done` с пустыми блоками при цели переезда запрещён | §cutover |
| AC-011 | S | AC-017/018 DevWorkflow-W4 в этот пакет не входят | R-KANBAN |
| AC-012 | O `depends: operator:answer:Q-1` | Выбран вендор/ОС: Linux 32/512 или Mac M6 32/512 (или «другой» текстом) | Q-1 |
| AC-013 | O `depends: operator:answer:Q-3` | После cutover: VPN+корп. API **или** личный агент без MoveFrom* | Q-3 |
| AC-014 | O `depends: operator:answer:Q-6` | Сеть сервера: оверлей / публичный HTTPS / LAN-only | Q-6 |

Q-2, Q-4, Q-5, Q-7 — **класс S в freeze** (не держат `GATE:done` этого слага сами по себе); `MIG:plan` заводит их в `open_questions`, если ещё открыты. Без Q-1/Q-3/Q-6 план блоков по железу/VPN/портам гадательный — поэтому O.

---

## Открытые вопросы

Оркестратору в origin — **по одному** (R3). Ниже полный набор для роли. Смена ответа = `TZ:patch`, не молчаливый impl.

### Q-1. Какое железо покупаем под 32 ГБ / 512 ГБ?

Контекст: базовая M6 16/256 **отвергнута**. M5 Pro **отвергнут**. Нужен always-on хост под Hermes + ownCloud-сервер + Obsidian, один пользователь, cutover ВМ.

1. Linux mini-PC / NUC / рефурб, 32 ГБ / 512 ГБ (systemd как на ВМ, сервер штатнее, дешевле).
2. Mac mini M6 **32 ГБ / 512 ГБ** (нативный Obsidian; цена выше; launchd + Docker/сервер).
3. Другое (Саша называет модель) — приёмка только если RAM≥32 и диск≥512.

**Рекомендация: 1**, если цель «как можно дешевле» и аналог ВМ+сервер. Вариант 2 — если нативный macOS-Obsidian важнее TCO.

### Q-2. Какой продукт сервера?

Контекст: Саша сказал «ownCloud-сервер». На ВМ живёт **клиент к ownCloud tutu.ru**. Семейство = ownCloud CE **или** Nextcloud. Это всё `[NEW-ENTITY]`.

1. Nextcloud (fork, активнее релиз-цикл; Docker-образ обычен).
2. ownCloud CE — как в названии, ближе к корп. бренду клиента.
3. Другое (Seafile и т.п.) — тогда новый бриф, не «ownCloud».

**Рекомендация: 1** (Nextcloud как реализация нормы «ownCloud-family сервер»). Имя сущности в манифесте можно оставить `owncloud_server` после согласования.

### Q-3. Корп. API после cutover?

Контекст: без сети tutu слепнут MoveFrom*, Exchange, Loop, Confluence, шлюз моделей. Verbatim оркестрацию внешнюю Саша оставляет.

1. Always-on VPN/корп. доступ с домашней машины; стек коннекторов **сохраняем**.
2. Личный агент **без** корп. коннекторов (только Telegram + vault + модели с личного/оставшегося Tutu-ключа, если ключ жив вне сети).
3. Гибрид: модели через VPN/ключ; MoveFrom* остаются на ВМ — **противоречит cutover Q-3=3**, по сути второй инстанс.

**Рекомендация: 1.** Вариант 3 запрещён этим freeze как скрытый откат к «второму инстансу». Вариант 2 — только если Саша явно принимает потерю корп. автоматики.

### Q-4. Telegram на время параллели и после cutover?

1. Новый личный бот с первого домашнего блока; `@sirene_vm_bot` живёт на ВМ до B9; после cutover дом = SoT (ВМ-бот архив).
2. Перенести токен `@sirene_vm_bot` в момент B9 (минута простоя; риск ошибки «забыли стопнуть ВМ»).
3. Один токен на двух хостах сразу — **запрещён** (не вариант).

**Рекомендация: 1.**

### Q-5. Судьба корп. ВМ после cutover?

1. ВМ жива ≥30 дней как откат (gateway disabled, не destroyed).
2. Выключить сразу после B9.
3. Оставить always-on второй Сиренью — **противоречит** Q-3=3; это другой кейс.

**Рекомендация: 1.**

### Q-6. Как публиковать личный ownCloud-сервер?

Контекст: домашний белый IP не гарантирован. Открытый WebDAV без TLS/auth — R-PII.

1. Оверлей (Tailscale/Headscale/VPN): порты не в интернет, ноут и телефон — клиенты оверлея.
2. Публичный HTTPS + DDNS + reverse-proxy + auth.
3. Только LAN; вне дома — не нужен (ломает ноут в кафе).

**Рекомендация: 1.**

### Q-7. Что лежит на личном сервере?

1. WorkVault + личный Obsidian-vault; `_Archives` и `WorkVault_backup` — отдельный офлайн/диск, не обязательно на SSD сервера.
2. Полный клон ВМ включая `_Archives`, `state.db`, кэши агентов.
3. Только личные заметки; WorkVault остаётся на `owncloud.tutu.ru` — **не** независимость.

**Рекомендация: 1.**

---

## Порядок для `MIG:plan` (намёк, не IAC)

1. Снять baseline: `df`, `free`, `jobs.json` enabled, rclone remote URL (без пароля), `systemctl --user`.
2. Закрыть/вписать Q-1/Q-3/Q-6 (O) — без них блоки закупки и сети не писать как «исполняемые».
3. `recipe-add` блоков B1–B10 (смысл §cutover); каждый с `GATE:block-accept`.
4. IAC плана: проверка RAM/диска купленного SKU; наличие **двух** ботов на параллели; сервер отвечает только с auth; ВМ жива до B9; backup path существует.
5. Не impl из плана. Не `set-case`. Не LIGHT.

---

## Границы `TZ:patch` / `TZ:finalize`

Сделано `TZ:patch`: master-файл `TZ/HomeCutover/HomeCutover_TZ.md` v0.1.0 `status: draft`; freeze цели, AS-IS, TO-BE, `[NEW-ENTITY]`, железо, риски, AC-001…014, Q-1..Q-7.

Сделано `TZ:finalize` (2026-10-18): канон того же v0.1.0 (bump нет) + строка `MAIN_TZ_INVENTORY.md` (таблица «План», статус `draft`).

Не сделано (запрещено этим TZ-WRITE): stub манифеста / `entities.json`; extract.md (нет `TZ:compress` в recipe — компрессор не этот ход); `MIG:plan`; закупка; установка; cutover; правки скиллов/YAML/cron/ядра.

---

## Приложения

| Файл | Роль |
|---|---|
| `research/20261016_sobstvennaya-mashina-pod-siren-collect.md` | факты ВМ 16.10 |
| `research/20261016_sobstvennaya-mashina-pod-siren-analyze.md` | вердикт RESEARCH (дефолты **проигрывают** Q-2/Q-3) |
| `MigrationToVM/TZ.md` | прецедент блоков; не SoT этого cutover |
| `TZ/TZ-Workflow/TZ-storage-system.md` | где живут ТЗ; backup VM-only |

## TZ:finalize (2026-10-18)

Каноническая фиксация freeze v0.1.0 + строка инвентаря (Б15 п.6 / Б18.6). Версия **не** bump: ревизии `REV:tz` в recipe MIGRATION нет; текст freeze после `TZ:patch` не менялся.

`status: draft` в frontmatter и инвентаре: открытые Q-1…Q-7 блокируют исполняемые блоки закупки/VPN/портов (`MIG:plan` / `GATE:block-accept`), не этот `TZ:finalize`. Легенда инвентаря: `approved` только при закрытых Q.

`[NEW-ENTITY, требует согласования Саши]` **ownCloud/ownCloud-family сервер** на домашней машине — маркер сохранён дословно; запись в манифест/`entities.json` **не** создавалась (ORCH). rclone-клиент к `owncloud.tutu.ru` норму **не** закрывает.

## Статус

Draft v0.1.0 (2026-10-18), `TZ:finalize` канон + инвентарь. Далее `GATE:take-into-work` → `MIG:plan`.
