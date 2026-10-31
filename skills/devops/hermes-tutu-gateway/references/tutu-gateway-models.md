# Tutu LLM Gateway — Verification Scripts

## Базовый тест модели
```bash
curl -s -X POST https://llm-gateway.tutu.ru/api/openrouter/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <API_KEY>" \
  -d '{"model":"<MODEL_ID>","messages":[{"role":"user","content":"say hi"}],"max_tokens":10}'
```

## Tool calling тест
```bash
curl -s -X POST https://llm-gateway.tutu.ru/api/openrouter/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <API_KEY>" \
  -d '{
    "model": "<MODEL_ID>",
    "messages": [{"role": "user", "content": "What is the weather in Moscow?"}],
    "tools": [{"type":"function","function":{"name":"get_weather","description":"Get weather","parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}}],
    "max_tokens": 100
  }'
```
Признак успеха: `tool_calls` массив в `choices[0].message`.

## Extended thinking тест (DeepSeek)
```bash
curl -s -X POST https://llm-gateway.tutu.ru/api/openrouter/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <API_KEY>" \
  -d '{"model":"deepseek/deepseek-v4-pro","messages":[{"role":"user","content":"2+2"}],"max_tokens":50,"reasoning":{"enabled":true,"max_tokens":100}}'
```
Признак успеха: `reasoning` поле в `choices[0].message`.
