# ПОТОК CRM Pilot v0.11

## Изменения безопасности браузерной сессии
- Browser login и регистрация требуют заголовок Origin из allowlist.
- Logout и изменяющие cookie-authenticated запросы требуют CSRF double-submit и разрешённый Origin; отсутствующий Origin отклоняется.
- Login/register ответы помечаются Cache-Control: no-store и Pragma: no-cache.
- Frontend при загрузке пытается восстановить состояние по HttpOnly cookie; access JWT не сохраняется в Web Storage.
- Добавлены unit-тесты на отсутствующий/чужой Origin и allowlist.

## Контроль качества v0.11
- 140 тестов пройдены в 39 файлах; PostgreSQL-only тест исключён из-за отсутствия psycopg и disposable test DB.
- 115 Python-файлов прошли compileall и статический аудит.
- 24 миграции: один корень, без ветвлений.
- Повторный запуск QA после синхронизации версии интерфейса прошёл.

## Ограничения
- Session rotation/revocation на уровне серверного хранилища ещё не реализованы.
- Не выполнены E2E/browser и penetration tests.
- PostgreSQL RLS integration не запускалась без отдельной disposable test DB.
- npm lockfile/production build не получены: npm registry не ответил в доступное время.
- Docker runtime не запускался.
- Production readiness: false.
