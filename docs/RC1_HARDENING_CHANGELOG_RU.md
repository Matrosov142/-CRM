# ПОТОК CRM — RC1 hardening iteration

## Технический preflight 2026-11-09

- Исправлен release workflow: `set -o pipefail` гарантирует, что ошибка `tools/qa_release.py` не будет скрыта успешным завершением `tee`.
- Добавлена контрактная проверка наличия `pipefail` в backend evidence step.
- npm lockfile не создавался: `npm` отсутствует; доступный `pnpm` не создаёт lockfile, совместимый с `npm ci`.
- Backend тесты, compileall, YAML/shell checks, PostgreSQL/RLS, npm ci/build и Docker smoke не запускались из-за отсутствия нужных инструментов. Это не результаты PASS.
- QA report, release plan, runbook и manifest обновлены только фактически выполненными результатами.

База: Pilot `0.25.0`.

## Изменения

1. Добавлен PostgreSQL RLS coverage test для всех таблиц с `company_id`: обязательны `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, политики и tenant-context. `auth_sessions` исключена явно, поскольку проверяется до установки tenant context и защищается комбинацией JWT subject + company + JTI.
2. Release workflow теперь дважды выполняет `alembic upgrade head` на чистой PostgreSQL 16.
3. Docker gate проверяет не только сборку: он запускает полный Compose stack, проверяет API readiness через nginx и web health endpoint, затем удаляет тестовые контейнеры и тома.
4. Обновлён contract test самого release workflow.
5. Синхронизированы QA report и release manifest.

## Локальные проверки

- 202 теста PASS / 54 тестовых файла.
- 141 Python-файл: `compileall` PASS.
- Статический release audit: PASS.
- YAML workflow и Compose: parse PASS.
- `bash -n` для трёх shell-скриптов: PASS.

## Не выполнено в локальной среде

- PostgreSQL 16 runtime и RLS integration matrix.
- Frontend `npm ci` и production build: `package-lock.json` отсутствует, npm registry недоступен.
- Docker Compose runtime: Docker daemon недоступен.

**Статус: NO-GO.** Этот пакет усиливает проверяемость релиза, но не является RC1 и не подтверждает production readiness.


## Дополнительная итерация hardening

- В CI добавлены `pip-audit` и `npm audit --audit-level=high`; обнаруженные критические/высокие уязвимости блокируют gate.
- Лог backend QA и JSON-отчёт сохраняются как CI artifact даже при падении job.
- В Docker build contexts исключены `.env*`, локальные backup-файлы, `.git`, `node_modules`, `dist` и тестовые артефакты.
- Исправлен `.gitignore`: ранее часть новых шаблонов была записана как буквальные `\\n`-последовательности, а не отдельные правила.
- Исправлен путь архивации документов в `ops/backup-pilot.sh`; Docker API image явно устанавливает `tar`.
- В Docker smoke CI добавлен реальный backup/restore drill: создание тестового документа, резервная копия БД и файлов, проверка SHA-256, восстановление БД в отдельную тестовую БД и восстановление файлового sentinel.
- Restore gate проверяет точную Alembic revision `0031_rfq_tender_position_link` и наличие таблиц после восстановления.
- Проверки локально: 207 PASS в 55 тестовых файлах; 142 Python-файла compileall PASS; static audit PASS; YAML parse PASS; shell syntax PASS.

Ограничение: эти проверки backup/restore, PostgreSQL, npm audit/build и Docker являются добавленными CI-процедурами. Они не считаются выполненными, пока workflow реально не завершился успешно на GitHub Actions.


## Критическое усиление модели PostgreSQL ролей

- Устранено использование `potok_owner` как первоначального PostgreSQL superuser в новых пилотных установках.
- Введены три роли: `potok_admin` (администрирование/выдача прав), `potok_owner` (Alembic и владение схемой, без SUPERUSER/BYPASSRLS), `potok_runtime` (FastAPI, без владения таблицами и без SUPERUSER/BYPASSRLS).
- Отдельный `db-bootstrap` создаёт роли и default privileges через admin; отдельный `db-migrate` выполняет миграции от non-superuser владельца схемы.
- Для старых пилотных volumes добавлен переходный путь: прежний superuser `potok_owner` создаёт отдельного `potok_admin`, после чего сам понижается до non-superuser. Volume и данные не удаляются.
- CI теперь создаёт non-superuser owner/runtime до Alembic и проверяет после запуска Compose, что обе роли не имеют SUPERUSER/BYPASSRLS, а таблицы принадлежат `potok_owner`.
- Генератор секретов создаёт отдельный DB admin password и добавляет его в старый `.env.pilot` без вывода значений.


Локальная проверка после разделения PostgreSQL ролей: 209 PASS в 55 тестовых файлах; 142 Python-файла compileall PASS; static audit PASS. PostgreSQL runtime всё ещё не запускался локально.

- Одноразовое создание первого директора переведено на `potok_admin`: таблицы `companies`, `memberships` и `audit_events` имеют FORCE RLS, поэтому bootstrap не должен пытаться вставлять первые записи через runtime или обычного schema owner без tenant context.


## Изоляция привилегированных задач от API

- `db-bootstrap` — отдельный одноразовый Compose-сервис, которому доступен только на время старта пароль `potok_admin`; он создаёт/обновляет роли и завершает работу.
- `db-migrate` — отдельный одноразовый сервис для Alembic от имени `potok_owner` и выдачи прав runtime-роли.
- Постоянный `api` получает только runtime `DATABASE_URL` и JWT secret; он не получает DB admin password, schema-owner password или migration URL.
- После успешного старта `pilot-up.sh` удаляет завершившиеся bootstrap/migration containers, чтобы их environment не оставался в Docker metadata.
- Создание первого директора запускается отдельным одноразовым `db-bootstrap` контейнером с временной передачей DB admin password; секрет не передаётся работающему API.
- CI дополнительно проверяет отсутствие DB admin/owner credentials в environment API-контейнера.

- Финальная компоновка разделяет три коротких/долгих процесса: `db-bootstrap` (admin), `db-migrate` (owner) и `api` (runtime only). API контейнер больше не получает ни admin, ни schema-owner credentials.

Итог локального offline QA после разделения контейнеров: 212 PASS / 55 файлов, 142 Python-файла compileall PASS, release audit PASS, YAML и все workflow shell-блоки проходят синтаксическую проверку.


## Финальный локальный preflight этой итерации

- 212 тестов PASS в 55 выбранных файлах; два PostgreSQL integration test-файла пропущены из-за отсутствия локального PostgreSQL/psycopg.
- 142 Python-файла compileall PASS; статический release audit PASS.
- Compose YAML разобран; все shell-блоки CI workflow и скрипты прошли `bash -n`.
- `pilot-up.sh` smoke-tested с подменёнными Docker/OpenSSL командами: создаёт четыре отдельных значения `.env.pilot`, файл имеет права `0600`.
- Docker runtime, PostgreSQL RLS, npm production build, dependency audits и backup/restore в этой среде не исполнялись. Требуется реальный GitHub Actions run.
- Статус релиза остаётся **NO-GO**.

Итоговый локальный QA после выноса bootstrap/migration в отдельные одноразовые сервисы: 212 PASS / 55 файлов. API контейнер получает только runtime DB URL; завершившиеся контейнеры с административными/owner credentials удаляются launcher-скриптом и CI.
