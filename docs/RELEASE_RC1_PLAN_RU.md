# ПОТОК CRM — план допуска к Release Candidate 1

**Текущая базовая версия:** `0.25.0-pilot`  
**Статус:** полный GitHub Actions Release Gate `PASS` на source commit `376066927eb96aa037a18a1bc5f66dd0e41b7b4f` (run 42605391256); CI run 42605391146 также `PASS`. Общий допуск к пилоту с рабочими данными остаётся `NO-GO` до независимой security review, формальной бизнес-приёмки и legal/hosting review.
**Правило:** ни один пункт не закрывается по наличию кода или статическому анализу. Нужен воспроизводимый лог успешной проверки.

## 1. Контрольные ворота RC1

| Ворота | Что считается доказательством | Текущий статус |
|---|---|---|
| Backend regression | Полный QA runner, все тесты, включая PostgreSQL suite | PASS в GitHub Actions run 42605391256: 58 test files, PostgreSQL included |
| PostgreSQL migrations | Чистая PostgreSQL 16 DB: `alembic upgrade head`; повторный запуск без ошибок | PASS: upgrade выполнен дважды |
| Least privilege | `potok_runtime` не владелец, не SUPERUSER, без BYPASSRLS; права проверены SQL | PASS в Compose smoke |
| Tenant isolation | Положительные и отрицательные cross-tenant тесты по tenant-owned сущностям | RLS matrix и PostgreSQL integration прошли в CI |
| Frontend | Зафиксированный `package-lock.json`, `npm ci`, `npm run build` | PASS: lockfile закоммичен, npm ci, audit и build прошли |
| Docker | Успешные сборки API и web образов, запуск с PostgreSQL, healthchecks | PASS: Compose smoke, API/web loopback health прошли |
| Browser E2E | Регистрация/вход/выход, CSRF/Origin, роли, критические бизнес-потоки | PASS в run 42605391256: real Chromium через disposable Compose/nginx |
| Backup/restore | Восстановление БД и файлов из резервной копии в чистую среду | PASS: SHA-256, head `0033_company_registration_rls`, 44 таблицы, документный sentinel |
| Security | Автоматизированные и браузерные проверки пройдены; независимый pentest/review | Технические проверки PASS; независимая оценка pending |
| Legal / hosting | Юридическая проверка 152-ФЗ, локализации, договоров и выбранного российского хостинга | Не проверено |
| Functional acceptance | Синтетический E2E поток тендер→закупка→склад→доставка→финансы/документы; формальная подпись владельца процесса | Автотест PASS; внешняя бизнес-подпись pending |

## 2. Автоматизация

Добавлен workflow `.github/workflows/release-gate.yml`:

- поднимает disposable PostgreSQL 16;
- применяет все миграции с нуля;
- создаёт отдельную runtime-роль без SUPERUSER/BYPASSRLS;
- запускает штатный QA runner с PostgreSQL integration tests;
- требует committed `frontend/package-lock.json`, выполняет `npm ci` и production build;
- собирает API и frontend Docker images.

Workflow намеренно не пропускает frontend gate при отсутствии lockfile. Для CI используется только временная тестовая БД и тестовые пароли; production secrets туда передавать нельзя.

## 3. Очерёдность закрытия блокеров

1. Выполнено: committed lockfile v3; `npm ci`, `npm audit --audit-level=high` (0 уязвимостей) и production build прошли в Release Gate.
2. Выполнено: PostgreSQL 16 миграции применены дважды; RLS matrix/backend QA и dependency audit прошли в run 42605391256.
3. Выполнено: CI PostgreSQL RLS matrix проверяет все tenant-owned таблицы; Browser E2E дополнительно проверил cross-company изоляцию тендера. Для полного security sign-off всё ещё нужна независимая оценка.
4. Compose build/start, API/web health, DB roles и backup/restore drill прошли в GitHub Actions. Полный пилотный хост с мониторингом/восстановлением ещё требует инфраструктурного испытания.
5. Выполнено для disposable Compose/nginx без TLS: Browser E2E PASS. Настоящий production-like TLS/reverse proxy сценарий ещё не проверен.
6. Выполнено в disposable CI: checksum БД/файлов, DB restore на revision 0033 (44 таблицы), document sentinel PASS. Время RTO/RPO для целевой инфраструктуры не измерено.
7. Провести функциональную приёмку по реальным пользовательским сценариям и юридическую проверку до подключения клиентских данных.

