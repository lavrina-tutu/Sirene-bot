# Независимый R-probe: возобновление после квоты без внешнего producer'а

Закрывает R-звено, когда внешнего источника сигнала доступности нет и Саша явно
разрешает сделать независимый опрос провайдера. Применять строго по полномочию — это
новое poll/scheduler, который канон по умолчанию запрещает.

## Схема (script-only, no_agent, без daemon/sleep/log-observer/core-hook)

- **Артефакты**: один script `devworkflow_b55_r_probe.py` в `<active-home>/scripts/`,
  nonsecret binding JSON, scoped incident/lock/events/resource ownership в cache, тест
  `test_b55_r_probe.py`. Native cron (`every 1h` / `once` с `repeat=1`); нового scheduler
  не требуется.
- **Raise-on-demand**: действующий обработчик фактического отказа захватывает исходный
  error/wait/scope, штатно WAIT, затем bounded arm с SHA улики. Один job/ресурс, idempotent
  duplicate/partial-success reconciliation. Вне инцидента R-job отсутствует. Не ставить крон
  заранее «на всякий случай» при healthy.
- **Actual probe**: минимальный inference POST тому же effective endpoint/provider/model/
  account_ref/limit; tools НЕ исполняются, output budget ≤32, total deadline 30s, SDK
  retries/fallback/auth redirects отключены. НЕ HEAD/health/истечение времени. Успех —
  валидный inference response без error envelope; scope mismatch/timeout не restored.

## Сценарий (a) — период неизвестен

`every 1h`, первый probe примерно через час, без immediate/catch-up серии. Один фактический
inference attempt на due. Failure → тихо в monitoring + пустой stdout/WAIT; success → тихо
в monitoring + evidence-backed native R; probes прекращаются; pending delivery не новый
inference. После приёма/проверки stop снимает owned job.

## Сценарий (b) — период известен в сообщении

`kind=once` по ISO UTC `retry_at+60s`, repeat=1. Прямой запрос с user content «Привет! Тут?»,
затем человеческое native касание процедуры с фактическим исходом и evidence ref.
И failure, и success тихо в monitoring; отрицательный ответ сохраняет WAIT. Нет hourly
fallback/автоперевзвода старого отказа.

## Таймбары (что реально отдаёт провайдер — определить режим a/b)

| Провайдер | retry-период в | Вывод для R |
|---|---|---|
| OpenAI/Codex | `Retry-After` header + текст «Please try again in <N>s/ms» | парсится → сценарий b; иначе exp backoff |
| DashScope/Alibaba (наш `deepseek` через tutu) | период в тексте НЕ даёт («a few minutes», «try again later», «request rate increased too quickly»); `Retry-After` не документирован; `X-DashScope-Wait-Timeout` — окно burst-ожидания, не срок | → сценарий **a** (~часовой опрос) |

Парсер: структурный retry_after; фактический Retry-After delta/date; однозначный scoped
reset_at; числовой текст ms/s/min/h; decimals. Относительные интервалы — от received_at,
абсолютные — с timezone; при нескольких достоверных границах — max. «later/few minutes»
и X-DashScope-Wait-Timeout не считаются точным сроком.

## Мониторинг без звука

Мониторинг — output в существующий Telegram-канал, НЕ bridge к процедуре. Оба исхода и
служебная ошибка — тихо (`disable_notification=true` через sendMessage), один bounded send.
Native cron не даёт per-job silent (берёт глобальный `cron.delivery.notify`), поэтому не
мутить чужие jobs ради тишины. Native global cron mute не используется; `config.yaml` без
diff. Если actual chat/thread/env ссылки неизвестны и credential/scope не проверены —
readiness FAIL, не новый credential store.

## Адресный вход в процедуру

Script stdout → native cron `local:<actual persisted id>` → existing messaging owner/committed
route → actual incoming turn текущего receiver/load. Admission/readback/одинаковые skills НЕ
dоказывают turn процедуры (LOCAL/detached cron может быть только note) — нужны исходный
receive и действие. В сценарии a failed stdout пуст; в b human-касание один раз и НЕ
разрешает resume по отрицательному ответу. Human provenance не подделывать.

**Откуда actual persisted id:** читать из `~/.hermes/sessions/sessions.json` (LEGACY MIRROR
роутинг-индекса; primary — `gateway_routing` в `~/.hermes/shared-state.db`) по ключу
`agent:main:telegram:group:<chat_id>:<thread_id>` → поле `session_id`. Совпадение с текущей
сессией поезда → адресный receiver существует, `local:<id>` допускаем; это read-only lookup,
НЕ создание сущности. session_key Telegram и выдуманные id не подставлять.

## Ограничения, которые нельзя объявлять закрытыми без фактов

- Один успешный probe ≠ достаточно TPM/квоты для большой роли: применяется только к
  проверенному исходному scope; при повторном отказе — снова WAIT, без серии role-invokes.
- Tutu/DeepSeek config не доказывает доступность Codex/Cursor backend — для чужого backend
  этот probe R не закрывает.
- `no_agent=true` даёт 0 LLM-токенов ВНУТРИ cron, но R-probe всё равно расходует provider
  tokens на direct inference, а содержательные role-invokes — ещё слой. Не выдавать R за
  бесплатный.
- **ARM_UNAVAILABLE**: если провайдер глушит саму процедуру ДО arm, независимый крон не
  поднять (остановленный контекст не исполняет tool). Держать FAIL до существующего
  исполняемого error-handler→arm; не выдавать заранее установленный крон за решение.
