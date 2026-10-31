---
name: hermes-docker-pitfalls
description: "Docker Compose healthcheck lag fix for Hermes services."
version: 0.1.0
author: agent
platforms: [linux]
---

# Hermes Docker Pitfalls

## Dependency Healthcheck Lag

**Symptom:** `docker compose up -d` не создаёт зависимые сервисы. `docker compose ps` показывает `dependency failed to start: container <name> is unhealthy`, хотя сервис **реально работает** (curl возвращает 200 OK, в логах `Ready`).

**Root cause:** Healthcheck в compose.yml срабатывает ДО загрузки моделей/данных сервисом (скачивание ~40-60с). Docker помечает `unhealthy`, `depends_on` блокирует создание зависимых сервисов.

**Fix:** `docker compose up -d <service> --no-deps` — принудительно создать без ожидания healthy. Сервис уже работает, Docker просто не успел это засчитать.

**Диагностика:**
1. `curl http://localhost:<port>/health` → 200 OK = сервис жив
2. `docker compose logs <service>` → `Ready` в логах = сервис готов
3. Только после подтверждения → `--no-deps`

**НЕ делать:** НЕ удалять/пересобирать контейнеры без проверки — потеря времени на повторное скачивание моделей.
