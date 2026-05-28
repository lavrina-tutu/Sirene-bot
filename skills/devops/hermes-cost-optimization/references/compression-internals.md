# Hermes Compression Internals (исследование Opus, май 2026)

## Где живёт логика (run_agent.py)

- **`_check_compression_model_feasibility()`** (строки ~3176–3344) — вызывается при старте каждой сессии
  - Считывает `aux_context = get_model_context_length(compression_model)`
  - Берёт `threshold = context_compressor.threshold_tokens`
  - Если `aux_context < threshold` → **жёстко затирает** `threshold_tokens = aux_context` и пересчитывает `threshold_percent`
  - Выводит предупреждение «Auto-lowered this session's threshold to N tokens»

- **`agent/context_compressor.py`**
  - `__init__` (строки ~404–460): `threshold_tokens = max(context_length × threshold_percent, MINIMUM_CONTEXT_LENGTH=64_000)`
  - `update_model()` (строки ~376–402): при смене модели **сохраняет тот же `threshold_percent`**, пересчитывает `threshold_tokens` от нового context_length
  - `should_compress()` (строки ~493–513): сравнивает текущие токены с `threshold_tokens`

## Инициализация порога (run_agent.py строки ~2104–2117)

```python
compression_threshold = float(_compression_cfg.get("threshold", 0.50))
try:
    from agent.auxiliary_client import _compression_threshold_for_model as _cthresh_fn
    _model_cthresh = _cthresh_fn(self.model)  # hardcoded per-model override
    if _model_cthresh is not None:
        compression_threshold = _model_cthresh
except Exception:
    pass
```

## Per-model override (`agent/auxiliary_client.py` строки ~227–239)

Функция `_compression_threshold_for_model()` — единственный встроенный per-model override, захардкожен:
- Сейчас содержит только: `arcee/trinity-large-thinking → 0.75`
- Расширить можно только правкой исходника (сотрётся при обновлении Hermes)

## Контексты моделей (model_metadata.py)

- `claude-haiku-4-5`: 200,000 токенов
- `claude-sonnet-4-6`: 1,000,000 токенов  
- `claude-opus-4-7`: 1,000,000 токенов

## Почему Haiku вызывает предупреждение

Sonnet (1M) × threshold 0.5 = 500,000 > 200,000 (Haiku) → Auto-lowered

## Поведение при смене модели

После Auto-lowered `threshold_percent ≈ 0.20`. При `switch_model()` на Opus (1M):
- Opus 1M × 0.20 = 200K — тот же порог
- Это корректно: Opus тоже использует Haiku для сжатия, который не примет >200K

## MINIMUM_CONTEXT_LENGTH = 64_000

Если Haiku используется как main model (200K × 0.17 ≈ 34K < 64K) → floor срабатывает, компрессия начнётся при 64K токенах.

## Вывод

Per-model compression thresholds через config.yaml **невозможны**. Единственные варианты:
1. Глобальный threshold под наименьший aux model context
2. Использовать aux compression model с достаточным контекстом
3. Правка исходника `_compression_threshold_for_model()`