## 4. Запреты

- До закрытия всех обязательных ворот `production_ready` остаётся `false`.
- Не использовать реальные клиентские данные в тестах и CI.
- Не подключать ЭТП автоматически: каждый коннектор остаётся выключенным до проверки официального API, договорных разрешений и безопасной авторизации.
- Не разворачивать персональные данные российских клиентов на инфраструктуре за пределами РФ без отдельной юридической оценки.
- Не считать зелёные unit/static tests доказательством безопасности или готовности к коммерческой эксплуатации.

## 5. Условия объявления RC1

RC1 допускается только после зелёного CI по backend/PostgreSQL, frontend и Docker; полного RLS matrix; браузерных E2E; успешного backup/restore drill; функциональной приёмки; закрытия юридических и инфраструктурных вопросов. Каждый результат должен иметь дату, commit SHA и приложенный лог.


## Дополнение к release gate (следующая инженерная итерация)

- Миграции PostgreSQL 16 выполняются дважды подряд: проверка чистого upgrade и повторного `upgrade head` без изменений схемы.
- Добавлен `test_postgres_rls_matrix.py`: проверяет все таблицы с `company_id` на включённый и принудительный RLS, наличие политик и привязку политик к tenant context. `auth_sessions` явно исключена как pre-tenant таблица: доступ к ней должен ограничиваться субъектом JWT, компанией и JTI в прикладном коде.
- Docker gate переведён с простой сборки образов на запуск полного `compose.pilot.yml`, проверку API readiness через nginx и web health endpoint, затем уничтожение временных томов.
- Offline QA после изменений: 202 теста PASS в 54 выбранных файлах; 141 Python-файл compileall PASS; статический аудит PASS.
- PostgreSQL RLS matrix фактически не запускалась в текущей среде: `psycopg`, PostgreSQL и disposable test DB отсутствуют. Frontend lockfile отсутствует, поэтому `npm ci` и production build остаются блокером. Docker runtime недоступен локально.
- Поэтому статус RC1 остаётся NO-GO до зелёного CI и приложенных runtime-логов.


## Дополнение: dependency, backup и artifact gates

- Backend CI запускает `pip-audit -r requirements.txt`; frontend CI запускает `npm audit --audit-level=high` после `npm ci`.
- Backend QA log и JSON report публикуются как отдельный CI artifact для аудита результата.
- Docker contexts исключают `.env*`, backups, `.git`, тесты и локальные build artifacts.
 - Docker smoke job запускает штатный `ops/backup-pilot.sh`, проверяет SHA-256, восстанавливает dump в отдельную БД, сверяет Alembic head с `0032_processing_quality_rls`, проверяет число таблиц и восстанавливает тестовый файл из документового архива.
- Исправлен путь tar-архива документов и добавлена утилита `tar` в API image.
- Все новые процедуры требуют фактического зелёного workflow. Локальные offline PASS не закрывают эти ворота.


## Текущий локальный preflight после hardening

- 207 тестов PASS в 55 выбранных тестовых файлах.
- 142 Python-файла проходят compileall.
- Статический release audit PASS.
- Workflow YAML успешно разбирается; все shell-блоки `run:` проходят `bash -n`.
- `.gitignore` исправлен; Docker build contexts исключают `.env*` и локальные артефакты.
- Backup script теперь архивирует правильный каталог документов; в API image явно установлен `tar`.
- CI содержит dependency audits и автоматический backup/restore drill, но эти удалённые процедуры ещё не исполнялись.
- Frontend lockfile отсутствует; backend dependencies также пока заданы диапазонами, а не полным hash-locked набором.
- PostgreSQL 16, RLS, Docker, production build, backup/restore и security audit не закрыты до фактического CI-run с сохранёнными логами.

**Решение:** NO-GO. Это локально проверенная подготовительная сборка, не релиз и не доказательство runtime-готовности.

