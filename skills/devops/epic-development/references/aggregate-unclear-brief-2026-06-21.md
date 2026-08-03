# Итоги брифа unclear-реестра AggregateFromMeetings (21.06.2026)

Бриф проведён по 294 unclear-записям из `_sandbox/unclear_queue.md`.
Живой документ: `~/WorkVault/Tools/AggregateFromMeetings/briefs/brief_people_v1.md`

## Люди — маршруты 1-1

| Имя в встречах | Login | ФИО |
|---------------|-------|-----|
| Кирилл, Кирилл 1-1, Daily Кирилл | kkrivorotov | Криворотов Кирилл |
| Илья, Илья 1-1 | isereda | Середа Илья |
| Олег, Олег 1-1 | opopkov | Попков Олег (до мая 2026 → isereda) |
| Даяна | dnabiev | Набиева Даяна |
| Саша Саша 1-1, PR Ткаченко, 1-1 Ткаченко | aralov | Аралов Александр |
| Саша (в 1-1 с подчинёнными) | aralov | Аралов Александр |

## Оргструктура АИД

```
aralov (Аралов Александр) — руководитель
├── tkachenkoav → kkrivorotov
├── isereda → (opopkov до мая 2026)
├── azhirov
├── dnabiev  ← BI/Metabase
├── yalekseeva
├── eperetjatkova
└── okotelnikova
```

## Новые проекты — созданные карточки

| Slug | Название | Алиасы |
|------|---------|--------|
| `chatbot` | Чат-бот АИД | Чат-бот, Бот с ИИ, RAG confluence |
| `alpha` | Альфа | Альфа, alpha |
| `ab-platform` | АБ-платформа | АБ тесты, Улучшение АБ, UserWay |
| `vestnik-aid` | Вестник АИД | Вестник, Вестник аналитики |
| `devrel` | DEVREL АИД | DEVREL, подкаст АИД |

## Существующие проекты — добавлены алиасы

| Slug | Новые алиасы |
|------|-------------|
| `trisigma` | Trisigma, tisigma, 3sigma |
| `ml-platforma` | ML-платформа, MLOps, Neoflex, Alpha NeoFlex |
| `parsery` | Парсинг конкурентов, Парсинг-К, Парсинг-Отели/Авиа/Автобусы |
| `metroteka` | Метротека, Реестр отчетов, KPI-навигатор |
| `antibot` | Антибот |
| `cu` | ЦУ-ТУТУ, Центральный Университет |
| `ai-transformaciya` | AI-ready, AI-трансформация, AI-зация, AI-РП, Персонализация |

## Правила маршрутизации без slug

Встречи по ИБ, Авиа, Каскаду коммуникаций, Миграции — **не отдельные проекты**.
Маршрутизировать по контексту summary в существующий проект.

## Технические решения

- `reports_to` добавлено в схему AC v2 (schema.py, merger.py) — Opus
- `project_roles` спроектировано для AC — Opus (job 1bc77a814a51)
- TZ_B и TZ_E обновлены: резолв через иерархию AC.reports_to
- EWS: пароль в `~/.config/hermes/.env` как `TUTU_DOMAIN_PASSWORD`, exchangelib+NTLM работает без VPN
