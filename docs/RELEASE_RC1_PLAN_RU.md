# ПОТОК CRM — план допуска к Release Candidate 1

**Текущая базовая версия:** `0.25.0-pilot`  
**Статус:** `NO-GO` — подготовка к RC1, не коммерческий релиз.  
**Правило:** ни один пункт не закрывается по наличию кода или статическому анализу. Нужен воспроизводимый лог успешной проверки.

## 1. Контрольные ворота RC1

| Ворота | Что считается доказательством | Текущий статус |
|---|---|---|
| Backend regression | Полный QA runner, все тесты, включая PostgreSQL suite | Частично: 197 тестов; PostgreSQL suite не запускался |
| PostgreSQL migrations | Чистая PostgreSQL 16 DB: `alembic upgrade head`; повторный запуск без ошибок | Не проверено |
| Least privilege | `potok_runtime` не владелец, не SUPERUSER, без BYPASSRLS; права проверены SQL | Не проверено |
| Tenant isolation | Положительные и отрицательные cross-tenant тесты по tenant-owned сущностям | Частично: есть базовый RLS test, не покрывает все домены |
| Frontend | Зафиксированный `package-lock.json`, `npm ci`, `npm run build` | Блокер: lockfile отсутствует |
| Docker | Успешные сборки API и web образов, запуск с PostgreSQL, healthchecks | Не проверено; локальный Docker недоступен |
| Browser E2E | Регистрация/вход/выход, CSRF/Origin, роли, критические бизнес-потоки | Не проверено |
| Backup/restore | Восстановление БД и файлов из резервной копии в чистую среду | Не проверено |
| Security | Проверка секретов, CORS, cookies, загрузок/скачиваний, tenant boundaries; независимый pentest | Не проверено |
| Legal / hosting | Юридическая проверка 152-ФЗ, локализации, договоров и выбранного российского хостинга | Не проверено |
| Functional acceptance | Подписанные сценарии тендеров, закупок, склада, логистики, финансов и документов | Не проверено |

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

1. Сгенерировать и закоммитить `frontend/package-lock.json` командой `npm install --package-lock-only` в среде с доступом к npm registry; затем проверить `npm ci && npm run build`.
2. Запустить release workflow и исправить все ошибки PostgreSQL migrations/RLS, не ослабляя политики ради зелёного теста.
3. Расширить RLS matrix на документы, вложения, тендеры, закупки, складские партии/резервы/отгрузки, финансы, согласования и транспортные расходы. Для каждого домена нужны тесты чтения, создания, изменения и доступа по чужому ID.
4. Запустить Docker Compose на чистом Linux-хосте, проверить healthchecks, перезапуск, volumes, логи и shutdown.
5. Добавить браузерные E2E сценарии и проверить cookie/CSRF/Origin поведение через реальный reverse proxy с TLS.
6. Выполнить backup/restore drill: БД плюс файловое хранилище; зафиксировать время восстановления и контроль целостности.
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
- Docker smoke job запускает штатный `ops/backup-pilot.sh`, проверяет SHA-256, восстанавливает dump в отдельную БД, сверяет Alembic head с `0031_rfq_tender_position_link`, проверяет число таблиц и восстанавливает тестовый файл из документового архива.
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
