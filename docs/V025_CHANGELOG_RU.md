# ПОТОК CRM Pilot v0.25 — журнал изменений

## Цель релиза

Maintenance-релиз для устранения рассинхронизации версий и недостоверных сведений в release manifest. Функциональные возможности v0.24 сохранены. Схема БД не меняется, новая миграция не требуется.

## Изменения

- Версия FastAPI, frontend package, UI banner, release audit и QA runner синхронизированы на `0.25.0-pilot` / `0.25.0`.
- Исправлена устаревшая подпись в dashboard footer.
- README приведён к текущему релизу; исторические заметки предыдущих версий сохранены.
- QA runner формирует отдельный `QA_REPORT_PILOT_0_25.json`.
- Добавлен тест целостности release manifest: версия, отчёт QA, количество тестов, файлов Python и миграций сверяются с фактическими артефактами.

## Проверки и ограничения

- Локальный QA запускается штатным `python tools/qa_release.py`.
- PostgreSQL/RLS integration запускается только при наличии `psycopg` и отдельных disposable TEST_ADMIN_DATABASE_URL / TEST_RUNTIME_DATABASE_URL.
- npm lockfile и production build не получены: npm registry недоступен в среде сборки.
- Docker runtime, browser E2E, backup/restore и penetration testing не выполнены.
- `production_ready=false`.
