# ПОТОК CRM Pilot v0.10

## Изменения
- Усилен PostgreSQL RLS integration test: проверяется изоляция двух компаний, членств и аудита, запрет записи в чужую компанию и отсутствие UPDATE/DELETE прав у runtime-роли на audit_events.
- Исправлен релизный QA runner: чистые unit-тесты, которые импортируют SQLAlchemy-модели, запускаются с временным SQLite URL и не исключаются только из-за отсутствия PostgreSQL DBAPI-драйвера.
- PostgreSQL integration test остаётся отдельным условным этапом и запускается только с двумя явно заданными disposable test базами и установленным psycopg.
- Синхронизированы версия API, frontend и release QA: 0.9.0-pilot.
- Исправлена JSX-синтаксическая ошибка в интерфейсе истории расчётов доставки; глобальный TypeScript compiler больше не выдаёт синтаксических TS1005 ошибок. Полная проверка типов и сборка Vite не выполнены из-за отсутствующих React/Vite зависимостей.

## Границы проверки
- SQLite используется только для импорта приложения и выполнения unit-тестов; это не проверка PostgreSQL-схемы, миграций или RLS.
- PostgreSQL integration tests не считаются пройденными, если тестовая инфраструктура недоступна.
- Production readiness остаётся false до успешных PostgreSQL, frontend build, deployment, backup/restore и security acceptance tests.

## Дополнение: защищённая браузерная сессия
- Добавлены `/api/v1/auth/session/login`, `/session/register-company` и `/session/logout`.
- Браузер получает access JWT только в cookie `HttpOnly; SameSite=Strict`; в production cookie помечается `Secure`.
- Отдельная CSRF-cookie доступна браузерному коду; изменяющие запросы должны передавать её значение в `X-CSRF-Token`.
- Для cookie-аутентификации сервер сравнивает CSRF cookie/header в постоянное по времени сравнение и проверяет Origin по allowlist.
- Старые Bearer endpoints сохранены для интеграционных API-клиентов; новый интерфейс использует cookie-сессию и `credentials: include`.
- Выход удаляет обе cookies. Рекомендуется размещать интерфейс и API на одном origin; production CORS/HTTPS должны быть настроены до пилота.
- Проверки: unit tests cookie attributes и отказа при CSRF/неразрешённом Origin. Полные browser/E2E и penetration tests не выполнялись.

## Версия 0.10 — браузерная авторизация
- Браузерный вход и регистрация переведены на HttpOnly cookie-сессию.
- Для cookie-аутентификации добавлены CSRF double-submit и проверка Origin.
- Logout удаляет cookie сессии и CSRF.
- Legacy Bearer endpoints оставлены для внешних API-клиентов.
- Добавлены тесты атрибутов cookie, CSRF и Origin.
- Проверено: 137 тестов, 1 PostgreSQL-only тест пропущен; статический аудит пройден.
- Production build frontend, PostgreSQL integration и Docker runtime по-прежнему не выполнены из-за отсутствия зависимостей/сервисов в среде.
