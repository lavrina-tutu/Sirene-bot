Source example: only send a live smoke when authorized. ok:true alone does not establish the actual destination thread; verify the delivered message.

## Проверка ПЕРЕД интеграцией (не верь выбору архитектора/self-report)

```bash
curl -s https://api.telegram.org/bot<TOKEN>/getMe          # кто бот (username)
curl -s -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -d 'chat_id=-1004300127777' -d 'message_thread_id=11112' -d 'text=smoke'
# ok:true  → этот бот реально доставляет в топик — можно использовать
# chat not found → НЕ тот бот (не состоит в группе)
```

`getMe` недостаточен (бот с токеном существует, но может не состоять в группе).
Единственное надёжное подтверждение — `ok:true` в ответе sendMessage в конкретный топик.
Исполнитель обязан прогнать live-smoke до сдачи; координатор — проверить реальную
доставку, а не верить финальному отчёту.


## Два канала доставки: различай

- **Штатный `deliver` крона** (`telegram:-1004300127777:<thread>`) — для бизнес-потока инструмента.
  У `no_agent`-скриптов реальный адрес = только поле `deliver` в jobs.json (не docstring/комментарий).
- **Прямой HTTP из скрипта/шины** — когда нужно писать в топик мимо `deliver` (напр. ошибки → Errors,
  т.к. на успехе крона stderr стирается scheduler'ом). Использует `TELEGRAM_BOT_TOKEN`.

