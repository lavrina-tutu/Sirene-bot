---
type: appendix
title: "Consolidated ТЗ каркас — импорт контакта из Exchange/GAL в contacts.enc (upsert_from_source)"
date: 2026-09-07
source: TZ:architect (session a4d43cb0), TZ:analyze (session a4d43cb0), TZ:compress (session 4f237f64)
status: draft-saved (архив теневой ветки exchange-contact-upsert)
related: AnywhereContacts_TZ.md, ExchangeOrgLookup_TZ.md
---

# Appendix — каркас ТЗ v0.3.0 (спасён из тенивой ветки, зафиксирован на диск)

Этот appendix фиксирует консолидированный каркас ТЗ, который архитектор (cursor-grok-4.6-high) собрал до остановки теневой ветки `DEV/exchange-contact-upsert`. Файл создан чтобы не потерять работу; поштучная доработка и верификация — впереди (см. основные мастер-ТЗ).

## Суть (рекомендованный вариант архитектора: срез A)
Новый инструмент НЕ нужен. Доработка двух существующих:
1. **AnywhereContacts** — честный `upsert_from_source()` (upsert контакта по source).
2. **ExchangeOrgLookup** — переписать `md_writer`/`cmd_add` на честный upsert + `--dry-run` + VPN exit 2.

## Факты на диске (найдены архитектором)
- `store.py`: уже лежит **невалидный черновик** `upsert_from_source` — заменить целиком.
- `md_writer.py:217-221`: `KeyError pass` ломает создание [контакта] — починить.

## План работ (по фазам, поштучные, с верификацией)
1. **AnywhereContacts:** реализовать `upsert_from_source()` (честный upsert по source), тесты.
2. **ExchangeOrgLookup:** переписать `md_writer`/`cmd_add` на честный upsert с `--dry-run`; VPN exit 2; тесты.

## Статус
- Каркас ТЗ v0.3.0 собран (открытых вопросов нет).
- Мастер-файлы инструментов не модифицированы (v0.2.1 / 0.2.1).
- Продолжение — после настройки процесса разработки (ProcessImprovement), по нормальной цепочке с верификацией Саши.