# ПОТОК CRM — RC1 hardening iteration

## CI regression fixes 2026-11-09

- Сокращены Alembic revision IDs, превышавшие PostgreSQL `alembic_version.version_num` в 32 символа; локальная подготовка истории миграций синхронизирована.
- Исправлен составной unique key `tender_positions`, необходимый до создания pricing foreign key; добавлена совместимость для БД, уже дошедших до revision 0029.
- Добавлена revision `0032_processing_quality_rls` для ENABLE/FORCE RLS и tenant policy на production/finished-goods таблицах.
- `pytest` ограничен версией `>=9.0.3`, закрывающей уязвимость, найденную `pip-audit` в CI.
- CI теперь создаёт отдельную роль `potok_owner` и применяет миграции от неё. Тест не удаляет append-only audit rows.
- GitHub Actions подтвердил: аудит зависимостей, миграции до head, повторный upgrade, compileall и static audit прошли. Полная PostgreSQL/RLS матрица ещё падала на незащищённых таблицах; исправление отправлено, ждём повторный CI.
- Frontend CI пока блокируется отсутствующим `frontend/package-lock.json`; npm build и Docker smoke не проходили.

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

## Текущий GitHub Actions прогон PR #1

- На последнем завершившемся прогоне миграции (включая повторный upgrade), `compileall`, static audit и dependency audit прошли.
- Исправлена избыточная проверка RLS-матрицы: таблица `memberships` требует включённый RLS и политики, но не `FORCE`, поскольку привилегированная SECURITY DEFINER проверка директора должна обходить RLS этой таблицы. Остальные tenant-таблицы по-прежнему требуют `ENABLE` и `FORCE`.
- Frontend gate остановился до `npm ci`: в репозитории отсутствует committed `frontend/package-lock.json`. Production build и зависимый Docker smoke/backup-restore drill этим прогоном не запускались.
- Исправление матрицы отправлено в PR; результат следующего GitHub Actions прогона ещё ожидается. Никакие пропущенные проверки не считаются успешными.

## Обновление по GitHub Actions commit 2035a78

- PostgreSQL 16 backend job: PASS, включая Alembic upgrade дважды, release QA, RLS matrix и Python dependency audit.
- Временно созданный npm lockfile candidate успешно прошёл `npm ci`, `npm audit --audit-level=high` и `npm run build` после обновления Vite до 6.4.5 (fix указан самим npm audit для уязвимой версии Vite/esbuild).
- Проверка committed `frontend/package-lock.json` ожидаемо FAIL: candidate существует только как CI artifact, в ветку он ещё не добавлен.
- Docker-образы собираются с candidate lockfile, но `db-migrate` завершился с exit 1; health, role-separation и backup/restore drill пока не запускались. В следующий Docker smoke добавлен вывод статуса и логов Compose при ошибке запуска.
- Релиз остаётся **NO-GO** до committed lockfile, диагностики/исправления db-migrate и успешного повторного полного smoke/restore.

## Docker Compose дефект, подтверждённый логами GitHub

- Повторный release gate с временным lockfile прошёл frontend install/audit/build, но Compose `db-migrate` падал при импорте `app.config.Settings`: отсутствовали обязательные `DATABASE_URL` и `JWT_SECRET`.
- Исправлено в `compose.pilot.yml`: миграционный контейнер получает owner `DATABASE_URL` и JWT secret только на время миграции; API credentials остаются runtime-only.
- Ошибка исправлена в рабочей ветке после последнего завершённого CI run; миграции Compose и следующий backup/restore drill ожидают повторного GitHub Actions.
- Полный релизный статус по-прежнему **NO-GO**.

## Docker host ingress issue, GitHub Actions commit cc308c3

- Compose images built, one-time bootstrap and Alembic migration completed successfully, and the API healthcheck became healthy.
- The host-side smoke could not connect to `127.0.0.1:18080`; `docker compose ps` showed no published host port for `web`, despite the declared loopback mapping. The role and backup/restore steps were consequently skipped.
- Fixed the network topology in the working branch: API/DB stay on the internal `backend` network; `web` now also joins a separate `ingress` bridge while retaining the loopback-only host mapping. Added a deployment contract assertion.
- This network change still requires a new GitHub Actions run; host ingress and backup/restore are not yet marked PASS.

## Backup drill invocation issue, GitHub Actions commit f95f478