## Обновлённый статус GitHub Actions — 2026-11-09

- Commit `2035a78`: Backend + PostgreSQL 16 + RLS прошёл; Alembic upgrade дважды, полный QA runner, RLS matrix и pip-audit успешны.
- Frontend прошёл `npm ci`, `npm audit --audit-level=high` и production build на временном npm-generated lockfile после обновления Vite до 6.4.5. Отдельный gate подтверждает, что `frontend/package-lock.json` пока не закоммичен; это остаётся блокером воспроизводимого релизного билда.
- Docker образы собрались с временным lockfile, но `db-migrate` падал при импорте Settings из-за отсутствующих `DATABASE_URL` и `JWT_SECRET`. Это подтверждённое окружение/Compose несоответствие исправлено в `compose.pilot.yml`; повторный CI ещё ожидается.
- Backup/restore drill не запускался, так как stack не прошёл миграцию. Не считать Docker или backup gate пройденными до зелёного workflow и сохранённых логов.

**Текущий статус:** NO-GO до committed lockfile и полного успешного Docker/backup-restore прогона. Production deployment запрещён.


## PostgreSQL privilege separation — обязательная проверка

- Новая установка создаёт `potok_admin` как единственную административную роль PostgreSQL.
- Alembic выполняется от `potok_owner` с `NOSUPERUSER`, `NOBYPASSRLS`, `NOCREATEDB`, `NOCREATEROLE`.
- FastAPI подключается только как `potok_runtime`; эта роль не владеет таблицами, не SUPERUSER и не BYPASSRLS.
- CI проверяет отсутствие SUPERUSER/BYPASSRLS у owner/runtime и подтверждает, что таблицы принадлежат owner.
- Для старых пилотных БД предусмотрен upgrade path от прежнего superuser `potok_owner` к отдельному `potok_admin`. Перед реальным обновлением требуется backup и проверка на копии существующего volume.


## Уточнение по текущему QA

После изменения модели PostgreSQL ролей локальный offline QA: 209 PASS / 55 файлов, compileall 142 Python-файла PASS, static audit PASS. Интеграционные тесты PostgreSQL исключены локально, но включены в CI. Это не закрывает PostgreSQL gate.

- Создание первого директора использует отдельную административную роль только в явно запускаемой one-time CLI-команде; обычные API-запросы остаются на `potok_runtime`.


## Изоляция привилегированных задач от API

- `db-bootstrap` — отдельный одноразовый Compose-сервис, которому доступен только на время старта пароль `potok_admin`; он создаёт/обновляет роли и завершает работу.
- `db-migrate` — отдельный одноразовый сервис для Alembic от имени `potok_owner` и выдачи прав runtime-роли.
- Постоянный `api` получает только runtime `DATABASE_URL` и JWT secret; он не получает DB admin password, schema-owner password или migration URL.
- После успешного старта `pilot-up.sh` удаляет завершившиеся bootstrap/migration containers, чтобы их environment не оставался в Docker metadata.
- Создание первого директора запускается отдельным одноразовым `db-bootstrap` контейнером с временной передачей DB admin password; секрет не передаётся работающему API.
- CI дополнительно проверяет отсутствие DB admin/owner credentials в environment API-контейнера.


## Final container privilege boundary

- `db-bootstrap`: short-lived service receives only PostgreSQL admin + role passwords; creates roles/default privileges and exits.
- `db-migrate`: short-lived service receives only schema-owner/runtime credentials; applies Alembic and grants runtime access, then exits.
- `api`: long-running service receives only `DATABASE_URL` for `potok_runtime` plus application secrets. It receives neither `DB_ADMIN_PASSWORD`, `DB_OWNER_PASSWORD`, nor `MIGRATION_DATABASE_URL`.
- First director creation is an explicit one-off command using the `db-bootstrap` service, not the running API container.

Последний локальный offline QA: 212 PASS / 55 файлов; 142 Python-файла compileall PASS; release audit, workflow YAML и shell syntax PASS. Интеграционные и frontend/runtime gates не исполнялись.


## Финальный локальный preflight этой итерации

