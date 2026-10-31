# Exchange Org Lookup — исследование bk-098

EWS `ResolveNames(ActiveDirectory)` возвращает `display_name`, `job_title`, `department`, `manager` (строка с display_name руководителя); Telegram-хендлы находятся в `phone_numbers`.

Рекомендация: TG-команда «кто руководитель у X?» вызывает EWS, затем обновляет `tutu-contacts.md` и AnywhereContacts. Оценка реализации: 4–6 часов Opus. Источник исследования: `~/WorkVault/Hermes-Backlog/research/bk-098-exchange-org-lookup.md`.