- Compose build/startup, Alembic migrations, host-side API/web health, and PostgreSQL role-separation checks passed.
- Backup/restore stopped before creating the archive: `ops/backup-pilot.sh` is tracked as mode `100644`, while CI invoked it as an executable and got `Permission denied`.
- Updated CI to invoke the script explicitly with `bash`, matching the runbook. Archive checksums, PostgreSQL restore, and document restore remain unverified until the next run.
- `frontend/package-lock.json` is still missing from the branch; the temporary candidate did pass frontend install/audit/build.

## Полный runtime и backup/restore gate — commit 212aadf

- Backend/PostgreSQL 16 job прошёл: Alembic migration head применяется дважды, release QA/RLS matrix и Python dependency audit успешны.
- Frontend candidate на GitHub runner прошёл `npm ci`, `npm audit --audit-level=high` и production build. Отдельный job намеренно обнаруживает отсутствие committed `frontend/package-lock.json` и поэтому оставляет release workflow красным.
- Compose smoke прошёл: образы собраны, bootstrap/migration завершились, API и web отвечали через loopback host port, роли `potok_owner`/`potok_runtime` прошли проверки привилегий.
- Backup/restore drill прошёл: `database.dump` и `documents.tar.gz` совпали с SHA-256; восстановленная БД имеет head `0032_processing_quality_rls` и 44 таблицы; документный sentinel восстановлен.
- Единственный известный blocker PR gate: lockfile candidate не включён в ветку. Production readiness не подтверждена; **NO-GO** до committed lockfile и зелёного release workflow.

## Frontend lockfile и полный Release Gate — commit add8210

- Добавлен npm-generated `frontend/package-lock.json` v3 из кандидата, созданного и проверенного GitHub runner. SHA-256: `96491406B390CDA4336CE8DFBED6920362748AB83FCCDA98815F39FC425B6714`.
- Frontend gate на закоммиченном lockfile: `npm ci` добавил 70 пакетов, npm audit проверил 71 пакет без high vulnerabilities, `npm run build` успешно завершился.
- Полный GitHub Actions Release Gate завершился **success**: PostgreSQL 16 migrations/RLS/backend QA, frontend reproducible build, committed-lockfile check и Docker Compose smoke.
- Compose smoke проверил API/web через loopback reverse proxy, least-privilege DB роли, SHA-256 backup обоих архивов, PostgreSQL restore на `0032_processing_quality_rls` (44 таблицы) и восстановление файлового sentinel.
- CI-блокеры закрыты. Production readiness не заявляется: browser E2E, независимый security review, функциональная и юридическая/hosting приёмка остаются отдельными воротами. PR #1 не слит, production deployment не выполнялся.

## Актуальное состояние — 2026-11-09, commit d736f94db43a6120f557f3125a90fea408ecebf7

GitHub Actions Release Gate run [42593724186](https://github.com/Matrosov142/-CRM/actions/runs/42593724186) завершился успешно: PostgreSQL 16 migration/RLS/backend QA, frontend committed lockfile/npm ci/audit/build, lockfile assertion и Docker Compose health/roles/backup/restore. Ранее приведённые локальные ограничения и промежуточные падения ниже являются историей, а не текущим состоянием этих ворот. Открытыми остаются browser E2E, независимый security review, функциональная и юридическая/hosting приёмка. PR #1 не слит; production deployment не выполнялся.

## Состояние контрольных ворот — 2026-11-09

- Текущий head `5c200aebed06d2742263e13d65f42d6182d92ab4` ожидает CI. Последний завершённый Release Gate [42600832811](https://github.com/Matrosov142/-CRM/actions/runs/42600832811), head `e4fa14870e97b2dc66bc93e0cf22551527430ff6`: backend/PostgreSQL/RLS, frontend `npm ci`/audit/build, lockfile assertion и Compose/backup/restore прошли; Browser E2E упал при создании procurement draft.
- Подтверждённая причина: первоначальный `total_amount=0.00` нарушал `ck_procurement_order_amount_positive` во время flush. Сумма теперь считается до INSERT; регрессионный контракт добавлен. Повторное подтверждение E2E ожидается.
- Браузерным Chromium уже реально проверены регистрация, cookie и security headers, создание тендера/позиции, экранирование XSS-payload, CSRF отказ. RFQ detail теперь включает `id` строки для дальнейшего предложения и выбора.
- Исправлен дефект Post-commit refresh при transaction-local RLS: tenant context восстанавливается до перечитывания тендера/позиции/калькуляции.
- Не заявлены успешными: полный браузерный бизнес-поток, независимый security review, функциональная бизнес-приёмка и юридический/hosting review.

**Решение:** остаётся **NO-GO**, `production_ready=false`; PR №1 не слит, deployment не выполнялся.