- 212 тестов PASS в 55 выбранных файлах; два PostgreSQL integration test-файла пропущены из-за отсутствия локального PostgreSQL/psycopg.
- 142 Python-файла compileall PASS; статический release audit PASS.
- Compose YAML разобран; все shell-блоки CI workflow и скрипты прошли `bash -n`.
- `pilot-up.sh` smoke-tested с подменёнными Docker/OpenSSL командами: создаёт четыре отдельных значения `.env.pilot`, файл имеет права `0600`.
- Docker runtime, PostgreSQL RLS, npm production build, dependency audits и backup/restore в этой среде не исполнялись. Требуется реальный GitHub Actions run.
- Статус релиза остаётся **NO-GO**.

Локальный offline QA после финального разделения сервисов: 212 PASS / 55 файлов; 142 Python-файла compileall PASS; статический аудит, YAML и shell syntax PASS. Runtime ворота остаются открыты до выполнения CI.

## Технический preflight 2026-11-09

- Исходный архив v0.25.2 открыт и распакован в рабочую копию; каталог `sources/` не менялся.
- Обнаружен дефект release workflow: конвейер QA через `tee` мог вернуть успешный код `tee`, скрыв падение QA. Добавлен `set -o pipefail` и контрактная проверка.
- `frontend/package.json` фиксирует версии прямых зависимостей, но `frontend/package-lock.json` и альтернативного lockfile нет. В среде есть Node.js и pnpm, но `npm` отсутствует; создать lockfile для `npm ci` здесь нельзя. Не генерировать фиктивный lock.
- Python/pytest, Bash, PostgreSQL client/server и Docker CLI недоступны. Backend тесты, compileall, YAML/shell tooling, PostgreSQL/RLS, npm ci/build и Compose smoke не запускались.
- Требуется создать npm lockfile в среде с npm и затем выполнить release workflow. Статус остаётся **NO-GO**.

## Дополнение по Compose ingress — 2026-11-09

- Последний успешный этап Compose: образы собраны, PostgreSQL bootstrap и migrations прошли, API healthcheck стал healthy.
- Host-side проверка показала отказ подключения к `127.0.0.1:18080`; `docker compose ps` не показывал published host port для `web`, поэтому role separation и backup/restore проверки были пропущены.
- В ветке разделена внутренняя сеть `backend` (DB/API) и `ingress` (только web вместе с backend для проксирования); web host binding остаётся loopback-only. Добавлен контрактный тест Compose.
- Повторный Actions run ожидается. Не считать опубликование web-порта, Docker smoke или backup/restore закрытыми.

## Docker and backup gate update — 2026-11-09

GitHub Actions commit `f95f478` passed image build, Compose startup/migrations, host-side API and web health, and DB role separation. Backup drill did not start: the tracked script is mode `100644` and workflow attempted direct execution (`Permission denied`). The gate now invokes it through Bash, as documented in this runbook. Checksums and database/document restore remain open pending CI. Frontend npm install/audit/build passed with a temporary generated lock; committed lockfile gate still fails.

## Текущий результат release gate — 2026-11-09, commit `212aadf`

| Ворота | Результат |
|---|---|
| PostgreSQL 16 migrations, повторный upgrade, release QA, RLS matrix, pip-audit | PASS |
| Frontend npm ci, npm audit high, production build на runner-generated lockfile candidate | PASS |
| Committed `frontend/package-lock.json` | FAIL — отсутствует в ветке |
| Compose build/start, API/web loopback health, разделение DB ролей | PASS |
| Backup SHA-256 и PostgreSQL/document restore | PASS — head `0032_processing_quality_rls`, 44 таблицы, sentinel PASS |
| Production readiness | NO-GO — reproducible committed frontend lockfile gate remains open |

Temporary npm candidate artifact: `13660698809`. Он подтверждает генерацию и тестирование настоящего lockfile через npm, но пока не входит в ветку.

## Результат полного Release Gate — 2026-11-09, commit `add8210`

Все job полного workflow завершились успешно: PostgreSQL/backend/RLS, frontend reproducible build, проверка committed lockfile и Docker Compose smoke. Закоммиченный npm lockfile v3 прошёл `npm ci`, `npm audit --audit-level=high` и production build. Backup/restore подтвердил SHA-256, восстановление БД на `0032_processing_quality_rls` (44 таблицы) и восстановление документного sentinel.

