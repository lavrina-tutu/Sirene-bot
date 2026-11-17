# Группа 1 — экспорт

Исправлен getTimephasedWork(List<LocalDateTimeRange>, TimeUnit.HOURS), сохранены отдельные raw planned/actual/remaining (regular/overtime). Календарная основа лага — ProjectProperties.getRelationshipLagCalendar. Рабочие периоды getWorkSplits сохранены; наличие одного периода не доказывает split-потерю (дальнейшее представление — группа 2).

Закреплённая MPXJ 16.4.0 получила observation overlay ConstraintFactory: тот же проход чтения фиксирует metadata count, позиции, причины отбрасывания, UID и raw bytes. graph-invalid: self 1→1 и dangling 99999→5 наблюдаемы; partial остаётся блокирующим. Отсутствие audit/несовпадение видимых UID не подтверждает полноту. Стоковый JAR неизменен. Минимально расширена prepared-plan.schema.json для metadata полноты и явной основы timephased-проекции; старые prepared документы совместимы.

Команда R: PYTHONPATH=/home/tkachenkoav/.local/lib/python3.9/site-packages /usr/bin/python3.9 -m pytest tests -q -o cache_dir=T/cache/pytest-r --basetemp=T/r-tmp-3 --junitxml=T/reports/r-group1-final2.xml. rc=0: 81 passed, 1 необязательный legacy ZD skip §19. Первоначальный отказ схемы и промежуточный прогон сохранены. Две сборки overlay дали одинаковый SHA-256 6d77ac02ba9de195e26e54045369c983cb94940abafcb3afb5541f100cbd0e38. Восстановление before + changes.patch + binary after проверено, все hashes совпали.

Gate экспортных исправлений: passed. Финальная приёмка §20 failed, представление не подтверждено. Unsupported reader format без audit остаётся fail-closed. MofsIndex, production, Gateway и расписания не менялись.