CI Release Gate: **PASS**. Общий статус допуска RC1/production: **NO-GO** до browser E2E, независимого security review, функциональной и юридической/hosting приёмки. PR остаётся открытым и не слит в `main`.

## Исторический статус на commit d736f94 (до E2E)

GitHub Actions Release Gate run [42593724186](https://github.com/Matrosov142/-CRM/actions/runs/42593724186) завершился успешно: PostgreSQL 16 migration/RLS/backend QA, frontend committed lockfile/npm ci/audit/build, lockfile assertion и Docker Compose health/roles/backup/restore. Ранее приведённые локальные ограничения и промежуточные падения ниже являются историей, а не текущим состоянием этих ворот. Открытыми остаются browser E2E, независимый security review, функциональная и юридическая/hosting приёмка. PR #1 не слит; production deployment не выполнялся.

## Исторический статус проверки до полного Browser E2E

На той промежуточной точке source commit `5c200aebed06d2742263e13d65f42d6182d92ab4` ожидал проверки; run 42600832811 подтвердил ошибку нулевой суммы закупки. Исправление было внесено после этого снимка. Последующая итоговая проверка приведена ниже.

Промежуточный Chromium прогон подтверждал только начальные этапы. Полный сквозной E2E ещё не был пройден на этом историческом снимке.

Статус на промежуточном снимке был **NO-GO**; ниже приведён новый подтверждённый Release Gate. `production_ready=false`; PR #1 открыт, не слит; production deployment не выполнялся.


## Актуальный результат — 2026-11-09

Release Gate [42605391256](https://github.com/Matrosov142/-CRM/actions/runs/42605391256) прошёл все пять заданий на source commit `376066927eb96aa037a18a1bc5f66dd0e41b7b4f`; CI run [42605391146](https://github.com/Matrosov142/-CRM/actions/runs/42605391146) тоже успешен. Подтверждены backend/PostgreSQL 16/RLS, 58 выбранных тестовых файлов, compileall 146 Python-файлов, статический аудит, npm ci/audit/build, real Chromium E2E и Docker Compose/backup/restore. Восстановленная БД: `0033_company_registration_rls`, 44 таблицы; файловый sentinel восстановлен.

Browser E2E прошёл синтетический поток: регистрация и cookie-сессия, CSRF/Origin, роли и tenant isolation; тендер/позиция, RFQ/offer и согласование закупки, две частичные приёмки с браком, резерв из нескольких партий, частичная отгрузка, план/факт доставки и variance, подтверждение платежа, загрузка/скачивание PDF. Денежные суммы и остатки проверены decimal assertions. Это автоматизированная техническая приёмка; формальное одобрение владельца бизнеса не получено.

Подтверждённые дефекты исправлены отдельными коммитами: восстановление transaction-local RLS контекста после commit перед ORM refresh; возврат ID строк RFQ и закупки; вычисление суммы закупки до вставки под положительным DB constraint; разделение employee id и membership id; безопасная строковая сериализация Decimal в JSONB audit details. Регрессионные проверки добавлены.

Независимый pentest/security sign-off, тест на реальной TLS инфраструктуре, юридическая оценка 152-ФЗ/локализации и формальная бизнес-приёмка остаются внешними/отдельными воротами. Статус допуска с реальными данными **NO-GO**, `production_ready=false`; PR #1 остаётся открытым и неслитым.

## Предпилотные действия — 2026-11-10

Пошаговые критерии и подтверждённые ограничения собраны в [контрольном листе допуска](RC1_PRE_PILOT_ACCEPTANCE_RU.md). Отдельно учтены TLS/production-like инфраструктура, backup encryption/retention и замер RPO/RTO, бизнесовая сверка сумм/остатков/частичных поставок, известные демонстрационные KPI и обязательная юридическая/hosting приёмка. Локальная проверка выявила некорректную кодировку QA JSON и риск подмены CI-отчёта неполным локальным префлайтом; исправление прошло новый CI gate (run 35) и CI (run 75); issue закрыт.
